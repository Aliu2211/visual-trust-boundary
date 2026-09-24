"""What an injected string can and cannot do through Python's sqlite3, for the containment design (gate G2).

Run inside the environment the vulnerable tier will run in (the Bookworm image, later the Pi):

    python tools/probes/sqlite_injection_limits.py

Capture it as evidence with:

    python tools/capture_evidence.py E-0NN -- python tools/probes/sqlite_injection_limits.py

Each case sends a string-built query through Cursor.execute(), as the vulnerable Tier 1 handler does, and
prints whether the library accepted or rejected it. Nothing is attempted against anything but an in-memory
database and a path that is checked afterwards.
"""

import sqlite3
import sys
import tempfile
from pathlib import Path


def attempt(label: str, sql: str, conn: sqlite3.Connection) -> None:
    try:
        conn.execute(sql)
    except Exception as exc:  # noqa: BLE001 - the exception type is the result
        print(f"{label:52} rejected: {type(exc).__name__}: {exc}")
    else:
        print(f"{label:52} ACCEPTED")


def main() -> int:
    print(f"python {sys.version.split()[0]} | sqlite {sqlite3.sqlite_version}")
    conn = sqlite3.connect(":memory:")
    conn.execute("create table badges(id text)")
    conn.execute("insert into badges values ('B-000001')")

    probe = Path(tempfile.mkdtemp()) / "attached.db"
    attempt("stacked statement (second statement: DROP TABLE)", "select * from badges where id = 'x'; drop table badges", conn)
    still = conn.execute("select count(*) from sqlite_master where name = 'badges'").fetchone()[0]
    print(f"{'table still exists after the stacked attempt':52} {bool(still)}")
    attempt("load_extension through SQL", "select load_extension('x')", conn)
    attempt("ATTACH smuggled after a SELECT", f"select 1; attach database '{probe}' as t", conn)
    print(f"{'file created by the ATTACH attempt':52} {probe.exists()}")
    print(f"{'Connection.enable_load_extension exists':52} {hasattr(conn, 'enable_load_extension')}")
    attempt("PRAGMA via a single injected statement (allowed kind)", "pragma table_info(badges)", conn)
    return 0


if __name__ == "__main__":
    sys.exit(main())
