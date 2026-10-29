"""Pick and order content from the master for one (track, language). Never adds or rewrites facts."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from . import i18n
from .model import Certification, Entry, Master, SkillGroup, Track, date_precision


@dataclass
class RItem:
    id: str
    title: str
    org: str = ""
    location: str = ""
    dates: str = ""
    status: str = ""
    grade: str = ""
    url: str = ""
    summary: str = ""
    bullets: list[str] = field(default_factory=list)
    start_iso: str = ""  # for machine formats (JSON Resume)
    end_iso: str = ""


@dataclass
class RCert:
    id: str
    name: str
    issuer: str = ""
    date: str = ""
    credential_id: str = ""
    url: str = ""
    date_iso: str = ""


@dataclass
class RSkills:
    id: str
    label: str
    items: list[str]


@dataclass
class RLanguage:
    name: str
    level: str
    cefr: str = ""


@dataclass
class Contact:
    kind: str  # email | phone | website | github | linkedin | location
    text: str
    href: str = ""


@dataclass
class ResolvedCV:
    """A finished CV for one track and language: plain strings, ready for any renderer."""

    track: str
    lang: str
    name: str
    headline: str
    contacts: list[Contact]
    extra: list[str]
    sections: list[str]  # order
    labels: dict[str, str]
    summary: str = ""
    experience: list[RItem] = field(default_factory=list)
    education: list[RItem] = field(default_factory=list)
    projects: list[RItem] = field(default_factory=list)
    certifications: list[RCert] = field(default_factory=list)
    skills: list[RSkills] = field(default_factory=list)
    languages: list[RLanguage] = field(default_factory=list)


Scores = dict[str, float]  # item id, or "item_id#bullet_index", → relevance (higher first)


def _iso(d: dt.date | None, raw) -> str:
    if d is None:
        return ""
    return {"year": f"{d.year}", "month": f"{d.year}-{d.month:02d}"}.get(date_precision(raw), d.isoformat())


def included(tags: list[str], track: Track) -> bool:
    if set(tags) & set(track.exclude_tags):
        return False
    if not track.include_tags or not tags:
        return True
    return bool(set(tags) & set(track.include_tags))


def _sort_key_date(e: Entry) -> tuple:
    end = dt.date.max if e.ongoing else (e.end or e.start or dt.date.min)
    return (end, e.start or dt.date.min)


def _entry(e: Entry, track: Track, lang: str, scores: Scores) -> RItem:
    bullets = [(i, b) for i, b in enumerate(e.bullets) if included(b.tags, track)]
    bullets.sort(key=lambda ib: (ib[1].priority, -scores.get(f"{e.id}#{ib[0]}", 0.0), ib[0]))
    limit = track.limits.get("bullets")
    if limit is not None:
        bullets = bullets[:limit]
    status = i18n.text(e.status, lang)
    if not status and e.ongoing and e.end is None and e.start and e.start > dt.date.today():
        status = i18n.label("in_progress", lang)
    return RItem(
        id=e.id, title=i18n.text(e.title, lang), org=i18n.text(e.org, lang), location=i18n.text(e.location, lang),
        dates=i18n.date_range(e.start, e.end, e.ongoing, lang, date_precision(e.start_raw), date_precision(e.end_raw)),
        status=status, grade=i18n.text(e.grade, lang), url=e.url or "",
        summary=i18n.text(e.summary, lang), bullets=[i18n.text(b.text, lang) for _, b in bullets],
        start_iso=_iso(e.start, e.start_raw), end_iso="" if e.ongoing else _iso(e.end, e.end_raw),
    )


def _entries(items: list[Entry], track: Track, lang: str, scores: Scores, limit_key: str, by_date: bool) -> list[RItem]:
    chosen = [e for e in items if included(e.tags, track)]
    if by_date:
        chosen.sort(key=_sort_key_date, reverse=True)
        chosen.sort(key=lambda e: e.priority)  # stable: keeps date order inside each priority
    else:
        order = {e.id: i for i, e in enumerate(chosen)}
        chosen.sort(key=lambda e: (e.priority, -scores.get(e.id, 0.0), order[e.id]))
    limit = track.limits.get(limit_key)
    if limit is not None:
        chosen = chosen[:limit]
    return [_entry(e, track, lang, scores) for e in chosen]


def _certs(items: list[Certification], track: Track, lang: str, scores: Scores) -> list[RCert]:
    chosen = [c for c in items if included(c.tags, track)]
    chosen.sort(key=lambda c: (c.priority, -scores.get(c.id, 0.0), -(c.date or dt.date.min).toordinal()))
    limit = track.limits.get("certifications")
    if limit is not None:
        chosen = chosen[:limit]
    return [RCert(c.id, i18n.text(c.name, lang), i18n.text(c.issuer, lang),
                  i18n.date(c.date, date_precision(c.date_raw), lang), c.credential_id or "", c.url or "",
                  _iso(c.date, c.date_raw)) for c in chosen]


def _skills(groups: list[SkillGroup], track: Track, lang: str, scores: Scores) -> list[RSkills]:
    chosen = [g for g in groups if included(g.tags, track)]
    order = {gid: i for i, gid in enumerate(track.skills_order)}
    if track.skills_order:
        chosen = [g for g in chosen if g.id in order] + [g for g in chosen if g.id not in order]
    chosen.sort(key=lambda g: (order.get(g.id, len(order)), -scores.get(g.id, 0.0)))
    if (n := track.limits.get("skills_groups")) is not None:
        chosen = chosen[:n]
    per = track.limits.get("skills_per_group")
    out = []
    for g in chosen:
        items = [(i, i18n.text(x, lang)) for i, x in enumerate(g.items)]
        items.sort(key=lambda ix: (-scores.get(f"{g.id}#{ix[0]}", 0.0), ix[0]))
        values = [x for _, x in items]
        out.append(RSkills(g.id, i18n.text(g.label, lang), values[:per] if per else values))
    return out


def _contacts(master: Master, track: Track, lang: str) -> list[Contact]:
    p = master.person
    show = track.show
    out = []
    if p.email and show.get("email", True):
        out.append(Contact("email", p.email, f"mailto:{p.email}"))
    if p.phone and show.get("phone", True):
        out.append(Contact("phone", p.phone, "tel:" + "".join(ch for ch in p.phone if ch.isdigit() or ch == "+")))
    if p.location and show.get("location", True):
        out.append(Contact("location", i18n.text(p.location, lang)))
    if p.website and show.get("website", True):
        out.append(Contact("website", p.website.removeprefix("https://").removeprefix("http://"),
                           p.website if "://" in p.website else f"https://{p.website}"))
    if p.linkedin and show.get("linkedin", True):
        out.append(Contact("linkedin", f"in/{p.linkedin}", f"https://www.linkedin.com/in/{p.linkedin}"))
    if p.github and show.get("github", True):
        out.append(Contact("github", f"github.com/{p.github}", f"https://github.com/{p.github}"))
    return out


def resolve(master: Master, track: Track, lang: str, scores: Scores | None = None) -> ResolvedCV:
    scores = scores or {}
    labels = {k: i18n.label(k, lang, master.labels) for k in i18n.LABELS["en"]}
    cv = ResolvedCV(
        track=track.id, lang=lang, name=master.person.name, headline=i18n.text(track.title, lang),
        contacts=_contacts(master, track, lang),
        extra=[i18n.text(x, lang) for x in master.person.extra] if track.show.get("extra", True) else [],
        sections=list(track.sections), labels=labels,
    )
    if track.summary:
        cv.summary = i18n.text(master.summaries.get(track.summary), lang)
    cv.experience = _entries(master.experience, track, lang, scores, "experience", by_date=True)
    cv.education = _entries(master.education, track, lang, scores, "education", by_date=True)
    cv.projects = _entries(master.projects, track, lang, scores, "projects", by_date=False)
    cv.certifications = _certs(master.certifications, track, lang, scores)
    cv.skills = _skills(master.skills, track, lang, scores)
    cv.languages = [RLanguage(i18n.text(l.name, lang), i18n.text(l.level, lang), l.cefr or "") for l in master.languages]
    return cv
