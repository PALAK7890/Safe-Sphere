"""
SafeSphere AI — Weather API Router
GET /api/v1/weather/current   — current conditions (Open-Meteo)
GET /api/v1/weather/forecast  — hourly forecast
GET /api/v1/weather/alerts    — IMD district warnings
"""

from __future__ import annotations

import os
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

OPEN_METEO_BASE = os.getenv("OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1/forecast")
OPEN_METEO_AQI  = os.getenv("OPEN_METEO_AQI_URL",  "https://air-quality-api.open-meteo.com/v1/air-quality")

WEATHER_ATTRIBUTION = "Weather data by Open-Meteo.com (CC BY 4.0) — https://open-meteo.com"
WEATHER_NOTICE = (
    "AQI data is derived from Copernicus CAMS atmospheric model forecasts, "
    "not real-time ground station measurements. "
    "For authoritative Delhi AQI, check CPCB at https://app.cpcbccr.com/AQI_India/"
)


@router.get(
    "/current",
    summary="Current weather conditions",
    description=f"Returns current weather for the given coordinates via Open-Meteo. Attribution: {WEATHER_ATTRIBUTION}",
)
async def get_current_weather(
    lat: float = Query(..., ge=8.0,  le=38.0),
    lon: float = Query(..., ge=68.0, le=98.0),
):
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,rain,wind_speed_10m,weather_code,uv_index",
        "timezone": "Asia/Kolkata",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(OPEN_METEO_BASE, params=params)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Weather service unavailable")
        data = resp.json()

    return {
        "current": data.get("current", {}),
        "attribution": WEATHER_ATTRIBUTION,
        "data_notice": WEATHER_NOTICE,
    }


@router.get(
    "/forecast",
    summary="Hourly weather forecast (48h)",
    description=f"Returns 48-hour hourly forecast via Open-Meteo. Attribution: {WEATHER_ATTRIBUTION}",
)
async def get_forecast(
    lat: float = Query(..., ge=8.0,  le=38.0),
    lon: float = Query(..., ge=68.0, le=98.0),
):
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,rain,wind_speed_10m,uv_index,weather_code",
        "forecast_days": 2,
        "timezone": "Asia/Kolkata",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(OPEN_METEO_BASE, params=params)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Weather service unavailable")
        data = resp.json()

    return {
        "hourly": data.get("hourly", {}),
        "attribution": WEATHER_ATTRIBUTION,
    }


@router.get(
    "/aqi",
    summary="Air quality index (Open-Meteo CAMS)",
    description="Returns AQI and PM2.5/PM10 forecast from Copernicus CAMS via Open-Meteo.",
)
async def get_aqi(
    lat: float = Query(..., ge=8.0,  le=38.0),
    lon: float = Query(..., ge=68.0, le=98.0),
):
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "pm2_5,pm10,us_aqi,european_aqi",
        "hourly": "pm2_5,pm10,us_aqi",
        "forecast_days": 1,
        "timezone": "Asia/Kolkata",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(OPEN_METEO_AQI, params=params)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="AQI service unavailable")
        data = resp.json()

    return {
        "current_aqi": data.get("current", {}),
        "hourly_aqi": data.get("hourly", {}),
        "attribution": WEATHER_ATTRIBUTION,
        "data_notice": WEATHER_NOTICE,
    }


@router.get(
    "/alerts",
    summary="IMD district weather warnings",
    description=(
        "Returns official India Meteorological Department district-level color-coded warnings. "
        "Requires IMD API registration. Returns empty list if key not configured."
    ),
)
async def get_imd_alerts(
    district: str = Query(..., description="District name (e.g. 'Delhi', 'Sonipat')"),
    state: str    = Query(..., description="State name (e.g. 'Delhi', 'Haryana')"),
):
    imd_key = os.getenv("IMD_API_KEY")
    if not imd_key:
        return {
            "alerts": [],
            "notice": (
                "IMD API key not configured. Register at https://api.imd.gov.in "
                "and set IMD_API_KEY in your .env file."
            ),
        }

    # TODO: Replace with real IMD API call once key is obtained and endpoint verified
    # GET https://api.imd.gov.in/api/v1/districtforecast?state={state}&district={district}
    # Headers: X-API-KEY: {imd_key}, Authorization: Bearer {jwt_token}
    return {
        "alerts": [],
        "notice": "IMD integration placeholder — implement after registration and endpoint verification.",
        "imd_reference": "https://api.imd.gov.in/public/api_reference.html",
    }
