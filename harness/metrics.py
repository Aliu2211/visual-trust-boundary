"""Schema-checked, append-only CSV of result rows (plan.md P3.2).

A row that breaks the ResultRow contract cannot be written, an existing file is never overwritten, and a row
identity (run, tier, mode, decoder mode, payload, repetition) can appear only once. Values are written exactly as
observed: `detail` can contain text a payload caused, so open these files with pandas, not a spreadsheet, which
would treat a leading `=`, `+`, `-` or `@` as a formula.
"""

import csv
from pathlib import Path

from contracts import ResultRow

COLUMNS = tuple(ResultRow.model_fields)  # TierOutcome's fields, then the row's own
_NULLABLE = ("error", "handle_ns", "defense_ns")


def row_key(row: ResultRow) -> tuple:
    return (row.run_id, row.tier.value, row.mode.value, row.decoder_mode, row.payload_id, row.rep)


class ResultWriter:
    def __init__(self, path: Path | str) -> None:
        self._fh = open(path, "x", newline="", encoding="utf-8")  # "x": never overwrite
        self._csv = csv.DictWriter(self._fh, fieldnames=COLUMNS, lineterminator="\n")
        self._csv.writeheader()
        self._seen: set[tuple] = set()

    def write(self, row: ResultRow) -> None:
        if not isinstance(row, ResultRow):
            raise TypeError(f"only a validated ResultRow can be written, got {type(row).__name__}")
        key = row_key(row)
        if key in self._seen:
            raise ValueError(f"duplicate row: {key}")
        self._seen.add(key)
        self._csv.writerow(row.model_dump(mode="json"))
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()

    def __enter__(self) -> "ResultWriter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def read_results(path: Path | str) -> list[ResultRow]:
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError(f"{path}: columns {reader.fieldnames} are not the ResultRow schema {list(COLUMNS)}")
        rows = []
        for record in reader:
            for name in _NULLABLE:
                if record[name] == "":
                    record[name] = None
            rows.append(ResultRow.model_validate(record))
    return rows
