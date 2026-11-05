# SafeSphere AI — Data Architecture
**Scope:** Delhi (NCT) + Sonipat (Haryana) Pilot
**Last Updated:** 2026-10-25

---

## 1. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND LAYER                           │
│   React + TypeScript + MapLibre GL JS                           │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│   │ Map View │  │ Alerts   │  │ Report   │  │ AI Assistant │  │
│   │ (Layers) │  │ Panel    │  │ Incident │  │ (RAG Agent)  │  │
│   └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTPS / WebSocket
┌─────────────────────────────▼───────────────────────────────────┐
│                        BACKEND LAYER                            │
│   FastAPI (Python 3.12)                                         │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│   │ Facility │  │ Incident │  │ Alerts   │  │ AI Agent     │  │
│   │ API      │  │ API      │  │ API      │  │ (LangChain)  │  │
│   └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │               PROVIDER ADAPTER LAYER                    │  │
│   │  OSMAdapter  NHFRAdapter  WeatherAdapter  PCRProvider   │  │
│   │  NCRBAdapter  GTFSAdapter  BhuvanAdapter  IMDAdapter    │  │
│   └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                       DATA LAYER                                │
│   PostgreSQL 16 + PostGIS 3.4                                   │
│   ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│   │ emergency_   │  │ incident_    │  │ administrative_    │   │
│   │ facilities   │  │ reports      │  │ boundaries         │   │
│   └──────────────┘  └──────────────┘  └────────────────────┘   │
│   ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│   │ official_    │  │ road_network │  │ data_source_       │   │
│   │ statistics   │  │ _metadata    │  │ registry           │   │
│   └──────────────┘  └──────────────┘  └────────────────────┘   │
│   pgvector (semantic search for RAG)                            │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                    BACKGROUND JOBS LAYER                        │
│   Celery + Redis                                                │
│   ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│   │ OSM Nightly  │  │ Weather      │  │ Risk Score         │   │
│   │ Ingestion    │  │ Refresh      │  │ Recompute          │   │
│   └──────────────┘  └──────────────┘  └────────────────────┘   │
│   ┌──────────────┐  ┌──────────────┐                           │
│   │ GTFS Static  │  │ Moderation   │                           │
│   │ Refresh      │  │ Queue        │                           │
│   └──────────────┘  └──────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Provider Adapter Pattern

Every external data source is accessed through a typed adapter that implements a common interface. This isolates external API changes from business logic and makes testing easy.

```python
# backend/app/providers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TypeVar, Generic

T = TypeVar("T")

@dataclass
class ProviderResult(Generic[T]):
    data: List[T]
    source_id: str
    fetched_at: datetime
    total_count: int
    page: int = 0
    has_more: bool = False
    errors: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)

class BaseProvider(ABC):
    source_id: str
    provider_name: str
    requires_api_key: bool = False

    def __init__(self, api_key: Optional[str] = None):
        if self.requires_api_key and not api_key:
            raise ValueError(f"{self.provider_name} requires an API key. Set {self.env_key_name}.")
        self.api_key = api_key

    @abstractmethod
    async def fetch(self, **kwargs) -> ProviderResult:
        """Fetch data from the external source."""
        ...

    @abstractmethod
    def validate(self, raw: Any) -> bool:
        """Validate a raw record before ingestion."""
        ...

    @abstractmethod
    def transform(self, raw: Any) -> Any:
        """Transform raw source data to SafeSphere schema."""
        ...
```

### 2.1 Implemented Adapters

| Adapter Class | Source | Data Type | Status |
|---|---|---|---|
| `OSMFacilityAdapter` | Overpass API | Police/fire/hospital POIs | ✅ Implemented |
| `DataGovHealthAdapter` | data.gov.in API | Hospital directory | Planned |
| `OpenMeteoAdapter` | Open-Meteo API | Weather forecast + AQI | Planned |
| `IMDAlertAdapter` | IMD API | Weather warnings | Planned |
| `GTFSDelhiAdapter` | OTD Delhi | Transit stops (GTFS) | Planned |
| `NCRBStatisticsAdapter` | NCRB PDF/Excel | Crime statistics | Planned |
| `BhuvanWMSAdapter` | ISRO Bhuvan | Boundary layers (WMS) | Planned |
| `SimulatedPCRProvider` | Internal | Simulated vehicles | ✅ Implemented (demo only) |

---

## 3. Ingestion Pipeline

### 3.1 Nightly OSM Ingestion (Primary)

