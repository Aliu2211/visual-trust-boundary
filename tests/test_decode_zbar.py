"""Round trips and measured decoder behaviour against the real zbar. Needs libzbar (the Docker dev image or the Pi).

The measured expectations were taken on libzbar0 0.23.92-7+deb12u1 (docs/evidence E-007 and E-008;
narrative in docs/decode.md). If one fails on a different zbar build, that is a finding about build
dependence: record it as evidence, do not just update the number.
"""

import io

import barcode
import pytest
from barcode.writer import ImageWriter
from PIL import Image

from attacks.benign import benign_ascii
from attacks.render import render_code128, render_qr
from contracts import DecodeStatus, PayloadRecord
from decode.capture import gray_from_bytes, main, record_from_symbols, replay_records

ECC_L_MAX = 2953  # bytes, byte mode


def qr_symbols(decoder, data: bytes, tmp_path, ecc="M"):
    path = tmp_path / "x.png"
    render_qr(data, path, ecc=ecc)
    return decoder.decode(gray_from_bytes(path.read_bytes()))


def qr_bytes(decoder, data: bytes, tmp_path, ecc="M") -> bytes:
    (only,) = qr_symbols(decoder, data, tmp_path, ecc)
    return only.data


def record_for(symbols) -> PayloadRecord:
    return record_from_symbols(
        symbols, run_id="r", payload_id="p", source_image="p.png", image_sha256="a" * 64, t_capture=0.0, t_decode_ns=1
    )


# --- ASCII: exact in both modes ------------------------------------------------------------


def test_ascii_qr_round_trips_are_exact(any_decoder, tmp_path):
    cases = benign_ascii(100)
    failures = [t for t in cases if qr_bytes(any_decoder, t.encode(), tmp_path) != t.encode()]
    assert not failures, f"{len(failures)}/{len(cases)} ASCII QR round trips differ, first: {failures[:3]}"


def test_code128_round_trips_are_exact(any_decoder, tmp_path):
    cases = benign_ascii(100)
    failures = []
    for i, text in enumerate(cases):
        path = tmp_path / f"c{i}.png"
        render_code128(text, path)
        got = [(s.symbology, s.data) for s in any_decoder.decode(gray_from_bytes(path.read_bytes()))]
        if got != [("CODE128", text.encode("ascii"))]:
            failures.append((text, got))
    assert not failures, f"{len(failures)}/{len(cases)} Code 128 round trips differ, first: {failures[:3]}"


@pytest.mark.parametrize("text", ["a\tb", "a\nb", "a\x00b", "a\x1bb", "a\x7fb"])
def test_code128_control_characters_are_exact(any_decoder, tmp_path, text):
    render_code128(text, tmp_path / "c.png")
    got = [s.data for s in any_decoder.decode(gray_from_bytes((tmp_path / "c.png").read_bytes()))]
    assert got == [text.encode("ascii")]


@pytest.mark.parametrize(
    "payload",
    [b"a\x00b", b"\x00abc", b"abc\x00", b"\x00\x00\x00", b"a\r\nb\tc\x1b[0m", b"  padded  ", b"0012345", b""],
    ids=["nul-middle", "nul-first", "nul-last", "only-nuls", "control-chars", "padded", "leading-zeros", "empty"],
)
def test_nul_control_chars_and_empty_payload_are_exact(any_decoder, tmp_path, payload):
    assert qr_bytes(any_decoder, payload, tmp_path) == payload


def test_an_empty_qr_payload_is_a_delivered_empty_string(any_decoder, tmp_path):
    record = record_for(qr_symbols(any_decoder, b"", tmp_path))
    assert record.decode_status is DecodeStatus.OK and record.text == "" and record.delivered


@pytest.mark.parametrize("size,ecc", [(1000, "M"), (2331, "M"), (ECC_L_MAX, "L")])
def test_max_capacity_ascii_qr_is_exact(any_decoder, tmp_path, size, ecc):
    data = b"a" * size
    assert qr_bytes(any_decoder, data, tmp_path, ecc) == data


# --- non-ASCII: zbar's default mode rewrites it -------------------------------------------------

REWRITTEN_BY_DEFAULT_MODE = {
    "José".encode(): b"Jos\xe7\x9f\x87",
    "李雷".encode(): b"\xe8\xad\x9a\xe6\x9c\xb1\xe5\xb3\xad",
    "Zoë O'Neil-Smith".encode(): b"Zo\xe7\xa6\xb1 O'Neil-Smith",
}


@pytest.mark.parametrize("original", list(REWRITTEN_BY_DEFAULT_MODE), ids=["accent", "cjk", "mixed"])
def test_non_ascii_qr_is_exact_in_raw_mode_and_rewritten_in_default_mode(decoder, raw_decoder, tmp_path, original):
    assert qr_bytes(raw_decoder, original, tmp_path) == original
    rewritten = qr_bytes(decoder, original, tmp_path)
    assert rewritten != original
    assert rewritten == REWRITTEN_BY_DEFAULT_MODE[original]  # measured on libzbar0 0.23.92-7+deb12u1


