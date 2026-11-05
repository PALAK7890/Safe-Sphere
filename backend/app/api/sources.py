"""
SafeSphere AI — Data Sources Transparency API
GET /api/v1/sources  — machine-readable data source registry
"""

from __future__ import annotations

import csv
import os
from typing import List, Optional

from fastapi import APIRouter, Query

router = APIRouter()

SOURCE_REGISTRY_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "source_registry.csv"
)


@router.get(
    "",
    summary="Data source registry",
    description=(
        "Returns the machine-readable registry of all data sources used by SafeSphere AI, "
        "including licence, access type, verification status, and limitations. "
        "Transparency is a core principle of this platform."
    ),
)
async def list_sources(
    status: Optional[str] = Query(None, description="Filter by verification status (A/B/C/D/E/F)"),
):
    sources = []
    try:
        with open(SOURCE_REGISTRY_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if status and row.get("verification_status") != status:
                    continue
                sources.append(row)
    except FileNotFoundError:
        return {"sources": [], "notice": "Source registry CSV not found at expected path."}

    return {
        "sources": sources,
        "count": len(sources),
        "notice": (
            "This registry documents all external data sources integrated into SafeSphere AI, "
            "including their licences, access requirements, and known limitations."
        ),
    }