```
00:00 IST (nightly)
    │
    ▼
Celery beat → OSMIngestionTask
    │
    ├── Query Overpass API (Delhi bbox)
    │     amenity IN (police, fire_station, hospital, clinic, pharmacy)
    │
    ├── Query Overpass API (Sonipat bbox)
    │
    ├── Parse JSON response
    │     → extract node/way/relation elements
    │     → resolve centroid for ways/relations
    │
    ├── Validate each record
    │     → has lat/lon? → skip if missing
    │     → has name? → flag if missing
    │     → amenity tag present?
    │
    ├── Transform to EmergencyFacility schema
    │     → set source_id = "osm_overpass"
    │     → set source_verified = False
    │     → set source_fetched_at = now()
    │     → compute data_quality_score
    │
    ├── Deduplication
    │     → match on osm_id (exact) — update if exists
    │     → spatial dedup: ST_DWithin(location, existing.location, 50)
    │        + name similarity > 0.85 → flag for review
    │
    ├── Upsert to PostgreSQL (emergency_facilities)
    │     → ON CONFLICT (osm_id) DO UPDATE
    │
    ├── Log provenance → data_source_registry (last_fetched_at)
    │
    └── Report: created/updated/skipped/errors → ingestion_log table
```

### 3.2 Ingestion Job Configuration

```python
# backend/ingestion/schedules.py
from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    "osm-nightly-ingestion": {
        "task": "ingestion.tasks.ingest_osm_facilities",
        "schedule": crontab(hour=0, minute=30),  # 12:30 AM IST
        "kwargs": {"regions": ["delhi", "sonipat"]},
    },
    "weather-refresh-hourly": {
        "task": "ingestion.tasks.refresh_weather",
        "schedule": crontab(minute=0),  # Every hour
    },
    "imd-alerts-refresh": {
        "task": "ingestion.tasks.refresh_imd_alerts",
        "schedule": crontab(minute="*/30"),  # Every 30 minutes
    },
    "gtfs-static-weekly": {
        "task": "ingestion.tasks.refresh_gtfs_static",
        "schedule": crontab(day_of_week="monday", hour=2, minute=0),
    },
    "risk-score-recompute": {
        "task": "ingestion.tasks.recompute_risk_scores",
        "schedule": crontab(hour=3, minute=0),  # 3 AM IST
    },
    "expired-incident-cleanup": {
        "task": "ingestion.tasks.expire_old_incidents",
        "schedule": crontab(hour=4, minute=0),  # 4 AM IST
    },
}
```

---

## 4. Data Provenance Layer

Every ingested record must carry full provenance:

```python
@dataclass
class ProvenanceRecord:
    source_id: str          # e.g. "osm_overpass"
    source_url: str         # exact URL queried
    fetched_at: datetime    # when the request was made
    licence: str            # e.g. "ODbL 1.0"
    attribution: str        # e.g. "© OpenStreetMap contributors"
    is_verified: bool       # False until cross-referenced with official source
    verification_source: Optional[str]  # e.g. "Delhi Police official directory 2024"
    verified_at: Optional[datetime]
    pipeline_version: str   # semver of ingestion code
    raw_data_hash: str      # SHA-256 of raw API response (for audit)
```

This is stored in `data_source_registry` (last_verified_at, last_fetched_at) and embedded in `emergency_facilities.source_id` + `source_fetched_at`.

---

## 5. Caching Strategy

| Layer | Cache | TTL | Reason |
|---|---|---|---|
| OSM facility data | PostgreSQL/PostGIS | 24 hours | Nightly refresh |
| Weather forecast | Redis | 1 hour | Open-Meteo free tier |
| IMD alerts | Redis | 30 minutes | Alert urgency |
| GTFS static stops | PostgreSQL | 7 days | Weekly refresh |
| Boundary polygons | PostgreSQL | 30 days | Rarely change |
| Risk scores | PostgreSQL + Redis | 24 hours | Nightly recompute |
| Map tiles | CDN / S3 | Immutable | PMTiles or CDN cached |

---

## 6. Rate Limit Handling

```python
# backend/app/providers/rate_limiter.py
import asyncio, time
from collections import deque

class RateLimiter:
    """Token-bucket rate limiter for API adapters."""
    def __init__(self, calls_per_minute: int):
        self.calls_per_minute = calls_per_minute
        self.timestamps: deque = deque()

    async def acquire(self):
        now = time.monotonic()
        # Remove timestamps older than 60 seconds
        while self.timestamps and now - self.timestamps[0] > 60:
            self.timestamps.popleft()
        if len(self.timestamps) >= self.calls_per_minute:
            sleep_time = 60 - (now - self.timestamps[0]) + 0.1
            await asyncio.sleep(sleep_time)
        self.timestamps.append(time.monotonic())
```

