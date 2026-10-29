"""Draft a master.yaml from the text of an existing CV with a language model (opt-in).

Works with any OpenAI-compatible chat endpoint: Ollama on your own machine (nothing leaves it), or a hosted
API with your own key (your CV is sent to that provider). The model only restructures what the CV says:

- the prompt forbids new facts, and anything missing becomes `TODO`;
- the result must load as a valid master file;
- every employer, school and certification it names must appear in the CV text, otherwise it is reported;
- address, nationality, birth date, photo and similar fields are dropped, whatever the CV contained.

Always read the draft before using it.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import yaml

from .loader import load_master
from .model import ModelError
from .setup import HEADER, dump
from .text import fold

PROMPT = """You convert a CV into a YAML file. Output only the YAML, in one ```yaml block.

Rules:
- Copy facts from the CV. Never add an employer, date, number, tool, grade or achievement that the CV doesn't state.
- If something the format needs is missing, write TODO.
- Keep the CV's wording for bullets; you may shorten, never embellish.
- Leave out: address, city, nationality, citizenship, birth date, age, gender, marital status, photo, ID numbers.
- Dates as YYYY or YYYY-MM. A current job gets `ongoing: true` instead of `end`.
- Write texts in {lang}; translate the CV if it is in another language.

Format:
```yaml
person: {{name: ..., email: ..., phone: ..., linkedin: <handle>, github: <handle>, website: ...}}
summaries:
  main: <the CV's own summary or profile text, else TODO>
experience:
  - {{id: <short-id>, role: ..., company: ..., start: 2022-09, end: 2025-06, bullets: [<text>, <text>]}}
education:
  - {{id: <short-id>, degree: ..., school: ..., start: 2020, end: 2022}}
projects:
  - {{id: <short-id>, name: ..., org: <tools used>, url: ..., bullets: [<text>]}}
certifications:
  - {{id: <short-id>, name: ..., issuer: ..., date: 2025-11, credential_id: ..., url: ...}}
skills:
  - {{id: <short-id>, label: <group name>, items: [..., ...]}}
languages:
  - {{name: ..., level: <as written>, cefr: <A1..C2 if stated>}}
