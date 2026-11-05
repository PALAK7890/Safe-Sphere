"""
SafeSphere AI — Phase 1 Persistence & Spatial API Integration Tests
Tests for SQLAlchemy models, FacilityRepository, PostGIS ST_DWithin queries,
batch ingestion idempotency, and FastAPI endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, DataSourceRegistryORM, EmergencyFacilityORM
from app.db.repository import BatchResult, FacilityRepository
from app.db.session import DATABASE_URL, get_db
from app.main import app
from app.models.facility import FacilityType
from ingestion.osm_adapter import OSMFacility


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Function-scoped async engine for testing against local PostGIS."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Provides an isolated async session for database tests with cleanup."""
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        # Ensure data source registry has osm_overpass
        await FacilityRepository.ensure_data_source(session)
        yield session
        # Cleanup test facilities after each test
        await session.execute(
            delete(EmergencyFacilityORM).where(
                EmergencyFacilityORM.source_id == "test_source"
            )
        )
        await session.commit()


@pytest.fixture
def api_client():
    """FastAPI TestClient for testing HTTP endpoints."""
    return TestClient(app)


def make_test_facility(
    osm_id: int = 100001,
    osm_type: str = "node",
    facility_type: FacilityType = FacilityType.HOSPITAL,
    name: str = "Test Metro Hospital",
    lat: float = 28.6139,
    lon: float = 77.2090,
    source_id: str = "test_source",
    source_verified: bool = False,
    score: int = 70,
) -> OSMFacility:
    """Helper to construct OSMFacility instances for testing."""
    return OSMFacility(
        osm_id=osm_id,
        osm_type=osm_type,
        facility_type=facility_type,
        latitude=lat,
        longitude=lon,
        name=name,
        name_hi=f"{name} (हिन्दी)",
        addr_street="Main Road",
        addr_city="Delhi",
        addr_postcode="110001",
        phone="+91-11-23010000",
        phone_secondary="+91-11-23010001",
        website="https://test-hospital.example.com",
        opening_hours_raw="24/7",
        source_id=source_id,
        source_verified=source_verified,
        licence="ODbL 1.0",
        attribution="© OpenStreetMap contributors",
        source_fetched_at=datetime.now(timezone.utc),
        data_quality_score=score,
        region="delhi",
    )


# ---------------------------------------------------------------------------
# Unit Tests: Validation and Normalization
# ---------------------------------------------------------------------------

class TestFacilityValidation:
    def test_validate_valid_facility(self):
        fac = make_test_facility(osm_id=101, name="Apollo Hospital", lat=28.5355, lon=77.2831)
        norm = FacilityRepository._validate_and_normalize(fac)
        assert norm is not None
        assert norm["osm_id"] == 101
        assert norm["name"] == "Apollo Hospital"
        assert norm["addr_postcode"] == "110001"
        assert norm["facility_type"] == "hospital"
        assert norm["source_verified"] is False

    def test_validate_invalid_latitude_rejected(self):
        fac = make_test_facility(osm_id=102, lat=95.0, lon=77.0)
        norm = FacilityRepository._validate_and_normalize(fac)
        assert norm is None

    def test_validate_invalid_longitude_rejected(self):
        fac = make_test_facility(osm_id=103, lat=28.0, lon=200.0)
        norm = FacilityRepository._validate_and_normalize(fac)
        assert norm is None

    def test_validate_missing_name_generates_fallback(self):
        fac = make_test_facility(osm_id=104, name="", facility_type=FacilityType.POLICE_STATION)
        norm = FacilityRepository._validate_and_normalize(fac)
        assert norm is not None
        assert norm["name"] == "Unnamed Police Station"

    def test_validate_postcode_cleaned_to_six_digits(self):
        fac = make_test_facility(osm_id=105, name="Hospital")
        fac.addr_postcode = "110001-02"
        norm = FacilityRepository._validate_and_normalize(fac)
        assert norm is not None
        assert norm["addr_postcode"] is None  # 8 digits not valid 6-digit PIN

        fac.addr_postcode = "110 092"
        norm = FacilityRepository._validate_and_normalize(fac)
        assert norm is not None
        assert norm["addr_postcode"] == "110092"


