# File format reference

A workspace is a folder with one `master.yaml` and a `tracks/` folder:

```
my-cv/
  master.yaml          every fact, once
  tracks/
    it-support.yaml    one CV version per target role
    soc-analyst.yaml
  out/                 what `cvtracks build` writes (safe to delete)
```

Both files are YAML. If you have never written YAML: indentation is two spaces (never tabs), `key: value`
on each line, a list item starts with `- `, and text containing `: ` or starting with a symbol goes in quotes.
`cvtracks lint` tells you the line when something is wrong.

## Text in several languages

Every text field can be a plain string (the same in every language) or one string per language:

```yaml
role: Help Desk Technician                                   # same everywhere
role: {en: Help Desk Technician, es: Técnico de soporte}      # per language
summary:                                                      # long texts: one per line
  en: Help desk technician with three years of first-line support...
  es: Técnico de soporte con tres años de soporte de primer nivel...
```

Language codes are free (`en`, `es`, `ro`, `de`…). A track lists the languages it's built in, and lint reports
any text that is missing in one of them. Section titles and dates are translated for `en`, `es` and `ro`; for
other languages, set them under `labels` (below).

## master.yaml

### person

| Key | Required | Notes |
|---|---|---|
| `name` | yes | As you want it on the CV |
| `email`, `phone`, `website` | no | |
| `linkedin`, `github` | no | Handle only (`jane-doe`), the link is built for you |
| `location` | no | Printed in the header. In most EU applications, leave it out (see below) |
| `extra` | no | List of short header lines. Same advice |

**What not to put on a CV in the EU.** Address, city, nationality or citizenship, date of birth, age, photo,
gender and marital status aren't needed to judge your skills. GDPR asks employers to collect only what they
need, and anti-discrimination practice in most EU countries is to leave these out. Some employers' systems
reject CVs that include them. If an employer needs your right to work or your location, the application form
asks for it.

### summaries

A map from a key to a text. Each track picks one by key (`summary: it-support`). Write 2–4 sentences about
you as a professional: what you do, how you work, what you bring. Every claim should be backed by a bullet
somewhere in the CV ("prove, don't claim").

```yaml
summaries:
  it-support: {en: "...", es: "..."}
  soc: {en: "...", es: "..."}
```

### experience, education, projects

Three lists of the same shape. The title and organisation keys have aliases so the file reads naturally.

| Key | Notes |
|---|---|
| `id` | Short unique name (`acme-support`). Used by tailoring and lint messages |
| `title` | Also accepted: `role` (experience), `degree` (education), `name` (projects). Required |
| `org` | Also accepted: `company`, `school`. For projects: the tools used |
| `location` | Printed next to the dates. Optional |
| `start`, `end` | `2024`, `2024-03` or `2024-03-15`. The precision you write is the precision printed |
| `ongoing: true` | Instead of `end`, for a current job or course. Printed as "Present" / "Actualidad" |
| `status`, `grade` | Education: e.g. `{en: In progress}`, `8.7/10` |
| `url` | Link (projects, a published thesis…) |
| `summary` | One line under the title, before the bullets |
| `bullets` | List of texts, or of `{text, tags, priority, keywords}` (below) |
| `tags` | Which tracks show this item. No tags = every track |
| `priority` | 1 = keep first, 2 = normal (default), 3 = first to drop when a track has limits |
| `keywords` | Extra words for matching job posts. Never printed |

Experience and education are sorted by date (newest first) inside each priority. Projects keep your order,
unless `cvtracks tailor` moves the relevant ones up.

A bullet can be just text, or a mapping:

```yaml
bullets:
  - Wrote 25 knowledge-base articles in GLPI
  - text: {en: "Cut repeat password tickets by 40% with self-service reset", es: "..."}
    priority: 1                 # keep even when the track allows few bullets
    tags: [support]             # only in tracks that include 'support'
    keywords: [SSPR, Active Directory]
```

Good bullets say what changed, with a number when there is one: "Resolved ~25 tickets a day with 94% fixed at
first contact" beats "Responsible for resolving tickets".

