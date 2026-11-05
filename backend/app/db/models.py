"""
SafeSphere AI — SQLAlchemy ORM Models
Corresponds to PostGIS schema in migrations/001_initial_schema.sql.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from geoalchemy2 import Geometry
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    FetchedValue,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


from sqlalchemy.dialects.postgresql import ENUM as PGEnum

access_type_enum = PGEnum(
    "public",
    "registration",
    "api_key",
    "partnership",
    "restricted",
    name="access_type_enum",
    create_type=False,
)

geographic_level_enum = PGEnum(
    "national",
    "state",
    "district",
    "city",
    "ward",
    name="geographic_level_enum",
    create_type=False,
)

facility_type_enum = PGEnum(
    "police_station",
    "fire_station",
    "hospital",
    "clinic",
    "pharmacy",
    "ambulance_post",
    "pcr_base",
    "emergency_shelter",
    name="facility_type",
    create_type=False,
)

osm_element_type_enum = PGEnum(
    "node",
    "way",
    "relation",
    name="osm_element_type",
    create_type=False,
)

incident_type_enum = PGEnum(
    "theft",
    "harassment",
    "assault",
    "road_accident",
    "fire",
    "flood",
    "suspicious_activity",
    "eve_teasing",
    "drunk_driving",
    "unsafe_road",
    "power_outage",
    "other",
    name="incident_type_enum",
    create_type=False,
)

verification_status_enum = PGEnum(
    "unverified",
    "under_review",
    "verified",
    "duplicate",
    "rejected",
    name="verification_status_enum",
    create_type=False,
)

severity_level_enum = PGEnum(
    "low",
    "medium",
    "high",
    "critical",
    name="severity_level_enum",
    create_type=False,
)

incident_source_enum = PGEnum(
    "app_ios",
    "app_android",
    "web",
    "api",
    name="incident_source_enum",
    create_type=False,
)

verification_event_type_enum = PGEnum(
    "submitted",
    "flagged",
    "moderation_started",
    "verified",
    "rejected",
    "duplicate_detected",
    "escalated",
    "auto_expired",
    name="verification_event_type_enum",
    create_type=False,
)


class DataSourceRegistryORM(Base):
    """Registry of external data sources with provenance and access requirements."""

    __tablename__ = "data_source_registry"

    source_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    provider: Mapped[str] = mapped_column(String(200), nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(300), nullable=False)
    official_url: Mapped[str] = mapped_column(Text, nullable=False)
    documentation_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    access_type: Mapped[str] = mapped_column(access_type_enum, nullable=False)
    licence: Mapped[str] = mapped_column(String(200), nullable=False)
    licence_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    geographic_coverage: Mapped[str] = mapped_column(geographic_level_enum, nullable=False)
    states_covered: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    update_frequency: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    data_format: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    has_coordinates: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(1), nullable=False)
    api_base_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requires_api_key: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    env_key_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rate_limit_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    commercial_use_permitted: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    attribution_required: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    limitations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ingestion_adapter: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    facilities: Mapped[List[EmergencyFacilityORM]] = relationship(
        "EmergencyFacilityORM", back_populates="data_source"
    )


class EmergencyFacilityORM(Base):
    """
    Emergency facilities (police, fire, hospitals, pharmacies).
    Stores PostGIS Point geometry with SRID 4326.
    latitude and longitude are generated/stored columns in PostgreSQL.
    """

    __tablename__ = "emergency_facilities"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("data_source_registry.source_id"), nullable=False
    )
    external_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    facility_type: Mapped[str] = mapped_column(facility_type_enum, nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    name_hi: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    address_raw: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    addr_street: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    addr_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    addr_district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    addr_state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    addr_postcode: Mapped[Optional[str]] = mapped_column(String(6), nullable=True)

    # PostGIS geometry column: Point in WGS84 (SRID 4326)
    location = Column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )

    # Generated stored columns in PostgreSQL (ST_Y(location), ST_X(location))
    # Marked as server_default=FetchedValue() so SQLAlchemy omits them from INSERT/UPDATE
    latitude: Mapped[float] = mapped_column(
        Float, server_default=FetchedValue(), nullable=False
    )
    longitude: Mapped[float] = mapped_column(
        Float, server_default=FetchedValue(), nullable=False
    )

    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    phone_secondary: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    opening_hours_raw: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    is_24h: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    beds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    services: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    jurisdiction_area = Column(Geometry(geometry_type="POLYGON", srid=4326), nullable=True)
    official_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    district_admin: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    osm_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    osm_type: Mapped[Optional[str]] = mapped_column(osm_element_type_enum, nullable=True)
    data_quality_score: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    source_fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    data_source: Mapped[DataSourceRegistryORM] = relationship(
        "DataSourceRegistryORM", back_populates="facilities"
    )


class IncidentReportORM(Base):
    """
    Community safety incident reports.
    Location is stored as PostGIS Point in WGS84 (SRID 4326).
    latitude and longitude are generated stored columns in PostgreSQL.
    """

    __tablename__ = "incident_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reporter_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    incident_type: Mapped[str] = mapped_column(incident_type_enum, nullable=False)
    incident_subtype: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    location = Column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    location_approximate: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    location_accuracy_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    latitude: Mapped[float] = mapped_column(
        Float, server_default=FetchedValue(), nullable=False
    )
    longitude: Mapped[float] = mapped_column(
        Float, server_default=FetchedValue(), nullable=False
    )

    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    incident_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_sanitized: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_refs: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)

    verification_status: Mapped[str] = mapped_column(
        verification_status_enum, default="unverified", nullable=False
    )
    severity: Mapped[Optional[str]] = mapped_column(severity_level_enum, nullable=True)
    is_emergency: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    escalated_to_112: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    official_complaint_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    duplicate_of: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("incident_reports.id"), nullable=True
    )
    upvote_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Moderation workflow fields
    moderation_status: Mapped[str] = mapped_column(
        String(50), default="pending_review", nullable=False
    )
    moderation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    moderation_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    moderated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    moderated_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    source: Mapped[str] = mapped_column(incident_source_enum, default="api", nullable=False)
    ip_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    verification_events: Mapped[List[IncidentVerificationEventORM]] = relationship(
        "IncidentVerificationEventORM", back_populates="incident", cascade="all, delete-orphan"
    )


class IncidentVerificationEventORM(Base):
    """Audit log of moderation and verification events for an incident."""

    __tablename__ = "incident_verification_events"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("incident_reports.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(verification_event_type_enum, nullable=False)
    performed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    previous_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    incident: Mapped[IncidentReportORM] = relationship(
        "IncidentReportORM", back_populates="verification_events"
    )
