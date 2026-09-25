"""Summarise a results file: per-payload verdicts across the four modes, verdict counts per mode, why each block
happened, and the benign false-positive count.

    python -m harness.summarize harness/results/raw/<run>/results.csv
"""

import sys
from collections import Counter, defaultdict
from pathlib import Path

from contracts import Family, Mode
from harness.metrics import read_results

MODES = (Mode.OFF, Mode.VALIDATE_ONLY, Mode.PARAMETERISE_ONLY, Mode.FULL)


def summarize(path: Path | str) -> str:
    rows = read_results(path)
    by_payload: dict[str, dict[str, object]] = defaultdict(dict)
    for r in rows:
        by_payload[r.payload_id][r.mode.value] = r
    lines = [f"{len(rows)} rows, {len(by_payload)} payloads, decoder condition(s): {sorted({r.decoder_mode for r in rows})}", ""]

    lines.append(f"{'payload':16} {'off':26} {'validate_only':14} {'parameterise_only':18} full")
    for pid in sorted(by_payload):
        modes = by_payload[pid]
        if modes[Mode.OFF.value].family is Family.BENIGN:
            continue
        off = modes[Mode.OFF.value]
        cell = off.verdict.value + (f"[{off.signals}]" if off.signals else "") + (f" {off.error}" if off.error else "")
        lines.append(f"{pid:16} {cell:26} {modes['validate_only'].verdict.value:14} "
                     f"{modes['parameterise_only'].verdict.value:18} {modes['full'].verdict.value}")

    lines += ["", "verdict counts per mode:"]
    for mode in MODES:
        counts = Counter(r.verdict.value for r in rows if r.mode is mode)
        lines.append(f"  {mode.value:18} " + ", ".join(f"{v} {n}" for v, n in sorted(counts.items())))

    lines += ["", "why validation blocked (validate_only):"]
    reasons = Counter(r.detail for r in rows if r.mode is Mode.VALIDATE_ONLY and r.blocked)
    lines += [f"  {reason}: {n}" for reason, n in sorted(reasons.items())] or ["  none"]

    benign = [r for r in rows if r.family is Family.BENIGN]
    false_positives = [r for r in benign if r.blocked]
    lines += ["", f"benign rows: {len(benign)}; benign_ok: {sum(r.verdict.value == 'benign_ok' for r in benign)}; "
                  f"refused by the boundary (false positives): {len(false_positives)}"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python -m harness.summarize results.csv", file=sys.stderr)
        return 2
    print(summarize(args[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
