# SafeSphere AI — Phase 3: Road Network Ingestion, Walking Safety Scoring & Route Comparison
**Pilot Scope:** Delhi (NCT) & Sonipat (Haryana)  
**Status:** Implemented & Verified (105/105 Tests Passing)  
**Date:** 2026-11-05  

---

## 1. Executive Summary

Phase 3 transitions SafeSphere AI from static facility discovery and incident reporting into an **active, location-aware pedestrian safety intelligence engine**. It equips citizens in Delhi and Sonipat with evidence-based pedestrian routing alternatives, transparent walkability scores, and real-time safety corridor evaluations.

### Key Deliverables Completed
1. **OpenStreetMap Highway Ingestion Adapter (`backend/ingestion/road_adapter.py`)**:
   - Queries Overpass API for pedestrian-walkable ways across Delhi NCT `(28.40, 76.83, 28.88, 77.35)` and Sonipat `(28.87, 76.88, 29.07, 77.15)`.
   - Parses ways with full LineString geometries, geodesic length calculations (Haversine formula), and road classification (`footway`, `pedestrian`, `path`, `residential`, `tertiary`, `secondary`, `living_street`, `steps`).
   - Normalizes street lighting attributes (`lit=yes/no/24/7/automatic/unknown`) and pedestrian sidewalks (`sidewalk=both/left/right/no/unknown`).
2. **PostGIS Road Network Persistence (`backend/app/db/road_repository.py`)**:
   - Backed by `road_network_metadata` table with GiST indexing on `geometry` (LineString SRID 4326).
   - High-performance idempotent upsert handling via `ON CONFLICT (osm_way_id) DO UPDATE`.
   - Real-time corridor incident density calculation (`incident_count_30d`, `incident_count_90d`) joining against approved community incident reports.
3. **Pedestrian Safe Routing Engine (`backend/app/services/routing.py`)**:
   - Computes multi-route comparisons:
     - **Safety-Optimized Route**: Maximizes illuminated thoroughfares, dedicated sidewalks, and proximity to active emergency facilities (police stations, hospitals).
     - **Shortest Walking Route**: Direct pedestrian path prioritizing minimal travel time.
     - **Well-Lit Transit Corridor**: High-illumination route favoring major transit stations and lit commercial avenues.
   - Dynamic day/night heuristic: Automatically shifts score weights when walking at night in India (IST 18:30 to 06:00), doubling penalties for unlit segments.
4. **FastAPI Endpoints (`backend/app/api/routing.py`)**:
   - `POST /api/v1/routing/compare`: Compares candidate routes between two coordinates with waypoint geometries, estimated durations, and transparent safety breakdowns.
   - `GET /api/v1/roads/nearby`: Queries road segments within a given radius with walkability and lighting metadata.
   - `POST /api/v1/roads/recompute-scores`: Protected administrator/moderator endpoint to batch recalculate safety scores across road segments based on recent incident trends.
5. **Background Automation (`backend/ingestion/tasks.py`)**:
   - Scheduled Celery task `ingestion.tasks.ingest_osm_roads` running weekly on Sundays at 1:00 AM IST.
6. **Automated Verification**:
   - 20 new comprehensive tests in `backend/tests/test_routing.py`.
   - Full test suite passing: **105 passed in 7.71s** (100% pass rate).

---

## 2. Safety Scoring Model & Heuristic Formulation

SafeSphere AI intentionally rejects opaque "black box" machine learning models for public safety routing. In compliance with public sector transparency guidelines and the Digital Personal Data Protection Act (DPDPA 2023), all safety scores are rule-based, deterministic, and verifiable by the public.

### Baseline Segment Walkability Equation
For each individual road segment, a baseline physical safety score $S_{\text{base}} \in [0.05, 0.95]$ is calculated:

$$S_{\text{base}} = S_{\text{init}} + \Delta_{\text{lit}} + \Delta_{\text{sidewalk}} + \Delta_{\text{type}} + \Delta_{\text{surface}}$$

