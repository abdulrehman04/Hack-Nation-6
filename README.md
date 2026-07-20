# RealDoor - Application-Readiness Copilot

> [!IMPORTANT]
> **Live link:** https://hack-nation-6-production.up.railway.app/
>
> This commit was made only to add the live deployment link above. No application code or functionality was changed.

A renter-side copilot for affordable-housing applications. It reads a renter's
synthetic documents into a confirmed profile, explains one program's rules with
citations, flags missing documents, and builds a renter-controlled packet. It
never decides eligibility.

Challenge 03, RealPage x Hack-Nation (6th Global AI Hackathon). See
[CLAUDE.md](./CLAUDE.md) for the full requirements and rules.

## Structure

```
backend/    Python: extraction pipeline (realdoor package) + FastAPI (app.py)
frontend/   React + Vite + TypeScript: upload and confirmation UI
```

## Status

- Stage 1 (extraction): done. Text-layer and OCR reading, watermark and
  injection filtering, label-anchored field assembly. 159/159 gold fields match.
- Upload + confirmation frontend: done (confirmation gate logic pending).
- Stage 2 (rules + math) and Stage 3 (packet): not started.

## Setup

Backend needs the Tesseract OCR engine:

```bash
brew install tesseract          # macOS  (Debian: apt-get install tesseract-ocr)
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
```

Frontend needs Node:

```bash
cd frontend && npm install
```

The challenge data is vendored in `backend/data/`, so the backend runs on its
own. Point it elsewhere with `REALDOOR_DATA=/path/to/data`. The data is a
trimmed copy of the organizer's draft pack; keep the repo private until cleared.

## Run

Two terminals:

```bash
# API
cd backend && uvicorn app:app --reload --port 8000

# web
cd frontend && npm run dev        # http://localhost:5173
```

Then upload PDFs from `backend/data/documents/`.

## Backend checks

```bash
cd backend
python -m unittest discover -s tests -v   # tests
python scripts/dump_output.py             # extract all docs to out/extraction_output.json
python scripts/ocr_inspect.py <file>      # OCR any pdf or image, dump tokens
flake8 realdoor app.py scripts tests      # lint
```
