"""
SafeSphere AI — Pydantic Models for Incident Reports
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class IncidentType(str, Enum):
    THEFT = "theft"
    HARASSMENT = "harassment"
    ASSAULT = "assault"
    ROAD_ACCIDENT = "road_accident"
    FIRE = "fire"
    FLOOD = "flood"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    EVE_TEASING = "eve_teasing"
    DRUNK_DRIVING = "drunk_driving"
    UNSAFE_ROAD = "unsafe_road"
    POWER_OUTAGE = "power_outage"
    OTHER = "other"


class VerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    UNDER_REVIEW = "under_review"
    VERIFIED = "verified"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"


class SeverityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentSource(str, Enum):
    APP_IOS = "app_ios"
    APP_ANDROID = "app_android"
    WEB = "web"
    API = "api"


# ---------------------------------------------------------------------------
# Request: Submit Incident
# ---------------------------------------------------------------------------

SENSITIVE_TYPES = {IncidentType.HARASSMENT, IncidentType.ASSAULT, IncidentType.EVE_TEASING}

DISCLAIMER = (
    "⚠️ This report is stored in SafeSphere AI and is NOT an official police complaint or FIR. "
    "For emergencies, call 112. To file an official complaint, visit your nearest police station "
    "or use Delhi Police eFIR at delhipolice.gov.in."
)

OFFICIAL_CHANNELS = {
    "emergency": "112",
    "cybercrime": "https://cybercrime.gov.in",
    "delhi_efir": "https://www.delhipolice.gov.in",
    "haryana_complaint": "https://haryanapolice.gov.in",
    "women_helpline": "1090",
    "senior_citizen": "1291",
}


class IncidentSubmitRequest(BaseModel):
    incident_type: IncidentType
    incident_subtype: Optional[str] = Field(None, max_length=100)
    latitude: float = Field(..., ge=8.0, le=38.0)
    longitude: float = Field(..., ge=68.0, le=98.0)
    location_accuracy_m: Optional[float] = Field(None, gt=0, le=5000)
    incident_at: Optional[datetime] = None
    description: Optional[str] = Field(None, max_length=1000)
    is_emergency: bool = Field(False)

    @field_validator("description")
    @classmethod
    def description_not_empty_string(cls, v):
        if v is not None and v.strip() == "":
            return None
        return v


class IncidentSubmitResponse(BaseModel):
    id: UUID
    incident_type: IncidentType
    verification_status: VerificationStatus
    reported_at: datetime
    is_emergency: bool

    # Always included — critical for responsible reporting
    disclaimer: str = DISCLAIMER
    official_channels: dict = Field(default_factory=lambda: OFFICIAL_CHANNELS)
    emergency_redirect: Optional[str] = None  # Set to "112" if is_emergency=True

    data_notice: str = (
        "Your location has been snapped to the nearest road ±50m to protect your privacy. "
        "Raw GPS coordinates are not stored."
    )


# ---------------------------------------------------------------------------
# Response: List Incidents (aggregated, public-facing)
# ---------------------------------------------------------------------------

class IncidentCluster(BaseModel):
    """Aggregated incident cluster for map display (min 5 reports)."""
    cluster_id: str
    latitude: float
    longitude: float
    count: int
    dominant_type: IncidentType
    recency_days: float  # Average days since report
    severity_estimate: Optional[SeverityLevel] = None
    data_notice: str = (
        "Clusters show 5+ community reports in this area. "
        "These are unverified community submissions, not official crime statistics."
    )


class IncidentListResponse(BaseModel):
    clusters: List[IncidentCluster]
    total_clusters: int
    time_window_days: int
    attribution_notice: str = (
        "Community incident reports submitted to SafeSphere AI. "
        "NOT official police records. Evidence-based estimates carry uncertainty. "
        "See privacy policy for data usage."
    )
