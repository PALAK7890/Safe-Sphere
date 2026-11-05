# SafeSphere AI — Phase 2: Community Incident Reporting, Validation & Moderation Report

**Date of Execution:** November 2026  
**Auditor / Engineer:** Senior Geospatial Data Engineer & Security Architect  
**Target Repository:** `/Users/PalakNst/Desktop/SafeSphere`  
**Pilot Geographic Focus:** Delhi (NCT) & Sonipat (Haryana)

---

## 1. Executive Summary

Phase 2 implements the complete **Community Incident Reporting, Validation, and Moderation** subsystem for SafeSphere AI. 

The implementation bridges public crowdsourced safety incident observations with rigorous privacy protections (DPDPA 2023 compliance), automated PII scrubbing, prompt-injection defense, multi-stage human moderation, PostGIS spatial queries, and strict legal boundaries ensuring that community submissions are never misrepresented as official police complaints or FIRs.

All 85 automated unit, repository, security, spatial, and API integration tests are passing (100% pass rate).

---

## 2. Deliverables Inventory

| # | Deliverable | Path | Status |
|---|---|---|---|
| 1 | **Database Migration 002** | [`migrations/002_incident_reporting.sql`](../migrations/002_incident_reporting.sql) | ✅ Complete (Moderation columns, region tag, generated lat/lon, geography GiST index) |
| 2 | **SQLAlchemy Incident Models** | [`backend/app/db/models.py`](../backend/app/db/models.py) | ✅ Complete (`IncidentReportORM`, `IncidentVerificationEventORM`) |
| 3 | **Pydantic Schemas** | [`backend/app/models/incident.py`](../backend/app/models/incident.py) | ✅ Complete (Submission, moderation, public queries, disclaimers) |
| 4 | **Privacy & Security Sanitizer** | [`backend/app/services/sanitizer.py`](../backend/app/services/sanitizer.py) | ✅ Complete (PII redaction, prompt injection defense, ~100m coordinate coarsening) |
| 5 | **Incident Repository & Rate Limiting** | [`backend/app/db/incident_repository.py`](../backend/app/db/incident_repository.py) | ✅ Complete (Duplicate detection, sliding-window rate limiter, PostGIS spatial queries) |
| 6 | **Incident API Router** | [`backend/app/api/incidents.py`](../backend/app/api/incidents.py) | ✅ Complete (`POST /incidents`, `GET /incidents`, `GET /incidents/nearby`, moderation queue & actions) |
| 7 | **Automated Test Suite** | [`backend/tests/test_incidents.py`](../backend/tests/test_incidents.py) | ✅ Complete (17 new tests; 85 total across test suite) |
| 8 | **Incident Reporting Policy** | [`docs/incident_reporting_policy.md`](incident_reporting_policy.md) | ✅ Complete (Permitted categories, rules, emergency escalation) |
| 9 | **Moderation & Verification Architecture** | [`docs/moderation_and_verification.md`](moderation_and_verification.md) | ✅ Complete (State machine, reason codes, audit trail) |
| 10 | **Incident Privacy Model** | [`docs/incident_privacy_model.md`](incident_privacy_model.md) | ✅ Complete (DPDPA 2023, location coarsening, salted SHA-256 pseudonymity) |
| 11 | **Phase 2 Completion Report** | [`docs/phase2_incident_reporting_report.md`](phase2_incident_reporting_report.md) | ✅ Complete (This document) |

---

## 3. Detailed Technical Implementation

### 3.1 Data Model & Database Migration
- **Migration:** `migrations/002_incident_reporting.sql` applied to PostgreSQL 16 + PostGIS 3.4 (`safesphere_db`).
- **Extended Fields:**
  - `moderation_status`: `VARCHAR(50) NOT NULL DEFAULT 'pending_review'` (`pending_review`, `approved`, `rejected`, `archived`).
  - `moderation_reason`: Standardized rejection/approval codes.
  - `moderated_at`: Timestamp of decision.
  - `moderated_by`: Identifier of reviewing moderator.
  - `region`: Pilot tag (`delhi`, `sonipat`, or `other`).
  - `latitude` / `longitude`: Stored generated columns derived from `ST_Y(location)` and `ST_X(location)`.
- **Spatial Indexing:** Added GiST index on geography expression:
  ```sql
  CREATE INDEX idx_incidents_location_geog ON incident_reports USING GIST (CAST(location AS geography));
  ```
- **Audit Logging:** Implemented `IncidentVerificationEventORM` mapping `incident_verification_events` table to log all lifecycle transitions (`submitted`, `verified`, `rejected`, `flagged`).

### 3.2 Submission Pipeline (`POST /api/v1/incidents`)
1. **Timestamp & Boundary Validation:**
   - Incident timestamp cannot be in the future (allowing 10m clock drift).
   - Timestamp cannot be older than 365 days.
   - Coordinates verified inside India bounds ($8.0^\circ\text{N}$ to $38.0^\circ\text{N}$, $68.0^\circ\text{E}$ to $98.0^\circ\text{E}$).
2. **Automated Sanitization:**
   - Detects and replaces Indian phone numbers with `[PHONE REDACTED]`.
   - Detects and replaces emails with `[EMAIL REDACTED]`.
   - Detects and replaces Aadhaar / 12-digit IDs with `[ID REDACTED]`.
   - Neutralizes prompt injection instructions with `[FILTERED INSTRUCTION]`.
   - Strips raw HTML and script tags.
3. **Pseudonymization:**
   - Generates one-way `reporter_hash` via `SHA-256(client_ip + user_agent + salt)`. Raw IP is discarded.
