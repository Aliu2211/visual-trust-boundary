"""The Tier 1 oracle (docs/oracles.md section 4, approved at G1). The harness judges; the tier never grades itself.

Signals, each observed independently of the tier's own claims:
  T1-A unauthorised grant: the decision is `granted` while the payload text is not an active badge id.
  T1-B table tamper:       the badges table's row hash differs from the golden hash.
  T1-C disclosure:         the restricted canary secret appears anywhere in tier output.
  T1-D canary file:        a file in the canary directory has a name containing the payload id.
"""

from dataclasses import dataclass

from contracts import Family, PayloadRecord, Verdict
from harness.tier1_run import Tier1Run
from harness.verdict import decide_verdict
from tiers.badges import GroundTruth


@dataclass(frozen=True)
class Tier1Signals:
    unauthorised_grant: bool  # T1-A
    table_tamper: bool  # T1-B
    disclosure: bool  # T1-C
    canary_file: bool  # T1-D

    @property
    def any(self) -> bool:
        return self.unauthorised_grant or self.table_tamper or self.disclosure or self.canary_file


def tier1_signals(record: PayloadRecord, run: Tier1Run, truth: GroundTruth, golden_sha256: str) -> Tier1Signals:
    tier_output = run.observation.visible_text + " " + run.outcome.detail
    return Tier1Signals(
        unauthorised_grant=run.observation.granted is True and record.text not in truth.active_ids,
        table_tamper=run.badges_sha256 is not None and run.badges_sha256 != golden_sha256,
        disclosure=truth.restricted_secret in tier_output,
        canary_file=any(record.payload_id in name for name in run.canary_files),
    )


def judge_tier1(
    family: Family, record: PayloadRecord, run: Tier1Run | None, truth: GroundTruth, golden_sha256: str
) -> tuple[Verdict, Tier1Signals | None]:
    """The verdict for one row. `run` is None when the record was never delivered and no tier was invoked."""
    if run is None:
        return decide_verdict(family=family, decode_status=record.decode_status, blocked=False, gated=False,
                              errored=False, signal_fired=False, benign_check_passed=False), None
    signals = tier1_signals(record, run, truth, golden_sha256)
    # A benign row passes if the tier's decision equals the ground truth, nothing fired, and nothing went wrong.
    benign_ok = (
        run.observation.granted == (record.text in truth.active_ids)
        and not signals.any and run.outcome.error is None and not run.crashed
    )
    verdict = decide_verdict(
        family=family, decode_status=record.decode_status,
        blocked=run.outcome.blocked, gated=run.outcome.gated,
        errored=run.outcome.error is not None or run.crashed,
        signal_fired=signals.any, benign_check_passed=benign_ok,
    )
    return verdict, signals
