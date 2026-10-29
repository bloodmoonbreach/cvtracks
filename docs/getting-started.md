# Getting started (5 minutes)

By the end you'll have your facts in one file and a PDF CV built from it. Adding a second version for another
role, or a second language, is then a few lines.

## 1. Install (1 minute)

You need Python 3.11 or newer (`python3 --version`).

```bash
pip install "cvtracks[pdf] @ git+https://github.com/bloodmoonbreach/cvtracks"
```

`[pdf]` adds the Typst engine for PDFs; no LaTeX or system packages needed. On Linux distributions that
block system-wide pip, use `pipx install …` or a virtual environment.

## 2. Create your workspace (3 minutes)

Pick a folder **outside** any public git repository: this is your personal data.

```bash
cvtracks init ~/my-cv
```

A short interview asks for:

1. your contact details (no address, age or nationality: they don't belong on an EU CV),
2. the languages your CVs should be in (`en`, or `en, es`…),
3. one to five target roles (each becomes a CV version, a *track*),
4. a short summary per role (or skip it and write it later),
5. your jobs, education, certifications and projects,
6. your skills in groups (`Systems: Windows, Active Directory`) and the languages you speak.

Press Enter to skip anything. What you skip becomes `TODO` in the file; nothing is made up.

**Already have a CV?** Let a language model copy it into the format instead of typing:

```bash
# Local, nothing leaves your computer (needs Ollama: https://ollama.com, then `ollama pull gemma3:12b`)
cvtracks init ~/my-cv --from-cv my-cv.pdf --model gemma3:12b --langs en,es

# Or any OpenAI-compatible API with your own key (your CV is sent to that provider)
export OPENAI_API_KEY=...
cvtracks init ~/my-cv --from-cv my-cv.pdf --llm-url https://api.openai.com/v1 \
    --model gpt-4.1-mini --api-key-env OPENAI_API_KEY
```

The model only restructures what your CV says. Address, nationality and birth date are dropped, and any
employer, school or certificate name that doesn't appear in your CV is reported. Read the draft anyway.
PDFs need `pip install pypdf`; a scanned PDF (an image) has no text to read, so export it as text first.

## 3. Check and build (1 minute)

```bash
cd ~/my-cv
cvtracks lint        # lists TODOs, missing translations, typos, impossible dates
cvtracks build       # every track, in every language, as PDF → out/
```

Open the PDF in `out/`. Then edit `master.yaml` in any text editor, and run `lint` and `build` again. That's
the whole loop.

## Next steps

- **Translate.** Replace each `TODO: translate`. Lint reports any text still missing in a language a track
  needs.
- **Write better bullets.** Results with numbers ("Cut repeat password tickets by 40%") beat duties
  ("Responsible for password resets").
- **Add keywords per role.** In `tracks/<role>.yaml`, list the terms employers screen for. Lint then tells
  you which ones your CV never mentions. Add them to `master.yaml` only if they're true.
- **Tailor to one job post** without inventing anything: `cvtracks tailor -t <role> --job post.txt`. It
  reorders your bullets and projects toward the post and lists the post's terms your file doesn't contain.
- **Other formats:** `cvtracks build -f pdf,md,html,json` (`json` is [JSON Resume](https://jsonresume.org)).
- Every key and option is in the [format reference](format.md).
