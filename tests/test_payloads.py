"""The payload set, its lab-only lint, and the generator. Pure: no Docker and no libzbar."""

import hashlib
import json
import re
from pathlib import Path

import pytest
from PIL import Image

from attacks import generate as gen
from attacks.payload_set import YAML, benign_specs, load_payload_set
from contracts import Family, Subset, TierId, load_payload_specs
from tiers.badges import ground_truth

SEED = 1337
ATTACKS = load_payload_specs(YAML)


def text_of(spec) -> str:
    return spec.content_bytes.decode("utf-8", errors="replace")


# --- the hand-written attacks ------------------------------------------------------------------------------------


def test_the_attack_list_is_the_naive_subset_for_tier_1_in_the_two_attack_families():
    assert {s.family for s in ATTACKS} == {Family.INJECTION, Family.MALFORMED}
    assert {s.subset for s in ATTACKS} == {Subset.NAIVE}
    assert all(s.target_tiers == (TierId.TIER1,) for s in ATTACKS)


def test_ids_are_unique_and_follow_the_family_prefix():
    ids = [s.id for s in ATTACKS]
    assert len(ids) == len(set(ids))
    for s in ATTACKS:
        assert s.id.startswith("inj-" if s.family is Family.INJECTION else "mal-"), s.id


def test_every_shell_payload_that_writes_a_file_writes_only_its_own_canary():
    # Oracle signal T1-D looks for a file named after the payload id; a payload writing anywhere else would be invisible to it.
    writers = [s for s in ATTACKS if "/canary/" in text_of(s)]
    assert len(writers) >= 6
    for s in writers:
        targets = re.findall(r"/canary/([A-Za-z0-9_.%-]+)", text_of(s))
        assert targets and set(targets) == {s.id}, (s.id, targets)


def test_damaged_and_raw_only_payloads_are_declared_as_such():
    for s in ATTACKS:
        if s.damage != "none":
            assert s.expected_decode == "fail"
        if not s.content_bytes.decode("utf-8", errors="replace").encode("utf-8") == s.content_bytes:  # invalid UTF-8
            assert s.decoder_modes == ("raw",), s.id


# --- the lab-only lint (ethics/LAB_ONLY.md): the sandbox contains a mistake, this stops one being written ----------

_FORBIDDEN = re.compile(
    r"\b(rm|curl|wget|nc|ncat|netcat|bash|sh|zsh|python\d?|perl|ruby|php|node|ssh|scp|ftp|telnet|chmod|chown|dd|mkfs|mount|"
    r"umount|cat|tee|base64|nohup|crontab|sudo|su|eval|exec|fork|reboot|shutdown)\b|https?://|\bforkbomb\b|:\(\)\{",
    re.IGNORECASE,
)


def test_no_payload_names_a_dangerous_program_or_a_url():
    hits = {s.id: _FORBIDDEN.findall(text_of(s)) for s in ATTACKS if _FORBIDDEN.search(text_of(s))}
    assert not hits, f"payloads must be inert (ethics/LAB_ONLY.md): {hits}"


def test_the_only_commands_are_touch_of_its_own_canary_a_bounded_sleep_and_the_harmless_kill():
    for s in ATTACKS:
        t = text_of(s)
        for m in re.finditer(r"\bsleep\s+(\d+)", t):
            assert int(m.group(1)) <= 30, s.id
        for m in re.finditer(r"\bkill\b[^;&|`$)\n]*\S*", t):
            assert re.fullmatch(r"kill -9 \$PPID", m.group(0).strip()), (s.id, m.group(0))
        for m in re.finditer(r"\btouch\s+(\S+)", t):
            assert m.group(1).rstrip(")`") == f"/canary/{s.id}", (s.id, m.group(1))


def test_the_lint_itself_catches_what_it_should():
    for bad in ("x; rm -rf /", "x; curl http://example.com", "x; bash -i", "x; cat /etc/passwd", "x && sudo id", "x; nc host 1"):
        assert _FORBIDDEN.search(bad), bad
    for ok in ("x; touch /canary/inj-shell-001", "x; sleep 30", "x; kill -9 $PPID", "' OR '1'='1"):
        assert not _FORBIDDEN.search(ok), ok


# --- the derived benign set ---------------------------------------------------------------------------------------


