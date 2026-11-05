# SafeSphere AI — Data Dictionary
**Scope:** Delhi (NCT) + Sonipat (Haryana) Pilot
**Last Updated:** 2026-10-25

---

## Table: `emergency_facilities`
Stores all police stations, fire stations, hospitals, and emergency facilities.

| Column | Type | Nullable | Description | Provenance |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | Primary key | Generated |
| `source_id` | VARCHAR(50) | NOT NULL | FK → `data_source_registry.source_id` | Ingestion pipeline |
| `external_id` | VARCHAR(200) | NULL | ID from original source (e.g. OSM node ID, NHFR code) | Source system |
| `facility_type` | ENUM | NOT NULL | `police_station`, `fire_station`, `hospital`, `clinic`, `pharmacy`, `ambulance_post` | Derived from source tags |
| `name` | VARCHAR(500) | NOT NULL | Primary facility name | Source |
| `name_hi` | VARCHAR(500) | NULL | Hindi name (from OSM `name:hi` or official record) | Source |
| `address_raw` | TEXT | NULL | Full address as provided by source | Source |
| `addr_street` | VARCHAR(300) | NULL | Street name | Source |
| `addr_city` | VARCHAR(100) | NULL | City | Source |
| `addr_district` | VARCHAR(100) | NULL | District (e.g., "North Delhi", "Sonipat") | Source or derived |
| `addr_state` | VARCHAR(100) | NULL | State ("Delhi", "Haryana") | Source or derived |
| `addr_postcode` | CHAR(6) | NULL | 6-digit PIN code | Source |
| `location` | GEOMETRY(Point, 4326) | NOT NULL | WGS84 lat/lon — PostGIS geometry | Source or geocoded |
| `latitude` | DOUBLE PRECISION | NOT NULL | Latitude (decimal degrees) | Derived from location |
| `longitude` | DOUBLE PRECISION | NOT NULL | Longitude (decimal degrees) | Derived from location |
| `phone` | VARCHAR(50) | NULL | Primary phone number (publicly listed only) | Source |
| `phone_secondary` | VARCHAR(50) | NULL | Secondary contact | Source |
| `website` | VARCHAR(500) | NULL | Official website URL | Source |
| `opening_hours_raw` | VARCHAR(300) | NULL | OSM opening_hours string or free text | Source |
| `is_24h` | BOOLEAN | NULL | True if confirmed 24/7 operation | Derived |
| `beds` | INTEGER | NULL | Bed count (hospitals only) | NHFR / data.gov.in |
| `services` | TEXT[] | NULL | Service categories (e.g., ["emergency","maternity","ICU"]) | NHFR |
| `jurisdiction_area` | GEOMETRY(Polygon, 4326) | NULL | Official jurisdiction boundary if known | Official source |
| `official_id` | VARCHAR(100) | NULL | Government-assigned facility code (NHFR HFR_ID, Delhi Police PS code) | Official source |
| `district_admin` | VARCHAR(100) | NULL | Administrative district per official records | Administrative boundary join |
| `source_verified` | BOOLEAN | NOT NULL DEFAULT FALSE | True only if confirmed by official government source | Verification workflow |
| `verification_notes` | TEXT | NULL | Human notes on verification | Manual review |
| `osm_id` | BIGINT | NULL | OpenStreetMap element ID | OSM |
| `osm_type` | ENUM('node','way','relation') | NULL | OSM element type | OSM |
| `data_quality_score` | SMALLINT | NULL | 0–100 completeness score (name+loc=40, phone=20, address=20, verified=20) | Computed |
| `created_at` | TIMESTAMPTZ | NOT NULL | Record creation timestamp | System |
| `updated_at` | TIMESTAMPTZ | NOT NULL | Last update timestamp | System |
| `source_fetched_at` | TIMESTAMPTZ | NOT NULL | When data was retrieved from source | Ingestion pipeline |
| `is_active` | BOOLEAN | NOT NULL DEFAULT TRUE | False if facility confirmed closed | Manual / update |

**Indexes:** `location` (GIST), `facility_type`, `addr_district`, `source_id`, `osm_id`
**Limitations:** Phone numbers from OSM are unreliable (<20% coverage, often outdated). Treat as unverified until independently confirmed. `jurisdiction_area` is rarely available from public sources.

---

## Table: `incident_reports`
Community-submitted safety incident reports within SafeSphere AI.