# ---------------------------------------------------------------------------
# Integration Tests: Database Persistence & Idempotency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestDatabasePersistence:
    async def test_upsert_batch_empty_list(self, db_session: AsyncSession):
        result = await FacilityRepository.upsert_batch(db_session, [])
        assert result.total == 0
        assert result.persisted == 0
        assert len(result.errors) == 0

    async def test_upsert_batch_and_query(self, db_session: AsyncSession):
        # Ensure test source exists in registry
        await FacilityRepository.ensure_data_source(
            db_session, source_id="test_source", dataset_name="Test Source Dataset"
        )

        fac1 = make_test_facility(osm_id=200001, name="Safdarjung Hospital", lat=28.5700, lon=77.2080)
        fac2 = make_test_facility(osm_id=200002, name="AIIMS Hospital", lat=28.5672, lon=77.2100)

        result = await FacilityRepository.upsert_batch(db_session, [fac1, fac2])
        assert result.total == 2
        assert result.valid == 2
        assert result.persisted == 2
        assert len(result.errors) == 0

        # Verify records exist in database
        stmt = select(EmergencyFacilityORM).where(
            EmergencyFacilityORM.osm_id.in_([200001, 200002])
        )
        rows = (await db_session.execute(stmt)).scalars().all()
        assert len(rows) == 2
        names = {r.name for r in rows}
        assert "Safdarjung Hospital" in names
        assert "AIIMS Hospital" in names

    async def test_idempotent_repeated_ingestion(self, db_session: AsyncSession):
        await FacilityRepository.ensure_data_source(db_session, source_id="test_source")

        fac = make_test_facility(osm_id=300001, name="Original Hospital Name", lat=28.6139, lon=77.2090)

        # First run: inserts record
        res1 = await FacilityRepository.upsert_batch(db_session, [fac])
        assert res1.persisted == 1

        # Second run with modified name: updates without creating a duplicate
        fac.name = "Updated Hospital Name"
        fac.data_quality_score = 95
        res2 = await FacilityRepository.upsert_batch(db_session, [fac])
        assert res2.persisted == 1

        # Check only 1 row exists
        stmt = select(EmergencyFacilityORM).where(EmergencyFacilityORM.osm_id == 300001)
        records = (await db_session.execute(stmt)).scalars().all()
        assert len(records) == 1
        assert records[0].name == "Updated Hospital Name"
        assert records[0].data_quality_score == 95

    async def test_batch_with_duplicate_records_within_same_batch(self, db_session: AsyncSession):
        await FacilityRepository.ensure_data_source(db_session, source_id="test_source")

        # Two records with identical (osm_id, osm_type) in single batch
        fac_a = make_test_facility(osm_id=400001, name="Hospital Copy A")
        fac_b = make_test_facility(osm_id=400001, name="Hospital Copy B")

        res = await FacilityRepository.upsert_batch(db_session, [fac_a, fac_b])
        assert res.total == 2
        assert res.valid == 2
        assert res.persisted == 1  # Deduplicated within batch before insert

        stmt = select(EmergencyFacilityORM).where(EmergencyFacilityORM.osm_id == 400001)
        records = (await db_session.execute(stmt)).scalars().all()
        assert len(records) == 1


