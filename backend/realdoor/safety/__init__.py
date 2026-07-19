"""Cross-cutting safety controls (stub).

The non-negotiable boundary applied across stages: refuse eligibility
decisions, resist prompt injection, log consent and rule versions (never raw
document text), and support export and deletion. Injection quarantine currently
lives in extraction/filters.py; this is where the rest will consolidate.

Planned: refusal.py, audit.py (consent log), session.py (export, deletion).
"""
