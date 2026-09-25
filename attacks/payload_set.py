"""The full Tier 1 payload set: the hand-written attacks (attacks/payloads.yaml) plus benign payloads derived from
the seeded badge database (docs/oracles.md section 4).

Benign payloads are derived, not listed, so they cannot drift out of step with the ground truth: every active and
revoked badge, a number of well-formed ids that are not in the database, and a few of the actives as Code 128.
This is the first-CSV set. The 1000-item benign set that decision D14 needs for a false-positive rate comes later.
"""

import random
from pathlib import Path

from contracts import Family, PayloadSpec, Subset, TierId, load_payload_specs
from tiers.badges import ground_truth

YAML = Path(__file__).parent / "payloads.yaml"


def benign_specs(seed: int, *, n_unknown: int = 40, n_code128: int = 10) -> list[PayloadSpec]:
    truth = ground_truth(seed)
    active, revoked = sorted(truth.active_ids), sorted(truth.revoked_ids)
    known = truth.active_ids | truth.revoked_ids | {truth.restricted_id}
    rng = random.Random(seed + 1)
    unknown: list[str] = []
    while len(unknown) < n_unknown:
        candidate = f"B-{rng.randrange(1, 1_000_000):06d}"
        if candidate not in known and candidate not in unknown:
            unknown.append(candidate)

    def spec(pid: str, text: str, symbology: str = "qr") -> PayloadSpec:
        return PayloadSpec(
            id=pid, family=Family.BENIGN, subset=Subset.BENIGN, target_tiers=[TierId.TIER1], symbology=symbology,
            content_text=text, oracle_ref="t1.benign", seed=seed, expected_decode="ok",
        )

    return (
        [spec(f"ben-a-{i:03d}", t) for i, t in enumerate(active, 1)]
        + [spec(f"ben-r-{i:03d}", t) for i, t in enumerate(revoked, 1)]
        + [spec(f"ben-u-{i:03d}", t) for i, t in enumerate(unknown, 1)]
        + [spec(f"ben-c128-{i:02d}", t, "code128") for i, t in enumerate(active[:n_code128], 1)]
    )


def load_payload_set(seed: int, yaml_path: Path = YAML) -> list[PayloadSpec]:
    specs = load_payload_specs(yaml_path) + benign_specs(seed)
    ids = [s.id for s in specs]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"payload ids clash between the attack list and the derived benign set: {dupes}")
    return sorted(specs, key=lambda s: s.id)
