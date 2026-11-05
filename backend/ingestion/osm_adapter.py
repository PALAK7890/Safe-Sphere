"""
SafeSphere AI — OSM Facility Ingestion Adapter
Source: OpenStreetMap via Overpass API
Licence: ODbL 1.0 — attribution required: © OpenStreetMap contributors
Data Quality: Community-maintained; NOT officially verified.
All ingested records are tagged source_verified=False.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OVERPASS_URL = os.getenv("OVERPASS_API_URL", "https://overpass-api.de/api/interpreter")
USER_AGENT = os.getenv(
    "OVERPASS_USER_AGENT",
    "SafeSphere-AI/1.0 (contact@safesphere.ai) - github.com/safesphere-ai",
)
SOURCE_ID = "osm_overpass"
LICENCE = "ODbL 1.0"
ATTRIBUTION = "© OpenStreetMap contributors"

# Bounding boxes: (south, west, north, east)
REGIONS: Dict[str, Tuple[float, float, float, float]] = {
    "delhi": (28.40, 76.83, 28.88, 77.35),
    "sonipat": (28.87, 76.88, 29.07, 77.15),
}

FACILITY_TAGS = ["police", "fire_station", "hospital", "clinic", "pharmacy"]


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class FacilityType(str, Enum):
    POLICE_STATION = "police_station"
    FIRE_STATION = "fire_station"
    HOSPITAL = "hospital"
    CLINIC = "clinic"
    PHARMACY = "pharmacy"


AMENITY_TO_TYPE: Dict[str, FacilityType] = {
    "police": FacilityType.POLICE_STATION,
    "fire_station": FacilityType.FIRE_STATION,
    "hospital": FacilityType.HOSPITAL,
    "clinic": FacilityType.CLINIC,
    "pharmacy": FacilityType.PHARMACY,
}


@dataclass
class OSMFacility:
    """Parsed facility record from OpenStreetMap."""
    osm_id: int
    osm_type: str                     # "node", "way", or "relation"
    facility_type: FacilityType
    latitude: float
    longitude: float
    name: Optional[str]
    name_hi: Optional[str]
    addr_street: Optional[str]
    addr_city: Optional[str]
    addr_postcode: Optional[str]
    phone: Optional[str]
    phone_secondary: Optional[str]
    website: Optional[str]
    opening_hours_raw: Optional[str]
    source_id: str = SOURCE_ID
    source_verified: bool = False     # Always False for OSM data
    licence: str = LICENCE
    attribution: str = ATTRIBUTION
    source_fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data_quality_score: int = 0
    region: Optional[str] = None


@dataclass
class IngestionResult:
    """Summary of a single ingestion run."""
    region: str
    facility_type: str
    fetched_count: int = 0
    valid_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    errors: List[str] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_url: str = ""
    raw_data_hash: str = ""


# ---------------------------------------------------------------------------
# Overpass Query Builder
# ---------------------------------------------------------------------------

def build_overpass_query(bbox: Tuple[float, float, float, float], amenity_tags: List[str]) -> str:
    """
    Build an Overpass QL query for the given bounding box and amenity tags.
    Returns node, way, and relation elements with centroid coordinates.
    Output format: JSON with 'out center' for way/relation centroids.
    """
    south, west, north, east = bbox
    bbox_str = f"{south},{west},{north},{east}"

    tag_filter = "|".join(amenity_tags)
    query = f"""[out:json][timeout:90];
