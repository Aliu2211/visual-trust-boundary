"""The command the harness runs inside the sandbox for one Tier 1 call: read a request on stdin, build the
seeded database, run the handler, print one JSON line. Harness-owned; baked into the read-only image.

A crash inside the tier is itself a result, so it is caught here and reported as an error instead of lost.
If the process is killed outright (a payload can do that), no line is printed and the host records a fault.
"""

import json
import sqlite3
import sys

from contracts import Mode, Observation, PayloadRecord, TierId, TierOutcome
from tiers import badges, tier1_rulebased


def main() -> int:
    request = json.load(sys.stdin)
    record = PayloadRecord.model_validate(request["record"])
    mode, rep, seed = Mode(request["mode"]), int(request["rep"]), int(request["seed"])

    conn = sqlite3.connect(":memory:")
    badges.build(conn, seed)
    try:
        outcome, observation = tier1_rulebased.handle(conn, record, mode, rep)
    except Exception as exc:  # noqa: BLE001 - an unhandled tier crash is a result, not something to hide
        outcome = TierOutcome(tier=TierId.TIER1, mode=mode, payload_id=record.payload_id, rep=rep,
                              error=type(exc).__name__, detail=str(exc)[:200])
        observation = Observation()
    try:
        table_sha = badges.canonical_sha256(conn)
    except sqlite3.Error:
        table_sha = None
    print(json.dumps({
        "outcome": outcome.model_dump(mode="json"),
        "observation": observation.model_dump(mode="json"),
        "state": {"badges_sha256": table_sha},
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
