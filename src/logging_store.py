"""
Logs each diagnosed case to Firestore (Firebase Spark free plan) and
provides a query for the RSK dashboard view. Only diagnosis text is
stored — the raw photo is never persisted, since Firebase Storage now
requires a paid plan and we don't need to keep the image anyway.
"""

import datetime
import json
import uuid
from google.cloud import firestore
from google.oauth2 import service_account

_db = None


def _client():
    global _db
    if _db is None:
        try:
            import streamlit as st
            if "firebase_credentials" in st.secrets:
                # Running on Streamlit Community Cloud — build credentials
                # from the JSON pasted into Secrets.
                cred_dict = dict(st.secrets["firebase_credentials"])
                credentials = service_account.Credentials.from_service_account_info(cred_dict)
                _db = firestore.Client(credentials=credentials, project=cred_dict["project_id"])
                return _db
        except Exception:
            pass
        # Local fallback — uses GOOGLE_APPLICATION_CREDENTIALS env var
        # pointing to your Firebase service account JSON file.
        _db = firestore.Client()
    return _db


def log_case(farmer_name: str, village: str, language: str, diagnosis: dict) -> str:
    case_id = str(uuid.uuid4())[:8]
    doc = {
        "case_id": case_id,
        "farmer_name": farmer_name,
        "village": village,
        "language": language,
        "diagnosis": diagnosis,
        "needs_expert_review": diagnosis.get("needs_expert_review", False),
        "status": "pending_review" if diagnosis.get("needs_expert_review") else "resolved",
        "created_at": datetime.datetime.utcnow().isoformat(),
    }
    _client().collection("cases").document(case_id).set(doc)
    return case_id


def get_flagged_cases(limit: int = 20) -> list[dict]:
    query = (
        _client()
        .collection("cases")
        .where("needs_expert_review", "==", True)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )
    return [doc.to_dict() for doc in query.stream()]
