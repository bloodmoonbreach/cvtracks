"""Languages: picking text, section labels and date formats (en, es, ro built in; others fall back to en)."""

from __future__ import annotations

import datetime as dt

from .model import Text

LABELS: dict[str, dict[str, str]] = {
    "en": {"summary": "Summary", "experience": "Professional Experience", "education": "Education",
           "projects": "Projects", "certifications": "Certifications", "skills": "Skills", "languages": "Languages",
           "present": "Present", "in_progress": "In progress", "credential": "ID"},
    "es": {"summary": "Perfil", "experience": "Experiencia profesional", "education": "Formación",
           "projects": "Proyectos", "certifications": "Certificaciones", "skills": "Habilidades", "languages": "Idiomas",
           "present": "Actualidad", "in_progress": "En curso", "credential": "ID"},
    "ro": {"summary": "Profil", "experience": "Experiență profesională", "education": "Educație",
           "projects": "Proiecte", "certifications": "Certificări", "skills": "Competențe", "languages": "Limbi străine",
           "present": "Prezent", "in_progress": "În curs", "credential": "ID"},
}

MONTHS = {
    "en": "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(),
    "es": "ene feb mar abr may jun jul ago sept oct nov dic".split(),
    "ro": "ian feb mar apr mai iun iul aug sept oct nov dec".split(),
}


class MissingTranslation(Exception):
    pass


def text(value: Text, lang: str, strict: bool = False) -> str:
    """Pick the text for `lang`. Plain strings are language-neutral. Missing languages fall back to
    English (or the first one given) unless `strict`."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if lang in value:
        return value[lang]
    if strict:
        raise MissingTranslation(lang)
    return value.get("en") or next(iter(value.values()), "")


def has_lang(value: Text, lang: str) -> bool:
    return value is None or isinstance(value, str) or lang in value


def label(key: str, lang: str, overrides: dict[str, Text] | None = None) -> str:
    if overrides and key in overrides:
        return text(overrides[key], lang)
    return LABELS.get(lang, LABELS["en"]).get(key) or LABELS["en"][key]


def date(d: dt.date | None, precision: str, lang: str) -> str:
    if d is None:
        return ""
    if precision == "year":
        return str(d.year)
    months = MONTHS.get(lang, MONTHS["en"])
    return f"{months[d.month - 1]} {d.year}"


def date_range(start: dt.date | None, end: dt.date | None, ongoing: bool, lang: str,
               start_prec: str = "month", end_prec: str = "month") -> str:
    a = date(start, start_prec, lang)
    # Only entries marked ongoing (or `end: present`) say "Present"; a lone start date is just a date.
    b = label("present", lang) if ongoing else date(end, end_prec, lang)
    if a and b and a != b:
        return f"{a} – {b}"
    return a or b
