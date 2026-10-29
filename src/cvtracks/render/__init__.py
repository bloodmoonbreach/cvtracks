"""Output formats. Each renderer turns a ResolvedCV into bytes; add one with @register."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..select import ResolvedCV


@dataclass
class Options:
    paper: str = "a4"
    font: str | None = None
    accent: str = "#1f3a5f"
    size: float = 9.8  # base font size in pt
    max_pages: int | None = None  # PDF: shrink the font a little until it fits (down to 8.6pt)


@dataclass
class Renderer:
    name: str
    ext: str
    func: Callable[[ResolvedCV, Options], bytes]
    needs: str | None = None  # optional dependency, for error messages


RENDERERS: dict[str, Renderer] = {}


def register(name: str, ext: str, needs: str | None = None):
    def deco(func):
        RENDERERS[name] = Renderer(name, ext, func, needs)
        return func
    return deco


def render(cv: ResolvedCV, fmt: str, options: Options | None = None) -> bytes:
    if fmt not in RENDERERS:
        raise KeyError(f"unknown format {fmt!r}; available: {', '.join(sorted(RENDERERS))}")
    return RENDERERS[fmt].func(cv, options or Options())


from . import html, jsonresume, markdown, typst  # noqa: E402,F401  (register built-ins)
