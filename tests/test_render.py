import barcode.errors
import pytest
from PIL import Image

from attacks.render import render_code128, render_qr


def test_qr_rendering_is_deterministic(tmp_path):
    render_qr(b"BADGE-0001", tmp_path / "a.png")
    render_qr(b"BADGE-0001", tmp_path / "b.png")
    assert (tmp_path / "a.png").read_bytes() == (tmp_path / "b.png").read_bytes()


def test_code128_rendering_is_deterministic(tmp_path):
    render_code128("BADGE-0001", tmp_path / "a.png")
    render_code128("BADGE-0001", tmp_path / "b.png")
    assert (tmp_path / "a.png").read_bytes() == (tmp_path / "b.png").read_bytes()


def test_different_payloads_render_differently(tmp_path):
    render_qr(b"one", tmp_path / "a.png")
    render_qr(b"two", tmp_path / "b.png")
    assert (tmp_path / "a.png").read_bytes() != (tmp_path / "b.png").read_bytes()


def test_qr_capacity_limit_at_ecc_l_is_2953_bytes(tmp_path):
    render_qr(b"a" * 2953, tmp_path / "max.png", ecc="L")
    with Image.open(tmp_path / "max.png") as img:
        assert img.width == img.height
    with pytest.raises(ValueError, match="do not fit"):
        render_qr(b"a" * 2954, tmp_path / "over.png", ecc="L")


def test_code128_rejects_non_ascii(tmp_path):
    with pytest.raises(barcode.errors.IllegalCharacterError):
        render_code128("José", tmp_path / "x.png")
