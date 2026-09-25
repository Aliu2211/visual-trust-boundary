"""P2.4: the same payloads through all four Tier 1 modes, inside the sandbox, judged by the harness oracle.

Needs Docker and the built vtb-sandbox image; run on the host with VTB_REQUIRE_SANDBOX=1. The vulnerable
paths execute only inside the sandbox. Each row prints what was observed so a capture carries the table.
"""

import base64
import sqlite3

import pytest

from contracts import Family, Mode, PayloadRecord, Verdict
from harness.oracles import judge_tier1
from harness.tier1_run import run_tier1
from tiers import badges

SEED = 1337
TRUTH = badges.ground_truth(SEED)
ACTIVE, REVOKED = sorted(TRUTH.active_ids)[0], sorted(TRUTH.revoked_ids)[0]
UNKNOWN = "B-999998"
assert UNKNOWN not in TRUTH.active_ids | TRUTH.revoked_ids

_golden = sqlite3.connect(":memory:")
badges.build(_golden, SEED)
GOLDEN = badges.canonical_sha256(_golden)

V = Verdict
MODES = (Mode.OFF, Mode.VALIDATE_ONLY, Mode.PARAMETERISE_ONLY, Mode.FULL)

# id, family, decoded text, expected verdict under (off, validate_only, parameterise_only, full)
CASES = [
    ("inj-sql-001", Family.INJECTION, "' OR '1'='1", (V.CROSSED, V.BLOCKED, V.NO_EFFECT, V.BLOCKED)),
    ("inj-union-001", Family.INJECTION, "' UNION SELECT id, secret, 1 FROM badges WHERE id = 'R-000000",
     (V.CROSSED, V.BLOCKED, V.NO_EFFECT, V.BLOCKED)),
    ("inj-shell-001", Family.INJECTION, "x; touch /canary/inj-shell-001", (V.CROSSED, V.BLOCKED, V.NO_EFFECT, V.BLOCKED)),
    # The tier is PID 1 in its container, and the kernel ignores SIGKILL sent to a namespace's init from inside it,
    # so this payload cannot kill the tier: observed, and a limit on what a payload can do here.
    ("inj-kill-001", Family.INJECTION, "x; kill -9 $PPID", (V.NO_EFFECT, V.BLOCKED, V.NO_EFFECT, V.BLOCKED)),
    ("inj-sleep-001", Family.INJECTION, "x; sleep 30", (V.FAULT, V.BLOCKED, V.NO_EFFECT, V.BLOCKED)),
    ("mal-quote-001", Family.MALFORMED, "O'BRIEN", (V.FAULT, V.BLOCKED, V.NO_EFFECT, V.BLOCKED)),
    ("ben-active-001", Family.BENIGN, ACTIVE, (V.BENIGN_OK,) * 4),
    ("ben-revoked-001", Family.BENIGN, REVOKED, (V.BENIGN_OK,) * 4),
    ("ben-unknown-001", Family.BENIGN, UNKNOWN, (V.BENIGN_OK,) * 4),
]


def record(pid: str, text: str) -> PayloadRecord:
    return PayloadRecord(run_id="demo", decoder_mode="default", payload_id=pid, raw_bytes_b64=base64.b64encode(text.encode()).decode(), text=text,
                         decode_status="ok", symbology="QRCODE", source_image=f"{pid}.png", image_sha256="a" * 64,
                         t_capture=0.0, t_decode_ns=1)


@pytest.mark.parametrize("mode_index", range(4), ids=[m.value for m in MODES])
@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_the_verdict_for_each_payload_and_mode(sandbox, case, mode_index):
    pid, family, text, expected = case
    mode = MODES[mode_index]
    rec = record(pid, text)

    run = run_tier1(sandbox, rec, mode, 0, SEED)
    verdict, signals = judge_tier1(family, rec, run, TRUTH, GOLDEN)

    fired = [n for n, on in (("A", signals.unauthorised_grant), ("B", signals.table_tamper),
                             ("C", signals.disclosure), ("D", signals.canary_file)) if on]
    print(f"row: {pid:16} {mode.value:18} -> {verdict.value:9} signals={fired or '-'} blocked={run.outcome.blocked} "
          f"error={run.outcome.error} crashed={run.crashed} canary={list(run.canary_files) or '-'}")
    assert verdict is expected[mode_index], (pid, mode.value, verdict, run.outcome, run.observation)
    # The tier reports defense time only in modes that ran the defense.
    assert (run.outcome.defense_ns is not None) is (mode in (Mode.VALIDATE_ONLY, Mode.FULL)) or run.crashed


def test_the_first_real_crossing_and_the_first_real_block(sandbox):
    """Plan P2 acceptance in one place: `off` crosses, `validate_only` blocks, `parameterise_only` accepts without effect, `full` blocks."""
    rec = record("inj-shell-001", "x; touch /canary/inj-shell-001")
    runs = {m: run_tier1(sandbox, rec, m, 0, SEED) for m in MODES}
    verdicts = {m: judge_tier1(Family.INJECTION, rec, runs[m], TRUTH, GOLDEN)[0] for m in MODES}
    assert verdicts == dict(zip(MODES, (V.CROSSED, V.BLOCKED, V.NO_EFFECT, V.BLOCKED)))
    assert runs[Mode.OFF].canary_files == ("inj-shell-001",)  # the side effect really happened, seen from the host side
    assert all(runs[m].canary_files == () for m in MODES[1:])
    assert not runs[Mode.PARAMETERISE_ONLY].outcome.blocked and runs[Mode.PARAMETERISE_ONLY].outcome.error is None


def test_a_disclosure_payload_fires_both_the_grant_and_the_disclosure_signals(sandbox):
    rec = record("inj-union-001", "' UNION SELECT id, secret, 1 FROM badges WHERE id = 'R-000000")
    run = run_tier1(sandbox, rec, Mode.OFF, 0, SEED)
    _, signals = judge_tier1(Family.INJECTION, rec, run, TRUTH, GOLDEN)
    assert signals.unauthorised_grant and signals.disclosure and not signals.table_tamper and not signals.canary_file
    assert TRUTH.restricted_secret in run.observation.visible_text


def test_a_payload_cannot_kill_the_tier_because_it_is_pid_1_in_its_container(sandbox):
    rec = record("inj-kill-001", "x; kill -9 $PPID")
    run = run_tier1(sandbox, rec, Mode.OFF, 0, SEED)
    assert not run.crashed and run.outcome.error is None and run.observation.granted is False
