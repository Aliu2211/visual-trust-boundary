"""Tier 1's defended modes and its host-side guard, in-process. No shell is involved in any path tested here;
the vulnerable paths are exercised only through the sandbox (tests/test_tier1_sandbox.py)."""

import base64
import json
import sqlite3

import pytest

from contracts import Mode, PayloadRecord, Reason
from tiers import badges, tier1_rulebased
from tiers.badges import ground_truth

TRUTH = ground_truth(1337)
ACTIVE, REVOKED = sorted(TRUTH.active_ids)[0], sorted(TRUTH.revoked_ids)[0]


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    badges.build(c, 1337)
    return c


def rec(text=None, *, raw=None, pid="p-001"):
    if raw is not None:
        return PayloadRecord(run_id="r", decoder_mode="default", payload_id=pid, raw_bytes_b64=base64.b64encode(raw).decode(), text=None,
                             decode_status="invalid_utf8", symbology="QRCODE", source_image="p.png", image_sha256="a" * 64,
                             t_capture=0.0, t_decode_ns=1)
    return PayloadRecord(run_id="r", decoder_mode="default", payload_id=pid, raw_bytes_b64=base64.b64encode(text.encode()).decode(), text=text,
                         decode_status="ok", symbology="QRCODE", source_image="p.png", image_sha256="a" * 64,
                         t_capture=0.0, t_decode_ns=1)


# --- the host-side guard ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("mode", [Mode.OFF, Mode.VALIDATE_ONLY])
def test_the_vulnerable_modes_refuse_to_run_outside_the_sandbox_and_touch_nothing(conn, tmp_path, monkeypatch, mode):
    monkeypatch.delenv("VTB_IN_SANDBOX", raising=False)
    marker, audit = tmp_path / "marker", tmp_path / "audit.log"
    with pytest.raises(RuntimeError, match="only inside the sandbox"):
        tier1_rulebased.handle(conn, rec(f"x; touch {marker}"), mode, 0, audit_path=str(audit))
    assert not marker.exists() and not audit.exists()


def test_the_guard_does_not_apply_to_the_parameterised_modes(conn, tmp_path, monkeypatch):
    monkeypatch.delenv("VTB_IN_SANDBOX", raising=False)
    outcome, _ = tier1_rulebased.handle(conn, rec(ACTIVE), Mode.PARAMETERISE_ONLY, 0, audit_path=str(tmp_path / "a.log"))
    assert outcome.error is None


# --- parameterise_only: control 2 without control 1 ---------------------------------------------------------------


def test_a_legitimate_badge_is_granted_and_audited_as_data(conn, tmp_path):
    audit = tmp_path / "audit.log"
    outcome, obs = tier1_rulebased.handle(conn, rec(ACTIVE), Mode.PARAMETERISE_ONLY, 3, audit_path=str(audit))
    assert obs.granted is True and obs.matched_id == ACTIVE and "GRANTED" in obs.visible_text
    assert (outcome.error, outcome.blocked, outcome.rep, outcome.defense_ns) == (None, False, 3, None)
    assert outcome.handle_ns > 0
    assert [json.loads(line) for line in audit.read_text().splitlines()] == [{"id": ACTIVE}]


def test_revoked_and_unknown_badges_are_denied(conn, tmp_path):
    for text in (REVOKED, "B-999998"):
        _, obs = tier1_rulebased.handle(conn, rec(text), Mode.PARAMETERISE_ONLY, 0, audit_path=str(tmp_path / "a.log"))
        assert obs.granted is False


@pytest.mark.parametrize(
    "text",
    ["' OR '1'='1", "' UNION SELECT id, secret, 1 FROM badges WHERE id = 'R-000000", "x'; drop table badges; --", "O'BRIEN"],
)
def test_sql_shaped_text_is_only_ever_data_in_parameterised_mode(conn, tmp_path, text):
    before = badges.canonical_sha256(conn)
    outcome, obs = tier1_rulebased.handle(conn, rec(text), Mode.PARAMETERISE_ONLY, 0, audit_path=str(tmp_path / "a.log"))
    assert outcome.error is None and obs.granted is False and ground_truth(1337).restricted_secret not in obs.visible_text
    assert badges.canonical_sha256(conn) == before


