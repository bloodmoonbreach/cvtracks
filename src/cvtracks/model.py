"""Data model: one master file of facts, many tracks that select from it.

Any text field can be a plain string (same in every language) or a mapping of language → text:

    role: {en: Inside Sales & Customer Support, es: Comercial interno y soporte técnico}

Items can carry `tags`; a track includes an item when it has no tags or shares one with the track.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Any, Union

Text = Union[str, dict[str, str], None]

_DATE = re.compile(r"^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?$")


class ModelError(ValueError):
    """A problem in the master or track file, with the path to the offending key."""


def parse_date(value: Any, where: str) -> dt.date | None:
    """Accept 2024, 2024-03, 2024-03-15 (YAML may already give a date)."""
    if value in (None, "", "present", "now"):
        return None
    if isinstance(value, dt.date):
        return value
    m = _DATE.match(str(value).strip())
    if not m:
        raise ModelError(f"{where}: dates look like 2024, 2024-03 or 2024-03-15, got {value!r}")
    y, mo, d = int(m.group(1)), int(m.group(2) or 1), int(m.group(3) or 1)
    return dt.date(y, mo, d)


def date_precision(value: Any) -> str:
    if isinstance(value, dt.date):
        return "day"
    s = str(value or "")
    return {1: "year", 2: "month", 3: "day"}.get(s.count("-") + 1, "month")


@dataclass
class Bullet:
    text: Text
    tags: list[str] = field(default_factory=list)
    priority: int = 2  # 1 = always keep, 3 = first to drop
    keywords: list[str] = field(default_factory=list)  # extra words for job matching (not printed)


@dataclass
class Entry:
    """Experience, education or project."""

    id: str
    title: Text  # role / degree / project name
    org: Text = None  # company / school / stack
    location: Text = None
    start: dt.date | None = None
    end: dt.date | None = None
    start_raw: Any = None
    end_raw: Any = None
    ongoing: bool = False
    status: Text = None  # e.g. {en: In progress, es: En curso}
    grade: Text = None
    url: str | None = None
    summary: Text = None
    bullets: list[Bullet] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    priority: int = 2
    keywords: list[str] = field(default_factory=list)


@dataclass
class Certification:
    id: str
    name: Text
    issuer: Text = None
    date: dt.date | None = None
    date_raw: Any = None
    credential_id: str | None = None
    url: str | None = None
    evidence: str | None = None  # local file, never printed
    tags: list[str] = field(default_factory=list)
    priority: int = 2
    keywords: list[str] = field(default_factory=list)


@dataclass
class SkillGroup:
    id: str
    label: Text
    items: list[Text]
    tags: list[str] = field(default_factory=list)


@dataclass
class Language:
    name: Text
    level: Text
    cefr: str | None = None


@dataclass
class Person:
    name: str
    location: Text = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    github: str | None = None
    linkedin: str | None = None
    extra: list[Text] = field(default_factory=list)  # e.g. "EU citizen", "Open to remote (Spain / EU)"


@dataclass
class Master:
    person: Person
    summaries: dict[str, Text]
    experience: list[Entry]
    education: list[Entry]
    projects: list[Entry]
    certifications: list[Certification]
    skills: list[SkillGroup]
    languages: list[Language]
    labels: dict[str, Text] = field(default_factory=dict)  # override section titles


SECTIONS = ("summary", "experience", "education", "projects", "certifications", "skills", "languages")


@dataclass
class Track:
    id: str
    title: Text  # headline under the name
    languages: list[str]
    summary: str | None = None  # key into master.summaries
    include_tags: list[str] = field(default_factory=list)  # empty = everything
    exclude_tags: list[str] = field(default_factory=list)
    sections: list[str] = field(default_factory=lambda: list(SECTIONS))
    limits: dict[str, int] = field(default_factory=dict)  # projects, certifications, bullets, skills_groups, skills_per_group
    skills_order: list[str] = field(default_factory=list)
    keywords: dict[str, list[str]] = field(default_factory=dict)  # lang (or "*") → terms screeners look for (lint)

    def keywords_for(self, lang: str) -> list[str]:
        return self.keywords.get("*", []) + self.keywords.get(lang, [])
    show: dict[str, bool] = field(default_factory=dict)  # phone, extra, …
    file_name: str | None = None  # output name pattern, e.g. "Jane_Doe_CV_{track}_{lang}"
