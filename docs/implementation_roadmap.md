# SafeSphere AI — Implementation Roadmap
**Scope:** Delhi (NCT) + Sonipat (Haryana) Pilot
**Last Updated:** 2026-10-25

---

## Phase 1 — Foundation (Weeks 1–4) ✅ START NOW

Everything in this phase uses verified, publicly accessible data. No authorization required.

### Data
- [x] Set up PostgreSQL + PostGIS + pgvector (Docker Compose)
- [ ] Run OSM Overpass ingestion for Delhi + Sonipat:
  - `amenity=police`, `amenity=fire_station`, `amenity=hospital`, `amenity=pharmacy`
- [ ] Download and ingest National Hospital Directory from data.gov.in API
- [ ] Import GADM Level 2+3 boundaries for Delhi and Sonipat (non-commercial dev use)
- [ ] Import OSM administrative boundaries via Overpass (for production)
- [ ] Download Geofabrik Delhi+Haryana road PBF extract → import to PostGIS via osm2pgsql
- [ ] Download DTC Bus + DMRC Metro GTFS static feeds from otd.delhi.gov.in
- [ ] Configure Open-Meteo integration (no API key needed)
- [ ] Register for OpenWeatherMap free API key (backup weather)
- [ ] Register for data.gov.in API key
- [ ] Set up nightly Celery + Redis job for OSM refresh

### Backend
- [ ] FastAPI project scaffold with SQLAlchemy async models
- [ ] Alembic migrations for all 9 database tables
- [ ] `GET /api/v1/facilities/nearby` — police/fire/hospital by radius
- [ ] `POST /api/v1/incidents` — community report submission (with disclaimer)
- [ ] `GET /api/v1/weather/current` — Open-Meteo integration
- [ ] Data source registry API `GET /api/v1/sources`
- [ ] Provider adapter: OSMFacilityAdapter (see `backend/ingestion/`)
- [ ] Provider adapter: OpenMeteoAdapter
- [ ] SimulatedPCRProvider (clearly labeled as SIMULATED)
- [ ] Unit tests for all adapters and core endpoints

### Frontend (basic map)
- [ ] MapLibre GL JS with Protomaps/Stadia Maps tiles
- [ ] Layer: emergency facilities (police/fire/hospital markers)
- [ ] Panel: tap a facility → name, type, phone, data source attribution
- [ ] Button: "Call Emergency (112)" always visible
- [ ] Attribution: "© OpenStreetMap contributors" on map
- [ ] Notice: "Data sourced from OpenStreetMap — not officially verified"

**Deliverable:** Working map showing OSM + NHFR facilities in Delhi + Sonipat with accurate data attribution.

---

## Phase 2 — Community Reporting & Alerts (Weeks 5–8)

### Data
- [ ] Download NCRB Crime in India 2022 + 2023 Excel tables
- [ ] Ingest state/city-level crime statistics into `official_incident_statistics`
- [ ] Set up GTFS-RT real-time bus position feed from OTD Delhi

### Backend
- [ ] Full incident reporting pipeline:
  - PII scrubbing on description text
  - Location fuzzing (snap to road + ±50m jitter)
  - Deduplication check (spatial + text similarity)
  - Moderation queue with status workflow
  - `incident_verification_events` audit trail
- [ ] Geofenced alert system (WebSocket + push notifications)
- [ ] `GET /api/v1/statistics/crime` — NCRB data by district/year
- [ ] Risk score computation job (transparent density model)
- [ ] Road segment safety overlay `GET /api/v1/route/safe`

### Frontend
- [ ] Incident report submission form with:
  - Mandatory disclaimer: "This is NOT an official police complaint"
  - Links to official reporting channels (112, cybercrime.gov.in)
  - Category selector + description (≤1000 chars)
  - Map pin placement
- [ ] Incident density heatmap (aggregated clusters of 5+)
- [ ] Red/Yellow/Green safety overlay on road segments (with uncertainty labels)
- [ ] Alert subscription management panel
- [ ] Crime statistics charts panel (NCRB aggregate data with caveats)
- [ ] Transit stop layer (DTC + DMRC from GTFS)

---

## Phase 3 — Intelligence & Polish (Weeks 9–12)

