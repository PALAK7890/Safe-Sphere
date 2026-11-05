"""
SafeSphere AI — Incident Repository
PostGIS-backed spatial queries, moderation workflow, and privacy-preserving community incident storage.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IncidentReportORM, IncidentVerificationEventORM
from app.models.incident import IncidentSubmitRequest, ModerationStatus, VerificationStatus
from app.services.sanitizer import (
    coarsen_coordinates,
    determine_pilot_region,
    sanitize_text,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rate Limiting (In-Memory Sliding Window for Development / Sandbox)
# ---------------------------------------------------------------------------

class IncidentRateLimiter:
    """
    Sliding window rate limiter by IP hash.
    Enforces maximum submissions per time window (e.g. 5 requests / 10 minutes).
    """

    def __init__(self, max_requests: int = 5, window_seconds: int = 600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, client_key: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        # Evict timestamps older than window
        self._history[client_key] = [t for t in self._history[client_key] if t > cutoff]

        if len(self._history[client_key]) >= self.max_requests:
            return False

        self._history[client_key].append(now)
        return True

    def reset(self):
        """Reset rate limiter state (useful for tests)."""
        self._history.clear()


rate_limiter = IncidentRateLimiter(max_requests=5, window_seconds=600)


# ---------------------------------------------------------------------------
# Incident Repository
# ---------------------------------------------------------------------------

class IncidentRepository:
    """Repository handling database operations for community safety incident reports."""

    @staticmethod
    async def find_recent_duplicate(
        db: AsyncSession,
        lat: float,
        lon: float,
        incident_type: str,
        reporter_hash: str,
        spatial_tolerance_m: float = 100.0,
        time_window_minutes: int = 60,
    ) -> Optional[IncidentReportORM]:
        """
        Check for near-duplicate reports within spatial and temporal tolerance.
        A report is considered a candidate duplicate if:
        1. Same reporter_hash + same incident_type within 15 minutes.
        2. Or same incident_type + within 100m + within 60 minutes.
        """
        now = datetime.now(timezone.utc)
        time_cutoff = now - timedelta(minutes=time_window_minutes)
        quick_cutoff = now - timedelta(minutes=15)

        # 1. Check quick repeated submission by same reporter
        stmt_same_reporter = (
            select(IncidentReportORM)
            .where(
                IncidentReportORM.reporter_hash == reporter_hash,
                IncidentReportORM.incident_type == incident_type,
                IncidentReportORM.reported_at >= quick_cutoff,
            )
            .limit(1)
        )
        res = await db.execute(stmt_same_reporter)
        same_reporter = res.scalar_one_or_none()
        if same_reporter:
            return same_reporter

        # 2. Check nearby same-type reports within window
        target_geog = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326).cast(Geography)
        stmt_spatial = (
            select(IncidentReportORM)
            .where(
                IncidentReportORM.incident_type == incident_type,
                IncidentReportORM.reported_at >= time_cutoff,
                func.ST_DWithin(
                    cast(IncidentReportORM.location, Geography),
                    target_geog,
                    spatial_tolerance_m,
                ),
            )
            .limit(1)
        )
        res_spatial = await db.execute(stmt_spatial)
        return res_spatial.scalar_one_or_none()

    @classmethod
    async def create_incident(
        cls,
        db: AsyncSession,
        request: IncidentSubmitRequest,
        reporter_hash: str,
        ip_hash: str,
        source: str = "api",
    ) -> IncidentReportORM:
        """
        Create a new community incident report with sanitization, privacy protections,
        and initial audit logging.
        """
        # 1. Sanitize text: remove HTML, redact PII, neutralize prompt injections
        sanitized_desc, pii_detected, prompt_inj_detected = sanitize_text(request.description)

        # 2. Determine pilot region
        region = determine_pilot_region(request.latitude, request.longitude)

        # 3. Privacy location: store as PostGIS point
        # Note: In public responses, coordinates are coarsened to ~100m.
        location_geom = func.ST_SetSRID(
            func.ST_MakePoint(request.longitude, request.latitude),
            4326,
        )

        # 4. Check for duplicates
        duplicate_candidate = await cls.find_recent_duplicate(
            db=db,
            lat=request.latitude,
            lon=request.longitude,
            incident_type=request.incident_type.value,
            reporter_hash=reporter_hash,
        )

        is_dup = duplicate_candidate is not None
        initial_verification_status = "duplicate" if is_dup else "unverified"
        initial_moderation_status = "pending_review"

        moderation_notes_init = []
        if pii_detected:
            moderation_notes_init.append("Auto-flag: PII detected and redacted in description.")
        if prompt_inj_detected:
            moderation_notes_init.append("Auto-flag: Potential prompt-injection pattern neutralized.")
        if is_dup:
            moderation_notes_init.append(f"Auto-flag: Possible duplicate of {duplicate_candidate.id}")

        incident = IncidentReportORM(
            reporter_hash=reporter_hash,
            incident_type=request.incident_type.value,
            incident_subtype=request.incident_subtype,
            location=location_geom,
            location_approximate=True,
            location_accuracy_m=request.location_accuracy_m,
            incident_at=request.incident_at,
            description=request.description,
            description_sanitized=sanitized_desc,
            verification_status=initial_verification_status,
            is_emergency=request.is_emergency,
            escalated_to_112=request.is_emergency,
            duplicate_of=duplicate_candidate.id if duplicate_candidate else None,
            moderation_status=initial_moderation_status,
            moderation_notes="\n".join(moderation_notes_init) if moderation_notes_init else None,
            region=region,
            source=source,
            ip_hash=ip_hash,
        )

        db.add(incident)
        await db.flush()  # Generate UUID

        # 5. Create initial audit log event
        event = IncidentVerificationEventORM(
            incident_id=incident.id,
            event_type="submitted",
            performed_by="system",
            new_status=initial_moderation_status,
            notes=f"Report submitted via {source}. Region={region}. Emergency={request.is_emergency}",
        )
        db.add(event)

        await db.commit()
        await db.refresh(incident)
        return incident

    @staticmethod
    async def get_by_id(db: AsyncSession, incident_id: UUID) -> Optional[IncidentReportORM]:
        """Fetch incident report by UUID."""
        stmt = select(IncidentReportORM).where(IncidentReportORM.id == incident_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_moderation_queue(
        db: AsyncSession,
        status: str = "pending_review",
        region: Optional[str] = None,
        limit: int = 50,
    ) -> Tuple[List[IncidentReportORM], int, int]:
        """
        Retrieve queue of incidents for moderator review.
        Returns (items, total_in_filter, total_pending).
        """
        stmt = select(IncidentReportORM).where(IncidentReportORM.moderation_status == status)
        if region:
            stmt = stmt.where(IncidentReportORM.region == region)

        stmt = stmt.order_by(IncidentReportORM.reported_at.asc()).limit(limit)
        res = await db.execute(stmt)
        items = list(res.scalars().all())

        # Count total in pending_review
        stmt_pending = select(func.count(IncidentReportORM.id)).where(
            IncidentReportORM.moderation_status == "pending_review"
        )
        pending_count = (await db.execute(stmt_pending)).scalar() or 0

        return items, len(items), pending_count

    @staticmethod
    async def moderate_incident(
        db: AsyncSession,
        incident_id: UUID,
        action: str,
        moderator_id: str,
        reason_code: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[IncidentReportORM]:
        """
        Execute moderation action (approve, reject, archive, flag) and write audit log.
        """
        stmt = select(IncidentReportORM).where(IncidentReportORM.id == incident_id)
        res = await db.execute(stmt)
        incident = res.scalar_one_or_none()
        if not incident:
            return None

        previous_status = incident.moderation_status

        if action == "approve":
            new_status = "approved"
            event_type = "verified"
        elif action == "reject":
            new_status = "rejected"
            event_type = "rejected"
        elif action == "archive":
            new_status = "archived"
            event_type = "auto_expired"
        elif action == "flag":
            new_status = "pending_review"
            event_type = "flagged"
        else:
            raise ValueError(f"Invalid moderation action: {action}")

        now = datetime.now(timezone.utc)
        incident.moderation_status = new_status
        incident.moderated_at = now
        incident.moderated_by = moderator_id
        if reason_code:
            incident.moderation_reason = reason_code
        if notes:
            existing_notes = incident.moderation_notes or ""
            incident.moderation_notes = f"{existing_notes}\n[{now.isoformat()}] {moderator_id}: {notes}".strip()

        # Audit trail event
        audit_event = IncidentVerificationEventORM(
            incident_id=incident.id,
            event_type=event_type,
            performed_by=moderator_id,
            previous_status=previous_status,
            new_status=new_status,
            notes=f"Action: {action}. Reason: {reason_code or 'none'}. Notes: {notes or 'none'}",
        )
        db.add(audit_event)

        await db.commit()
        await db.refresh(incident)
        return incident

    @staticmethod
    async def get_public_incidents(
        db: AsyncSession,
        region: Optional[str] = None,
        incident_type: Optional[str] = None,
        days: int = 30,
        limit: int = 50,
    ) -> List[IncidentReportORM]:
        """
        Query approved community reports for public aggregate viewing.
        STRICT PRIVACY: Excludes unapproved, rejected, or pending reports.
        """
        days = max(1, min(days, 365))
        limit = max(1, min(limit, 100))
        time_cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        stmt = select(IncidentReportORM).where(
            IncidentReportORM.moderation_status == "approved",
            IncidentReportORM.reported_at >= time_cutoff,
        )

        if region:
            stmt = stmt.where(IncidentReportORM.region == region)
        if incident_type:
            stmt = stmt.where(IncidentReportORM.incident_type == incident_type)

        stmt = stmt.order_by(IncidentReportORM.reported_at.desc()).limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_public_nearby(
        db: AsyncSession,
        lat: float,
        lon: float,
        radius_m: int = 2000,
        incident_type: Optional[str] = None,
        days: int = 30,
        limit: int = 20,
    ) -> List[Tuple[IncidentReportORM, float]]:
        """
        Query approved community reports within radius_m using PostGIS geography ST_DWithin.
        Returns (IncidentReportORM, distance_in_metres) ordered by distance ascending.
        """
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            raise ValueError(f"Coordinates ({lat}, {lon}) out of bounds")

        radius_m = max(100, min(radius_m, 25000))
        limit = max(1, min(limit, 100))
        time_cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 365)))

        target_geog = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326).cast(Geography)

        distance_expr = func.ST_Distance(
            cast(IncidentReportORM.location, Geography),
            target_geog,
        ).label("distance_m")

        stmt = select(IncidentReportORM, distance_expr).where(
            IncidentReportORM.moderation_status == "approved",
            IncidentReportORM.reported_at >= time_cutoff,
            func.ST_DWithin(
                cast(IncidentReportORM.location, Geography),
                target_geog,
                radius_m,
            ),
        )

        if incident_type:
            stmt = stmt.where(IncidentReportORM.incident_type == incident_type)

        stmt = stmt.order_by(distance_expr.asc()).limit(limit)
        res = await db.execute(stmt)
        return [(row[0], float(row[1])) for row in res.all()]
