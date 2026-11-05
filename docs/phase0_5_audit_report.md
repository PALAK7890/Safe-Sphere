# SafeSphere AI — Phase 0.5 Repository Audit & End-to-End Verification Report
**Date of Audit:** 2026-10-26  
**Auditor:** Senior Data Engineer, Geospatial Systems Architect & API Researcher  
**Target Repository:** `/Users/PalakNst/Desktop/SafeSphere`  
**Pilot Geographic Focus:** Delhi (NCT) & Sonipat (Haryana)

---

## 1. Repository Files Actually Inspected

The repository was inspected from disk at `/Users/PalakNst/Desktop/SafeSphere`. The file inventory is as follows:

```
/Users/PalakNst/Desktop/SafeSphere/
├── .env.example                               # Environment template (placeholders only)
├── .env                                       # Local environment copy (created during audit)
├── .gitignore                                 # Git ignore rules (protects .env, binaries, temp files)
├── README.md                                  # Developer and operational overview
├── docker-compose.yml                         # Multi-container orchestration (db, redis, api, worker, beat)
├── migrations/
│   └── 001_initial_schema.sql                 # PostGIS DDL with 10 tables, enums, triggers & seeds
├── data/
│   └── source_registry.csv                    # 21 cataloged data sources with verification metadata
├── docs/
│   ├── api_access_matrix.md                   # API quotas, authentication, costs, and terms
│   ├── data_architecture.md                   # System ingestion and adapter design
│   ├── data_dictionary.md                     # Schema definitions, PostGIS fields, and provenance
│   ├── data_source_audit.md                   # Primary source investigations and A–F status ratings
│   ├── emergency_integration_plan.md          # 112 ERSS integration pathways and legal disclaimers
│   ├── implementation_roadmap.md              # Phased rollout schedule (Phases 1–4)
│   └── privacy_and_data_governance.md         # DPDPA 2023 alignment, fuzzing rules, and risk model ethics
├── backend/
│   ├── Dockerfile                             # Python 3.12-slim container definition
│   ├── requirements.txt                       # Python dependency manifest
│   ├── app/
│   │   ├── main.py                            # FastAPI application entry point with legal notices
│   │   ├── api/
│   │   │   ├── facilities.py                  # Emergency facility search endpoints
│   │   │   ├── incidents.py                   # Community incident submission endpoint
│   │   │   ├── weather.py                     # Open-Meteo & IMD alert endpoints
│   │   │   └── sources.py                     # Data source transparency registry endpoint
│   │   ├── models/
│   │   │   ├── facility.py                    # Pydantic schemas for facilities and queries
│   │   │   └── incident.py                    # Pydantic schemas for incidents and safety notices
│   │   └── providers/
│   │       ├── base_pcr_provider.py           # Abstract PCR vehicle provider interface
│   │       └── simulated_pcr_provider.py      # Development-only simulated PCR vehicle provider
│   ├── ingestion/
│   │   ├── osm_adapter.py                     # OpenStreetMap Overpass API ingestion adapter
│   │   └── tasks.py                           # Celery asynchronous task definitions and beat schedules
│   └── tests/
│       └── test_osm_adapter.py                # Pytest unit tests for OSM adapter (49 test cases)
└── scripts/                                   # Empty directory (created during setup)
```

### Discrepancies Against Walkthrough Map
1. **Git Repository Status:** The directory was not initialized as a Git repository (`fatal: not a git repository`). Initialized with `git init` during this audit.
2. **Alembic Migration Environment:** `docs/data_architecture.md` and `README.md` documented Alembic migration execution (`alembic upgrade head`, `env.py`, `script.py.mako`), but only raw SQL (`migrations/001_initial_schema.sql`) existed; no `alembic.ini` or migration environment was present.
3. **Empty Modules / Placeholders:**
   - `scripts/` directory was completely empty.
   - `backend/app/api/facilities.py` returned an empty hardcoded array (`facilities=[]`) with a `# TODO: Replace with real DB query` comment.
   - `backend/ingestion/tasks.py` contained `# TODO: await FacilityRepository.upsert_batch(facilities)` without a functioning ORM/DB repository class.
   - `django_celery_beat` was referenced in `docker-compose.yml`, but was not installed in `requirements.txt`.
