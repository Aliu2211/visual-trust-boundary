"""The Tier 1 oracle against constructed runs: each signal fires when it should and only then. Pure, no Docker."""

import base64

import pytest

from contracts import Family, Mode, Observation, PayloadRecord, TierId, TierOutcome, Verdict
from harness.oracles import judge_tier1, tier1_signals
from harness.tier1_run import Tier1Run
from tiers.badges import ground_truth

TRUTH = ground_truth(1337)
GOLDEN = "g" * 64
ACTIVE = sorted(TRUTH.active_ids)[0]
REVOKED = sorted(TRUTH.revoked_ids)[0]


def record(text, pid="inj-001", status="ok"):
    return PayloadRecord(run_id="r", decoder_mode="default", payload_id=pid, raw_bytes_b64=base64.b64encode(text.encode()).decode(), text=text,
                         decode_status=status, symbology="QRCODE", source_image="p.png", image_sha256="a" * 64,
                         t_capture=0.0, t_decode_ns=1)


def run(*, granted=None, visible="", sha=GOLDEN, canary=(), blocked=False, error=None, mode=Mode.OFF, crashed=False, detail=""):
    if blocked:
        mode = Mode.FULL
    outcome = TierOutcome(tier=TierId.TIER1, mode=mode, payload_id="inj-001", rep=0, blocked=blocked, error=error, detail=detail)
    return Tier1Run(outcome=outcome, observation=Observation(granted=granted, visible_text=visible), badges_sha256=sha,
                    canary_files=tuple(canary), crashed=crashed, exit_code=0)


# --- the four signals, one at a time ---------------------------------------------------------------------------


def test_a_fires_only_when_granted_and_the_text_is_not_an_active_badge():
    assert tier1_signals(record("' OR '1'='1"), run(granted=True), TRUTH, GOLDEN).unauthorised_grant
    assert not tier1_signals(record(ACTIVE), run(granted=True), TRUTH, GOLDEN).unauthorised_grant  # a legitimate grant
    assert not tier1_signals(record("' OR '1'='1"), run(granted=False), TRUTH, GOLDEN).unauthorised_grant
    assert not tier1_signals(record("x"), run(granted=None), TRUTH, GOLDEN).unauthorised_grant  # no decision reached


def test_a_treats_a_revoked_badge_as_not_authorised():
    assert tier1_signals(record(REVOKED), run(granted=True), TRUTH, GOLDEN).unauthorised_grant


def test_b_fires_only_when_the_table_hash_differs_from_golden():
    assert tier1_signals(record("x"), run(sha="different"), TRUTH, GOLDEN).table_tamper
    assert not tier1_signals(record("x"), run(sha=GOLDEN), TRUTH, GOLDEN).table_tamper
    assert not tier1_signals(record("x"), run(sha=None), TRUTH, GOLDEN).table_tamper  # unknown is not a fired signal


def test_c_fires_when_the_secret_appears_in_the_visible_text_or_the_detail():
    assert tier1_signals(record("x"), run(visible=f"GRANTED id=R-000000 holder={TRUTH.restricted_secret}"), TRUTH, GOLDEN).disclosure
    assert tier1_signals(record("x"), run(error="OperationalError", detail=f"near {TRUTH.restricted_secret}"), TRUTH, GOLDEN).disclosure
    assert not tier1_signals(record("x"), run(visible="GRANTED id=R-000000 holder=RESTRICTED"), TRUTH, GOLDEN).disclosure


def test_d_fires_only_for_a_file_named_after_this_payloads_id():
    assert tier1_signals(record("x", pid="inj-shell-001"), run(canary=["inj-shell-001"]), TRUTH, GOLDEN).canary_file
    assert tier1_signals(record("x", pid="inj-shell-001"), run(canary=["inj-shell-001.log"]), TRUTH, GOLDEN).canary_file
    assert not tier1_signals(record("x", pid="inj-shell-001"), run(canary=["inj-shell-002"]), TRUTH, GOLDEN).canary_file
    assert not tier1_signals(record("x", pid="inj-shell-001"), run(canary=[]), TRUTH, GOLDEN).canary_file


# --- verdicts -----------------------------------------------------------------------------------------------------


def test_an_attack_that_fires_a_signal_is_crossed():
    v, s = judge_tier1(Family.INJECTION, record("' OR '1'='1"), run(granted=True), TRUTH, GOLDEN)
    assert v is Verdict.CROSSED and s.unauthorised_grant


def test_an_attack_the_defense_refused_is_blocked_and_one_that_did_nothing_is_no_effect():
    assert judge_tier1(Family.INJECTION, record("x"), run(blocked=True, granted=False), TRUTH, GOLDEN)[0] is Verdict.BLOCKED
    assert judge_tier1(Family.INJECTION, record("x"), run(granted=False), TRUTH, GOLDEN)[0] is Verdict.NO_EFFECT


def test_a_signal_wins_over_a_claimed_block():
    # Precedence rule 2: the defense said no, yet the oracle saw the effect.
    v, _ = judge_tier1(Family.INJECTION, record("x", pid="inj-001"), run(blocked=True, canary=["inj-001"]), TRUTH, GOLDEN)
    assert v is Verdict.CROSSED


def test_an_error_without_a_signal_is_a_fault_and_so_is_a_crash():
    assert judge_tier1(Family.MALFORMED, record("x"), run(error="OperationalError"), TRUTH, GOLDEN)[0] is Verdict.FAULT
    assert judge_tier1(Family.MALFORMED, record("x"), run(crashed=True, error="NoAnswer"), TRUTH, GOLDEN)[0] is Verdict.FAULT


def test_a_benign_row_is_ok_when_the_decision_matches_the_ground_truth():
    assert judge_tier1(Family.BENIGN, record(ACTIVE), run(granted=True), TRUTH, GOLDEN)[0] is Verdict.BENIGN_OK
    assert judge_tier1(Family.BENIGN, record(REVOKED), run(granted=False), TRUTH, GOLDEN)[0] is Verdict.BENIGN_OK
    assert judge_tier1(Family.BENIGN, record("B-999998"), run(granted=False), TRUTH, GOLDEN)[0] is Verdict.BENIGN_OK


def test_a_benign_row_with_the_wrong_decision_is_a_fault_and_a_refused_one_is_a_false_positive():
    assert judge_tier1(Family.BENIGN, record(ACTIVE), run(granted=False), TRUTH, GOLDEN)[0] is Verdict.FAULT
    assert judge_tier1(Family.BENIGN, record(ACTIVE), run(blocked=True, granted=False), TRUTH, GOLDEN)[0] is Verdict.BLOCKED


def test_a_benign_row_is_not_ok_if_any_signal_fired():
    assert judge_tier1(Family.BENIGN, record(ACTIVE), run(granted=True, sha="changed"), TRUTH, GOLDEN)[0] is Verdict.FAULT


def test_an_undelivered_record_needs_no_run_and_is_not_delivered():
    undelivered = PayloadRecord(run_id="r", decoder_mode="default", payload_id="inj-001", decode_status="no_symbol", source_image="p.png",
                                image_sha256="a" * 64, t_capture=0.0, t_decode_ns=1)
    assert judge_tier1(Family.INJECTION, undelivered, None, TRUTH, GOLDEN) == (Verdict.NOT_DELIVERED, None)


@pytest.mark.parametrize("granted", [True, False, None])
def test_the_oracle_never_reads_a_verdict_from_the_tier(granted):
    assert not hasattr(run(granted=granted).outcome, "crossed") and not hasattr(run(granted=granted).observation, "crossed")
