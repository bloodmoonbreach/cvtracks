"""Read master and track YAML files into the model, with errors that point at the bad key."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .model import (SECTIONS, Bullet, Certification, Entry, Language, Master, ModelError, Person, SkillGroup,
                    Track, parse_date)

_TEXT_TYPES = (str, dict, type(None))


def _text(v: Any, where: str):
    if not isinstance(v, _TEXT_TYPES) and not isinstance(v, (int, float)):
        raise ModelError(f"{where}: expected text or {{lang: text}}, got {type(v).__name__}")
    if isinstance(v, dict):
        for k, x in v.items():
            if not isinstance(k, str) or not isinstance(x, (str, int, float)):
                raise ModelError(f"{where}.{k}: expected text")
        return {k: str(x) for k, x in v.items()}
    return None if v is None else str(v)


def _list(v: Any, where: str) -> list:
    if v is None:
        return []
    if not isinstance(v, list):
        raise ModelError(f"{where}: expected a list")
    return v


def _tags(d: dict, where: str) -> list[str]:
    return [str(t) for t in _list(d.get("tags"), f"{where}.tags")]


def _check_keys(d: dict, allowed: set[str], where: str) -> None:
    unknown = set(d) - allowed
    if unknown:
        raise ModelError(f"{where}: unknown key(s) {', '.join(sorted(unknown))} (allowed: {', '.join(sorted(allowed))})")


def _bullet(v: Any, where: str) -> Bullet:
    if isinstance(v, (str, dict)) and not (isinstance(v, dict) and "text" in v):
        return Bullet(_text(v, where))
    if not isinstance(v, dict):
        raise ModelError(f"{where}: expected text or a mapping with 'text'")
    _check_keys(v, {"text", "tags", "priority", "keywords"}, where)
    return Bullet(_text(v["text"], f"{where}.text"), _tags(v, where), int(v.get("priority", 2)),
                  [str(k) for k in _list(v.get("keywords"), f"{where}.keywords")])


_ENTRY_KEYS = {"id", "title", "role", "degree", "name", "org", "company", "school", "location", "start", "end",
               "ongoing", "status", "grade", "url", "summary", "bullets", "tags", "priority", "keywords"}


def _entry(d: Any, where: str, i: int) -> Entry:
    if not isinstance(d, dict):
        raise ModelError(f"{where}: expected a mapping")
    _check_keys(d, _ENTRY_KEYS, where)
    title = d.get("title", d.get("role", d.get("degree", d.get("name"))))
    if title is None:
        raise ModelError(f"{where}: needs a title (or role / degree / name)")
    end_raw = d.get("end")
    return Entry(
        id=str(d.get("id") or f"{where.split('[')[0]}-{i}"),
        title=_text(title, f"{where}.title"),
        org=_text(d.get("org", d.get("company", d.get("school"))), f"{where}.org"),
        location=_text(d.get("location"), f"{where}.location"),
        start=parse_date(d.get("start"), f"{where}.start"), start_raw=d.get("start"),
        end=parse_date(end_raw, f"{where}.end"), end_raw=end_raw,
        ongoing=bool(d.get("ongoing", end_raw in ("present", "now"))),
        status=_text(d.get("status"), f"{where}.status"),
        grade=_text(d.get("grade"), f"{where}.grade"),
        url=d.get("url"),
        summary=_text(d.get("summary"), f"{where}.summary"),
        bullets=[_bullet(b, f"{where}.bullets[{j}]") for j, b in enumerate(_list(d.get("bullets"), f"{where}.bullets"))],
        tags=_tags(d, where),
        priority=int(d.get("priority", 2)),
        keywords=[str(k) for k in _list(d.get("keywords"), f"{where}.keywords")],
    )


def load_master(path: str | Path) -> Master:
    p = Path(path)
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ModelError(f"{p}: invalid YAML: {e}") from e
    if not isinstance(data, dict):
        raise ModelError(f"{p}: top level must be a mapping")
    _check_keys(data, {"person", "summaries", "experience", "education", "projects", "certifications",
                       "skills", "languages", "labels"}, str(p.name))

    pd = data.get("person") or {}
    if not isinstance(pd, dict) or not pd.get("name"):
        raise ModelError("person.name is required")
    _check_keys(pd, {"name", "location", "email", "phone", "website", "github", "linkedin", "extra"}, "person")
    person = Person(
        name=str(pd["name"]), location=_text(pd.get("location"), "person.location"),
        email=pd.get("email"), phone=str(pd["phone"]) if pd.get("phone") else None,
        website=pd.get("website"), github=pd.get("github"), linkedin=pd.get("linkedin"),
        extra=[_text(x, f"person.extra[{i}]") for i, x in enumerate(_list(pd.get("extra"), "person.extra"))],
    )

    certs = []
    for i, c in enumerate(_list(data.get("certifications"), "certifications")):
        w = f"certifications[{i}]"
        if not isinstance(c, dict) or "name" not in c:
            raise ModelError(f"{w}: needs a name")
        _check_keys(c, {"id", "name", "issuer", "date", "credential_id", "url", "evidence", "tags", "priority", "keywords"}, w)
        certs.append(Certification(
            id=str(c.get("id") or f"cert-{i}"), name=_text(c["name"], f"{w}.name"),
            issuer=_text(c.get("issuer"), f"{w}.issuer"), date=parse_date(c.get("date"), f"{w}.date"), date_raw=c.get("date"),
            credential_id=str(c["credential_id"]) if c.get("credential_id") else None, url=c.get("url"),
            evidence=c.get("evidence"), tags=_tags(c, w), priority=int(c.get("priority", 2)),
            keywords=[str(k) for k in _list(c.get("keywords"), f"{w}.keywords")]))

    skills = []
    for i, g in enumerate(_list(data.get("skills"), "skills")):
        w = f"skills[{i}]"
        if not isinstance(g, dict) or "items" not in g:
            raise ModelError(f"{w}: needs label and items")
        _check_keys(g, {"id", "label", "items", "tags"}, w)
        skills.append(SkillGroup(str(g.get("id") or f"skills-{i}"), _text(g.get("label", ""), f"{w}.label"),
                                 [_text(x, f"{w}.items[{j}]") for j, x in enumerate(_list(g["items"], f"{w}.items"))],
                                 _tags(g, w)))

    langs = []
    for i, l in enumerate(_list(data.get("languages"), "languages")):
        w = f"languages[{i}]"
        if not isinstance(l, dict) or "name" not in l:
            raise ModelError(f"{w}: needs name and level")
        langs.append(Language(_text(l["name"], f"{w}.name"), _text(l.get("level"), f"{w}.level"), l.get("cefr")))

    summaries = data.get("summaries") or {}
    if not isinstance(summaries, dict):
        raise ModelError("summaries: expected {key: text}")

    ids: dict[str, str] = {}
    master = Master(
        person=person,
        summaries={str(k): _text(v, f"summaries.{k}") for k, v in summaries.items()},
        experience=[_entry(e, f"experience[{i}]", i) for i, e in enumerate(_list(data.get("experience"), "experience"))],
        education=[_entry(e, f"education[{i}]", i) for i, e in enumerate(_list(data.get("education"), "education"))],
        projects=[_entry(e, f"projects[{i}]", i) for i, e in enumerate(_list(data.get("projects"), "projects"))],
        certifications=certs, skills=skills, languages=langs,
        labels={str(k): _text(v, f"labels.{k}") for k, v in (data.get("labels") or {}).items()},
    )
    for section in ("experience", "education", "projects", "certifications", "skills"):
        for item in getattr(master, section):
            if item.id in ids:
                raise ModelError(f"duplicate id {item.id!r} in {section} and {ids[item.id]}")
            ids[item.id] = section
    return master


def load_track(path: str | Path) -> Track:
    p = Path(path)
    d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    w = p.name
    if not isinstance(d, dict):
        raise ModelError(f"{w}: top level must be a mapping")
    _check_keys(d, {"id", "title", "languages", "summary", "include_tags", "exclude_tags", "sections", "limits",
                    "skills_order", "keywords", "show", "file_name"}, w)
    langs = [str(x) for x in _list(d.get("languages") or ["en"], f"{w}.languages")]
    sections = [str(x) for x in _list(d.get("sections"), f"{w}.sections")] or list(SECTIONS)
    bad = [s for s in sections if s not in SECTIONS]
    if bad:
        raise ModelError(f"{w}.sections: unknown {bad} (known: {', '.join(SECTIONS)})")
    return Track(
        id=str(d.get("id") or p.stem), title=_text(d.get("title"), f"{w}.title"), languages=langs,
        summary=d.get("summary"),
        include_tags=[str(x) for x in _list(d.get("include_tags"), f"{w}.include_tags")],
        exclude_tags=[str(x) for x in _list(d.get("exclude_tags"), f"{w}.exclude_tags")],
        sections=sections, limits={str(k): int(v) for k, v in (d.get("limits") or {}).items()},
        skills_order=[str(x) for x in _list(d.get("skills_order"), f"{w}.skills_order")],
        keywords=_keywords(d.get("keywords"), f"{w}.keywords"),
        show={str(k): bool(v) for k, v in (d.get("show") or {}).items()},
        file_name=d.get("file_name"),
    )


def _keywords(v, where: str) -> dict[str, list[str]]:
    """`keywords: [a, b]` applies to every language; `keywords: {en: [...], es: [...]}` per language."""
    if v is None:
        return {}
    if isinstance(v, list):
        return {"*": [str(x) for x in v]}
    if isinstance(v, dict):
        return {str(k): [str(x) for x in _list(x, f"{where}.{k}")] for k, x in v.items()}
    raise ModelError(f"{where}: expected a list, or {{lang: [terms]}}")


def load_tracks(directory: str | Path) -> dict[str, Track]:
    tracks = {}
    for p in sorted(Path(directory).glob("*.y*ml")):
        t = load_track(p)
        if t.id in tracks:
            raise ModelError(f"duplicate track id {t.id!r} ({p.name})")
        tracks[t.id] = t
    return tracks
