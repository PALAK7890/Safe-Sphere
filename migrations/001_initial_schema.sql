CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

BEGIN;

-- ======================================================
-- ENUM TYPES
-- ======================================================

CREATE TYPE facility_type AS ENUM (
    'police_station', 'fire_station', 'hospital', 'clinic',
    'pharmacy', 'ambulance_post', 'pcr_base', 'emergency_shelter'
);

CREATE TYPE incident_type_enum AS ENUM (
    'theft', 'harassment', 'assault', 'road_accident', 'fire',
    'flood', 'suspicious_activity', 'eve_teasing', 'drunk_driving',
    'unsafe_road', 'power_outage', 'other'
);

CREATE TYPE verification_status_enum AS ENUM (
    'unverified', 'under_review', 'verified', 'duplicate', 'rejected'
);

CREATE TYPE access_type_enum AS ENUM (
    'public', 'api_key_free', 'api_key_paid', 'registration',
    'application', 'partnership', 'restricted'
);

CREATE TYPE geographic_level_enum AS ENUM (
    'national', 'state', 'district', 'city', 'ward'
);

CREATE TYPE osm_element_type AS ENUM ('node', 'way', 'relation');
CREATE TYPE legal_framework_enum AS ENUM ('IPC', 'BNS');
CREATE TYPE lit_status_enum AS ENUM ('yes', 'no', '24/7', 'automatic', 'unknown');
CREATE TYPE sidewalk_status_enum AS ENUM ('both', 'left', 'right', 'no', 'unknown');
CREATE TYPE severity_level_enum AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE notify_channel_enum AS ENUM ('push', 'in_app');
CREATE TYPE verification_event_type_enum AS ENUM (
    'submitted', 'flagged', 'moderation_started', 'verified',
    'rejected', 'duplicate_detected', 'escalated', 'auto_expired'
);
CREATE TYPE incident_source_enum AS ENUM ('app_ios', 'app_android', 'web', 'api');


-- ======================================================
-- TABLE: data_source_registry
-- ======================================================