### certifications

| Key | Notes |
|---|---|
| `id`, `name` | Required |
| `issuer`, `date` | Optional; `date` like `2025-11` |
| `credential_id`, `url` | Printed, so an employer can verify it |
| `evidence` | Path to your certificate file. Lint checks it exists; never printed |
| `tags`, `priority`, `keywords` | As above |

### skills

Groups of short items. Only list what you could explain in an interview.

```yaml
skills:
  - id: systems
    label: {en: Systems, es: Sistemas}
    items: [Windows 11, Active Directory, Microsoft 365, Linux (Ubuntu)]
    tags: [support]          # optional
```

### languages

```yaml
languages:
  - {name: {en: English, es: Inglés}, level: C1, cefr: C1}
  - {name: {en: Spanish, es: Español}, level: {en: Native, es: Nativo}}
```

`level` is printed; `cefr` (A1–C2) is for tools that read the CV as data.

### labels (optional)

Override section titles, for a language cvtracks doesn't know or wording you prefer. Keys: `summary`,
`experience`, `education`, `projects`, `certifications`, `skills`, `languages`, `present`, `in_progress`,
`credential`.

```yaml
labels:
  experience: {en: Work experience, de: Berufserfahrung}
  present: {de: heute}
```

## tracks/*.yaml

One file per CV version. The file name doesn't matter; `id` does.

| Key | Default | Notes |
|---|---|---|
| `id` | file name | Used in `-t` and in output file names |
| `title` | | The headline under your name (the role you apply for) |
| `languages` | `[en]` | Languages this version is built in |
| `summary` | | Key into `summaries` |
| `include_tags` | everything | Show items with one of these tags, plus items without tags |
| `exclude_tags` | | Never show items with these tags (e.g. `[unpublished]`) |
| `sections` | all | Order of sections; leave one out to hide it: `summary`, `experience`, `education`, `projects`, `certifications`, `skills`, `languages` |
| `skills_order` | file order | Skill group ids, most relevant first |
| `limits` | none | See below |
| `keywords` | | Terms employers screen for. Lint warns when the CV never mentions one. A list, or per language: `{"*": [SIEM], en: [incident response], es: [respuesta a incidentes]}` |
| `show` | all `true` | Hide header items for this version: `email`, `phone`, `location`, `website`, `linkedin`, `github`, `extra` |
| `file_name` | `{name}_CV_{track}_{lang}` | Output file name pattern |

`limits` keys:

| Key | Effect |
|---|---|
| `pages` | PDF page limit. The font shrinks a little until it fits, then cvtracks warns |
| `experience`, `education`, `projects`, `certifications` | Maximum items (lowest priority dropped first) |
| `bullets` | Maximum bullets per item |
| `skills_groups`, `skills_per_group` | Trim the skills section |
| `max_words` | Lint warns above this (about 600–700 words is one page) |

Example:

```yaml
id: it-support
title: {en: IT Support Technician, es: Técnico de Soporte IT}
languages: [es, en]
summary: it-support
include_tags: [support]
sections: [summary, experience, certifications, skills, education, languages]
skills_order: [systems, tools]
limits: {pages: 1, bullets: 4, projects: 3, max_words: 650}
keywords: [ticketing, Active Directory, Microsoft 365, ITIL]
```

## What lint checks

- **The file doesn't load** (invalid YAML, an unknown key, a date like `March 2024`): every command stops
  and names the key, e.g. `experience[2].start: dates look like 2024, 2024-03 or 2024-03-15`.
- **Errors** (exit code 1): a text missing in a language a track needs, an end date before the start, a
  track pointing at a summary that doesn't exist, common typos.
- **Warnings**: `TODO` placeholders, jobs without bullets, dates in the future, ongoing items with a past
  end date, repeated words, a missing evidence file, a CV over its word limit, and track keywords the CV
  never mentions (add them only if they are true).
- **Info** (`-v`): empty sections, items without dates.
