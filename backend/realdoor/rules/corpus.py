"""Load the frozen rule corpus (data/rule_corpus.jsonl).

The corpus is the only place rule text, authority, effective date, and source
location live. Every citation elsewhere in Stage 02 is built from here, never
hardcoded.
"""

from __future__ import annotations

import json
from functools import lru_cache

from .. import config


def load_rules(path=None) -> dict[str, dict]:
    """Load rule_corpus.jsonl into a dict keyed by rule_id."""
    rules_path = path or config.RULE_CORPUS
    with rules_path.open(encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    ids = [r["rule_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate rule_id in rule corpus")
    return {r["rule_id"]: r for r in rows}


@lru_cache(maxsize=1)
def get_rules() -> dict[str, dict]:
    """Cached load of the frozen rule corpus."""
    return load_rules()


def cite(rule_id: str) -> dict:
    """Build a citation dict for one rule: id, authority, effective date, source."""
    rule = get_rules()[rule_id]
    return {
        "rule_id": rule["rule_id"],
        "authority": rule["authority"],
        "effective_date": rule["effective_date"],
        "source_url": rule["source_url"],
        "source_locator": rule["source_locator"],
    }
