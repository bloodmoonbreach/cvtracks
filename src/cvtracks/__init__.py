"""One master file of facts → every CV you need."""

from .lint import lint
from .loader import load_master, load_track, load_tracks
from .render import RENDERERS, Options, register, render
from .select import resolve
from .tailor import tailor

__all__ = ["load_master", "load_track", "load_tracks", "resolve", "render", "register", "RENDERERS", "Options",
           "lint", "tailor"]
__version__ = "0.1.0"
