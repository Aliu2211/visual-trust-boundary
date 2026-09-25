"""Tier 1: a rule-based access node doing an identifier lookup (plan.md section 4; docs/oracles.md section 4).

DELIBERATELY VULNERABLE. Without control 2 (`off`, `validate_only`) the decoded text is concatenated into a SQL
string and into a shell command. Those paths run only inside the sandbox (docs/containment.md) and refuse to run
anywhere else. Modes: off (no control), validate_only (control 1), parameterise_only (control 2), full (both).

The tier reports what it did. It never says whether that crossed the boundary; the harness oracle decides that.
"""

import json
import os
import sqlite3
import subprocess
import time

from contracts import Mode, Observation, PayloadRecord, TierId, TierOutcome
from defense.boundary import check
from defense.grammar import Use

AUDIT_PATH = "/audit/audit.log"
_VALIDATING = frozenset({Mode.VALIDATE_ONLY, Mode.FULL})
_PARAMETERISED = frozenset({Mode.PARAMETERISE_ONLY, Mode.FULL})
_SHELL_TIMEOUT_S = 5


def _decode_naively(record: PayloadRecord) -> str:
    """What a tier that never checked the encoding does with bad bytes: replace them (source plan section 3)."""
    if record.text is not None:
        return record.text
    return (record.raw_bytes or b"").decode("utf-8", errors="replace")


def _lookup(conn: sqlite3.Connection, text: str, *, parameterised: bool):
    if parameterised:
        return conn.execute("SELECT id, holder, active FROM badges WHERE id = ?", (text,)).fetchone()
    # VULNERABLE BY DESIGN: the identifier is concatenated into the query string.
    return conn.execute("SELECT id, holder, active FROM badges WHERE id = '%s'" % text).fetchone()


def _audit(text: str, *, parameterised: bool, audit_path: str) -> None:
    if parameterised:  # the identifier is data: written as one JSON line, no shell
        with open(audit_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": text}) + "\n")
        return
    # VULNERABLE BY DESIGN: the identifier is concatenated into a shell command string.
    subprocess.run(
        "echo " + text + " >> " + audit_path,
        shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=_SHELL_TIMEOUT_S, check=False,
    )


def handle(
    conn: sqlite3.Connection, record: PayloadRecord, mode: Mode, rep: int, *, audit_path: str = AUDIT_PATH
) -> tuple[TierOutcome, Observation]:
    if mode not in _PARAMETERISED and os.environ.get("VTB_IN_SANDBOX") != "1":
        raise RuntimeError("the vulnerable Tier 1 paths run only inside the sandbox (docs/containment.md)")
    if record.payload_id is None:
        raise ValueError("a record needs a payload_id to be handled")

    start = time.perf_counter_ns()
    defense_ns = None

    def outcome(**fields) -> TierOutcome:
        return TierOutcome(
            tier=TierId.TIER1, mode=mode, payload_id=record.payload_id, rep=rep,
            handle_ns=time.perf_counter_ns() - start, defense_ns=defense_ns, **fields,
        )

    if mode in _VALIDATING:
        t0 = time.perf_counter_ns()
        decision = check(record, Use.IDENTIFIER)
        defense_ns = time.perf_counter_ns() - t0
        if not decision.allow:
            reason = decision.reason_code.value
            return (
                outcome(blocked=True, detail=f"refused: {reason}"),
                Observation(granted=False, visible_text=f"DENIED: input refused ({reason})"),
            )

    text = _decode_naively(record)
    parameterised = mode in _PARAMETERISED
    try:
        row = _lookup(conn, text, parameterised=parameterised)
    except (sqlite3.Error, ValueError) as exc:  # a malformed query: reported, and the audit step is never reached
        return outcome(error=type(exc).__name__, detail=str(exc)[:200]), Observation(visible_text=f"ERROR: {exc}"[:4096])

    granted = row is not None and row[2] == 1
    visible = f"{'GRANTED' if granted else 'DENIED'} id={row[0]} holder={row[1]}" if row else "DENIED: unknown id"
    observation = Observation(granted=granted, matched_id=None if row is None else str(row[0]), visible_text=visible[:4096])
    try:
        _audit(text, parameterised=parameterised, audit_path=audit_path)
    except subprocess.TimeoutExpired:
        # A fixed description: the exception's own text embeds the measured elapsed time, which made two runs of the
        # same payload differ in a non-timing column (E-025).
        return outcome(error="TimeoutExpired", detail=f"audit shell command exceeded {_SHELL_TIMEOUT_S} s"), observation
    except (OSError, ValueError, subprocess.SubprocessError) as exc:  # the decision was made; the audit step failed
        return outcome(error=type(exc).__name__, detail=str(exc)[:200]), observation
    return outcome(), observation
