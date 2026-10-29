"""Markdown / plain text: for pasting into application forms and quick review."""

from __future__ import annotations

from ..select import RItem, ResolvedCV
from . import Options, register


def _item(it: RItem) -> list[str]:
    head = f"**{it.title}**" + (f" — {it.org}" if it.org else "")
    meta = " · ".join(x for x in (it.dates, it.location, it.status, it.grade) if x)
    out = [head + (f"  \n{meta}" if meta else "")]
    if it.url:
        out.append(it.url)
    if it.summary:
        out.append(it.summary)
    out += [f"- {b}" for b in it.bullets]
    return out


def to_markdown(cv: ResolvedCV) -> str:
    lines = [f"# {cv.name}"]
    if cv.headline:
        lines.append(f"**{cv.headline}**")
    lines.append(" · ".join([c.text for c in cv.contacts] + cv.extra))
    for key in cv.sections:
        body: list[str] = []
        if key == "summary" and cv.summary:
            body = [cv.summary]
        elif key in ("experience", "education", "projects"):
            for it in getattr(cv, key):
                body += _item(it) + [""]
        elif key == "certifications":
            body = [f"- **{c.name}**" + (f" — {c.issuer}" if c.issuer else "") + (f" ({c.date})" if c.date else "")
                    + (f" · {cv.labels['credential']} {c.credential_id}" if c.credential_id else "") for c in cv.certifications]
        elif key == "skills":
            body = [f"- **{g.label}:** {', '.join(g.items)}" if g.label else f"- {', '.join(g.items)}" for g in cv.skills]
        elif key == "languages":
            body = [f"- {l.name}: {l.level}" + (f" ({l.cefr})" if l.cefr and l.cefr not in l.level else "") for l in cv.languages]
        if body:
            lines += ["", f"## {cv.labels[key]}", ""] + body
    return "\n".join(lines).rstrip() + "\n"


@register("md", "md")
def render_md(cv: ResolvedCV, opts: Options) -> bytes:
    return to_markdown(cv).encode()
