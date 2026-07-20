"""
Soil data + crop recommendation for Kisan Alert.

Uses SoilGrids (ISRIC) for free, no-key soil properties by lat/lon, then
asks Gemini for a short crop suggestion given soil + rainfall forecast.
Mirrors the pattern used in src/weather.py (geocode -> lookup) and
src/diagnosis.py (Gemini call).
"""

import requests
import google.generativeai as genai

SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"


def get_soil_data(lat: float, lon: float) -> dict:
    """Fetch topsoil (0-5cm) properties for a location from SoilGrids.

    Returns pH, organic carbon, and sand/clay/silt fractions (g/kg).
    Raises requests.HTTPError on failure — caller should catch and
    show a calm message, same as the weather flow does.
    """
    params = {
        "lat": lat,
        "lon": lon,
        "property": ["phh2o", "soc", "sand", "clay", "silt"],
        "depth": "0-5cm",
        "value": "mean",
    }
    r = requests.get(SOILGRIDS_URL, params=params, timeout=15)
    r.raise_for_status()
    layers = r.json()["properties"]["layers"]
    values = {layer["name"]: layer["depths"][0]["values"]["mean"] for layer in layers}

    # SoilGrids returns phh2o in pH*10 (conventional scale factor)
    return {
        "ph": values["phh2o"] / 10,
        "organic_carbon": values["soc"],
        "sand": values["sand"],
        "clay": values["clay"],
        "silt": values["silt"],
    }


def recommend_crops(soil: dict, rainfall_mm: float | None, language: str) -> str:
    """Ask Gemini for 2-3 crop suggestions given soil + rainfall context.

    NOTE: assumes the same Gemini API key configuration your
    src/diagnosis.py already sets up (genai.configure(api_key=...) at
    import time or app startup). If diagnosis.py configures the client
    differently, import and reuse that instead of calling
    genai.GenerativeModel directly here.
    """
    model = genai.GenerativeModel("gemini-2.5-flash")

    rainfall_line = (
        f"7-day forecast rainfall: {rainfall_mm:.0f} mm total."
        if rainfall_mm is not None
        else "Rainfall forecast unavailable."
    )

    prompt = f"""
    You are an agricultural advisor for small and marginal farmers in India.

    Soil data (topsoil, 0-5cm):
    - pH: {soil['ph']:.1f}
    - Organic carbon: {soil['organic_carbon']} dg/kg
    - Sand: {soil['sand']} g/kg, Clay: {soil['clay']} g/kg, Silt: {soil['silt']} g/kg

    {rainfall_line}

    Suggest 2-3 crops well suited to this soil and rainfall for the
    current season. For each, give one short practical reason (1 line).
    Keep the whole answer under 100 words, written in {language},
    in plain farmer-friendly language — no jargon.
    """

    response = model.generate_content(prompt)
    return response.text.strip()
