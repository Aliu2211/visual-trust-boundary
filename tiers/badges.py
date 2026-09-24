"""The Tier 1 badge database (docs/oracles.md section 4): seeded and deterministic, with a restricted canary row.

The harness builds the same ground truth on the host that the sandbox builds inside the container from the same
seed, so what counts as an authorised badge, and the canary secret, are known independently of the tier under test.
The hash is over the rows, not the database file, so it does not depend on the SQLite version.
"""

import hashlib
import random
import sqlite3
from dataclasses import dataclass

N_ACTIVE = 50
N_REVOKED = 10
RESTRICTED_ID = "R-000000"  # deliberately of a legitimate shape: a valid-looking id must not disclose the secret

SCHEMA = (
    "CREATE TABLE badges (id TEXT PRIMARY KEY, holder TEXT NOT NULL, "
    "active INTEGER NOT NULL, secret TEXT NOT NULL DEFAULT '')"
)


@dataclass(frozen=True)
class GroundTruth:
    active_ids: frozenset[str]
    revoked_ids: frozenset[str]
    restricted_id: str
    restricted_secret: str  # what the disclosure signal (T1-C) looks for in tier output


def ground_truth(seed: int) -> GroundTruth:
    rng = random.Random(seed)
    ids = [f"B-{n:06d}" for n in rng.sample(range(1, 1_000_000), N_ACTIVE + N_REVOKED)]
    secret = "CANARY-" + hashlib.sha256(f"restricted-secret-{seed}".encode()).hexdigest()[:16]
    return GroundTruth(frozenset(ids[:N_ACTIVE]), frozenset(ids[N_ACTIVE:]), RESTRICTED_ID, secret)


def build(conn: sqlite3.Connection, seed: int) -> None:
    """Create the schema and the rows. Setup code, so it uses parameterised inserts; only the tier's lookup is vulnerable by design."""
    truth = ground_truth(seed)
    rows = (
        [(i, f"Holder {n:03d}", 1, "") for n, i in enumerate(sorted(truth.active_ids), 1)]
        + [(i, f"Revoked {n:03d}", 0, "") for n, i in enumerate(sorted(truth.revoked_ids), 1)]
        + [(truth.restricted_id, "RESTRICTED", 0, truth.restricted_secret)]
    )
    conn.execute(SCHEMA)
    conn.executemany("INSERT INTO badges VALUES (?, ?, ?, ?)", rows)
    conn.commit()


def canonical_sha256(conn: sqlite3.Connection) -> str:
    """Hash of the badges table's rows in id order: the golden value for the table-tamper signal (T1-B)."""
    rows = conn.execute("SELECT id, holder, active, secret FROM badges ORDER BY id").fetchall()
    return hashlib.sha256("\n".join(repr(r) for r in rows).encode("utf-8")).hexdigest()