4. **Endpoint Path Inconsistency:**
   - Walkthrough and prompt mentioned `/api/v1/data-sources`. The actual registered FastAPI endpoint was `/api/v1/sources`.
   - Walkthrough mentioned `/api/v1/facilities`. The actual router only implemented `/api/v1/facilities/nearby` and `/api/v1/facilities/{id}` (`GET /api/v1/facilities` returned `404 Not Found`).

---

## 2. Verification of Walkthrough Claims

| Claim from Walkthrough | Status | Evidence / Analysis |
|---|---|---|
| **OSM Overpass Ingestion Adapter implemented** | **VERIFIED** | Implemented in `backend/ingestion/osm_adapter.py`. Handles node and way centroids, sanitizes phone numbers, tags records with `source_verified=False`, computes quality scores. |
| **Simulated PCR Provider with disclaimers** | **VERIFIED** | `backend/app/providers/simulated_pcr_provider.py` marks all vehicles with `is_simulated=True`, returns non-empty disclaimers, and restricts coordinates to bounding boxes. Seeded in DB with `is_simulated=TRUE`. |
| **49 Unit Tests exist and pass** | **VERIFIED** | Executed via `pytest backend/tests/test_osm_adapter.py`. All 49 tests pass in 0.10s. |
| **PostGIS Database Schema created** | **VERIFIED** | 10 tables/relations created in PostgreSQL 16 + PostGIS 3.4 (`safesphere_db`). Verified via `\dt`. |
| **Live OpenStreetMap Overpass integration working** | **VERIFIED** (after defect fix) | Successfully executed live query to `overpass-api.de` for Sonipat city center (`28.98, 77.00, 29.01, 77.03`). Retrieved and parsed 28 valid facilities. |
| **Automated End-to-End Persistence to Database** | **PARTIALLY VERIFIED** | Direct database upsert and idempotency verified via PostGIS SQL (`ON CONFLICT (osm_id, osm_type) DO UPDATE`). However, the glue connecting `OSMFacilityAdapter` to the DB in `tasks.py` (`FacilityRepository`) is a placeholder stub. |
| **FastAPI Retrieval of Persisted Records** | **NOT VERIFIED** | `/api/v1/facilities/nearby` currently returns an empty stub response (`facilities: []`). Database query integration was scoped for Phase 1. |
| **DPDPA 2023 Compliance** | **PARTIALLY VERIFIED** | Policies, governance, and disclaimers are documented in `privacy_and_data_governance.md`. However, technical controls (automated PII scrubbing, consent token management, GPS road snapping) remain commented `# TODO` stubs in `incidents.py`. |

---

## 3. Test Commands and Actual Results

### Test Execution Details
- **Python Version:** 3.13.6 (`/usr/local/bin/python3.13`)
- **Pytest Version:** 9.1.1
- **Plugins:** `pytest-asyncio-1.4.1`, `anyio-4.15.1`

### Execution Command
```bash
PYTHONPATH=/Users/PalakNst/Desktop/SafeSphere/backend \
/usr/local/bin/python3.13 -m pytest /Users/PalakNst/Desktop/SafeSphere/backend/tests/test_osm_adapter.py -v
```

