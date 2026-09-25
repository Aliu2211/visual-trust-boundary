"""The experiment runner's orchestration, with a fake sandbox that answers the way tiers/sandbox_entry.py does."""

import base64
import json
import re
import threading

import pytest

from attacks.payload_set import load_payload_set
from contracts import DecodeStatus, Mode, PayloadRecord, TierId, Verdict, load_config
from harness import run_experiments as rx
from harness.metrics import read_results
from harness.sandbox import SandboxResult
from tiers import badges

ROOT = rx.ROOT
CONFIG = load_config(ROOT / "config.yaml")
SPECS = load_payload_set(CONFIG.seed)
TRUTH = badges.ground_truth(CONFIG.seed)
import sqlite3

_db = sqlite3.connect(":memory:")
badges.build(_db, CONFIG.seed)
GOLDEN = badges.canonical_sha256(_db)
IDENT = re.compile(r"[A-Z]{1,4}-[0-9]{4,8}")


class FakeSandbox:
    """Stands in for Docker: validating modes refuse anything off-grammar, the others 'grant' the active badges,
    and the shell payload leaves its canary file in `off` mode."""

    def __init__(self):
        self.calls = 0
        self._lock = threading.Lock()

    def run(self, argv, *, stdin=None, timeout=None):
        with self._lock:
            self.calls += 1
        request = json.loads(stdin)
        rec, mode = request["record"], request["mode"]
        text = rec["text"] or ""
        validating = mode in ("validate_only", "full")
        blocked = validating and not IDENT.fullmatch(text)
        granted = (not blocked) and text in TRUTH.active_ids
        outcome = dict(tier="tier1", mode=mode, payload_id=rec["payload_id"], rep=request["rep"], blocked=blocked, gated=False,
                       error=None, handle_ns=1000, defense_ns=10 if validating else None,
                       detail="refused: charset" if blocked else "")
        observation = dict(granted=False if blocked else granted, matched_id=text if granted else None,
                           visible_text="DENIED" if not granted else f"GRANTED id={text}")
        canary = ("inj-shell-001",) if (mode == "off" and rec["payload_id"] == "inj-shell-001") else ()
        stdout = json.dumps({"outcome": outcome, "observation": observation, "state": {"badges_sha256": GOLDEN}}) + "\n"
        return SandboxResult(stdout=stdout, stderr="", exit_code=0, timed_out=False, output_truncated=False, canary_files=canary)


def records_for(specs, decoder_mode="default", run_id="run-x", undelivered=()):
    out = []
    for s in specs:
        if TierId.TIER1 not in s.target_tiers or decoder_mode not in s.decoder_modes:
            continue
        common = dict(run_id=run_id, payload_id=s.id, decoder_mode=decoder_mode, source_image=f"{s.id}.png",
                      image_sha256="a" * 64, t_capture=0.0, t_decode_ns=1)
        if s.id in undelivered or s.damage != "none":
            out.append(PayloadRecord(decode_status="no_symbol", **common))
            continue
        raw = s.content_bytes
        try:
            text = raw.decode("utf-8")
            out.append(PayloadRecord(decode_status="ok", raw_bytes_b64=base64.b64encode(raw).decode(), text=text, symbology="QRCODE", **common))
        except UnicodeDecodeError:
            out.append(PayloadRecord(decode_status="invalid_utf8", raw_bytes_b64=base64.b64encode(raw).decode(), symbology="QRCODE", **common))
    return out


def applicable(decoder_mode):
    return [s for s in SPECS if TierId.TIER1 in s.target_tiers and decoder_mode in s.decoder_modes]


# --- planning ---------------------------------------------------------------------------------------------------------


def test_the_matrix_is_every_applicable_payload_times_every_configured_mode():
    work, mismatches = rx.plan_work(records_for(SPECS), SPECS, CONFIG)
    assert len(work) == len(applicable("default")) * len(CONFIG.tiers[TierId.TIER1].modes) * CONFIG.reps.correctness
    assert {w.mode for w in work} == set(CONFIG.tiers[TierId.TIER1].modes)
    assert mismatches == []


def test_raw_only_payloads_are_in_the_raw_run_and_not_in_the_default_one():
    default_ids = {w.spec.id for w in rx.plan_work(records_for(SPECS, "default"), SPECS, CONFIG)[0]}
    raw_ids = {w.spec.id for w in rx.plan_work(records_for(SPECS, "raw"), SPECS, CONFIG)[0]}
    assert {"mal-utf8-001", "mal-utf8-002"} <= raw_ids and not {"mal-utf8-001", "mal-utf8-002"} & default_ids
    assert default_ids <= raw_ids


def test_a_payload_that_decodes_unexpectedly_is_reported():
    records = records_for(SPECS, undelivered={"inj-sql-001"})  # expected to decode, did not
    records = [r for r in records if r.payload_id != "mal-trunc-001"] + [
        PayloadRecord(run_id="run-x", payload_id="mal-trunc-001", decoder_mode="default", decode_status="ok",
                      raw_bytes_b64=base64.b64encode(b"x").decode(), text="x", symbology="QRCODE", source_image="m.png",
                      image_sha256="a" * 64, t_capture=0.0, t_decode_ns=1)]  # expected not to decode, did
    _, mismatches = rx.plan_work(records, SPECS, CONFIG)
    assert {m["payload_id"] for m in mismatches} == {"inj-sql-001", "mal-trunc-001"}