All adapters implement exponential backoff on 429/503 responses:
- First retry: 30s
- Second retry: 60s
- Third retry: 120s
- After 3 failures: log to `ingestion_failures` table, alert monitoring, skip this run

---

## 7. API Design (FastAPI)

### 7.1 Core Endpoints

```
GET  /api/v1/facilities                     # List emergency facilities (bbox filter)
GET  /api/v1/facilities/{id}               # Single facility detail
GET  /api/v1/facilities/nearby             # Nearest N facilities by type + radius
POST /api/v1/incidents                     # Submit community report
GET  /api/v1/incidents                     # List verified incidents (bbox, time filter)
GET  /api/v1/weather/current              # Current weather for location
GET  /api/v1/weather/forecast             # Hourly forecast
GET  /api/v1/weather/alerts               # IMD district alerts
GET  /api/v1/boundaries/{admin_level}      # Administrative boundaries
GET  /api/v1/route/safe                   # Route comparison with safety overlay
GET  /api/v1/statistics/crime             # NCRB aggregate stats by district
GET  /api/v1/sources                      # Data source registry (transparency)
WS   /api/v1/alerts/subscribe            # WebSocket: geofenced alert stream
POST /api/v1/alerts/subscriptions        # Create alert subscription
```

### 7.2 Facility Nearby Query Example

```python
# GET /api/v1/facilities/nearby?lat=28.6139&lon=77.2090&type=police_station&radius_m=2000&limit=5
@router.get("/facilities/nearby")
async def get_nearby_facilities(
    lat: float = Query(..., ge=8.0, le=38.0),
    lon: float = Query(..., ge=68.0, le=98.0),
    facility_type: FacilityType = Query(...),
    radius_m: int = Query(2000, ge=100, le=10000),
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    facilities = await FacilityService.get_nearby(
        db, lat=lat, lon=lon,
        facility_type=facility_type,
        radius_m=radius_m,
        limit=limit,
    )
    return {
        "facilities": [FacilityResponse.from_orm(f) for f in facilities],
        "data_notice": "Facility data sourced from OpenStreetMap and government directories. Verify contact details before use in emergencies.",
        "source_attribution": "© OpenStreetMap contributors (ODbL 1.0)",
    }
```

---

## 8. Database Migrations

See `migrations/` directory for Alembic migration files.

```
migrations/
├── env.py
├── script.py.mako
└── versions/
    ├── 001_create_enums.sql
    ├── 002_create_emergency_facilities.sql
    ├── 003_create_incident_reports.sql
    ├── 004_create_official_statistics.sql
    ├── 005_create_admin_boundaries.sql
    ├── 006_create_road_network_metadata.sql
    ├── 007_create_data_source_registry.sql
    ├── 008_create_incident_verification_events.sql
    ├── 009_create_user_alert_subscriptions.sql
    └── 010_create_authorized_emergency_integrations.sql
```

---

## 9. Technology Stack

| Component | Technology | Version | Purpose |
|---|---|---|---|
| Frontend | React + TypeScript | 18+ | UI |
| Map rendering | MapLibre GL JS | 4+ | OSM vector tiles + data layers |
| Map tiles | Protomaps / Stadia Maps | — | Tile hosting |
| Routing | Self-hosted OSRM | Latest | Pedestrian routing |
| Geocoding | LocationIQ or Photon | — | Address lookup |
| Backend API | FastAPI + Python | 3.12 | REST API + WebSocket |
| ORM | SQLAlchemy 2.0 (async) | 2.0+ | DB access |
| Migrations | Alembic | — | Schema versioning |
| Database | PostgreSQL + PostGIS | 16 + 3.4 | Spatial data store |
| Vector search | pgvector | — | RAG semantic search |
| Task queue | Celery + Redis | — | Background ingestion jobs |
| AI agent | LangChain / LangGraph | — | RAG query engine |
| Auth | JWT + OAuth2 | — | User authentication |
| Secret management | Environment variables | — | API keys (never hardcoded) |
| Container | Docker + Docker Compose | — | Local dev + deployment |
| Testing | pytest + pytest-asyncio | — | Unit + integration tests |