### Raw Test Results
```
============================= test session starts ==============================
platform darwin -- Python 3.13.6, pytest-9.1.1, pluggy-1.7.0 -- /usr/local/bin/python3.13
cachedir: .pytest_cache
rootdir: /Users/PalakNst/Desktop/SafeSphere
plugins: asyncio-1.4.1, anyio-4.15.1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 49 items

backend/tests/test_osm_adapter.py::TestBuildOverpassQuery::test_contains_bbox PASSED [  2%]
backend/tests/test_osm_adapter.py::TestBuildOverpassQuery::test_contains_amenity_tag PASSED [  4%]
backend/tests/test_osm_adapter.py::TestBuildOverpassQuery::test_output_format_json PASSED [  6%]
backend/tests/test_osm_adapter.py::TestBuildOverpassQuery::test_includes_node_way_relation PASSED [  8%]
backend/tests/test_osm_adapter.py::TestBuildOverpassQuery::test_out_center_for_way_centroids PASSED [ 10%]
backend/tests/test_osm_adapter.py::TestExtractLatLon::test_node_direct_coordinates PASSED [ 12%]
backend/tests/test_osm_adapter.py::TestExtractLatLon::test_way_uses_center PASSED [ 14%]
backend/tests/test_osm_adapter.py::TestExtractLatLon::test_way_without_center_returns_none PASSED [ 16%]
backend/tests/test_osm_adapter.py::TestExtractLatLon::test_relation_uses_center PASSED [ 18%]
backend/tests/test_osm_adapter.py::TestCleanPhone::test_none_returns_none PASSED [ 20%]
backend/tests/test_osm_adapter.py::TestCleanPhone::test_empty_string_returns_none PASSED [ 22%]
backend/tests/test_osm_adapter.py::TestCleanPhone::test_too_short_returns_none PASSED [ 24%]
backend/tests/test_osm_adapter.py::TestCleanPhone::test_valid_phone_trimmed PASSED [ 26%]
backend/tests/test_osm_adapter.py::TestCleanPhone::test_valid_mobile_kept PASSED [ 28%]
backend/tests/test_osm_adapter.py::TestCleanPhone::test_long_phone_truncated_to_50 PASSED [ 30%]
backend/tests/test_osm_adapter.py::TestParseOSMElement::test_valid_police_node PASSED [ 32%]
backend/tests/test_osm_adapter.py::TestParseOSMElement::test_valid_hospital_way PASSED [ 34%]
backend/tests/test_osm_adapter.py::TestParseOSMElement::test_fire_station_parsed PASSED [ 36%]
backend/tests/test_osm_adapter.py::TestParseOSMElement::test_pharmacy_parsed PASSED [ 38%]
backend/tests/test_osm_adapter.py::TestParseOSMElement::test_unknown_amenity_returns_none PASSED [ 40%]
backend/tests/test_osm_adapter.py::TestParseOSMElement::test_node_without_coordinates_returns_none PASSED [ 42%]
backend/tests/test_osm_adapter.py::TestParseOSMElement::test_way_without_center_returns_none PASSED [ 44%]
backend/tests/test_osm_adapter.py::TestParseOSMElement::test_out_of_bounds_coordinates_returns_none PASSED [ 46%]
backend/tests/test_osm_adapter.py::TestParseOSMElement::test_hindi_name_extracted PASSED [ 48%]
backend/tests/test_osm_adapter.py::TestParseOSMElement::test_address_fields_extracted PASSED [ 51%]
backend/tests/test_osm_adapter.py::TestParseOSMElement::test_source_id_is_osm_overpass PASSED [ 53%]
backend/tests/test_osm_adapter.py::TestParseOSMElement::test_licence_is_odbl PASSED [ 55%]
backend/tests/test_osm_adapter.py::TestParseOSMElement::test_attribution_contains_osm PASSED [ 57%]
backend/tests/test_osm_adapter.py::TestComputeQualityScore::test_minimal_facility_scores_40 PASSED [ 59%]
backend/tests/test_osm_adapter.py::TestComputeQualityScore::test_with_phone_scores_60 PASSED [ 61%]
backend/tests/test_osm_adapter.py::TestComputeQualityScore::test_with_address_scores_60 PASSED [ 63%]
backend/tests/test_osm_adapter.py::TestComputeQualityScore::test_fully_complete_unverified_scores_80 PASSED [ 65%]
backend/tests/test_osm_adapter.py::TestComputeQualityScore::test_verified_scores_100 PASSED [ 67%]
backend/tests/test_osm_adapter.py::TestComputeQualityScore::test_no_name_scores_zero_baseline PASSED [ 69%]
backend/tests/test_osm_adapter.py::TestParseOverpassResponse::test_parses_multiple_elements PASSED [ 71%]
backend/tests/test_osm_adapter.py::TestParseOverpassResponse::test_skips_invalid_amenity PASSED [ 73%]
backend/tests/test_osm_adapter.py::TestParseOverpassResponse::test_empty_response PASSED [ 75%]
backend/tests/test_osm_adapter.py::TestParseOverpassResponse::test_mixes_nodes_and_ways PASSED [ 77%]
backend/tests/test_osm_adapter.py::TestDeduplicate::test_removes_exact_osm_id_duplicates PASSED [ 79%]
backend/tests/test_osm_adapter.py::TestDeduplicate::test_unique_ids_unchanged PASSED [ 81%]
backend/tests/test_osm_adapter.py::TestOSMFacilityAdapterIngestion::test_ingest_region_returns_facilities PASSED [ 83%]
backend/tests/test_osm_adapter.py::TestOSMFacilityAdapterIngestion::test_ingest_region_handles_api_failure PASSED [ 85%]
backend/tests/test_osm_adapter.py::TestOSMFacilityAdapterIngestion::test_all_returned_facilities_are_not_verified PASSED [ 87%]
backend/tests/test_osm_adapter.py::TestOSMFacilityAdapterIngestion::test_all_facilities_have_attribution PASSED [ 89%]
backend/tests/test_osm_adapter.py::TestOSMFacilityAdapterIngestion::test_sonipat_region_ingested PASSED [ 91%]
backend/tests/test_osm_adapter.py::TestOSMFacilityAdapterIngestion::test_ingestion_result_tracks_raw_data_hash PASSED [ 93%]
backend/tests/test_osm_adapter.py::TestConstants::test_delhi_bbox_bounds PASSED [ 95%]
backend/tests/test_osm_adapter.py::TestConstants::test_sonipat_bbox_bounds PASSED [ 97%]
backend/tests/test_osm_adapter.py::TestConstants::test_required_facility_tags_present PASSED [100%]

============================== 49 passed in 0.10s ==============================
```