| Column | Type | Nullable | Description | Provenance |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | Primary key | Generated |
| `reporter_hash` | VARCHAR(64) | NOT NULL | SHA-256 of anonymous reporter session token — NOT email/phone | App auth layer |
| `incident_type` | ENUM | NOT NULL | `theft`, `harassment`, `assault`, `road_accident`, `fire`, `flood`, `suspicious_activity`, `eve_teasing`, `drunk_driving`, `unsafe_road`, `other` | User input |
| `incident_subtype` | VARCHAR(100) | NULL | Free-form sub-category | User input |
| `location` | GEOMETRY(Point, 4326) | NOT NULL | Reported incident location | User (map pin or GPS) |
| `location_approximate` | BOOLEAN | NOT NULL DEFAULT TRUE | True if location snapped to nearest road (privacy protection) | System |
| `location_accuracy_m` | REAL | NULL | GPS accuracy radius in metres (if available from device) | User device |
| `reported_at` | TIMESTAMPTZ | NOT NULL | Timestamp of submission | System |
| `incident_at` | TIMESTAMPTZ | NULL | User-reported time of incident | User input |
| `description` | TEXT | NULL | User-provided description (max 1000 chars) | User input |
| `description_sanitized` | TEXT | NULL | After PII scrubbing (phone numbers, names removed) | NLP pipeline |
| `image_refs` | TEXT[] | NULL | Storage references to uploaded images (no raw URLs in this table) | Object storage |
| `verification_status` | ENUM | NOT NULL DEFAULT 'unverified' | `unverified`, `under_review`, `verified`, `duplicate`, `rejected` | Moderation workflow |
| `severity` | ENUM | NULL | `low`, `medium`, `high`, `critical` — assigned by moderator, not user | Moderation |
| `is_emergency` | BOOLEAN | NOT NULL DEFAULT FALSE | True if user flagged as ongoing emergency | User input |
| `escalated_to_112` | BOOLEAN | NOT NULL DEFAULT FALSE | True if user was directed to call 112 | System (emergency flow) |
| `official_complaint_url` | VARCHAR(500) | NULL | Link to official reporting channel shown to user | System |
| `duplicate_of` | UUID | NULL | FK → `incident_reports.id` if this is a duplicate | Deduplication engine |
| `upvote_count` | INTEGER | NOT NULL DEFAULT 0 | Community corroboration count | App users |
| `moderation_notes` | TEXT | NULL | Internal moderator notes (not user-visible) | Moderation team |
| `source` | ENUM | NOT NULL | `app_ios`, `app_android`, `web`, `api` | System |
| `ip_hash` | VARCHAR(64) | NULL | SHA-256 of submitter IP (rate limiting / abuse) | System |
| `created_at` | TIMESTAMPTZ | NOT NULL | DB insertion time | System |
| `expires_at` | TIMESTAMPTZ | NULL | Auto-delete time (default: 90 days for unverified reports) | Retention policy |

**Indexes:** `location` (GIST), `incident_type`, `verification_status`, `reported_at`, `reporter_hash`
**Privacy:** Never store raw IP addresses, emails, or phone numbers in this table. `reporter_hash` and `ip_hash` are one-way hashes used only for rate limiting and abuse detection.
**Important:** A record in this table IS NOT an official police complaint or FIR. Users must be shown a clear disclaimer and directed to official channels (112, cybercrime.gov.in, police station) for formal reporting.

---

## Table: `official_incident_statistics`
Aggregated crime and safety statistics from official government sources (NCRB, data.gov.in).

| Column | Type | Nullable | Description | Provenance |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | Primary key | Generated |
| `source_id` | VARCHAR(50) | NOT NULL | FK → `data_source_registry.source_id` | Ingestion pipeline |
| `stat_year` | SMALLINT | NOT NULL | Reporting year (e.g. 2023) | Source |
| `geographic_level` | ENUM | NOT NULL | `national`, `state`, `district`, `city` | Source |
| `area_name` | VARCHAR(200) | NOT NULL | Name of geographic area (e.g. "Delhi", "Haryana", "Sonipat") | Source |
| `area_code` | VARCHAR(20) | NULL | Census code or LGD code | Source |
| `crime_category` | VARCHAR(200) | NOT NULL | Crime category as per source (IPC section or description) | Source |
| `crime_code` | VARCHAR(20) | NULL | IPC/BNS section code | Source |
| `legal_framework` | ENUM | NOT NULL DEFAULT 'IPC' | `IPC` (pre-2024) or `BNS` (2024 onward) | Source |
| `total_cases` | INTEGER | NULL | Total cases registered | Source |
| `charge_sheeted` | INTEGER | NULL | Cases charge-sheeted | Source |
| `convicted` | INTEGER | NULL | Convictions | Source |
| `victims_total` | INTEGER | NULL | Total victims if reported | Source |
| `victims_female` | INTEGER | NULL | Female victims | Source |
| `victims_children` | INTEGER | NULL | Child victims | Source |
| `raw_data_url` | TEXT | NULL | Direct URL to source table/report | Source |
| `notes` | TEXT | NULL | Methodology notes, caveats | Manual |
| `created_at` | TIMESTAMPTZ | NOT NULL | Ingestion timestamp | System |

