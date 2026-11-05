"""
SafeSphere AI — Pydantic Models for Emergency Facilities
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator


class FacilityType(str, Enum):
    POLICE_STATION = "police_station"
    FIRE_STATION = "fire_station"
    HOSPITAL = "hospital"
    CLINIC = "clinic"
    PHARMACY = "pharmacy"
    AMBULANCE_POST = "ambulance_post"
    PCR_BASE = "pcr_base"
    EMERGENCY_SHELTER = "emergency_shelter"


class OSMElementType(str, Enum):
    NODE = "node"
    WAY = "way"
    RELATION = "relation"


# ---------------------------------------------------------------------------
# Response Models
# ---------------------------------------------------------------------------

class FacilityBase(BaseModel):
    facility_type: FacilityType
    name: str
    name_hi: Optional[str] = None
    latitude: float = Field(..., ge=8.0, le=38.0)
    longitude: float = Field(..., ge=68.0, le=98.0)
    addr_street: Optional[str] = None
    addr_city: Optional[str] = None
    addr_district: Optional[str] = None
    addr_state: Optional[str] = None
    addr_postcode: Optional[str] = None
    phone: Optional[str] = None
    phone_secondary: Optional[str] = None
    website: Optional[str] = None
    opening_hours_raw: Optional[str] = None
    is_24h: Optional[bool] = None


class FacilityResponse(FacilityBase):
    id: UUID
    source_id: str
    external_id: Optional[str] = None
    osm_id: Optional[int] = None
    osm_type: Optional[OSMElementType] = None
    source_verified: bool
    data_quality_score: Optional[int] = None
    beds: Optional[int] = None
    services: Optional[List[str]] = None
    source_fetched_at: datetime
    is_active: bool
    distance_m: Optional[float] = None

    # Data trust fields — always present in response
    data_notice: str = Field(
        default=(
            "Facility data sourced from OpenStreetMap and government directories. "
            "Contact details may be incomplete or outdated. "
            "Verify before use in emergencies."
        )
    )
    attribution: str = Field(default="© OpenStreetMap contributors (ODbL 1.0)")
    source_verified_note: Optional[str] = None

    @field_validator("source_verified_note", mode="before")
    @classmethod
    def set_verified_note(cls, v, info):
        data = info.data
        if not data.get("source_verified"):
            return (
                "This record has NOT been verified against an official government source. "
                "It is sourced from OpenStreetMap (community-maintained)."
            )
        return "Verified against official government source."

    model_config = {"from_attributes": True}


class FacilityNearbyResponse(BaseModel):
    facilities: List[FacilityResponse]
    count: int
    search_lat: float
    search_lon: float
    radius_m: int
    data_notice: str = (
        "Results include OpenStreetMap community data (not officially verified) "
        "and government directory data where available. "
        "For emergencies, call 112."
    )
    attribution: str = "© OpenStreetMap contributors (ODbL 1.0)"


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------

class FacilityQueryParams(BaseModel):
    """Query parameters for nearby facility search."""
    lat: float = Field(..., ge=8.0, le=38.0, description="Latitude (WGS84)")
    lon: float = Field(..., ge=68.0, le=98.0, description="Longitude (WGS84)")
    facility_type: FacilityType
    radius_m: int = Field(2000, ge=100, le=10000, description="Search radius in metres")
    limit: int = Field(5, ge=1, le=20, description="Maximum number of results")
    verified_only: bool = Field(False, description="If true, return only officially verified records")
