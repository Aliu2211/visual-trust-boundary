"""Run one Tier 1 call inside the sandbox and bring back what was observed (docs/containment.md, docs/oracles.md section 4)."""

import json
from dataclasses import dataclass

from contracts import Mode, Observation, PayloadRecord, TierId, TierOutcome
from harness.sandbox import DockerSandbox


@dataclass(frozen=True)
class Tier1Run:
    outcome: TierOutcome
    observation: Observation
    badges_sha256: str | None  # computed inside the sandbox after the handler, by harness-owned code
    canary_files: tuple[str, ...]  # listed by the harness from the host side of the mount
    crashed: bool  # no parseable answer came back: the tier died, was killed, or timed out
    exit_code: int


def run_tier1(sandbox: DockerSandbox, record: PayloadRecord, mode: Mode, rep: int, seed: int) -> Tier1Run:
    request = json.dumps({"record": record.model_dump(mode="json"), "mode": mode.value, "rep": rep, "seed": seed})
    result = sandbox.run(["python", "-m", "tiers.sandbox_entry"], stdin=request)
    try:
        answer = json.loads(result.stdout.strip().splitlines()[-1])
        return Tier1Run(
            outcome=TierOutcome.model_validate(answer["outcome"]),
            observation=Observation.model_validate(answer["observation"]),
            badges_sha256=answer["state"]["badges_sha256"],
            canary_files=result.canary_files,
            crashed=False,
            exit_code=result.exit_code,
        )
    except (IndexError, ValueError, KeyError, TypeError):  # no parseable answer: report a fault, never guess
        why = "Timeout" if result.timed_out else "NoAnswer"
        return Tier1Run(
            outcome=TierOutcome(tier=TierId.TIER1, mode=mode, payload_id=record.payload_id, rep=rep, error=why,
                                detail=f"exit code {result.exit_code}"),
            observation=Observation(),
            badges_sha256=None,
            canary_files=result.canary_files,
            crashed=True,
            exit_code=result.exit_code,
        )
