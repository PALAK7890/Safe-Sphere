# SafeSphere AI — Privacy and Data Governance
**Scope:** Delhi (NCT) + Sonipat (Haryana) Pilot
**Last Updated:** 2026-10-25
**Applicable Law:** Digital Personal Data Protection Act 2023 (DPDPA), IT Act 2000

---

## 1. Principles

1. **Minimum necessary data** — Collect only what is required for the stated safety purpose.
2. **No PII in analytical data** — User identifiers are one-way hashed before reaching the database.
3. **Explicit purpose limitation** — Data collected for safety alerts may not be used for advertising, profiling, or third-party sharing.
4. **Transparency** — Users can see what data is collected, why, and request deletion.
5. **Accuracy over completeness** — Uncertain data is labeled uncertain; gaps are not filled with guesses.

---

## 2. Data Collected

### 2.1 From Users

| Data Element | Purpose | Stored As | Retention |
|---|---|---|---|
| Device location (GPS) | Show nearby facilities; route safety | Used in-session; NOT persistently stored | Session only |
| Incident report content | Community safety mapping | Sanitized text in `incident_reports` | 90 days (unverified); 2 years (verified) |
| Incident report location | Incident mapping | Snapped to nearest road ± 50m | Same as above |
| Alert zone (polygon) | Geofenced notifications | Geometry in `user_alert_subscriptions` | Until user deletes |
| Anonymous session token | Duplicate/abuse prevention | SHA-256 hash only | 30 days |
| IP address | Rate limiting | SHA-256 hash only; never raw | 7 days |

**NOT collected:** Name, email, phone number, Aadhaar, face/biometric data, contact list, precise home/work locations.

### 2.2 From External Sources

| Data | Source | PII Risk | Mitigation |
|---|---|---|---|
| OSM facility POIs | OpenStreetMap | Phone numbers may be publicly listed individual contacts | Only ingest facility-level contacts; flag personal numbers for removal |
| NCRB statistics | NCRB | Aggregate counts only | No individual records; safe |
| NHFR hospital data | data.gov.in | Facility contacts; no patient data | Only facility-level data |
| Weather data | Open-Meteo / IMD | No PII | Safe |
| GTFS transit data | OTD Delhi | Stop locations; no passenger data | Safe |

---

## 3. Retention Policy

| Data Category | Retention | Basis |
|---|---|---|
| Unverified incident reports | 90 days from submission | Minimum necessary for community review |
| Verified incident reports | 2 years from verification | Safety pattern analysis |
| Rejected / duplicate reports | 30 days (for abuse tracking) | Fraud prevention |
| OSM facility data | Until next nightly refresh | Operational necessity |
| Weather data | 7 days current; 5 years historical (archived separately) | Historical analysis |
| NCRB statistics | 10 years (archival, never deleted) | Public record; historical analysis |
| User alert subscriptions | Until user cancels + 30 days | User consent |
| Incident images | 90 days (unverified); 2 years (verified) | Aligned with report |
| Session hashes | 30 days | Abuse prevention |
| IP hashes | 7 days | Rate limiting only |
| Audit logs (ingestion, verification) | 5 years | Compliance |

---

## 4. Anonymization Standards

### 4.1 Incident Location Privacy
- User-submitted incident locations are **snapped to the nearest road segment** within 50 metres before storage.
- For sensitive incident types (sexual assault, stalking, domestic violence), locations are fuzzed to a **500-metre radius** from the actual reported point.
- Raw GPS coordinates submitted by users are NEVER stored — only the snapped/fuzzed geometry.

### 4.2 Incident Aggregation Rules
- Incidents are only displayed on public maps in **aggregated clusters of 5 or more**.
- Individual unverified incidents are NEVER shown to other users.
- Moderators see a fuzzed location, not the exact pin.

### 4.3 PII Scrubbing in Descriptions
All free-text incident descriptions are processed by a PII detection pipeline before storage:
- Phone numbers → `[PHONE REDACTED]`
- Names (NER detection) → `[NAME REDACTED]`
- Aadhaar / PAN patterns → `[ID REDACTED]`
- Email addresses → `[EMAIL REDACTED]`

---

## 5. Access Controls

| Role | Access Level |
|---|---|
| Public (unauthenticated) | Read: aggregated facility locations, weather, aggregate stats |
| Authenticated user | + Submit incidents, manage own alert subscriptions |
| Moderator | + View individual (fuzzed) incident reports, change verification status |
| Admin | + Full database read; data source management; user account actions |
| Ingestion service | + Write to facility/statistics/boundary tables only; no user data access |
| AI agent | + Read all approved data; no write access; no access to `reporter_hash` or `ip_hash` |

