"""`cvtracks init`: a short interview that writes your own master.yaml and one track per target role.

Nothing is invented. What you skip stays out, or becomes a `TODO` that `cvtracks lint` lists.
Texts in your other CV languages start as `TODO: translate`.
"""

from __future__ import annotations

import re
from typing import Callable

import yaml

from .model import SECTIONS, parse_date, ModelError
from .text import fold

Ask = Callable[[str, str], str]  # (question, default) -> answer

HEADER = """\
# Your master file: every fact you might put on a CV, written once. Created by `cvtracks init`.
# Text can be one string, or one per language: {en: ..., es: ...}. Tags decide which CVs show an item.
# Format reference: https://github.com/bloodmoonbreach/cvtracks/blob/main/docs/format.md
# Next: fill the TODOs, then `cvtracks lint` and `cvtracks build`.
"""

TRACK_HEADER = """\
# One CV version. `cvtracks build -t {id}` builds it in every language listed below.
# keywords: terms employers for this role screen for. Lint warns when your CV never mentions one;
# add the skill to master.yaml only if it's true.
"""


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", fold(text).lower()).strip("-")[:30] or "cv"


def _list(answer: str) -> list[str]:
    return [x.strip() for x in re.split(r"[,;]", answer) if x.strip()]


def _date(ask: Ask, question: str, default: str = "") -> str:
    while True:
        a = ask(question, default).strip()
        if not a:
            return ""
        try:
            parse_date(a, "date")
            return a
        except ModelError:
            print("  Dates look like 2024, 2024-03 or 2024-03-15.")


def _yes(ask: Ask, question: str, default: bool = False) -> bool:
    a = ask(question + (" [Y/n]" if default else " [y/N]"), "").strip().lower()
    return default if not a else a.startswith(("y", "s", "d"))  # yes / sí / da


LANGUAGE_NAMES = {  # name in English → {lang: name}
    "english": {"en": "English", "es": "Inglés", "ro": "Engleză", "fr": "Anglais", "de": "Englisch", "it": "Inglese", "pt": "Inglês"},
    "spanish": {"en": "Spanish", "es": "Español", "ro": "Spaniolă", "fr": "Espagnol", "de": "Spanisch", "it": "Spagnolo", "pt": "Espanhol"},
    "romanian": {"en": "Romanian", "es": "Rumano", "ro": "Română", "fr": "Roumain", "de": "Rumänisch", "it": "Rumeno", "pt": "Romeno"},
    "french": {"en": "French", "es": "Francés", "ro": "Franceză", "fr": "Français", "de": "Französisch", "it": "Francese", "pt": "Francês"},
    "german": {"en": "German", "es": "Alemán", "ro": "Germană", "fr": "Allemand", "de": "Deutsch", "it": "Tedesco", "pt": "Alemão"},
    "italian": {"en": "Italian", "es": "Italiano", "ro": "Italiană", "fr": "Italien", "de": "Italienisch", "it": "Italiano", "pt": "Italiano"},
    "portuguese": {"en": "Portuguese", "es": "Portugués", "ro": "Portugheză", "fr": "Portugais", "de": "Portugiesisch", "it": "Portoghese", "pt": "Português"},
    "catalan": {"en": "Catalan", "es": "Catalán", "ro": "Catalană", "fr": "Catalan", "de": "Katalanisch", "it": "Catalano", "pt": "Catalão"},
    "dutch": {"en": "Dutch", "es": "Neerlandés", "ro": "Neerlandeză", "fr": "Néerlandais", "de": "Niederländisch", "it": "Olandese", "pt": "Neerlandês"},
    "polish": {"en": "Polish", "es": "Polaco", "ro": "Poloneză", "fr": "Polonais", "de": "Polnisch", "it": "Polacco", "pt": "Polaco"},
}
NATIVE = {"en": "Native", "es": "Nativo", "ro": "Nativ", "fr": "Langue maternelle", "de": "Muttersprache", "it": "Madrelingua", "pt": "Nativo"}
_NAME_ALIASES = {fold(v).lower(): k for k, names in LANGUAGE_NAMES.items() for v in names.values()}


class _Texts:
    """Turns an answer in the main language into {main: answer, other: "TODO: translate"}."""

    def __init__(self, langs: list[str]):
        self.langs = langs

    def __call__(self, value: str):
        if len(self.langs) == 1:
            return value
        return {self.langs[0]: value, **{l: "TODO: translate" for l in self.langs[1:]}}


