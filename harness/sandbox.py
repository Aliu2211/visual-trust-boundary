"""Run a command inside the lab sandbox on the laptop (docs/containment.md section 3).

Every call is a fresh, throwaway container with a fresh /canary directory, so nothing persists between
calls: the reset the oracles rely on (docs/oracles.md principle 2) holds by construction. The harness reads
what a payload left behind from the host side of the /canary mount, never from inside the container.

The Pi uses systemd-run instead (containment.md section 4); it is not written yet.
"""

import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

IMAGE = "vtb-sandbox"
SANDBOX_UID = 10001
OUTPUT_CAP = 1024 * 1024  # bytes kept per stream; a runaway writer stalls on a full pipe and is killed


@dataclass(frozen=True)
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int  # the container's; 137 means it was killed (memory limit, or this runner on timeout or output cap)
    timed_out: bool
    output_truncated: bool
    canary_files: tuple[str, ...]  # what the run left in /canary, listed from the host side


def _read_capped(stream, sink: list[bytes], truncated: threading.Event, cap: int) -> None:
    total = 0
    while True:
        chunk = stream.read(4096)
        if not chunk:
            return
        room = cap - total
        sink.append(chunk[:room])
        total += min(len(chunk), room)
        if len(chunk) > room:
            truncated.set()
            return


class DockerSandbox:
    def __init__(
        self, image: str = IMAGE, *, memory: str = "256m", pids: int = 64, cpus: str = "1", timeout: float = 60.0
    ) -> None:
        self.image, self.memory, self.pids, self.cpus, self.timeout = image, memory, pids, cpus, timeout

    @staticmethod
    def available(image: str = IMAGE) -> tuple[bool, str]:
        """(usable, reason). Checks the docker CLI, a running daemon and the built image."""
        if not shutil.which("docker"):
            return False, "docker is not installed here"
        try:
            info = subprocess.run(["docker", "info"], capture_output=True, timeout=15, check=False)
            if info.returncode != 0:
                return False, "the docker daemon is not running"
            inspect = subprocess.run(["docker", "image", "inspect", image], capture_output=True, timeout=15, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, f"docker did not answer: {exc}"
        if inspect.returncode != 0:
            return False, f"image {image} is not built (docker build -f Dockerfile.sandbox -t {image} .)"
        return True, ""

    def docker_args(self, name: str, canary: Path, *, interactive: bool = False) -> list[str]:
        """The exact `docker run` flags. Pure, so a test can pin them to the approved design without Docker."""
        return [
            "docker", "run", "--rm", "--name", name,
            *(["-i"] if interactive else []),
            "--network", "none",
            "--read-only",
            "--user", f"{SANDBOX_UID}:{SANDBOX_UID}",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", str(self.pids),
            "--memory", self.memory,
            "--memory-swap", self.memory,  # equal to --memory: no swap, so the limit is a hard one
            "--cpus", self.cpus,
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=32m",
            "--tmpfs", "/audit:rw,noexec,nosuid,size=8m",
            "-v", f"{canary}:/canary",
            self.image,
        ]

    def run(self, argv: Sequence[str], *, stdin: str | None = None, timeout: float | None = None) -> SandboxResult:
        limit = self.timeout if timeout is None else timeout
        name = f"vtb-sbx-{uuid.uuid4().hex[:12]}"
        canary = Path(tempfile.mkdtemp(prefix="vtb-canary-"))
        canary.chmod(0o777)  # the container's user is not the host user; the directory is the payload's playground
        cmd = [*self.docker_args(name, canary, interactive=stdin is not None), *argv]

        out: list[bytes] = []
        err: list[bytes] = []
        truncated = threading.Event()
        timed_out = False
        try:
            proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            readers = [
                threading.Thread(target=_read_capped, args=(proc.stdout, out, truncated, OUTPUT_CAP), daemon=True),
                threading.Thread(target=_read_capped, args=(proc.stderr, err, truncated, OUTPUT_CAP), daemon=True),
            ]
            for reader in readers:
                reader.start()
            if stdin is not None:
                try:
                    proc.stdin.write(stdin.encode("utf-8"))
                    proc.stdin.close()
                except BrokenPipeError:  # the command exited without reading its input
                    pass

            deadline = time.monotonic() + limit
            while proc.poll() is None:
                if time.monotonic() > deadline:
                    timed_out = True
                    break
                if truncated.is_set():
                    break
                time.sleep(0.05)
            if proc.poll() is None:  # timed out or over the output cap: killing the client alone would leave the container running
                subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=30, check=False)
                proc.kill()
            proc.wait(timeout=30)
            for reader in readers:
                reader.join(timeout=5)
            files = tuple(sorted(p.name for p in canary.iterdir()))
        finally:
            shutil.rmtree(canary, ignore_errors=True)

        return SandboxResult(
            stdout=b"".join(out).decode("utf-8", errors="replace"),
            stderr=b"".join(err).decode("utf-8", errors="replace"),
            exit_code=proc.returncode,
            timed_out=timed_out,
            output_truncated=truncated.is_set(),
            canary_files=files,
        )
