# SafeSphere AI — API Access Matrix
**Scope:** Delhi (NCT) + Sonipat (Haryana) Pilot
**Last Updated:** 2026-10-25

---

## Quick Reference

| API / Dataset | Provider | Access Type | API Key? | Cost | Commercial OK? | Rate Limit | Status |
|---|---|---|---|---|---|---|---|
| Overpass API (OSM POIs) | FOSSGIS / OSM | Public | ❌ | Free | ✅ (attribution) | ≤100 batch/day public | A |
| data.gov.in API | Govt of India | Registration | ✅ Free | Free | ✅ GODL | Not documented | A |
| NHFR Hospital Directory | NHM / MoHFW | Registration | ✅ Free | Free | ✅ GODL | Not documented | B |
| Open-Meteo Forecast | Open-Meteo | Public | ❌ | Free (non-comm) / $29+ | ❌ Free tier | 10K/day | A |
| Open-Meteo AQI | Open-Meteo | Public | ❌ | Free (non-comm) / $29+ | ❌ Free tier | 10K/day | A |
| Open-Meteo Historical | Open-Meteo | Public | ❌ | Free (non-comm) / $29+ | ❌ Free tier | 10K/day | A |
| IMD Weather API | India Met Dept | Registration | ✅ Free | Free (govt data) | TBC via MoU | Not documented | B |
| OpenWeatherMap Current | OWM | Registration | ✅ Free | Free tier / $40+/mo | ✅ Paid tiers | 60/min, 1M/mo | A |
| OpenWeatherMap AQI | OWM | Registration | ✅ Free | Free | ✅ | Shared with above | A |
| OTD Delhi GTFS Static | Dept Transport Delhi | Public | ❌ | Free | ✅ Open govt | No limit (download) | A |
| OTD Delhi GTFS-RT | Dept Transport Delhi | Registration | ✅ Free | Free | ✅ | Not documented | A |
| Bhuvan WMS | ISRO/NRSC | Public | ❌ | Free | Non-comm only | Not documented | A |
| Bhuvan Data Download | ISRO/NRSC | Registration | ✅ Free | Free | Needs MoU (comm) | Not documented | B |
| OSM Admin Boundaries | OpenStreetMap | Public | ❌ | Free | ✅ ODbL | Shared Overpass | A |
| GADM Boundaries | GADM | Public | ❌ | Free | ❌ Non-comm only | No limit (download) | B |
| OpenRouteService | HeiGIT | Registration | ✅ Free | Free / custom | ✅ (self-hosted) | 2K dir/day free | A |
| OSRM (self-hosted) | Project OSRM | Self-hosted | ❌ | Infra cost | ✅ BSD-2 | Unlimited | A |
| Nominatim (self-hosted) | OSM / Nominatim | Self-hosted | ❌ | Infra cost | ✅ | Unlimited | A |
| LocationIQ Geocoding | LocationIQ | Registration | ✅ Free tier | Free 5K/day / paid | ✅ | 5K/day free | A |
| Stadia Maps Tiles | Stadia | Registration | ✅ | $0 dev / $20+/mo | ✅ paid | 200K credits/mo free | A |
| Protomaps / PMTiles | Protomaps | Public CDN / self | ❌ / ✅ | ~$0–5/mo R2 | ✅ | None (self-hosted) | A |
| MapTiler Cloud | MapTiler | Registration | ✅ | Free (5K sess) / $30+/mo | ✅ paid | 100K req/mo free | A |
| NCRB Crime Reports | NCRB / MHA | Public | ❌ | Free | Research use | No limit (download) | D |
| iRAD Crash Database | IIT Madras / MoRTH | Govt restricted | ❌ | N/A | ❌ Restricted | N/A | C |
| ERSS 112 API | MHA / NIC | Govt partnership | N/A | N/A | ❌ Formal MoU | N/A | F |
| Delhi PCR Live Feed | Delhi Police | Govt authorization | N/A | N/A | ❌ | N/A | C |
| Digital Police FIR API | CCTNS / BPR&D | Govt restricted | N/A | N/A | ❌ | N/A | F |
| CPCB AQI Ground Truth | CPCB | Web only (no API) | N/A | Free (web) | ❌ (no API) | N/A | D |

---

## Detailed Access Instructions

### 1. data.gov.in API
**Registration:** https://data.gov.in/user/register
**API Base:** `https://api.data.gov.in/resource/{resource_id}?api_key=YOUR_KEY&format=json`
**Key datasets:**
- National Hospital Directory: search "National Hospital Directory with Geo Code"
- Crime statistics: search "NCRB", "police station", "crime"
**Filters:** `filters[State]=Delhi`, `filters[State]=Haryana`
**Pagination:** `offset=0&limit=100` (max 100 per request)

### 2. Open-Meteo (No Key Required)
**Forecast:** `https://api.open-meteo.com/v1/forecast?latitude=28.6139&longitude=77.2090&hourly=temperature_2m,rain,wind_speed_10m,uv_index&timezone=Asia/Kolkata`
**AQI:** `https://air-quality-api.open-meteo.com/v1/air-quality?latitude=28.6139&longitude=77.2090&hourly=pm2_5,pm10,us_aqi`
**Historical:** `https://archive-api.open-meteo.com/v1/archive?latitude=28.6139&longitude=77.2090&start_date=2024-01-01&end_date=2024-12-31&hourly=temperature_2m,rain`
Attribution required: "Weather data by Open-Meteo.com" (CC BY 4.0)
**Commercial:** Switch to `customer-api.open-meteo.com` with API key ($29/month Standard)

