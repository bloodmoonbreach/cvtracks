"""JSON Resume (https://jsonresume.org/schema) export, for themes and tools that read the standard."""

from __future__ import annotations

import json

from ..select import ResolvedCV
from . import Options, register


@register("json", "json")
def render_json(cv: ResolvedCV, opts: Options) -> bytes:
    by = {c.kind: c for c in cv.contacts}
    profiles = [{"network": k.title(), "url": by[k].href} for k in ("github", "linkedin") if k in by]
    data = {
        "$schema": "https://raw.githubusercontent.com/jsonresume/resume-schema/v1.0.0/schema.json",
        "basics": {
            "name": cv.name, "label": cv.headline, "summary": cv.summary,
            **({"email": by["email"].text} if "email" in by else {}),
            **({"phone": by["phone"].text} if "phone" in by else {}),
            **({"url": by["website"].href} if "website" in by else {}),
            **({"location": {"address": by["location"].text}} if "location" in by else {}),
            "profiles": profiles,
        },
        "work": [{"name": e.org, "position": e.title, "location": e.location, "startDate": e.start_iso,
                  **({"endDate": e.end_iso} if e.end_iso else {}), "summary": e.summary, "highlights": e.bullets}
                 for e in cv.experience],
        "education": [{"institution": e.org, "area": e.title, "startDate": e.start_iso,
                       **({"endDate": e.end_iso} if e.end_iso else {}), **({"score": e.grade} if e.grade else {})}
                      for e in cv.education],
        "projects": [{"name": p.title, "description": p.summary or p.org, "highlights": p.bullets,
                      **({"url": p.url} if p.url else {}), **({"startDate": p.start_iso} if p.start_iso else {})}
                     for p in cv.projects],
        "certificates": [{"name": c.name, "issuer": c.issuer, **({"date": c.date_iso} if c.date_iso else {}),
                          **({"url": c.url} if c.url else {})} for c in cv.certifications],
        "skills": [{"name": g.label, "keywords": g.items} for g in cv.skills],
        "languages": [{"language": l.name, "fluency": l.level} for l in cv.languages],
        "meta": {"language": cv.lang, "track": cv.track},
    }
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