---

## 4. Live Data Ingestion Results

A permitted, bounded request was executed against the primary Overpass API interpreter (`https://overpass-api.de/api/interpreter`) targeting Sonipat city center (`28.98, 77.00, 29.01, 77.03`).

### Execution Summary
- **Target Area:** Sonipat Urban Core (`south=28.98, west=77.00, north=29.01, east=77.03`)
- **Tags Filtered:** `amenity=police`, `amenity=hospital`, `amenity=fire_station`
- **User-Agent Sent:** `SafeSphere-AI/1.0 (contact@safesphere.ai) - github.com/safesphere-ai`
- **Fetched Elements:** **28**
- **Valid Facilities Parsed:** **28**
- **Skipped Elements:** **0**
- **Errors Encountered:** **0**
- **Raw Response Hash (SHA-256):** `d1b5444c741067e35a04ccaa188d4161ebc49ebad15527af063f5ae0cd8c8f57`

### Sample Parsed Records
1. **Vardhman General Hospital**: `facility_type=hospital`, Lat/Lon: `(28.9946005, 77.0268074)`, `source_verified=False`, `score=40`
2. **Sarita Jain Hospital**: `facility_type=hospital`, Lat/Lon: `(28.9946272, 77.0049938)`, `source_verified=False`, `score=40`
3. **Janta Charitable Hospital**: `facility_type=hospital`, Lat/Lon: `(28.9883968, 77.0152077)`, `source_verified=False`, `score=40`
4. **Memorial Hospital**: `facility_type=hospital`, Lat/Lon: `(28.9945198, 77.0247543)`, `source_verified=False`, `score=40`
5. **Chauhan Hospital**: `facility_type=hospital`, Lat/Lon: `(28.9842252, 77.0149903)`, `source_verified=False`, `score=40`

### Deduplication Verification
- **Test:** Injected 28 duplicates into a 56-element list and called `adapter.deduplicate()`.
- **Result:** Exact list reduction back to 28 records. Verified idempotency.

