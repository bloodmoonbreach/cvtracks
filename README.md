# cvtracks

**One master file of facts → every CV you need.**

Most people keep five slightly different CVs in five files, and they drift: a certificate added to one but not the others, a typo fixed in English but not in Spanish, dates that no longer match. `cvtracks` keeps every fact **once** in `master.yaml`, and small **track** files decide what each version shows.

```
master.yaml          every job, project, certificate, skill — in every language you need
tracks/soc.yaml      "Junior SOC Analyst": these tags, this order, 1 page, EN + ES
tracks/helpdesk.yaml "IT Support": other tags, other order, ES + EN
        │
        ▼  cvtracks build
out/  Jane_Doe_CV_SOC_EN.pdf  …_SOC_ES.pdf  …_HelpDesk_ES.pdf  …  (+ .md .html .json .typ)
```

- **Multilingual facts:** any text can be `{en: …, es: …, ro: …}`. Section titles and dates are localised (`Sep 2025 – Present`, `sept 2025 – Actualidad`).
- **Tracks** pick content by tags, order sections and skill groups, cap projects/bullets, and set a page limit. The PDF shrinks the font slightly until it fits.
- **Formats:** PDF via [Typst](https://typst.app) (single column, real text, links kept, readable by ATS parsers), HTML, Markdown, Typst source, and [JSON Resume](https://jsonresume.org) for other tools and themes. New formats are one function (`@register`).
- **Lint:** missing translations, leftover `TODO`s, common typos (EN/ES), impossible dates, missing evidence files, CVs over their word limit, and **keywords screeners look for that the CV never mentions**.
- **Per-job tailoring that never invents:** `cvtracks tailor` reorders your existing bullets, projects and skills toward a job post, then lists the post's terms that aren't anywhere in your master. You decide whether any of them is true for you. The post is untrusted input: with [remote-eligibility](https://github.com/bloodmoonbreach/remote-check) installed, hidden text and prompt injections are stripped first, and AI-trap words are reported so you don't use them.

## Install

```bash
pip install "cvtracks[pdf] @ git+https://github.com/bloodmoonbreach/cvtracks"
```

Python 3.11+. The only required dependency is PyYAML; `[pdf]` adds the `typst` package (no system install needed).

## Quick start

```bash
cvtracks init ~/my-cv         # a short interview writes master.yaml + one track per target role
cd ~/my-cv
cvtracks lint                 # what's still TODO, missing translations, typos, impossible dates
cvtracks build                # all tracks, all their languages, PDF → out/
cvtracks build -t soc -l es -f pdf,md,json
cvtracks tailor -t soc --job acme-soc-analyst.txt     # → out/tailored/…
```

Already have a CV? `cvtracks init ~/my-cv --from-cv cv.pdf --model gemma3:12b` lets a language model copy it
into the format: locally through [Ollama](https://ollama.com), or through any OpenAI-compatible API with your
own key (`--llm-url`, `--api-key-env`). It drops address, nationality and birth date, and reports any name it
can't find in your CV. Want to see a finished example first? `cvtracks init ~/demo --example`.

Keep your workspace **outside** any public repo: it's your personal data.

**Docs:** [Getting started in 5 minutes](docs/getting-started.md) · [File format reference](docs/format.md)

## master.yaml

```yaml
person:
  name: Jane Doe
  email: jane@example.com
  linkedin: jane-doe          # handle only; also github, website, phone

summaries:
  soc: {en: "Junior SOC analyst with…", es: "Analista SOC junior con…"}

experience:
  - id: acme
    role: {en: IT Support Technician, es: Técnico de soporte IT}
    company: Acme S.L.
    start: 2022-09          # 2022, 2022-09 or 2022-09-15
    end: 2025-06            # or `ongoing: true`
    tags: [support, soc]    # no tags = in every track
    bullets:
      - text: {en: "Rolled out MFA for 120 users", es: "Despliegue de MFA para 120 usuarios"}
        priority: 1         # 1 = keep first, 3 = drop first
        keywords: [MFA, Active Directory]   # helps job matching, never printed
        tags: [soc]

education: [...]      # same shape: degree, school, start/end/ongoing, status, grade
projects: [...]       # same shape: name, org (stack), url
certifications:
  - {id: cc, name: ISC2 Certified in Cybersecurity (CC), issuer: ISC2, date: 2025-11,
     credential_id: "123", url: https://…, evidence: ~/certs/cc.pdf}   # evidence is checked by lint, never printed
skills:
  - {id: security, label: {en: Security, es: Seguridad}, tags: [soc], items: [SIEM (Wazuh), Log analysis]}
languages:
  - {name: {en: English, es: Inglés}, level: {en: Professional (C1), es: Profesional (C1)}}
```

## tracks/*.yaml

```yaml
id: soc
title: {en: Junior SOC Analyst, es: Analista SOC Junior}
languages: [en, es]
summary: soc                                   # key in master.summaries
include_tags: [soc]                            # items with these tags, or no tags
exclude_tags: [unpublished]
sections: [summary, experience, projects, certifications, skills, education, languages]
skills_order: [security, systems]
limits: {pages: 1, projects: 4, bullets: 3, skills_groups: 5, skills_per_group: 10, max_words: 700}
keywords:                                      # lint: does the CV mention what screeners look for?
  "*": [SIEM, EDR]
  en: [incident response, log analysis]
  es: [respuesta a incidentes, análisis de logs]
file_name: "{name}_CV_SOC_{lang}"
show: {phone: true, extra: true}
```

## Principles

- **Facts are written by you, once.** Tracks and tailoring select and order; they never generate text.
- **Honest gaps.** Lint and `tailor` tell you what's missing. Add it only if it's true.
- **Untrusted job posts.** A job post can't add anything to your CV, and its hidden instructions are removed and reported.

## Status

An early open-source tool. It's used for a real job search (CVs in English, Spanish and Romanian), and the
format may still change before 1.0. Issues and pull requests are welcome.

## Roadmap

- LLM-assisted *rewording* of a bullet (opt-in, shown as a diff, approved by you; never new facts).
- Cover-letter skeletons from the same master.
- More languages for section labels (PR welcome: one dict in `i18n.py`).
- More Typst templates.

## License

MIT
