"""
SafeSphere AI — Facility Repository
PostGIS-backed spatial operations and batch ingestion persistence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from geoalchemy2 import Geography
from sqlalchemy import cast, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DataSourceRegistryORM, EmergencyFacilityORM
from ingestion.osm_adapter import OSMFacility

logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    total: int = 0
    valid: int = 0
    persisted: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)


class FacilityRepository:
    """Repository handling all database operations for emergency facilities."""

    @staticmethod
    async def ensure_data_source(
        db: AsyncSession,
        source_id: str = "osm_overpass",
        provider: str = "OpenStreetMap / FOSSGIS e.V.",
        dataset_name: str = "OSM POIs via Overpass API",
        official_url: str = "https://www.openstreetmap.org",
        licence: str = "ODbL 1.0",
        verification_status: str = "A",
        attribution_required: str = "© OpenStreetMap contributors",
    ) -> None:
        """Ensure the parent data source registry record exists to satisfy foreign key."""
        stmt = (
            pg_insert(DataSourceRegistryORM)
            .values(
                source_id=source_id,
                provider=provider,
                dataset_name=dataset_name,
                official_url=official_url,
                access_type="public",
                licence=licence,
                geographic_coverage="national",
                verification_status=verification_status,
                has_coordinates=True,
                commercial_use_permitted=True,
                attribution_required=attribution_required,
                limitations="Community-maintained; NOT officially verified",
                ingestion_adapter="OSMFacilityAdapter",
            )
            .on_conflict_do_nothing(index_elements=["source_id"])
        )
        await db.execute(stmt)
        await db.commit()

    @staticmethod
    def _validate_and_normalize(facility: OSMFacility) -> Optional[Dict[str, Any]]:
        """
        Validate coordinate ranges and required fields.
        Returns a dictionary ready for insertion or None if invalid.
        """
        # Validate coordinates
        if facility.latitude is None or facility.longitude is None:
            return None
        if not (-90.0 <= facility.latitude <= 90.0 and -180.0 <= facility.longitude <= 180.0):
            return None

        # Sanitize name
        name = facility.name
        if not name or not name.strip():
            name = f"Unnamed {facility.facility_type.value.replace('_', ' ').title()}"
        name = name.strip()[:500]

        # Sanitize postcode for CHAR(6)
        postcode = None
        if facility.addr_postcode:
            cleaned = "".join(filter(str.isdigit, facility.addr_postcode))
            if len(cleaned) == 6:
                postcode = cleaned

        facility_type_val = (
            facility.facility_type.value
            if hasattr(facility.facility_type, "value")
            else str(facility.facility_type)
        )

        return {
            "source_id": facility.source_id or "osm_overpass",
            "facility_type": facility_type_val,
            "name": name,
            "name_hi": facility.name_hi[:500] if facility.name_hi else None,
            "addr_street": facility.addr_street[:300] if facility.addr_street else None,
            "addr_city": facility.addr_city[:100] if facility.addr_city else None,
            "addr_district": facility.region.capitalize() if facility.region else None,
            "addr_postcode": postcode,
            "phone": facility.phone[:50] if facility.phone else None,
            "phone_secondary": facility.phone_secondary[:50] if facility.phone_secondary else None,
            "website": facility.website[:500] if facility.website else None,
            "opening_hours_raw": facility.opening_hours_raw[:300] if facility.opening_hours_raw else None,
            "location": func.ST_SetSRID(func.ST_MakePoint(facility.longitude, facility.latitude), 4326),
            "source_verified": False,  # Always False for OSM
            "osm_id": facility.osm_id,
            "osm_type": facility.osm_type,
            "data_quality_score": facility.data_quality_score or 0,
            "source_fetched_at": facility.source_fetched_at or datetime.now(timezone.utc),
            "is_active": True,
        }

    @classmethod
    async def upsert_batch(
        cls,
        db: AsyncSession,
        facilities: List[OSMFacility],
        chunk_size: int = 500,
    ) -> BatchResult:
        """
        Idempotently persist a batch of normalized OSM facilities into PostgreSQL/PostGIS.
        Uses ON CONFLICT (osm_id, osm_type) DO UPDATE to ensure re-runs don't duplicate.
        """
        result = BatchResult(total=len(facilities))
        if not facilities:
            return result

        await cls.ensure_data_source(db)

        # 1. Validate and normalize records
        normalized_records: List[Dict[str, Any]] = []
        for fac in facilities:
            norm = cls._validate_and_normalize(fac)
            if norm is None:
                result.skipped += 1
                result.errors.append(f"Invalid record skipped: osm_id={getattr(fac, 'osm_id', None)}")
            else:
                normalized_records.append(norm)

        result.valid = len(normalized_records)
        if not normalized_records:
            return result

        # 2. In-batch deduplication by (osm_id, osm_type) to prevent PostgreSQL
        # "ON CONFLICT DO UPDATE command cannot affect row a second time" error
        unique_records_map: Dict[Tuple[int, str], Dict[str, Any]] = {}
        for rec in normalized_records:
            key = (rec["osm_id"], rec["osm_type"])
            unique_records_map[key] = rec
        records_to_insert = list(unique_records_map.values())

        # 3. Process in chunks
        for i in range(0, len(records_to_insert), chunk_size):
            chunk = records_to_insert[i : i + chunk_size]
            insert_stmt = pg_insert(EmergencyFacilityORM).values(chunk)
            upsert_stmt = insert_stmt.on_conflict_do_update(
                constraint="uq_osm_id_type",
                set_={
                    "name": insert_stmt.excluded.name,
                    "name_hi": insert_stmt.excluded.name_hi,
                    "facility_type": insert_stmt.excluded.facility_type,
                    "addr_street": insert_stmt.excluded.addr_street,
                    "addr_city": insert_stmt.excluded.addr_city,
                    "addr_district": insert_stmt.excluded.addr_district,
                    "addr_postcode": insert_stmt.excluded.addr_postcode,
                    "phone": insert_stmt.excluded.phone,
                    "phone_secondary": insert_stmt.excluded.phone_secondary,
                    "website": insert_stmt.excluded.website,
                    "opening_hours_raw": insert_stmt.excluded.opening_hours_raw,
                    "location": insert_stmt.excluded.location,
                    "data_quality_score": insert_stmt.excluded.data_quality_score,
                    "source_fetched_at": insert_stmt.excluded.source_fetched_at,
                    "updated_at": func.now(),
                    "is_active": True,
                },
            )

            try:
                await db.execute(upsert_stmt)
                await db.commit()
                result.persisted += len(chunk)
            except Exception as exc:
                await db.rollback()
                logger.error("Database batch upsert error: %s", exc, exc_info=True)
                result.errors.append(f"Batch upsert failed: {exc}")
                raise

        return result

    @staticmethod
    async def get_nearby(
        db: AsyncSession,
        lat: float,
        lon: float,
        radius_m: int = 2000,
        facility_type: Optional[str] = None,
        verified_only: bool = False,
        limit: int = 20,
    ) -> List[Tuple[EmergencyFacilityORM, float]]:
        """
        Query nearby facilities using PostGIS ST_DWithin and ST_Distance on geography.
        Returns a list of (EmergencyFacilityORM, distance_in_metres) tuples ordered by distance ASC.
        """
        # Validate coordinates
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            raise ValueError(f"Coordinates ({lat}, {lon}) out of bounds")

        # Enforce radius constraints
        radius_m = max(100, min(radius_m, 50000))
        limit = max(1, min(limit, 100))

        # Target geography point
        target_geog = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326).cast(Geography)

        # Distance calculation expression in metres
        distance_expr = func.ST_Distance(
            cast(EmergencyFacilityORM.location, Geography),
            target_geog,
        ).label("distance_m")

        # Spatial filter using ST_DWithin on geography
        stmt = (
            select(EmergencyFacilityORM, distance_expr)
            .where(
                EmergencyFacilityORM.is_active == True,
                func.ST_DWithin(
                    cast(EmergencyFacilityORM.location, Geography),
                    target_geog,
                    radius_m,
                ),
            )
        )

        if facility_type:
            stmt = stmt.where(EmergencyFacilityORM.facility_type == facility_type)

        if verified_only:
            stmt = stmt.where(EmergencyFacilityORM.source_verified == True)

        stmt = stmt.order_by(distance_expr.asc()).limit(limit)

        results = await db.execute(stmt)
        return [(row[0], float(row[1])) for row in results.all()]

    @staticmethod
    async def get_by_id(db: AsyncSession, facility_id: UUID) -> Optional[EmergencyFacilityORM]:
        """Fetch single facility by UUID."""
        stmt = select(EmergencyFacilityORM).where(
            EmergencyFacilityORM.id == facility_id,
            EmergencyFacilityORM.is_active == True,
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()