def interview(ask: Ask) -> tuple[dict, list[dict]]:
    """Ask the questions, return (master, tracks) as plain data ready for YAML."""
    print("About you. Contact details only: no address, age, photo or nationality on a CV.")
    person: dict = {"name": ask("Full name", "").strip() or "TODO"}
    for key, q in (("email", "Email"), ("phone", "Phone (optional)"), ("linkedin", "LinkedIn handle (optional)"),
                   ("github", "GitHub handle (optional)"), ("website", "Website (optional)")):
        if v := ask(q, "").strip():
            person[key] = v

    langs = _list(ask("\nLanguages your CVs should be in, main one first (e.g. en, es)", "en").lower()) or ["en"]
    t = _Texts(langs)

    print("\nTarget roles: one CV version (track) per role, e.g. 'IT Support Technician'.")
    roles: list[tuple[str, str]] = []
    while len(roles) < 5:
        name = ask(f"Role {len(roles) + 1}" + (" (Enter to stop)" if roles else ""), "").strip()
        if not name:
            if roles:
                break
            continue
        rid = slug(name)
        while rid in {r for r, _ in roles}:
            rid += "-2"
        roles.append((rid, name))
    role_ids = [r for r, _ in roles]

    def tags_for(what: str) -> list[str]:
        if len(roles) < 2:
            return []
        a = ask(f"  Show {what} in which CVs? ({', '.join(role_ids)}; Enter = all)", "").strip()
        return [x for x in _list(a) if x in role_ids]

    master: dict = {"person": person, "summaries": {}, "experience": [], "education": [], "projects": [],
                    "certifications": [], "skills": [], "languages": []}

    print("\nSummary. 2-4 sentences about you as a professional: what you do, how you work, what you bring.\n"
          "Every claim should be backed by a bullet below. Leave empty to write it later.")
    for rid, name in roles:
        s = ask(f"Summary for {name}", "").strip()
        master["summaries"][rid] = t(s) if s else t("TODO: write a 2-4 sentence summary")

    print("\nWork experience, most recent first. Results with numbers beat duties ('Resolved ~25 tickets a day').")
    while _yes(ask, "Add a job?", default=not master["experience"]):
        job: dict = {"role": t(ask("  Job title", "").strip() or "TODO"),
                     "company": ask("  Employer", "").strip() or "TODO"}
        if start := _date(ask, "  Start (YYYY-MM)"):
            job["start"] = start
        end = _date(ask, "  End (YYYY-MM, Enter if you still work there)")
        job.update({"end": end} if end else {"ongoing": True})
        bullets = []
        while len(bullets) < 6:
            b = ask(f"  What you did or achieved #{len(bullets) + 1} (Enter to stop)", "").strip()
            if not b:
                break
            bullets.append({"text": t(b)})
        job["bullets"] = bullets or [{"text": t("TODO: 2-4 results or responsibilities")}]
        if tags := tags_for("this job"):
            job["tags"] = tags
        job["id"] = _unique(master["experience"], slug(f"{job['company']}-{_main(job['role'])}"))
        master["experience"].append(_ordered(job))

    print("\nEducation and training.")
    while _yes(ask, "Add a degree or course?", default=not master["education"]):
        ed: dict = {"degree": t(ask("  Degree or programme", "").strip() or "TODO"),
                    "school": ask("  School", "").strip() or "TODO"}
        if start := _date(ask, "  Start (YYYY-MM)"):
            ed["start"] = start
        end = _date(ask, "  End (YYYY-MM, Enter if in progress)")
        ed.update({"end": end} if end else {"ongoing": True})
        ed["id"] = _unique(master["education"], slug(ed["school"]))
        master["education"].append(_ordered(ed))

    print("\nCertifications (with a verification link if there is one).")
    while _yes(ask, "Add a certification?"):
        c: dict = {"name": ask("  Name", "").strip() or "TODO", "issuer": ask("  Issuer", "").strip() or None}
        if d := _date(ask, "  Date (YYYY-MM)"):
            c["date"] = d
        if u := ask("  Verification URL (optional)", "").strip():
            c["url"] = u
        c["id"] = _unique(master["certifications"], slug(c["name"]))
        master["certifications"].append(_ordered({k: v for k, v in c.items() if v is not None}))

    print("\nProjects that show your skills (home lab, open source, coursework with a result).")
    while _yes(ask, "Add a project?"):
        p: dict = {"name": t(ask("  Name", "").strip() or "TODO"),
                   "org": ask("  Tools used (e.g. Python, Wazuh)", "").strip() or None}
        if u := ask("  Link (optional)", "").strip():
            p["url"] = u
        b = ask("  What it does and what came out of it", "").strip()
        p["bullets"] = [{"text": t(b or "TODO: what it does and the result")}]
        if tags := tags_for("this project"):
            p["tags"] = tags
        p["id"] = _unique(master["projects"], slug(_main(p["name"])))
        master["projects"].append(_ordered({k: v for k, v in p.items() if v is not None}))

    print("\nSkills you could explain in an interview, in groups. One group per line, e.g.\n"
          "  Systems: Windows, Active Directory, Linux\nEnter on an empty line to stop.")
    while True:
        line = ask("  Group: skills", "").strip()
        if not line:
            break
        label, _, items = line.partition(":")
        if not items:
            label, items = "Skills", line
        master["skills"].append({"id": _unique(master["skills"], slug(label)), "label": t(label.strip()),
                                 "items": _list(items)})

    print("\nLanguages you speak, with level (CEFR A1-C2 or native), e.g. 'English C1, Spanish native'.")
    for item in _list(ask("Languages", "")):
        m = re.match(r"(.+?)\s+((?:[ABC][12])|native|nativo|nativ\w*)$", item, re.IGNORECASE)
        name, level = (m.group(1).strip(), m.group(2)) if m else (item, "")
        known = LANGUAGE_NAMES.get(_NAME_ALIASES.get(fold(name).lower(), ""), {})
        entry = {"name": {l: known.get(l, "TODO: translate") for l in langs} if known and len(langs) > 1
                 else known.get(langs[0], name) if known else t(name)}
        if re.fullmatch(r"[ABC][12]", level, re.IGNORECASE):
            entry["level"] = entry["cefr"] = level.upper()
        elif level:
            entry["level"] = {l: NATIVE.get(l, "TODO: translate") for l in langs} if len(langs) > 1 else NATIVE.get(langs[0], level)
        else:
            entry["level"] = "TODO"
        master["languages"].append(entry)

    tracks = [{
        "id": rid, "title": t(name), "languages": langs, "summary": rid,
        "include_tags": [rid] if len(roles) > 1 else [],
        "sections": list(SECTIONS),
        "limits": {"pages": 1, "bullets": 4, "projects": 4},
        "keywords": [],
    } for rid, name in roles]
    return master, tracks


