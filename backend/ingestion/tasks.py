"""
SafeSphere AI — Celery Background Tasks
Ingestion pipeline for all external data sources.

Schedule: see CELERYBEAT_SCHEDULE at bottom.
Broker: Redis (REDIS_URL env var)
"""

from __future__ import annotations

import asyncio
import logging
import os

from celery import Celery
from celery.schedules import crontab

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Celery App
# ---------------------------------------------------------------------------

app = Celery(
    "safesphere",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)

app.config_from_object({
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "Asia/Kolkata",
    "enable_utc": True,
    "task_track_started": True,
    "task_acks_late": True,
    "worker_prefetch_multiplier": 1,
})

# ---------------------------------------------------------------------------
# Helper: run async adapter inside Celery (sync) task
# ---------------------------------------------------------------------------

def run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Task: OSM Facility Ingestion (Nightly)
# ---------------------------------------------------------------------------

@app.task(
    name="ingestion.tasks.ingest_osm_facilities",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    soft_time_limit=600,
    time_limit=720,
)
def ingest_osm_facilities(self, regions=None):
    """
    Nightly ingestion of police stations, fire stations, hospitals,
    clinics, and pharmacies from OpenStreetMap via Overpass API.

    Regions: ["delhi", "sonipat"] (default both)
    Source: ODbL 1.0 — attribution required
    Data: community-maintained, NOT officially verified
    """
    from ingestion.osm_adapter import OSMFacilityAdapter, REGIONS
    from app.db.session import async_session_factory
    from app.db.repository import FacilityRepository

    async def _persist_facilities(facs):
        async with async_session_factory() as session:
            return await FacilityRepository.upsert_batch(session, facs)

    target_regions = regions or list(REGIONS.keys())
    logger.info("Starting OSM facility ingestion for regions: %s", target_regions)

    adapter = OSMFacilityAdapter(regions={r: REGIONS[r] for r in target_regions if r in REGIONS})

    try:
        results = run_async(adapter.ingest_all())
    except Exception as exc:
        logger.error("OSM ingestion failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc)

    summary = {}
    for region, (facilities, result) in results.items():
        # Deduplicate
        facilities = adapter.deduplicate(facilities)

        # Upsert facilities to PostgreSQL/PostGIS
        try:
            db_result = run_async(_persist_facilities(facilities))
            persisted_count = db_result.persisted
            db_skipped = db_result.skipped
            db_errors = len(db_result.errors)
        except Exception as db_exc:
            logger.error("Database persistence failed for region %s: %s", region, db_exc)
            persisted_count = 0
            db_skipped = 0
            db_errors = 1

        summary[region] = {
            "fetched": result.fetched_count,
            "valid": result.valid_count,
            "persisted": persisted_count,
            "skipped": result.skipped_count + db_skipped,
            "errors": result.error_count + db_errors,
            "raw_data_hash": result.raw_data_hash,
        }
        logger.info(
            "Region %s ingestion complete: %d valid facilities",
            region,
            result.valid_count,
        )

    logger.info("OSM ingestion complete. Summary: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# Task: Weather Refresh (Hourly)
# ---------------------------------------------------------------------------

@app.task(
    name="ingestion.tasks.refresh_weather",
    soft_time_limit=60,
    time_limit=90,
)
def refresh_weather():
    """
    Refresh weather data from Open-Meteo for Delhi and Sonipat centroids.
    Stores to Redis cache for fast API response.
    Attribution: Weather data by Open-Meteo.com (CC BY 4.0)
    """
    import httpx

    OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"
    locations = {
        "delhi":   {"lat": 28.6139, "lon": 77.2090},
        "sonipat": {"lat": 28.9931, "lon": 77.0151},
    }
    params_template = {
        "hourly": "temperature_2m,rain,wind_speed_10m,uv_index,weather_code",
        "current": "temperature_2m,rain,wind_speed_10m,weather_code",
        "forecast_days": 2,
        "timezone": "Asia/Kolkata",
    }

    results = {}
    for city, coords in locations.items():
        try:
            params = {**params_template, "latitude": coords["lat"], "longitude": coords["lon"]}
            resp = httpx.get(OPEN_METEO_BASE, params=params, timeout=15)
            resp.raise_for_status()
            results[city] = "ok"
            # TODO: Store in Redis: redis_client.setex(f"weather:{city}", 3600, resp.text)
        except Exception as exc:
            logger.error("Weather refresh failed for %s: %s", city, exc)
            results[city] = f"error: {exc}"

    return results


# ---------------------------------------------------------------------------
# Task: IMD Alert Refresh (Every 30 minutes)
# ---------------------------------------------------------------------------

@app.task(
    name="ingestion.tasks.refresh_imd_alerts",
    soft_time_limit=60,
    time_limit=90,
)
def refresh_imd_alerts():
    """
    Refresh IMD district weather warnings for Delhi and Sonipat.
    Requires IMD_API_KEY to be set. Skips gracefully if not configured.
    Source: India Meteorological Department (authoritative)
    """
    imd_key = os.getenv("IMD_API_KEY")
    if not imd_key:
        logger.warning(
            "IMD_API_KEY not set. Skipping IMD alert refresh. "
            "Register at https://api.imd.gov.in to obtain a key."
        )
        return {"status": "skipped", "reason": "IMD_API_KEY not configured"}

    # TODO: Implement once IMD API endpoint is verified post-registration
    # GET https://api.imd.gov.in/api/v1/districtforecast?state=Delhi
    # GET https://api.imd.gov.in/api/v1/districtforecast?state=Haryana&district=Sonipat
    # Headers: X-API-KEY: {imd_key}
    logger.info("IMD alert refresh: placeholder — implement after API key registration")
    return {"status": "placeholder"}


# ---------------------------------------------------------------------------
# Task: GTFS Static Refresh (Weekly)
# ---------------------------------------------------------------------------

@app.task(
    name="ingestion.tasks.refresh_gtfs_static",
    soft_time_limit=300,
    time_limit=400,
)
def refresh_gtfs_static():
    """
    Download and process DTC bus + DMRC metro GTFS static feeds from OTD Delhi.
    Source: otd.delhi.gov.in — Open Government Data
    Note: Haryana/Sonipat GTFS feed does not exist as of 2026-10-25.
    """
    # TODO: Implement GTFS download and import to PostgreSQL
    # import gtfs_kit
    # feed_dtc = gtfs_kit.read(OTD_DTC_GTFS_URL)
    # feed_dmrc = gtfs_kit.read(OTD_DMRC_GTFS_URL)
    logger.info("GTFS refresh: placeholder — implement with otd.delhi.gov.in download URL")
    return {"status": "placeholder"}


# ---------------------------------------------------------------------------
# Task: Risk Score Recompute (Nightly at 3 AM IST)
# ---------------------------------------------------------------------------

@app.task(
    name="ingestion.tasks.recompute_risk_scores",
    soft_time_limit=300,
    time_limit=400,
)
def recompute_risk_scores():
    """
    Recompute road segment safety scores using the transparent density model.

    Formula:
      score = 1 - normalized_weighted_incident_density
      weight = severity_weight × verification_factor × recency_decay(λ=0.05)
      NULL score if incident_count < 3 (insufficient evidence)

    See docs/privacy_and_data_governance.md for risk model governance rules.
    IMPORTANT: This model is DESCRIPTIVE, not predictive. Green ≠ safe.
    """
    # TODO: Execute PostGIS-based recompute query
    logger.info("Risk score recompute: placeholder — implement with PostGIS query")
    return {"status": "placeholder"}


# ---------------------------------------------------------------------------
# Task: Expire Old Incidents (Nightly at 4 AM IST)
# ---------------------------------------------------------------------------

@app.task(
    name="ingestion.tasks.expire_old_incidents",
    soft_time_limit=120,
    time_limit=180,
)
def expire_old_incidents():
    """
    Mark unverified incident reports as expired after 90 days.
    Delete expired incidents that have passed their expires_at timestamp.
    Retention policy: see docs/privacy_and_data_governance.md.
    """
    # TODO: Execute DELETE/UPDATE on incident_reports WHERE expires_at < NOW()
    logger.info("Incident expiry: placeholder — implement with SQLAlchemy")
    return {"status": "placeholder"}


# ---------------------------------------------------------------------------
# Celery Beat Schedule
# ---------------------------------------------------------------------------

app.conf.beat_schedule = {
    "osm-nightly-ingestion": {
        "task": "ingestion.tasks.ingest_osm_facilities",
        "schedule": crontab(hour=0, minute=30),          # 12:30 AM IST
        "kwargs": {"regions": ["delhi", "sonipat"]},
    },
    "weather-refresh-hourly": {
        "task": "ingestion.tasks.refresh_weather",
        "schedule": crontab(minute=0),                   # Every hour
    },
    "imd-alerts-refresh": {
        "task": "ingestion.tasks.refresh_imd_alerts",
        "schedule": crontab(minute="*/30"),              # Every 30 minutes
    },
    "gtfs-static-weekly": {
        "task": "ingestion.tasks.refresh_gtfs_static",
        "schedule": crontab(day_of_week="monday", hour=2, minute=0),
    },
    "risk-score-recompute": {
        "task": "ingestion.tasks.recompute_risk_scores",
        "schedule": crontab(hour=3, minute=0),           # 3 AM IST
    },
    "expired-incident-cleanup": {
        "task": "ingestion.tasks.expire_old_incidents",
        "schedule": crontab(hour=4, minute=0),           # 4 AM IST
    },
}
