# SafeSphere AI — Data Source Audit
**Geographic Scope:** Delhi (NCT) and Sonipat (Haryana)
**Last Verified:** 2026-10-25
**Status Legend:** A = Verified usable · B = Documented, restrictions unclear · C = Partnership required · D = Historical/incomplete · E = Unverified · F = Not available

---

## 1. Police Stations

### 1.1 OpenStreetMap (Overpass API) — `amenity=police`
| Field | Value |
|---|---|
| Provider | OpenStreetMap / FOSSGIS e.V. |
| API URL | https://overpass-api.de/api/interpreter |
| Fields | id, lat/lon, name, name:hi, addr:street, addr:city, phone, website, opening_hours |
| Delhi Coverage | ⭐⭐⭐ Moderate — major stations present; sub-posts/chaukis often missing |
| Sonipat Coverage | ⭐⭐ Low-Moderate — district HQ likely; tehsil/village posts often missing |
| Access | Public; User-Agent header mandatory |
| Rate Limits | ≤100 scheduled queries/day on public endpoint; self-host for production |
| Licence | ODbL 1.0 — attribution required: "© OpenStreetMap contributors" |
| **Status** | **A — Usable with caveats; NOT officially verified** |

**Delhi query bbox:** `(28.40,76.83,28.88,77.35)`
**Sonipat query bbox:** `(28.87,76.88,29.07,77.15)`

Sample query (Delhi police stations):
```
[out:json][timeout:60];
(
  node["amenity"="police"](28.40,76.83,28.88,77.35);
  way["amenity"="police"](28.40,76.83,28.88,77.35);
  relation["amenity"="police"](28.40,76.83,28.88,77.35);
);
out body; >; out skel qt;
```

> ⚠️ OSM records are community-maintained, NOT officially verified. All records must be tagged `source_verified=false` until cross-referenced with official directories.

---

### 1.2 Delhi Police — Official Directory
| Field | Value |
|---|---|
| Provider | Delhi Police, Ministry of Home Affairs |
| Official URL | https://www.delhipolice.gov.in |
| Data | Station name, district, address, SHO name, phone — web UI only |
| API | ❌ None |
| Bulk Download | ❌ Not documented; requires scraping or RTI |
| Licence | Government of India; redistribution terms unclear |
| **Status** | **B — Data visible in UI; no structured download** |

**Action:** Submit RTI for official station CSV/Excel, or contact Delhi Police PRO.

Confirmed helplines: ERSS 112 | Cyber Crime 1930 | Women 1091 | Senior Citizen 1291 | Missing 1094

---

### 1.3 Haryana Police — Sonipat Commissionerate
| Field | Value |
|---|---|
| Provider | Haryana Police, Government of Haryana |
| Official URL | https://haryanapolice.gov.in |
| Data | Station name, SHO, phone — web UI only |
| API | ❌ None |
| **Status** | **B — Data visible; no structured download** |

**Confirmed Sonipat stations (from Haryana Police portal):**
| Station | Phone |
|---|---|
| Police Control Room Sonipat | 0130-2222903 / 112 |
| Civil Lines Sonipat | 0130-2989400 |
| Sonipat City | 0130-2240520 |
| Sonipat Sadar | 0130-2220522 |
| Murthal | 0130-2482562 |
| Kundli | 0130-2371131 |
| Rai | 0130-2366370 |
| Ganaur | 0130-2460037 |
| HSIIDC Barhi | 0130-2982980 |

Note: Sonipat was upgraded to a Police Commissionerate (subdivisions: Sonipat East, Sonipat West, Gohana, Ganaur, Kharkhoda).

---

### 1.4 data.gov.in — Police/Crime Datasets
| Field | Value |
|---|---|
| Official URL | https://data.gov.in |
| Dataset | BPR&D "Data on Police Organisations"; NCRB crime tables |
| Fields | State/district tabular counts; station counts — rarely geocoordinates |
| Format | CSV, XLS, JSON (API) |
| API | ✅ Free key at data.gov.in/user/register |
| Licence | GODL (Government Open Data License — India) |
| **Status** | **B — Free download; coordinate data usually absent in police datasets** |

