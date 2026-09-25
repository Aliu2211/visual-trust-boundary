"""run_tier1's handling of a run that produced no usable answer. Pure: a fake sandbox stands in for Docker."""

import base64
import json

import pytest

from contracts import Family, Mode, PayloadRecord, Verdict
from harness.oracles import judge_tier1
from harness.sandbox import SandboxResult
from harness.tier1_run import run_tier1
from tiers.badges import ground_truth

TRUTH = ground_truth(1337)


class FakeSandbox:
    def __init__(self, **fields):
        self.result = SandboxResult(**{"stdout": "", "stderr": "", "exit_code": 0, "timed_out": False,
                                       "output_truncated": False, "canary_files": (), **fields})

    def run(self, argv, *, stdin=None, timeout=None):
        self.stdin = stdin
        return self.result


def rec():
    return PayloadRecord(run_id="r", decoder_mode="default", payload_id="inj-001", raw_bytes_b64=base64.b64encode(b"x").decode(), text="x",
                         decode_status="ok", symbology="QRCODE", source_image="p.png", image_sha256="a" * 64,
                         t_capture=0.0, t_decode_ns=1)


@pytest.mark.parametrize(
    "fields,error",
    [
        (dict(stdout="", exit_code=137), "NoAnswer"),                        # killed
        (dict(stdout="not json at all\n"), "NoAnswer"),                      # garbage
        (dict(stdout='{"outcome": 1}\n'), "NoAnswer"),                       # wrong shape
        (dict(stdout='{"outcome": {}, "observation": {}, "state": {}}\n'), "NoAnswer"),  # fails validation
        (dict(stdout="", exit_code=137, timed_out=True), "Timeout"),
    ],
)
def test_no_usable_answer_is_reported_as_a_fault_never_lost(fields, error):
    fake = FakeSandbox(**fields, canary_files=("inj-001",))
    run = run_tier1(fake, rec(), Mode.OFF, 2, 1337)
    assert run.crashed and run.outcome.error == error and run.outcome.rep == 2 and run.badges_sha256 is None
    assert run.canary_files == ("inj-001",)  # what the host saw is kept even when the tier said nothing
    # An attack whose only visible effect is a canary file is still crossed: the oracle does not need the tier's answer.
    assert judge_tier1(Family.INJECTION, rec(), run, TRUTH, "g" * 64)[0] is Verdict.CROSSED
    # With no canary file either, the same silence is a fault.
    bare = run_tier1(FakeSandbox(**fields), rec(), Mode.OFF, 0, 1337)
    assert judge_tier1(Family.MALFORMED, rec(), bare, TRUTH, "g" * 64)[0] is Verdict.FAULT


def test_the_request_carries_the_record_mode_rep_and_seed():
    fake = FakeSandbox()
    run_tier1(fake, rec(), Mode.FULL, 7, 99)
    request = json.loads(fake.stdin)
    assert (request["mode"], request["rep"], request["seed"]) == ("full", 7, 99)
    assert request["record"]["payload_id"] == "inj-001"
