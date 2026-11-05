"""
SafeSphere AI — Road Network Repository
Handles PostGIS persistence, idempotent batch upserts, spatial corridor queries,
and road safety score recalculation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from geoalchemy2 import Geography
from geoalchemy2.functions import ST_AsGeoJSON, ST_DWithin, ST_Distance, ST_GeomFromText, ST_SetSRID, ST_MakePoint
from sqlalchemy import cast, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    EmergencyFacilityORM,
    IncidentReportORM,
    RoadNetworkMetadataORM,
)
from ingestion.road_adapter import ParsedRoadSegment

logger = logging.getLogger(__name__)


class RoadRepository:
    """Data access layer for road network metadata and pedestrian spatial queries."""

    @staticmethod
    async def upsert_batch(
        session: AsyncSession, segments: List[ParsedRoadSegment]
    ) -> int:
        """
        Idempotently batch upsert road segments.
        If a segment with the same osm_way_id exists, updates geometry and attributes.
        """
        if not segments:
            return 0

        upserted_count = 0
        for seg in segments:
            # Prepare statement with PostGIS geometry
            stmt = (
                pg_insert(RoadNetworkMetadataORM)
                .values(
                    osm_way_id=seg.osm_way_id,
                    name=seg.name,
                    highway=seg.highway,
                    surface=seg.surface,
                    lanes=seg.lanes,
                    maxspeed=seg.maxspeed,
                    lit=seg.lit,
                    sidewalk=seg.sidewalk,
                    oneway=seg.oneway,
                    access=seg.access,
                    geometry=func.ST_GeomFromText(seg.wkt, 4326),
                    length_m=seg.length_m,
                    district=seg.district,
                    safety_score=seg.initial_safety_score,
                    safety_score_updated_at=func.now(),
                    source_fetched_at=func.now(),
                )
                .on_conflict_do_update(
                    index_elements=[RoadNetworkMetadataORM.osm_way_id],
                    set_={
                        "name": seg.name,
                        "highway": seg.highway,
                        "surface": seg.surface,
                        "lanes": seg.lanes,
                        "maxspeed": seg.maxspeed,
                        "lit": seg.lit,
                        "sidewalk": seg.sidewalk,
                        "oneway": seg.oneway,
                        "access": seg.access,
                        "geometry": func.ST_GeomFromText(seg.wkt, 4326),
                        "length_m": seg.length_m,
                        "district": seg.district,
                        "safety_score": seg.initial_safety_score,
                        "safety_score_updated_at": func.now(),
                        "source_fetched_at": func.now(),
                    },
                )
            )
            await session.execute(stmt)
            upserted_count += 1

        await session.commit()
        return upserted_count

    @staticmethod
    async def get_nearby_roads(
        session: AsyncSession,
        lat: float,
        lon: float,
        radius_m: float = 500.0,
        highway_filter: Optional[str] = None,
        lit_filter: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Query road segments within radius_m of a coordinate.
        Calculates distance in metres using geography cast and returns GeoJSON linestring.
        """
        # PostGIS query: ST_DWithin on geography
        point_geog = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326).cast(Geography)
        road_geog = cast(RoadNetworkMetadataORM.geometry, Geography)

        dist_col = func.ST_Distance(road_geog, point_geog).label("distance_m")
        geojson_col = func.ST_AsGeoJSON(RoadNetworkMetadataORM.geometry).label("geojson")

        query = (
            select(
                RoadNetworkMetadataORM.id,
                RoadNetworkMetadataORM.osm_way_id,
                RoadNetworkMetadataORM.name,
                RoadNetworkMetadataORM.highway,
                RoadNetworkMetadataORM.surface,
                RoadNetworkMetadataORM.lanes,
                RoadNetworkMetadataORM.maxspeed,
                RoadNetworkMetadataORM.lit,
                RoadNetworkMetadataORM.sidewalk,
                RoadNetworkMetadataORM.length_m,
                RoadNetworkMetadataORM.district,
                RoadNetworkMetadataORM.incident_count_30d,
                RoadNetworkMetadataORM.incident_count_90d,
                RoadNetworkMetadataORM.safety_score,
                dist_col,
                geojson_col,
            )
            .where(func.ST_DWithin(road_geog, point_geog, radius_m))
        )

        if highway_filter:
            query = query.where(RoadNetworkMetadataORM.highway == highway_filter)
        if lit_filter:
            query = query.where(RoadNetworkMetadataORM.lit == lit_filter)

        query = query.order_by(dist_col.asc()).limit(limit)

        result = await session.execute(query)
        rows = result.all()

        output = []
        for r in rows:
            output.append({
                "id": str(r.id),
                "osm_way_id": r.osm_way_id,
                "name": r.name,
                "highway": r.highway,
                "surface": r.surface,
                "lanes": r.lanes,
                "maxspeed": r.maxspeed,
                "lit": r.lit,
                "sidewalk": r.sidewalk,
                "length_m": r.length_m,
                "district": r.district,
                "incident_count_30d": r.incident_count_30d,
                "incident_count_90d": r.incident_count_90d,
                "safety_score": float(r.safety_score) if r.safety_score is not None else None,
                "distance_m": round(float(r.distance_m), 1),
                "geojson": r.geojson,
            })
        return output

    @staticmethod
    async def get_by_way_id(
        session: AsyncSession, osm_way_id: int
    ) -> Optional[RoadNetworkMetadataORM]:
        """Fetch a single road segment by its OSM Way ID."""
        stmt = select(RoadNetworkMetadataORM).where(
            RoadNetworkMetadataORM.osm_way_id == osm_way_id
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def recompute_incident_scores(
        session: AsyncSession, buffer_m: float = 60.0
    ) -> int:
        """
        Recompute incident_count_30d and safety_score for road segments
        based on approved incidents within buffer_m of road linestrings.
        """
        # PostGIS query associating approved incidents with roads
        update_sql = text("""
            WITH incident_densities AS (
                SELECT
                    r.id AS road_id,
                    COUNT(i.id) FILTER (WHERE i.reported_at >= NOW() - INTERVAL '30 days') AS inc_30d,
                    COUNT(i.id) FILTER (WHERE i.reported_at >= NOW() - INTERVAL '90 days') AS inc_90d
                FROM road_network_metadata r
                LEFT JOIN incident_reports i
                    ON i.moderation_status = 'approved'
                    AND ST_DWithin(r.geometry::geography, i.location::geography, :buffer_m)
                GROUP BY r.id
            )
            UPDATE road_network_metadata r
            SET
                incident_count_30d = idens.inc_30d,
                incident_count_90d = idens.inc_90d,
                safety_score = GREATEST(0.05, LEAST(0.95,
                    -- Base score from lit & sidewalk
                    CASE
                        WHEN r.lit IN ('yes', '24/7', 'automatic') THEN 0.70
                        WHEN r.lit = 'no' THEN 0.35
                        ELSE 0.50
                    END
                    + CASE
                        WHEN r.sidewalk = 'both' THEN 0.15
                        WHEN r.sidewalk IN ('left', 'right') THEN 0.08
                        WHEN r.sidewalk = 'no' THEN -0.10
                        ELSE 0.0
                    END
                    -- Incident penalties
                    - (idens.inc_30d * 0.15)
                    - (idens.inc_90d * 0.05)
                )),
                safety_score_updated_at = NOW()
            FROM incident_densities idens
            WHERE r.id = idens.road_id;
        """)

        res = await session.execute(update_sql, {"buffer_m": buffer_m})
        await session.commit()
        return res.rowcount
