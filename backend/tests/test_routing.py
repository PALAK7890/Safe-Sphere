"""
SafeSphere AI — Phase 3 Tests: Road Network Ingestion, Pedestrian Routing & Safety Scoring
Run: TESTING=true PYTHONPATH=./backend /usr/local/bin/python3.13 -m pytest backend/tests/test_routing.py -v
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RoadNetworkMetadataORM
from app.db.repository import FacilityRepository
from app.db.road_repository import RoadRepository
from app.db.session import async_session_factory, get_db
from app.main import app
from app.models.routing import (
    RoutingPriority,
    SafeRouteRequest,
    SafeRouteResponse,
)
from app.services.routing import (
    PedestrianRoutingEngine,
    interpolate_waypoints,
    is_nighttime_in_india,
)
from ingestion.osm_adapter import FacilityType, OSMFacility
from ingestion.road_adapter import (
    LitStatus,
    OSMRoadAdapter,
    ParsedRoadSegment,
    SidewalkStatus,
    build_road_overpass_query,
    calculate_linestring_length_m,
    compute_baseline_road_safety_score,
    coordinates_to_wkt,
    haversine_distance_m,
    normalize_lit,
    normalize_sidewalk,
    parse_osm_way,
    parse_overpass_road_response,
)

# ---------------------------------------------------------------------------
# Test Fixtures & Samples
# ---------------------------------------------------------------------------

SAMPLE_OVERPASS_WAY = {
    "type": "way",
    "id": 1001,
    "geometry": [
        {"lat": 28.6315, "lon": 77.2167},
        {"lat": 28.6320, "lon": 77.2175},
        {"lat": 28.6325, "lon": 77.2185},
    ],
    "tags": {
        "highway": "pedestrian",
        "name": "Connaught Place Inner Circle Walkway",
        "lit": "yes",
        "surface": "paving_stones",
    },
}

SAMPLE_OVERPASS_UNLIT_WAY = {
    "type": "way",
    "id": 1002,
    "geometry": [
        {"lat": 28.6300, "lon": 77.2150},
        {"lat": 28.6305, "lon": 77.2155},
    ],
    "tags": {
        "highway": "residential",
        "name": "Lane 4",
        "lit": "no",
        "sidewalk": "no",
    },
}


# ---------------------------------------------------------------------------
# Test Suite 1: Road Adapter & Geodesic Math
# ---------------------------------------------------------------------------

class TestRoadAdapterAndMath:
    def test_haversine_distance_known_points(self):
        # Distance between Connaught Place (28.6315, 77.2167) and India Gate (28.6129, 77.2295) ~ 2.4 km
        dist = haversine_distance_m(28.6315, 77.2167, 28.6129, 77.2295)
        assert 2000 < dist < 2600

    def test_calculate_linestring_length(self):
        coords = [(28.6315, 77.2167), (28.6320, 77.2175), (28.6325, 77.2185)]
        length = calculate_linestring_length_m(coords)
        assert length > 50.0

    def test_calculate_linestring_empty_or_single_point(self):
        assert calculate_linestring_length_m([]) == 0.0
        assert calculate_linestring_length_m([(28.0, 77.0)]) == 0.0

    def test_coordinates_to_wkt(self):
        coords = [(28.6315, 77.2167), (28.6320, 77.2175)]
        wkt = coordinates_to_wkt(coords)
        assert wkt.startswith("LINESTRING(")
        # In WKT, lon comes first
        assert "77.2167000 28.6315000" in wkt
        assert "77.2175000 28.6320000" in wkt

    def test_normalize_lit_tags(self):
        assert normalize_lit("yes") == LitStatus.YES.value
        assert normalize_lit("true") == LitStatus.YES.value
        assert normalize_lit("1") == LitStatus.YES.value
        assert normalize_lit("no") == LitStatus.NO.value
        assert normalize_lit("unlit") == LitStatus.NO.value
        assert normalize_lit("24/7") == LitStatus.ALWAYS.value
        assert normalize_lit("automatic") == LitStatus.AUTOMATIC.value
        assert normalize_lit(None) == LitStatus.UNKNOWN.value
        assert normalize_lit("custom_unknown_val") == LitStatus.UNKNOWN.value

    def test_normalize_sidewalk_tags(self):
        # Dedicated footway gets 'both' automatically
        assert normalize_sidewalk(None, "footway") == SidewalkStatus.BOTH.value
        assert normalize_sidewalk(None, "pedestrian") == SidewalkStatus.BOTH.value
        # Roads with explicit tags
        assert normalize_sidewalk("both", "residential") == SidewalkStatus.BOTH.value
        assert normalize_sidewalk("left", "secondary") == SidewalkStatus.LEFT.value
        assert normalize_sidewalk("right", "secondary") == SidewalkStatus.RIGHT.value
        assert normalize_sidewalk("no", "residential") == SidewalkStatus.NO.value
        assert normalize_sidewalk(None, "residential") == SidewalkStatus.UNKNOWN.value

    def test_compute_baseline_road_safety_score(self):
        lit_paved_pedestrian = compute_baseline_road_safety_score(
            highway="pedestrian", lit="yes", sidewalk="both", surface="paving_stones"
        )
        unlit_no_sidewalk_primary = compute_baseline_road_safety_score(
            highway="primary", lit="no", sidewalk="no", surface="asphalt"
        )
        assert lit_paved_pedestrian > 0.80
        assert unlit_no_sidewalk_primary < 0.45
        assert lit_paved_pedestrian > unlit_no_sidewalk_primary

    def test_build_road_overpass_query(self):
        bbox = (28.4, 76.8, 28.8, 77.3)
        query = build_road_overpass_query(bbox)
        assert "[out:json]" in query
        assert "way[\"highway\"~" in query
        assert "out body geom;" in query

    def test_parse_osm_way_valid(self):
        parsed = parse_osm_way(SAMPLE_OVERPASS_WAY, default_district="Delhi Central")
        assert parsed is not None
        assert parsed.osm_way_id == 1001
        assert parsed.name == "Connaught Place Inner Circle Walkway"
        assert parsed.highway == "pedestrian"
        assert parsed.lit == "yes"
        assert parsed.sidewalk == "both"
        assert len(parsed.coordinates) == 3
        assert parsed.length_m > 0
        assert parsed.initial_safety_score > 0.70

    def test_parse_osm_way_rejects_invalid_elements(self):
        # Not a way
        assert parse_osm_way({"type": "node", "id": 999}) is None
        # Non-walkable highway (e.g. motorway)
        assert parse_osm_way({
            "type": "way",
            "id": 998,
            "tags": {"highway": "motorway"},
            "geometry": [{"lat": 28.0, "lon": 77.0}, {"lat": 28.1, "lon": 77.1}],
        }) is None
        # Too few coordinates
        assert parse_osm_way({
            "type": "way",
            "id": 997,
            "tags": {"highway": "residential"},
            "geometry": [{"lat": 28.0, "lon": 77.0}],
        }) is None

    def test_parse_overpass_road_response_deduplication(self):
        resp = {"elements": [SAMPLE_OVERPASS_WAY, SAMPLE_OVERPASS_WAY, SAMPLE_OVERPASS_UNLIT_WAY]}
        parsed_list = parse_overpass_road_response(resp)
        assert len(parsed_list) == 2
        assert {p.osm_way_id for p in parsed_list} == {1001, 1002}


# ---------------------------------------------------------------------------
# Test Suite 2: Road Network Persistence & Spatial Queries
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRoadPersistenceAndSpatialQueries:
    async def test_upsert_batch_and_nearby_query(self):
        seg1 = parse_osm_way(SAMPLE_OVERPASS_WAY, default_district="Delhi Central")
        seg2 = parse_osm_way(SAMPLE_OVERPASS_UNLIT_WAY, default_district="Delhi Central")
        assert seg1 is not None and seg2 is not None

        async with async_session_factory() as session:
            # 1. Upsert batch
            count = await RoadRepository.upsert_batch(session, [seg1, seg2])
            assert count == 2

            # 2. Idempotent re-run
            count_repeat = await RoadRepository.upsert_batch(session, [seg1, seg2])
            assert count_repeat == 2

            # 3. Spatial query nearby Connaught Place point
            nearby = await RoadRepository.get_nearby_roads(
                session=session,
                lat=28.6318,
                lon=77.2170,
                radius_m=500.0,
            )
            assert len(nearby) >= 1
            way_ids = [n["osm_way_id"] for n in nearby]
            assert 1001 in way_ids

            # Check distance and geojson fields
            match = next(n for n in nearby if n["osm_way_id"] == 1001)
            assert match["distance_m"] < 100.0
            assert match["lit"] == "yes"
            assert "coordinates" in match["geojson"]

            # 4. Filter by highway
            filtered = await RoadRepository.get_nearby_roads(
                session=session,
                lat=28.6318,
                lon=77.2170,
                radius_m=500.0,
                highway_filter="pedestrian",
            )
            assert all(f["highway"] == "pedestrian" for f in filtered)

    async def test_recompute_road_scores(self):
        async with async_session_factory() as session:
            updated = await RoadRepository.recompute_incident_scores(session, buffer_m=60.0)
            assert updated >= 0


# ---------------------------------------------------------------------------
# Test Suite 3: Pedestrian Safe Routing Engine
# ---------------------------------------------------------------------------

class TestRoutingEngineCalculations:
    def test_nighttime_detector(self):
        # 14:00 UTC = 19:30 IST (Night)
        night_utc = datetime(2026, 10, 25, 14, 0, tzinfo=timezone.utc)
        assert is_nighttime_in_india(night_utc) is True

        # 05:00 UTC = 10:30 IST (Day)
        day_utc = datetime(2026, 10, 25, 5, 0, tzinfo=timezone.utc)
        assert is_nighttime_in_india(day_utc) is False

    def test_interpolate_waypoints(self):
        start = (28.6315, 77.2167)
        end = (28.6129, 77.2295)
        waypoints = interpolate_waypoints(start, end, steps=4, offset_lat=0.001, offset_lon=0.001)
        assert len(waypoints) == 5
        assert waypoints[0].latitude == start[0]
        assert waypoints[-1].latitude == end[0]
        # Middle waypoint has curvature
        assert waypoints[2].latitude != start[0]

    @pytest.mark.asyncio
    async def test_calculate_routes_comprehensive(self):
        # Seed an emergency facility nearby
        facility = OSMFacility(
            osm_id=999888777,
            osm_type="node",
            facility_type=FacilityType.POLICE_STATION,
            latitude=28.6250,
            longitude=77.2150,  # Nearby Connaught Place corridor
            name="Parliament Street Police Station",
            name_hi="संसद मार्ग पुलिस स्टेशन",
            addr_street="Parliament Street",
            addr_city="New Delhi",
            addr_postcode="110001",
            phone="011-23361100",
            phone_secondary=None,
            website=None,
            opening_hours_raw="24/7",
            source_id="osm_overpass",
            source_verified=True,
        )
        async with async_session_factory() as session:
            await FacilityRepository.ensure_data_source(session)
            await FacilityRepository.upsert_batch(session, [facility])

            engine = PedestrianRoutingEngine(session)
            req = SafeRouteRequest(
                origin_latitude=28.6315,
                origin_longitude=77.2167,
                destination_latitude=28.6129,
                destination_longitude=77.2295,
                prioritize=RoutingPriority.SAFEST,
            )
            response = await engine.calculate_routes(req)

            assert isinstance(response, SafeRouteResponse)
            assert len(response.routes) == 3
            # Emergency disclaimer check
            assert "EMERGENCY NOTICE" in response.disclaimer
            assert "112" in response.disclaimer

            # Route comparisons
            safety_route = next(r for r in response.routes if r.route_id == "route_safety_optimized")
            shortest_route = next(r for r in response.routes if r.route_id == "route_shortest_direct")

            assert safety_route.is_recommended is True
            assert safety_route.overall_safety_index >= shortest_route.overall_safety_index
            assert safety_route.lighting_coverage_pct > shortest_route.lighting_coverage_pct
            assert len(safety_route.waypoints) >= 4
            assert len(safety_route.segments) >= 1


# ---------------------------------------------------------------------------
# Test Suite 4: API Endpoints & Validation
# ---------------------------------------------------------------------------

class TestRoutingAPIEndpoints:
    @pytest.fixture(autouse=True)
    def setup_client(self):
        self.client = TestClient(app)

    def test_compare_routes_endpoint_success(self):
        payload = {
            "origin_latitude": 28.6315,
            "origin_longitude": 77.2167,
            "destination_latitude": 28.6129,
            "destination_longitude": 77.2295,
            "prioritize": "safest",
        }
        res = self.client.post("/api/v1/routing/compare", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "routes" in data
        assert len(data["routes"]) == 3
        assert "disclaimer" in data
        assert "112" in data["disclaimer"]

    def test_compare_routes_rejects_identical_coordinates(self):
        payload = {
            "origin_latitude": 28.6315,
            "origin_longitude": 77.2167,
            "destination_latitude": 28.6315,
            "destination_longitude": 77.2167,
        }
        res = self.client.post("/api/v1/routing/compare", json=payload)
        assert res.status_code == 422
        assert "Origin and destination must be distinct" in res.text

    def test_get_nearby_roads_endpoint(self):
        res = self.client.get(
            "/api/v1/roads/nearby",
            params={"latitude": 28.6315, "longitude": 77.2167, "radius": 1000},
        )
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)

    def test_recompute_scores_requires_auth(self):
        # Missing auth header -> 403
        res = self.client.post("/api/v1/roads/recompute-scores")
        assert res.status_code == 403

        # Invalid auth header -> 403
        res = self.client.post(
            "/api/v1/roads/recompute-scores",
            headers={"X-Moderator-Key": "invalid-secret"},
        )
        assert res.status_code == 403

        # Valid auth header -> 200
        res = self.client.post(
            "/api/v1/roads/recompute-scores",
            headers={"X-Moderator-Key": "safesphere-dev-moderator-key-2026"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert "updated_road_segments" in data
