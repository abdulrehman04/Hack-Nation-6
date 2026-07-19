"""Drop watermark and boilerplate tokens, and set aside injected instructions.

Document text is untrusted. Any instruction hidden in a document is captured
for the record but never acted on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .readers import Token
from .layout import group_lines

# Fixture furniture: prose that is not applicant evidence.
_BOILERPLATE = re.compile(
    r"training fixture|names and organizations|not a real document|"
    r"generated \d{4}-\d{2}|no real person|not issued by a real employer|"
    r"declarations are claims|requires corroboration|untrusted document text",
    re.IGNORECASE,
)

# Attempts to hijack the system through document text.
_INJECTION = re.compile(
    r"ignore (prior|previous|all) instructions|disregard .* instructions|"
    r"mark .* approved|reveal .* system prompt|you are now",
    re.IGNORECASE,
)


@dataclass
class FilterResult:
    """Clean tokens, plus what was quarantined or dropped."""

    clean_tokens: list[Token]
    injected_instruction: str | None
    injected_tokens: list[Token]  # Kept for their location, never obeyed.
    dropped_watermark: int
    dropped_boilerplate: int


def filter_tokens(tokens: list[Token], watermark_terms: set[str]) -> FilterResult:
    """Strip watermark and boilerplate; pull out any injected instruction."""
    survivors = [t for t in tokens if t.text.strip().upper() not in watermark_terms]
    dropped_watermark = len(tokens) - len(survivors)

    clean: list[Token] = []
    injected: list[str] = []
    injected_tokens: list[Token] = []
    dropped_boilerplate = 0
    for line in group_lines(survivors):
        text = line.text
        if _INJECTION.search(text):
            injected.append(text)
            injected_tokens.extend(line.tokens)
            continue
        if _BOILERPLATE.search(text):
            dropped_boilerplate += len(line.tokens)
            continue
        clean.extend(line.tokens)

    return FilterResult(
        clean_tokens=clean,
        injected_instruction=" ".join(injected) if injected else None,
        injected_tokens=injected_tokens,
        dropped_watermark=dropped_watermark,
        dropped_boilerplate=dropped_boilerplate,
    )
