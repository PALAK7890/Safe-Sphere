# SafeSphere AI — Community Incident Reporting Policy

**Scope:** Delhi (National Capital Territory) & Sonipat (Haryana) Pilot  
**Version:** 1.0 (Phase 2)  
**Effective Date:** November 2026

---

## 1. Core Purpose and Legal Framework

SafeSphere AI is a research, mapping, and community safety intelligence platform. Its incident reporting capability is designed to capture, aggregate, and surface environmental and neighborhood safety indicators to assist citizens with situational awareness.

### ⚠️ Crucial Legal Notice: Not an Official Police Channel
1. **No Police Dispatch:** SafeSphere AI has **no connection to police dispatch systems or emergency computer-aided dispatch (CAD)**. Submitting a report to SafeSphere AI does **not** alert the police, PCR vehicles, or emergency services.
2. **Not an FIR or Legal Complaint:** A report submitted to SafeSphere AI does **not** constitute a First Information Report (FIR), Daily Diary (DD) entry, or formal complaint under the Indian Penal Code (IPC) or Bharatiya Nyaya Sanhita (BNS).
3. **Emergency Escalation:** For any ongoing crime, physical violence, medical emergency, fire, or immediate threat to life, users **must immediately dial 112** (Emergency Response Support System - ERSS).
4. **Official e-FIR Portals:** To register a formal police complaint:
   - **Delhi Police:** [delhipolice.gov.in](https://www.delhipolice.gov.in) (e-FIR for theft, lost property, cybercrime)
   - **Haryana Police (Sonipat):** [haryanapolice.gov.in](https://haryanapolice.gov.in)
   - **National Cyber Crime Reporting:** [cybercrime.gov.in](https://cybercrime.gov.in) (Helpline: 1930)
   - **Women Safety Helpline:** 1090 / 1091
   - **Senior Citizen Helpline:** 1291

---

## 2. Permitted Incident Categories

Users may report observations within the following standardized categories:

| Category | Description & Examples | Sensitive Privacy Level |
|---|---|---|
| `theft` | Pickpocketing, bicycle theft, bag snatching, vehicle break-ins | Standard |
| `harassment` | Stalking, verbal threats, intimidation | **High (Location coarsened ±100m, PII scrubbed)** |
| `eve_teasing` | Catcalling, unwelcome sexual remarks, persistent following | **High (Location coarsened ±100m, PII scrubbed)** |
| `assault` | Physical altercations, scuffles, violent encounters | **High (Immediate 112 redirect banner displayed)** |
| `road_accident` | Minor or major traffic collisions, pedestrian hit-and-runs | Standard |
| `unsafe_road` | Missing manhole covers, deep potholes, lack of dividers, construction hazards | Environmental |
| `power_outage` | Broken street lights, blacked-out public pedestrian corridors | Environmental |
| `suspicious_activity` | Open drug peddling, gang loitering in unlit transit subways | Standard |
| `drunk_driving` | Reckless or intoxicated driving observed on public thoroughfares | Standard |
| `fire` | Open trash burning, transformer spark, minor fire | Standard (Call 101) |
| `flood` | Waterlogged underpasses, urban flooding during monsoon | Environmental |
| `other` | Other civic or neighborhood public safety hazards | Standard |

---

## 3. Submission Guidelines & Quality Standards

To maintain evidence-based integrity and public utility, all submissions must comply with the following standards:

1. **First-Hand or Direct Observation:** Users should only report incidents they directly witnessed or experienced. Rumors, viral social media forwards, and speculative accusations are prohibited.
2. **Reasonable Timestamps:** Incident occurrences must have happened within the preceding **365 days** and cannot be set in the future.
3. **Bounded Coordinates:** Submissions must fall within valid geographic envelopes. Coordinates outside India bounds ($8.0^\circ\text{N}$ to $38.0^\circ\text{N}$, $68.0^\circ\text{E}$ to $98.0^\circ\text{E}$) are rejected. Submissions are tagged by pilot region (`delhi`, `sonipat`, or `other`).
4. **Structured Free-Text:** Descriptions are limited to 1,000 characters. Descriptions must describe the safety condition or hazard objectively.

---

## 4. Prohibited Content and Abuse Controls

The following content is strictly prohibited and will result in immediate rejection by moderators and potential IP hashing blocks:

- **Naming Individuals or Accusations against Named Persons:** Reports must focus on the hazard or event, not on personal vigilantism or targeted naming.
- **Exposure of Personal Identifiable Information (PII):** Phone numbers, email addresses, vehicle registration numbers, full residential door numbers, and national identity numbers (Aadhaar, PAN) are automatically redacted.
- **Hate Speech, Communal or Defamatory Remarks:** Content targeting religious, caste, ethnic, or gender groups is strictly rejected.
- **Commercial Spam or Solicitations:** Advertisements for private security guards, businesses, or legal services.
- **Prompt Injection Attacks:** Text attempting to inject instructions into downstream LLMs (e.g. `ignore previous instructions`, `system prompt:`) is detected, neutralized, and flagged for review.
- **Malicious Flooding:** Submissions are subject to a rate limit of **5 reports per 10-minute window per IP hash**.

---

## 5. Uncertainty and the "Low Count ≠ Safe" Principle

SafeSphere AI operates under strict epidemiological and geospatial public health ethics:

> [!WARNING]
> **Low Incident Counts Do Not Mean an Area is Safe.**
> An absence of reports in a specific neighborhood or street segment may simply indicate:
> 1. Low platform adoption or lack of digital access in that area.
> 2. Severe under-reporting due to fear, stigma, or lack of lighting.
> 3. Delayed moderator review queues.
> SafeSphere AI explicitly displays uncertainty disclaimers on all public layers to prevent users from acquiring a false sense of security.