**Critical Limitations:**
1. All data here is **aggregate counts** — there are NO geocoded incident locations in this table.
2. Do not attempt to derive precise incident coordinates from these statistics.
3. Values represent **reported** crimes only — unreported incidents are unknown.
4. IPC→BNS transition from 2024 means categories are not directly comparable across years.
5. Suitable for: trend charts, city-level context, category breakdown. NOT suitable for: hotspot maps at street level.

---

## Table: `administrative_boundaries`
Administrative boundary polygons for Delhi and Sonipat.

| Column | Type | Nullable | Description | Provenance |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | Primary key | Generated |
| `source_id` | VARCHAR(50) | NOT NULL | FK → `data_source_registry.source_id` | Ingestion pipeline |
| `admin_level` | SMALLINT | NOT NULL | OSM admin_level (4=state, 5=district, 6=tehsil, 8=city, 9=ward) | OSM / GADM |
| `admin_level_name` | VARCHAR(50) | NULL | Human label: "state", "district", "tehsil", "ward" | Derived |
| `name` | VARCHAR(300) | NOT NULL | Area name | Source |
| `name_hi` | VARCHAR(300) | NULL | Hindi name | Source |
| `osm_relation_id` | BIGINT | NULL | OSM relation ID | OSM |
| `lgd_code` | VARCHAR(20) | NULL | Local Government Directory code | Official |
| `census_code` | VARCHAR(20) | NULL | Census 2011 code | Census data |
| `parent_id` | UUID | NULL | FK → self (parent boundary) | Derived |
| `state` | VARCHAR(100) | NULL | State name | Derived |
| `district` | VARCHAR(100) | NULL | District name | Derived |
| `geometry` | GEOMETRY(MultiPolygon, 4326) | NOT NULL | Boundary polygon(s) | Source |
| `area_sqkm` | DOUBLE PRECISION | NULL | Area in square kilometres | Computed |
| `centroid` | GEOMETRY(Point, 4326) | NULL | Centroid for label placement | Computed |
| `created_at` | TIMESTAMPTZ | NOT NULL | Ingestion timestamp | System |
| `updated_at` | TIMESTAMPTZ | NOT NULL | Last update | System |

**Indexes:** `geometry` (GIST), `admin_level`, `name`, `lgd_code`

---

## Table: `road_network_metadata`
Metadata for road segments with safety-relevant attributes.

| Column | Type | Nullable | Description | Provenance |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | Primary key | Generated |
| `osm_way_id` | BIGINT | NOT NULL | OSM way ID | OSM |
| `name` | VARCHAR(500) | NULL | Road name | OSM |
| `highway` | VARCHAR(50) | NOT NULL | OSM highway tag (motorway, primary, secondary, residential, footway, path…) | OSM |
| `surface` | VARCHAR(50) | NULL | Surface type (asphalt, concrete, unpaved, gravel…) | OSM |
| `lanes` | SMALLINT | NULL | Number of lanes | OSM |
| `maxspeed` | SMALLINT | NULL | Speed limit (km/h) | OSM |
| `lit` | ENUM | NULL | `yes`, `no`, `24/7`, `automatic`, `unknown` | OSM tag |
| `sidewalk` | ENUM | NULL | `both`, `left`, `right`, `no`, `unknown` | OSM tag |
| `oneway` | BOOLEAN | NULL | True if one-way | OSM |
| `access` | VARCHAR(50) | NULL | Access restriction | OSM |
| `geometry` | GEOMETRY(LineString, 4326) | NOT NULL | Road geometry | OSM |
| `length_m` | DOUBLE PRECISION | NULL | Length in metres | Computed |
| `district` | VARCHAR(100) | NULL | Administrative district | Spatial join |
| `incident_count_30d` | INTEGER | NOT NULL DEFAULT 0 | Community reports on/near this segment (rolling 30 days) | Computed nightly |
| `incident_count_90d` | INTEGER | NOT NULL DEFAULT 0 | Community reports (rolling 90 days) | Computed nightly |
| `safety_score` | REAL | NULL | Computed safety indicator 0–1 (see risk_model doc) | Risk model |
| `safety_score_updated_at` | TIMESTAMPTZ | NULL | When safety score was last computed | Risk model |
| `source_fetched_at` | TIMESTAMPTZ | NOT NULL | OSM data retrieval time | Ingestion |
| `created_at` | TIMESTAMPTZ | NOT NULL | Record creation | System |