---

## 5. Database and API Integration Results

### PostgreSQL / PostGIS Service Health
- **Container Name:** `safesphere_db` (Image: `postgis/postgis:16-3.4`)
- **Container Status:** `Up About a minute (healthy)`
- **Port:** `0.0.0.0:5432->5432/tcp`
- **Database Name:** `safesphere_db`
- **PostGIS Extensions:** `postgis`, `pg_trgm`, `plpgsql` verified active.

### Schema & Migration Execution
The initial migration (`migrations/001_initial_schema.sql`) executed automatically upon container initialization. 10 relations confirmed present:
1. `administrative_boundaries`
2. `authorized_emergency_integrations`
3. `data_source_registry`
4. `emergency_facilities`
5. `incident_reports`
6. `incident_verification_events`
7. `official_incident_statistics`
8. `road_network_metadata`
9. `user_alert_subscriptions`
10. `spatial_ref_sys` (PostGIS metadata)

### Database Upsert & Deduplication Test
Direct SQL upsert test executed on `emergency_facilities`:
```sql
INSERT INTO emergency_facilities (
    source_id, facility_type, name, location,
    source_verified, osm_id, osm_type, data_quality_score
) VALUES (
    'osm_overpass', 'hospital', 'Vardhman General Hospital',
    ST_SetSRID(ST_MakePoint(77.0268074, 28.9946005), 4326),
    FALSE, 1234567, 'node', 40
)
ON CONFLICT (osm_id, osm_type) DO UPDATE
SET name = EXCLUDED.name, updated_at = NOW();
```
- **Result:** Two consecutive inserts with identical `(osm_id, osm_type)` produced exactly 1 stored row. PostGIS `ST_X` and `ST_Y` generated stored columns `latitude` (`28.9946005`) and `longitude` (`77.0268074`) accurately.

### Redis Service Health
- **Container Name:** `safesphere_redis` (Image: `redis:7-alpine`)
- **Container Status:** `Up About a minute (healthy)`
- **Healthcheck:** `redis-cli ping` responded `PONG`.

### FastAPI Endpoint Verification (via TestClient)
| Endpoint | Expected Path | Actual Path Tested | HTTP Status | Response Details |
|---|---|---|---|---|
| Service Root | `/` | `/` | **200 OK** | Returns legal attribution, 112 emergency notice, and version metadata. |
| Healthcheck | `/health` | `/health` | **200 OK** | `{"status": "ok"}` |
| Nearby Facilities | `/api/v1/facilities/nearby` | `/api/v1/facilities/nearby` | **200 OK** | Returns valid schema with safety notices and attribution; data array is currently empty stub. |
| Facility List | `/api/v1/facilities` | `/api/v1/facilities` | **404 Not Found** | Router does not implement generic list endpoint; only `/nearby` and `/{id}` are defined. |
| Data Sources | `/api/v1/data-sources` | `/api/v1/sources` | **200 OK** (on `/sources`) | Returns 21 cataloged data sources from `source_registry.csv`. Returns 404 on `/data-sources`. |
| Current Weather | `/api/v1/weather/current` | `/api/v1/weather/current` | **200 OK** | Live Open-Meteo call succeeded; returned real Delhi temperature (`28.0°C`). |
| Submit Incident | `/api/v1/incidents` | `/api/v1/incidents` | **201 Created** | Returned generated incident UUID, mandatory disclaimer, and official helpline directory (112, etc.). |

---

## 6. Security, Privacy & Licensing Audit

### 1. DPDPA 2023 Technical Readiness
- **Finding:** While documentation defines retention limits, fuzzed coordinates, and PII anonymization, the application code contains no user authentication or active PII scrubbing filters (`# TODO: scrub_pii` and `# TODO: snap_to_road`).
- **Risk:** High if opened to public traffic without completing the moderation and sanitization layer.

### 2. Live Patrol & Emergency Boundaries
- **Finding:** All simulated patrol vehicles are strictly identified with `is_simulated=True`, prefixed with `SIM-PCR-`, and include non-suppressible warning banners. The database explicitly records `is_live=FALSE`.
- **Finding:** Incident responses prominently declare that submissions are **not** official police complaints and direct users to 112 and official state e-FIR portals.

