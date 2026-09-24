"""Run a command and store its output with provenance, as raw evidence for the paper.

    python tools/capture_evidence.py E-012 -- python -m pytest -q
    python tools/capture_evidence.py --verify docs/evidence/raw/E-012.txt

Writes docs/evidence/raw/E-012.txt: a header (code commit and whether the working tree was dirty,
platform, Python, the versions of the packages results depend on, the exact command, the exit
code), then the captured output, then a SHA-256 of everything above it. An existing file is never
overwritten; a new capture is a new id. Only the versions listed in PACKAGES are recorded, never
the environment variables. See docs/evidence/LOG.md.

Inside a container without git, pass VTB_GIT_SHA and VTB_GIT_DIRTY (0 or 1) as environment variables.
"""

import argparse
import hashlib
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "docs" / "evidence" / "raw"
ID_RE = re.compile(r"^E-\d{3,}$")
HASH_PREFIX = "# sha256-of-above: "
PACKAGES = ["pydantic", "pyyaml", "pillow", "pyzbar", "qrcode", "python-barcode", "pytest", "opencv-python-headless"]


def _run(args: list[str], cwd: Path = ROOT) -> str | None:
    try:
        done = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def git_state() -> tuple[str, str, list[str]]:
    """(commit, 'yes'|'no'|'unknown', changed files). Falls back to VTB_GIT_* where git is absent."""
    sha = _run(["git", "rev-parse", "HEAD"])
    status = _run(["git", "status", "--porcelain"])
    if sha is None or status is None:
        dirty = {"0": "no", "1": "yes"}.get(os.environ.get("VTB_GIT_DIRTY", ""), "unknown")
        return os.environ.get("VTB_GIT_SHA", "unknown"), dirty, []
    files = [line for line in status.splitlines() if line.strip()]
    return sha.strip(), "yes" if files else "no", files


def package_versions() -> str:
    found = []
    for name in PACKAGES:
        try:
            found.append(f"{name} {metadata.version(name)}")
        except metadata.PackageNotFoundError:
            found.append(f"{name} not installed")
    return ", ".join(found)


def libzbar_version() -> str:
    if not shutil.which("dpkg-query"):
        return "n/a (no dpkg on this platform)"
    out = _run(["dpkg-query", "-W", "-f=${Version}", "libzbar0"])
    return out.strip() if out else "not installed"


def normalise(text: str) -> str:
    """Keep local paths out of a public repo: the repo root becomes <repo>, the home directory ~."""
    text = text.replace(str(ROOT), "<repo>")
    home = str(Path.home())
    return text.replace(home, "~") if home not in ("", "/") else text


def _as_text(data: bytes | str | None) -> str:
    if data is None:
        return ""
    return data if isinstance(data, str) else data.decode("utf-8", errors="replace")


def build_header(evidence_id: str, command: list[str], exit_label: str) -> str:
    sha, dirty, files = git_state()
    lines = [
        f"# evidence: {evidence_id}",
        f"# captured: {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"# code commit: {sha} (working tree dirty: {dirty})",
        *[f"#   changed: {f}" for f in files],
        f"# host label: {os.environ.get('VTB_HOST_LABEL', 'unlabelled')}",
        f"# platform: {platform.platform()} {platform.machine()}",
        f"# python: {platform.python_version()}",
        f"# libzbar0: {libzbar_version()}",
        f"# packages: {package_versions()}",
        "# paths normalised: repo root -> <repo>, home -> ~",
        f"# command: {shlex.join(command)}",
        f"# exit: {exit_label}",
    ]
    return normalise("\n".join(lines)) + "\n"


def capture(evidence_id: str, command: list[str], out_dir: Path, timeout: int) -> tuple[Path, int]:
    if not ID_RE.fullmatch(evidence_id):
        raise ValueError(f"evidence id must look like E-012, got {evidence_id!r}")
    path = out_dir / f"{evidence_id}.txt"
    if path.exists():
        raise FileExistsError(f"{path} exists; evidence is never overwritten, use a new id")

    stdout = stderr = ""
    try:
        done = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=timeout, check=False)
        stdout, stderr, code, label = _as_text(done.stdout), _as_text(done.stderr), done.returncode, str(done.returncode)
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, code, label = _as_text(exc.stdout), _as_text(exc.stderr), 124, f"timeout after {timeout}s"
    except OSError as exc:
        code, label = 127, f"could not start: {exc}"

    body = build_header(evidence_id, command, label)
    body += "--- stdout ---\n" + normalise(stdout)
    body += ("" if stdout.endswith("\n") or not stdout else "\n") + "--- stderr ---\n" + normalise(stderr)
    body += "" if stderr.endswith("\n") or not stderr else "\n"
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()

    out_dir.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8") as fh:  # "x": never overwrite, even if it appeared meanwhile
        fh.write(body + HASH_PREFIX + digest + "\n")
    return path, code


def verify(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    head, sep, last = text.rstrip("\n").rpartition("\n")
    if not sep or not last.startswith(HASH_PREFIX):
        return False
    return hashlib.sha256((head + "\n").encode("utf-8")).hexdigest() == last[len(HASH_PREFIX):]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/capture_evidence.py", description=__doc__.split("\n")[0])
    parser.add_argument("--verify", metavar="FILE", help="check a capture's hash instead of capturing")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("evidence_id", nargs="?")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    if args.verify:
        ok = verify(Path(args.verify))
        print(f"{args.verify}: {'OK' if ok else 'HASH MISMATCH'}")
        return 0 if ok else 1

    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not args.evidence_id or not command:
        parser.error("usage: capture_evidence.py E-012 -- <command...>")
    try:
        path, code = capture(args.evidence_id, command, Path(args.out_dir), args.timeout)
    except (ValueError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"captured {path} (command exit {code})")
    return code


if __name__ == "__main__":
    sys.exit(main())