@pytest.mark.parametrize(
    "mutate,message",
    [
        (lambda r: [], "empty"),
        (lambda r: r[:-1], "no record for"),
        (lambda r: r + [r[0]], "more than once"),
        (lambda r: r[:-1] + [r[-1].model_copy(update={"decoder_mode": "raw"})], "one decoder mode"),
        (lambda r: r[:-1] + [r[-1].model_copy(update={"run_id": "other"})], "one decode run"),
        (lambda r: r + [r[0].model_copy(update={"payload_id": "not-a-payload"})], "not in the payload set"),
    ],
)
def test_inputs_that_do_not_describe_a_trustworthy_run_stop_it(mutate, message):
    with pytest.raises(rx.RunError, match=message):
        rx.plan_work(mutate(records_for(SPECS)), SPECS, CONFIG)


def test_a_decoder_condition_the_config_does_not_run_stops_it():
    config = CONFIG.model_copy(update={"tiers": {**CONFIG.tiers, TierId.TIER1: CONFIG.tiers[TierId.TIER1].model_copy(update={"decoder_modes": ("raw",)})}})
    with pytest.raises(rx.RunError, match="does not run tier1 under the default"):
        rx.plan_work(records_for(SPECS, "default"), SPECS, config)


# --- executing ----------------------------------------------------------------------------------------------------------


def test_an_undelivered_record_gets_rows_without_the_tier_being_invoked():
    work, _ = rx.plan_work(records_for(SPECS), SPECS, CONFIG)
    fake = FakeSandbox()
    rows = rx.execute(work, fake, CONFIG)
    delivered = [w for w in work if w.record.delivered]
    assert fake.calls == len(delivered) and len(rows) == len(work)
    truncated = [r for r in rows if r.payload_id.startswith("mal-trunc")]
    assert truncated and all(r.verdict is Verdict.NOT_DELIVERED and r.handle_ns is None and r.decode_status is DecodeStatus.NO_SYMBOL for r in truncated)


def test_verdicts_and_signals_come_out_of_the_oracle_and_are_named_on_the_row():
    work, _ = rx.plan_work(records_for(SPECS), SPECS, CONFIG)
    rows = {(r.payload_id, r.mode.value): r for r in rx.execute(work, FakeSandbox(), CONFIG)}
    assert rows[("inj-shell-001", "off")].verdict is Verdict.CROSSED and rows[("inj-shell-001", "off")].signals == "D"
    assert rows[("inj-shell-001", "full")].verdict is Verdict.BLOCKED and rows[("inj-shell-001", "full")].signals == ""
    assert rows[("ben-a-001", "full")].verdict is Verdict.BENIGN_OK and rows[("ben-r-001", "off")].verdict is Verdict.BENIGN_OK


def test_the_rows_are_in_a_fixed_order_whatever_the_parallelism():
    work, _ = rx.plan_work(records_for(SPECS), SPECS, CONFIG)
    one = rx.execute(work, FakeSandbox(), CONFIG, jobs=1)
    four = rx.execute(work, FakeSandbox(), CONFIG, jobs=4)
    assert [r.model_dump() for r in one] == [r.model_dump() for r in four]
    assert [rx.row_key(r) for r in one] == sorted(rx.row_key(r) for r in one)


# --- the whole thing through main() ----------------------------------------------------------------------------------


@pytest.fixture
def cli(monkeypatch, tmp_path):
    class Fake(FakeSandbox):
        @staticmethod
        def available():
            return True, ""

    monkeypatch.setattr(rx, "DockerSandbox", Fake)
    return tmp_path


def write_records(path, records):
    path.write_text("".join(r.model_dump_json() + "\n" for r in records))


def test_main_writes_a_valid_csv_and_run_metadata(cli, capsys):
    records = cli / "records.jsonl"
    write_records(records, records_for(SPECS))
    out = cli / "out"
    assert rx.main(["--records", str(records), "--out", str(out), "--allow-decode-mismatch"]) == 0
    rows = read_results(out / "results.csv")
    assert len(rows) == len(applicable("default")) * 4 and {r.decoder_mode for r in rows} == {"default"}
    meta = json.loads((out / "run_meta.json").read_text())
    assert meta["decoder_mode"] == "default" and meta["run_id"] == "run-x" and meta["config_sha256"]
    assert "rows (default decoder condition)" in capsys.readouterr().out


def test_main_exits_3_on_a_decode_mismatch_unless_told_otherwise(cli):
    records = cli / "records.jsonl"
    write_records(records, records_for(SPECS, undelivered={"inj-sql-001"}))
    assert rx.main(["--records", str(records), "--out", str(cli / "a")]) == 3
    assert json.loads((cli / "a" / "decode_mismatches.json").read_text())[0]["payload_id"] == "inj-sql-001"
    assert rx.main(["--records", str(records), "--out", str(cli / "b"), "--allow-decode-mismatch"]) == 0


def test_main_refuses_a_bad_input_and_never_overwrites_a_run(cli, capsys):
    records = cli / "records.jsonl"
    write_records(records, records_for(SPECS)[:-1])
    assert rx.main(["--records", str(records), "--out", str(cli / "x")]) == 2
    assert "no record for" in capsys.readouterr().err
    write_records(records, records_for(SPECS))
    assert rx.main(["--records", str(records), "--out", str(cli / "y"), "--allow-decode-mismatch"]) == 0
    with pytest.raises(FileExistsError):
        rx.main(["--records", str(records), "--out", str(cli / "y")])
