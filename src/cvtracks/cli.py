"""cvtracks: one master file of facts → every CV you need (tracks × languages × formats).

    cvtracks init [DIR]                    create your workspace: a short interview (or --example, --from-cv)
    cvtracks tracks                        list tracks
    cvtracks build [--track T] [--lang L]  write CVs to out/
    cvtracks lint                          check facts, translations, typos, keywords
    cvtracks tailor -t T --job FILE        reorder a track for one job post and report gaps

The workspace is a folder with master.yaml and tracks/*.yaml (default: current folder, or $CVTRACKS_DIR).
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

from . import __version__
from .lint import lint
from .loader import load_master, load_tracks
from .model import ModelError
from .render import RENDERERS, Options, render
from .select import resolve
from .tailor import tailor
from .text import fold

EXAMPLES = Path(__file__).parent / "examples"


def _workspace(args) -> Path:
    return Path(args.dir or os.environ.get("CVTRACKS_DIR") or ".").expanduser().resolve()


def _load(ws: Path):
    master_file = ws / "master.yaml"
    if not master_file.exists():
        raise SystemExit(f"cvtracks: no master.yaml in {ws} (run `cvtracks init {ws}` or pass --dir)")
    return load_master(master_file), load_tracks(ws / "tracks")


def _file_stem(pattern: str | None, name: str, track: str, lang: str, suffix: str = "") -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "_", fold(name)).strip("_").title().replace("_", "_")
    stem = (pattern or "{name}_CV_{track}_{lang}").format(name=safe, track=track, lang=lang.upper())
    return re.sub(r"[^\w.-]+", "_", stem) + suffix


def _formats(value: str) -> list[str]:
    fmts = [f.strip() for f in value.split(",") if f.strip()]
    bad = [f for f in fmts if f not in RENDERERS]
    if bad:
        raise SystemExit(f"cvtracks: unknown format(s) {bad}; available: {', '.join(sorted(RENDERERS))}")
    return fmts


def _ask(question: str, default: str = "") -> str:
    try:
        a = input(f"{question}{f' [{default}]' if default else ''}: ")
    except EOFError:
        raise SystemExit("\ncvtracks: interview cancelled; nothing was written")
    return a or default


def _write_workspace(target: Path, master_text: str, tracks: list[dict]) -> None:
    from .setup import track_yaml
    (target / "tracks").mkdir(parents=True, exist_ok=True)
    (target / "master.yaml").write_text(master_text, encoding="utf-8")
    for t in tracks:
        (target / "tracks" / f"{t['id']}.yaml").write_text(track_yaml(t), encoding="utf-8")


def _roles_only(langs: list[str]) -> list[dict]:
    from .model import SECTIONS
    from .setup import slug
    roles = []
    print("Target roles: one CV version (track) per role, e.g. 'IT Support Technician'. Enter to stop.")
    while len(roles) < 5:
        name = _ask(f"Role {len(roles) + 1}").strip()
        if not name:
            if roles:
                break
            continue
        roles.append((slug(name), name))
    title = (lambda n: n) if len(langs) == 1 else (lambda n: {langs[0]: n, **{l: "TODO: translate" for l in langs[1:]}})
    return [{"id": rid, "title": title(name), "languages": langs, "summary": "main",
             "include_tags": [], "sections": list(SECTIONS), "limits": {"pages": 1, "bullets": 4, "projects": 4},
             "keywords": []} for rid, name in roles]


def cmd_init(args) -> int:
    target = Path(args.path or ".").expanduser()
    if (target / "master.yaml").exists() and not args.force:
        print(f"cvtracks: {target}/master.yaml already exists (use --force to overwrite it)", file=sys.stderr)
        return 1
    target.mkdir(parents=True, exist_ok=True)
    interactive = sys.stdin.isatty() and sys.stdout.isatty()

    if args.example or (not interactive and not args.from_cv):
        shutil.copy(EXAMPLES / "master.yaml", target / "master.yaml")
        shutil.copytree(EXAMPLES / "tracks", target / "tracks", dirs_exist_ok=True)
        print(f"Created {target}/master.yaml and {target}/tracks/ with an example (a fictional person).\n"
              "Replace it with your facts, then run `cvtracks lint` and `cvtracks build`.")
        return 0

    if args.from_cv:
        from .draft import LLMConfig, draft_master, read_cv
        cfg = LLMConfig(base_url=args.llm_url or os.environ.get("CVTRACKS_LLM_URL") or "http://localhost:11434/v1",
                        model=args.model or os.environ.get("CVTRACKS_LLM_MODEL") or "",
                        api_key=os.environ.get(args.api_key_env) if args.api_key_env else None)
        if not cfg.model:
            raise SystemExit("cvtracks: --from-cv needs a model: --model gemma3:12b (Ollama) or set CVTRACKS_LLM_MODEL")
        cv_text = read_cv(args.from_cv)
        if len(cv_text.strip()) < 200:
            raise SystemExit("cvtracks: that CV has almost no text (a scanned PDF?); save it as text and try again")
        if not cfg.is_local:
            print(f"Your CV will be sent to {urlparse(cfg.base_url).hostname} ({cfg.model}). "
                  "Their privacy terms apply to it.")
            if not args.yes and not (interactive and _ask("Continue? [y/N]").strip().lower().startswith("y")):
                return 1
        langs = [l.strip() for l in (args.langs or "en").split(",") if l.strip()]
        tracks = _roles_only(langs) if interactive else []
        if not tracks:  # one general CV; add a track per target role later
            from .model import SECTIONS
            tracks = [{"id": "main", "title": "TODO: your target role", "languages": langs, "summary": "main",
                       "sections": list(SECTIONS), "limits": {"pages": 1, "bullets": 4, "projects": 4}, "keywords": []}]
        print(f"Drafting master.yaml with {cfg.model}... (a local model can take a few minutes)")
        try:
            d = draft_master(cv_text, cfg, langs)
        except (RuntimeError, ValueError) as e:
            raise SystemExit(f"cvtracks: {e}")
        _write_workspace(target, d.yaml, tracks)
        print(f"\nWrote {target}/master.yaml and {len(tracks)} track(s) in {target}/tracks/.")
        for w in d.warnings:
            print(f"  ⚠ {w}")
        print("Read the whole draft: the model may have misread or reworded something. "
              "Then `cvtracks lint` lists what is still TODO.")
        return 0

    from .setup import interview, master_yaml
    print(f"cvtracks: let's create your CV workspace in {target.resolve()}.\n"
          "Answer what you can; Enter skips. Anything skipped becomes TODO, nothing is made up.\n")
    master, tracks = interview(_ask)
    _write_workspace(target, master_yaml(master), tracks)
    print(f"\nWrote {target}/master.yaml and {len(tracks)} track(s) in {target}/tracks/.\n"
          f"Next: open master.yaml, fill the TODOs, then\n  cd {target}\n  cvtracks lint\n  cvtracks build")
    return 0


def cmd_tracks(args) -> int:
    master, tracks = _load(_workspace(args))
    for t in tracks.values():
        from . import i18n
        print(f"{t.id:<14} {', '.join(t.languages):<8} {i18n.text(t.title, t.languages[0])}")
    return 0


def cmd_build(args) -> int:
    ws = _workspace(args)
    master, tracks = _load(ws)
    chosen = args.track or list(tracks)
    unknown = [t for t in chosen if t not in tracks]
    if unknown:
        raise SystemExit(f"cvtracks: unknown track(s) {unknown}; have: {', '.join(tracks)}")
    out = Path(args.out).expanduser() if args.out else ws / "out"
    out.mkdir(parents=True, exist_ok=True)
    for tid in chosen:
        track = tracks[tid]
        opts = Options(paper=args.paper, font=args.font, max_pages=track.limits.get("pages"))
        langs = [l for l in (args.lang.split(",") if args.lang else track.languages)]
        for lang in langs:
            cv = resolve(master, track, lang)
            for fmt in _formats(args.format):
                r = RENDERERS[fmt]
                path = out / _file_stem(track.file_name, master.person.name, tid, lang, f".{r.ext}")
                path.write_bytes(render(cv, fmt, opts))
                print(path)
    return 0


def cmd_lint(args) -> int:
    ws = _workspace(args)
    master, tracks = _load(ws)
    issues = lint(master, tracks, base_dir=ws)
    for i in sorted(issues, key=lambda i: ("error", "warning", "info").index(i.level)):
        if i.level != "info" or args.verbose:
            print(i)
    errors = sum(i.level == "error" for i in issues)
    warnings = sum(i.level == "warning" for i in issues)
    print(f"\n{errors} error(s), {warnings} warning(s)")
    return 1 if errors or (args.strict and warnings) else 0


def cmd_tailor(args) -> int:
    ws = _workspace(args)
    master, tracks = _load(ws)
    if args.track not in tracks:
        raise SystemExit(f"cvtracks: unknown track {args.track!r}; have: {', '.join(tracks)}")
    track = tracks[args.track]
    if args.job == "-":
        job_text = sys.stdin.read()
    elif args.job.startswith(("http://", "https://")):
        try:
            from remote_eligibility.fetch import fetch
        except ImportError:
            raise SystemExit("cvtracks: fetching URLs needs remote-eligibility installed; save the post to a file instead")
        job_text = fetch(args.job)
    else:
        job_text = Path(args.job).read_text(encoding="utf-8", errors="replace")

    scores, report = tailor(master, track, job_text)
    lang = args.lang or track.languages[0]
    cv = resolve(master, track, lang, scores)
    slug = args.name or re.sub(r"[^a-z0-9]+", "-", fold(Path(args.job).stem if args.job not in ("-",) and "://" not in args.job else "job")).strip("-")
    out = (Path(args.out).expanduser() if args.out else ws / "out" / "tailored")
    out.mkdir(parents=True, exist_ok=True)
    opts = Options(paper=args.paper, font=args.font, max_pages=track.limits.get("pages"))
    for fmt in _formats(args.format):
        r = RENDERERS[fmt]
        path = out / (_file_stem(track.file_name, master.person.name, track.id, lang) + f"_{slug}.{r.ext}")
        path.write_bytes(render(cv, fmt, opts))
        print(path)

    if report.safety and report.safety.get("findings"):
        print(f"\n⚠ the job post contained text aimed at AI tools (risk: {report.safety['risk']}); it was ignored:")
        for f in report.safety["findings"]:
            word = f" (trap word: “{f['trap_word']}”, don't use it)" if f.get("trap_word") else ""
            print(f"   - {f['category']}{word}: {f['text']}")
    print(f"\nMatched ({len(report.matched)}): {', '.join(report.matched) or '-'}")
    if report.top_items:
        print("Moved up: " + ", ".join(f"{k} ({v:g})" for k, v in report.top_items[:6]))
    if report.gaps:
        print(f"In the post but not in your master ({len(report.gaps)}): {', '.join(report.gaps)}")
        print("  → nothing was added. If any of these are true for you, add them to master.yaml.")
    if report.hidden:
        print(f"Relevant but excluded by track '{track.id}': {', '.join(report.hidden)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cvtracks", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, out=True):
        p.add_argument("-d", "--dir", help="workspace folder (default: . or $CVTRACKS_DIR)")
        if out:
            p.add_argument("-f", "--format", default="pdf", help=f"comma-separated: {', '.join(sorted(RENDERERS))} (default pdf)")
            p.add_argument("-o", "--out", help="output folder (default: <workspace>/out)")
            p.add_argument("--paper", default="a4", choices=("a4", "us-letter"))
            p.add_argument("--font", help="font family to try first")

    p = sub.add_parser("init", help="create your workspace (interview, --example or --from-cv)")
    p.add_argument("path", nargs="?")
    p.add_argument("--force", action="store_true", help="overwrite an existing master.yaml")
    p.add_argument("--example", action="store_true", help="copy the example workspace instead of the interview")
    p.add_argument("--from-cv", metavar="FILE", help="draft master.yaml from your CV (.txt, .md, .pdf) with a language model")
    p.add_argument("--langs", help="CV languages, main first (default en), with --from-cv")
    p.add_argument("--llm-url", help="OpenAI-compatible endpoint (default http://localhost:11434/v1, Ollama)")
    p.add_argument("--model", help="model name, e.g. gemma3:12b")
    p.add_argument("--api-key-env", metavar="VAR", help="environment variable holding the API key, for hosted APIs")
    p.add_argument("-y", "--yes", action="store_true", help="don't ask before sending the CV to a non-local endpoint")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("tracks", help="list tracks")
    common(p, out=False)
    p.set_defaults(func=cmd_tracks)

    p = sub.add_parser("build", help="build CVs")
    common(p)
    p.add_argument("-t", "--track", action="append", help="track id (repeatable; default: all)")
    p.add_argument("-l", "--lang", help="comma-separated languages (default: the track's)")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("lint", help="check the master and tracks")
    common(p, out=False)
    p.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    p.add_argument("-v", "--verbose", action="store_true", help="show info-level notes")
    p.set_defaults(func=cmd_lint)

    p = sub.add_parser("tailor", help="reorder a track for one job post (no new text)")
    common(p)
    p.add_argument("-t", "--track", required=True)
    p.add_argument("-j", "--job", required=True, help="job post: file, URL (needs remote-eligibility) or - for stdin")
    p.add_argument("-l", "--lang")
    p.add_argument("-n", "--name", help="short name for the output file (default: from the job file name)")
    p.set_defaults(func=cmd_tailor)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except ModelError as e:
        print(f"cvtracks: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
