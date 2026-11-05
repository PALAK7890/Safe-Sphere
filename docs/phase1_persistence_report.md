# SafeSphere AI — Phase 1: Database Persistence Wiring Report

**Date of Execution:** 2026-10-27  
**Module:** PostGIS Spatial Database Persistence & Nearby Facilities API  
**Target Repository:** `/Users/PalakNst/Desktop/SafeSphere`  
**Pilot Geographic Area:** Delhi (NCT) & Sonipat (Haryana)

---

## 1. Executive Summary

Phase 1 establishes the full end-to-end database persistence layer connecting the `OSMFacilityAdapter` to PostgreSQL 16 + PostGIS 3.4. 

The previous placeholder stubs in `backend/app/api/facilities.py` and `backend/ingestion/tasks.py` have been replaced with a production-grade SQLAlchemy 2.0 asynchronous persistence repository (`FacilityRepository`), PostGIS spatial query engine (`ST_DWithin` & `ST_Distance` on WGS84 geography), idempotent batch upsert logic, route aliasing for `/api/v1/data-sources`, and port conflict resolution remapping the API host port to **8001**.

All 68 unit and integration tests are passing (100% pass rate).

---

## 2. Deliverables & Implemented Modules

### 2.1 Database Session & Connection Management
- **File:** [`backend/app/db/session.py`](../backend/app/db/session.py)
- **Engine:** SQLAlchemy 2.0 `create_async_engine` using `asyncpg`.
- **Connection Handling:** Configured with `pool_pre_ping=True`, environment-based pool sizing (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`), and automatic test-mode fallback to `NullPool` to prevent event-loop affinity conflicts during asynchronous testing.
- **Dependency:** `get_db()` async generator yielding active sessions for FastAPI route handlers with automatic transaction rollback on failure.

### 2.2 SQLAlchemy ORM Spatial Models
- **File:** [`backend/app/db/models.py`](../backend/app/db/models.py)
- **`EmergencyFacilityORM`**:
  - Primary Key: `UUID` (`as_uuid=True`, default `uuid.uuid4`).
  - Spatial Column: `location = Column(Geometry(geometry_type='POINT', srid=4326), nullable=False)`.
  - Generated Stored Columns: `latitude` and `longitude` mapped with `server_default=FetchedValue()` to prevent insertion errors into Postgres `GENERATED ALWAYS AS (ST_Y/X(location)) STORED` columns.
  - Native Enum Typing: `facility_type` and `osm_type` bound via `postgresql.ENUM` matching Postgres types (`facility_type`, `osm_element_type`).
  - Constraint: `CONSTRAINT uq_osm_id_type UNIQUE (osm_id, osm_type)`.
- **`DataSourceRegistryORM`**:
  - Mapped to `data_source_registry` with native enums `access_type_enum` and `geographic_level_enum`.

### 2.3 Facility Repository
- **File:** [`backend/app/db/repository.py`](../backend/app/db/repository.py)
- **`ensure_data_source(...)`**: Verifies and seeds parent data source entries in `data_source_registry` to maintain foreign key integrity.
- **`upsert_batch(db, facilities, chunk_size=500)`**:
  1. Validates coordinates (`-90 <= lat <= 90`, `-180 <= lon <= 180`).
  2. Sanitizes fallback facility names (`Unnamed <FacilityType>`).
  3. Sanitizes postal codes for `CHAR(6)`.
  4. Deduplicates within each batch by `(osm_id, osm_type)` to eliminate Postgres `"ON CONFLICT DO UPDATE command cannot affect row a second time"` errors.
  5. Executes PostgreSQL `INSERT ... ON CONFLICT (osm_id, osm_type) DO UPDATE SET ...` updating timestamps, names, quality scores, and contact details without duplicating rows.
- **`get_nearby(db, lat, lon, radius_m, facility_type, verified_only, limit)`**:
  1. Validates coordinate ranges and clamps radius between 100m and 50km.
  2. Calculates spatial distances in metres using `ST_Distance(location::geography, ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography)`.
  3. Applies spatial filtering with `ST_DWithin(...)`.
  4. Filters by active records, optional `facility_type`, and `verified_only`.
  5. Orders results by `distance_m ASC` and limits result set.
- **`get_by_id(db, facility_id)`**: Fetches a single active facility by UUID.

### 2.4 Connected API Endpoints
- **File:** [`backend/app/api/facilities.py`](../backend/app/api/facilities.py)
- `GET /api/v1/facilities/nearby`: Accepts `lat`, `lon`, optional `facility_type`, `radius_m`, `limit`, and `verified_only`. Returns `FacilityNearbyResponse` with `distance_m` on each facility and strict data disclaimers.
- `GET /api/v1/facilities/{id}`: Fetches facility details by UUID or returns 404 Not Found.

### 2.5 Data-Source Route Alias
- **File:** [`backend/app/main.py`](../backend/app/main.py)
- Mounted router at both `/api/v1/sources` and `/api/v1/data-sources`. Both routes utilize the same handler and schema, returning identical results.

### 2.6 Docker Compose & Port Remapping
- **File:** [`docker-compose.yml`](../docker-compose.yml)
- Remapped API service port from `"8000:8000"` to `"8001:8000"`, keeping container internal port at 8000 while eliminating conflicts with existing host services on port 8000.
- Updated documentation in `README.md` and health check documentation.

---

## 3. PostGIS Spatial Query Performance & Indexing

To ensure optimal execution of `ST_DWithin` on geography, the PostGIS schema includes both geometry and geography expression GiST indexes:

```sql
CREATE INDEX idx_facilities_location         ON emergency_facilities USING GIST (location);
CREATE INDEX idx_facilities_location_geog    ON emergency_facilities USING GIST (CAST(location AS geography));
```

Spatial query structure:
```sql
SELECT emergency_facilities.*,
       ST_Distance(location::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS distance_m
FROM emergency_facilities
WHERE is_active = TRUE
  AND ST_DWithin(location::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius_m)
ORDER BY distance_m ASC
LIMIT :limit;
```

---

## 4. End-to-End Live Demonstration Evidence

### 4.1 Ingestion & Idempotent Persistence Demonstration
A live batch of facilities in the Sonipat pilot area (`south=28.98, west=77.00, north=29.01, east=77.03`) was fetched from Overpass API and persisted into `safesphere_db`:

```
1. Ingesting from Overpass API...
   Fetched: 28, Valid: 28
2. Persisting batch to PostGIS database...
   Batch 1 persisted: 28, skipped: 0, errors: 0
   Total OSM facilities in DB: 29
3. Testing idempotency: Re-running exact same batch...
   Batch 2 persisted: 28
   Total OSM facilities in DB after second run: 29
   Idempotency successfully confirmed!
```

### 4.2 Live HTTP Verification on Host Port 8001
The application was launched on `http://127.0.0.1:8001` and tested over HTTP:

#### 1. Healthcheck: `GET /health`
```http
HTTP/1.1 200 OK
content-type: application/json

{"status":"ok"}
```

#### 2. Data Sources & Alias Check
- `GET /api/v1/sources` $\rightarrow$ `200 OK` (Loaded 21 external sources)
- `GET /api/v1/data-sources` $\rightarrow$ `200 OK` (Identical payload returned)

#### 3. Spatial Query on Port 8001: `GET /api/v1/facilities/nearby?lat=28.9946&lon=77.0268&radius_m=3000&limit=3`
```json
{
    "facilities": [
        {
            "facility_type": "hospital",
            "name": "Vardhman General Hospital",
            "latitude": 28.9946005,
            "longitude": 77.0268074,
            "addr_district": "Sonipat_pilot",
            "addr_postcode": "131001",
            "id": "d2db4e51-1bde-4823-a672-7b58361c416a",
            "source_id": "osm_overpass",
            "osm_id": 6993994145,
            "osm_type": "node",
            "source_verified": false,
            "data_quality_score": 40,
            "distance_m": 0.7,
            "data_notice": "Facility data sourced from OpenStreetMap and government directories. Contact details may be incomplete or outdated. Verify before use in emergencies.",
            "attribution": "© OpenStreetMap contributors (ODbL 1.0)"
        },
        {
            "facility_type": "hospital",
            "name": "Tulip Women Hospital",
            "latitude": 28.9943382,
            "longitude": 77.0270378,
            "addr_district": "Sonipat_pilot",
            "addr_postcode": "131001",
            "id": "aafc9fec-8428-4da3-913e-ca7b1b6e2954",
            "source_id": "osm_overpass",
            "osm_id": 7622516622,
            "osm_type": "node",
            "source_verified": false,
            "data_quality_score": 40,
            "distance_m": 37.1,
            "data_notice": "Facility data sourced from OpenStreetMap and government directories. Contact details may be incomplete or outdated. Verify before use in emergencies.",
            "attribution": "© OpenStreetMap contributors (ODbL 1.0)"
        }
    ],
    "count": 3,
    "search_lat": 28.9946,
    "search_lon": 77.0268,
    "radius_m": 3000,
    "data_notice": "Results include OpenStreetMap community data (not officially verified) and government directory data where available. For emergencies, call 112.",
    "attribution": "© OpenStreetMap contributors (ODbL 1.0)"
}
```

---

## 5. Automated Test Suite Results

The comprehensive test suite covers all units, repositories, spatial calculations, and API endpoints:

```bash
TESTING=true PYTHONPATH=./backend python3.13 -m pytest backend/tests/ -v
```

### Result Summary
```
============================== 68 passed in 5.93s ==============================
```

- **49 Adapter Tests (`test_osm_adapter.py`):** Bounding box query formatting, node and way centroid extraction, phone number sanitization, quality score calculation, unverified provenance tagging (`source_verified=False`).
- **19 Persistence Tests (`test_persistence.py`):**
  - Coordinate range and name validation.
  - Postal code 6-digit PIN sanitization.
  - Empty batch handling.
  - Database persistence and row verification in PostgreSQL.
  - Idempotent repeated ingestion without duplicate generation.
  - In-batch duplicate record deduplication.
  - `ST_DWithin` spatial radius filtering and distance computation in metres.
  - `facility_type` filter accuracy.
  - Empty area queries returning zero rows.
  - Single facility lookup by UUID and 404 handling.
  - `/api/v1/sources` and `/api/v1/data-sources` alias verification.
  - `/api/v1/facilities/nearby` schema and parameter validation.

---

## 6. Phase 1 Completion Criteria Checklist

| Requirement | Status | Evidence |
|---|---|---|
| **SQLAlchemy models for `emergency_facilities`** | ✅ Complete | [`backend/app/db/models.py`](../backend/app/db/models.py) |
| **Idempotent batch persistence repository** | ✅ Complete | [`backend/app/db/repository.py`](../backend/app/db/repository.py) (`upsert_batch`) |
| **PostGIS `ST_DWithin` spatial query** | ✅ Complete | Verified with geography-based distance and GiST indexing |
| **Nearby-facility API endpoint connected to DB** | ✅ Complete | [`backend/app/api/facilities.py`](../backend/app/api/facilities.py) |
| **Data source route alias (`/api/v1/data-sources`)** | ✅ Complete | Mounted in `main.py` and verified via HTTP |
| **API port conflict resolved (port 8001)** | ✅ Complete | Mapped in `docker-compose.yml`, verified with live curl on 8001 |
| **Celery task persistence wiring** | ✅ Complete | Updated `ingestion/tasks.py` with `_persist_facilities` |
| **Automated tests** | ✅ Complete | 68 passed in 5.93s |

**Phase 1 is complete and ready for Phase 2.**
