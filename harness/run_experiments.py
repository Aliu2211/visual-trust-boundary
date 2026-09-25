"""Run the payload set through Tier 1: decoded records in, result rows out (plan.md P3.2).

    python -m attacks.generate
    python -m decode.capture --run-id r1 --decoder-mode default replay attacks/out --out records-default.jsonl
    python -m harness.run_experiments --records records-default.jsonl

The decode stage and the tier need different environments on the laptop (libzbar in the dev image, Docker on the
host), so they are joined by the records file. On the Pi both run on one machine. One run covers one decoder
condition (decision recorded 2026-09-24); run it once per condition.

For every payload that applies to Tier 1 under the run's decoder condition and every configured Tier 1 mode, the
tier is driven inside the sandbox and the harness oracle judges the result. A record that was not delivered gets
its rows without the tier being invoked. Rows are written in a fixed order so a re-run can be compared exactly.
"""

import argparse
import hashlib
import json
import os
import platform
import sqlite3
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from attacks.payload_set import load_payload_set
from contracts import (
    Config,
    Mode,
    PayloadRecord,
    PayloadSpec,
    ResultRow,
    RunMetadata,
    TierId,
    TierOutcome,
    Verdict,
    load_config,
)
from harness.metrics import ResultWriter, row_key
from harness.oracles import Tier1Signals, judge_tier1
from harness.sandbox import DockerSandbox
from harness.tier1_run import Tier1Run, run_tier1
from tiers import badges
from tools.capture_evidence import docker_version, git_state, sandbox_image

ROOT = Path(__file__).resolve().parent.parent
_SIGNAL_CODES = (("A", "unauthorised_grant"), ("B", "table_tamper"), ("C", "disclosure"), ("D", "canary_file"))


@dataclass(frozen=True)
class Work:
    spec: PayloadSpec
    record: PayloadRecord
    mode: Mode
    rep: int


class RunError(ValueError):
    """The inputs do not describe a run that can be trusted, so nothing is executed."""


def load_records(path: Path | str) -> list[PayloadRecord]:
    with open(path, encoding="utf-8") as fh:
        return [PayloadRecord.model_validate_json(line) for line in fh if line.strip()]


def plan_work(records: list[PayloadRecord], specs: list[PayloadSpec], config: Config) -> tuple[list[Work], list[dict]]:
    """Join records to specs and lay out the matrix. Returns the work and the decode-expectation mismatches."""
    if not records:
        raise RunError("the records file is empty")
    if len({r.run_id for r in records}) != 1 or len({r.decoder_mode for r in records}) != 1:
        raise RunError("a records file must come from one decode run in one decoder mode")
    decoder_mode = records[0].decoder_mode
    tier1 = config.tiers[TierId.TIER1]
    if not tier1.enabled or decoder_mode not in tier1.decoder_modes:
        raise RunError(f"config.yaml does not run tier1 under the {decoder_mode} decoder condition")

    by_id = {s.id: s for s in specs}
    unknown = sorted({r.payload_id for r in records if r.payload_id not in by_id}, key=str)
    if unknown:
        raise RunError(f"records for payloads that are not in the payload set: {unknown}")
    by_record = {r.payload_id: r for r in records}
    if len(by_record) != len(records):
        raise RunError("a payload appears more than once in the records file")

    applicable = [s for s in specs if TierId.TIER1 in s.target_tiers and decoder_mode in s.decoder_modes]
    missing = sorted(s.id for s in applicable if s.id not in by_record)
    if missing:
        raise RunError(f"no record for {len(missing)} payloads that apply to this run (were the images decoded?): {missing[:5]}")

    mismatches = [
        {"payload_id": s.id, "expected_decode": s.expected_decode, "decode_status": by_record[s.id].decode_status.value}
        for s in applicable
        if (s.expected_decode == "ok") != by_record[s.id].delivered
    ]
    work = [
        Work(s, by_record[s.id], mode, rep)
        for s in applicable
        for mode in tier1.modes
        for rep in range(config.reps.correctness)
    ]
    return work, mismatches


def _signal_codes(signals: Tier1Signals | None) -> str:
    return ",".join(code for code, attribute in _SIGNAL_CODES if signals is not None and getattr(signals, attribute))


