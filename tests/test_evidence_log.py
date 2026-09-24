"""Keeps docs/evidence/LOG.md honest: every raw capture has an entry, every entry's file verifies, and the hash the ledger quotes is the one in the file."""

import re
from pathlib import Path

from tools.capture_evidence import HASH_PREFIX, verify

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "docs" / "evidence" / "LOG.md"
RAW = ROOT / "docs" / "evidence" / "raw"


def entries() -> dict[str, str]:
    sections = re.split(r"^### (E-\d{3,}) ", LOG.read_text(), flags=re.MULTILINE)[1:]
    return dict(zip(sections[0::2], sections[1::2]))


def recorded_hash(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").rstrip("\n").splitlines()[-1].removeprefix(HASH_PREFIX)


def test_every_raw_capture_has_a_ledger_entry_and_vice_versa():
    raw_ids = {p.stem for p in RAW.glob("E-*.txt")}
    assert raw_ids, "no captures found"
    assert raw_ids == set(entries())


def test_every_raw_capture_verifies():
    bad = [p.name for p in sorted(RAW.glob("E-*.txt")) if not verify(p)]
    assert not bad, f"hash mismatch: {bad}"


def test_the_hash_quoted_in_each_entry_is_the_hash_in_its_file():
    wrong = []
    for eid, body in entries().items():
        quoted = re.search(rf"raw/{eid}\.txt\)?, sha256 `([0-9a-f]{{64}})`", body)
        if not quoted or quoted.group(1) != recorded_hash(RAW / f"{eid}.txt"):
            wrong.append(eid)
    assert not wrong, f"ledger hash missing or different from the file for: {wrong}"


def test_every_entry_states_class_confidence_caveats_and_paper_use():
    for eid, body in entries().items():
        assert re.search(r"\*\*Class:\*\* (design|dev-observation|pi-observation|result-of-record)", body), eid
        assert re.search(r"\*\*Confidence:\*\* (verified|source-read|assumed)", body), eid
        assert "**Caveats:**" in body and "**Paper use:**" in body, eid


def test_the_index_lists_exactly_the_entries():
    index_ids = set(re.findall(r"^\| (E-\d{3,}) \|", LOG.read_text(), flags=re.MULTILINE))
    assert index_ids == set(entries())