**Indexes:** `geometry` (GIST), `highway`, `lit`, `district`
**Note:** `safety_score` is a descriptive estimate based on available evidence, NOT a predictive safety guarantee. Sparse data areas carry high uncertainty. See `docs/privacy_and_data_governance.md` for risk model constraints.

---

## Table: `data_source_registry`
Master registry of all data sources used by SafeSphere AI.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `source_id` | VARCHAR(50) | NOT NULL PK | Short identifier (e.g. `osm_overpass`, `ncrb_crime_in_india`) |
| `provider` | VARCHAR(200) | NOT NULL | Organization providing data |
| `dataset_name` | VARCHAR(300) | NOT NULL | Full dataset name |
| `official_url` | TEXT | NOT NULL | Official source landing page URL |
| `documentation_url` | TEXT | NULL | API documentation or data guide URL |
| `access_type` | ENUM | NOT NULL | `public`, `api_key_free`, `api_key_paid`, `registration`, `application`, `partnership`, `restricted` |
| `licence` | VARCHAR(200) | NOT NULL | Licence name (ODbL, GODL, CC-BY-4.0, etc.) |
| `licence_url` | TEXT | NULL | Licence text URL |
| `geographic_coverage` | ENUM | NOT NULL | `national`, `state`, `district`, `city` |
| `states_covered` | TEXT[] | NULL | States covered (e.g. `["Delhi","Haryana"]`) |
| `update_frequency` | VARCHAR(100) | NULL | e.g. "Nightly", "Annual", "Real-time", "Continuous" |
| `data_format` | TEXT[] | NULL | e.g. `["CSV","JSON","GeoJSON"]` |
| `has_coordinates` | BOOLEAN | NULL | True if dataset includes lat/lon |
| `last_verified_at` | TIMESTAMPTZ | NULL | When this entry was last manually verified |
| `verification_status` | CHAR(1) | NOT NULL | A/B/C/D/E/F (see data_source_audit.md) |
| `api_base_url` | TEXT | NULL | API endpoint base |
| `requires_api_key` | BOOLEAN | NOT NULL DEFAULT FALSE | Whether API key is required |
| `env_key_name` | VARCHAR(100) | NULL | Environment variable holding the key (e.g. `DATA_GOV_IN_API_KEY`) |
| `rate_limit_notes` | TEXT | NULL | Rate limit description |
| `commercial_use_permitted` | BOOLEAN | NULL | TRUE/FALSE/NULL (unknown) |
| `attribution_required` | TEXT | NULL | Attribution string required |
| `limitations` | TEXT | NULL | Known limitations and caveats |
| `ingestion_adapter` | VARCHAR(100) | NULL | Name of Python adapter class |
| `created_at` | TIMESTAMPTZ | NOT NULL | Record creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL | Last update |

---

## Table: `incident_verification_events`
Audit trail of verification actions on incident reports.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | UUID | NOT NULL PK | Primary key |
| `incident_id` | UUID | NOT NULL | FK → `incident_reports.id` |
| `event_type` | ENUM | NOT NULL | `submitted`, `flagged`, `moderation_started`, `verified`, `rejected`, `duplicate_detected`, `escalated`, `auto_expired` |
| `performed_by` | VARCHAR(100) | NULL | Moderator ID or `system` |
| `previous_status` | VARCHAR(50) | NULL | Status before event |
| `new_status` | VARCHAR(50) | NULL | Status after event |
| `notes` | TEXT | NULL | Reason or notes |
| `created_at` | TIMESTAMPTZ | NOT NULL | Event timestamp |

---

