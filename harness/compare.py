"""Compare two result files, ignoring what legitimately differs between runs (plan.md P3 acceptance: a re-run
reproduces every non-timing column exactly).

    python -m harness.compare a/results.csv b/results.csv
"""

import sys
from pathlib import Path

from harness.metrics import COLUMNS, read_results

TIMING = ("handle_ns", "defense_ns")
PER_RUN = ("run_id",)  # named by the decode step, so it differs between runs by design


def compare_results(a: Path | str, b: Path | str, ignore: tuple[str, ...] = TIMING + PER_RUN) -> list[str]:
    def keyed(path):
        return {(r.tier.value, r.mode.value, r.decoder_mode, r.payload_id, r.rep): r for r in read_results(path)}

    left, right = keyed(a), keyed(b)
    problems = [f"{key}: only in the first file" for key in sorted(left.keys() - right.keys())]
    problems += [f"{key}: only in the second file" for key in sorted(right.keys() - left.keys())]
    compared = [c for c in COLUMNS if c not in ignore]
    for key in sorted(left.keys() & right.keys()):
        for column in compared:
            x, y = left[key].model_dump(mode="json")[column], right[key].model_dump(mode="json")[column]
            if x != y:
                problems.append(f"{key}: {column} differs ({x!r} then {y!r})")
    return problems


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: python -m harness.compare A.csv B.csv", file=sys.stderr)
        return 2
    problems = compare_results(*args)
    for problem in problems:
        print(problem)
    print(f"{len(problems)} differences (ignoring {', '.join(TIMING + PER_RUN)})")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
