"""cvtracks init: interview → files that load, lint and build; CV draft cleaning."""

from pathlib import Path

import yaml

from cvtracks.cli import _write_workspace, main
from cvtracks.draft import LLMConfig, _clean, _not_in_cv
from cvtracks.loader import load_master, load_tracks
from cvtracks.setup import interview, master_yaml

ANSWERS = [
    "Jane Doe", "jane@example.com", "", "jane-doe", "", "",   # name, email, phone, linkedin, github, website
    "en, es",                                                   # CV languages
    "IT Support Technician", "Junior SOC Analyst", "",          # roles
    "IT support technician who documents every fix.", "",       # summaries (second skipped)
    "", "Support Technician", "Acme S.L.", "2022-09", "",       # add job (default yes), title, employer, start, ongoing
    "Resolved ~25 tickets a day", "Rolled out MFA for 120 users", "",
    "",                                                         # tags: all CVs
    "n",                                                        # another job? no
    "", "SMR", "IES Example", "2020", "2022",                   # education
    "n",
    "y", "ISC2 CC", "ISC2", "2025-11", "",                      # certification
    "n",
    "n",                                                        # projects
    "Systems: Windows, Active Directory, Linux", "",            # skills
    "English C1, Spanish native",                               # languages
]


def run_interview():
    answers = iter(ANSWERS)
    return interview(lambda q, d="": next(answers))


def test_interview_writes_a_workspace_that_loads(tmp_path: Path):
    master, tracks = run_interview()
    _write_workspace(tmp_path, master_yaml(master), tracks)
    m = load_master(tmp_path / "master.yaml")
    t = load_tracks(tmp_path / "tracks")
    assert m.person.name == "Jane Doe" and m.person.location is None
    assert set(t) == {"it-support-technician", "junior-soc-analyst"}
    assert m.experience[0].ongoing and len(m.experience[0].bullets) == 2
    assert m.experience[0].bullets[0].text == {"en": "Resolved ~25 tickets a day", "es": "TODO: translate"}
    assert m.summaries["junior-soc-analyst"]["en"].startswith("TODO")
    assert m.languages[1].name == {"en": "Spanish", "es": "Español"}
    assert m.languages[1].level == {"en": "Native", "es": "Nativo"}
    assert m.languages[0].cefr == "C1"
    assert main(["lint", "-d", str(tmp_path)]) in (0, 1)  # TODOs are warnings, not crashes
    assert main(["build", "-d", str(tmp_path), "-f", "md"]) == 0
    assert any(tmp_path.glob("out/*.md"))


def test_example_when_not_interactive(tmp_path: Path):
    assert main(["init", str(tmp_path)]) == 0
    assert (tmp_path / "master.yaml").exists()
    assert main(["init", str(tmp_path)]) == 1  # never overwrites without --force


def test_draft_drops_private_fields_and_flags_unknown_names():
    warnings: list[str] = []
    data = _clean({
        "person": {"name": "Jane Doe", "email": "j@example.com", "nationality": "X", "address": "Street 1"},
        "experience": [{"id": "Acme Job", "role": "Tech", "company": "Acme S.L.", "start": 2022, "salary": "lots"},
                       {"id": "acme job", "role": "Tech", "company": "Globex", "start": "2020-01"}],
    }, warnings)
    assert set(data["person"]) == {"name", "email"} and "nationality" in warnings[0]
    assert [e["id"] for e in data["experience"]] == ["acme-job", "acme-job-2"]
    assert "salary" not in data["experience"][0] and data["experience"][0]["start"] == "2022"
    missing = _not_in_cv(data, "Jane Doe. Tech at ACME S.L. since 2022.")
    assert missing == ["experience: 'Globex' is not in the CV text; check it"]


def test_local_endpoints():
    assert LLMConfig("http://localhost:11434/v1").is_local
    assert LLMConfig("http://192.168.0.5:11434/v1").is_local
    assert not LLMConfig("https://api.openai.com/v1").is_local