def execute_one(work: Work, sandbox: DockerSandbox, seed: int, truth: badges.GroundTruth, golden: str) -> ResultRow:
    record = work.record
    run: Tier1Run | None = run_tier1(sandbox, record, work.mode, work.rep, seed) if record.delivered else None
    verdict, signals = judge_tier1(work.spec.family, record, run, truth, golden)
    outcome = run.outcome if run is not None else TierOutcome(
        tier=TierId.TIER1, mode=work.mode, payload_id=work.spec.id, rep=work.rep)
    return ResultRow(
        **outcome.model_dump(),
        run_id=record.run_id, family=work.spec.family, subset=work.spec.subset, decoder_mode=record.decoder_mode,
        decode_status=record.decode_status, verdict=verdict, signals=_signal_codes(signals),
    )


def execute(work: list[Work], sandbox: DockerSandbox, config: Config, *, jobs: int = 1) -> list[ResultRow]:
    truth = badges.ground_truth(config.seed)
    golden_db = sqlite3.connect(":memory:")
    badges.build(golden_db, config.seed)
    golden = badges.canonical_sha256(golden_db)
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        rows = list(pool.map(lambda w: execute_one(w, sandbox, config.seed, truth, golden), work))
    return sorted(rows, key=row_key)


def run_metadata(records: list[PayloadRecord], config_path: Path, decode_meta: dict | None) -> RunMetadata:
    sha, dirty, _ = git_state()
    return RunMetadata(
        run_id=records[0].run_id,
        started_at=datetime.now(UTC),
        git_sha=sha if sha != "unknown" else "0000000",
        git_dirty=dirty != "no",
        config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
        host_label=os.environ.get("VTB_HOST_LABEL", "unlabelled"),
        os=platform.system(), kernel=platform.release(), python=platform.python_version(),
        decoder_mode=records[0].decoder_mode,
        zbar_version=(decode_meta or {}).get("libzbar0"),
        docker_version=docker_version(),
        sandbox_image=sandbox_image(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.run_experiments", description=__doc__.split("\n")[0])
    parser.add_argument("--records", required=True, help="JSON lines from `python -m decode.capture ... replay ... --out`")
    parser.add_argument("--config", default=str(ROOT / "config.yaml"))
    parser.add_argument("--out", help="output folder (default: <results_dir>/raw/<run_id>)")
    parser.add_argument("--jobs", type=int, default=1, help="sandbox calls in parallel; timings are only meaningful at 1")
    parser.add_argument("--allow-decode-mismatch", action="store_true", help="do not fail when a payload decodes unexpectedly")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    config = load_config(config_path)
    records = load_records(args.records)
    meta_path = Path(args.records).with_name(Path(args.records).name + ".meta.json")
    decode_meta = json.loads(meta_path.read_text()) if meta_path.exists() else None

    try:
        work, mismatches = plan_work(records, load_payload_set(config.seed), config)
    except RunError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    ok, reason = DockerSandbox.available()
    if not ok:
        print(f"error: the sandbox is unavailable: {reason}", file=sys.stderr)
        return 2

    out = Path(args.out) if args.out else ROOT / config.paths.results_dir / "raw" / records[0].run_id
    out.mkdir(parents=True, exist_ok=False)
    rows = execute(work, DockerSandbox(), config, jobs=args.jobs)
    with ResultWriter(out / "results.csv") as writer:
        for row in rows:
            writer.write(row)
    (out / "run_meta.json").write_text(run_metadata(records, config_path, decode_meta).model_dump_json(indent=1) + "\n")
    if mismatches:
        (out / "decode_mismatches.json").write_text(json.dumps(mismatches, indent=1) + "\n")

    counts = Counter((r.mode.value, r.verdict.value) for r in rows)
    print(f"{len(rows)} rows ({records[0].decoder_mode} decoder condition) written to {out}")
    for (mode, verdict), n in sorted(counts.items()):
        print(f"  {mode:18} {verdict:14} {n}")
    if mismatches:
        print(f"{len(mismatches)} payloads did not decode as expected; see decode_mismatches.json", file=sys.stderr)
        return 0 if args.allow_decode_mismatch else 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