### 3. Licensing & Attribution Compliance
- **OSM ODbL 1.0:** Handled properly in all responses (`© OpenStreetMap contributors`).
- **Open-Meteo CC BY 4.0:** Attributed in weather API payloads (`Weather data by Open-Meteo.com`).
- **GADM vs OSM Boundaries:** Matrix properly distinguishes that GADM is restricted to non-commercial use, advising OSM administrative boundaries for production.

---

## 7. Defects Fixed During Audit

1. **USER_AGENT Non-ASCII Encoding Crash (`backend/ingestion/osm_adapter.py`)**:
   - *Defect:* `USER_AGENT` contained an em-dash `—` (`\u2014`), causing `httpx` to crash on every live HTTP request with `'ascii' codec can't encode character '\u2014'`.
   - *Fix:* Replaced em-dash with an ASCII hyphen `-`.
2. **PostGIS Migration Crash (`migrations/001_initial_schema.sql`)**:
   - *Defect:* Schema defined `location GEOMETRY(Point, 4326)` without enabling PostGIS first, causing PostgreSQL initdb to fail with `ERROR: type "geometry" does not exist`.
   - *Fix:* Added `CREATE EXTENSION IF NOT EXISTS postgis;` and `CREATE EXTENSION IF NOT EXISTS pg_trgm;` at the beginning of the migration.
3. **Database Healthcheck Failure (`docker-compose.yml`)**:
   - *Defect:* Healthcheck ran `pg_isready -U safesphere`, which attempted to connect to non-existent database `safesphere` instead of `safesphere_db`, causing infinite `health: starting` status.
   - *Fix:* Updated check command to `pg_isready -U ${POSTGRES_USER:-safesphere} -d ${POSTGRES_DB:-safesphere_db}`.
4. **Invalid Celery Beat Scheduler (`docker-compose.yml`)**:
   - *Defect:* Celery beat command specified `--scheduler django_celery_beat.schedulers:DatabaseScheduler`, which would crash the container due to missing Django dependencies.
   - *Fix:* Replaced with standard Celery beat command `celery -A ingestion.tasks beat --loglevel=info`.

---

## 8. Remaining Blockers

1. **Host Port 8000 Collision:**
   - Another Docker container (`confidence_guardian_api`) on the host machine is currently bound to port 8000. To launch the SafeSphere API container via Docker Compose, port 8000 in `docker-compose.yml` must be mapped to an alternative host port (e.g. `8001:8000`) or the conflicting container must be stopped.
2. **Database Glue in Ingestion Pipeline:**
   - `backend/ingestion/tasks.py` lacks SQLAlchemy asynchronous ORM models and a persistence repository (`FacilityRepository`). Parsed facilities currently exist in memory only during batch runs.
3. **Database Querying in Facilities API:**
   - `GET /api/v1/facilities/nearby` currently returns a stub response (`facilities: []`). Connecting this endpoint to PostgreSQL with `ST_DWithin` is required for live map reads.

---

## 9. Go / No-Go Recommendation

### Verdict: **CONDITIONAL GO (Ready for Phase 1 Ingestion Wiring)**

### Justification:
- **Foundations are solid:** Research is authentic, licensing boundaries are properly documented, PostGIS DDL is validated and running in Docker, and the OSM parsing adapter passed 49/49 unit tests and successfully retrieved live records from Sonipat.
- **Immediate Next Steps for Phase 1:**
  1. Map SafeSphere API host port in `docker-compose.yml` to 8001 to resolve host port 8000 collision.
  2. Implement SQLAlchemy models and repository to wire `osm_adapter.py` results into `emergency_facilities`.
  3. Wire `GET /api/v1/facilities/nearby` to execute `ST_DWithin` spatial queries against persisted PostGIS rows.
  4. Register alias route `/api/v1/data-sources` to point to `/api/v1/sources`.