---

## 2. Fire Stations

### 2.1 OpenStreetMap — `amenity=fire_station`
| Delhi Coverage | ⭐⭐⭐ Moderate — main stations present; newer sub-stations missing |
| Sonipat Coverage | ⭐ Very Low — likely 1–2 entries only |
| **Status** | **A — Usable initial layer; supplement with official directory** |

Sample query (Delhi):
```
[out:json][timeout:60];
(
  node["amenity"="fire_station"](28.40,76.83,28.88,77.35);
  way["amenity"="fire_station"](28.40,76.83,28.88,77.35);
);
out body; >; out skel qt;
```

---

### 2.2 Delhi Fire Services
| Field | Value |
|---|---|
| Official URL | https://www.delhi.gov.in/departments/delhi-fire-service |
| Data | Station name, address, phone, coverage area — web UI |
| API | ❌ None |
| **Status** | **B — Contact for structured data** |

---

### 2.3 Haryana Fire Services (Sonipat)
| **Status** | **E — No structured public dataset found; contact Haryana ULB/Emergency Services directly** |

---

## 3. Hospitals and Emergency Facilities

### 3.1 National Hospital Directory — data.gov.in / NHFR
| Field | Value |
|---|---|
| Provider | NIHFW / MoHFW |
| Dataset | "National Hospital Directory with Geo Code and additional parameters" |
| Official URL | https://data.gov.in + https://nhfr.nhp.gov.in |
| Fields | Facility name, type (PHC/CHC/DH/private), lat/lon, district, state, bed capacity, services |
| Geographic Coverage | National — Delhi + Haryana (Sonipat) included |
| Update Frequency | Monthly (claimed) |
| API | ✅ `https://api.data.gov.in/resource/{resource_id}?api_key=KEY&format=json` |
| Licence | GODL — commercial and non-commercial use permitted |
| **Status** | **A — Best available geocoded facility directory; free API key** |

---

### 3.2 OpenStreetMap — `amenity=hospital` / `amenity=clinic`
| Delhi Coverage | ⭐⭐⭐⭐ High — large public + private hospitals well-tagged |
| Sonipat Coverage | ⭐⭐⭐ Moderate — city-centre facilities mapped; PHCs patchy |
| **Status** | **A — Good initial discovery layer; supplement with NHFR** |

---

## 4. Emergency Services

### 4.1 ERSS 112 System
| Field | Value |
|---|---|
| Provider | Ministry of Home Affairs / NIC |
| Official URL | https://erss.nic.in |
| Description | Unified emergency number integrating Police (100), Fire (101), Ambulance (108), Women (1090) |
| Public API | ❌ None documented |
| Integration | Formal MoU with State Police/Home Dept + NIC/C-DAC authorization required |
| **Status** | **F — No public dataset or API; document 112 as emergency contact only** |

**Emergency numbers (Delhi & Sonipat):**
| Service | Number |
|---|---|
| Universal Emergency (ERSS) | 112 |
| Police | 100 |
| Fire | 101 |
| Ambulance (National) | 108 |
| Ambulance (Delhi CATS) | 102 |
| Women Helpline | 1090 |
| Senior Citizen | 1291 |
| Disaster Management | 1070 |
| Cyber Crime | 1930 |

---

## 5. PCR Vehicles / Live Police Patrols

### 5.1 Delhi Police PCR Live Data
| Public API | ❌ None — internal dispatch system only |
| Integration Path | Written authorization from Delhi Police Commissioner |
| **Status** | **C — Not publicly available** |

> ⚠️ Never show simulated vehicle positions as live. Implement `PCRVehicleProvider` interface; label all demo data as `SIMULATED — NOT LIVE DATA`.

---

## 6. Community Safety Incidents

