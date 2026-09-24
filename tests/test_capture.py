"""Decode policy and replay behaviour, using a fake decoder so no libzbar is needed."""

import base64
import hashlib
import io

import pytest
from PIL import Image

from contracts import DecodeStatus
from decode.capture import gray_from_bytes, live_records, record_from_symbols, replay_records
from decode.decoder import GrayImage, RawSymbol

COMMON = dict(
    run_id="run-1",
    payload_id="p-1",
    source_image="p-1.png",
    image_sha256="a" * 64,
    t_capture=1.0,
    t_decode_ns=10,
)


class FakeDecoder:
    name = "fake"

    def __init__(self, symbols):
        self.symbols = symbols
        self.calls = 0

    def decode(self, image):
        self.calls += 1
        return list(self.symbols)


def write_png(path, size=(10, 10)):
    Image.new("L", size, 255).save(path)


# --- record_from_symbols ---------------------------------------------------------


def test_no_symbol_carries_nothing():
    r = record_from_symbols([], **COMMON)
    assert r.decode_status is DecodeStatus.NO_SYMBOL
    assert (r.raw_bytes_b64, r.text, r.symbology) == (None, None, None)
    assert not r.delivered


def test_more_than_one_symbol_fails_closed():
    two = [RawSymbol(b"a", "QRCODE"), RawSymbol(b"b", "QRCODE")]
    r = record_from_symbols(two, **COMMON)
    assert r.decode_status is DecodeStatus.MULTIPLE_SYMBOLS
    assert r.raw_bytes_b64 is None and not r.delivered


def test_one_valid_utf8_symbol_is_ok_with_raw_and_text():
    r = record_from_symbols([RawSymbol("José".encode(), "QRCODE")], **COMMON)
    assert r.decode_status is DecodeStatus.OK
    assert r.text == "José" and r.raw_bytes == "José".encode() and r.symbology == "QRCODE"


def test_invalid_utf8_is_reported_not_repaired():
    r = record_from_symbols([RawSymbol(b"ab\xff\xfe", "QRCODE")], **COMMON)
    assert r.decode_status is DecodeStatus.INVALID_UTF8
    assert r.text is None and r.raw_bytes == b"ab\xff\xfe" and r.delivered


def test_empty_symbol_is_a_symbol_not_a_miss():
    r = record_from_symbols([RawSymbol(b"", "QRCODE")], **COMMON)
    assert r.decode_status is DecodeStatus.OK and r.text == "" and r.raw_bytes == b""


def test_nul_bytes_survive_into_the_record():
    r = record_from_symbols([RawSymbol(b"a\x00b", "QRCODE")], **COMMON)
    assert r.text == "a\x00b" and base64.b64decode(r.raw_bytes_b64) == b"a\x00b"


# --- GrayImage and image loading ---------------------------------------------------


def test_grayimage_checks_its_buffer_length():
    GrayImage(2, 3, bytes(6))
    with pytest.raises(ValueError, match="width\\*height"):
        GrayImage(2, 3, bytes(5))
    with pytest.raises(ValueError):
        GrayImage(0, 3, b"")


def test_gray_from_bytes_converts_colour_to_8_bit_gray():
    buf = io.BytesIO()
    Image.new("RGB", (7, 5), (255, 0, 0)).save(buf, format="PNG")
    g = gray_from_bytes(buf.getvalue())
    assert (g.width, g.height, len(g.pixels)) == (7, 5, 35)


# --- replay ------------------------------------------------------------------------


def test_replay_is_sorted_and_hashes_the_file(tmp_path):
    for name in ["b.png", "a.png", "c-1.png"]:
        write_png(tmp_path / name)
    (tmp_path / "notes.txt").write_text("ignored")
    dec = FakeDecoder([RawSymbol(b"x", "QRCODE")])

    records = list(replay_records(tmp_path, "run-1", dec))

    assert [r.payload_id for r in records] == ["a", "b", "c-1"]
    assert [r.source_image for r in records] == ["a.png", "b.png", "c-1.png"]
    assert records[0].image_sha256 == hashlib.sha256((tmp_path / "a.png").read_bytes()).hexdigest()
    assert all(r.t_decode_ns >= 0 and r.run_id == "run-1" for r in records)
    assert dec.calls == 3


def test_replay_problems_raise_before_any_decoding(tmp_path):
    dec = FakeDecoder([])
    with pytest.raises(NotADirectoryError):
        replay_records(tmp_path / "missing", "r", dec)
    with pytest.raises(ValueError, match="no .png files"):
        replay_records(tmp_path, "r", dec)
    write_png(tmp_path / "Bad Name.png")
    with pytest.raises(ValueError, match="not valid payload ids"):
        replay_records(tmp_path, "r", dec)
    assert dec.calls == 0


# --- live --------------------------------------------------------------------------


def test_live_records_number_frames_and_have_no_payload_id():
    frames = [GrayImage(2, 2, bytes([1, 2, 3, 4])), GrayImage(2, 2, bytes(4))]
    records = list(live_records(frames, "run-1", FakeDecoder([]), source_label="cam0"))
    assert [r.source_image for r in records] == ["cam0#0", "cam0#1"]
    assert all(r.payload_id is None and r.decode_status is DecodeStatus.NO_SYMBOL for r in records)
    assert records[0].image_sha256 == hashlib.sha256(bytes([1, 2, 3, 4])).hexdigest()
