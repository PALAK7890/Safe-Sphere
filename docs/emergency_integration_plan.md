# SafeSphere AI — Emergency Integration Plan
**Scope:** Delhi (NCT) + Sonipat (Haryana) Pilot
**Last Updated:** 2026-10-25

---

## 1. Summary

No public, documented, authorized API exists for live emergency dispatch data in India as of 2026-10-25. All live police/PCR and ERSS-112 integrations require formal institutional authorization. This document describes:
- What is publicly usable today (emergency numbers, static data)
- What requires authorization and how to pursue it
- How to design the system so live data can be plugged in when authorization is obtained
- Rules that must NEVER be violated

---

## 2. What Is Publicly Available (No Authorization Required)

### 2.1 Emergency Phone Numbers
These are official, publicly documented, and must be prominently displayed in the SafeSphere UI.

| Service | Number | Authority |
|---|---|---|
| Universal Emergency (ERSS) | **112** | Ministry of Home Affairs |
| Police | 100 | State Police |
| Fire | 101 | State Fire Services |
| Ambulance (National) | 108 | State Health Dept / NHM |
| Ambulance (Delhi — CATS) | 102 | GNCT Delhi |
| Women Helpline | 1090 | MHA / NCW |
| Senior Citizen Helpline | 1291 | MHA |
| Disaster Management | 1070 | NDMA |
| Cyber Crime | 1930 | MHA / I4C |
| Child Helpline | 1098 | Ministry of WCD |
| Delhi Police PCR (non-emergency) | 011-23490000 | Delhi Police |
| Sonipat PCR | 0130-2222903 | Haryana Police |

**Implementation requirement:** The app must show a one-tap "Call Emergency (112)" button accessible from any screen. This is non-negotiable for a safety platform.

### 2.2 ERSS 112 Mobile App Integration
The 112 India app (iOS + Android) can be launched via deep link from SafeSphere AI to allow users to trigger emergency calls with location sharing.

- Android intent: `android.intent.action.CALL` with `tel:112`
- iOS: `tel:112` URL scheme
- In-app browser: redirect to `https://erss.nic.in` for non-emergency citizen services

### 2.3 Official Online Reporting Channels
Display these links within SafeSphere AI's incident reporting flow:

| Portal | URL | Purpose |
|---|---|---|
| Cybercrime Reporting | https://cybercrime.gov.in | Online cyber crime complaints |
| Delhi e-FIR | https://delhipolice.gov.in (eFIR section) | Vehicle theft, property theft |
| Digital Police (FIR status) | https://digitalpolice.gov.in | Check existing FIR status |
| Haryana Police Online Complaints | https://haryanapolice.gov.in | Grievances and complaints |
| Delhi Police Lost Report | https://delhipolice.gov.in | Lost property |
| Women SOS (Himmat+) | https://delhipolice.gov.in/himmat | Women safety Delhi |

---

## 3. What Requires Authorization

### 3.1 ERSS 112 — Live Dispatch API

**What it would provide:** Incident IDs, call types, timestamps, dispatch status, assigned PCR ID, response time records
**Why it's restricted:** Classified operational data; active incident details could compromise ongoing police response; data sensitivity rules under MHA

**Responsible authority:** Ministry of Home Affairs — ERSS Programme Division + State-level ERSS Director (varies by state)

**Pathway to access:**
1. Prepare a formal proposal describing SafeSphere AI's purpose, data handling, and security framework
2. Submit to **State Police Commissioner** (Delhi: Commissioner of Police, Delhi Police HQ, MSO Building, ITO) **AND** State Home Secretary (Delhi/Haryana)
3. Request forwarding to **NIC/C-DAC** (National Informatics Centre) who operate the technical backend of ERSS
4. Obtain a formal Memorandum of Understanding (MoU) covering: data scope, retention, access controls, incident handling
5. NIC/C-DAC will issue authenticated gateway credentials if approved
6. Estimated timeline: **6–18 months** for a new commercial platform

