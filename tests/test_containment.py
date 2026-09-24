"""The containment battery (docs/containment.md section 5): inert escape attempts through the same entry point
the vulnerable handler will use. Needs Docker and the built vtb-sandbox image; run on the host, not in the dev image.

Each test states what it proves and includes a control that shows it could have failed.
"""

import json
import re
import socket
import subprocess
import time
import uuid

import pytest

from harness.sandbox import IMAGE, OUTPUT_CAP


def py(sandbox, code, **kw):
    return sandbox.run(["python", "-c", code], **kw)


def result_json(result):
    assert result.exit_code == 0, f"exit {result.exit_code}: {result.stderr[-400:]}"
    return json.loads(result.stdout)


# 1. no network ------------------------------------------------------------------------------------------------


def test_1_there_is_no_network(sandbox):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(1.0)
    port = listener.getsockname()[1]
    try:
        out = result_json(py(sandbox, f"""
import json, socket
out = {{}}
for label, addr in (("external", ("1.1.1.1", 53)), ("host_loopback", ("127.0.0.1", {port})), ("host_alias", ("host.docker.internal", {port}))):
    try:
        socket.create_connection(addr, timeout=3).close()
        out[label] = "CONNECTED"
    except OSError as e:
        out[label] = "refused:" + type(e).__name__ + ":" + str(e.errno)
try:
    socket.getaddrinfo("example.com", 80)
    out["dns"] = "RESOLVED"
except OSError as e:
    out["dns"] = "refused:" + type(e).__name__
print(json.dumps(out))
"""))
        try:
            listener.accept()[0].close()
            arrived = True
        except OSError:  # timeout: nothing connected
            arrived = False
    finally:
        listener.close()

    print("observed:", json.dumps(out), "| a connection reached the host listener:", arrived)
    assert all(v.startswith("refused") for v in out.values()), out
    assert not arrived, "a connection from inside the sandbox reached a listener on the host"


# 2 and 3. writes: refused outside, allowed inside -------------------------------------------------------------


def test_2_writes_outside_the_allowed_directories_are_refused(sandbox):
    out = result_json(py(sandbox, """
import json, os
out = {}
for path in ("/etc/vtb_probe", "/usr/vtb_probe", "/app/vtb_probe", "/vtb_probe", "/var/vtb_probe", "/run/vtb_probe",
             "/proc/vtb_probe", "/sys/vtb_probe", "/dev/vtb_probe", os.path.expanduser("~/vtb_probe")):
    try:
        open(path, "w").close()
        out[path] = "WROTE"
    except OSError as e:
        out[path] = "refused:" + str(e.errno)
print(json.dumps(out))
"""))
    print("observed:", json.dumps(out))
    assert len(out) == 10 and all(v.startswith("refused") for v in out.values()), out


def test_3_the_allowed_places_can_be_written_and_the_harness_sees_the_canary(sandbox):
    # The positive control for tests 2 and 7: an oracle that can never fire would make every defense look perfect.
    r = py(sandbox, 'for p in ("/canary/probe-1", "/tmp/t", "/audit/a"):\n    open(p, "w").write("x")\nprint("ok")')
    assert r.exit_code == 0 and r.stdout.strip() == "ok", r.stderr
    assert r.canary_files == ("probe-1",)


def test_3b_scratch_space_is_noexec(sandbox):
    out = result_json(py(sandbox, """
import json, os, subprocess
open("/tmp/x.sh", "w").write("#!/bin/sh\\necho ran\\n")
os.chmod("/tmp/x.sh", 0o755)
try:
    subprocess.run(["/tmp/x.sh"], check=True, capture_output=True)
    print(json.dumps("EXECUTED"))
except OSError as e:
    print(json.dumps("refused:" + str(e.errno)))
"""))
    assert out.startswith("refused"), out


# 4. the host is invisible -------------------------------------------------------------------------------------


def test_4_a_host_file_outside_every_mount_is_not_visible(sandbox, tmp_path):
    marker = tmp_path / f"host-only-{uuid.uuid4().hex}.txt"
    marker.write_text("host secret")
    out = result_json(py(sandbox, f"""
import json, os
target, found = {marker.name!r}, []
for root, dirs, files in os.walk("/"):
    dirs[:] = [d for d in dirs if d not in ("proc", "sys", "dev")]
    if target in files:
        found.append(os.path.join(root, target))
print(json.dumps({{"path_exists": os.path.exists({str(marker)!r}), "found": found}}))
"""))
    assert marker.exists()  # control: it is really there on the host
    print("observed:", json.dumps(out))
    assert out == {"path_exists": False, "found": []}


