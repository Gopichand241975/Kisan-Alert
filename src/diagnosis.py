"""
Crop health diagnosis using the free Gemini API (Google AI Studio key).
Takes a crop photo + a farmer's transcribed voice note and returns a
structured diagnosis in one multimodal call.
"""

import json
import os
import google.generativeai as genai
from PIL import Image
import io

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

_DIAGNOSIS_PROMPT = """You are an agricultural extension expert helping a small or marginal
farmer in India diagnose a crop problem from a photo and their description.

Farmer's description (in their own words, may be short or informal): "{description}"
Crop (if known): {crop_hint}

Look at the attached photo carefully. Respond ONLY with a JSON object, no markdown
fences, no extra text, in this exact shape:

{{
  "likely_issue": "short name of the disease/pest/deficiency, or 'unclear' if not identifiable",
  "confidence": "high" | "medium" | "low",
  "explanation": "1-2 plain sentences a farmer with no agricultural science background can understand",
  "immediate_action": "1-2 concrete, low-cost steps the farmer can take today",
  "needs_expert_review": true | false
}}

Set needs_expert_review to true if: confidence is low, the issue could cause major
crop loss if misdiagnosed, or the photo is unclear/ambiguous. Be conservative —
prefer to flag for human review over giving a confident-sounding wrong answer.
"""


def diagnose_crop(image_bytes: bytes, description: str, crop_hint: str = "unknown") -> dict:
    """
    Run multimodal diagnosis on a crop photo + farmer description using
    the free Gemini API (no GCP project, no billing needed).
    """
    model = genai.GenerativeModel("gemini-2.5-flash-lite")
    image = Image.open(io.BytesIO(image_bytes))
    prompt = _DIAGNOSIS_PROMPT.format(description=description, crop_hint=crop_hint)

    response = model.generate_content([prompt, image])

    raw_text = response.text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        result = {
            "likely_issue": "unclear",
            "confidence": "low",
            "explanation": "The system could not confidently analyze this photo.",
            "immediate_action": "Please share this with your local Rythu Seva Kendra.",
            "needs_expert_review": True,
        }

    return result
