"""
SafeSphere AI — OSM Road Network Ingestion Adapter
Source: OpenStreetMap via Overpass API
Licence: ODbL 1.0 — attribution required: © OpenStreetMap contributors
Extracts pedestrian-walkable ways, lighting, sidewalks, and geometry for Delhi and Sonipat.
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration & Constants
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

WALKABLE_HIGHWAY_TYPES: List[str] = [
    "footway",
    "pedestrian",
    "path",
    "steps",
    "living_street",
    "residential",
    "tertiary",
    "secondary",
    "primary",
]


class LitStatus(str, Enum):
    YES = "yes"
    NO = "no"
    ALWAYS = "24/7"
    AUTOMATIC = "automatic"
    UNKNOWN = "unknown"


class SidewalkStatus(str, Enum):
    BOTH = "both"
    LEFT = "left"
    RIGHT = "right"
    NO = "no"
    UNKNOWN = "unknown"


@dataclass
class ParsedRoadSegment:
    osm_way_id: int
    name: Optional[str]
    highway: str
    surface: Optional[str]
    lanes: Optional[int]
    maxspeed: Optional[int]
    lit: str
    sidewalk: str
    oneway: Optional[bool]
    access: Optional[str]
    coordinates: List[Tuple[float, float]]  # (lat, lon)
    length_m: float
    district: str
    wkt: str
    initial_safety_score: float = 0.50


# ---------------------------------------------------------------------------
# Geodesic Math & Normalizers
# ---------------------------------------------------------------------------

def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate geodesic distance between two points in metres using Haversine formula."""
    r = 6371000.0  # Earth radius in metres
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def calculate_linestring_length_m(coords: List[Tuple[float, float]]) -> float:
    """Calculate cumulative length of a coordinate sequence in metres."""
    if len(coords) < 2:
        return 0.0
    total = 0.0
    for i in range(len(coords) - 1):
        total += haversine_distance_m(
            coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1]
        )
    return round(total, 2)


def coordinates_to_wkt(coords: List[Tuple[float, float]]) -> str:
    """
    Convert list of (lat, lon) tuples to WKT LINESTRING(lon lat, ...).
    Note: PostGIS and OGC standard order is (X Y) = (lon lat).
    """
    pts = [f"{lon:.7f} {lat:.7f}" for lat, lon in coords]
    return f"LINESTRING({', '.join(pts)})"


def normalize_lit(tag_value: Optional[str]) -> str:
    """Normalize OSM lit=* tag value to lit_status_enum."""
    if not tag_value:
        return LitStatus.UNKNOWN.value
    cleaned = tag_value.strip().lower()
    if cleaned in ("yes", "true", "1", "operating"):
        return LitStatus.YES.value
    if cleaned in ("no", "false", "0", "unlit", "disused"):
        return LitStatus.NO.value
    if cleaned in ("24/7", "24_7", "always"):
        return LitStatus.ALWAYS.value
    if cleaned in ("automatic", "dusk-dawn", "sunset-sunrise"):
        return LitStatus.AUTOMATIC.value
    return LitStatus.UNKNOWN.value


def normalize_sidewalk(tag_value: Optional[str], highway_tag: str) -> str:
    """Normalize OSM sidewalk=* tag or infer based on dedicated pedestrian highway."""
    if highway_tag in ("footway", "pedestrian", "path", "steps"):
        return SidewalkStatus.BOTH.value

    if not tag_value:
        return SidewalkStatus.UNKNOWN.value

    cleaned = tag_value.strip().lower()
    if cleaned in ("both", "yes", "separate"):
        return SidewalkStatus.BOTH.value
    if cleaned in ("left", "left_only"):
        return SidewalkStatus.LEFT.value
    if cleaned in ("right", "right_only"):
        return SidewalkStatus.RIGHT.value
    if cleaned in ("no", "none", "unseparated"):
        return SidewalkStatus.NO.value
    return SidewalkStatus.UNKNOWN.value


def compute_baseline_road_safety_score(
    highway: str,
    lit: str,
    sidewalk: str,
    surface: Optional[str] = None,
) -> float:
    """
    Transparent rule-based baseline safety score (0.05 to 0.95).
    Evaluates physical pedestrian infrastructure and visibility.
    """
    score = 0.50

    # Lighting contribution
    if lit in (LitStatus.YES.value, LitStatus.ALWAYS.value, LitStatus.AUTOMATIC.value):
        score += 0.22
    elif lit == LitStatus.NO.value:
        score -= 0.18
    # lit == unknown adds 0 (neutral with uncertainty flag)

    # Sidewalk & highway classification contribution
    if sidewalk == SidewalkStatus.BOTH.value:
        score += 0.18
    elif sidewalk in (SidewalkStatus.LEFT.value, SidewalkStatus.RIGHT.value):
        score += 0.10
    elif sidewalk == SidewalkStatus.NO.value:
        score -= 0.10

    if highway in ("footway", "pedestrian", "living_street"):
        score += 0.15
    elif highway == "steps":
        score += 0.05
    elif highway in ("secondary", "primary"):
        # Higher vehicle speed and traffic volume
        score -= 0.12

    # Surface quality bonus/penalty if mapped
    if surface in ("paved", "asphalt", "concrete", "paving_stones"):
        score += 0.05
    elif surface in ("unpaved", "dirt", "ground", "mud"):
        score -= 0.08

    return max(0.05, min(0.95, round(score, 2)))