Row-level security (PostgreSQL RLS) enforces these boundaries at the database level.

---

## 6. Risk Model Governance

### 6.1 What the Risk Model IS
- A **descriptive incident-density estimate** — showing where community reports have been submitted, weighted by recency and severity.
- An evidence-based relative indicator — "more reports have been received near X than Y."

### 6.2 What the Risk Model IS NOT
- A prediction of future crime.
- A guarantee of safety or danger.
- A representation of actual crime rates (only reported community events).
- A measure of a specific person's risk.

### 6.3 Risk Score Formula (Initial Transparent Model)

```
safety_score(segment) = 1 - normalized_weighted_incident_density

weighted_density = Σ( weight(incident_i) × recency_decay(incident_i) )
                   ─────────────────────────────────────────────────────
                   normalization_constant(area)

where:
  recency_decay(i) = exp(-λ × days_since_incident)   [λ = 0.05, half-life ~14 days]

  weight(i) = severity_weight(incident_type_i) × verification_factor(i)
  
  severity_weight:
    critical = 3.0  (assault, fire with injury)
    high     = 2.0  (harassment, road accident)
    medium   = 1.0  (theft, suspicious activity)
    low      = 0.5  (unsafe road, noise)
  
  verification_factor:
    verified = 1.0
    under_review = 0.5
    unverified = 0.25
    
  Sparse-data penalty: if incident_count < 3, score → NULL (insufficient evidence)
  Display "Data insufficient" rather than green/safe.
```

### 6.4 Display Rules for Risk Zones

| Colour | Meaning | Required Label |
|---|---|---|
| 🔴 Red | Multiple verified/high-severity reports in recent period | "Elevated community reports — exercise caution. This is not a crime statistic." |
| 🟡 Yellow | Some reports; moderate evidence | "Some community reports in this area." |
| 🟢 Green | Few or no reports | "Low community report density — data may be incomplete." |
| ⬜ Grey | Insufficient data | "Insufficient data to estimate." |

**The green zone disclaimer is mandatory.** A low report count does NOT mean an area is safe — it may mean reporting is low, coverage is sparse, or nothing has happened in the collection period.

---

## 7. Prohibited Actions

The following are explicitly prohibited in SafeSphere AI:

1. ❌ Infer or display the identity of any person mentioned in an incident report.
2. ❌ Publish the precise location of victims of sexual assault, stalking, or domestic violence.
3. ❌ Treat community reports as evidence of guilt for any individual.
4. ❌ Share user data with law enforcement without a valid legal order (court order/warrant).
5. ❌ Sell, rent, or share user data with advertisers or data brokers.
6. ❌ Display live PCR vehicle positions without confirmed ERSS/police authorization.
7. ❌ Label simulated vehicle data as live under any circumstances.
8. ❌ Present NCRB aggregate statistics as geocoded incident locations.
9. ❌ Store raw IP addresses, raw GPS tracks, or any biometric data.
10. ❌ Retain incident reports beyond the stated retention period without user consent.

---

## 8. DPDPA 2023 Compliance

| Requirement | Implementation |
|---|---|
| Consent notice | Clear consent screen before first location access or incident submission |
| Purpose limitation | Data used only for stated safety features |
| Data principal rights | In-app: "Delete my data" button removes all linked user data within 72 hours |
| Data fiduciary registration | Register as Data Fiduciary with Data Protection Board when operational |
| Significant Data Fiduciary | Assess threshold when user base exceeds regulatory threshold |
| Cross-border transfer | No user data transferred outside India without consent and adequacy check |
| Security safeguards | Encryption at rest (AES-256) and in transit (TLS 1.3); access logs; penetration testing |
| Grievance officer | Designate a named Grievance Officer; publish contact in Privacy Policy |

---

## 9. Security Safeguards

- All API keys in environment variables — never in source code or git history
- `.env.example` with placeholder values only in repository
- Database credentials via secrets manager in production (AWS Secrets Manager / Vault)
- HTTPS enforced everywhere; HSTS headers
- Rate limiting on all public API endpoints (1000 req/hour per IP hash)
- Moderation queue requires separate moderator authentication (no shared credentials)
- Penetration test before public launch — minimum OWASP Top 10 audit
- Dependency scanning (Dependabot / pip-audit) on all Python packages
- No raw logs containing user content in CloudWatch / centralized logging — sanitize before export
