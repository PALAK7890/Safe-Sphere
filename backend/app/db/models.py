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