### 6.1 SafeSphere Internal Incident Reports
| Source | SafeSphere AI — user-submitted community reports |
| API | Own FastAPI endpoint (see architecture doc) |
| Fields | incident_type, lat/lon, timestamp, description, anonymous reporter ID, verification_status |
| Moderation | Required; duplicate detection; abuse prevention |
| **Status** | **A — Build own system** |

> ⚠️ Community reports stored in SafeSphere MUST NOT be represented as official police complaints or FIRs.

### 6.2 Digital Police Portal — FIR Data
| Official URL | https://digitalpolice.gov.in |
| Available | FIR status (case number lookup only); no bulk export |
| Public API | ❌ None |
| **Status** | **F — Not available as bulk dataset** |

---

## 7. Historical Crime Statistics

### 7.1 NCRB — Crime in India Annual Report
| Field | Value |
|---|---|
| Official URL | https://ncrb.gov.in |
| Latest Report | Crime in India 2023 (released October 2025) |
| Fields | Crime category (IPC/BNS sections), state, district, registered cases, charge-sheeted, convicted |
| Delhi Coverage | ✅ Full metropolitan city tables |
| Sonipat Coverage | ⚠️ State-level (Haryana) only; district-level requires Haryana SCRB or RTI |
| Temporal Detail | Annual aggregates only — NO hourly/daily breakdown |
| Format | PDF + Excel/CSV tables |
| Downloadable | ✅ Free |
| **Status** | **D — Historical annual aggregate; suitable for context, NOT hotspot geocoding** |

> ⚠️ NCRB statistics cover reported crimes only. Aggregate counts cannot be converted to precise incident locations. IPC→BNS transition from 2024 creates continuity issues.

---

### 7.2 data.gov.in Crime Datasets
| Coverage | State/district crime stats, women safety stats, road accident data |
| Format | CSV/XLS; no real-time API |
| **Status** | **D — Annual aggregate; same limitations as NCRB** |

---

## 8. Roads and Pedestrian Infrastructure

### 8.1 OpenStreetMap Road Network
| Field | Value |
|---|---|
| Source | Geofabrik: https://download.geofabrik.de/asia/india.html |
| Fields | highway, name, lanes, surface, maxspeed, lit, sidewalk, oneway |
| Delhi Road Coverage | ⭐⭐⭐⭐⭐ Excellent |
| Sonipat Major Roads | ⭐⭐⭐⭐ Good (NH44, state highways) |
| Sonipat Local/Rural | ⭐⭐ Sparse |
| `lit` tag coverage | ⚠️ Very sparse — major arterials only; absence ≠ unlit |
| Licence | ODbL |
| **Status** | **A — Best available open source** |

### 8.2 Delhi OTD GTFS — Transit
| Field | Value |
|---|---|
| Official URL | https://otd.delhi.gov.in |
| Datasets | DTC bus GTFS (static), DMRC metro GTFS (static), DTC GTFS-RT (real-time) |
| Mobility Database ID | mdb-1262 |
| Static Access | ✅ Free direct download |
| RT Access | Free API key via registration |
| Haryana/Sonipat GTFS | ❌ Not available |
| **Status** | **A — Static download available immediately** |

### 8.3 MoRTH Road Accident Data
| URL | https://morth.nic.in + https://data.gov.in |
| Coverage | State-level: Delhi + Haryana |
| Format | CSV, PDF (annual) |
| Geocoded crash locations (iRAD) | ❌ Restricted to govt stakeholders |
| **Status** | **D — Annual aggregate; no public crash geocoordinates** |

---

## 9. Geospatial Boundaries

### 9.1 OSM Administrative Boundaries (RECOMMENDED for production)
| Tags | `boundary=administrative`, `admin_level=5` (district), `admin_level=6` (tehsil) |
| Licence | ODbL — **commercially usable with attribution** |
| **Status** | **A** |

Query (Delhi district boundaries):
```
[out:json][timeout:90];
relation["boundary"="administrative"]["admin_level"="5"](28.40,76.83,28.88,77.35);
out body; >; out skel qt;
```

