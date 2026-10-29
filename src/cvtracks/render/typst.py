"""Typst source and PDF output (single column, real text, links kept: readable by ATS parsers).

All CV text is passed to Typst as string literals, never as markup, so characters like
# * _ $ @ [ ] in your data can't change the layout.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from ..select import RItem, ResolvedCV
from . import Options, register

_TEMPLATE = r"""
#let accent = rgb(@@ACCENT@@)
#set document(title: @@NAME@@ + " — " + @@HEADLINE@@, author: @@NAME@@)
#set page(paper: @@PAPER@@, margin: (x: 1.5cm, top: 1.3cm, bottom: 1.2cm))
#set text(font: @@FONTS@@, size: @@SIZE@@pt, lang: @@LANG@@, hyphenate: false)
#set par(justify: false, leading: 0.55em, spacing: 0.7em)
#set list(indent: 0.4em, body-indent: 0.5em, spacing: 0.45em)
#show link: it => it

#let muted(body) = text(fill: luma(85), body)
// sticky: a heading never ends up alone at the bottom of a page
#let section(title) = block(sticky: true, above: 1.1em, below: 0.6em, {
  text(size: 1.07em, weight: "bold", fill: accent, tracking: 0.04em, upper(title))
  v(-0.6em)
  line(length: 100%, stroke: 0.6pt + accent)
})
#let entry(title: "", org: "", meta: "", dates: "", summary: "", bullets: (), url: "") = block(breakable: false, spacing: 0.75em, {
  grid(columns: (1fr, auto), column-gutter: 1em,
    [#text(weight: "bold", title)#if org != "" [ — #org]],
    align(right, muted(dates)))
  if meta != "" { v(-0.45em); text(size: 9pt, muted(meta)) }
  if url != "" { v(-0.45em); text(size: 9pt, link(url, url)) }
  if summary != "" { v(-0.2em); summary }
  if bullets.len() > 0 { v(-0.2em); list(..bullets) }
})

#align(left)[
  #text(size: 20pt, weight: "bold", @@NAME@@) \
  #if @@HEADLINE@@ != "" [#text(size: 11.5pt, fill: accent, weight: "semibold", @@HEADLINE@@) \ ]
  #text(size: 9pt, muted(@@CONTACT_LINE@@))
]

@@BODY@@
"""


def _s(value: str) -> str:
    """A Typst string literal."""
    return '"' + (value or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def _arr(values: list[str]) -> str:
    if not values:
        return "()"
    return "(" + ", ".join(_s(v) for v in values) + ("," if len(values) == 1 else "") + ")"


def _contact_line(cv: ResolvedCV) -> str:
    parts = []
    for c in cv.contacts:
        parts.append(f"link({_s(c.href)}, {_s(c.text)})" if c.href else _s(c.text))
    parts += [_s(x) for x in cv.extra]
    if not parts:
        return '""'
    return "[" + " · ".join(f"#{p}" for p in parts) + "]"


def _entry(it: RItem) -> str:
    meta = " · ".join(x for x in (it.location, it.status, it.grade) if x)
    return (f"#entry(title: {_s(it.title)}, org: {_s(it.org)}, meta: {_s(meta)}, dates: {_s(it.dates)}, "
            f"summary: {_s(it.summary)}, bullets: {_arr(it.bullets)}, url: {_s(it.url)})")


def to_typst(cv: ResolvedCV, opts: Options) -> str:
    body: list[str] = []
    for key in cv.sections:
        block: list[str] = []
        if key == "summary" and cv.summary:
            block = [f"#{_s(cv.summary)}"]
        elif key in ("experience", "education", "projects"):
            block = [_entry(it) for it in getattr(cv, key)]
        elif key == "certifications" and cv.certifications:
            rows = []
            for c in cv.certifications:
                right = c.date
                left = f"text(weight: \"bold\", {_s(c.name)})" + (f" + \" — \" + {_s(c.issuer)}" if c.issuer else "")
                if c.credential_id:
                    left += f" + muted(\" · {cv.labels['credential']} \" + {_s(c.credential_id)})"
                rows.append(f"[#({left})], align(right, muted({_s(right)}))")
            block = ["#grid(columns: (1fr, auto), column-gutter: 1em, row-gutter: 0.55em,\n  "
                     + ",\n  ".join(rows) + ")"]
        elif key == "skills" and cv.skills:
            rows = [f"[#text(weight: \"bold\", {_s(g.label)})], [#{_s(', '.join(g.items))}]" for g in cv.skills]
            block = ["#grid(columns: (auto, 1fr), column-gutter: 0.8em, row-gutter: 0.55em,\n  " + ",\n  ".join(rows) + ")"]
        elif key == "languages" and cv.languages:
            items = [f"[#text(weight: \"bold\", {_s(l.name)}) — #{_s(l.level)}]" for l in cv.languages]
            block = ["#(" + ", ".join(items) + ").join(h(1.2em))" if len(items) > 1 else items[0].strip("[]")]
        if block:
            body.append(f"#section({_s(cv.labels[key])})")
            body += block
    fonts = [opts.font] if opts.font else []
    fonts += ["Inter", "Liberation Sans", "Carlito", "DejaVu Sans", "Libertinus Serif"]
    values = {"ACCENT": _s(opts.accent), "FONTS": _arr(fonts), "PAPER": _s(opts.paper), "LANG": _s(cv.lang),
              "CONTACT_LINE": _contact_line(cv), "HEADLINE": _s(cv.headline), "NAME": _s(cv.name),
              "BODY": "\n".join(body), "SIZE": f"{opts.size:g}"}
    # One pass, so placeholder-like words inside the CV text are never substituted.
    return re.sub(r"@@([A-Z_]+)@@", lambda m: values[m.group(1)], _TEMPLATE).lstrip()


@register("typst", "typ")
def render_typst(cv: ResolvedCV, opts: Options) -> bytes:
    return to_typst(cv, opts).encode()


@register("pdf", "pdf", needs="typst")
def render_pdf(cv: ResolvedCV, opts: Options) -> bytes:
    try:
        import typst
    except ImportError as e:
        raise RuntimeError("PDF output needs the 'typst' package: pip install 'cvtracks[pdf]'") from e
    import dataclasses
    import sys

    def compile_at(size: float) -> bytes:
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "cv.typ"
            src.write_text(to_typst(cv, dataclasses.replace(opts, size=size)), encoding="utf-8")
            return typst.compile(str(src))

    pdf = compile_at(opts.size)
    if not opts.max_pages:
        return pdf
    size = opts.size
    while page_count(pdf) > opts.max_pages and size > 8.6 + 1e-9:
        size = round(size - 0.2, 1)
        pdf = compile_at(size)
    if page_count(pdf) > opts.max_pages:
        print(f"cvtracks: {cv.track} [{cv.lang}] is {page_count(pdf)} pages even at {size:g}pt "
              f"(limit {opts.max_pages}); trim bullets or lower the track's limits", file=sys.stderr)
    return pdf


def page_count(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page(?!s)", pdf))
