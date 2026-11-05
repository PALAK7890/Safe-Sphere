"""
SafeSphere AI — Facilities API Router
GET /api/v1/facilities/nearby  — nearest emergency facilities by type + radius
GET /api/v1/facilities/{id}    — single facility detail
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import FacilityRepository
from app.db.session import get_db
from app.models.facility import (
    FacilityNearbyResponse,
    FacilityResponse,
    FacilityType,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/nearby",
    response_model=FacilityNearbyResponse,
    summary="Find nearest emergency facilities",
    description=(
        "Returns the nearest emergency facilities within the given radius using PostGIS ST_DWithin. "
        "Results include distance in metres, OpenStreetMap community data, and government directory data. "
        "Data quality score (0–100) indicates completeness. "
        "**Always call 112 for emergencies — do not rely solely on this API.**"
    ),
)
async def get_nearby_facilities(
    lat: float = Query(..., ge=8.0,  le=38.0,  description="Your latitude (WGS84, India scope 8.0-38.0)"),
    lon: float = Query(..., ge=68.0, le=98.0,  description="Your longitude (WGS84, India scope 68.0-98.0)"),
    facility_type: Optional[FacilityType] = Query(None, description="Optional type of facility to find"),
    radius_m: int  = Query(2000, ge=100, le=50000, description="Search radius in metres (100m to 50km)"),
    limit: int     = Query(10,   ge=1,   le=100,   description="Maximum results to return"),
    verified_only: bool = Query(False, description="Only return officially verified records"),
    db: AsyncSession = Depends(get_db),
):
    """
    Queries PostGIS emergency_facilities within radius_m of (lat, lon).
    Returns facilities sorted by distance ascending.
    """
    try:
        type_str = facility_type.value if facility_type else None
        results = await FacilityRepository.get_nearby(
            db=db,
            lat=lat,
            lon=lon,
            radius_m=radius_m,
            facility_type=type_str,
            verified_only=verified_only,
            limit=limit,
        )

        facility_responses = []
        for fac_orm, dist_m in results:
            item = FacilityResponse(
                id=fac_orm.id,
                source_id=fac_orm.source_id,
                external_id=fac_orm.external_id,
                facility_type=fac_orm.facility_type,
                name=fac_orm.name,
                name_hi=fac_orm.name_hi,
                latitude=fac_orm.latitude,
                longitude=fac_orm.longitude,
                addr_street=fac_orm.addr_street,
                addr_city=fac_orm.addr_city,
                addr_district=fac_orm.addr_district,
                addr_state=fac_orm.addr_state,
                addr_postcode=fac_orm.addr_postcode,
                phone=fac_orm.phone,
                phone_secondary=fac_orm.phone_secondary,
                website=fac_orm.website,
                opening_hours_raw=fac_orm.opening_hours_raw,
                is_24h=fac_orm.is_24h,
                beds=fac_orm.beds,
                services=fac_orm.services,
                source_verified=fac_orm.source_verified,
                osm_id=fac_orm.osm_id,
                osm_type=fac_orm.osm_type,
                data_quality_score=fac_orm.data_quality_score,
                source_fetched_at=fac_orm.source_fetched_at,
                is_active=fac_orm.is_active,
                distance_m=round(dist_m, 1),
            )
            facility_responses.append(item)

        return FacilityNearbyResponse(
            facilities=facility_responses,
            count=len(facility_responses),
            search_lat=lat,
            search_lon=lon,
            radius_m=radius_m,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error("Error querying nearby facilities: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve nearby facilities from database.",
        )


@router.get(
    "/{facility_id}",
    response_model=FacilityResponse,
    summary="Get facility details",
)
async def get_facility(facility_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Returns full detail for a single facility by ID.
    Includes data provenance, verification status, and source attribution.
    """
    try:
        fac_orm = await FacilityRepository.get_by_id(db, facility_id)
        if not fac_orm:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found")

        return FacilityResponse(
            id=fac_orm.id,
            source_id=fac_orm.source_id,
            external_id=fac_orm.external_id,
            facility_type=fac_orm.facility_type,
            name=fac_orm.name,
            name_hi=fac_orm.name_hi,
            latitude=fac_orm.latitude,
            longitude=fac_orm.longitude,
            addr_street=fac_orm.addr_street,
            addr_city=fac_orm.addr_city,
            addr_district=fac_orm.addr_district,
            addr_state=fac_orm.addr_state,
            addr_postcode=fac_orm.addr_postcode,
            phone=fac_orm.phone,
            phone_secondary=fac_orm.phone_secondary,
            website=fac_orm.website,
            opening_hours_raw=fac_orm.opening_hours_raw,
            is_24h=fac_orm.is_24h,
            beds=fac_orm.beds,
            services=fac_orm.services,
            source_verified=fac_orm.source_verified,
            osm_id=fac_orm.osm_id,
            osm_type=fac_orm.osm_type,
            data_quality_score=fac_orm.data_quality_score,
            source_fetched_at=fac_orm.source_fetched_at,
            is_active=fac_orm.is_active,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error retrieving facility %s: %s", facility_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while retrieving facility.",
        )
