"""
Weather / dry-spell irrigation advisory using Open-Meteo — a genuinely free
weather API that needs no signup and no API key at all (unlike
OpenWeatherMap, which requires account creation).

Two calls:
1. Geocode the village/town name into lat/lon (Open-Meteo Geocoding API)
2. Pull a 7-day rainfall forecast for that location
Then apply a simple rule: low total rainfall over the next week -> dry-spell
alert with an irrigation nudge; otherwise, a "no urgent action" message.
"""

import requests

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Below this total forecast rainfall (mm) over 7 days, we flag a dry spell.
# This is a simple, transparent threshold — worth tuning per crop/region in
# a real pilot, but good enough to demonstrate the concept end-to-end.
DRY_SPELL_THRESHOLD_MM = 10


def geocode_village(place_name: str) -> dict | None:
    """
    Turn a village/town name into coordinates.
    Returns {"name", "latitude", "longitude"} or None if not found.
    """
    params = {"name": place_name, "count": 1, "language": "en", "format": "json"}
    response = requests.get(GEOCODE_URL, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    results = data.get("results")
    if not results:
        return None

    top = results[0]
    return {
        "name": top.get("name"),
        "latitude": top["latitude"],
        "longitude": top["longitude"],
    }


def get_dry_spell_advisory(latitude: float, longitude: float) -> dict:
    """
    Fetch a 7-day rainfall forecast and return a simple irrigation advisory.

    Returns:
        {
          "total_rainfall_mm": float,
          "is_dry_spell": bool,
          "message": str,
          "daily_forecast": [{"date": ..., "rain_mm": ...}, ...]
        }
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "precipitation_sum",
        "forecast_days": 7,
        "timezone": "auto",
    }
    response = requests.get(FORECAST_URL, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    dates = data["daily"]["time"]
    rainfall = data["daily"]["precipitation_sum"]
    total_rainfall = sum(rainfall)
    is_dry_spell = total_rainfall < DRY_SPELL_THRESHOLD_MM

    if is_dry_spell:
        message = (
            f"Dry spell expected: only {total_rainfall:.1f}mm of rain forecast "
            "over the next 7 days. Plan irrigation now rather than waiting for rain."
        )
    else:
        message = (
            f"Adequate rain expected: {total_rainfall:.1f}mm forecast over the "
            "next 7 days. Irrigation is likely not urgent, but keep monitoring soil moisture."
        )

    return {
        "total_rainfall_mm": round(total_rainfall, 1),
        "is_dry_spell": is_dry_spell,
        "message": message,
        "daily_forecast": [
            {"date": d, "rain_mm": r} for d, r in zip(dates, rainfall)
        ],
    }