Where:
- $S_{\text{init}} = 0.50$ (neutral baseline).
- $\Delta_{\text{lit}}$:
  - $+0.22$ for confirmed lighting (`yes`, `24/7`, `automatic`).
  - $-0.18$ for confirmed unlit roads (`no`).
  - $0.00$ for unknown lighting (accompanied by an explicit uncertainty flag).
- $\Delta_{\text{sidewalk}}$:
  - $+0.18$ for sidewalks on both sides (`both`).
  - $+0.10$ for single-side sidewalk (`left`, `right`).
  - $-0.10$ for confirmed absence of sidewalk (`no`).
- $\Delta_{\text{type}}$:
  - $+0.15$ for pedestrian-only spaces (`pedestrian`, `footway`, `living_street`).
  - $+0.05$ for pedestrian stairs (`steps`).
  - $-0.12$ for high-speed vehicular roads (`primary`, `secondary`).
- $\Delta_{\text{surface}}$:
  - $+0.05$ for paved/asphalt/concrete surfaces.
  - $-0.08$ for unpaved/dirt/mud surfaces.

### Route Corridor Overall Safety Index
The composite route safety index $I_{\text{route}} \in [0, 100]$ combines infrastructure, temporal lighting, incident proximity, and emergency support:

$$I_{\text{route}} = \text{clamp}\Big( \bar{S}_{\text{infra}} \times 100 - P_{\text{night}} - P_{\text{incidents}} + B_{\text{facility}}, \, 10, \, 98 \Big)$$

- **Nighttime Penalty ($P_{\text{night}}$)**: If departure is between 18:30 and 06:00 IST and lighting coverage $< 70\%$, a penalty of up to 20 points is applied.
- **Incident Corridor Penalty ($P_{\text{incidents}}$)**: $8 \times N_{\text{incidents}}$ (where $N_{\text{incidents}}$ is the count of approved community incidents within 250m corridor in the last 30 days).
- **Emergency Facility Bonus ($B_{\text{facility}}$)**: $+6$ points per verified police station or 24/7 emergency hospital along the corridor (up to $+12$).

---

## 3. Data Governance & Ethical Guardrails

1. **Explicit Uncertainty Disclosures**:
   - If $> 30\%$ of road segments along a route lack verified lighting in OpenStreetMap, the response embeds a prominent advisory note:
     > *"Portions of road segments have unknown street lighting in OpenStreetMap."*
2. **Never Guarantee Physical Safety**:
   - SafeSphere AI explicitly rejects marketing claims such as "100% safe route" or "crime-free zone".
   - Every API response includes the mandatory legal disclaimer:
     > *"EMERGENCY NOTICE: SafeSphere AI routing guidance is advisory and calculated from open-source community data. It is NOT a guarantee of physical safety. In an emergency or if you feel unsafe, call 112 immediately."*
3. **Emergency Escalation Pathway**:
   - In all UI layers and API documentation, the ERSS 112 nationwide helpline is presented as the primary emergency channel. Community routing is strictly advisory navigation assistance.

---

## 4. Verification & Automated Test Summary

```bash
TESTING=true PYTHONPATH=./backend /usr/local/bin/python3.13 -m pytest backend/tests/ -v
```

### Results
- `backend/tests/test_osm_adapter.py`: **49 passed** (OSM facility Overpass parser, geocoding, quality scoring).
- `backend/tests/test_persistence.py`: **19 passed** (PostGIS `ST_DWithin` queries, idempotency, data source registry).
- `backend/tests/test_incidents.py`: **17 passed** (PII redaction, prompt injection defense, moderation workflow, public spatial queries).
- `backend/tests/test_routing.py`: **20 passed** (Geodesic distance, WKT parsing, lighting normalizers, road repository upsert, routing engine, endpoint validation).

**Total: 105 passed in 7.71s (100% passing across all 4 suites)**
