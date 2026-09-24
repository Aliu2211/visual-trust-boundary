import base64
import sqlite3

import pytest

from contracts import PayloadRecord
from defense.boundary import check
from defense.grammar import Use
from tiers.badges import N_ACTIVE, N_REVOKED, RESTRICTED_ID, build, canonical_sha256, ground_truth

SEED = 1337
# The reference value for the config seed. If it changes on another machine or Python build, the ground
# truth differs and results are not comparable, so this is a reproducibility guard, not just a unit test.
SEED_1337_SHA256 = "0d28bf3b30d1c6a5d521c1b0b1233847a991da9a033e927f907a159baf616dab"


def db(seed=SEED) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    build(conn, seed)
    return conn


def rec(text: str) -> PayloadRecord:
    return PayloadRecord(run_id="r", payload_id="p", raw_bytes_b64=base64.b64encode(text.encode()).decode(), text=text,
                         decode_status="ok", symbology="QRCODE", source_image="p.png", image_sha256="a" * 64,
                         t_capture=0.0, t_decode_ns=1)


def test_the_seed_builds_the_documented_database():
    assert canonical_sha256(db()) == SEED_1337_SHA256


def test_the_ground_truth_is_deterministic_and_seed_dependent():
    assert ground_truth(SEED) == ground_truth(SEED)
    assert ground_truth(1).active_ids != ground_truth(2).active_ids
    assert canonical_sha256(db(1)) != canonical_sha256(db(2))


def test_sizes_and_disjointness():
    t = ground_truth(SEED)
    assert len(t.active_ids) == N_ACTIVE and len(t.revoked_ids) == N_REVOKED
    assert not t.active_ids & t.revoked_ids
    assert t.restricted_id == RESTRICTED_ID and RESTRICTED_ID not in t.active_ids | t.revoked_ids
    assert db().execute("select count(*), sum(active) from badges").fetchone() == (N_ACTIVE + N_REVOKED + 1, N_ACTIVE)


def test_the_table_matches_the_ground_truth():
    t = ground_truth(SEED)
    rows = {r[0]: r for r in db().execute("select id, holder, active, secret from badges")}
    assert {i for i, r in rows.items() if r[2] == 1} == t.active_ids
    assert {i for i, r in rows.items() if r[2] == 0} == t.revoked_ids | {RESTRICTED_ID}
    assert rows[RESTRICTED_ID][3] == t.restricted_secret


def test_the_canary_secret_is_in_exactly_one_row_and_looks_like_a_canary():
    t = ground_truth(SEED)
    holders_and_secrets = db().execute("select holder, secret from badges where id != ?", (RESTRICTED_ID,)).fetchall()
    assert all(t.restricted_secret not in field for row in holders_and_secrets for field in row)
    assert t.restricted_secret.startswith("CANARY-") and len(t.restricted_secret) == len("CANARY-") + 16


@pytest.mark.parametrize("which", ["active_ids", "revoked_ids"])
def test_every_legitimate_id_passes_the_defense_grammar(which):
    # The defense's false-positive rate on the modelled system's own identifiers must start at zero.
    ids = getattr(ground_truth(SEED), which)
    assert ids and all(check(rec(i), Use.IDENTIFIER).allow for i in ids)


def test_the_restricted_id_is_grammar_valid_but_not_a_grant():
    assert check(rec(RESTRICTED_ID), Use.IDENTIFIER).allow
    assert db().execute("select active from badges where id = ?", (RESTRICTED_ID,)).fetchone() == (0,)


@pytest.mark.parametrize(
    "tamper",
    [
        "update badges set active = 1 where id = 'R-000000'",
        "delete from badges where id = 'R-000000'",
        "insert into badges values ('B-000001', 'x', 1, '')",
        "update badges set holder = 'changed' where holder = 'Holder 001'",
        "update badges set secret = 'x' where id = 'R-000000'",
    ],
)
def test_the_canonical_hash_detects_every_kind_of_tampering(tamper):
    conn = db()
    before = canonical_sha256(conn)
    conn.execute(tamper)
    assert canonical_sha256(conn) != before


def test_the_canonical_hash_does_not_depend_on_row_insertion_order():
    a, b = db(), sqlite3.connect(":memory:")
    b.execute("CREATE TABLE badges (id TEXT PRIMARY KEY, holder TEXT NOT NULL, active INTEGER NOT NULL, secret TEXT NOT NULL DEFAULT '')")
    for row in reversed(a.execute("select id, holder, active, secret from badges").fetchall()):
        b.execute("insert into badges values (?, ?, ?, ?)", row)
    assert canonical_sha256(a) == canonical_sha256(b)