def _main(text) -> str:
    return next(iter(text.values())) if isinstance(text, dict) else str(text)


def _unique(items: list[dict], base: str) -> str:
    used = {i["id"] for i in items}
    out, n = base or "item", 2
    while out in used:
        out, n = f"{base}-{n}", n + 1
    return out


def _ordered(d: dict) -> dict:
    """id first, bullets last: easier to read in the file."""
    head = {"id": d["id"]} if "id" in d else {}
    tail = {"bullets": d["bullets"]} if "bullets" in d else {}
    return head | {k: v for k, v in d.items() if k not in ("id", "bullets")} | tail


class _Dumper(yaml.SafeDumper):
    """Block style for structure; {en: ..., es: ...} texts and lists of plain values stay on one line."""


def _is_texts(d: dict) -> bool:
    return bool(d) and all(isinstance(k, str) and re.fullmatch(r"[a-z]{2}", k) for k in d)


_Dumper.add_representer(dict, lambda dumper, d: dumper.represent_mapping(
    "tag:yaml.org,2002:map", d.items(), flow_style=_is_texts(d) and len(str(d)) < 90))
_Dumper.add_representer(list, lambda dumper, l: dumper.represent_sequence(
    "tag:yaml.org,2002:seq", l, flow_style=all(isinstance(x, (str, int, float)) for x in l) and len(str(l)) < 120))


def dump(data) -> str:
    return yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=110)


def master_yaml(master: dict) -> str:
    master = {k: v for k, v in master.items() if v not in ([], {})} | {"person": master["person"]}
    order = ["person", "summaries", "experience", "education", "projects", "certifications", "skills", "languages"]
    return HEADER + "\n" + dump({k: master[k] for k in order if k in master})


def track_yaml(track: dict) -> str:
    return TRACK_HEADER.format(id=track["id"]) + dump(track)
