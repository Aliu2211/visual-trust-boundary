"""The sandbox image is labelled with a hash of the source baked into it, so a stale image is recognised. Pure."""

from pathlib import Path

import pytest

from harness.sandbox import REPO, source_files, source_hash


def make_tree(root: Path) -> None:
    for name in ("Dockerfile.sandbox", "requirements-sandbox.txt", "contracts.py"):
        (root / name).write_text(name)
    (root / "tools/probes").mkdir(parents=True)
    (root / "tools/probes/sqlite_injection_limits.py").write_text("probe")
    for d in ("defense", "tiers"):
        (root / d).mkdir()
        (root / d / "__init__.py").write_text("")
        (root / d / "a.py").write_text(d)


def test_the_hash_is_deterministic_and_changes_with_any_baked_in_file(tmp_path):
    make_tree(tmp_path)
    base = source_hash(tmp_path)
    assert source_hash(tmp_path) == base
    for target in ("contracts.py", "tiers/a.py", "defense/a.py", "Dockerfile.sandbox", "requirements-sandbox.txt"):
        path = tmp_path / target
        original = path.read_text()
        path.write_text(original + " changed")
        assert source_hash(tmp_path) != base, target
        path.write_text(original)
    assert source_hash(tmp_path) == base


def test_a_new_file_in_a_baked_in_package_changes_the_hash(tmp_path):
    make_tree(tmp_path)
    base = source_hash(tmp_path)
    (tmp_path / "tiers/new_tier.py").write_text("x = 1")
    assert source_hash(tmp_path) != base


def test_files_outside_the_image_do_not_change_the_hash(tmp_path):
    make_tree(tmp_path)
    base = source_hash(tmp_path)
    (tmp_path / "README.md").write_text("docs")
    (tmp_path / "harness").mkdir()
    (tmp_path / "harness/oracles.py").write_text("host side")
    assert source_hash(tmp_path) == base


def test_the_real_repo_hashes_everything_the_dockerfile_copies():
    copied = {p.relative_to(REPO).as_posix() for p in source_files()}
    dockerfile = (REPO / "Dockerfile.sandbox").read_text()
    for line in dockerfile.splitlines():
        if line.startswith("COPY "):
            source = line.split()[1]
            if source.endswith(".py") or source.endswith(".txt"):
                assert source in copied, f"Dockerfile copies {source} but the source hash ignores it"
            elif source in ("defense", "tiers"):
                assert any(c.startswith(source + "/") for c in copied), source


@pytest.mark.parametrize("missing", ["contracts.py", "Dockerfile.sandbox"])
def test_a_missing_baked_in_file_is_an_error_not_a_silent_omission(tmp_path, missing):
    make_tree(tmp_path)
    (tmp_path / missing).unlink()
    with pytest.raises(FileNotFoundError):
        source_hash(tmp_path)