```
Omit any section the CV doesn't have. Omit keys whose value you don't know, except required ones (write TODO).

CV:
<<<CV
{cv}
CV>>>"""

_PRIVATE_PERSON = {"location", "address", "nationality", "citizenship", "birth", "birthday", "birth_date",
                   "date_of_birth", "age", "gender", "photo", "marital_status", "extra"}
_ALLOWED = {
    "person": {"name", "email", "phone", "website", "github", "linkedin"},
    "entry": {"id", "title", "role", "degree", "name", "org", "company", "school", "start", "end", "ongoing",
              "status", "grade", "url", "summary", "bullets", "tags", "priority", "keywords"},
    "certifications": {"id", "name", "issuer", "date", "credential_id", "url"},
    "skills": {"id", "label", "items"},
    "languages": {"name", "level", "cefr"},
}


@dataclass
class LLMConfig:
    base_url: str = "http://localhost:11434/v1"
    model: str = ""
    api_key: str | None = None
    timeout: float = 600

    @property
    def is_local(self) -> bool:
        host = (urlparse(self.base_url).hostname or "").lower()
        return host in ("localhost", "127.0.0.1", "::1") or host.endswith(".local") or \
            bool(re.match(r"^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.)", host))


@dataclass
class Draft:
    yaml: str
    warnings: list[str] = field(default_factory=list)


def chat(cfg: LLMConfig, prompt: str) -> str:
    """One user message to an OpenAI-compatible /chat/completions endpoint; returns the reply text.

    Asks for no "thinking" first: a reasoning model otherwise spends its whole budget reasoning about a
    long CV (Ollama runs a small context window by default). Endpoints that reject the option get the
    plain request.
    """
    if not cfg.model:
        raise ValueError("no model set")
    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"
    base = {"model": cfg.model, "temperature": 0, "messages": [{"role": "user", "content": prompt}]}
    for body in ({**base, "reasoning_effort": "none"}, base):
        req = urllib.request.Request(cfg.base_url.rstrip("/") + "/chat/completions", json.dumps(body).encode(), headers)
        try:
            with urllib.request.urlopen(req, timeout=cfg.timeout) as r:
                data = json.load(r)
            break
        except urllib.error.HTTPError as e:
            detail = e.read()[:300].decode(errors="replace")
            if e.code == 400 and "reasoning_effort" in body:
                continue
            raise RuntimeError(f"model endpoint answered HTTP {e.code}: {detail}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise RuntimeError(f"could not reach {cfg.base_url}: {getattr(e, 'reason', e)}") from e
    try:
        choice = data["choices"][0]
        text = choice["message"].get("content") or ""
    except (KeyError, IndexError, TypeError, AttributeError) as e:
        raise RuntimeError(f"unexpected reply from the model endpoint: {str(data)[:300]}") from e
    if not text.strip() and choice.get("finish_reason") == "length":
        raise RuntimeError("the model ran out of room before answering; try a model without 'thinking', "
                           "or a larger context window")
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _yaml_block(reply: str) -> str:
    m = re.search(r"```(?:ya?ml)?\s*\n(.*?)```", reply, re.DOTALL)
    return (m.group(1) if m else reply).strip()


# Optional keys: a TODO there is noise, not a reminder.
_OPTIONAL = {"phone", "github", "linkedin", "website", "email", "issuer", "credential_id", "url", "cefr", "org",
             "status", "grade", "start", "end", "date", "summary"}
# Keys holding text that differs per language.
_TEXT_KEYS = {"role", "degree", "title", "name", "label", "status", "summary", "level"}


def _todo(v) -> bool:
    return isinstance(v, str) and v.strip().upper().startswith("TODO")


def _per_lang(v, langs: list[str]):
    if len(langs) < 2 or not isinstance(v, str) or _todo(v):
        return v
    return {langs[0]: v, **{l: "TODO: translate" for l in langs[1:]}}


def _clean(data: dict, warnings: list[str], langs: list[str] | None = None) -> dict:
    from .setup import LANGUAGE_NAMES, NATIVE, _NAME_ALIASES
    langs = langs or ["en"]
    person = data.get("person") or {}
    dropped = sorted(k for k in person if k in _PRIVATE_PERSON or k not in _ALLOWED["person"])
    if dropped:
        warnings.append(f"left out of person: {', '.join(dropped)} (not needed on a CV)")
    out: dict = {"person": {k: v for k, v in person.items() if k in _ALLOWED["person"] and v not in (None, "")}}
    out["person"] = {k: v for k, v in out["person"].items() if not (k in _OPTIONAL and _todo(v))}
    name = str(out["person"].get("name") or "TODO")
    out["person"]["name"] = name.title() if name.isupper() else name
    if isinstance(data.get("summaries"), dict):
        out["summaries"] = {str(k): _per_lang(v, langs) for k, v in data["summaries"].items() if v}
    for section in ("experience", "education", "projects", "certifications", "skills", "languages"):
        items = data.get(section)
        if not isinstance(items, list):
            continue
        allowed = _ALLOWED.get(section, _ALLOWED["entry"])
        clean, seen = [], set()
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            item = {k: v for k, v in item.items()
                    if k in allowed and v not in (None, "", []) and not (k in _OPTIONAL and _todo(v))}
            if "id" in allowed:
                base = re.sub(r"[^a-z0-9]+", "-", fold(str(item.get("id") or f"{section}-{i}")).lower()).strip("-")
                uid, n = base or f"{section}-{i}", 2
                while uid in seen:
                    uid, n = f"{base}-{n}", n + 1
                seen.add(uid)
                item["id"] = uid
            for k in ("start", "end", "date"):
                if k in item:
                    item[k] = str(item[k])
            if section == "skills":
                item.setdefault("label", "Skills")
                item["items"] = [str(x) for x in item.get("items") or []]
            if section == "languages":
                known = LANGUAGE_NAMES.get(_NAME_ALIASES.get(fold(str(item.get("name", ""))).lower(), ""))
                if known:
                    item["name"] = {l: known.get(l, "TODO: translate") for l in langs} if len(langs) > 1 else known.get(langs[0], item["name"])
                level = str(item.get("level", ""))
                if re.fullmatch(r"[ABC][12]", level.upper()):
                    item["level"] = item["cefr"] = level.upper()
                elif re.match(r"(native|nativ|mother)", fold(level).lower()):
                    item["level"] = {l: NATIVE.get(l, "TODO: translate") for l in langs} if len(langs) > 1 else NATIVE.get(langs[0], level)
            for k in _TEXT_KEYS & set(item):
                if not (section == "languages" and k in ("name", "level")) and not (section == "certifications" and k == "name"):
                    item[k] = _per_lang(item[k], langs)
            if isinstance(item.get("bullets"), list):
                item["bullets"] = [_per_lang(b, langs) if isinstance(b, str) else b for b in item["bullets"]]
            clean.append(item)
        if clean:
            out[section] = clean
    return out


def _not_in_cv(data: dict, cv: str) -> list[str]:
    """Names of employers, schools and certifications that the CV text doesn't contain."""
    text = re.sub(r"\s+", " ", fold(cv).lower())
    missing = []
    for section, keys in (("experience", ("company", "org")), ("education", ("school", "org")),
                          ("certifications", ("name",))):
        for item in data.get(section, []):
            for k in keys:
                v = item.get(k)
                if isinstance(v, str) and v != "TODO" and re.sub(r"\s+", " ", fold(v).lower()) not in text:
                    missing.append(f"{section}: {v!r} is not in the CV text; check it")
    return missing


def draft_master(cv_text: str, cfg: LLMConfig, langs: list[str] | None = None) -> Draft:
    langs = langs or ["en"]
    reply = chat(cfg, PROMPT.format(cv=cv_text.strip()[:30000], lang=langs[0]))
    try:
        data = yaml.safe_load(_yaml_block(reply))
    except yaml.YAMLError as e:
        raise RuntimeError(f"the model didn't return valid YAML ({e}); try again or use the interview") from e
    if not isinstance(data, dict):
        raise RuntimeError("the model didn't return a master file; try again or use the interview")
    warnings: list[str] = []
    data = _clean(data, warnings, langs)
    warnings += _not_in_cv(data, cv_text)
    text = HEADER + "# Drafted by a language model from your CV. Read every line before using it.\n\n" + dump(data)
    # Must load like a hand-written file.
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(text)
    try:
        load_master(f.name)
    except ModelError as e:
        warnings.append(f"the draft doesn't load yet: {e}")
    finally:
        Path(f.name).unlink(missing_ok=True)
    return Draft(text, warnings)


def read_cv(path: str | Path) -> str:
    """Text of a CV file: .txt/.md as is, .pdf through pypdf if installed."""
    p = Path(path).expanduser()
    if p.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            raise SystemExit("cvtracks: reading PDFs needs `pip install pypdf`; or save your CV as text and pass that")
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(p)).pages)
    return p.read_text(encoding="utf-8", errors="replace")
