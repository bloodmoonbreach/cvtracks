"""Single-column, ATS-friendly HTML (open in a browser and print to PDF if you prefer)."""

from __future__ import annotations

from html import escape

from ..select import RItem, ResolvedCV
from . import Options, register

_CSS = """
:root{--accent:%(accent)s}
*{box-sizing:border-box}body{font:10.5pt/1.45 "Inter","Liberation Sans","Helvetica Neue",Arial,sans-serif;color:#1a1a1a;max-width:800px;margin:2rem auto;padding:0 1.5rem}
h1{font-size:22pt;margin:0}.headline{font-size:12pt;color:var(--accent);font-weight:600;margin:.1rem 0 .4rem}
.contact{color:#444;font-size:9.5pt}.contact a{color:inherit}
h2{font-size:11pt;text-transform:uppercase;letter-spacing:.04em;color:var(--accent);border-bottom:1px solid var(--accent);margin:1.1rem 0 .4rem;padding-bottom:.1rem}
.item{margin:.35rem 0 .6rem}.row{display:flex;justify-content:space-between;gap:1rem}.dates{color:#555;white-space:nowrap}
.meta{color:#555;font-size:9.5pt}ul{margin:.2rem 0 0 1.1rem;padding:0}li{margin:.1rem 0}
@media print{body{margin:0;max-width:none}a{text-decoration:none}}
"""


def _item(it: RItem) -> str:
    title = f"<strong>{escape(it.title)}</strong>" + (f" — {escape(it.org)}" if it.org else "")
    meta = " · ".join(escape(x) for x in (it.location, it.status, it.grade) if x)
    out = [f'<div class="item"><div class="row"><span>{title}</span><span class="dates">{escape(it.dates)}</span></div>']
    if meta:
        out.append(f'<div class="meta">{meta}</div>')
    if it.summary:
        out.append(f"<p>{escape(it.summary)}</p>")
    if it.bullets:
        out.append("<ul>" + "".join(f"<li>{escape(b)}</li>" for b in it.bullets) + "</ul>")
    out.append("</div>")
    return "".join(out)


@register("html", "html")
def render_html(cv: ResolvedCV, opts: Options) -> bytes:
    contacts = " · ".join(
        f'<a href="{escape(c.href)}">{escape(c.text)}</a>' if c.href else escape(c.text) for c in cv.contacts)
    if cv.extra:
        contacts += " · " + " · ".join(escape(x) for x in cv.extra)
    parts = [f'<!doctype html><html lang="{cv.lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
             f"<title>{escape(cv.name)} — {escape(cv.headline)}</title><style>{_CSS % {'accent': opts.accent}}</style></head><body>",
             f"<header><h1>{escape(cv.name)}</h1><div class=\"headline\">{escape(cv.headline)}</div><div class=\"contact\">{contacts}</div></header>"]
    for key in cv.sections:
        body = ""
        if key == "summary" and cv.summary:
            body = f"<p>{escape(cv.summary)}</p>"
        elif key in ("experience", "education", "projects"):
            body = "".join(_item(it) for it in getattr(cv, key))
        elif key == "certifications" and cv.certifications:
            body = "<ul>" + "".join(
                f"<li><strong>{escape(c.name)}</strong>" + (f" — {escape(c.issuer)}" if c.issuer else "")
                + (f" · {escape(c.date)}" if c.date else "") + "</li>" for c in cv.certifications) + "</ul>"
        elif key == "skills" and cv.skills:
            body = "<ul>" + "".join(f"<li><strong>{escape(g.label)}:</strong> {escape(', '.join(g.items))}</li>" for g in cv.skills) + "</ul>"
        elif key == "languages" and cv.languages:
            body = "<p>" + " · ".join(f"<strong>{escape(l.name)}</strong> — {escape(l.level)}" for l in cv.languages) + "</p>"
        if body:
            parts.append(f"<section><h2>{escape(cv.labels[key])}</h2>{body}</section>")
    parts.append("</body></html>")
    return "".join(parts).encode()
