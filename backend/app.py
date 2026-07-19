"""FastAPI wrapper around the realdoor extraction pipeline.

One endpoint, /extract: take uploaded documents plus their types, read and
assemble each, and return typed fields with confidence and source boxes for the
confirmation UI. Files are processed in memory and never persisted.

    uvicorn backend.app:app --reload      # from the repo root
"""

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from typing import Any  # noqa: E402

from fastapi import FastAPI, File, Header, HTTPException, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from realdoor import config  # noqa: E402
from realdoor.auth import AuthError, verify_id_token  # noqa: E402
from realdoor.extraction.assembly import LABELS, assemble  # noqa: E402
from realdoor.extraction.classify import detect_document_type  # noqa: E402
from realdoor.extraction.readers import extract_bytes, render_first_page  # noqa: E402
from realdoor.rules import answer_question, build_profile, documents_from_confirmed  # noqa: E402
from realdoor.rules import corpus  # noqa: E402
from realdoor.packet import build_checklist, build_packet  # noqa: E402
from realdoor.packet import delete_session as delete_household_session  # noqa: E402
from realdoor.packet import is_session_deleted  # noqa: E402
from realdoor.storage import get_store  # noqa: E402
from realdoor.storage.base import household_id_from_documents  # noqa: E402
from realdoor.discover import AVAILABILITY_NOTICE, DATA_NOTICE, load_properties  # noqa: E402

app = FastAPI(title="RealDoor extraction API")

# Any localhost port, so the Vite dev server works whatever port it lands on.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "document_types": sorted(LABELS)}


def _serialize(assembled) -> dict:
    return {
        "document_type": assembled.document_type,
        "method": assembled.method,
        "injected_instruction": assembled.injected_instruction,
        "fields": [
            {
                "name": f.name,
                "value": f.value,
                "confidence": f.confidence,
                "source_method": f.source_method,
                "source_bbox": f.source_bbox,
                "status": f.status,
                "reason": f.reason,
            }
            for f in assembled.fields
        ],
    }


@app.post("/extract")
async def extract(files: list[UploadFile] = File(...)) -> dict:
    """Read each uploaded document, detect its type, and assemble its fields."""
    documents = []
    for upload in files:
        data = await upload.read()
        extracted = extract_bytes(data, upload.filename or "document.pdf")
        page_image, page_size = render_first_page(data)
        doc_type = detect_document_type(extracted)
        base = {
            "file_name": upload.filename,
            "page_image": page_image,
            "page_size_points": [page_size[0], page_size[1]],
        }
        if doc_type is None:
            documents.append({
                **base,
                "document_type": None,
                "detected": False,
                "method": extracted.method,
                "injected_instruction": None,
                "fields": [],
            })
            continue
        assembled = assemble(extracted, doc_type)
        documents.append({**base, "detected": True, **_serialize(assembled)})

    return {"documents": documents}


class StoredField(BaseModel):
    name: str
    value: Any = None
    confidence: float | None = None
    source_method: str | None = None
    reviewed: bool = True
    page: int | None = None
    bbox: list[float] | None = None
    bbox_units: str | None = None


class StoredDocument(BaseModel):
    document_type: str | None = None
    file_name: str | None = None
    method: str
    fields: list[StoredField]


class ConfirmedProfile(BaseModel):
    household_id: str | None = None
    household: dict[str, Any] = {}
    documents: list[StoredDocument]
    sanity_issues: list[str] = []
    consent: dict[str, Any] | None = None
    audit: list[dict[str, Any]] = []


def _rule_versions() -> dict:
    """The frozen rule set in force at save time, for later auditing."""
    with config.MTSP_CSV.open(encoding="utf-8") as f:
        mtsp_rows = list(csv.DictReader(f))
    rules = corpus.get_rules()
    return {
        "mtsp_effective_date": mtsp_rows[0]["effective_date"] if mtsp_rows else None,
        "rules": [{"rule_id": rid, "effective_date": r["effective_date"]} for rid, r in rules.items()],
        "stamped_at": datetime.now(timezone.utc).isoformat(),
    }


def _require_uid(authorization: str | None) -> str:
    """Verify the bearer token and return the caller's uid, or 401."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "sign in required")
    id_token = authorization.split(" ", 1)[1]
    try:
        return verify_id_token(id_token, config.FIREBASE_API_KEY)
    except AuthError as exc:
        raise HTTPException(401, f"authentication failed: {exc}") from None


def _owner_confirmed_profile(uid: str) -> tuple[str, list]:
    """Load the signed-in user's saved profile from storage and build pipeline documents.

    This is the single source of truth for Stage 2/3: renter corrections persisted here
    drive every downstream number. Nothing reads the frozen extraction file at request time.
    """
    store = get_store()
    summary = next((s for s in store.list_summaries() if s.get("owner_uid") == uid), None)
    if summary is None:
        raise HTTPException(404, "No saved profile for this account yet.")
    record = store.get(summary["profile_id"])
    if record is None:
        raise HTTPException(404, "No saved profile for this account yet.")
    household_id = record.get("household_id") or household_id_from_documents(record.get("documents"))
    if not household_id:
        raise HTTPException(422, "Saved profile has no household id.")
    documents = documents_from_confirmed(household_id, record.get("documents", []))
    return household_id, documents


@app.post("/profiles")
def create_profile(profile: ConfirmedProfile, authorization: str | None = Header(None)) -> dict:
    """Save a renter-confirmed profile. One profile per user: re-saving updates it."""
    uid = _require_uid(authorization)
    if not (profile.consent and profile.consent.get("consented")):
        raise HTTPException(400, "consent is required to save")

    store = get_store()
    now = datetime.now(timezone.utc).isoformat()
    record = profile.model_dump()
    record["owner_uid"] = uid
    record["rule_versions"] = _rule_versions()

    # Update in place if this user already has a profile, so edits don't duplicate.
    existing = next((s for s in store.list_summaries() if s.get("owner_uid") == uid), None)
    if existing:
        prior = store.get(existing["profile_id"]) or {}
        record["profile_id"] = existing["profile_id"]
        record["created_at"] = prior.get("created_at")
        record["updated_at"] = now
        record["audit"] = [*prior.get("audit", []), *record.get("audit", []), {"action": "edited", "at": now}]
    else:
        record["audit"] = [*record.get("audit", []), {"action": "stored", "at": now}]

    try:
        profile_id = store.save(record)
    except Exception as exc:  # storage backend failed; surface it cleanly
        raise HTTPException(502, f"Could not save profile: {exc}") from None
    return {"profile_id": profile_id, "saved": True}


@app.get("/profiles")
def list_profiles(authorization: str | None = Header(None)) -> dict:
    """List only the signed-in user's profiles."""
    uid = _require_uid(authorization)
    mine = [s for s in get_store().list_summaries() if s.get("owner_uid") == uid]
    return {"profiles": mine}


