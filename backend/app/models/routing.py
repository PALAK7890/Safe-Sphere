"""
SafeSphere AI — Routing Pydantic Models & Schemas
Defines request and response schemas for pedestrian safe route calculation and comparison.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


class RoutingPriority(str, Enum):
    SAFEST = "safest"
    SHORTEST = "shortest"
    BALANCED = "balanced"


class RouteConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CoordinatePoint(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)


class RouteWaypoint(BaseModel):
    latitude: float
    longitude: float


class RouteSegmentDetail(BaseModel):
    name: Optional[str] = None
    highway: str
    lit: str
    sidewalk: str
    length_m: float
    safety_score: Optional[float] = None
    safety_notes: Optional[str] = None


class EmergencyFacilitySummary(BaseModel):
    id: str
    name: str
    facility_type: str
    distance_to_route_m: float
    phone: Optional[str] = None


class RouteOption(BaseModel):
    route_id: str
    label: str  # e.g., "Safety-Optimized", "Shortest Walking", "Well-Lit Alternative"
    is_recommended: bool = False
    total_distance_m: float
    estimated_duration_min: float
    overall_safety_index: int = Field(..., ge=0, le=100)
    lighting_coverage_pct: float = Field(..., ge=0.0, le=100.0)
    sidewalk_coverage_pct: float = Field(..., ge=0.0, le=100.0)
    incident_exposure_count: int = 0
    emergency_facility_count: int = 0
    confidence_level: RouteConfidenceLevel
    recommendation_reason: str
    uncertainty_notes: List[str] = Field(default_factory=list)
    waypoints: List[RouteWaypoint]
    segments: List[RouteSegmentDetail] = Field(default_factory=list)
    nearby_emergency_facilities: List[EmergencyFacilitySummary] = Field(default_factory=list)


class SafeRouteRequest(BaseModel):
    origin_latitude: float = Field(..., ge=28.0, le=30.0, description="Start lat in Delhi/Sonipat pilot area")
    origin_longitude: float = Field(..., ge=76.5, le=77.6, description="Start lon in Delhi/Sonipat pilot area")
    destination_latitude: float = Field(..., ge=28.0, le=30.0, description="End lat in Delhi/Sonipat pilot area")
    destination_longitude: float = Field(..., ge=76.5, le=77.6, description="End lon in Delhi/Sonipat pilot area")
    departure_time: Optional[datetime] = None
    prioritize: RoutingPriority = RoutingPriority.SAFEST

    @model_validator(mode="after")
    def validate_points_not_identical(self) -> "SafeRouteRequest":
        if (
            abs(self.origin_latitude - self.destination_latitude) < 0.0001
            and abs(self.origin_longitude - self.destination_longitude) < 0.0001
        ):
            raise ValueError("Origin and destination must be distinct locations (> 15 metres apart)")
        return self


class SafeRouteResponse(BaseModel):
    request_id: str
    origin: CoordinatePoint
    destination: CoordinatePoint
    is_nighttime: bool
    routes: List[RouteOption]
    disclaimer: str = (
        "EMERGENCY NOTICE: SafeSphere AI routing guidance is advisory and calculated from open-source "
        "community data. It is NOT a guarantee of physical safety. In an emergency or if you feel unsafe, "
        "call 112 immediately."
    )
    data_attribution: str = "Road infrastructure © OpenStreetMap contributors (ODbL 1.0)"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NearbyRoadSegmentResponse(BaseModel):
    id: str
    osm_way_id: int
    name: Optional[str] = None
    highway: str
    lit: str
    sidewalk: str
    length_m: Optional[float] = None
    district: Optional[str] = None
    incident_count_30d: int
    safety_score: Optional[float] = None
    distance_m: float
    geojson: Optional[str] = None