@pytest.mark.parametrize(
    "payload,default_returns",
    [(b"ab\xff\xfe", b"ab\xc3\xbf\xc3\xbe"), (b"caf\xe9", b"caf\xc3\xa9"), (b"a\x80b", b"a\xc2\x80b")],
    ids=["ff-fe", "latin1-e-acute", "lone-continuation"],
)
def test_invalid_utf8_is_reported_in_raw_mode_but_comes_back_as_valid_utf8_in_default_mode(
    decoder, raw_decoder, tmp_path, payload, default_returns
):
    raw = record_for(qr_symbols(raw_decoder, payload, tmp_path))
    assert raw.decode_status is DecodeStatus.INVALID_UTF8 and raw.raw_bytes == payload

    default = record_for(qr_symbols(decoder, payload, tmp_path))
    assert default.decode_status is DecodeStatus.OK
    assert default.raw_bytes == default_returns  # measured on libzbar0 0.23.92-7+deb12u1


def test_default_mode_output_is_valid_utf8_for_every_byte_value_and_can_exceed_the_capacity(decoder, raw_decoder, tmp_path):
    every_byte = bytes(range(256))
    mixed = bytes((i * 7 + 3) % 256 for i in range(ECC_L_MAX))

    assert qr_bytes(raw_decoder, every_byte, tmp_path) == every_byte
    assert qr_bytes(raw_decoder, mixed, tmp_path, "L") == mixed

    converted = qr_bytes(decoder, every_byte, tmp_path)
    converted.decode("utf-8")  # raises if the default mode ever returns invalid UTF-8
    assert len(converted) == 384  # 256 bytes, of which 128 are >= 0x80 and each became two bytes

    grown = qr_bytes(decoder, mixed, tmp_path, "L")
    grown.decode("utf-8")
    assert len(grown) > ECC_L_MAX  # a length limit applied after decoding sees more than the code carried


# --- images and policy --------------------------------------------------------------------------


def test_replay_folder_end_to_end(any_decoder, tmp_path):
    texts = benign_ascii(20)
    for i, text in enumerate(texts):
        render_qr(text.encode(), tmp_path / f"benign-{i:03d}.png")
    records = list(replay_records(tmp_path, "run-1", any_decoder))
    assert [r.payload_id for r in records] == [f"benign-{i:03d}" for i in range(len(texts))]
    assert [r.text for r in records] == texts
    assert all(r.decode_status is DecodeStatus.OK and r.symbology == "QRCODE" for r in records)


def test_two_symbols_in_one_image_fail_closed(any_decoder, tmp_path):
    render_qr(b"LEFT", tmp_path / "left.png")
    render_qr(b"RIGHT", tmp_path / "right.png")
    left = Image.open(tmp_path / "left.png").convert("L")
    right = Image.open(tmp_path / "right.png").convert("L")
    canvas = Image.new("L", (left.width + right.width + 40, max(left.height, right.height)), 255)
    canvas.paste(left, (0, 0))
    canvas.paste(right, (left.width + 40, 0))
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")

    symbols = any_decoder.decode(gray_from_bytes(buf.getvalue()))
    assert sorted(s.data for s in symbols) == [b"LEFT", b"RIGHT"]  # the decoder sees both; the policy refuses them
    record = record_for(symbols)
    assert record.decode_status is DecodeStatus.MULTIPLE_SYMBOLS and not record.delivered


def test_symbologies_that_are_not_enabled_are_ignored(any_decoder, tmp_path):
    ean = barcode.get("ean13", "590123412345", writer=ImageWriter(format="PNG"))
    with open(tmp_path / "ean.png", "wb") as fh:
        ean.write(fh, options={"write_text": False})
    assert any_decoder.decode(gray_from_bytes((tmp_path / "ean.png").read_bytes())) == []


def test_blank_image_has_no_symbol(any_decoder):
    buf = io.BytesIO()
    Image.new("L", (300, 300), 255).save(buf, format="PNG")
    assert any_decoder.decode(gray_from_bytes(buf.getvalue())) == []


@pytest.mark.parametrize("mode", ["default", "raw"])
def test_cli_replay_prints_one_valid_record_per_image(tmp_path, capsys, decoder, mode):
    render_qr(b"BADGE-0001", tmp_path / "b-1.png")
    render_qr(b"BADGE-0002", tmp_path / "b-2.png")
    assert main(["--run-id", "run-cli", "--decoder-mode", mode, "replay", str(tmp_path)]) == 0
    records = [PayloadRecord.model_validate_json(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert [r.text for r in records] == ["BADGE-0001", "BADGE-0002"]
    assert {r.run_id for r in records} == {"run-cli"}


def test_seeded_benign_set_is_reproducible_and_well_formed():
    assert benign_ascii(50) == benign_ascii(50)
    assert benign_ascii(50, seed=1) != benign_ascii(50, seed=2)
    ids = benign_ascii(100)
    assert len(set(ids)) == 100 and all(0 < len(t) <= 64 for t in ids)
