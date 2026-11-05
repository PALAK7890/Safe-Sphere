"""
SafeSphere AI — Pydantic Models for Incident Reports
Handles community reporting, privacy redaction, moderation workflow, and public queries.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
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


class ModerationStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class ModerationReasonCode(str, Enum):
    PII_DETECTED = "pii_detected"
    HATE_SPEECH_OR_HARASSMENT = "hate_speech_or_harassment"
    SPAM_OR_COMMERCIAL = "spam_or_commercial"
    ABUSIVE_OR_DEFAMATORY = "abusive_or_defamatory"
    UNVERIFIABLE_OR_VAGUE = "unverifiable_or_vague"
    DUPLICATE = "duplicate"
    PROMPT_INJECTION = "prompt_injection"
    OUT_OF_PILOT_SCOPE = "out_of_pilot_scope"
    APPROVED_FOR_PUBLIC = "approved_for_public"
    OTHER = "other"


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
# Constants & Disclaimers
# ---------------------------------------------------------------------------

SENSITIVE_TYPES = {IncidentType.HARASSMENT, IncidentType.ASSAULT, IncidentType.EVE_TEASING}

DISCLAIMER = (
    "⚠️ This report is stored in SafeSphere AI and is NOT an official police complaint or FIR. "
    "SafeSphere AI is NOT connected to police dispatch. For immediate emergencies, call 112. "
    "To file an official FIR, visit your nearest police station or use Delhi Police eFIR "
    "at delhipolice.gov.in or Haryana Police portal at haryanapolice.gov.in."
)

OFFICIAL_CHANNELS = {
    "emergency": "112",
    "police_control_room": "100",
    "fire": "101",
    "ambulance": "102 / 108",
    "cybercrime": "https://cybercrime.gov.in (Helpline 1930)",
    "delhi_efir": "https://www.delhipolice.gov.in",
    "haryana_complaint": "https://haryanapolice.gov.in",
    "women_helpline": "1090 / 1091",
    "senior_citizen": "1291",
}

PUBLIC_UNCERTAINTY_NOTICE = (
    "Community safety incident reports submitted to SafeSphere AI. "
    "These are community submissions and are NOT official police records. "
    "Low incident counts in an area do NOT imply or guarantee safety; "
    "data may be sparse, delayed, or under-reported."
)


# ---------------------------------------------------------------------------
# Request: Submit Incident
# ---------------------------------------------------------------------------

class IncidentSubmitRequest(BaseModel):
    incident_type: IncidentType
    incident_subtype: Optional[str] = Field(None, max_length=100)
    latitude: float = Field(..., ge=8.0, le=38.0, description="Latitude within India bounds (8.0 to 38.0)")
    longitude: float = Field(..., ge=68.0, le=98.0, description="Longitude within India bounds (68.0 to 98.0)")
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

    @field_validator("incident_at")
    @classmethod
    def validate_incident_timestamp(cls, v):
        if v is not None:
            now = datetime.now(timezone.utc)
            # Allow up to 10 minutes clock drift into the future
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            if v > now + timedelta(minutes=10):
                raise ValueError("Incident timestamp cannot be in the future.")
            if v < now - timedelta(days=365):
                raise ValueError("Incident timestamp cannot be older than 365 days.")
        return v


class IncidentSubmitResponse(BaseModel):
    id: UUID
    incident_type: IncidentType
    incident_subtype: Optional[str] = None
    moderation_status: ModerationStatus = ModerationStatus.PENDING_REVIEW
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    reported_at: datetime
    is_emergency: bool
    region: Optional[str] = None

    # Always included — critical for responsible reporting and legal protection
    disclaimer: str = DISCLAIMER
    official_channels: dict = Field(default_factory=lambda: OFFICIAL_CHANNELS)
    emergency_redirect: Optional[str] = None

    data_notice: str = (
        "Report submitted and queued for moderation review. "
        "Location has been coarsened to protect reporter privacy. "
        "This submission is NOT sent to the police."
    )


# ---------------------------------------------------------------------------
# Moderation Models
# ---------------------------------------------------------------------------

class ModerationActionRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject|archive|flag)$", description="Moderation action")
    reason_code: Optional[ModerationReasonCode] = None
    notes: Optional[str] = Field(None, max_length=500, description="Internal review notes")


class ModerationQueueItem(BaseModel):
    id: UUID
    incident_type: IncidentType
    incident_subtype: Optional[str] = None
    latitude: float
    longitude: float
    region: Optional[str] = None
    description_raw: Optional[str] = None
    description_sanitized: Optional[str] = None
    moderation_status: ModerationStatus
    verification_status: VerificationStatus
    reported_at: datetime
    incident_at: Optional[datetime] = None
    is_emergency: bool
    moderation_reason: Optional[str] = None
    moderation_notes: Optional[str] = None
    moderated_at: Optional[datetime] = None
    moderated_by: Optional[str] = None


class ModerationQueueResponse(BaseModel):
    items: List[ModerationQueueItem]
    count: int
    pending_count: int


# ---------------------------------------------------------------------------
# Public Responses (Privacy-Preserving)
# ---------------------------------------------------------------------------

class PublicIncidentResponse(BaseModel):
    id: UUID
    incident_type: IncidentType
    incident_subtype: Optional[str] = None
    latitude: float = Field(..., description="Privacy-coarsened latitude (~100m precision)")
    longitude: float = Field(..., description="Privacy-coarsened longitude (~100m precision)")
    location_approximate: bool = True
    region: Optional[str] = None
    reported_at: datetime
    incident_at: Optional[datetime] = None
    description: Optional[str] = Field(None, description="Sanitized text with PII removed")
    moderation_status: ModerationStatus
    verification_status: VerificationStatus
    distance_m: Optional[float] = None
    data_notice: str = PUBLIC_UNCERTAINTY_NOTICE
    attribution: str = "SafeSphere AI Community Reports (Unverified)"


class PublicIncidentListResponse(BaseModel):
    incidents: List[PublicIncidentResponse]
    count: int
    region_filter: Optional[str] = None
    category_filter: Optional[str] = None
    time_window_days: Optional[int] = None
    data_notice: str = PUBLIC_UNCERTAINTY_NOTICE


class PublicIncidentNearbyResponse(BaseModel):
    incidents: List[PublicIncidentResponse]
    count: int
    search_lat: float
    search_lon: float
    radius_m: int
    data_notice: str = PUBLIC_UNCERTAINTY_NOTICE


# ---------------------------------------------------------------------------
# Legacy / Aggregated Cluster Models (Backwards-compatibility)
# ---------------------------------------------------------------------------

class IncidentCluster(BaseModel):
    """Aggregated incident cluster for map display (min 5 reports)."""
    cluster_id: str
    latitude: float
    longitude: float
    count: int
    dominant_type: IncidentType
    recency_days: float
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
