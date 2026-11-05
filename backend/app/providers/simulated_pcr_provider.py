"""
SafeSphere AI — Simulated PCR Provider (Development Only)

WARNING: This provider generates random vehicle positions for demonstration.
It MUST NEVER be used in a way that presents data as live or real.
The UI MUST show a prominent "⚠️ SIMULATED DATA — NOT LIVE" label whenever
data from this provider is displayed.

Remove or disable this provider entirely before connecting a real authorized feed.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import List, Optional

from app.providers.base_pcr_provider import (
    DispatchEvent,
    PCRVehicle,
    PCRVehicleProvider,
    VehicleStatus,
)

SIMULATED_DISCLAIMER = (
    "⚠️ SIMULATED DATA — NOT LIVE. "
    "Vehicle positions shown are randomly generated for development/demonstration only. "
    "This data does NOT represent real Delhi Police or Haryana Police vehicle locations. "
    "Do NOT use for emergency response decisions. "
    "For all emergencies, call 112 immediately."
)

# Delhi bounding box for demo positions
_DELHI_LAT_RANGE = (28.40, 28.88)
_DELHI_LON_RANGE = (76.83, 77.35)

# Sonipat bounding box for demo positions
_SONIPAT_LAT_RANGE = (28.87, 29.07)
_SONIPAT_LON_RANGE = (76.88, 77.15)


class SimulatedPCRProvider(PCRVehicleProvider):
    """
    Development-only simulated PCR provider.
    All returned PCRVehicle objects have is_simulated=True.
    """

    def is_authorized(self) -> bool:
        return False  # NEVER authorized — this is a simulation

    def get_disclaimer(self) -> str:
        return SIMULATED_DISCLAIMER

    async def get_vehicles(self, district: Optional[str] = None) -> List[PCRVehicle]:
        """Generate 5 random vehicles within Delhi bounds."""
        vehicles = []
        for i in range(5):
            lat = random.uniform(*_DELHI_LAT_RANGE)
            lon = random.uniform(*_DELHI_LON_RANGE)
            vehicles.append(
                PCRVehicle(
                    vehicle_id=f"SIM-PCR-DL-{i:03d}",
                    latitude=round(lat, 4),
                    longitude=round(lon, 4),
                    status=random.choice(list(VehicleStatus)),
                    district="Delhi (Simulated)",
                    assigned_incident_id=None,
                    last_updated=datetime.now(timezone.utc),
                    is_simulated=True,
                )
            )
        return vehicles

    async def get_dispatch_events(
        self,
        since: datetime,
        district: Optional[str] = None,
    ) -> List[DispatchEvent]:
        """No simulated dispatch events — returns empty list."""
        return []