### 9.2 GADM
| URL | https://gadm.org |
| Levels | L1 (state), L2 (district), L3 (tehsil) |
| Format | GeoPackage, Shapefile, GeoJSON; WGS84 |
| Licence | ⚠️ Free for academic/non-commercial; NOT for commercial redistribution |
| **Status** | **B — Development only; switch to OSM for production** |

### 9.3 ISRO Bhuvan
| Field | Value |
|---|---|
| Official URL | https://bhuvan.nrsc.gov.in |
| WMS Endpoint | `https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms` |
| WMTS Endpoint | `https://bhuvan-vec2.nrsc.gov.in/bhuvan/gwc/service/wmts` |
| Data | Admin boundaries, LULC, CartoDEM elevation, disaster layers |
| WMS streaming | ✅ Free, no registration |
| Data download | Free registration required |
| Licence | NRSC Open Data — free non-commercial; MoU for commercial |
| **Status** | **A — WMS streaming immediately usable; download needs registration** |

---

## 10. Weather and Contextual Data

### 10.1 Open-Meteo (Primary — Recommended)
| Field | Value |
|---|---|
| URL | https://api.open-meteo.com/v1/forecast |
| AQI URL | https://air-quality-api.open-meteo.com/v1/air-quality |
| Historical | https://archive-api.open-meteo.com/v1/archive (back to 1940) |
| Fields | temperature_2m, rain, wind_speed, uv_index, pm2_5, pm10, us_aqi, no2, so2 |
| API Key | ❌ Not required (free tier) |
| Free Limit | 10,000 calls/day |
| Licence | CC BY 4.0 — attribute: "Weather data by Open-Meteo.com" |
| Commercial | $29/month (Standard) |
| **Status** | **A — Best free weather stack for development; upgrade for commercial** |

Delhi example: `https://api.open-meteo.com/v1/forecast?latitude=28.6139&longitude=77.2090&hourly=temperature_2m,rain,wind_speed_10m,uv_index&timezone=auto`

### 10.2 IMD API (Official India Alerts)
| Field | Value |
|---|---|
| URL | https://api.imd.gov.in |
| Fields | District color-coded warnings (Green/Yellow/Orange/Red), nowcast, fog, heat wave alerts |
| Coverage | Delhi + Sonipat (Haryana subdivision) — both covered |
| API Key | ✅ Free registration |
| **Status** | **B — Register and verify; use as official alert source** |

### 10.3 OpenWeatherMap (Backup)
| URL | https://api.openweathermap.org |
| Free Tier | 60 calls/min; 1M calls/month; 5-day forecast; AQI included |
| API Key | ✅ Required (free registration) |
| **Status** | **A — Good backup; free tier for development** |

---

## Master Summary Table

| # | Category | Best Source | Status | Immediate Action |
|---|---|---|---|---|
| 1 | Police stations | OSM + Delhi/HP official directories | A/B | Query OSM; submit RTI for official CSV |
| 2 | Fire stations | OSM + Delhi Fire Services | A/B | Query OSM; contact Delhi Fire for directory |
| 3 | Hospitals | OSM + data.gov.in NHFR | A | Register for data.gov.in API key |
| 4 | Emergency numbers | ERSS/MHA documentation | A (numbers) | Document 112 only; no live integration yet |
| 5 | PCR / live vehicles | None public | C/F | Design provider interface; label SIMULATED |
| 6 | Community incidents | Own SafeSphere system | A (build) | Build internal report system |
| 7 | Crime statistics | NCRB + data.gov.in | D | Download for contextual analysis only |
| 8 | Road network | OSM/Geofabrik + OTD GTFS | A | Download Geofabrik PBF; register for OTD key |
| 9 | Admin boundaries | OSM admin boundaries | A | Overpass query |
| 10 | Weather | Open-Meteo + IMD API | A/B | Integrate Open-Meteo; register IMD |
| 11 | AQI | Open-Meteo + CPCB (web) | A/D | Open-Meteo CAMS data; CPCB has no public API |
| 12 | Street lighting | OSM lit= tag (proxy) | D | Use as positive signal only; gaps expected |