CREATE TABLE data_source_registry (
    source_id               VARCHAR(50)         PRIMARY KEY,
    provider                VARCHAR(200)        NOT NULL,
    dataset_name            VARCHAR(300)        NOT NULL,
    official_url            TEXT                NOT NULL,
    documentation_url       TEXT,
    access_type             access_type_enum    NOT NULL,
    licence                 VARCHAR(200)        NOT NULL,
    licence_url             TEXT,
    geographic_coverage     geographic_level_enum NOT NULL,
    states_covered          TEXT[],
    update_frequency        VARCHAR(100),
    data_format             TEXT[],
    has_coordinates         BOOLEAN,
    last_verified_at        TIMESTAMPTZ,
    last_fetched_at         TIMESTAMPTZ,
    verification_status     CHAR(1)             NOT NULL CHECK (verification_status IN ('A','B','C','D','E','F')),
    api_base_url            TEXT,
    requires_api_key        BOOLEAN             NOT NULL DEFAULT FALSE,
    env_key_name            VARCHAR(100),
    rate_limit_notes        TEXT,
    commercial_use_permitted BOOLEAN,
    attribution_required    TEXT,
    limitations             TEXT,
    ingestion_adapter       VARCHAR(100),
    created_at              TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE data_source_registry IS
    'Master registry of all external data sources with provenance and access metadata.';


-- ======================================================
-- TABLE: emergency_facilities
-- ======================================================

CREATE TABLE emergency_facilities (
    id                      UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id               VARCHAR(50)         NOT NULL REFERENCES data_source_registry(source_id),
    external_id             VARCHAR(200),
    facility_type           facility_type       NOT NULL,
    name                    VARCHAR(500)        NOT NULL,
    name_hi                 VARCHAR(500),
    address_raw             TEXT,
    addr_street             VARCHAR(300),
    addr_city               VARCHAR(100),
    addr_district           VARCHAR(100),
    addr_state              VARCHAR(100),
    addr_postcode           CHAR(6),
    location                GEOMETRY(Point, 4326) NOT NULL,
    latitude                DOUBLE PRECISION    NOT NULL GENERATED ALWAYS AS (ST_Y(location)) STORED,
    longitude               DOUBLE PRECISION    NOT NULL GENERATED ALWAYS AS (ST_X(location)) STORED,
    phone                   VARCHAR(50),
    phone_secondary         VARCHAR(50),
    website                 VARCHAR(500),
    opening_hours_raw       VARCHAR(300),
    is_24h                  BOOLEAN,
    beds                    INTEGER,
    services                TEXT[],
    jurisdiction_area       GEOMETRY(Polygon, 4326),
    official_id             VARCHAR(100),
    district_admin          VARCHAR(100),
    source_verified         BOOLEAN             NOT NULL DEFAULT FALSE,
    verification_notes      TEXT,
    osm_id                  BIGINT,
    osm_type                osm_element_type,
    data_quality_score      SMALLINT            CHECK (data_quality_score BETWEEN 0 AND 100),
    created_at              TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    source_fetched_at       TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    is_active               BOOLEAN             NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_osm_id_type UNIQUE (osm_id, osm_type)
);

CREATE INDEX idx_facilities_location         ON emergency_facilities USING GIST (location);
CREATE INDEX idx_facilities_location_geog    ON emergency_facilities USING GIST (CAST(location AS geography));
CREATE INDEX idx_facilities_type        ON emergency_facilities (facility_type);
CREATE INDEX idx_facilities_district    ON emergency_facilities (addr_district);
CREATE INDEX idx_facilities_source      ON emergency_facilities (source_id);
CREATE INDEX idx_facilities_osm         ON emergency_facilities (osm_id);
CREATE INDEX idx_facilities_active      ON emergency_facilities (is_active);

COMMENT ON COLUMN emergency_facilities.source_verified IS
    'FALSE for OSM data (community-maintained). TRUE only when confirmed by official government source.';
COMMENT ON COLUMN emergency_facilities.data_quality_score IS
    'Completeness score 0-100: name+coords=40, phone=20, address=20, official_verified=20.';


-- ======================================================
-- TABLE: incident_reports
-- ======================================================

CREATE TABLE incident_reports (
    id                      UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    reporter_hash           VARCHAR(64)         NOT NULL,
    incident_type           incident_type_enum  NOT NULL,
    incident_subtype        VARCHAR(100),
    location                GEOMETRY(Point, 4326) NOT NULL,
    location_approximate    BOOLEAN             NOT NULL DEFAULT TRUE,
    location_accuracy_m     REAL,
    reported_at             TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    incident_at             TIMESTAMPTZ,
    description             TEXT                CHECK (char_length(description) <= 1000),
    description_sanitized   TEXT,
    image_refs              TEXT[],
    verification_status     verification_status_enum NOT NULL DEFAULT 'unverified',
    severity                severity_level_enum,
    is_emergency            BOOLEAN             NOT NULL DEFAULT FALSE,
    escalated_to_112        BOOLEAN             NOT NULL DEFAULT FALSE,
    official_complaint_url  VARCHAR(500),
    duplicate_of            UUID                REFERENCES incident_reports(id),
    upvote_count            INTEGER             NOT NULL DEFAULT 0,
    moderation_notes        TEXT,
    source                  incident_source_enum NOT NULL,
    ip_hash                 VARCHAR(64),
    created_at              TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    expires_at              TIMESTAMPTZ
);

CREATE INDEX idx_incidents_location         ON incident_reports USING GIST (location);
CREATE INDEX idx_incidents_type             ON incident_reports (incident_type);
CREATE INDEX idx_incidents_status           ON incident_reports (verification_status);
CREATE INDEX idx_incidents_reported_at      ON incident_reports (reported_at DESC);
CREATE INDEX idx_incidents_reporter_hash    ON incident_reports (reporter_hash);
CREATE INDEX idx_incidents_expires_at       ON incident_reports (expires_at);

COMMENT ON TABLE incident_reports IS
    'Community-submitted safety incident reports. NOT official police complaints.
     Users must be directed to 112/official channels for formal reporting.';
COMMENT ON COLUMN incident_reports.location IS
    'Location snapped to nearest road ±50m for privacy. Raw GPS never stored.';


-- ======================================================
-- TABLE: official_incident_statistics
-- ======================================================

CREATE TABLE official_incident_statistics (
    id                  UUID                    PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id           VARCHAR(50)             NOT NULL REFERENCES data_source_registry(source_id),
    stat_year           SMALLINT                NOT NULL CHECK (stat_year BETWEEN 2000 AND 2100),
    geographic_level    geographic_level_enum   NOT NULL,
    area_name           VARCHAR(200)            NOT NULL,
    area_code           VARCHAR(20),
    crime_category      VARCHAR(200)            NOT NULL,
    crime_code          VARCHAR(20),
    legal_framework     legal_framework_enum    NOT NULL DEFAULT 'IPC',
    total_cases         INTEGER,
    charge_sheeted      INTEGER,
    convicted           INTEGER,
    victims_total       INTEGER,
    victims_female      INTEGER,
    victims_children    INTEGER,
    raw_data_url        TEXT,
    notes               TEXT,
    created_at          TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_stat UNIQUE (source_id, stat_year, area_name, crime_category, legal_framework)
);

CREATE INDEX idx_stats_year         ON official_incident_statistics (stat_year);
CREATE INDEX idx_stats_area         ON official_incident_statistics (area_name);
CREATE INDEX idx_stats_category     ON official_incident_statistics (crime_category);

COMMENT ON TABLE official_incident_statistics IS
    'Aggregate crime statistics from NCRB, data.gov.in etc.
     IMPORTANT: These are aggregate counts only — NO geocoded incident locations.
     Do NOT attempt to derive precise incident coordinates from this data.';


-- ======================================================
-- TABLE: administrative_boundaries
-- ======================================================

CREATE TABLE administrative_boundaries (
    id                  UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id           VARCHAR(50)         NOT NULL REFERENCES data_source_registry(source_id),
    admin_level         SMALLINT            NOT NULL,
    admin_level_name    VARCHAR(50),
    name                VARCHAR(300)        NOT NULL,
    name_hi             VARCHAR(300),
    osm_relation_id     BIGINT,
    lgd_code            VARCHAR(20),
    census_code         VARCHAR(20),
    parent_id           UUID                REFERENCES administrative_boundaries(id),
    state               VARCHAR(100),
    district            VARCHAR(100),
    geometry            GEOMETRY(MultiPolygon, 4326) NOT NULL,
    area_sqkm           DOUBLE PRECISION,
    centroid            GEOMETRY(Point, 4326),
    created_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_boundaries_geometry    ON administrative_boundaries USING GIST (geometry);
CREATE INDEX idx_boundaries_level       ON administrative_boundaries (admin_level);
CREATE INDEX idx_boundaries_name        ON administrative_boundaries (name);
CREATE INDEX idx_boundaries_lgd         ON administrative_boundaries (lgd_code);


-- ======================================================
-- TABLE: road_network_metadata
-- ======================================================

CREATE TABLE road_network_metadata (
    id                          UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    osm_way_id                  BIGINT              NOT NULL UNIQUE,
    name                        VARCHAR(500),
    highway                     VARCHAR(50)         NOT NULL,
    surface                     VARCHAR(50),
    lanes                       SMALLINT,
    maxspeed                    SMALLINT,
    lit                         lit_status_enum,
    sidewalk                    sidewalk_status_enum,
    oneway                      BOOLEAN,
    access                      VARCHAR(50),
    geometry                    GEOMETRY(LineString, 4326) NOT NULL,
    length_m                    DOUBLE PRECISION,
    district                    VARCHAR(100),
    incident_count_30d          INTEGER             NOT NULL DEFAULT 0,
    incident_count_90d          INTEGER             NOT NULL DEFAULT 0,
    safety_score                REAL                CHECK (safety_score BETWEEN 0 AND 1),
    safety_score_updated_at     TIMESTAMPTZ,
    source_fetched_at           TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_road_geometry      ON road_network_metadata USING GIST (geometry);
CREATE INDEX idx_road_highway       ON road_network_metadata (highway);
CREATE INDEX idx_road_lit           ON road_network_metadata (lit);
CREATE INDEX idx_road_district      ON road_network_metadata (district);
CREATE INDEX idx_road_safety_score  ON road_network_metadata (safety_score);

COMMENT ON COLUMN road_network_metadata.safety_score IS
    'Descriptive safety estimate 0-1 based on incident density and recency.
     NOT a predictive model. Sparse data = NULL, not zero. See privacy_and_data_governance.md.';
COMMENT ON COLUMN road_network_metadata.lit IS
    'OSM lit= tag. Missing value means unknown — NOT confirmed unlit.';


-- ======================================================
-- TABLE: incident_verification_events
-- ======================================================

CREATE TABLE incident_verification_events (
    id              UUID                            PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id     UUID                            NOT NULL REFERENCES incident_reports(id) ON DELETE CASCADE,
    event_type      verification_event_type_enum    NOT NULL,
    performed_by    VARCHAR(100),
    previous_status VARCHAR(50),
    new_status      VARCHAR(50),
    notes           TEXT,
    created_at      TIMESTAMPTZ                     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_verification_incident  ON incident_verification_events (incident_id);
CREATE INDEX idx_verification_created   ON incident_verification_events (created_at DESC);


-- ======================================================
-- TABLE: user_alert_subscriptions
-- ======================================================

CREATE TABLE user_alert_subscriptions (
    id              UUID                    PRIMARY KEY DEFAULT gen_random_uuid(),
    user_hash       VARCHAR(64)             NOT NULL,
    alert_name      VARCHAR(200),
    geofence        GEOMETRY(Polygon, 4326) NOT NULL,
    radius_m        INTEGER,
    incident_types  TEXT[]                  NOT NULL,
    min_severity    severity_level_enum,
    notify_weather  BOOLEAN                 NOT NULL DEFAULT FALSE,
    notify_channel  notify_channel_enum     NOT NULL,
    is_active       BOOLEAN                 NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ
);

CREATE INDEX idx_alert_geofence     ON user_alert_subscriptions USING GIST (geofence);
CREATE INDEX idx_alert_user_hash    ON user_alert_subscriptions (user_hash);
CREATE INDEX idx_alert_active       ON user_alert_subscriptions (is_active);

COMMENT ON TABLE user_alert_subscriptions IS
    'Geofenced alert subscriptions. No PII stored — user_hash is one-way hash.
     Push tokens stored separately in encrypted token store.';


-- ======================================================
-- TABLE: authorized_emergency_integrations
-- ======================================================

CREATE TABLE authorized_emergency_integrations (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    integration_name    VARCHAR(200) NOT NULL,
    provider            VARCHAR(200) NOT NULL,
    authorization_ref   VARCHAR(200),
    authorized_at       DATE,
    expires_at          DATE,
    endpoint_url        TEXT,
    auth_method         VARCHAR(50),
    data_scope          TEXT,
    is_live             BOOLEAN     NOT NULL DEFAULT FALSE,
    is_simulated        BOOLEAN     NOT NULL DEFAULT TRUE,
    simulation_disclaimer TEXT,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE authorized_emergency_integrations IS
    'Registry of formally authorized emergency integrations (PCR, ERSS).
     RULE: is_simulated=TRUE means UI MUST show SIMULATED warning. Cannot be suppressed.
     is_live=FALSE until formal authorization is received.';

-- Seed: default simulated PCR entry
INSERT INTO authorized_emergency_integrations (
    integration_name, provider, is_live, is_simulated,
    simulation_disclaimer, notes
) VALUES (
    'Delhi Police PCR — Simulated (Development Only)',
    'SafeSphere AI Internal (NOT Delhi Police)',
    FALSE,
    TRUE,
    '⚠️ SIMULATED DATA — NOT LIVE. Vehicle positions are randomly generated for development purposes only. Do NOT use for emergency decisions. Call 112 for all emergencies.',
    'Replace with real MoU-authorized feed when Delhi Police formal authorization is received.'
);

COMMIT;
