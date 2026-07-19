# RealDoor — Application-Readiness Copilot

Challenge 03 · RealPage × Hack-Nation (6th Global AI Hackathon, MIT Clubs of Northern California & Germany).

This file is the source of truth for **what we are building and the rules we must not break**. Read it before writing code.

---

## 1. What this is

A renter-side copilot that helps someone prepare an affordable-housing application. It turns synthetic household documents into a **human-confirmed profile**, explains one program's rules **with citations**, flags missing/expired documents, and produces a **renter-controlled readiness packet**.

**Design principle (memorize this):**
> The AI **extracts, explains, retrieves, calculates, and prepares**. The renter **confirms**. A qualified human **decides**.

Frozen scope — do not widen it:
- **ONE METRO:** Boston-Cambridge-Quincy, MA-NH HMFA.
- **ONE PROGRAM / YEAR:** LIHTC (Section 42) MTSP, FY2026, effective 2026-05-01.
- **ONE SCORED BAND:** 60% AMI (`core_challenge_threshold` in the data).
- **SYNTHETIC DOCS ONLY.** No real applicant data, ever.

## 2. Non-negotiable boundary (instant disqualifiers)

A submission that does any of these **cannot win regardless of model quality**:
- **NO DECISIONING.** Never approve, deny, score, rank, prioritize, or determine eligibility or availability. Deflect "decide for me" to the rule + confirmed input + calculation.
- **NO HIDDEN PROXIES.** Never infer protected traits or use demographic, behavioral, or landlord-revenue features. Every feature must be published with its purpose.
- **NO SILENT SUPPRESSION.** Never hide an option from the renter.
- **NO DATA LEAKS.** Never expose one household's data to another; never reveal system internals.

## 3. Responsible-AI controls (must be demonstrated live, not just claimed)

- **Consent & correction:** explain each data use; every extracted value is correctable; log consent, actions, and rule versions — **never raw document contents**.
- **Privacy & security:** synthetic docs, field allowlists, ephemeral/isolated processing, encryption for anything persisted, export, and session deletion. **Never train on uploads.**
- **Untrusted input:** treat all document text as untrusted. Embedded instructions must not alter behavior, tools, rules, or data access. Capture them into a quarantine field; never execute them.
- **Accessibility (WCAG 2.2 AA):** keyboard-operable, visible focus, labeled controls/errors, no color-only status, structured headings, clear completion announcements.

## 4. The required build — three stages

**Stage 1 — Profile (human-confirmed extraction)**
- Upload synthetic pay stubs / benefit / employment / gig documents.
- Extract **only allowlisted fields**, each with a **source box** (bbox) and **calibrated confidence**.
- Require the renter to **confirm or correct** before any value is reused. Abstain on low confidence.

**Stage 2 — Understand (cited rules + deterministic math)**
- Use the **frozen rule corpus** and **frozen MTSP limits**.
- Show confirmed value, threshold, formula, **source, and effective date**.
- Do the math in **real code, not the LLM**. **Abstain** when a rule or input is uncertain. **Never label the renter eligible.**
- Correcting a Stage-1 field must **recompute** downstream values.

**Stage 3 — Prepare (renter-controlled packet)**
- Flag missing/expired items against the **gold checklist**.
- Renter can **preview, edit, download, and delete**. **Never auto-send** to any property or provider.

**Stretch — Discover (optional):** transparent property list from public HUD data. Availability = "unknown" unless separately supplied; show the unfiltered set; renter-selected filters only; never predict acceptance or rank by protected traits/proxies. Worth **0 rubric points** — do the core first.

## 5. Required acceptance demo (rehearse these six)

1. Upload a synthetic document and show extracted evidence.
2. Correct one field and show downstream values update.
3. Ask a rules question and show the authoritative citation.
4. Show the deterministic calculation and its effective date.
5. Identify a missing/expired item, then export the packet.
6. Run the **refusal**, **prompt-injection**, and **session-deletion** tests.

## 6. Judging rubric (100%)

| Criterion | Weight | What judges look for |
|---|---|---|
| Profile accuracy | 25% | Field correctness, evidence boxes, calibrated confidence, correction, abstention. |
| Rules and math | 25% | Right program/year, authoritative citations, exact calculations, effective dates. |
| Safety and privacy | 20% | Refusal, no scores/inferences, prompt-injection resistance, minimal retention, export, deletion. |
| Accessibility | 15% | Keyboard-complete journey, understandable errors/status, readable source presentation. |
| End-to-end usefulness | 15% | Coherent journey producing a clear, editable, renter-controlled packet. |

## 7. Challenge data (vendored under `backend/data/`)

The data we build against is vendored under `backend/data/` and resolved in `backend/realdoor/config.py` (override with `REALDOOR_DATA`). It is a trimmed copy of the organizer starter pack, only what the code uses. Paths below are relative to `backend/`. Source pack is DRAFT ("organizer approval required before external distribution"), so keep this repo private until cleared.