@app.get("/profiles/{profile_id}")
def read_profile(profile_id: str, authorization: str | None = Header(None)) -> dict:
    uid = _require_uid(authorization)
    record = get_store().get(profile_id)
    if record is None or record.get("owner_uid") != uid:
        raise HTTPException(404, "profile not found")
    return record


@app.delete("/profiles")
def delete_my_data(authorization: str | None = Header(None)) -> dict:
    """Delete every profile owned by the signed-in user."""
    uid = _require_uid(authorization)
    store = get_store()
    mine = [s for s in store.list_summaries() if s.get("owner_uid") == uid]
    deleted = sum(1 for s in mine if store.delete(s["profile_id"]))
    return {"deleted": deleted}


def _require_active_session(household_id: str) -> None:
    """Refuse to serve a household's data once its session has been deleted (Stage 03)."""
    if is_session_deleted(household_id):
        raise HTTPException(404, f"Session for {household_id} has been deleted")


@app.get("/api/understand/{household_id}")
def understand(household_id: str, authorization: str | None = Header(None)) -> dict:
    """Run the Stage 02 Phase 1 calculation engine over the renter's confirmed profile."""
    uid = _require_uid(authorization)
    hh_id, documents = _owner_confirmed_profile(uid)
    _require_active_session(hh_id)
    return build_profile(hh_id, documents)


class ChatRequest(BaseModel):
    household_id: str
    question: str
    conversation_history: list[dict[str, Any]] = []


@app.post("/api/chat")
def chat(request: ChatRequest, authorization: str | None = Header(None)) -> dict:
    """Answer a grounded, safety-checked question about the renter's confirmed profile."""
    uid = _require_uid(authorization)
    hh_id, documents = _owner_confirmed_profile(uid)
    _require_active_session(hh_id)
    profile = build_profile(hh_id, documents)
    return answer_question(profile, request.question)


def _serialize_document(doc) -> dict:
    return {
        "document_id": doc.document_id,
        "document_type": doc.document_type,
        "file_name": doc.file_name,
        "fields": list(doc.fields.values()),
    }


@app.get("/api/prepare/{household_id}")
def prepare(household_id: str, authorization: str | None = Header(None)) -> dict:
    """Run the Stage 03 checklist against the confirmed profile and return packet data for the UI."""
    uid = _require_uid(authorization)
    household_id, documents = _owner_confirmed_profile(uid)
    _require_active_session(household_id)
    profile = build_profile(household_id, documents)
    checklist = build_checklist(household_id, documents)["checklist"]

    return {
        "household_id": profile["household_id"],
        "person_name": profile["person_name"],
        "household_size": profile["household_size"],
        "address": profile["address"],
        "application_date": profile["application_date"],
        "annualized_income": profile["annualized_income"],
        "frozen_60_percent_threshold": profile["frozen_60_percent_threshold"],
        "comparison": profile["comparison"],
        "readiness_status": profile["readiness_status"],
        "review_reasons": profile["review_reasons"],
        "checklist": checklist,
        "documents": [_serialize_document(doc) for doc in documents],
        "citations": profile["citations"],
        "disclosure": profile["disclosure"],
    }


@app.post("/api/export/{household_id}")
def export(household_id: str, authorization: str | None = Header(None)) -> JSONResponse:
    """Assemble the final Stage 03 packet and return it as a downloadable JSON file.

    Only ever returned to the renter's own request — never sent anywhere else.
    """
    uid = _require_uid(authorization)
    household_id, documents = _owner_confirmed_profile(uid)
    _require_active_session(household_id)
    profile = build_profile(household_id, documents)
    checklist = build_checklist(household_id, documents)["checklist"]
    packet = build_packet(household_id, profile, checklist)

    return JSONResponse(
        content=packet,
        headers={"Content-Disposition": f'attachment; filename="realdoor_packet_{household_id}.json"'},
    )


@app.delete("/api/session/{household_id}")
def delete_session_endpoint(household_id: str) -> dict:
    """Delete all session data for this household. Never touches other households or frozen data."""
    return delete_household_session(household_id)


@app.get("/api/discover")
def discover() -> dict:
    """Return the full, unfiltered public LIHTC property set for renter-side browsing.

    Public HUD data only — no household data involved, so no auth. The renter filters
    client-side; the server never ranks, recommends, or claims availability.
    """
    return {
        "properties": load_properties(),
        "availability_notice": AVAILABILITY_NOTICE,
        "data_notice": DATA_NOTICE,
    }