def test_shell_shaped_text_is_never_executed_in_parameterised_mode(conn, tmp_path):
    marker, audit = tmp_path / "marker", tmp_path / "audit.log"
    tier1_rulebased.handle(conn, rec(f"x; touch {marker}"), Mode.PARAMETERISE_ONLY, 0, audit_path=str(audit))
    assert not marker.exists()
    assert json.loads(audit.read_text())["id"] == f"x; touch {marker}"  # stored as data, one JSON line


def test_a_newline_in_the_text_cannot_forge_a_second_audit_line(conn, tmp_path):
    audit = tmp_path / "audit.log"
    tier1_rulebased.handle(conn, rec("B-000001\nFORGED"), Mode.PARAMETERISE_ONLY, 0, audit_path=str(audit))
    assert len(audit.read_text().splitlines()) == 1


def test_invalid_utf8_is_decoded_naively_without_a_control_and_nothing_breaks(conn, tmp_path):
    outcome, obs = tier1_rulebased.handle(conn, rec(raw=b"B-00\xff\xfe"), Mode.PARAMETERISE_ONLY, 0, audit_path=str(tmp_path / "a.log"))
    assert outcome.error is None and obs.granted is False


# --- full: both controls ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,reason",
    [("' OR '1'='1", Reason.CHARSET), ("x" * 40, Reason.LENGTH), ("BB-00-000", Reason.GRAMMAR), ("B-000123\n", Reason.CHARSET)],
)
def test_full_mode_refuses_hostile_input_before_any_lookup_or_audit(conn, tmp_path, text, reason):
    audit = tmp_path / "audit.log"
    outcome, obs = tier1_rulebased.handle(conn, rec(text), Mode.FULL, 0, audit_path=str(audit))
    assert outcome.blocked and outcome.detail == f"refused: {reason.value}"
    assert obs.granted is False and outcome.defense_ns is not None and outcome.defense_ns > 0
    assert not audit.exists(), "a refused input must not reach the audit step"


def test_full_mode_refuses_invalid_utf8_as_encoding(conn, tmp_path):
    outcome, _ = tier1_rulebased.handle(conn, rec(raw=b"B-00\xff\xfe"), Mode.FULL, 0, audit_path=str(tmp_path / "a.log"))
    assert outcome.blocked and outcome.detail == "refused: encoding"


def test_full_mode_still_serves_every_legitimate_badge(conn, tmp_path):
    for i, text in enumerate(sorted(TRUTH.active_ids | TRUTH.revoked_ids)):
        outcome, obs = tier1_rulebased.handle(conn, rec(text), Mode.FULL, i, audit_path=str(tmp_path / "a.log"))
        assert not outcome.blocked and outcome.error is None
        assert obs.granted is (text in TRUTH.active_ids)


def test_a_record_without_a_payload_id_cannot_be_handled(conn, tmp_path):
    live = PayloadRecord(run_id="r", decoder_mode="default", raw_bytes_b64=base64.b64encode(b"x").decode(), text="x", decode_status="ok",
                         symbology="QRCODE", source_image="live#0", image_sha256="a" * 64, t_capture=0.0, t_decode_ns=1)
    with pytest.raises(ValueError, match="payload_id"):
        tier1_rulebased.handle(conn, live, Mode.FULL, 0, audit_path=str(tmp_path / "a.log"))


# --- reproducibility: nothing measured may leak into a text column (E-025) ------------------------------------------


@pytest.mark.parametrize("elapsed", [4.999930853999103, 4.99997205100226, 5.0021])
def test_a_shell_timeout_is_described_without_the_measured_time(conn, tmp_path, monkeypatch, elapsed):
    import subprocess

    def slow(cmd, **kwargs):  # stands in for the shell step; nothing is executed
        raise subprocess.TimeoutExpired(cmd, elapsed)

    monkeypatch.setenv("VTB_IN_SANDBOX", "1")
    monkeypatch.setattr(tier1_rulebased.subprocess, "run", slow)
    outcome, obs = tier1_rulebased.handle(conn, rec("x; sleep 30"), Mode.OFF, 0, audit_path=str(tmp_path / "a.log"))
    assert outcome.error == "TimeoutExpired"
    assert outcome.detail == "audit shell command exceeded 5 s"  # the same text whatever the elapsed time
    assert obs.granted is False  # the lookup had already decided; only the audit step failed
