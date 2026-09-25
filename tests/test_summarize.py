from contracts import ResultRow
from harness.metrics import ResultWriter
from harness.summarize import summarize


def row(pid, mode, verdict, *, family="injection", signals="", blocked=False, error=None, detail=""):
    return ResultRow(tier="tier1", mode=mode, payload_id=pid, rep=0, run_id="r", family=family,
                     subset="benign" if family == "benign" else "naive", decoder_mode="default", decode_status="ok",
                     verdict=verdict, signals=signals, blocked=blocked, error=error, detail=detail, handle_ns=1)


EXPECTED = """8 rows, 2 payloads, decoder condition(s): ['default']

payload          off                        validate_only  parameterise_only  full
inj-1            crossed[A]                 blocked        no_effect          blocked

verdict counts per mode:
  off                benign_ok 1, crossed 1
  validate_only      blocked 2
  parameterise_only  benign_ok 1, no_effect 1
  full               blocked 2

why validation blocked (validate_only):
  refused: charset: 2

benign rows: 4; benign_ok: 2; refused by the boundary (false positives): 2"""


def test_the_summary_is_exactly_this_for_a_known_file(tmp_path):
    rows = []
    for mode, verdict, blocked, detail in (("off", "crossed", False, ""), ("validate_only", "blocked", True, "refused: charset"),
                                           ("parameterise_only", "no_effect", False, ""), ("full", "blocked", True, "refused: charset")):
        rows.append(row("inj-1", mode, verdict, signals="A" if verdict == "crossed" else "", blocked=blocked, detail=detail))
        rows.append(row("ben-1", mode, "blocked" if blocked else "benign_ok", family="benign", blocked=blocked, detail=detail))
    with ResultWriter(tmp_path / "r.csv") as w:
        for r in rows:
            w.write(r)
    assert summarize(tmp_path / "r.csv") == EXPECTED


def test_a_fault_names_its_error_and_an_encoding_block_is_counted(tmp_path):
    rows = [row("mal-1", "off", "fault", error="OperationalError"),
            row("mal-1", "validate_only", "blocked", blocked=True, detail="refused: encoding"),
            row("mal-1", "parameterise_only", "no_effect"), row("mal-1", "full", "blocked", blocked=True, detail="refused: encoding")]
    with ResultWriter(tmp_path / "r.csv") as w:
        for r in rows:
            w.write(r)
    text = summarize(tmp_path / "r.csv")
    assert "fault OperationalError" in text and "refused: encoding: 1" in text and "benign rows: 0" in text
