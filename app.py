"""
Kisan Alert — Smart Water, Crop & Advisory System
Core flow: photo + voice crop diagnosis, spoken advisory in Indic languages,
with automatic escalation to Rythu Seva Kendra for uncertain/severe cases.
Also includes a weather-based dry-spell irrigation advisory.


"""

import streamlit as st
from src.diagnosis import diagnose_crop
from src.voice import build_spoken_advisory, transcribe_and_translate, LANGUAGES
from src.logging_store import log_case, get_flagged_cases
from src.weather import geocode_village, get_dry_spell_advisory

st.set_page_config(page_title="Kisan Alert", page_icon="🌾", layout="centered")

st.title("Kisan Alert")
st.caption("Smart Water, Crop & Advisory System — crop health diagnosis for small and marginal farmers")

tab_diagnose, tab_weather, tab_rsk = st.tabs(
    ["Farmer: get a diagnosis", "Weather & irrigation advisory", "RSK: flagged cases"]
)

with tab_diagnose:
    st.subheader("Upload a photo of the affected crop")

    col1, col2 = st.columns(2)
    with col1:
        farmer_name = st.text_input("Farmer name")
    with col2:
        village = st.text_input("Village")

    language = st.selectbox("Language", LANGUAGES, index=0)
    crop_hint = st.text_input("Crop (optional, improves accuracy)", placeholder="e.g. cotton, paddy, chilli")

    photo = st.file_uploader("Crop photo", type=["jpg", "jpeg", "png"])

    st.write("Describe the problem — speak into your microphone or type:")
    input_mode = st.radio("Input method", ["Speak", "Type"], horizontal=True, label_visibility="collapsed")

    description = ""
    if input_mode == "Speak":
        st.caption(f"Tap the microphone and speak in {language}")
        voice_recording = st.audio_input("Record your voice note", key="voice_recording")
        if voice_recording is not None:
            with st.spinner("Understanding your voice note..."):
                try:
                    audio_bytes = voice_recording.getvalue()
                    mime_type = voice_recording.type or "audio/wav"
                    description = transcribe_and_translate(audio_bytes, mime_type, language)
                    if description:
                        st.success(f"Understood: \"{description}\"")
                    else:
                        st.warning("Could not understand that clearly — try again or switch to typing.")
                except Exception as e:
                    st.caption(f"(Voice understanding failed: {e}. Try typing instead.)")
    else:
        description = st.text_area("Type the problem description", placeholder="e.g. yellow spots on leaves, spreading fast")

    if st.button("Get diagnosis", type="primary", disabled=not (photo and description)):
        with st.spinner("Analyzing photo..."):
            image_bytes = photo.read()
            try:
                diagnosis = diagnose_crop(image_bytes, description, crop_hint or "unknown")
            except Exception as e:
                error_text = str(e)
                if "ResourceExhausted" in error_text or "429" in error_text:
                    st.error(
                        "Our diagnosis service is briefly at capacity (free-tier rate limit). "
                        "Please wait a minute and try again."
                    )
                else:
                    st.error(
                        "Something went wrong while analyzing this photo. Please try again "
                        "or contact your local Rythu Seva Kendra directly."
                    )
                st.stop()

        st.image(image_bytes, caption="Submitted photo", width=300)
        st.markdown(f"**Likely issue:** {diagnosis['likely_issue']} ({diagnosis['confidence']} confidence)")
        st.write(diagnosis["explanation"])
        st.info(f"**Recommended action:** {diagnosis['immediate_action']}")

        if diagnosis.get("needs_expert_review"):
            st.warning("This case has been flagged for review by your local Rythu Seva Kendra.")

        with st.spinner(f"Preparing spoken advisory in {language}..."):
            try:
                translated_text, audio_bytes_out = build_spoken_advisory(diagnosis, language)
                st.audio(audio_bytes_out, format="audio/wav")
                st.caption(translated_text)
            except Exception as e:
                st.caption(f"(Voice output unavailable: {e})")

        try:
            case_id = log_case(farmer_name or "unknown", village or "unknown", language, diagnosis)
            st.success(f"Case logged: {case_id}")
        except Exception as e:
            st.caption(f"(Logging unavailable: {e})")

with tab_weather:
    st.subheader("Dry-spell & irrigation advisory")
    st.caption("Free 7-day rainfall forecast — no API key needed (powered by Open-Meteo)")

    weather_village = st.text_input(
        "Village / town name",
        value=village if "village" in dir() and village else "",
        key="weather_village",
        placeholder="e.g. Anantapur",
    )

    if st.button("Check forecast", type="primary", disabled=not weather_village):
        with st.spinner("Looking up location..."):
            try:
                location = geocode_village(weather_village)
            except Exception as e:
                st.error(f"Could not reach the weather service: {e}")
                location = None

        if location is None:
            st.warning("Could not find that village. Try a nearby larger town name instead.")
        else:
            st.caption(f"Using forecast location: {location['name']}")
            with st.spinner("Fetching 7-day rainfall forecast..."):
                try:
                    advisory = get_dry_spell_advisory(location["latitude"], location["longitude"])
                except Exception as e:
                    st.error(f"Could not fetch forecast: {e}")
                    advisory = None

            if advisory:
                if advisory["is_dry_spell"]:
                    st.warning(advisory["message"])
                else:
                    st.success(advisory["message"])

                st.write("Daily forecast (rainfall in mm):")
                st.bar_chart(
                    {d["date"][5:]: d["rain_mm"] for d in advisory["daily_forecast"]}
                )

with tab_rsk:
    st.subheader("Cases flagged for expert follow-up")
    st.caption("In a pilot deployment, this view would be used by Rythu Seva Kendra staff.")

    if st.button("Refresh"):
        st.rerun()

    try:
        cases = get_flagged_cases()
        if not cases:
            st.write("No flagged cases yet.")
        for case in cases:
            with st.expander(f"{case['farmer_name']} — {case['village']} ({case['case_id']})"):
                st.write(f"Language: {case['language']}")
                st.write(f"Likely issue: {case['diagnosis']['likely_issue']}")
                st.write(f"Explanation: {case['diagnosis']['explanation']}")
                st.write(f"Logged at: {case['created_at']}")
    except Exception as e:
        st.caption(f"(Firestore not connected yet: {e})")
