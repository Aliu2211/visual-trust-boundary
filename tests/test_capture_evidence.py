import sys

import pytest

from tools import capture_evidence as ce


def run(tmp_path, eid, *cmd, **kw):
    return ce.capture(eid, list(cmd), tmp_path, kw.get("timeout", 60))


def test_capture_records_provenance_output_and_a_valid_hash(tmp_path):
    path, code = run(tmp_path, "E-001", sys.executable, "-c", "print('hello'); import sys; print('warn', file=sys.stderr)")
    text = path.read_text()

    assert code == 0 and path.name == "E-001.txt"
    for field in ("# evidence: E-001", "# captured: ", "# code commit: ", "# python: ", "# libzbar0: ",
                  "# packages: ", "# command: ", "# exit: 0", "--- stdout ---\nhello\n", "--- stderr ---\nwarn\n"):
        assert field in text, field
    assert ce.verify(path)


def test_a_failing_command_is_still_captured_with_its_exit_code(tmp_path):
    path, code = run(tmp_path, "E-002", sys.executable, "-c", "import sys; print('boom'); sys.exit(3)")
    assert code == 3 and "# exit: 3" in path.read_text() and "boom" in path.read_text()
    assert ce.verify(path)


def test_a_missing_program_is_recorded_not_raised(tmp_path):
    path, code = run(tmp_path, "E-003", "definitely-not-a-program-xyz")
    assert code == 127 and "# exit: could not start" in path.read_text()


def test_a_timeout_is_recorded_with_partial_output(tmp_path):
    path, code = run(tmp_path, "E-004", sys.executable, "-c",
                     "import time,sys; print('partial', flush=True); time.sleep(30)", timeout=1)
    assert code == 124 and "# exit: timeout after 1s" in path.read_text() and "partial" in path.read_text()


def test_evidence_is_never_overwritten(tmp_path):
    path, _ = run(tmp_path, "E-005", sys.executable, "-c", "print('first')")
    with pytest.raises(FileExistsError):
        run(tmp_path, "E-005", sys.executable, "-c", "print('second')")
    assert "first" in path.read_text() and "second" not in path.read_text()


def test_the_command_is_not_run_when_the_file_already_exists(tmp_path):
    (tmp_path / "E-006.txt").write_text("old")
    marker = tmp_path / "ran"
    with pytest.raises(FileExistsError):
        run(tmp_path, "E-006", sys.executable, "-c", f"open({str(marker)!r}, 'w')")
    assert not marker.exists()


@pytest.mark.parametrize("bad", ["E-1", "e-001", "E-001.txt", "001", "../E-001"])
def test_bad_ids_are_rejected(tmp_path, bad):
    with pytest.raises(ValueError, match="evidence id"):
        run(tmp_path, bad, sys.executable, "-c", "pass")


def test_verify_detects_edits_to_body_and_header(tmp_path):
    path, _ = run(tmp_path, "E-007", sys.executable, "-c", "print('42 passed')")
    original = path.read_text()
    path.write_text(original.replace("42 passed", "43 passed"))
    assert not ce.verify(path)
    path.write_text(original.replace("# exit: 0", "# exit: 1"))
    assert not ce.verify(path)
    path.write_text(original)
    assert ce.verify(path)


def test_other_evidence_captures_do_not_make_the_tree_dirty():
    porcelain = "?? docs/evidence/raw/E-008.txt\n M contracts.py\n?? docs/evidence/LOG.md\n?? docs/evidence/raw/E-009.txt\n"
    assert ce.code_changes(porcelain) == [" M contracts.py", "?? docs/evidence/LOG.md"]
    assert ce.code_changes("?? docs/evidence/raw/E-008.txt\n") == []
    assert ce.code_changes("") == []


def test_carriage_returns_in_output_survive_and_still_verify(tmp_path):
    # HTTP headers from curl end in \r\n; a text-mode read once turned these into a false HASH MISMATCH.
    path, _ = run(tmp_path, "E-011", sys.executable, "-c",
                  "import sys; sys.stdout.write('HTTP/1.1 404 Not Found\\r\\ndate: x\\r\\nlone\\rcr\\n')")
    assert b"404 Not Found\r\ndate: x\r\nlone\rcr\n" in path.read_bytes()
    assert ce.verify(path)
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))  # a real edit must still be caught
    assert not ce.verify(path)


def test_output_that_is_not_utf8_is_captured_and_verifies(tmp_path):
    path, _ = run(tmp_path, "E-012", sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'ok \\xff\\xfe end\\n')")
    assert "ok" in path.read_text(encoding="utf-8", errors="replace") and ce.verify(path)


def test_verify_rejects_a_file_without_a_hash_line(tmp_path):
    f = tmp_path / "E-008.txt"
    f.write_text("# evidence: E-008\n--- stdout ---\nhi\n")
    assert not ce.verify(f)


def test_local_paths_are_normalised_out_of_the_capture(tmp_path):
    path, _ = run(tmp_path, "E-009", sys.executable, "-c", f"print({str(ce.ROOT)!r}); print({str(ce.Path.home())!r})")
    text = path.read_text()
    assert str(ce.ROOT) not in text and "<repo>" in text
    assert str(ce.Path.home()) not in text


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("/Users/someone/Work/x/tests/t.py:50: AssertionError", "~/Work/x/tests/t.py:50: AssertionError"),
        ("File '/home/pi/vtb/decode.py', line 3", "File '~/vtb/decode.py', line 3"),
        ("a /Users/a/b and /home/c/d", "a ~/b and ~/d"),
        ("/usr/lib/python3.11/site-packages/x.py", "/usr/lib/python3.11/site-packages/x.py"),
    ],
)
def test_foreign_home_paths_are_scrubbed_too(raw, expected):
    # A container once printed a host path (from bytecode compiled on the host) into a public capture.
    assert ce.normalise(raw) == expected


def test_main_returns_the_command_exit_code_and_verify_reports(tmp_path, capsys):
    rc = ce.main(["--out-dir", str(tmp_path), "E-010", "--", sys.executable, "-c", "import sys; sys.exit(5)"])
    assert rc == 5
    assert ce.main(["--verify", str(tmp_path / "E-010.txt")]) == 0
    assert "OK" in capsys.readouterr().out
    assert ce.main(["--out-dir", str(tmp_path), "E-010", "--", sys.executable, "-c", "pass"]) == 2  # refuses to overwrite
