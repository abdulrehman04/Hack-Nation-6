"""FastAPI wrapper around the realdoor extraction pipeline.

One endpoint, /extract: take uploaded documents plus their types, read and
assemble each, and return typed fields with confidence and source boxes for the
confirmation UI. Files are processed in memory and never persisted.

    uvicorn backend.app:app --reload      # from the repo root
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, File, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from realdoor.extraction.assembly import LABELS, assemble  # noqa: E402
from realdoor.extraction.classify import detect_document_type  # noqa: E402
from realdoor.extraction.readers import extract_bytes, render_first_page  # noqa: E402

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