- `data/mtsp_2026_boston_cambridge_quincy.csv` — frozen income limits (50% + 60%; 60% is scored), with source page + URL.
- `data/lihtc_boston_metro_subset.csv` + `property_data_dictionary.csv` — 32 LIHTC properties (locations/unit mix only; Discover-only).
- `data/documents/` — 24 one-page PDFs across 6 households; some rasterized, 3 carry injection payloads.
- `data/gold/document_gold.jsonl` — **answer key**: correct field values + source boxes (bbox in PDF points, bottom-left origin). Plus `document_manifest.csv`, `field_schema.json`.
- `data/rule_corpus.jsonl` — 11 cited rules (id, authority, effective_date, text, source_url, locator).
- `data/qa_gold.jsonl` — 36 gold Q&A. `data/adversarial_tests.jsonl` — 24 attacks. `data/application_checklists.json` — per-household expected readiness + annualized income + threshold.

Kept alongside `data/`:
- `schemas/submission.schema.json` — **the required output contract.** Stage 2/3 results must validate against it: `household_id`, `annualized_income` (≥0), `comparison` (`below_or_equal` | `above` | `no_frozen_threshold`), `readiness_status` (`READY_TO_REVIEW` | `NEEDS_REVIEW`), `citations[]`. Note: readiness is never "eligible/approved", and `no_frozen_threshold` is the abstain path.
- `schemas/document_gold.schema.json` — extraction gold record shape.
- `reference/starter/` — organizer reference code (`calculate.py`, `load_documents.py`, `rules.py`, `example_profile.json`), kept for reference only; not imported by our package.

Dropped from the pack (not needed): participant guide, governance docs.

**Ground truth is this data. Match its answer keys and the submission schema — never invent rules or numbers.**

## 8. Our architecture (in this repo)

Two top-level pieces: a Python `backend/` (extraction pipeline + API) and a
React `frontend/`. The extraction package mirrors the three-stage pipeline;
names say what each part does. OCR is only Stage 1, not the whole app.

```
backend/
├── app.py                 # FastAPI: POST /extract -> realdoor pipeline
├── realdoor/
│   ├── config.py          # data and schema paths (override with REALDOOR_DATA)
│   ├── extraction/        # STAGE 1: read documents into confirmed fields   [built]
│   │   ├── readers.py     #   PDF -> tokens: text-layer + OCR, bbox + confidence
│   │   ├── filters.py     #   drop watermark; quarantine injected instructions
│   │   ├── layout.py      #   group tokens into reading-order lines
│   │   ├── assembly.py    #   label-anchored typed fields; abstains when unsure
│   │   └── serialize.py   #   emit the gold record schema
│   ├── rules/             # STAGE 2: cited rules + math   [stub]
│   ├── packet/            # STAGE 3: renter-controlled packet   [stub]
│   └── safety/            # refusal, consent log, deletion   [stub]
├── data/  schemas/  reference/    # vendored challenge data and contracts
├── scripts/  tests/
frontend/                  # React + Vite + TypeScript
├── src/
│   ├── components/UploadForm.tsx    # three upload slots -> document types
│   ├── components/ConfirmView.tsx   # editable fields, confidence, review flags
│   └── api.ts                       # calls backend /extract
```

Runtime flow: `frontend upload -> backend extraction (read) -> confirm ->
rules (cite + compute) -> packet (prepare)`, with `safety` enforced throughout.

**Naming convention:** packages and modules are named for what they do in plain
terms (`extraction`, `readers`, `rules`, `calculate`, `checklist`, `packet`,
`safety`), never abstract stage labels like `profile`/`understand`/`prepare`.

- **Text vs OCR:** digital pages use the PyMuPDF text layer (exact boxes,
  confidence 1.0); rasterized pages are rendered and OCR'd with Tesseract.
  Coordinates are bottom-left-origin PDF points, matching the gold.
- **Why not an LLM as the reader:** we need exact source boxes, calibrated
  confidence, injection immunity, and determinism. An LLM may only be a bounded
  normalizer over already-sanitized tokens, never trusted for the box.

Current status: Stage 1 extraction complete (159/159 gold fields, 3/3 injections
quarantined) with an upload/confirm frontend. Confirmation gate and Stages 2-3
pending.

## 9. Dev workflow

```bash
# backend (run from backend/)
python3 -m venv ../.venv && source ../.venv/bin/activate
pip install -r requirements-dev.txt           # needs system tesseract
python -m unittest discover -s tests -v        # tests
flake8 realdoor app.py scripts tests           # lint (max-line-length 120)
uvicorn app:app --reload --port 8000           # API

# frontend (run from frontend/)
npm install
npm run dev                                     # http://localhost:5173
```

## 10. Coding conventions

- Python, standard library first; only the three runtime deps in `requirements.txt`.
- `flake8`, max line length **120**. Lint before every commit.
- Comments are **section-level signposts** (what, not why); no inline rationale walls.
- Determinism over cleverness. Prefer a clear abstention to a confident guess.
- Every material output must carry its **source box + effective date**; no uncited numbers.