# ---------------------------------------------------------------------------
# Integration Tests: PostGIS Spatial Queries
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestSpatialQueries:
    async def test_get_nearby_returns_facilities_within_radius_with_distance(
        self, db_session: AsyncSession
    ):
        await FacilityRepository.ensure_data_source(db_session, source_id="test_source")

        # Reference center: Connaught Place (28.6315, 77.2167)
        cp_lat, cp_lon = 28.6315, 77.2167

        # Near facility: ~500m away (28.6350, 77.2167)
        fac_near = make_test_facility(
            osm_id=500001,
            name="Near CP Clinic",
            lat=28.6350,
            lon=77.2167,
            facility_type=FacilityType.CLINIC,
        )

        # Far facility: Sonipat (~40km away) (28.9931, 77.0151)
        fac_far = make_test_facility(
            osm_id=500002,
            name="Far Sonipat Hospital",
            lat=28.9931,
            lon=77.0151,
            facility_type=FacilityType.HOSPITAL,
        )

        await FacilityRepository.upsert_batch(db_session, [fac_near, fac_far])

        # Query with 2km radius from Connaught Place
        results = await FacilityRepository.get_nearby(
            db=db_session,
            lat=cp_lat,
            lon=cp_lon,
            radius_m=2000,
        )

        # Must include fac_near, must NOT include fac_far
        osm_ids = [r[0].osm_id for r in results]
        assert 500001 in osm_ids
        assert 500002 not in osm_ids

        # Check distance in metres is positive and reasonable (~380-450m)
        near_tuple = next(r for r in results if r[0].osm_id == 500001)
        distance = near_tuple[1]
        assert 300 < distance < 600

    async def test_get_nearby_facility_type_filtering(self, db_session: AsyncSession):
        await FacilityRepository.ensure_data_source(db_session, source_id="test_source")

        lat, lon = 28.6139, 77.2090
        fac_police = make_test_facility(
            osm_id=600001,
            name="Central Police Station",
            facility_type=FacilityType.POLICE_STATION,
            lat=28.6145,
            lon=77.2095,
        )
        fac_hospital = make_test_facility(
            osm_id=600002,
            name="Central Hospital",
            facility_type=FacilityType.HOSPITAL,
            lat=28.6148,
            lon=77.2098,
        )

        await FacilityRepository.upsert_batch(db_session, [fac_police, fac_hospital])

        # Query only police stations
        police_results = await FacilityRepository.get_nearby(
            db=db_session,
            lat=lat,
            lon=lon,
            radius_m=2000,
            facility_type="police_station",
        )
        police_ids = [r[0].osm_id for r in police_results]
        assert 600001 in police_ids
        assert 600002 not in police_ids

    async def test_get_nearby_empty_location(self, db_session: AsyncSession):
        # Empty middle of Thar desert
        results = await FacilityRepository.get_nearby(
            db=db_session,
            lat=27.0000,
            lon=71.0000,
            radius_m=1000,
        )
        assert len(results) == 0

    async def test_get_by_id(self, db_session: AsyncSession):
        await FacilityRepository.ensure_data_source(db_session, source_id="test_source")

        fac = make_test_facility(osm_id=700001, name="Lookup Hospital")
        await FacilityRepository.upsert_batch(db_session, [fac])

        stmt = select(EmergencyFacilityORM).where(EmergencyFacilityORM.osm_id == 700001)
        record = (await db_session.execute(stmt)).scalar_one()

        fetched = await FacilityRepository.get_by_id(db_session, record.id)
        assert fetched is not None
        assert fetched.name == "Lookup Hospital"

        # Nonexistent ID
        missing = await FacilityRepository.get_by_id(db_session, uuid.uuid4())
        assert missing is None


# ---------------------------------------------------------------------------
# API Endpoint Integration Tests
# ---------------------------------------------------------------------------

class TestAPIEndpoints:
    def test_sources_endpoint(self, api_client: TestClient):
        response = api_client.get("/api/v1/sources")
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data
        assert "count" in data
        assert data["count"] > 0
        assert "notice" in data

    def test_data_sources_alias_endpoint(self, api_client: TestClient):
        """GET /api/v1/data-sources must return the identical payload as /api/v1/sources."""
        resp_sources = api_client.get("/api/v1/sources")
        resp_alias = api_client.get("/api/v1/data-sources")

        assert resp_alias.status_code == 200
        assert resp_alias.json() == resp_sources.json()

    def test_facilities_nearby_endpoint_returns_json_schema(self, api_client: TestClient):
        response = api_client.get(
            "/api/v1/facilities/nearby?lat=28.6139&lon=77.2090&radius_m=5000"
        )
        assert response.status_code == 200
        data = response.json()
        assert "facilities" in data
        assert "count" in data
        assert "search_lat" in data
        assert "search_lon" in data
        assert "radius_m" in data
        assert "data_notice" in data
        assert "attribution" in data
        assert data["search_lat"] == 28.6139

    def test_facilities_nearby_coordinate_validation(self, api_client: TestClient):
        # Latitude out of India bounds (< 8.0)
        resp = api_client.get("/api/v1/facilities/nearby?lat=5.0&lon=77.2090")
        assert resp.status_code == 422

        # Longitude out of India bounds (> 98.0)
        resp2 = api_client.get("/api/v1/facilities/nearby?lat=28.6139&lon=105.0")
        assert resp2.status_code == 422

    def test_get_single_facility_404_for_unknown_uuid(self, api_client: TestClient):
        random_uuid = str(uuid.uuid4())
        response = api_client.get(f"/api/v1/facilities/{random_uuid}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Facility not found"

    def test_health_check(self, api_client: TestClient):
        response = api_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
