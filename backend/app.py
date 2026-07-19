"""FastAPI wrapper around the realdoor extraction pipeline.

One endpoint, /extract: take uploaded documents plus their types, read and
assemble each, and return typed fields with confidence and source boxes for the
confirmation UI. Files are processed in memory and never persisted.

    uvicorn backend.app:app --reload      # from the repo root
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from typing import Any  # noqa: E402

from fastapi import FastAPI, File, HTTPException, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from realdoor.extraction.assembly import LABELS, assemble  # noqa: E402
from realdoor.extraction.classify import detect_document_type  # noqa: E402
from realdoor.extraction.readers import extract_bytes, render_first_page  # noqa: E402
from realdoor.packet import build_checklist, build_packet  # noqa: E402
from realdoor.packet import delete_session as delete_household_session  # noqa: E402
from realdoor.packet import is_session_deleted  # noqa: E402
from realdoor.rules import answer_question, build_profile, load_households, run_household  # noqa: E402
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
    household: dict[str, Any] = {}
    documents: list[StoredDocument]
    sanity_issues: list[str] = []


@app.post("/profiles")
def create_profile(profile: ConfirmedProfile) -> dict:
    """Persist a renter-confirmed profile and return its id."""
    profile_id = get_store().save(profile.model_dump())
    return {"profile_id": profile_id, "saved": True}


@app.get("/profiles")
def list_profiles() -> dict:
    return {"profiles": get_store().list_summaries()}


@app.get("/profiles/{profile_id}")
def read_profile(profile_id: str) -> dict:
    record = get_store().get(profile_id)
    if record is None:
        raise HTTPException(404, "profile not found")
    return record


def _require_active_session(household_id: str) -> None:
    """Refuse to serve a household's data once its session has been deleted (Stage 03)."""
    if is_session_deleted(household_id):
        raise HTTPException(404, f"Session for {household_id} has been deleted")


@app.get("/api/understand/{household_id}")
def understand(household_id: str) -> dict:
    """Run the Stage 02 Phase 1 calculation engine and return the cited enriched profile."""
    _require_active_session(household_id)
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
    _require_active_session(request.household_id)
    try:
        profile = run_household(request.household_id)
    except KeyError:
        raise HTTPException(404, f"Unknown household_id: {request.household_id}")
    return answer_question(profile, request.question)


def _load_household_documents(household_id: str) -> list:
    households = load_households()
    documents = households.get(household_id)
    if documents is None:
        raise HTTPException(404, f"Unknown household_id: {household_id}")
    return documents


def _serialize_document(doc) -> dict:
    return {
        "document_id": doc.document_id,
        "document_type": doc.document_type,
        "file_name": doc.file_name,
        "fields": list(doc.fields.values()),
    }


@app.get("/api/prepare/{household_id}")
def prepare(household_id: str) -> dict:
    """Run the Stage 03 checklist against the confirmed profile and return packet data for the UI."""
    _require_active_session(household_id)
    documents = _load_household_documents(household_id)
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
def export(household_id: str) -> JSONResponse:
    """Assemble the final Stage 03 packet and return it as a downloadable JSON file.

    Only ever returned to the renter's own request — never sent anywhere else.
    """
    _require_active_session(household_id)
    documents = _load_household_documents(household_id)
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
