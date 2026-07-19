"""Cross-cutting — Safety, privacy, and consent controls (to build).

Enforces the non-negotiable boundary across every stage: refuse eligibility
decisions, resist prompt injection, log consent and rule versions (never raw
document contents), and support export and session deletion.

Injection quarantine already lives in profile.filters; this package is where
the refusal policy, consent/action log, and deletion routines will consolidate.

Planned modules:
    refusal.py    deflect 'decide for me' to rule + confirmed input + math
    audit.py      consent, actions, rule versions (no raw document contents)
    session.py    ephemeral storage, export, and hard deletion
"""
