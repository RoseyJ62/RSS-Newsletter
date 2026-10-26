from typing import List, Optional

import scorer


def normalize(keyword: str) -> str:
    """Comparison form used to detect duplicates: trimmed, single-spaced, case-insensitive."""
    return " ".join(keyword.split()).casefold()


def clean(keyword: str) -> str:
    """Display/storage form for newly entered keywords: trimmed and single-spaced."""
    return " ".join(keyword.split())


def find_duplicate(keyword: str, keywords: List[str], ignore_index: Optional[int] = None) -> Optional[str]:
    target = normalize(keyword)
    for i, existing in enumerate(keywords):
        if i != ignore_index and normalize(existing) == target:
            return existing
    return None


def load_high_signal() -> List[str]:
    context = scorer.load_context()
    return list(context.get("keyword_rules", {}).get("high_signal", []))


def save_high_signal(keywords: List[str]) -> None:
    # Re-read the context so only the high-signal list changes and every other
    # part of osf_context.json is preserved.
    context = scorer.load_context()
    context.setdefault("keyword_rules", {})["high_signal"] = list(keywords)
    scorer.save_context(context)