4. **Duplicate Detection:**
   - Identifies candidate duplicates submitted within 100 metres and within 60 minutes for the same category, or repeated submissions by the same reporter hash within 15 minutes.
5. **Rate Limiting:**
   - Limits client requests to **5 submissions per 10-minute window**. Exceeding returns `HTTP 429 Too Many Requests`.
6. **Emergency Escalation:**
   - If `is_emergency=True`, returns prominent banner directing user to call **112 immediately**, while saving the report for audit.

### 3.3 Moderation & Review Workflow
- **Protected Endpoints:**
  - `GET /api/v1/incidents/moderation/queue`: Review pending reports with full raw and sanitized text.
  - `POST /api/v1/incidents/{id}/moderate`: Execute `approve`, `reject`, `archive`, or `flag` with reason code.
- **Authorization:** Enforced via `X-Moderator-Key` header or `Authorization: Bearer <key>`. Missing or invalid tokens return `HTTP 401 Unauthorized`.
- **Reason Codes:** Standardized enum values (`pii_detected`, `hate_speech_or_harassment`, `spam_or_commercial`, `abusive_or_defamatory`, `unverifiable_or_vague`, `duplicate`, `prompt_injection`, `out_of_pilot_scope`, `approved_for_public`).

### 3.4 Privacy-Preserving Public Queries
- **`GET /api/v1/incidents` & `GET /api/v1/incidents/nearby`:**
  - **Strict Isolation:** Only returns reports where `moderation_status = 'approved'`.
  - **Location Coarsening:** Coordinates are rounded to 3 decimal places (~100m grid cell) before transmission. Exact GPS coordinates are never exposed.
  - **No PII or Internal Notes:** Reporter hashes, IP hashes, and internal moderation notes are stripped from the response schema.
  - **Uncertainty Disclaimers:** Public payload includes mandatory notice: *"Low incident counts do NOT guarantee safety; data may be sparse, delayed, or unverified."*

---

## 4. Test Verification Results

The entire SafeSphere AI test suite was executed in an isolated environment against the live PostgreSQL/PostGIS database:

```bash
TESTING=true PYTHONPATH=./backend python3.13 -m pytest backend/tests/ -v
```

### Raw Test Execution Summary
```
============================= test session starts ==============================
platform darwin -- Python 3.13.6, pytest-9.1.1, pluggy-1.7.0 -- /usr/local/bin/python3.13
cachedir: .pytest_cache
rootdir: /Users/PalakNst/Desktop/SafeSphere/backend/tests
plugins: asyncio-1.4.1, anyio-4.15.1
asyncio: mode=Mode.STRICT, debug=False

collected 85 items

backend/tests/test_incidents.py .................                             [ 20%]
backend/tests/test_osm_adapter.py ............................................ [ 77%]
...................                                                           
backend/tests/test_persistence.py ...................                         [100%]

======================== 85 passed, 1 warning in 6.22s =========================
```

### Breakdown of Passing Test Suites:
- **`test_incidents.py` (17 tests):**
  - `test_pii_redaction_phone_numbers`: PASSED
  - `test_pii_redaction_email_addresses`: PASSED
  - `test_pii_redaction_aadhaar_numbers`: PASSED
  - `test_prompt_injection_defense`: PASSED
  - `test_html_tag_stripping`: PASSED
  - `test_coarsen_coordinates`: PASSED
  - `test_determine_pilot_regions`: PASSED
  - `test_submit_valid_incident_creates_pending_review`: PASSED
  - `test_submit_emergency_returns_immediate_112_redirect`: PASSED
  - `test_submit_invalid_coordinates_rejected`: PASSED
  - `test_submit_future_timestamp_rejected`: PASSED
  - `test_submit_ancient_timestamp_rejected`: PASSED
  - `test_rate_limiting_enforced`: PASSED
  - `test_moderation_endpoints_require_authorization`: PASSED
  - `test_full_moderation_lifecycle_approve_and_reject`: PASSED
  - `test_nearby_query_radius_and_filtering`: PASSED
  - `test_sql_injection_resilience`: PASSED
- **`test_osm_adapter.py` (49 tests):** All 49 Overpass ingestion and normalization tests PASSED.
- **`test_persistence.py` (19 tests):** All 19 PostGIS facility persistence and spatial tests PASSED.

---

## 5. Demonstration of Phase 2 Completion Criteria

| # | Completion Criterion | Demonstrated Evidence |
|---|---|---|
| **1** | **Submit community report** | `POST /api/v1/incidents` returns `HTTP 201 Created` with unique report UUID. |
| **2** | **Confirm report is pending review** | Response confirms `moderation_status: "pending_review"`. |
| **3** | **Confirm absent from public queries** | `GET /api/v1/incidents` and `GET /api/v1/incidents/nearby` exclude pending reports. |
| **4** | **Approve report through authorized moderation** | `POST /api/v1/incidents/{id}/moderate` with `X-Moderator-Key` approves report; logs audit event. |
| **5** | **Confirm approved report appears publicly** | Report appears in `GET /api/v1/incidents` with coarsened location (~100m) and uncertainty disclaimers. |
| **6** | **Confirm rejected report remains excluded** | Rejected reports are strictly filtered out from all public queries. |
| **7** | **Verify no false FIR / police claims** | Disclaimers prominently state: *"NOT an official police complaint or FIR. For emergencies, call 112."* |
| **8** | **Regression test suite passes** | All 85 unit and integration tests passing. |

---

## 6. Conclusion & Next Phase Readiness

Phase 2 is fully complete. The community incident reporting and moderation layer is robust, secure, and respectful of user privacy under the DPDPA 2023. The platform is ready for **Phase 3: Road Network Ingestion, Walking Profile Graph & Safe Routing**.
