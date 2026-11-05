"""
SafeSphere AI — Routing and Road Network API Endpoints
Provides route comparison, walkability analysis, and nearby road metadata queries.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import FacilityRepository
from app.db.road_repository import RoadRepository
from app.db.session import get_db
from app.models.routing import (
    NearbyRoadSegmentResponse,
    SafeRouteRequest,
    SafeRouteResponse,
)
from app.services.routing import PedestrianRoutingEngine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["routing"])

MODERATOR_API_KEY = os.getenv("MODERATOR_API_KEY", "safesphere-dev-moderator-key-2026")


def require_moderator_key(
    x_moderator_key: Optional[str] = Header(None, alias="X-Moderator-Key"),
) -> str:
    """Dependency ensuring caller is an authorized moderator or administrator."""
    if not x_moderator_key or x_moderator_key != MODERATOR_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: valid X-Moderator-Key header required.",
        )
    return x_moderator_key


@router.post(
    "/routing/compare",
    response_model=SafeRouteResponse,
    summary="Compare pedestrian routes by distance, lighting, and safety index",
)
async def compare_safe_routes(
    request: SafeRouteRequest,
    db: AsyncSession = Depends(get_db),
) -> SafeRouteResponse:
    """
    Calculates and compares candidate pedestrian routes between origin and destination coordinates.
    Considers OpenStreetMap infrastructure, confirmed street lighting, sidewalk availability,
    corridor incident density, and proximity to active emergency facilities.
    """
    try:
        engine = PedestrianRoutingEngine(db)
        return await engine.calculate_routes(request)
    except Exception as exc:
        logger.error("Failed to calculate safe routes: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Route calculation failed: {str(exc)}",
        )


@router.get(
    "/roads/nearby",
    response_model=List[NearbyRoadSegmentResponse],
    summary="Query nearby road network segments with walkability metadata",
)
async def get_nearby_roads(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees"),
    radius: float = Query(500.0, ge=10.0, le=5000.0, description="Search radius in metres (max 5000)"),
    highway: Optional[str] = Query(None, description="Filter by highway type (e.g., pedestrian, footway, tertiary)"),
    lit: Optional[str] = Query(None, description="Filter by lit status (yes, no, 24/7, automatic, unknown)"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of segments to return"),
    db: AsyncSession = Depends(get_db),
) -> List[NearbyRoadSegmentResponse]:
    """
    Returns road segments within a given radius along with street lighting,
    sidewalk availability, and baseline walkability safety scores.
    """
    try:
        results = await RoadRepository.get_nearby_roads(
            session=db,
            lat=latitude,
            lon=longitude,
            radius_m=radius,
            highway_filter=highway,
            lit_filter=lit,
            limit=limit,
        )
        return [NearbyRoadSegmentResponse(**r) for r in results]
    except Exception as exc:
        logger.error("Failed to query nearby roads: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query nearby roads: {str(exc)}",
        )


@router.post(
    "/roads/recompute-scores",
    summary="Recompute road safety scores using latest approved community incidents",
)
async def recompute_road_scores(
    buffer_m: float = Query(60.0, ge=10.0, le=200.0, description="Corridor buffer in metres around road line"),
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_moderator_key),
) -> Dict[str, Any]:
    """
    Administrative endpoint to recompute 30-day and 90-day incident densities
    and updated safety scores for all road segments in the database.
    """
    try:
        updated_count = await RoadRepository.recompute_incident_scores(session=db, buffer_m=buffer_m)
        return {
            "status": "success",
            "updated_road_segments": updated_count,
            "corridor_buffer_m": buffer_m,
            "message": "Road segment safety scores updated successfully.",
        }
    except Exception as exc:
        logger.error("Failed to recompute road scores: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to recompute road safety scores: {str(exc)}",
        )
