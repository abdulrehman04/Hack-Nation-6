"""FastAPI wrapper around the realdoor extraction pipeline.

One endpoint, /extract: take uploaded documents plus their types, read and
assemble each, and return typed fields with confidence and source boxes for the
confirmation UI. Files are processed in memory and never persisted.

    uvicorn backend.app:app --reload      # from the repo root
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from realdoor.extraction.assembly import LABELS, assemble  # noqa: E402
from realdoor.extraction.readers import extract_bytes  # noqa: E402

app = FastAPI(title="RealDoor extraction API")

# Vite dev server origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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
                "source_bbox": f.source_bbox,
                "status": f.status,
                "reason": f.reason,
            }
            for f in assembled.fields
        ],
    }


@app.post("/extract")
async def extract(
    files: list[UploadFile] = File(...),
    document_types: list[str] = Form(...),
) -> dict:
    """Read each uploaded document and return its assembled fields."""
    if len(files) != len(document_types):
        raise HTTPException(400, "files and document_types must line up")

    documents = []
    for upload, doc_type in zip(files, document_types):
        if doc_type not in LABELS:
            raise HTTPException(400, f"unknown document_type: {doc_type}")
        data = await upload.read()
        extracted = extract_bytes(data, upload.filename or doc_type)
        assembled = assemble(extracted, doc_type)
        documents.append({"file_name": upload.filename, **_serialize(assembled)})

    return {"documents": documents}