### Data
- [ ] Register for IMD API and integrate district weather warnings
- [ ] Set up self-hosted OSRM with foot.lua pedestrian profile (India OSM extract)
- [ ] Set up self-hosted LocationIQ-compatible Photon geocoder OR use LocationIQ API
- [ ] Apply for NHFR API access (NHM registration)
- [ ] Begin RTI process for official police station directory (Delhi + Haryana)
- [ ] Explore OSM community mapping sprint for Sonipat (pedestrian infrastructure)

### Backend
- [ ] Safe route comparison (`/api/v1/route/safe`): OSRM walking route + incident overlay
- [ ] RAG AI agent: LangChain + pgvector for answering safety questions
- [ ] Semantic search over facility descriptions and incident summaries
- [ ] IMD weather alert integration → push alerts for severe weather events
- [ ] Data quality dashboard API (internal): missing phone/address stats by district

### Frontend
- [ ] Safe route mode: compare 2–3 pedestrian routes with safety score overlay
- [ ] AI assistant panel: natural language safety Q&A
- [ ] Weather alerts panel (IMD integration)
- [ ] DMRC metro integration: nearest metro stations with route to them

---

## Phase 4 — Authorization Pursuit (Months 4–12)

**None of this can be built until formal authorization is received. Design interfaces only.**

| Action | Authority | Timeline |
|---|---|---|
| Submit MoU application for Delhi Police PCR data | Commissioner of Police, Delhi | Month 4 |
| Submit MoU application for ERSS 112 API | MHA + NIC/C-DAC | Month 4 |
| Submit application for Haryana Police PCR data | CP Sonipat | Month 4 |
| Follow up on academic partnership for iRAD data | IIT Madras Road Bytes | Month 3 |
| Apply for Bhuvan commercial data download MoU | NRSC Hyderabad | Month 4 |
| NHFR API formal access registration | NHM | Month 2 |

---

## What Can Be Built Immediately (No Authorization)

| Feature | Data Source | Confidence |
|---|---|---|
| Emergency facility map (police/fire/hospital) | OSM + data.gov.in NHFR | High |
| Facility detail panel (name, location, phone*) | OSM | Medium (*sparse) |
| Community incident reporting | Own system | High |
| Weather overlay (temperature, rain, AQI, UV) | Open-Meteo | High |
| Delhi bus + metro transit stops | OTD Delhi GTFS | High |
| Admin boundary layers | OSM + GADM | High |
| Historical crime context (district-level) | NCRB Excel tables | High |
| Pedestrian route calculation | Self-hosted OSRM | High |
| Geocoding | LocationIQ / Photon | High |
| Geofenced weather alerts | IMD API (post-registration) | Medium |
| Road safety score (community-based) | Own incident data | Medium |

## What Requires Authorization

| Feature | Required Authorization | Estimated Wait |
|---|---|---|
| Live PCR vehicle positions | Delhi Police / Haryana Police MoU | 6–18 months |
| ERSS 112 dispatch data | MHA + NIC/C-DAC MoU | 6–18 months |
| Geocoded crash locations | iRAD academic MoU | 3–6 months |
| Street lighting GIS | MCD / NDMC formal request | 3–12 months |

## What Cannot Be Filled with Verified Public Sources

| Gap | Status |
|---|---|
| Haryana Roadways / Sonipat bus GTFS | No public GTFS feed |
| Fire station coverage for Sonipat | No structured public dataset |
| Sub-post (chauki) level police data | Not publicly geocoded |
| CPCB ground-truth AQI as API | Web only; no public REST API |
| NCRB district-level data for Sonipat | Haryana SCRB only (contact separately) |

---

## Minimum Viable Data Stack for Launch

| Layer | Tool | Cost |
|---|---|---|
| Database | PostgreSQL 16 + PostGIS + pgvector | Infrastructure (~$20/mo VPS) |
| Tiles | Protomaps + Cloudflare R2 | ~$1–5/mo |
| Routing | Self-hosted OSRM | Shared VPS |
| Geocoding | LocationIQ free tier | Free (5K/day) |
| Weather | Open-Meteo free | Free |
| Weather alerts | IMD API (after registration) | Free |
| POI data | OSM Overpass (nightly batch) | Free |
| Health facilities | data.gov.in NHFR API | Free (API key) |
| Transit | OTD Delhi GTFS static | Free |
| Task queue | Redis + Celery | Shared infra |
| **Total estimated monthly cost** | | **~$25–50/month** |
