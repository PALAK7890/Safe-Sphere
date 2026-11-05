# SafeSphere AI — Incident Privacy Model & DPDPA Compliance

**Scope:** Delhi (NCT) & Sonipat (Haryana) Pilot  
**Framework:** Digital Personal Data Protection Act, 2023 (DPDPA) & Geospatial Privacy by Design  
**Version:** 1.0 (Phase 2)

---

## 1. Principles of Geospatial Privacy by Design

Public safety platforms risk inadvertently creating surveillance databases or exposing victims if precise location and identity data are carelessly handled. SafeSphere AI applies five foundational privacy principles:

1. **Data Minimization:** No citizen names, phone numbers, email addresses, or national IDs are requested or stored.
2. **Location Coarsening:** Exact GPS coordinates are never exposed in public query responses.
3. **Pseudonymous Attribution:** Reporters are identified only by irreversible salted cryptographic hashes.
4. **Automated Content Redaction:** Free text passes through regex sanitizers before storage.
5. **Purpose Limitation:** Community reports are used solely for public safety intelligence and environmental hazard mapping.

---

## 2. Location Privacy: The 100m Coarsening Model

### Problem:
A report filed at an exact latitude/longitude (e.g. `28.613928, 77.209048`) could pinpoint a victim's exact house, apartment balcony, or workplace desk, exposing them to retaliation or stalking.

### Technical Solution:
- **Storage:** Stored in the PostGIS database snapped to the nearest road or intersection geometry.
- **Public Query Coarsening:**
  When returned over public endpoints (`GET /api/v1/incidents` and `GET /api/v1/incidents/nearby`), coordinates are rounded to **3 decimal places**:
  $$\text{Latitude}_{\text{coarse}} = \text{round}(\text{lat}, 3)$$
  $$\text{Longitude}_{\text{coarse}} = \text{round}(\text{lon}, 3)$$
- **Grid Resolution:**
  At Delhi's latitude ($28.6^\circ\text{N}$), $0.001^\circ$ corresponds to approximately:
  - Latitude: $\approx 111\text{ metres}$
  - Longitude: $\approx 97\text{ metres}$
- This ~100m bounding grid preserves the street/corridor context for routing without pinpointing an individual's doorstep.

---

## 3. Pseudonymization and Reporter Identity

SafeSphere AI implements strict reporter pseudonymity:

```
[Client IP Address] + [User-Agent Header] + [Secret Server Salt]
                                │
                                ▼
                       SHA-256 Hash Function
                                │
                                ▼
                     reporter_hash (64 hex characters)
```

- **Raw IP Address:** Discarded immediately after computing the hash; never written to disk or database tables.
- **`reporter_hash`:** Used solely for:
  1. Preventing rapid duplicate submissions (within 15 minutes).
  2. Moderating coordinated spam or brigading.
- **No Reverse Lookup:** Because SHA-256 is computationally irreversible and combined with a server salt, the hash cannot be converted back into an IP address or personal identity.

---

## 4. Automated PII Detection and Redaction Pipeline

Before any submitted description is written to the database or presented to moderators, it passes through `app.services.sanitizer.sanitize_text`:

1. **Indian Mobile & Landline Numbers:**
   - Patterns: `(?:\+?91[\-\s]?)?[6-9]\d{9}` and `\b0\d{2,4}[\-\s]?\d{6,8}\b`
   - Replacement: `[PHONE REDACTED]`
2. **Email Addresses:**
   - Pattern: `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b`
   - Replacement: `[EMAIL REDACTED]`
3. **National Identity Numbers (Aadhaar / PAN):**
   - Pattern: `\b\d{4}\s?\d{4}\s?\d{4}\b`
   - Replacement: `[ID REDACTED]`
4. **HTML & Script Markup:**
   - Stripped cleanly to prevent persistent cross-site scripting (XSS).

---

## 5. Protection Against Spatial Triangulation Attacks

Attackers might issue repeated spatial queries with slightly shifting radiuses to deduce the exact coordinates of an uncoarsened incident. SafeSphere AI prevents this via:

1. **Enforced Minimum Query Radius:** All `/nearby` queries enforce a minimum radius of **100 metres**. Sub-100m queries are rejected.
2. **Maximum Query Radius:** Capped at **25,000 metres (25 km)** to prevent resource exhaustion and mass database scraping.
3. **Location Snapping:** Returned coordinates are always the coarsened centroid of the 100m grid cell.
4. **Rate Limiting:** Public queries are rate-limited per IP hash to prevent automated brute-force grid scanning.

---

## 6. Retention and Automated Expiry Policy

In compliance with the DPDPA 2023 principle of storage limitation:
- **Unverified / Rejected Reports:** Retained in audit archives for **90 days**, after which they are permanently purged.
- **Approved Public Reports:** Retained for **365 days** to support seasonal and temporal analysis (e.g., monsoon waterlogging patterns), after which they are aggregated into statistical counts and the granular incident records are dropped.
- **Right to Erasure:** Users can request deletion of a report by providing their submission ID and verification proof through the designated data protection contact.
