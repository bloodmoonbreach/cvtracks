from pathlib import Path

from cvtracks import tailor
from cvtracks.loader import load_master, load_tracks
from cvtracks.tailor import SKILLS, _case_sensitive

EX = Path(__file__).resolve().parents[1] / "src" / "cvtracks" / "examples"

POST = """CHALLENGE
COME and DARE to join us in Buenos Aires! About Acme Acme is a Best WorkplacesTM company.
You will triage alerts in Microsoft Sentinel and Splunk, hunt threats with MITRE ATT&CK, manage
Intune and Active Directory, and know ISO 27001 and NIS2. Pam from HR will call you. Provide great service."""


def test_missing_lists_only_real_skills():
    master = load_master(EX / "master.yaml")
    track = next(iter(load_tracks(EX / "tracks").values()))
    _, r = tailor(master, track, POST)
    junk = {"CHALLENGE", "COME", "DARE", "Buenos Aires", "About Acme Acme", "Best WorkplacesTM", "Provide", "PAM", "HR"}
    assert not junk & set(r.gaps)
    for skill in ("Microsoft Sentinel", "Splunk", "MITRE ATT&CK", "Intune", "Active Directory", "ISO 27001", "NIS2"):
        assert skill in r.gaps or skill in r.matched


def test_acronyms_need_capitals():
    assert _case_sensitive("PAM") and _case_sensitive("ENS") and not _case_sensitive("Splunk")
    assert "Go" not in SKILLS and "C" not in SKILLS and "Teams" not in SKILLS


def test_vocabulary_is_clean():
    assert len(SKILLS) > 300 and len(SKILLS) == len(set(SKILLS))