def test_the_benign_set_covers_every_badge_unknown_ids_and_both_symbologies():
    truth = ground_truth(SEED)
    specs = benign_specs(SEED)
    texts = {s.id: text_of(s) for s in specs}
    assert len(specs) == 50 + 10 + 40 + 10 and len({s.id for s in specs}) == len(specs)
    assert {t for i, t in texts.items() if i.startswith("ben-a-")} == truth.active_ids
    assert {t for i, t in texts.items() if i.startswith("ben-r-")} == truth.revoked_ids
    unknown = {t for i, t in texts.items() if i.startswith("ben-u-")}
    assert len(unknown) == 40 and not unknown & (truth.active_ids | truth.revoked_ids | {truth.restricted_id})
    assert {s.symbology.value for s in specs} == {"qr", "code128"}
    assert all(s.family is Family.BENIGN and s.subset is Subset.BENIGN and s.decoder_modes == ("default", "raw") for s in specs)


def test_the_benign_set_is_deterministic_and_seed_dependent():
    assert benign_specs(SEED) == benign_specs(SEED)
    assert [text_of(s) for s in benign_specs(1)] != [text_of(s) for s in benign_specs(2)]


def test_the_full_set_has_unique_ids_and_is_sorted():
    specs = load_payload_set(SEED)
    ids = [s.id for s in specs]
    assert ids == sorted(ids) and len(ids) == len(set(ids)) == len(ATTACKS) + 110


def test_an_id_clash_between_the_attack_list_and_the_benign_set_is_an_error(tmp_path):
    clash = tmp_path / "p.yaml"
    clash.write_text('payloads:\n  - {id: ben-a-001, family: injection, subset: naive, target_tiers: [tier1], symbology: qr, '
                     'content_text: "x", oracle_ref: t1.default, seed: 1, expected_decode: ok}\n')
    with pytest.raises(ValueError, match="clash"):
        load_payload_set(SEED, clash)


# --- the generator -----------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    out = tmp_path_factory.mktemp("images")
    return out, gen.generate(load_payload_set(SEED), out, SEED)


def test_one_image_per_payload_and_the_manifest_hashes_are_the_files(generated):
    out, manifest = generated
    specs = load_payload_set(SEED)
    assert sorted(p.stem for p in out.glob("*.png")) == [s.id for s in specs]
    for entry in manifest["payloads"]:
        assert hashlib.sha256((out / f"{entry['id']}.png").read_bytes()).hexdigest() == entry["sha256"]


def test_generation_is_deterministic(generated, tmp_path):
    _, first = generated
    assert gen.generate(load_payload_set(SEED), tmp_path, SEED) == first


def test_the_error_correction_level_is_the_smallest_that_fits(generated):
    by_id = {p["id"]: p for p in generated[1]["payloads"]}
    assert by_id["mal-long-001"]["ecc"] == "L"  # 2953 bytes only fit at L (E-006)
    assert by_id["mal-long-003"]["ecc"] == "M"  # 2331 bytes fit at M
    assert by_id["inj-sql-001"]["ecc"] == "M"
    assert by_id["ben-c128-01"]["ecc"] == "-"