## Table: `user_alert_subscriptions`
Geofenced alert subscriptions for SafeSphere users.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | UUID | NOT NULL PK | Primary key |
| `user_hash` | VARCHAR(64) | NOT NULL | Hashed user identifier (no PII) |
| `alert_name` | VARCHAR(200) | NULL | User-defined label (e.g. "Home area", "Work route") |
| `geofence` | GEOMETRY(Polygon, 4326) | NOT NULL | Alert zone polygon |
| `radius_m` | INTEGER | NULL | Radius in metres (if circle-based) |
| `incident_types` | TEXT[] | NOT NULL | Incident types to alert on |
| `min_severity` | ENUM | NULL | Minimum severity to notify |
| `notify_weather` | BOOLEAN | NOT NULL DEFAULT FALSE | Receive weather alerts for zone |
| `notify_channel` | ENUM | NOT NULL | `push`, `in_app` |
| `is_active` | BOOLEAN | NOT NULL DEFAULT TRUE | Whether subscription is active |
| `created_at` | TIMESTAMPTZ | NOT NULL | Creation time |
| `updated_at` | TIMESTAMPTZ | NOT NULL | Last update |
| `expires_at` | TIMESTAMPTZ | NULL | Optional expiry |

**Privacy:** No raw device identifiers stored. `user_hash` is a one-way hash. Push tokens stored separately in an encrypted token store, never in this table.

---

## Table: `authorized_emergency_integrations`
Registry of formally authorized emergency data integrations (PCR feeds, ERSS, etc.).

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | UUID | NOT NULL PK | Primary key |
| `integration_name` | VARCHAR(200) | NOT NULL | e.g. "Delhi Police PCR Live Feed" |
| `provider` | VARCHAR(200) | NOT NULL | Authorizing agency |
| `authorization_ref` | VARCHAR(200) | NULL | MoU or agreement reference number |
| `authorized_at` | DATE | NULL | Date of authorization |
| `expires_at` | DATE | NULL | Authorization expiry date |
| `endpoint_url` | TEXT | NULL | Encrypted API endpoint (stored encrypted) |
| `auth_method` | ENUM | NULL | `api_key`, `oauth2`, `mtls`, `ip_whitelist` |
| `data_scope` | TEXT | NULL | What data is accessible under this authorization |
| `is_live` | BOOLEAN | NOT NULL DEFAULT FALSE | FALSE until formal authorization received |
| `is_simulated` | BOOLEAN | NOT NULL DEFAULT TRUE | TRUE means demo/simulated data — MUST be displayed with SIMULATED label |
| `simulation_disclaimer` | TEXT | NULL | Disclaimer text to display when simulated |
| `notes` | TEXT | NULL | Internal notes |
| `created_at` | TIMESTAMPTZ | NOT NULL | Record creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL | Last update |

> **Rule:** If `is_simulated = TRUE`, the UI MUST display a prominent "⚠️ SIMULATED DATA — NOT LIVE" label on any feature using this integration. This must never be suppressed or hidden.

---

## Enumerated Types

```sql
CREATE TYPE facility_type AS ENUM (
    'police_station', 'fire_station', 'hospital', 'clinic',
    'pharmacy', 'ambulance_post', 'pcr_base', 'emergency_shelter'
);

CREATE TYPE incident_type AS ENUM (
    'theft', 'harassment', 'assault', 'road_accident', 'fire',
    'flood', 'suspicious_activity', 'eve_teasing', 'drunk_driving',
    'unsafe_road', 'power_outage', 'other'
);

CREATE TYPE verification_status AS ENUM (
    'unverified', 'under_review', 'verified', 'duplicate', 'rejected'
);

CREATE TYPE access_type AS ENUM (
    'public', 'api_key_free', 'api_key_paid', 'registration',
    'application', 'partnership', 'restricted'
);

CREATE TYPE geographic_level AS ENUM (
    'national', 'state', 'district', 'city', 'ward'
);

CREATE TYPE osm_element_type AS ENUM ('node', 'way', 'relation');
CREATE TYPE legal_framework AS ENUM ('IPC', 'BNS');
CREATE TYPE lit_status AS ENUM ('yes', 'no', '24/7', 'automatic', 'unknown');
CREATE TYPE sidewalk_status AS ENUM ('both', 'left', 'right', 'no', 'unknown');
CREATE TYPE severity_level AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE notify_channel AS ENUM ('push', 'in_app');
CREATE TYPE auth_method AS ENUM ('api_key', 'oauth2', 'mtls', 'ip_whitelist');
CREATE TYPE integration_status AS ENUM ('pending', 'active', 'suspended', 'revoked');
CREATE TYPE verification_event_type AS ENUM (
    'submitted', 'flagged', 'moderation_started', 'verified',
    'rejected', 'duplicate_detected', 'escalated', 'auto_expired'
);
CREATE TYPE incident_source AS ENUM ('app_ios', 'app_android', 'web', 'api');
```
