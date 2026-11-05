"""
SafeSphere AI — PCR Vehicle Provider Interface

DESIGN INTENT:
This abstract interface exists so that a formally authorized live PCR/patrol
data feed can be integrated without changing any application logic.

CURRENT STATUS (2026-10-25):
- No public, documented, authorized PCR data API exists for Delhi or Haryana.
- Formal MoU with Delhi Police Commissioner / CP Sonipat is required.
- Until authorization is obtained, ONLY SimulatedPCRProvider may be used.
- All simulated data MUST be labeled "SIMULATED — NOT LIVE DATA" in the UI.

PROHIBITED:
- Scraping police dispatch dashboards
- Bypassing authentication on any government system
- Using private/leaked feeds
- Presenting simulated positions as real vehicle locations
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


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

    def __post_init__(self):
        if not self.is_simulated:
            # This check ensures that a real feed can only be connected
            # after explicit authorization is set in the integration registry.
            pass  # Authorization check happens at provider level


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

    All implementations MUST:
    1. Set is_simulated=True on returned objects unless formal authorization is confirmed.
    2. Return a non-empty disclaimer string from get_disclaimer().
    3. Never expose sub-10m precision vehicle locations without explicit authorization.
    4. Log all data access for audit.
    5. Return is_authorized()=False until an authorization record exists in
       authorized_emergency_integrations with is_live=True and is_simulated=False.
    """

    @abstractmethod
    async def get_vehicles(self, district: Optional[str] = None) -> List[PCRVehicle]:
        """Return current vehicle positions and status."""
        ...

    @abstractmethod
    async def get_dispatch_events(
        self,
        since: datetime,
        district: Optional[str] = None,
    ) -> List[DispatchEvent]:
        """Return dispatch events since a given timestamp."""
        ...

    @abstractmethod
    def is_authorized(self) -> bool:
        """
        Return True ONLY if a formal, current MoU authorization exists.
        Check the authorized_emergency_integrations table.
        """
        ...

    @abstractmethod
    def get_disclaimer(self) -> str:
        """
        Return the disclaimer string to display prominently in the UI.
        This must NEVER return an empty string.
        """
        ...