def test_a_truncated_qr_keeps_the_upper_half_and_a_truncated_barcode_the_left_half(generated, tmp_path):
    from attacks.render import render_code128, render_qr
    out, manifest = generated
    render_qr(b"B-000001", tmp_path / "whole-qr.png")
    render_code128("B-000001", tmp_path / "whole-c128.png")
    with Image.open(out / "mal-trunc-001.png") as damaged, Image.open(tmp_path / "whole-qr.png") as whole:
        assert damaged.size == (whole.width, whole.height // 2)
        assert damaged.tobytes() == whole.crop((0, 0, whole.width, whole.height // 2)).tobytes()
    # A linear barcode reads along any row, so cutting its height would leave it decodable (E-019): cut its width.
    with Image.open(out / "mal-trunc-002.png") as damaged, Image.open(tmp_path / "whole-c128.png") as whole:
        assert damaged.size == (whole.width // 2, whole.height)
        assert damaged.tobytes() == whole.crop((0, 0, whole.width // 2, whole.height)).tobytes()
    hashes = {p["id"]: p["pixel_sha256"] for p in manifest["payloads"]}
    assert hashes["mal-trunc-001"] != hashes["mal-trunc-002"]


def test_the_manifest_records_versions_and_the_decoder_conditions(generated):
    manifest = generated[1]
    assert set(manifest["generated_with"]) == {"platform", "python", "pillow", "qrcode", "python-barcode"}
    assert all(len(p["pixel_sha256"]) == 64 and len(p["sha256"]) == 64 for p in manifest["payloads"])
    by_id = {p["id"]: p for p in manifest["payloads"]}
    assert by_id["mal-utf8-001"]["decoder_modes"] == ["raw"] and by_id["inj-sql-001"]["decoder_modes"] == ["default", "raw"]
    assert by_id["mal-trunc-001"]["expected_decode"] == "fail" and by_id["mal-trunc-001"]["damage"] == "truncate"


def test_a_payload_too_big_for_any_qr_code_is_an_error(tmp_path):
    from contracts import PayloadSpec
    huge = PayloadSpec(id="mal-huge-001", family="malformed", subset="naive", target_tiers=["tier1"], symbology="qr",
                       content_text="a" * 3000, oracle_ref="t1.default", seed=1, expected_decode="ok")
    with pytest.raises(ValueError, match="do not fit"):
        gen.render_spec(huge, tmp_path / "x.png")


# --- the committed manifest ---------------------------------------------------------------------------------------


def test_the_committed_manifest_matches_a_fresh_generation(generated):
    # Pixel content is always compared; PNG file hashes only if this environment matches the manifest's (E-019).
    assert gen.compare(json.loads(gen.DEFAULT_MANIFEST.read_text()), generated[1]) == []


def test_pixel_hashes_ignore_how_the_png_is_compressed_and_file_hashes_do_not(tmp_path):
    from attacks.render import render_qr
    render_qr(b"B-000001", tmp_path / "a.png")
    with Image.open(tmp_path / "a.png") as img:
        img.save(tmp_path / "b.png", compress_level=0)  # same pixels, different compressor setting
        changed = img.copy()
        changed.putpixel((5, 5), 0 if changed.getpixel((5, 5)) else 255)  # the QR image is 1-bit: flip a pixel
        changed.save(tmp_path / "c.png")
    a, b, c = (tmp_path / f"{n}.png" for n in "abc")
    assert a.read_bytes() != b.read_bytes() and gen.pixel_sha256(a) == gen.pixel_sha256(b)
    assert gen.pixel_sha256(a) != gen.pixel_sha256(c)


def _manifest(env, **payload):
    return {"generated_with": env, "payloads": [{"id": "a", "sha256": "f1", "pixel_sha256": "p1", "ecc": "M", **payload}]}


def test_compare_ignores_file_hashes_across_environments_but_not_pixel_content():
    linux, mac = {"platform": "Linux x86_64"}, {"platform": "Darwin x86_64"}
    assert gen.compare(_manifest(mac), _manifest(linux, sha256="f2")) == []  # different compressor, same pixels
    problems = gen.compare(_manifest(mac), _manifest(linux, sha256="f2", pixel_sha256="p2"))
    assert len(problems) == 1 and "pixel_sha256 differs" in problems[0]


def test_compare_checks_file_hashes_within_one_environment_and_reports_missing_and_extra_payloads():
    env = {"platform": "Darwin x86_64"}
    assert "sha256 differs" in " ".join(gen.compare(_manifest(env), _manifest(env, sha256="f2")))
    old = {"generated_with": env, "payloads": [{"id": "a"}, {"id": "b"}]}
    new = {"generated_with": env, "payloads": [{"id": "a"}, {"id": "c"}]}
    text = " | ".join(gen.compare(old, new))
    assert "b: in the committed manifest" in text and "c: generated, not in the committed manifest" in text


def test_check_mode_reports_a_match_and_a_mismatch(tmp_path, capsys):
    assert gen.main(["--check"]) in (0, 1)  # 0 when versions match; 1 with a clear message when they do not
    tampered = json.loads(gen.DEFAULT_MANIFEST.read_text())
    # The pixel hash is compared in every environment; the file hash only where the environment matches (E-019),
    # so tampering with that one would go unnoticed in the dev image (E-033).
    tampered["payloads"][0]["pixel_sha256"] = "0" * 64
    bad = tmp_path / "manifest.json"
    bad.write_text(json.dumps(tampered))
    assert gen.main(["--check", "--manifest", str(bad)]) == 1
    assert "MISMATCH" in capsys.readouterr().out