(
  node["amenity"~"{tag_filter}"]({bbox_str});
  way["amenity"~"{tag_filter}"]({bbox_str});
  relation["amenity"~"{tag_filter}"]({bbox_str});
);
out center tags;"""
    return query


# ---------------------------------------------------------------------------
# Overpass API Client
# ---------------------------------------------------------------------------

class OverpassClient:
    """
    Async HTTP client for the Overpass API with retry and rate-limit handling.

    IMPORTANT: This client must ONLY be used in scheduled batch jobs.
    It must NEVER be called per user request. Always cache results in the
    local database before serving to users.
    """

    def __init__(
        self,
        base_url: str = OVERPASS_URL,
        user_agent: str = USER_AGENT,
        timeout: int = 120,
        max_retries: int = 3,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = {
            "User-Agent": user_agent,
            "Accept": "application/json",
        }

    async def query(self, overpass_ql: str) -> Dict[str, Any]:
        """
        Execute an Overpass QL query with exponential backoff retry.
        Returns the parsed JSON response.
        Raises httpx.HTTPError on final failure.
        """
        delays = [30, 60, 120]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    logger.info(
                        "Overpass query attempt %d/%d",
                        attempt + 1,
                        self.max_retries,
                    )
                    response = await client.post(
                        self.base_url,
                        data={"data": overpass_ql},
                        headers=self.headers,
                    )

                    if response.status_code == 429:
                        delay = delays[min(attempt, len(delays) - 1)]
                        logger.warning(
                            "Overpass rate limited (429). Backing off %ds.", delay
                        )
                        await asyncio.sleep(delay)
                        continue

                    if response.status_code == 200:
                        data = response.json()
                        logger.info(
                            "Overpass query succeeded: %d elements returned.",
                            len(data.get("elements", [])),
                        )
                        return data

                    logger.error(
                        "Overpass HTTP %d: %s",
                        response.status_code,
                        response.text[:200],
                    )
                    response.raise_for_status()

                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    delay = delays[min(attempt, len(delays) - 1)]
                    logger.warning(
                        "Overpass network error on attempt %d: %s. Retrying in %ds.",
                        attempt + 1,
                        exc,
                        delay,
                    )
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(delay)
                    else:
                        raise

        raise RuntimeError("Overpass query failed after all retries.")


# ---------------------------------------------------------------------------
# Parsing and Validation
# ---------------------------------------------------------------------------

def _extract_lat_lon(element: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    """Extract lat/lon from a node, way, or relation element."""
    if element["type"] == "node":
        return element.get("lat"), element.get("lon")

    # Ways and relations: use the 'center' field (requires 'out center' in query)
    center = element.get("center")
    if center:
        return center.get("lat"), center.get("lon")

    return None, None


def _clean_phone(raw: Optional[str]) -> Optional[str]:
    """Normalize Indian phone numbers; return None if clearly invalid."""
    if not raw:
        return None
    # Strip common noise
    cleaned = raw.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if len(cleaned) < 7:
        return None
    return raw.strip()[:50]  # Keep original format, just trimmed


def _compute_quality_score(facility: OSMFacility) -> int:
    """
    Compute a 0–100 data completeness/quality score.
    name + coordinates = 40 pts (mandatory baseline)
    phone = 20 pts
    address (street or city) = 20 pts
    source_verified by official source = 20 pts
    """
    score = 0
    if facility.name and facility.latitude and facility.longitude:
        score += 40
    if facility.phone:
        score += 20
    if facility.addr_street or facility.addr_city:
        score += 20
    if facility.source_verified:
        score += 20
    return score


def parse_osm_element(element: Dict[str, Any], region: str) -> Optional[OSMFacility]:
    """
    Parse a single Overpass API element into an OSMFacility.
    Returns None if the element is invalid or missing required fields.
    """
    tags = element.get("tags", {})
    amenity = tags.get("amenity")

    if amenity not in AMENITY_TO_TYPE:
        return None

    lat, lon = _extract_lat_lon(element)
    if lat is None or lon is None:
        logger.debug(
            "Skipping OSM element %s/%s — no coordinates.",
            element["type"],
            element["id"],
        )
        return None

    # Latitude/longitude bounds sanity check for Delhi + Sonipat
    if not (8.0 <= lat <= 38.0 and 68.0 <= lon <= 98.0):
        logger.warning("Out-of-bounds coordinates for element %s: (%s, %s)", element["id"], lat, lon)
        return None

    name = tags.get("name") or tags.get("name:en")
    phone = _clean_phone(tags.get("phone") or tags.get("contact:phone"))
    phone_secondary = None
    if tags.get("phone") and tags.get("contact:phone") and tags.get("phone") != tags.get("contact:phone"):
        phone_secondary = _clean_phone(tags.get("contact:phone"))

    facility = OSMFacility(
        osm_id=element["id"],
        osm_type=element["type"],
        facility_type=AMENITY_TO_TYPE[amenity],
        latitude=lat,
        longitude=lon,
        name=name,
        name_hi=tags.get("name:hi"),
        addr_street=tags.get("addr:street"),
        addr_city=tags.get("addr:city"),
        addr_postcode=tags.get("addr:postcode"),
        phone=phone,
        phone_secondary=phone_secondary,
        website=tags.get("website") or tags.get("contact:website"),
        opening_hours_raw=tags.get("opening_hours"),
        region=region,
    )
    facility.data_quality_score = _compute_quality_score(facility)
    return facility


def parse_overpass_response(
    raw: Dict[str, Any], region: str
) -> Tuple[List[OSMFacility], List[str]]:
    """
    Parse a full Overpass API response into a list of OSMFacility objects.
    Returns (facilities, error_messages).
    """
    facilities: List[OSMFacility] = []
    errors: List[str] = []

    elements = raw.get("elements", [])
    for element in elements:
        try:
            facility = parse_osm_element(element, region)
            if facility:
                facilities.append(facility)
        except Exception as exc:  # noqa: BLE001
            msg = f"Error parsing element {element.get('id')}: {exc}"
            errors.append(msg)
            logger.warning(msg)

    return facilities, errors


# ---------------------------------------------------------------------------
# Main Adapter
# ---------------------------------------------------------------------------

class OSMFacilityAdapter:
    """
    Full ingestion adapter for OSM facility data.

    Usage:
        adapter = OSMFacilityAdapter()
        results = await adapter.ingest_all()

    The adapter returns OSMFacility objects ready for upsert into the
    emergency_facilities table. Database persistence is handled separately
    by the ingestion task to keep this class testable without a DB connection.
    """

    def __init__(
        self,
        client: Optional[OverpassClient] = None,
        regions: Optional[Dict[str, Tuple[float, float, float, float]]] = None,
        amenity_tags: Optional[List[str]] = None,
    ):
        self.client = client or OverpassClient()
        self.regions = regions or REGIONS
        self.amenity_tags = amenity_tags or FACILITY_TAGS

    async def ingest_region(self, region_name: str) -> Tuple[List[OSMFacility], IngestionResult]:
        """Fetch and parse all facilities for a single region."""
        bbox = self.regions[region_name]
        query = build_overpass_query(bbox, self.amenity_tags)

        result = IngestionResult(
            region=region_name,
            facility_type="all",
            source_url=OVERPASS_URL,
        )

        try:
            raw = await self.client.query(query)
        except Exception as exc:  # noqa: BLE001
            result.error_count += 1
            result.errors.append(f"Overpass query failed: {exc}")
            logger.error("Overpass query failed for region %s: %s", region_name, exc)
            return [], result

        # Hash raw response for provenance
        raw_str = str(raw).encode()
        result.raw_data_hash = hashlib.sha256(raw_str).hexdigest()

        facilities, errors = parse_overpass_response(raw, region_name)
        result.fetched_count = len(raw.get("elements", []))
        result.valid_count = len(facilities)
        result.skipped_count = result.fetched_count - len(facilities) - len(errors)
        result.error_count = len(errors)
        result.errors = errors

        logger.info(
            "Region %s: fetched=%d valid=%d skipped=%d errors=%d",
            region_name,
            result.fetched_count,
            result.valid_count,
            result.skipped_count,
            result.error_count,
        )
        return facilities, result

    async def ingest_all(self) -> Dict[str, Tuple[List[OSMFacility], IngestionResult]]:
        """
        Ingest all configured regions sequentially (NOT parallel — respects rate limits).
        Returns a dict mapping region_name → (facilities, result).
        """
        output: Dict[str, Tuple[List[OSMFacility], IngestionResult]] = {}

        for region_name in self.regions:
            facilities, result = await self.ingest_region(region_name)
            output[region_name] = (facilities, result)
            if len(self.regions) > 1:
                # Brief pause between regions to avoid hammering the public endpoint
                await asyncio.sleep(5)

        return output

    def deduplicate(self, facilities: List[OSMFacility]) -> List[OSMFacility]:
        """
        Remove exact OSM ID duplicates (shouldn't normally happen but guards against
        duplicate elements in Overpass response).
        Geographic near-deduplication (within 50m + similar name) is handled
        at the database level using PostGIS ST_DWithin.
        """
        seen: set[int] = set()
        deduped: List[OSMFacility] = []
        for f in facilities:
            if f.osm_id not in seen:
                seen.add(f.osm_id)
                deduped.append(f)
        return deduped
