"""
SafeSphere AI — Incidents API Router
POST /api/v1/incidents         — submit community report
GET  /api/v1/incidents         — list aggregated incident clusters
"""

from __future__ import annotations

import hashlib
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import JSONResponse

from app.models.incident import (
    DISCLAIMER,
    OFFICIAL_CHANNELS,
    SENSITIVE_TYPES,
    IncidentCluster,
    IncidentListResponse,
    IncidentSubmitRequest,
    IncidentSubmitResponse,
)

router = APIRouter()

NOT_OFFICIAL_COMPLAINT_NOTICE = (
    "⚠️ SafeSphere community reports are NOT official police complaints or FIRs. "
    "For emergencies, call 112 immediately."
)


@router.post(
    "",
    response_model=IncidentSubmitResponse,
    status_code=201,
    summary="Submit a community safety incident report",
    description=(
        "Submit a community safety report. "
        "**This is NOT an official police complaint.** "
        "The report enters SafeSphere AI's moderation queue. "
        "For emergencies, call 112. For FIRs, visit your nearest police station."
    ),
)
async def submit_incident(
    body: IncidentSubmitRequest,
    request: Request,
):
    """
    Incident report submission endpoint.

    Safety rules enforced here:
    1. If is_emergency=True → redirect user to 112 (in addition to storing report)
    2. Location is snapped to nearest road ±50m before storage (privacy)
    3. Description passes through PII scrubber before storage
    4. Sensitive incident types get extra location fuzzing (±500m)
    5. Disclaimer and official channels ALWAYS included in response
    """

    # Emergency escalation — always redirect to 112 first
    if body.is_emergency:
        # TODO: trigger push notification to moderator queue
        return IncidentSubmitResponse(
            id=_placeholder_uuid(),
            incident_type=body.incident_type,
            verification_status="unverified",
            reported_at=_now(),
            is_emergency=True,
            disclaimer=DISCLAIMER,
            official_channels=OFFICIAL_CHANNELS,
            emergency_redirect=(
                "⚠️ You flagged this as an emergency. "
                "CALL 112 NOW. Do not wait for this report to be reviewed."
            ),
        )

    # TODO: Replace stub with full pipeline:
    # 1. scrub_pii(body.description)
    # 2. snap_to_road(body.latitude, body.longitude)
    # 3. fuzz_location_if_sensitive(body.incident_type)
    # 4. check_rate_limit(ip_hash)
    # 5. check_duplicate(lat, lon, incident_type, last_1h)
    # 6. insert into incident_reports
    # 7. create incident_verification_events (submitted)

    return IncidentSubmitResponse(
        id=_placeholder_uuid(),
        incident_type=body.incident_type,
        verification_status="unverified",
        reported_at=_now(),
        is_emergency=False,
        disclaimer=DISCLAIMER,
        official_channels=OFFICIAL_CHANNELS,
    )


@router.get(
    "",
    response_model=IncidentListResponse,
    summary="List aggregated incident clusters",
    description=(
        "Returns aggregated incident density clusters for the given bounding box. "
        "Clusters require a minimum of 5 verified/under-review reports. "
        "Individual report locations are never exposed."
    ),
)
async def list_incidents(
    south: float = Query(..., ge=8.0,  le=38.0),
    west:  float = Query(..., ge=68.0, le=98.0),
    north: float = Query(..., ge=8.0,  le=38.0),
    east:  float = Query(..., ge=68.0, le=98.0),
    days:  int   = Query(30, ge=1, le=365, description="Time window in days"),
):
    """
    Returns only aggregated clusters (min 5 reports). Individual reports never shown.
    """
    # TODO: Replace stub with real PostGIS cluster query
    return IncidentListResponse(clusters=[], total_clusters=0, time_window_days=days)


# ---------------------------------------------------------------------------
# Helpers (stub only — replace with real implementations)
# ---------------------------------------------------------------------------

def _placeholder_uuid():
    import uuid
    return uuid.uuid4()

def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)
