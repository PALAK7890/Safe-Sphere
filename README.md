# SafeSphere AI

**Location-aware public safety intelligence platform — Delhi & Sonipat pilot**

> ⚠️ **Emergency:** Call **112** for all emergencies in India.

SafeSphere AI is a research and mapping tool that aggregates public safety data from verified sources, accepts community incident reports, and provides safety context for Delhi (NCT) and Sonipat (Haryana).

---

## What This Is

- A **map platform** showing emergency facilities (police, fire, hospitals)
- A **community reporting** tool for local safety incidents (with full moderation)
- A **weather and AQI** overlay (Open-Meteo + IMD)
- A **historical context** layer for NCRB crime statistics
- An **AI-assisted** question-answering agent (RAG, read-only)

## What This Is NOT

- An official police or government system
- A live crime monitoring system
- A replacement for calling 112
- A source of live PCR/patrol vehicle data (pending formal authorization)

---

## Quick Start (Development)

```bash
# 1. Clone and enter the project
cd SafeSphere

# 2. Copy environment variables
cp .env.example .env
# Fill in your real API keys in .env

# 3. Start all services
docker compose up -d

# 4. Apply database migrations
docker compose exec api python -m alembic upgrade head

# 5. Run OSM ingestion (first-time data load)
docker compose exec worker celery -A ingestion.tasks call ingestion.tasks.ingest_osm_facilities

# 6. Access the API
open http://localhost:8001/docs
```

---

## Project Structure

```
SafeSphere/
├── docs/
│   ├── data_source_audit.md          # Verified sources with status ratings
│   ├── api_access_matrix.md          # API access, costs, restrictions
│   ├── data_dictionary.md            # Schema field definitions + provenance
│   ├── emergency_integration_plan.md # Official emergency pathways
│   ├── data_architecture.md          # System architecture + adapter pattern
│   ├── privacy_and_data_governance.md # DPDPA compliance + risk model rules
│   └── implementation_roadmap.md     # Phased build plan
├── data/
│   └── source_registry.csv           # Machine-readable source registry
├── migrations/
│   └── 001_initial_schema.sql        # PostgreSQL/PostGIS schema
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI entry point
│   │   ├── api/                      # API routers
│   │   │   ├── facilities.py         # Emergency facility endpoints
│   │   │   ├── incidents.py          # Community report endpoints
│   │   │   ├── weather.py            # Weather + AQI endpoints
│   │   │   └── sources.py            # Data source transparency API
│   │   ├── models/                   # Pydantic request/response models
│   │   │   ├── facility.py
│   │   │   └── incident.py
│   │   └── providers/                # External data provider adapters
│   │       ├── base_pcr_provider.py  # PCR vehicle interface (abstract)
│   │       └── simulated_pcr_provider.py  # Dev-only simulated provider
│   ├── ingestion/
│   │   ├── osm_adapter.py            # OSM Overpass ingestion (VERIFIED ✅)
│   │   └── tasks.py                  # Celery background jobs
│   ├── tests/
│   │   └── test_osm_adapter.py       # 25 unit tests for OSM adapter
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml
├── .env.example                      # Placeholder env vars only
└── .gitignore
```

---

## Data Sources

| Category | Source | Status |
|---|---|---|
| Police/fire/hospital POIs | OpenStreetMap (Overpass API) | ✅ A — ODbL attribution required |
| Hospital directory | data.gov.in NHFR | ✅ A — Free API key |
| Weather + AQI | Open-Meteo | ✅ A — CC BY 4.0, no key needed |
| Weather alerts | IMD API (api.imd.gov.in) | ⚠️ B — Register for key |
| Transit stops | OTD Delhi (DTC + DMRC GTFS) | ✅ A — Free download |
| Admin boundaries | OSM via Overpass | ✅ A — ODbL |
| Crime statistics | NCRB (annual aggregate) | ⚠️ D — No geocoordinates |
| Live PCR vehicles | None public | ❌ C — MoU required |
| ERSS 112 API | None public | ❌ F — Not available |

See [`docs/data_source_audit.md`](docs/data_source_audit.md) for full details.

---

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/test_osm_adapter.py -v
```

---

## Attribution

- Map data: **© OpenStreetMap contributors** ([ODbL 1.0](https://opendatacommons.org/licenses/odbl/))
- Weather data: **Open-Meteo.com** ([CC BY 4.0](https://open-meteo.com))
- Hospital data: **National Health Mission / data.gov.in** (GODL)
- Transit data: **Dept of Transport, GNCT Delhi + IIIT-Delhi**
- Weather alerts: **India Meteorological Department**

---

## Legal

Community incident reports submitted to SafeSphere AI are **NOT** official police complaints or FIRs. For formal reporting, visit your nearest police station or use official online portals.

See [`docs/privacy_and_data_governance.md`](docs/privacy_and_data_governance.md) for DPDPA 2023 compliance details.
