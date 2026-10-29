"""Small text helpers shared by lint and tailor."""

from __future__ import annotations

import re
import unicodedata


def fold(s: str) -> str:
    """Lower-case, strip accents: 'Ciberseguridad Ofensiva' → 'ciberseguridad ofensiva'."""
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


def contains_term(haystack_folded: str, term: str) -> bool:
    t = fold(term).strip()
    if not t:
        return False
    return re.search(rf"(?<![\w]){re.escape(t)}(?![\w])", haystack_folded) is not None


def contains_term_exact(haystack_lower: str, term: str) -> bool:
    """Like contains_term but accent-sensitive (for typo lists)."""
    t = term.lower().strip()
    return bool(t) and re.search(rf"(?<![\w]){re.escape(t)}(?![\w])", haystack_lower) is not None


def words(s: str) -> int:
    return len(re.findall(r"\w+", s))
