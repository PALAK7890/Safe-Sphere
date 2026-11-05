"""
SafeSphere AI — FastAPI Application Entry Point
Scope: Delhi (NCT) + Sonipat (Haryana) Pilot
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.facilities import router as facilities_router
from app.api.incidents import router as incidents_router
from app.api.weather import router as weather_router
from app.api.sources import router as sources_router

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application Lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("SafeSphere AI API starting up — Delhi + Sonipat pilot scope")
    yield
    logger.info("SafeSphere AI API shutting down")


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SafeSphere AI",
    description=(
        "Location-aware public safety intelligence platform for Delhi and Sonipat.\n\n"
        "**Data Notice:** Facility data sourced from OpenStreetMap (© OpenStreetMap contributors, "
        "ODbL 1.0) and government directories. Not all records are officially verified. "
        "Always verify contact details before use in emergencies.\n\n"
        "**Emergency:** Call **112** for all emergencies in India."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # expand in production via settings
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(facilities_router, prefix="/api/v1/facilities", tags=["Facilities"])
app.include_router(incidents_router,  prefix="/api/v1/incidents",  tags=["Incidents"])
app.include_router(weather_router,    prefix="/api/v1/weather",    tags=["Weather"])
app.include_router(sources_router,    prefix="/api/v1/sources",      tags=["Data Sources"])
app.include_router(sources_router,    prefix="/api/v1/data-sources", tags=["Data Sources"])

# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "SafeSphere AI",
        "scope": "Delhi (NCT) + Sonipat (Haryana) — Pilot",
        "version": "0.1.0",
        "emergency": "Call 112 for all emergencies in India",
        "status": "running",
        "docs": "/docs",
        "attribution": "© OpenStreetMap contributors (ODbL 1.0) — https://openstreetmap.org/copyright",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
