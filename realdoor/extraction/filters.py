"""Remove watermark/boilerplate tokens and quarantine injected instructions.

Document text is untrusted input. This layer strips the pack's synthetic
watermark and fixture boilerplate, and lifts any embedded instruction into a
separate quarantine string so it can be reported but never obeyed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .readers import Token
from .layout import group_lines

# Prose lines that are fixture furniture, not applicant evidence.
_BOILERPLATE = re.compile(
    r"training fixture|names and organizations|not a real document|"
    r"generated \d{4}-\d{2}|no real person|not issued by a real employer|"
    r"declarations are claims|requires corroboration|untrusted document text",
    re.IGNORECASE,
)

# Signatures of an attempt to hijack the system through document text.
_INJECTION = re.compile(
    r"ignore (prior|previous|all) instructions|disregard .* instructions|"
    r"mark .* approved|reveal .* system prompt|you are now",
    re.IGNORECASE,
)


@dataclass
class FilterResult:
    """Clean tokens plus anything quarantined or dropped for the record."""

    clean_tokens: list[Token]
    injected_instruction: str | None
    dropped_watermark: int
    dropped_boilerplate: int


def filter_tokens(tokens: list[Token], watermark_terms: set[str]) -> FilterResult:
    """Drop watermark/boilerplate; capture (do not obey) injected instructions."""
    survivors = [t for t in tokens if t.text.strip().upper() not in watermark_terms]
    dropped_watermark = len(tokens) - len(survivors)

    clean: list[Token] = []
    injected: list[str] = []
    dropped_boilerplate = 0
    for line in group_lines(survivors):
        text = line.text
        if _INJECTION.search(text):
            injected.append(text)  # quarantined: recorded, never executed
            continue
        if _BOILERPLATE.search(text):
            dropped_boilerplate += len(line.tokens)
            continue
        clean.extend(line.tokens)

    return FilterResult(
        clean_tokens=clean,
        injected_instruction=" ".join(injected) if injected else None,
        dropped_watermark=dropped_watermark,
        dropped_boilerplate=dropped_boilerplate,
    )
