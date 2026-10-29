"""Checks that catch the problems hand-edited CVs drift into."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

from . import i18n
from .model import Master, Text, Track
from .select import ResolvedCV, included, resolve
from .text import contains_term, contains_term_exact, fold, words

# Frequent CV misspellings (folded). Extend in the master with `labels`? No: keep data-only; PRs welcome.
TYPOS = {
    "desarollador": "desarrollador", "desarollo": "desarrollo", "penetretion": "penetration", "experiance": "experience",
    "managment": "management", "responsable de de": "responsable de", "enviroment": "environment",
    "developement": "development", "succesful": "successful", "succesfully": "successfully", "acheived": "achieved",
    "recieved": "received", "seperate": "separate", "maintainance": "maintenance", "occured": "occurred",
    "comunicacion": "comunicación", "aplicacion web": "aplicación web", "informatica": "informática",
    "vulnerabilites": "vulnerabilities", "vulnerabilties": "vulnerabilities", "authetication": "authentication",
    "linux kernal": "linux kernel", "pentration": "penetration", "penetation": "penetration", "securtiy": "security",
    "certificaction": "certification", "certifcate": "certificate", "proficiency in in": "proficiency in",
}
_PLACEHOLDER = re.compile(r"\b(TODO|TBD|FIXME|XXX|lorem ipsum)\b|\?\?\?", re.IGNORECASE)
_REPEAT = re.compile(r"\b(\w{2,})\s+\1\b", re.IGNORECASE)


@dataclass
class Issue:
    level: str  # error | warning | info
    where: str
    message: str

    def __str__(self) -> str:
        icon = {"error": "✖", "warning": "⚠", "info": "·"}[self.level]
        return f"{icon} {self.where}: {self.message}"


def _texts(master: Master, track: Track):
    """Yield (where, Text) for every text that this track can print."""
    p = master.person
    yield "person.location", p.location
    for i, x in enumerate(p.extra):
        yield f"person.extra[{i}]", x
    yield f"track {track.id}: title", track.title
    if track.summary:
        yield f"summaries.{track.summary}", master.summaries.get(track.summary)
    for section in ("experience", "education", "projects"):
        for e in getattr(master, section):
            if not included(e.tags, track):
                continue
            w = f"{section}:{e.id}"
            for key in ("title", "org", "location", "status", "grade", "summary"):
                yield f"{w}.{key}", getattr(e, key)
            for j, b in enumerate(e.bullets):
                if included(b.tags, track):
                    yield f"{w}.bullets[{j}]", b.text
    for c in master.certifications:
        if included(c.tags, track):
            yield f"certifications:{c.id}.name", c.name
            yield f"certifications:{c.id}.issuer", c.issuer
    for g in master.skills:
        if included(g.tags, track):
            yield f"skills:{g.id}.label", g.label
            for j, x in enumerate(g.items):
                yield f"skills:{g.id}.items[{j}]", x
    for i, l in enumerate(master.languages):
        yield f"languages[{i}].name", l.name
        yield f"languages[{i}].level", l.level


def _flat(cv: ResolvedCV) -> str:
    from .render.markdown import to_markdown
    return to_markdown(cv)


def lint(master: Master, tracks: dict[str, Track], base_dir: Path | None = None) -> list[Issue]:
    issues: list[Issue] = []
    today = dt.date.today()

    # Facts: dates, evidence files, ids
    for section in ("experience", "education", "projects"):
        for e in getattr(master, section):
            w = f"{section}:{e.id}"
            if e.start and e.end and e.end < e.start:
                issues.append(Issue("error", w, "ends before it starts"))
            if e.ongoing and e.end and e.end < today:
                issues.append(Issue("warning", w, "marked ongoing but has an end date in the past"))
            if e.start and e.start > today and not e.ongoing:
                issues.append(Issue("warning", w, "starts in the future"))
            if section == "experience" and not e.bullets and not e.summary:
                issues.append(Issue("warning", w, "no bullets: say what you achieved, with numbers if you have them"))
    for c in master.certifications:
        w = f"certifications:{c.id}"
        if not c.date:
            issues.append(Issue("info", w, "no date"))
        if c.evidence and base_dir is not None:
            ev = Path(c.evidence).expanduser()
            if not ev.is_absolute():
                ev = base_dir / ev
            if not ev.exists():
                issues.append(Issue("warning", w, f"evidence file not found: {c.evidence}"))

    # Text quality, per track and language
    seen_typos: set[tuple[str, str]] = set()
    for track in tracks.values():
        for where, value in _texts(master, track):
            for lang in track.languages:
                if value is not None and not i18n.has_lang(value, lang):
                    issues.append(Issue("error", where, f"missing '{lang}' text (needed by track {track.id})"))
            values = [value] if isinstance(value, str) else list((value or {}).values())
            for v in values:
                if _PLACEHOLDER.search(v):
                    issues.append(Issue("warning", where, f"placeholder left: {v[:80]!r}"))
                low = v.lower()  # not folded: "aplicación" must not match the typo "aplicacion"
                for bad, good in TYPOS.items():
                    if contains_term_exact(low, bad) and (where, bad) not in seen_typos:
                        seen_typos.add((where, bad))
                        issues.append(Issue("error", where, f"typo: '{bad}' → '{good}'"))
                if m := _REPEAT.search(v):
                    issues.append(Issue("warning", where, f"repeated word: '{m.group(0)}'"))

        # Output checks
        for lang in track.languages:
            cv = resolve(master, track, lang)
            text = _flat(cv)
            n = words(text)
            max_words = track.limits.get("max_words")
            if max_words and n > max_words:
                issues.append(Issue("warning", f"track {track.id} [{lang}]", f"{n} words, over the {max_words} limit (probably 2+ pages)"))
            if track.summary and track.summary not in master.summaries:
                issues.append(Issue("error", f"track {track.id}", f"summary {track.summary!r} not found in summaries"))
            folded = fold(text)
            missing = [k for k in track.keywords_for(lang) if not contains_term(folded, k)]
            if missing:
                issues.append(Issue("warning", f"track {track.id} [{lang}]",
                                    "keywords screeners look for but the CV doesn't mention: " + ", ".join(missing)
                                    + " (add them only where they're true)"))
            for key in track.sections:
                empty = (key == "summary" and not cv.summary) or (key != "summary" and not getattr(cv, key))
                if empty:
                    issues.append(Issue("info", f"track {track.id} [{lang}]", f"section '{key}' is empty"))
    unique: list[Issue] = []
    seen: set[tuple[str, str, str]] = set()
    for i in issues:
        key = (i.level, i.where, i.message)
        if key not in seen:
            seen.add(key)
            unique.append(i)
    return unique
