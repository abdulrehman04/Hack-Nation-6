"""Stage 2 — cited rules and deterministic math (to build).

Takes the renter-confirmed profile and, using the frozen rule corpus and frozen
MTSP limits, shows confirmed value, threshold, formula, source, and effective
date. Math runs in real code here, never in an LLM. Abstains when a rule or
input is uncertain and never labels the renter eligible.

Planned modules:
    corpus.py     load and cite the frozen rule corpus (id -> text + source)
    calculate.py  annualize income; compare to the frozen 60% threshold
"""
