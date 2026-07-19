# RealDoor - Application-Readiness Copilot

A renter-side copilot for affordable-housing applications. It reads a renter's
synthetic documents into a confirmed profile, explains one program's rules with
citations, flags missing documents, and builds a renter-controlled packet. It
never decides eligibility.

Challenge 03, RealPage x Hack-Nation (6th Global AI Hackathon). See
[CLAUDE.md](./CLAUDE.md) for the full requirements and rules.

## Status

- Stage 1 (extraction): done. Text-layer and OCR reading, watermark and
  injection filtering, label-anchored field assembly. 159/159 gold fields match.
- Stage 2 (rules + math): not started.
- Stage 3 (packet): not started.

## Setup

Needs the Tesseract OCR engine:

```bash
brew install tesseract          # macOS  (Debian: apt-get install tesseract-ocr)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

The challenge data lives in `data/`, so the repo runs on its own. Point it
elsewhere with `REALDOOR_DATA=/path/to/data`. The data is a trimmed copy of the
organizer's draft pack; keep the repo private until it is cleared for release.

## Run

```bash
python -m unittest discover -s tests -v   # tests
python scripts/dump_output.py             # extract all docs to out/extraction_output.json
python scripts/dump_gold.py               # gold as pretty json in out/gold_pretty.json
python scripts/ocr_inspect.py <file>      # OCR any pdf or image, dump tokens
flake8 realdoor scripts tests             # lint
```

## Layout

```
realdoor/
  config.py       data and schema paths (override with REALDOOR_DATA)
  extraction/     Stage 1: readers (text/OCR), filters, layout, assembly, serialize
  rules/          Stage 2: cited rules + math (stub)
  packet/         Stage 3: renter-controlled packet (stub)
  safety/         refusal, consent log, deletion (stub)
data/             challenge data (documents, gold, MTSP, rules, eval)
schemas/          submission and document-gold schemas
scripts/          extraction runners and dumps
tests/            unit and gold-accuracy tests
```
