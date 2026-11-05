-- SafeSphere AI — Migration 002: Incident Reporting, Validation & Moderation
-- Extends incident_reports with moderation tracking, region tags, and spatial geography indexes.

BEGIN;

-- 1. Moderation and pilot region columns
ALTER TABLE incident_reports
    ADD COLUMN IF NOT EXISTS moderation_status VARCHAR(50) NOT NULL DEFAULT 'pending_review',
    ADD COLUMN IF NOT EXISTS moderation_reason VARCHAR(100),
    ADD COLUMN IF NOT EXISTS moderated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS moderated_by VARCHAR(100),
    ADD COLUMN IF NOT EXISTS region VARCHAR(50);

-- 2. Stored generated coordinates derived from location geometry
ALTER TABLE incident_reports
    ADD COLUMN IF NOT EXISTS latitude FLOAT GENERATED ALWAYS AS (ST_Y(location)) STORED,
    ADD COLUMN IF NOT EXISTS longitude FLOAT GENERATED ALWAYS AS (ST_X(location)) STORED;

-- 3. Geography index for fast meter-based ST_DWithin spatial queries
CREATE INDEX IF NOT EXISTS idx_incidents_location_geog
    ON incident_reports USING GIST (CAST(location AS geography));

-- 4. Filter indexes for moderation status and region
CREATE INDEX IF NOT EXISTS idx_incidents_moderation_status
    ON incident_reports (moderation_status);

CREATE INDEX IF NOT EXISTS idx_incidents_region
    ON incident_reports (region);

-- 5. Comments on table and columns
COMMENT ON COLUMN incident_reports.moderation_status IS
    'Moderation workflow status: pending_review, approved, rejected, archived. Only approved reports are queryable publicly.';
COMMENT ON COLUMN incident_reports.verification_status IS
    'Factual verification status: unverified, under_review, verified, duplicate, rejected. Independent of moderation approval.';
COMMENT ON COLUMN incident_reports.region IS
    'Geographic pilot region tag: delhi, sonipat, or other.';

COMMIT;
