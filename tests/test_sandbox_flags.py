"""The sandbox's docker flags, pinned to docs/containment.md section 3. Pure: needs no Docker."""

from pathlib import Path

import pytest

from harness.sandbox import IMAGE, OUTPUT_CAP, SANDBOX_UID, DockerSandbox

CANARY = Path("/tmp/example-canary")


def flags(**kw) -> list[str]:
    return DockerSandbox(**kw).docker_args("vtb-sbx-test", CANARY)


def value_after(args: list[str], flag: str) -> str:
    return args[args.index(flag) + 1]


def test_the_flags_match_the_approved_design():
    a = flags()
    assert value_after(a, "--network") == "none"
    assert "--read-only" in a
    assert value_after(a, "--user") == f"{SANDBOX_UID}:{SANDBOX_UID}" and SANDBOX_UID != 0
    assert value_after(a, "--cap-drop") == "ALL"
    assert value_after(a, "--security-opt") == "no-new-privileges"
    assert value_after(a, "--pids-limit") == "64"
    assert value_after(a, "--memory") == "256m" and value_after(a, "--cpus") == "1"
    assert "--rm" in a


def test_swap_is_disabled_so_the_memory_limit_is_hard():
    a = flags(memory="128m")
    assert value_after(a, "--memory") == value_after(a, "--memory-swap") == "128m"


def test_scratch_space_is_tmpfs_and_noexec():
    a = flags()
    tmpfs = [a[i + 1] for i, x in enumerate(a) if x == "--tmpfs"]
    assert {t.split(":")[0] for t in tmpfs} == {"/tmp", "/audit"}
    assert all("noexec" in t and "nosuid" in t and "size=" in t for t in tmpfs)


def test_the_audit_tmpfs_is_owned_by_the_sandbox_user():
    # tmpfs takes the mount point's permissions and /audit is root-only in the image (E-013).
    audit = next(a for a in flags() if a.startswith("/audit:"))
    assert f"uid={SANDBOX_UID}" in audit and f"gid={SANDBOX_UID}" in audit


def test_the_canary_is_the_only_bind_mount_and_nothing_else_is_passed_in():
    a = flags()
    mounts = [a[i + 1] for i, x in enumerate(a) if x in ("-v", "--volume", "--mount")]
    assert mounts == [f"{CANARY}:/canary"]
    for forbidden in ("-e", "--env", "--env-file", "--privileged", "--pid", "--ipc", "--network=host", "docker.sock"):
        assert forbidden not in a and not any(forbidden in x for x in a if x.startswith("/")), forbidden


def test_the_image_comes_last_so_the_command_cannot_smuggle_in_flags():
    assert flags()[-1] == IMAGE


def test_stdin_is_only_attached_when_asked_for():
    plain = DockerSandbox().docker_args("n", CANARY)
    with_stdin = DockerSandbox().docker_args("n", CANARY, interactive=True)
    assert "-i" not in plain and "-i" in with_stdin


def test_the_output_cap_is_bounded():
    assert 0 < OUTPUT_CAP <= 4 * 1024 * 1024


@pytest.mark.parametrize("attr", ["memory", "pids", "cpus", "timeout"])
def test_limits_are_configurable_but_have_defaults(attr):
    assert getattr(DockerSandbox(), attr)
