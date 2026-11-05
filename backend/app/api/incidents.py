"""
SafeSphere AI — Incidents API Router
POST /api/v1/incidents                 — submit community safety report
GET  /api/v1/incidents                 — query approved public reports (privacy-coarsened)
GET  /api/v1/incidents/nearby          — spatial search for approved reports within radius
GET  /api/v1/incidents/moderation/queue— moderator review queue (requires moderator key)
POST /api/v1/incidents/{id}/moderate   — execute moderation action (approve/reject/archive)
"""

from __future__ import annotations

import logging
import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.incident_repository import IncidentRepository, rate_limiter
from app.db.session import get_db
from app.models.incident import (
    DISCLAIMER,
    OFFICIAL_CHANNELS,
    PUBLIC_UNCERTAINTY_NOTICE,
    IncidentSubmitRequest,
    IncidentSubmitResponse,
    IncidentType,
    ModerationActionRequest,
    ModerationQueueItem,
    ModerationQueueResponse,
    ModerationStatus,
    PublicIncidentListResponse,
    PublicIncidentNearbyResponse,
    PublicIncidentResponse,
    VerificationStatus,
)
from app.services.sanitizer import coarsen_coordinates, generate_reporter_hash

logger = logging.getLogger(__name__)

router = APIRouter()

# Default development key if not specified in environment
DEFAULT_MODERATOR_KEY = "safesphere-dev-moderator-key-2026"
MODERATOR_API_KEY = os.getenv("MODERATOR_API_KEY", DEFAULT_MODERATOR_KEY)


# ---------------------------------------------------------------------------
# Moderator Authorization Dependency
# ---------------------------------------------------------------------------

async def verify_moderator_auth(
    x_moderator_key: Optional[str] = Header(None, alias="X-Moderator-Key"),
    authorization: Optional[str] = Header(None),
) -> str:
    """
    Enforces authorization on moderation endpoints.
    Checks X-Moderator-Key header or Bearer token.
    """
    token = x_moderator_key
    if not token and authorization:
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        else:
            token = authorization.strip()

    if not token or token != MODERATOR_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Unauthorized moderator access. A valid 'X-Moderator-Key' header or "
                "Bearer token is required to access moderation workflows."
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )
    return "moderator:authorized"


