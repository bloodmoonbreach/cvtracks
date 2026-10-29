"""Re-order a track's content for one job post. Selection and order only: no new text, ever.

The job post is untrusted input. If `remote-eligibility` is installed, its sanitiser removes hidden
text and injected instructions first; either way the post is only used for keyword matching.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from . import i18n
from .model import Master, Track
from .select import Scores, included
from .text import contains_term, fold

_STOP = set("""a an and are as at be by for from has have in is it its of on or our the to we with you your will
this that these those can may must should able work working team role job years year experience plus etc
el la los las de del y o en con por para un una que se su sus es al lo como más mas tu tus nuestro nuestra
si sí este esta trabajo equipo experiencia años año
și si sau de la în in cu pentru un o ce din pe să sa este ai ale al fi echipa experienta ani""".split())



def _read_terms(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]


def _load_skills() -> list[str]:
    """The curated vocabulary in skills/*.txt (one file per field): only these terms can be reported as
    missing, so page boilerplate never is. $CVTRACKS_SKILLS can name extra files (os.pathsep-separated)."""
    import os
    from importlib import resources
    from pathlib import Path
    terms: list[str] = []
    for f in sorted(resources.files("cvtracks").joinpath("skills").iterdir(), key=lambda f: f.name):
        if f.name.endswith(".txt"):
            terms += _read_terms(f.read_text(encoding="utf-8"))
    for extra in filter(None, os.environ.get("CVTRACKS_SKILLS", "").split(os.pathsep)):
        if Path(extra).is_file():
            terms += _read_terms(Path(extra).read_text(encoding="utf-8"))
    return list(dict.fromkeys(terms))


SKILLS = _load_skills()


def _case_sensitive(term: str) -> bool:
    """Acronyms (PAM, ENS, DORA, ICS) only count in capitals, so names and ordinary words don't match."""
    letters = [c for c in term if c.isalpha()]
    return len(letters) <= 5 and all(c.isupper() for c in letters) and any(letters)


def _count(term: str, text: str, folded: str) -> int:
    if _case_sensitive(term):
        return len(re.findall(rf"(?<![\w]){re.escape(term)}(?![\w])", text))
    return len(re.findall(rf"(?<![\w]){re.escape(fold(term).strip())}(?![\w])", folded))


@dataclass
class TailorReport:
    matched: list[str] = field(default_factory=list)  # job terms your master covers
    gaps: list[str] = field(default_factory=list)  # job terms nowhere in your master
    hidden: list[str] = field(default_factory=list)  # in your master, but excluded by this track
    top_items: list[tuple[str, float]] = field(default_factory=list)
    safety: dict | None = None


def _clean(job_text: str) -> tuple[str, dict | None]:
    try:
        from remote_eligibility.safety import prepare
    except ImportError:
        return job_text, None
    from remote_eligibility.safety import REMOVED

    text, report, _ = prepare(job_text)
    return text.replace(REMOVED, " "), report.to_dict()  # the marker itself must not match anything


def _vocab(master: Master) -> dict[str, list[str]]:
    """term → item ids it belongs to (all languages)."""
    out: dict[str, set[str]] = {}

    def add(term: str, item: str) -> None:
        term = term.strip()
        if len(term) >= 2 and fold(term) not in _STOP:
            out.setdefault(term, set()).add(item)

    for g in master.skills:
        for j, x in enumerate(g.items):
            for v in ([x] if isinstance(x, str) else x.values()):
                for part in re.split(r"\s*[/,|]\s*", v):
                    add(part, f"{g.id}#{j}")
    for section in ("experience", "projects", "education"):
        for e in getattr(master, section):
            for k in e.keywords:
                add(k, e.id)
            for j, b in enumerate(e.bullets):
                for k in b.keywords:
                    add(k, f"{e.id}#{j}")
    for c in master.certifications:
        for k in c.keywords + [i18n.text(c.name, "en")]:
            add(k, c.id)
    return {k: sorted(v) for k, v in out.items()}


def _item_texts(master: Master) -> dict[str, str]:
    """item id (and id#bullet) → folded text in every language."""
    def all_text(v) -> str:
        return " ".join([v] if isinstance(v, str) else (v or {}).values())

    out: dict[str, str] = {}
    for section in ("experience", "projects", "education"):
        for e in getattr(master, section):
            parts = [all_text(e.title), all_text(e.org), all_text(e.summary), " ".join(e.keywords)]
            for j, b in enumerate(e.bullets):
                bt = all_text(b.text) + " " + " ".join(b.keywords)
                out[f"{e.id}#{j}"] = fold(bt)
                parts.append(bt)
            out[e.id] = fold(" ".join(parts))
    for c in master.certifications:
        out[c.id] = fold(all_text(c.name) + " " + all_text(c.issuer) + " " + " ".join(c.keywords))
    for g in master.skills:
        out[g.id] = fold(all_text(g.label) + " " + " ".join(all_text(x) for x in g.items))
        for j, x in enumerate(g.items):
            out[f"{g.id}#{j}"] = fold(all_text(x))
    return out


def tailor(master: Master, track: Track, job_text: str) -> tuple[Scores, TailorReport]:
    text, safety = _clean(job_text)
    job = fold(text)
    report = TailorReport(safety=safety)

    vocab = _vocab(master)
    matched = [t for t in vocab if contains_term(job, t)]
    seen: dict[str, str] = {}
    for t in sorted(matched, key=lambda t: (t.lower(), t)):
        seen.setdefault(t.lower(), t)
    report.matched = sorted(seen.values(), key=str.lower)

    # Known skills the post names that nothing in the master mentions (candidates to learn, or to add if true)
    items = _item_texts(master)
    summaries = " ".join(v if isinstance(v, str) else " ".join((v or {}).values()) for v in master.summaries.values())
    everything = " ".join(items.values()) + " " + fold(summaries)
    candidates = Counter({t: n for t in SKILLS if (n := _count(t, text, job)) and not contains_term(everything, t)})
    # drop a term already covered by a longer one ("Sentinel" when "Microsoft Sentinel" is listed)
    kept = {c for c in candidates if not any(c != o and contains_term(fold(o), c) for o in candidates)}
    report.gaps = sorted(kept, key=lambda c: (-candidates[c], c.lower()))[:25]

    # Score every item by how many matched terms its text contains
    scores: Scores = {}
    for item_id, folded in items.items():
        hits = sum(1 for t in matched if contains_term(folded, t))
        if hits:
            scores[item_id] = float(hits)

    # Items that would help but this track leaves out
    def tags_of(item_id: str):
        base = item_id.split("#")[0]
        for section in ("experience", "projects", "education", "certifications", "skills"):
            for x in getattr(master, section):
                if x.id == base:
                    return x.tags
        return []

    report.hidden = sorted({i.split("#")[0] for i, s in scores.items() if s >= 2 and not included(tags_of(i), track)})
    report.top_items = sorted(((k, v) for k, v in scores.items() if "#" not in k), key=lambda kv: -kv[1])[:10]
    return scores, report