**Questions to ask the authority:**
- What data fields are available via the API (incident type, location precision, timestamps, vehicle ID)?
- Is location data available in real time or with a delay?
- Are there geographic restrictions (specific districts only)?
- What is the data retention policy for received records?
- What security certifications are required (ISO 27001? VAPT report)?
- Is there a sandbox/test environment for integration testing before production?
- What is the cost structure, if any?
- What are the grounds for revocation?

---

### 3.2 Delhi Police PCR — Live Vehicle Positions

**What it would provide:** PCR van GPS coordinates, availability status, dispatch assignment, current call type
**Why it's restricted:** Operational security — publishing live vehicle positions could aid criminal avoidance of police patrols

**Responsible authority:** Commissioner of Police, Delhi Police; Operations / PCR Division
**Contact:** Delhi Police PRO: 011-23490000; dcp-ops@delhipolice.gov.in (verify current email via website)

**Pathway:**
1. Submit formal application to Commissioner of Police, Delhi Police Headquarters, MSO Building, ITO, New Delhi
2. Application must include: company registration, purpose, technical security assessment, proposed data usage policy
3. Likely requires sign-off from Delhi Home Department (GNCT)
4. Timeline: **6–18 months**

---

### 3.3 Haryana Police PCR — Sonipat

**Responsible authority:** Commissioner of Police, Sonipat (post-commissionerate upgrade)
**Contact:** Via Haryana Police portal: https://haryanapolice.gov.in → Citizen Services → Contact Us
**Address:** Office of CP Sonipat, Police Lines, Sonipat, Haryana 131001
**Timeline:** **6–18 months** (similar pathway to Delhi)

---

### 3.4 iRAD (Integrated Road Accident Database) — Geocoded Crash Data

**What it would provide:** Geocoded crash locations, crash type, vehicle involved, injury severity, black spots
**Responsible authority:** IIT Madras — Road Bytes Group (academic operator) + Ministry of Road Transport & Highways
**Contact:** irad@iitm.ac.in; irad.parivahan.gov.in
**Pathway:** Academic partnership MoU — SafeSphere could partner with a research institution to access iRAD for research purposes
**Timeline:** **3–6 months** (academic MoU pathway)

---

## 4. Provider Interface Design

The `PCRVehicleProvider` interface allows future live integrations without changing application logic.

```python
# backend/app/providers/base_pcr_provider.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import enum

class VehicleStatus(str, enum.Enum):
    AVAILABLE = "available"
    DISPATCHED = "dispatched"
    ON_SCENE = "on_scene"
    RETURNING = "returning"
    OFF_DUTY = "off_duty"
    UNKNOWN = "unknown"

@dataclass
class PCRVehicle:
    vehicle_id: str
    latitude: float
    longitude: float
    status: VehicleStatus
    district: Optional[str]
    assigned_incident_id: Optional[str]
    last_updated: datetime
    is_simulated: bool  # MUST be True for all non-authorized feeds

@dataclass
class DispatchEvent:
    event_id: str
    vehicle_id: str
    incident_type: str
    dispatched_at: datetime
    acknowledged_at: Optional[datetime]
    arrived_at: Optional[datetime]
    incident_latitude: float
    incident_longitude: float
    is_simulated: bool

class PCRVehicleProvider(ABC):
    """
    Abstract provider interface for PCR/patrol vehicle data.

    Implementations MUST:
    - Set is_simulated=True on all returned objects unless formal authorization is confirmed.
    - Never expose exact vehicle locations with sub-10m precision unless explicitly authorized.
    - Log all data access for audit purposes.
    """

    @abstractmethod
    async def get_vehicles(self, district: Optional[str] = None) -> List[PCRVehicle]:
        """Return current vehicle positions and status."""
        ...

    @abstractmethod
    async def get_dispatch_events(
        self,
        since: datetime,
        district: Optional[str] = None
    ) -> List[DispatchEvent]:
        """Return dispatch events since a given timestamp."""
        ...

    @abstractmethod
    def is_authorized(self) -> bool:
        """Return True only if formal authorization has been confirmed."""
        ...

    @abstractmethod
    def get_disclaimer(self) -> str:
        """Return the disclaimer string to display in the UI."""
        ...
```

