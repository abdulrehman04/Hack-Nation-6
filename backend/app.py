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
from pydantic import BaseModel  # noqa: E402

from realdoor import config  # noqa: E402
from realdoor.auth import AuthError, verify_id_token  # noqa: E402
from realdoor.extraction.assembly import LABELS, assemble  # noqa: E402
from realdoor.extraction.classify import detect_document_type  # noqa: E402
from realdoor.extraction.readers import extract_bytes, render_first_page  # noqa: E402
from realdoor.rules import answer_question, run_household  # noqa: E402
from realdoor.rules import corpus  # noqa: E402
from realdoor.storage import get_store  # noqa: E402

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


@app.post("/profiles")
def create_profile(profile: ConfirmedProfile, authorization: str | None = Header(None)) -> dict:
    """Persist a renter-confirmed profile against the signed-in user."""
    uid = _require_uid(authorization)
    if not (profile.consent and profile.consent.get("consented")):
        raise HTTPException(400, "consent is required to save")

    record = profile.model_dump()
    record["owner_uid"] = uid
    record["rule_versions"] = _rule_versions()
    record["audit"] = [*record.get("audit", []), {
        "action": "stored",
        "at": datetime.now(timezone.utc).isoformat(),
    }]
    try:
        profile_id = get_store().save(record)
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


@app.get("/api/understand/{household_id}")
def understand(household_id: str) -> dict:
    """Run the Stage 02 Phase 1 calculation engine and return the cited enriched profile."""
    try:
        return run_household(household_id)
    except KeyError:
        raise HTTPException(404, f"Unknown household_id: {household_id}")


class ChatRequest(BaseModel):
    household_id: str
    question: str
    conversation_history: list[dict[str, Any]] = []


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict:
    """Answer a grounded, safety-checked question about one household's Phase 1 profile."""
    try:
        profile = run_household(request.household_id)
    except KeyError:
        raise HTTPException(404, f"Unknown household_id: {request.household_id}")
    return answer_question(profile, request.question)
