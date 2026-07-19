"""Turn located tokens into typed, cited profile fields.

Each value is read by finding its printed label and taking the column beneath,
so every field keeps a source box and a confidence. When a value is missing or
can't be parsed, the field abstains instead of guessing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .readers import ExtractedDocument, Token
from .filters import filter_tokens
from .layout import Line, group_lines

# Per document type: (field_name, printed_label, value_type).
LABELS: dict[str, list[tuple[str, str, str]]] = {
    "application_summary": [
        ("person_name", "APPLICANT", "name"),
        ("household_size", "HOUSEHOLD SIZE", "int"),
        ("address", "MAILING ADDRESS", "text"),
        ("application_date", "APPLICATION DATE", "date"),
    ],
    "pay_stub": [
        ("person_name", "EMPLOYEE", "name"),
        ("pay_date", "PAY DATE", "date"),
        ("pay_period_start", "PAY PERIOD", "date"),
        ("pay_period_end", "THROUGH", "date"),
        ("pay_frequency", "PAY FREQUENCY", "frequency"),
        ("regular_hours", "REGULAR HOURS", "int"),
        ("hourly_rate", "HOURLY RATE", "money_float"),
        ("gross_pay", "GROSS PAY", "money_float"),
        ("net_pay", "NET PAY", "money_float"),
    ],
    "employment_letter": [
        ("person_name", "EMPLOYEE", "name"),
        ("document_date", "LETTER DATE", "date"),
        ("weekly_hours", "HOURS PER WEEK", "int"),
        ("hourly_rate", "HOURLY RATE", "money_float"),
    ],
    "benefit_letter": [
        ("person_name", "RECIPIENT", "name"),
        ("document_date", "LETTER DATE", "date"),
        ("monthly_benefit", "MONTHLY AMOUNT", "money_int"),
        ("benefit_frequency", "FREQUENCY", "frequency"),
    ],
    "gig_statement": [
        ("person_name", "WORKER", "name"),
        ("statement_month", "STATEMENT MONTH", "month"),
        ("gross_receipts", "GROSS RECEIPTS", "money_int"),
        ("platform_fees", "PLATFORM FEES", "money_float"),
    ],
}

_MAX_LABEL_TO_VALUE_GAP = 35.0
_COLUMN_PAD_LEFT = 6.0
_COLUMN_PAD_RIGHT = 3.0


@dataclass
class Field:
    """One assembled field with provenance, or an abstention."""

    name: str
    value: object | None
    confidence: float
    source_bbox: tuple[float, float, float, float] | None
    source_method: str | None
    status: str  # "extracted" | "abstained" | "quarantined"
    reason: str | None = None


@dataclass
class AssembledDocument:
    document_type: str
    method: str
    fields: list[Field]
    injected_instruction: str | None


# Value parsing

def _parse(value_type: str, text: str):
    text = text.strip()
    if value_type in ("name", "text"):
        return text or None
    if value_type == "int":
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else None
    if value_type in ("money_float", "money_int"):
        m = re.search(r"\d[\d,]*\.?\d*", text)
        if not m:
            return None
        number = float(m.group().replace(",", ""))
        return int(number) if value_type == "money_int" else number
    if value_type == "date":
        m = re.search(r"\d{4}-\d{2}-\d{2}", text)
        return m.group() if m else None
    if value_type == "month":
        m = re.search(r"\b\d{4}-\d{2}\b", text)
        return m.group() if m else None
    if value_type == "frequency":
        m = re.search(r"[A-Za-z]+", text)
        return m.group().lower() if m else None
    return None


# Labels and columns

def _find_label(lines: list[Line], phrase: str) -> tuple[int, float] | None:
    """Locate a label phrase; return (line index, first-token x0)."""
    words = phrase.upper().split()
    for li, line in enumerate(lines):
        toks = line.tokens
        for start in range(len(toks) - len(words) + 1):
            window = [toks[start + k].text.strip().upper() for k in range(len(words))]
            if window == words:
                return li, toks[start].bbox[0]
    return None


def _column_end(label_hits: dict[str, tuple[int, float]], line_idx: int, x0: float) -> float:
    """Right edge of a label's column: the next label's x0 on the same line."""
    rights = [hx for _, (hli, hx) in label_hits.items() if hli == line_idx and hx > x0]
    return min(rights) if rights else float("inf")


def _value_line(lines: list[Line], label_y: float) -> Line | None:
    """Nearest line below the label, within a small vertical gap."""
    below = [ln for ln in lines if ln.y < label_y and label_y - ln.y <= _MAX_LABEL_TO_VALUE_GAP]
    return max(below, key=lambda ln: ln.y) if below else None


def _value_tokens(line: Line, x0: float, x_end: float) -> list[Token]:
    lo, hi = x0 - _COLUMN_PAD_LEFT, x_end - _COLUMN_PAD_RIGHT
    return [t for t in line.tokens if lo <= (t.bbox[0] + t.bbox[2]) / 2 < hi]


def _union_box(tokens: list[Token]) -> tuple[float, float, float, float]:
    return (min(t.bbox[0] for t in tokens), min(t.bbox[1] for t in tokens),
            max(t.bbox[2] for t in tokens), max(t.bbox[3] for t in tokens))


# Assembly

def assemble(extracted: ExtractedDocument, document_type: str) -> AssembledDocument:
    """Assemble typed fields for a document from its located tokens."""
    spec = LABELS.get(document_type, [])
    filtered = filter_tokens(extracted.tokens, extracted.watermark_terms)
    lines = group_lines(filtered.clean_tokens)

    label_hits: dict[str, tuple[int, float]] = {}
    for name, phrase, _ in spec:
        hit = _find_label(lines, phrase)
        if hit:
            label_hits[name] = hit

    fields: list[Field] = []
    for name, phrase, value_type in spec:
        hit = label_hits.get(name)
        if not hit:
            fields.append(Field(name, None, 0.0, None, None, "abstained", "label_not_found"))
            continue
        line_idx, x0 = hit
        x_end = _column_end(label_hits, line_idx, x0)
        vline = _value_line(lines, lines[line_idx].y)
        toks = _value_tokens(vline, x0, x_end) if vline else []
        if not toks:
            fields.append(Field(name, None, 0.0, None, None, "abstained", "value_not_found"))
            continue
        value = _parse(value_type, " ".join(t.text for t in toks))
        if value is None:
            fields.append(Field(name, None, 0.0, None, None, "abstained", "unparseable"))
            continue
        fields.append(Field(
            name=name,
            value=value,
            confidence=round(min(t.confidence for t in toks), 3),
            source_bbox=_union_box(toks),
            source_method=toks[0].source,
            status="extracted",
        ))

    if filtered.injected_instruction:
        toks = filtered.injected_tokens
        fields.append(Field(
            name="untrusted_instruction_text",
            value=filtered.injected_instruction,
            confidence=round(min(t.confidence for t in toks), 3) if toks else 1.0,
            source_bbox=_union_box(toks) if toks else None,
            source_method=toks[0].source if toks else extracted.method,
            status="quarantined",
            reason="embedded_instruction_detected_not_executed",
        ))

    return AssembledDocument(
        document_type=document_type,
        method=extracted.method,
        fields=fields,
        injected_instruction=filtered.injected_instruction,
    )
