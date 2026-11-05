"""
Tests for SafeSphere AI — OSM Facility Ingestion Adapter
Run: pytest backend/tests/test_osm_adapter.py -v
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.ingestion.osm_adapter import (
    FACILITY_TAGS,
    REGIONS,
    FacilityType,
    IngestionResult,
    OSMFacility,
    OSMFacilityAdapter,
    OverpassClient,
    _clean_phone,
    _compute_quality_score,
    _extract_lat_lon,
    build_overpass_query,
    parse_osm_element,
    parse_overpass_response,
)


# ---------------------------------------------------------------------------
# Fixtures — sample Overpass API data
# ---------------------------------------------------------------------------

def make_node(
    osm_id: int = 123456789,
    amenity: str = "police",
    lat: float = 28.6139,
    lon: float = 77.2090,
    name: str = "Connaught Place Police Station",
    phone: str = "011-23341234",
    **extra_tags: str,
) -> Dict[str, Any]:
    tags = {
        "amenity": amenity,
        "name": name,
        "phone": phone,
        **extra_tags,
    }
    return {"type": "node", "id": osm_id, "lat": lat, "lon": lon, "tags": tags}


def make_way(
    osm_id: int = 987654321,
    amenity: str = "hospital",
    center_lat: float = 28.5672,
    center_lon: float = 77.2100,
    name: str = "AIIMS Delhi",
) -> Dict[str, Any]:
    return {
        "type": "way",
        "id": osm_id,
        "center": {"lat": center_lat, "lon": center_lon},
        "tags": {"amenity": amenity, "name": name},
    }


def make_overpass_response(elements: list) -> Dict[str, Any]:
    return {"version": 0.6, "elements": elements}


# ---------------------------------------------------------------------------
# Tests: build_overpass_query
# ---------------------------------------------------------------------------

class TestBuildOverpassQuery:
    def test_contains_bbox(self):
        query = build_overpass_query((28.40, 76.83, 28.88, 77.35), ["police"])
        # Python may render 28.40 as "28.4" (trailing zero stripped) — accept both
        assert ("28.40,76.83,28.88,77.35" in query or "28.4,76.83,28.88,77.35" in query)

    def test_contains_amenity_tag(self):
        query = build_overpass_query((28.40, 76.83, 28.88, 77.35), ["police", "hospital"])
        assert "police" in query
        assert "hospital" in query

    def test_output_format_json(self):
        query = build_overpass_query((28.40, 76.83, 28.88, 77.35), ["police"])
        assert "[out:json]" in query

    def test_includes_node_way_relation(self):
        query = build_overpass_query((28.40, 76.83, 28.88, 77.35), ["police"])
        assert "node" in query
        assert "way" in query
        assert "relation" in query

    def test_out_center_for_way_centroids(self):
        query = build_overpass_query((28.40, 76.83, 28.88, 77.35), ["hospital"])
        assert "out center" in query


# ---------------------------------------------------------------------------
# Tests: _extract_lat_lon
# ---------------------------------------------------------------------------

class TestExtractLatLon:
    def test_node_direct_coordinates(self):
        element = {"type": "node", "id": 1, "lat": 28.6, "lon": 77.2, "tags": {}}
        lat, lon = _extract_lat_lon(element)
        assert lat == 28.6
        assert lon == 77.2

    def test_way_uses_center(self):
        element = {
            "type": "way",
            "id": 2,
            "center": {"lat": 28.5, "lon": 77.1},
            "tags": {},
        }
        lat, lon = _extract_lat_lon(element)
        assert lat == 28.5
        assert lon == 77.1

    def test_way_without_center_returns_none(self):
        element = {"type": "way", "id": 3, "tags": {}}
        lat, lon = _extract_lat_lon(element)
        assert lat is None
        assert lon is None

    def test_relation_uses_center(self):
        element = {
            "type": "relation",
            "id": 4,
            "center": {"lat": 28.9, "lon": 77.05},
            "tags": {},
        }
        lat, lon = _extract_lat_lon(element)
        assert lat == 28.9
        assert lon == 77.05


# ---------------------------------------------------------------------------
# Tests: _clean_phone
# ---------------------------------------------------------------------------

class TestCleanPhone:
    def test_none_returns_none(self):
        assert _clean_phone(None) is None

    def test_empty_string_returns_none(self):
        assert _clean_phone("") is None

    def test_too_short_returns_none(self):
        assert _clean_phone("123") is None

    def test_valid_phone_trimmed(self):
        result = _clean_phone("  011-23341234  ")
        assert result == "011-23341234"

    def test_valid_mobile_kept(self):
        result = _clean_phone("+91 98765 43210")
        assert result is not None
        assert "98765" in result

    def test_long_phone_truncated_to_50(self):
        long_phone = "0" * 60
        result = _clean_phone(long_phone)
        assert result is not None
        assert len(result) <= 50


# ---------------------------------------------------------------------------
# Tests: parse_osm_element
# ---------------------------------------------------------------------------

class TestParseOSMElement:
    def test_valid_police_node(self):
        element = make_node(amenity="police")
        facility = parse_osm_element(element, "delhi")
        assert facility is not None
        assert facility.facility_type == FacilityType.POLICE_STATION
        assert facility.osm_type == "node"
        assert facility.osm_id == 123456789
        assert facility.latitude == 28.6139
        assert facility.longitude == 77.2090
        assert facility.name == "Connaught Place Police Station"
        assert facility.source_verified is False
        assert facility.region == "delhi"

    def test_valid_hospital_way(self):
        element = make_way(amenity="hospital")
        facility = parse_osm_element(element, "delhi")
        assert facility is not None
        assert facility.facility_type == FacilityType.HOSPITAL
        assert facility.osm_type == "way"
        assert facility.latitude == 28.5672

    def test_fire_station_parsed(self):
        element = make_node(amenity="fire_station", name="Shahdara Fire Station")
        facility = parse_osm_element(element, "delhi")
        assert facility is not None
        assert facility.facility_type == FacilityType.FIRE_STATION

    def test_pharmacy_parsed(self):
        element = make_node(amenity="pharmacy", name="Apollo Pharmacy")
        facility = parse_osm_element(element, "sonipat")
        assert facility is not None
        assert facility.facility_type == FacilityType.PHARMACY

    def test_unknown_amenity_returns_none(self):
        element = make_node(amenity="restaurant")
        facility = parse_osm_element(element, "delhi")
        assert facility is None

    def test_node_without_coordinates_returns_none(self):
        element = {"type": "node", "id": 999, "tags": {"amenity": "police", "name": "X"}}
        # No lat/lon
        facility = parse_osm_element(element, "delhi")
        assert facility is None

    def test_way_without_center_returns_none(self):
        element = {"type": "way", "id": 888, "tags": {"amenity": "hospital", "name": "Y"}}
        facility = parse_osm_element(element, "delhi")
        assert facility is None

    def test_out_of_bounds_coordinates_returns_none(self):
        element = make_node(lat=0.0, lon=0.0)  # Not India
        facility = parse_osm_element(element, "delhi")
        assert facility is None

    def test_hindi_name_extracted(self):
        element = make_node(**{"name:hi": "कनॉट प्लेस थाना"})
        facility = parse_osm_element(element, "delhi")
        assert facility is not None
        assert facility.name_hi == "कनॉट प्लेस थाना"

    def test_address_fields_extracted(self):
        element = make_node(
            **{
                "addr:street": "Connaught Place",
                "addr:city": "New Delhi",
                "addr:postcode": "110001",
            }
        )
        facility = parse_osm_element(element, "delhi")
        assert facility is not None
        assert facility.addr_street == "Connaught Place"
        assert facility.addr_city == "New Delhi"
        assert facility.addr_postcode == "110001"

    def test_source_id_is_osm_overpass(self):
        element = make_node()
        facility = parse_osm_element(element, "delhi")
        assert facility.source_id == "osm_overpass"

    def test_licence_is_odbl(self):
        element = make_node()
        facility = parse_osm_element(element, "delhi")
        assert "ODbL" in facility.licence

    def test_attribution_contains_osm(self):
        element = make_node()
        facility = parse_osm_element(element, "delhi")
        assert "OpenStreetMap" in facility.attribution


# ---------------------------------------------------------------------------
# Tests: _compute_quality_score
# ---------------------------------------------------------------------------

class TestComputeQualityScore:
    def _make_minimal_facility(self) -> OSMFacility:
        return OSMFacility(
            osm_id=1,
            osm_type="node",
            facility_type=FacilityType.POLICE_STATION,
            latitude=28.6,
            longitude=77.2,
            name="Test PS",
            name_hi=None,
            addr_street=None,
            addr_city=None,
            addr_postcode=None,
            phone=None,
            phone_secondary=None,
            website=None,
            opening_hours_raw=None,
        )

    def test_minimal_facility_scores_40(self):
        f = self._make_minimal_facility()
        assert _compute_quality_score(f) == 40

    def test_with_phone_scores_60(self):
        f = self._make_minimal_facility()
        f.phone = "011-12345678"
        assert _compute_quality_score(f) == 60

    def test_with_address_scores_60(self):
        f = self._make_minimal_facility()
        f.addr_street = "Main Road"
        assert _compute_quality_score(f) == 60

    def test_fully_complete_unverified_scores_80(self):
        f = self._make_minimal_facility()
        f.phone = "011-12345678"
        f.addr_city = "Delhi"
        assert _compute_quality_score(f) == 80

    def test_verified_scores_100(self):
        f = self._make_minimal_facility()
        f.phone = "011-12345678"
        f.addr_city = "Delhi"
        f.source_verified = True
        assert _compute_quality_score(f) == 100

    def test_no_name_scores_zero_baseline(self):
        f = self._make_minimal_facility()
        f.name = None
        # Name missing → baseline 40 not earned
        assert _compute_quality_score(f) == 0


# ---------------------------------------------------------------------------
# Tests: parse_overpass_response
# ---------------------------------------------------------------------------

class TestParseOverpassResponse:
    def test_parses_multiple_elements(self):
        response = make_overpass_response([
            make_node(osm_id=1, amenity="police"),
            make_node(osm_id=2, amenity="hospital"),
            make_node(osm_id=3, amenity="fire_station"),
        ])
        facilities, errors = parse_overpass_response(response, "delhi")
        assert len(facilities) == 3
        assert len(errors) == 0

    def test_skips_invalid_amenity(self):
        response = make_overpass_response([
            make_node(osm_id=1, amenity="police"),
            make_node(osm_id=2, amenity="restaurant"),  # should be skipped
        ])
        facilities, errors = parse_overpass_response(response, "delhi")
        assert len(facilities) == 1

    def test_empty_response(self):
        response = make_overpass_response([])
        facilities, errors = parse_overpass_response(response, "sonipat")
        assert facilities == []
        assert errors == []

    def test_mixes_nodes_and_ways(self):
        response = make_overpass_response([
            make_node(osm_id=1, amenity="police"),
            make_way(osm_id=2, amenity="hospital"),
        ])
        facilities, errors = parse_overpass_response(response, "delhi")
        assert len(facilities) == 2
        types = {f.osm_type for f in facilities}
        assert types == {"node", "way"}


# ---------------------------------------------------------------------------
# Tests: OSMFacilityAdapter.deduplicate
# ---------------------------------------------------------------------------

class TestDeduplicate:
    def _make_facility(self, osm_id: int) -> OSMFacility:
        return OSMFacility(
            osm_id=osm_id,
            osm_type="node",
            facility_type=FacilityType.HOSPITAL,
            latitude=28.6,
            longitude=77.2,
            name="Test",
            name_hi=None,
            addr_street=None,
            addr_city=None,
            addr_postcode=None,
            phone=None,
            phone_secondary=None,
            website=None,
            opening_hours_raw=None,
        )

    def test_removes_exact_osm_id_duplicates(self):
        adapter = OSMFacilityAdapter()
        facilities = [self._make_facility(1), self._make_facility(1), self._make_facility(2)]
        result = adapter.deduplicate(facilities)
        assert len(result) == 2
        assert {f.osm_id for f in result} == {1, 2}

    def test_unique_ids_unchanged(self):
        adapter = OSMFacilityAdapter()
        facilities = [self._make_facility(i) for i in range(5)]
        result = adapter.deduplicate(facilities)
        assert len(result) == 5


# ---------------------------------------------------------------------------
# Tests: OSMFacilityAdapter.ingest_region (mocked HTTP)
# ---------------------------------------------------------------------------

class TestOSMFacilityAdapterIngestion:
    @pytest.mark.asyncio
    async def test_ingest_region_returns_facilities(self):
        mock_response = make_overpass_response([
            make_node(osm_id=101, amenity="police", name="Paharganj PS"),
            make_node(osm_id=102, amenity="hospital", name="RML Hospital"),
            make_node(osm_id=103, amenity="fire_station", name="Karol Bagh FS"),
        ])

        mock_client = MagicMock(spec=OverpassClient)
        mock_client.query = AsyncMock(return_value=mock_response)

        adapter = OSMFacilityAdapter(client=mock_client)
        facilities, result = await adapter.ingest_region("delhi")

        assert len(facilities) == 3
        assert result.valid_count == 3
        assert result.error_count == 0
        assert result.region == "delhi"

    @pytest.mark.asyncio
    async def test_ingest_region_handles_api_failure(self):
        mock_client = MagicMock(spec=OverpassClient)
        mock_client.query = AsyncMock(side_effect=RuntimeError("Overpass timeout"))

        adapter = OSMFacilityAdapter(client=mock_client)
        facilities, result = await adapter.ingest_region("delhi")

        assert facilities == []
        assert result.error_count == 1
        assert "Overpass timeout" in result.errors[0]

    @pytest.mark.asyncio
    async def test_all_returned_facilities_are_not_verified(self):
        """OSM data must NEVER be marked source_verified=True automatically."""
        mock_response = make_overpass_response([
            make_node(osm_id=201, amenity="police", name="Some PS"),
        ])
        mock_client = MagicMock(spec=OverpassClient)
        mock_client.query = AsyncMock(return_value=mock_response)

        adapter = OSMFacilityAdapter(client=mock_client)
        facilities, _ = await adapter.ingest_region("delhi")

        for f in facilities:
            assert f.source_verified is False, (
                f"Facility {f.osm_id} ({f.name}) has source_verified=True — "
                "OSM data must never be auto-marked as officially verified."
            )

    @pytest.mark.asyncio
    async def test_all_facilities_have_attribution(self):
        mock_response = make_overpass_response([
            make_node(osm_id=301, amenity="hospital", name="Safdarjung Hospital"),
        ])
        mock_client = MagicMock(spec=OverpassClient)
        mock_client.query = AsyncMock(return_value=mock_response)

        adapter = OSMFacilityAdapter(client=mock_client)
        facilities, _ = await adapter.ingest_region("delhi")

        for f in facilities:
            assert "OpenStreetMap" in f.attribution
            assert "ODbL" in f.licence

    @pytest.mark.asyncio
    async def test_sonipat_region_ingested(self):
        mock_response = make_overpass_response([
            make_node(
                osm_id=401,
                amenity="police",
                name="Sonipat Sadar PS",
                lat=28.99,
                lon=77.02,
            ),
        ])
        mock_client = MagicMock(spec=OverpassClient)
        mock_client.query = AsyncMock(return_value=mock_response)

        adapter = OSMFacilityAdapter(client=mock_client)
        facilities, result = await adapter.ingest_region("sonipat")

        assert len(facilities) == 1
        assert facilities[0].region == "sonipat"
        assert result.region == "sonipat"

    @pytest.mark.asyncio
    async def test_ingestion_result_tracks_raw_data_hash(self):
        mock_response = make_overpass_response([make_node()])
        mock_client = MagicMock(spec=OverpassClient)
        mock_client.query = AsyncMock(return_value=mock_response)

        adapter = OSMFacilityAdapter(client=mock_client)
        _, result = await adapter.ingest_region("delhi")

        assert result.raw_data_hash  # Non-empty hash
        assert len(result.raw_data_hash) == 64  # SHA-256 hex = 64 chars


# ---------------------------------------------------------------------------
# Tests: REGIONS and FACILITY_TAGS constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_delhi_bbox_bounds(self):
        s, w, n, e = REGIONS["delhi"]
        assert s < n  # south < north
        assert w < e  # west < east
        assert 28.0 <= s <= 29.0
        assert 76.0 <= w <= 78.0

    def test_sonipat_bbox_bounds(self):
        s, w, n, e = REGIONS["sonipat"]
        assert s < n
        assert w < e
        assert 28.0 <= s <= 30.0

    def test_required_facility_tags_present(self):
        required = {"police", "fire_station", "hospital"}
        assert required.issubset(set(FACILITY_TAGS))