### 3. IMD API
**Registration:** https://api.imd.gov.in (create account)
**Auth:** `X-API-KEY` header + `Authorization: Bearer <JWT>`
**District warnings:** `GET https://api.imd.gov.in/api/v1/districtforecast?state=Delhi`
**Nowcast:** `GET https://api.imd.gov.in/api/v1/stationnowcast?id=Delhi`
Note: Endpoint stability and SLA not publicly documented — test after registration.

### 4. OpenWeatherMap
**Registration:** https://openweathermap.org/api
**Current weather:** `https://api.openweathermap.org/data/2.5/weather?lat=28.6139&lon=77.2090&appid=YOUR_KEY`
**AQI:** `http://api.openweathermap.org/data/2.5/air_pollution?lat=28.6139&lon=77.2090&appid=YOUR_KEY`
**Free tier:** 60 calls/min; 1M calls/month — no credit card required

### 5. OTD Delhi GTFS
**Portal:** https://otd.delhi.gov.in
**Static DTC buses:** Direct ZIP download from portal (no auth)
**Static DMRC metro:** Direct ZIP download from portal (no auth)
**Real-time GTFS-RT:** Register at portal for free API key → `GET /api/realtime/VehiclePositions.pb?key=YOUR_KEY`
**Mobility Database ID:** mdb-1262

### 6. Overpass API
**Endpoint:** `https://overpass-api.de/api/interpreter`
**Required header:** `User-Agent: SafeSphere-AI/1.0 (contact@example.com)`
**Caching rule:** Never query per user request. Run nightly batch → store in PostGIS.
**Self-hosting:** https://wiki.openstreetmap.org/wiki/Overpass_API/Installation (Docker available)

### 7. Bhuvan WMS (No Registration for Streaming)
**WMS:** `https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms`
**GetCapabilities:** `https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetCapabilities`
Add as WMS layer in QGIS or MapLibre GL JS via custom WMS adapter.

### 8. OSRM (Self-Hosted — Recommended for Routing)
```bash
# Download India extract from Geofabrik
wget https://download.geofabrik.de/asia/india-latest.osm.pbf

# Process and run OSRM with foot profile
docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-extract -p /opt/foot.lua /data/india-latest.osm.pbf
docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-partition /data/india-latest.osrm
docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-customize /data/india-latest.osrm
docker run -t -i -p 5000:5000 -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-routed --algorithm mld /data/india-latest.osrm
```
**Route endpoint:** `GET http://localhost:5000/route/v1/foot/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson`

### 9. LocationIQ Geocoding (Recommended for Production)
**Registration:** https://locationiq.com
**Free tier:** 5,000 requests/day; commercial use permitted
**Geocode:** `https://us1.locationiq.com/v1/search?key=YOUR_KEY&q=Connaught+Place+Delhi&format=json`
**Reverse:** `https://us1.locationiq.com/v1/reverse?key=YOUR_KEY&lat=28.6139&lon=77.2090&format=json`

### 10. Stadia Maps Tiles
**Registration:** https://client.stadiamaps.com
**MapLibre GL JS tile URL:** `https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}.png?api_key=YOUR_KEY`
**Vector tile style:** `https://tiles.stadiamaps.com/styles/alidade_smooth.json?api_key=YOUR_KEY`
**Attribution:** "© Stadia Maps © OpenStreetMap contributors"
**Free:** 200K credits/month (non-commercial); Starter $20/month (commercial)

---

## What Requires Official Authorization

| Data | Authority to Contact | Department | Estimated Timeline |
|---|---|---|---|
| ERSS 112 API integration | State Police Commissioner + NIC/C-DAC | MHA Women Safety Division | 3–12 months |
| Delhi PCR live vehicle feed | Delhi Police Commissioner | Delhi Police Operations | 6–18 months |
| iRAD crash database | IIT Madras (Road Bytes Group) + MoRTH | Transport Research Wing | 3–6 months (academic MoU) |
| Haryana Police official data export | DGP Haryana or District SP Sonipat | Haryana Police Commissionerate | 1–3 months (RTI/formal request) |
| Delhi Police official station export | Commissioner of Police Delhi | Delhi Police PRO / Data Cell | 1–3 months (RTI/formal request) |
| ISRO Bhuvan commercial data download | NRSC Data Dissemination Centre | ISRO/NRSC Hyderabad | 1–2 months |

---

## Environment Variables Required

See `.env.example` for placeholder list. Keys needed:
- `DATA_GOV_IN_API_KEY` — data.gov.in API
- `IMD_API_KEY` — IMD weather API
- `OWM_API_KEY` — OpenWeatherMap
- `OTD_DELHI_API_KEY` — Delhi OTD GTFS-RT
- `LOCATIONIQ_API_KEY` — geocoding
- `STADIA_MAPS_API_KEY` — map tiles (if using Stadia)
- `MAPTILER_API_KEY` — map tiles (if using MapTiler)
- `OPEN_METEO_API_KEY` — commercial tier only (not needed for free dev tier)