# ---------------------------------------------------------------------------
# Public Submission Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=IncidentSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a community safety incident report",
    description=(
        "Submit a community safety incident report. "
        "**This is NOT an official police complaint or FIR.** "
        "The report enters SafeSphere AI's moderation queue and is reviewed before inclusion in public layers. "
        "For immediate life-threatening emergencies, call 112."
    ),
)
async def submit_incident(
    body: IncidentSubmitRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Incident report submission endpoint.

    Privacy & Safety Guarantees:
    1. Raw IPs and PII are never stored (salted SHA-256 hashes only).
    2. Description is sanitized with PII redaction and prompt-injection neutralization.
    3. Rate limiting prevents spam floods.
    4. Emergency reports prominently redirect to 112.
    5. Disclaimers and official channels are always returned.
    """
    # 1. Compute privacy hashes
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "unknown")
    reporter_hash = generate_reporter_hash(client_ip, user_agent)
    ip_hash = generate_reporter_hash(client_ip, "ip-salt")[:64]

    # 2. Rate limit check (5 requests / 10 min)
    if not rate_limiter.is_allowed(ip_hash):
        logger.warning("Incident rate limit exceeded for ip_hash=%s", ip_hash[:8])
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Submission rate limit exceeded. Please wait 10 minutes before submitting another report.",
        )

    # 3. Create incident record in database
    try:
        incident = await IncidentRepository.create_incident(
            db=db,
            request=body,
            reporter_hash=reporter_hash,
            ip_hash=ip_hash,
            source="api",
        )
    except Exception as exc:
        logger.error("Failed to store incident report: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while saving incident report.",
        )

    # 4. Construct emergency redirect message if flagged
    emergency_redirect = None
    if body.is_emergency:
        emergency_redirect = (
            "🚨 CRITICAL: You flagged this incident as an emergency. "
            "CALL 112 IMMEDIATELY. SafeSphere AI does NOT dispatch police or emergency responders."
        )

    return IncidentSubmitResponse(
        id=incident.id,
        incident_type=IncidentType(incident.incident_type),
        incident_subtype=incident.incident_subtype,
        moderation_status=ModerationStatus(incident.moderation_status),
        verification_status=VerificationStatus(incident.verification_status),
        reported_at=incident.reported_at,
        is_emergency=incident.is_emergency,
        region=incident.region,
        disclaimer=DISCLAIMER,
        emergency_redirect=emergency_redirect,
    )


# ---------------------------------------------------------------------------
# Public Incident Query Endpoints (Approved & Privacy-Preserved Only)
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=PublicIncidentListResponse,
    summary="List approved public incident reports",
    description=(
        "Returns approved, moderated community safety reports for public analysis. "
        "Strict Privacy: Location coordinates are coarsened to ~100m grid resolution. "
        "Pending and rejected reports are excluded. Low incident counts do NOT guarantee safety."
    ),
)
async def list_public_incidents(
    region: Optional[str] = Query(None, description="Filter by region (delhi, sonipat)"),
    incident_type: Optional[IncidentType] = Query(None, description="Filter by incident category"),
    days: int = Query(30, ge=1, le=365, description="Time window in days"),
    limit: int = Query(50, ge=1, le=100, description="Max results"),
    db: AsyncSession = Depends(get_db),
):
    try:
        type_str = incident_type.value if incident_type else None
        incidents = await IncidentRepository.get_public_incidents(
            db=db,
            region=region,
            incident_type=type_str,
            days=days,
            limit=limit,
        )

        public_items = []
        for inc in incidents:
            coarse_lat, coarse_lon = coarsen_coordinates(inc.latitude, inc.longitude)
            public_items.append(
                PublicIncidentResponse(
                    id=inc.id,
                    incident_type=IncidentType(inc.incident_type),
                    incident_subtype=inc.incident_subtype,
                    latitude=coarse_lat,
                    longitude=coarse_lon,
                    location_approximate=True,
                    region=inc.region,
                    reported_at=inc.reported_at,
                    incident_at=inc.incident_at,
                    description=inc.description_sanitized,
                    moderation_status=ModerationStatus(inc.moderation_status),
                    verification_status=VerificationStatus(inc.verification_status),
                )
            )

        return PublicIncidentListResponse(
            incidents=public_items,
            count=len(public_items),
            region_filter=region,
            category_filter=type_str,
            time_window_days=days,
            data_notice=PUBLIC_UNCERTAINTY_NOTICE,
        )
    except Exception as exc:
        logger.error("Error retrieving public incidents: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query incident reports from database.",
        )


@router.get(
    "/nearby",
    response_model=PublicIncidentNearbyResponse,
    summary="Query approved incidents near a location",
    description=(
        "Returns approved community safety reports within radius_m using PostGIS ST_DWithin. "
        "Strict Privacy: Coordinates are coarsened. Only moderator-approved reports are returned. "
        "Results include distance in metres."
    ),
)
async def get_nearby_incidents(
    lat: float = Query(..., ge=8.0, le=38.0, description="Latitude (India 8.0-38.0)"),
    lon: float = Query(..., ge=68.0, le=98.0, description="Longitude (India 68.0-98.0)"),
    radius_m: int = Query(2000, ge=100, le=25000, description="Radius in metres (100m to 25km)"),
    incident_type: Optional[IncidentType] = Query(None, description="Optional incident category"),
    days: int = Query(30, ge=1, le=365, description="Time window in days"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    db: AsyncSession = Depends(get_db),
):
    try:
        type_str = incident_type.value if incident_type else None
        results = await IncidentRepository.get_public_nearby(
            db=db,
            lat=lat,
            lon=lon,
            radius_m=radius_m,
            incident_type=type_str,
            days=days,
            limit=limit,
        )

        public_items = []
        for inc, dist_m in results:
            coarse_lat, coarse_lon = coarsen_coordinates(inc.latitude, inc.longitude)
            public_items.append(
                PublicIncidentResponse(
                    id=inc.id,
                    incident_type=IncidentType(inc.incident_type),
                    incident_subtype=inc.incident_subtype,
                    latitude=coarse_lat,
                    longitude=coarse_lon,
                    location_approximate=True,
                    region=inc.region,
                    reported_at=inc.reported_at,
                    incident_at=inc.incident_at,
                    description=inc.description_sanitized,
                    moderation_status=ModerationStatus(inc.moderation_status),
                    verification_status=VerificationStatus(inc.verification_status),
                    distance_m=round(dist_m, 1),
                )
            )

        return PublicIncidentNearbyResponse(
            incidents=public_items,
            count=len(public_items),
            search_lat=lat,
            search_lon=lon,
            radius_m=radius_m,
            data_notice=PUBLIC_UNCERTAINTY_NOTICE,
        )
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as exc:
        logger.error("Error retrieving nearby incidents: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error during nearby incident spatial query.",
        )


# ---------------------------------------------------------------------------
# Moderation Endpoints (Moderator Authorization Required)
# ---------------------------------------------------------------------------

@router.get(
    "/moderation/queue",
    response_model=ModerationQueueResponse,
    summary="Get moderator review queue",
    description="Lists submitted reports awaiting moderation. Requires moderator authorization.",
)
async def get_moderation_queue(
    status_filter: str = Query("pending_review", description="pending_review, approved, rejected, archived"),
    region: Optional[str] = Query(None, description="Optional region filter (delhi, sonipat)"),
    limit: int = Query(50, ge=1, le=100),
    moderator_auth: str = Depends(verify_moderator_auth),
    db: AsyncSession = Depends(get_db),
):
    try:
        items, count, pending_count = await IncidentRepository.get_moderation_queue(
            db=db,
            status=status_filter,
            region=region,
            limit=limit,
        )

        queue_items = [
            ModerationQueueItem(
                id=item.id,
                incident_type=IncidentType(item.incident_type),
                incident_subtype=item.incident_subtype,
                latitude=item.latitude,
                longitude=item.longitude,
                region=item.region,
                description_raw=item.description,
                description_sanitized=item.description_sanitized,
                moderation_status=ModerationStatus(item.moderation_status),
                verification_status=VerificationStatus(item.verification_status),
                reported_at=item.reported_at,
                incident_at=item.incident_at,
                is_emergency=item.is_emergency,
                moderation_reason=item.moderation_reason,
                moderation_notes=item.moderation_notes,
                moderated_at=item.moderated_at,
                moderated_by=item.moderated_by,
            )
            for item in items
        ]

        return ModerationQueueResponse(
            items=queue_items,
            count=count,
            pending_count=pending_count,
        )
    except Exception as exc:
        logger.error("Error retrieving moderation queue: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve moderation queue from database.",
        )


@router.post(
    "/{incident_id}/moderate",
    response_model=ModerationQueueItem,
    summary="Execute moderation action on an incident report",
    description="Approve, reject, archive, or flag an incident report. Requires moderator authorization.",
)
async def moderate_incident(
    incident_id: UUID,
    action_body: ModerationActionRequest,
    moderator_auth: str = Depends(verify_moderator_auth),
    db: AsyncSession = Depends(get_db),
):
    try:
        updated = await IncidentRepository.moderate_incident(
            db=db,
            incident_id=incident_id,
            action=action_body.action,
            moderator_id=moderator_auth,
            reason_code=action_body.reason_code.value if action_body.reason_code else None,
            notes=action_body.notes,
        )
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident with ID {incident_id} not found.",
            )

        return ModerationQueueItem(
            id=updated.id,
            incident_type=IncidentType(updated.incident_type),
            incident_subtype=updated.incident_subtype,
            latitude=updated.latitude,
            longitude=updated.longitude,
            region=updated.region,
            description_raw=updated.description,
            description_sanitized=updated.description_sanitized,
            moderation_status=ModerationStatus(updated.moderation_status),
            verification_status=VerificationStatus(updated.verification_status),
            reported_at=updated.reported_at,
            incident_at=updated.incident_at,
            is_emergency=updated.is_emergency,
            moderation_reason=updated.moderation_reason,
            moderation_notes=updated.moderation_notes,
            moderated_at=updated.moderated_at,
            moderated_by=updated.moderated_by,
        )
    except HTTPException:
        raise
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as exc:
        logger.error("Error executing moderation on incident %s: %s", incident_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while applying moderation decision.",
        )