# ---------------------------------------------------------------------------
# Overpass Query & Parsing
# ---------------------------------------------------------------------------

def build_road_overpass_query(
    bbox: Tuple[float, float, float, float],
    highway_types: Optional[List[str]] = None,
    timeout_sec: int = 180,
) -> str:
    """
    Constructs an Overpass QL query retrieving ways with geometries.
    Format: (south, west, north, east)
    """
    s, w, n, e = bbox
    types = highway_types or WALKABLE_HIGHWAY_TYPES
    type_regex = "^(" + "|".join(types) + ")$"
    return f"""[out:json][timeout:{timeout_sec}];
(
  way["highway"~"{type_regex}"]({s},{w},{n},{e});
);
out body geom;
"""


def parse_osm_way(
    element: Dict[str, Any], default_district: str = "Delhi"
) -> Optional[ParsedRoadSegment]:
    """Parse a single OSM way element from Overpass output with geometry."""
    if element.get("type") != "way":
        return None

    osm_id = element.get("id")
    if not osm_id:
        return None

    tags = element.get("tags", {})
    highway = tags.get("highway")
    if not highway or highway not in WALKABLE_HIGHWAY_TYPES:
        return None

    geom = element.get("geometry", [])
    if not geom or len(geom) < 2:
        return None

    coordinates: List[Tuple[float, float]] = []
    for pt in geom:
        lat = pt.get("lat")
        lon = pt.get("lon")
        if lat is None or lon is None:
            continue
        # Sanity check lat/lon ranges for India
        if not (6.0 <= lat <= 38.0 and 68.0 <= lon <= 98.0):
            continue
        coordinates.append((float(lat), float(lon)))

    if len(coordinates) < 2:
        return None

    name = tags.get("name") or tags.get("name:en")
    surface = tags.get("surface")
    access = tags.get("access")

    # Lanes
    lanes: Optional[int] = None
    raw_lanes = tags.get("lanes")
    if raw_lanes:
        try:
            lanes = int(raw_lanes.split(";")[0])
        except (ValueError, TypeError):
            pass

    # Maxspeed
    maxspeed: Optional[int] = None
    raw_speed = tags.get("maxspeed")
    if raw_speed:
        try:
            digits = "".join(ch for ch in raw_speed if ch.isdigit())
            if digits:
                maxspeed = int(digits)
        except (ValueError, TypeError):
            pass

    # Oneway
    oneway: Optional[bool] = None
    raw_oneway = tags.get("oneway")
    if raw_oneway:
        oneway = raw_oneway.strip().lower() in ("yes", "true", "1", "-1")

    lit = normalize_lit(tags.get("lit"))
    sidewalk = normalize_sidewalk(tags.get("sidewalk"), highway)
    length_m = calculate_linestring_length_m(coordinates)
    wkt = coordinates_to_wkt(coordinates)

    initial_score = compute_baseline_road_safety_score(
        highway=highway, lit=lit, sidewalk=sidewalk, surface=surface
    )

    return ParsedRoadSegment(
        osm_way_id=int(osm_id),
        name=name,
        highway=highway,
        surface=surface,
        lanes=lanes,
        maxspeed=maxspeed,
        lit=lit,
        sidewalk=sidewalk,
        oneway=oneway,
        access=access,
        coordinates=coordinates,
        length_m=length_m,
        district=default_district,
        wkt=wkt,
        initial_safety_score=initial_score,
    )


def parse_overpass_road_response(
    data: Dict[str, Any], default_district: str = "Delhi"
) -> List[ParsedRoadSegment]:
    """Parse full Overpass JSON response into list of ParsedRoadSegments with deduplication."""
    elements = data.get("elements", [])
    results: List[ParsedRoadSegment] = []
    seen_ids = set()

    for el in elements:
        parsed = parse_osm_way(el, default_district=default_district)
        if parsed and parsed.osm_way_id not in seen_ids:
            seen_ids.add(parsed.osm_way_id)
            results.append(parsed)

    return results


# ---------------------------------------------------------------------------
# Ingestion Client / Adapter
# ---------------------------------------------------------------------------

class OSMRoadAdapter:
    """Adapter for downloading and parsing road network data from Overpass API."""

    def __init__(
        self,
        base_url: str = OVERPASS_URL,
        user_agent: str = USER_AGENT,
        timeout_sec: float = 120.0,
    ) -> None:
        self.base_url = base_url
        self.user_agent = user_agent
        self.timeout_sec = timeout_sec

    async def fetch_region_roads(
        self, region_name: str, client: Optional[httpx.AsyncClient] = None
    ) -> List[ParsedRoadSegment]:
        """Fetch and parse walkable road segments for a configured pilot region."""
        if region_name not in REGIONS:
            raise ValueError(f"Unknown region '{region_name}'. Available: {list(REGIONS.keys())}")

        bbox = REGIONS[region_name]
        query = build_road_overpass_query(bbox)
        headers = {"User-Agent": self.user_agent}
        district_label = "Delhi NCT" if region_name == "delhi" else "Sonipat"

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=self.timeout_sec)
            should_close = True

        try:
            logger.info("Executing Overpass query for road network in %s...", region_name)
            response = await client.post(
                self.base_url,
                data={"data": query},
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return parse_overpass_road_response(data, default_district=district_label)
        except httpx.HTTPError as exc:
            logger.error("Failed to query Overpass for road network: %s", exc)
            return []
        finally:
            if should_close:
                await client.aclose()
