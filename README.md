# RealDoor — Application-Readiness Copilot

A renter-side copilot for affordable-housing applications. It extracts a **human-confirmed profile** from synthetic documents, explains one program's rules **with citations**, flags missing documents, and produces a **renter-controlled readiness packet** — **without ever deciding eligibility.**

Challenge 03 · RealPage × Hack-Nation (6th Global AI Hackathon). See [CLAUDE.md](./CLAUDE.md) for the full requirements and non-negotiable rules.

## Status

- ✅ **Stage 1 — Profile:** extraction (text + OCR), watermark/injection filtering, label-anchored field assembly. **159/159 gold fields, 3/3 injections quarantined.**
- ⏳ Stage 2 — Understand (cited rules + deterministic math)
- ⏳ Stage 3 — Prepare (renter-controlled packet)

## Setup

Requires the **Tesseract** OCR engine:

```bash
brew install tesseract          # macOS  (Debian: apt-get install tesseract-ocr)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

The challenge data is **vendored** in `data/` (synthetic docs, gold, frozen MTSP limits, rule corpus, eval sets), so the repo is self-contained. To point at a copy elsewhere, set `REALDOOR_DATA=/path/to/data`. Note: the data is a trimmed copy of the organizer's DRAFT pack — keep this repo private until cleared for distribution.

## Run

```bash
python -m unittest discover -s tests -v   # tests (gold accuracy + units)
python scripts/run_assembly.py            # field-accuracy report vs gold
python scripts/run_extraction.py          # extraction / source-box coverage
flake8 realdoor scripts tests             # lint
```

## Layout

The package mirrors the three-stage pipeline — extraction (incl. OCR) is only Stage 1.

```
realdoor/
├── config.py       vendored data paths (REALDOOR_DATA)
├── extraction/     Stage 1 — readers (text/OCR) → filters → assembly   [built]
├── rules/          Stage 2 — cited rules + deterministic math          [to build]
├── packet/         Stage 3 — renter-controlled packet                  [to build]
└── safety/         cross-cutting refusal / consent / deletion          [to build]
data/               vendored challenge data (documents, gold, MTSP, rules, eval)
scripts/            runnable demos / accuracy reports
tests/              unit tests + gold-accuracy integration test
CLAUDE.md           full challenge requirements + architecture
```