def test_4b_the_host_environment_is_not_passed_in(sandbox, monkeypatch):
    monkeypatch.setenv("VTB_TEST_SECRET", "s3cret")
    inside = set(result_json(py(sandbox, "import json, os\nprint(json.dumps(sorted(os.environ)))")))
    declared = json.loads(subprocess.run(["docker", "image", "inspect", IMAGE, "--format", "{{json .Config.Env}}"],
                                         capture_output=True, text=True, check=True).stdout)
    allowed = {entry.split("=", 1)[0] for entry in declared} | {"HOME", "HOSTNAME"}  # the image's own, plus what docker adds
    assert "VTB_TEST_SECRET" not in inside
    assert inside <= allowed, f"variables that are not the image's own: {sorted(inside - allowed)}"


# 5. privileges ------------------------------------------------------------------------------------------------


def test_5_not_root_no_capabilities_and_no_new_privileges(sandbox):
    out = result_json(py(sandbox, """
import json
st = dict(line.split(":\\t", 1) for line in open("/proc/self/status").read().splitlines() if ":\\t" in line)
print(json.dumps({k: st[k].strip() for k in ("Uid", "CapPrm", "CapEff", "CapBnd", "NoNewPrivs")}))
"""))
    print("observed:", json.dumps(out))
    assert out["Uid"].split()[0] == "10001"
    assert {out["CapPrm"], out["CapEff"], out["CapBnd"]} == {"0000000000000000"}, out
    assert out["NoNewPrivs"] == "1"


# 6. resource limits -------------------------------------------------------------------------------------------


def test_6a_the_process_limit_is_enforced(sandbox):
    out = result_json(py(sandbox, """
import json, subprocess
kids, failed_at = [], None
for i in range(300):
    try:
        kids.append(subprocess.Popen(["sleep", "20"]))
    except OSError:
        failed_at = i
        break
print(json.dumps({"started": len(kids), "failed_at": failed_at}))
""", timeout=30))
    print("observed:", json.dumps(out), "(pids limit 64)")
    assert out["failed_at"] is not None and out["started"] < 100, out


def test_6b_the_memory_limit_is_enforced(sandbox):
    r = py(sandbox, "b = bytearray(400 * 1024 * 1024)\nfor i in range(0, len(b), 4096):\n    b[i] = 1\nprint('survived')", timeout=30)
    print("observed: exit code", r.exit_code, "| survived printed:", "survived" in r.stdout, "(memory limit 256m, allocation 400 MiB)")
    assert "survived" not in r.stdout and r.exit_code != 0  # killed by the 256m limit (exit 137 expected)


# 7. no persistence --------------------------------------------------------------------------------------------


def test_7_nothing_persists_between_calls(sandbox):
    first = py(sandbox, 'for p in ("/canary/persist-me", "/tmp/persist-me", "/audit/persist-me"):\n    open(p, "w").write("x")\nprint("wrote")')
    assert first.exit_code == 0, first.stderr  # control: the first call really did write everywhere
    assert first.canary_files == ("persist-me",)
    out = result_json(py(sandbox, 'import json, os\nprint(json.dumps({d: sorted(os.listdir(d)) for d in ("/canary", "/tmp", "/audit")}))'))
    print("observed:", json.dumps(out))
    assert out == {"/canary": [], "/tmp": [], "/audit": []}, out


# 8. SQLite ----------------------------------------------------------------------------------------------------


def test_8_the_sqlite_behaviour_in_e012_holds_inside_the_sandbox(sandbox):
    r = sandbox.run(["python", "/app/tools/probes/sqlite_injection_limits.py"])
    assert r.exit_code == 0, r.stderr
    print(r.stdout)
    assert re.search(r"stacked statement.*rejected: ProgrammingError", r.stdout)
    assert re.search(r"table still exists after the stacked attempt\s+True", r.stdout)
    assert re.search(r"load_extension through SQL\s+rejected: OperationalError: not authorized", r.stdout)
    assert re.search(r"file created by the ATTACH attempt\s+False", r.stdout)


# the runner itself --------------------------------------------------------------------------------------------


def test_9a_a_timeout_removes_the_container_and_not_just_the_client(sandbox):
    r = sandbox.run(["sleep", "60"], timeout=3)
    assert r.timed_out
    time.sleep(1)
    running = subprocess.run(["docker", "ps", "--filter", "name=vtb-sbx-", "--format", "{{.Names}}"],
                             capture_output=True, text=True, check=True).stdout.split()
    assert running == [], f"containers still running after a timeout: {running}"


def test_9b_runaway_output_is_capped_and_stops_the_container(sandbox):
    r = sandbox.run(["python", "-c", "import sys\nwhile True:\n    sys.stdout.write('x' * 65536)"], timeout=30)
    assert r.output_truncated and len(r.stdout) <= OUTPUT_CAP
    assert not r.timed_out, "should stop at the cap, not wait for the timeout"


def test_9c_stdin_and_exit_codes_pass_through(sandbox):
    r = sandbox.run(["python", "-c", "import sys\nprint(sys.stdin.read().upper())\nsys.exit(3)"], stdin="abc")
    assert r.stdout.strip() == "ABC" and r.exit_code == 3 and not r.timed_out
