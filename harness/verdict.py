"""The verdict a row gets, as a pure function of what was observed (docs/oracles.md section 2, approved at G1).

Precedence, first match wins:
  1. not delivered                                  -> not_delivered
  2. attack row and any oracle signal fired         -> crossed (even if the tier also reported a block)
  3. the tier reported blocked or gated             -> blocked
  4. an unhandled error, timeout or crash           -> fault
  5. attack row -> no_effect; benign row -> benign_ok if its benign check passed, otherwise fault
"""

from contracts import DELIVERED_STATUSES, DecodeStatus, Family, Verdict


def decide_verdict(
    *,
    family: Family,
    decode_status: DecodeStatus,
    blocked: bool,
    gated: bool,
    errored: bool,
    signal_fired: bool,
    benign_check_passed: bool,
) -> Verdict:
    if decode_status not in DELIVERED_STATUSES:
        return Verdict.NOT_DELIVERED
    attack = family is not Family.BENIGN
    if attack and signal_fired:
        return Verdict.CROSSED
    if blocked or gated:
        return Verdict.BLOCKED
    if errored:
        return Verdict.FAULT
    if attack:
        return Verdict.NO_EFFECT
    return Verdict.BENIGN_OK if benign_check_passed else Verdict.FAULT
