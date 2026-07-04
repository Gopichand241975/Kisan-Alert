"""
Handles both directions of voice using only the free Gemini API:
- Voice IN: Gemini reads audio directly (no separate Speech-to-Text call)
- Voice OUT: Gemini's native TTS turns the advisory into spoken audio
- Translation: handled by asking Gemini to respond directly in the target
  language — no separate Translation API call needed.
"""

import os
import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

LANGUAGES = ["Telugu", "Hindi", "Kannada", "Tamil", "English"]

# Gemini TTS prebuilt voice names (see docs for the full list of 30 voices)
_TTS_VOICE = "Kore"


def transcribe_and_translate(audio_bytes: bytes, mime_type: str, language: str) -> str:
    """
    Send a farmer's voice note straight to Gemini and get back a clean
    English-readable transcript (Gemini reads audio natively — no
    separate STT model needed).
    """
    model = genai.GenerativeModel("gemini-2.5-flash")
    audio_part = {"mime_type": mime_type, "data": audio_bytes}
    prompt = (
        f"Transcribe this farmer's voice note, which is spoken in {language}. "
        "Return only the transcription in English, no extra commentary."
    )
    response = model.generate_content([prompt, audio_part])
    return response.text.strip()


def build_spoken_advisory(diagnosis: dict, language: str) -> tuple[str, bytes]:
    """
    Translate the diagnosis into the farmer's language and synthesize speech,
    both via the same free Gemini API key.

    Returns (translated_text, audio_bytes_wav)
    """
    text_model = genai.GenerativeModel("gemini-2.5-flash")
    english_message = f"{diagnosis['explanation']} {diagnosis['immediate_action']}"

    if language == "English":
        translated = english_message
    else:
        translate_prompt = (
            f"Translate this agricultural advisory into {language}, in simple, "
            f"everyday words a farmer would use (not formal/literary style). "
            f"Return only the translation, nothing else.\n\n{english_message}"
        )
        translated = text_model.generate_content(translate_prompt).text.strip()

    tts_model = genai.GenerativeModel("gemini-2.5-flash-preview-tts")
    tts_response = tts_model.generate_content(
        translated,
        generation_config={
            "response_modalities": ["AUDIO"],
            "speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": _TTS_VOICE}}},
        },
    )
    audio_bytes = tts_response.candidates[0].content.parts[0].inline_data.data

    return translated, audio_bytes