```python
# backend/app/providers/simulated_pcr_provider.py
"""
Simulated PCR provider for development and demonstration purposes.
MUST NEVER be used in production without clearly labeling data as simulated.
"""
from datetime import datetime, timezone
from typing import List, Optional
from .base_pcr_provider import PCRVehicleProvider, PCRVehicle, DispatchEvent, VehicleStatus
import random, uuid

DISCLAIMER = (
    "⚠️ SIMULATED DATA — NOT LIVE. "
    "Vehicle positions shown are randomly generated for demonstration only. "
    "Do NOT use for emergency response decisions. "
    "Call 112 for all emergencies."
)

class SimulatedPCRProvider(PCRVehicleProvider):
    """Development-only simulated provider. All vehicles are marked is_simulated=True."""

    def is_authorized(self) -> bool:
        return False  # Never authorized

    def get_disclaimer(self) -> str:
        return DISCLAIMER

    async def get_vehicles(self, district: Optional[str] = None) -> List[PCRVehicle]:
        # Delhi bounding box for demo
        vehicles = []
        for i in range(5):
            vehicles.append(PCRVehicle(
                vehicle_id=f"SIM-PCR-{i:03d}",
                latitude=28.40 + random.uniform(0, 0.48),
                longitude=76.83 + random.uniform(0, 0.52),
                status=random.choice(list(VehicleStatus)),
                district="Simulated",
                assigned_incident_id=None,
                last_updated=datetime.now(timezone.utc),
                is_simulated=True,
            ))
        return vehicles

    async def get_dispatch_events(self, since: datetime, district: Optional[str] = None) -> List[DispatchEvent]:
        return []  # No simulated dispatch events
```

---

## 5. Incident Reporting Rules

### 5.1 What SafeSphere CAN do
- Accept community incident reports via its own API
- Store reports internally with full moderation pipeline
- Show aggregated, anonymized incident density on maps (minimum 5 reports to display a cluster)
- Direct users to official reporting channels with pre-filled context
- Forward emergency situations to 112 via phone deep link with user consent

### 5.2 What SafeSphere MUST NOT do
- Claim or imply that a community report constitutes an official police complaint or FIR
- Forward reports to police APIs without formal authorization (none currently exist)
- Display individual unverified reports on public maps without moderation
- Store or display the exact location of victims of sensitive crimes (sexual assault, stalking)
- Promise that a report will be seen by police unless the integration is formally authorized
- Display real-time PCR vehicle positions unless ERSS/police authorization is confirmed

### 5.3 User-facing disclaimer (required in the app)
> "SafeSphere community reports are collected to help map safety patterns. They are NOT official police complaints. For emergencies, call 112. To file an FIR, visit your nearest police station or use Delhi Police's eFIR service."

---

## 6. Emergency Escalation Workflow

```
User submits incident
         │
         ▼
Is incident_type == emergency AND is_emergency == True?
         │
        YES → Show "Call 112 Now" screen immediately
         │     (Deep link to tel:112)
         │     Log escalated_to_112 = True
         │
        NO → Continue to moderation queue
              │
              ▼
        Is description flagged as high-severity by NLP?
              │
             YES → Escalate to human moderator within 15 min
              │
             NO → Standard moderation queue (4-hour SLA)
```

---

## 7. Departments to Contact (Priority Order)

| Priority | Department | Contact Point | Purpose |
|---|---|---|---|
| 1 | Delhi Police Commissioner's Office | dcp-ops@delhipolice.gov.in / 011-23490000 | PCR data MoU |
| 2 | MHA — ERSS Programme Division | mha.gov.in → Contact | ERSS 112 integration MoU |
| 3 | NIC/C-DAC ERSS Technical Team | Via MHA referral | Technical gateway credentials |
| 4 | Haryana Police — CP Sonipat | haryanapolice.gov.in → Contact | Sonipat PCR data |
| 5 | IIT Madras — Road Bytes Group | irad@iitm.ac.in | iRAD crash data access |
| 6 | NIHFW / data.gov.in | data.gov.in → Contact Us | NHFR API confirmation |
| 7 | Delhi Fire Services | delhi.gov.in → Fire Service | Official station directory |
| 8 | Haryana ULB / Emergency Services | Town & Country Planning Dept | Sonipat fire station data |
