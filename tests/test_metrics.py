import pytest

from contracts import ResultRow
from harness.compare import compare_results
from harness.metrics import COLUMNS, ResultWriter, read_results


def row(**over):
    base = dict(tier="tier1", mode="off", payload_id="inj-001", rep=0, run_id="run-1", family="injection", subset="naive",
                decoder_mode="default", decode_status="ok", verdict="crossed", signals="A", handle_ns=5000)
    base.update(over)
    return ResultRow(**base)


def test_the_columns_are_the_result_row_schema_in_order():
    assert COLUMNS[:4] == ("tier", "mode", "payload_id", "rep") and COLUMNS[-3:] == ("decode_status", "verdict", "signals")
    assert "decoder_mode" in COLUMNS and len(COLUMNS) == len(ResultRow.model_fields)


def test_rows_round_trip_through_the_csv_exactly(tmp_path):
    rows = [
        row(),
        row(mode="full", blocked=True, verdict="blocked", signals="", handle_ns=None, defense_ns=900, detail="refused: charset"),
        row(payload_id="mal-001", family="malformed", verdict="fault", signals="", error="OperationalError", detail='near "x": syntax'),
        row(payload_id="mal-002", family="malformed", decode_status="no_symbol", verdict="not_delivered", signals="", handle_ns=None),
    ]
    with ResultWriter(tmp_path / "r.csv") as w:
        for r in rows:
            w.write(r)
    assert [r.model_dump() for r in read_results(tmp_path / "r.csv")] == [r.model_dump() for r in rows]


def test_a_duplicate_row_identity_is_refused_but_a_different_mode_is_a_different_row(tmp_path):
    with ResultWriter(tmp_path / "r.csv") as w:
        w.write(row())
        w.write(row(mode="full", blocked=True, verdict="blocked", signals=""))  # same payload, another mode: allowed
        with pytest.raises(ValueError, match="duplicate"):
            w.write(row())  # the same identity again


def test_only_a_validated_row_can_be_written_and_a_file_is_never_overwritten(tmp_path):
    with ResultWriter(tmp_path / "r.csv") as w:
        with pytest.raises(TypeError):
            w.write({"tier": "tier1"})
    with pytest.raises(FileExistsError):
        ResultWriter(tmp_path / "r.csv")


def test_a_file_with_the_wrong_columns_is_refused_on_read(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError, match="schema"):
        read_results(bad)


def test_a_tampered_cell_that_breaks_the_contract_is_refused_on_read(tmp_path):
    with ResultWriter(tmp_path / "r.csv") as w:
        w.write(row())
    path = tmp_path / "r.csv"
    path.write_text(path.read_text().replace("crossed", "benign_ok"))  # a benign verdict on an attack row
    with pytest.raises(ValueError):
        read_results(path)


# --- compare -------------------------------------------------------------------------------------------------------


def write(tmp_path, name, rows):
    with ResultWriter(tmp_path / name) as w:
        for r in rows:
            w.write(r)
    return tmp_path / name


def test_runs_that_differ_only_in_timing_and_run_id_compare_equal(tmp_path):
    a = write(tmp_path, "a.csv", [row(run_id="run-1", handle_ns=100), row(mode="full", blocked=True, verdict="blocked", signals="", handle_ns=None, defense_ns=5)])
    b = write(tmp_path, "b.csv", [row(run_id="run-2", handle_ns=999), row(mode="full", blocked=True, verdict="blocked", signals="", handle_ns=None, defense_ns=77)])
    assert compare_results(a, b) == []


def test_compare_reports_a_changed_verdict_a_missing_row_and_an_extra_row(tmp_path):
    a = write(tmp_path, "a.csv", [row(), row(payload_id="inj-002")])
    b = write(tmp_path, "b.csv", [row(verdict="no_effect", signals=""), row(payload_id="inj-003")])
    text = " | ".join(compare_results(a, b))
    assert "verdict differs" in text and "signals differs" in text
    assert "inj-002" in text and "only in the first file" in text and "inj-003" in text and "only in the second file" in text


def test_timing_columns_are_compared_only_when_asked(tmp_path):
    a = write(tmp_path, "a.csv", [row(handle_ns=1)])
    b = write(tmp_path, "b.csv", [row(handle_ns=2)])
    assert compare_results(a, b) == []
    assert any("handle_ns" in p for p in compare_results(a, b, ignore=("run_id",)))
