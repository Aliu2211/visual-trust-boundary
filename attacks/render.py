"""Render payloads into code images (plan.md P1 and P3).

Deterministic: the same input and library versions give the same PNG bytes, so the manifest
hashes in P3 can detect a library change. Payloads are passed as bytes so the renderer never
guesses an encoding.
"""

from pathlib import Path
from typing import Literal

import barcode
import qrcode
from barcode.writer import ImageWriter
from qrcode.constants import ERROR_CORRECT_H, ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q

Ecc = Literal["L", "M", "Q", "H"]
_ECC = {"L": ERROR_CORRECT_L, "M": ERROR_CORRECT_M, "Q": ERROR_CORRECT_Q, "H": ERROR_CORRECT_H}


def render_qr(data: bytes, path: Path | str, *, ecc: Ecc = "M", box_size: int = 10, border: int = 4) -> None:
    """Write a QR code. Raises ValueError if `data` does not fit (the limit is 2953 bytes at ecc L)."""
    qr = qrcode.QRCode(error_correction=_ECC[ecc], box_size=box_size, border=border)
    qr.add_data(data)
    try:
        qr.make(fit=True)
    except ValueError as exc:  # qrcode reports overflow as "Invalid version (was 41, ...)"
        raise ValueError(f"{len(data)} bytes do not fit in a QR code at error correction {ecc}") from exc
    qr.make_image(fill_color="black", back_color="white").save(path)


def render_code128(text: str, path: Path | str) -> None:
    """Write a Code 128 barcode. Code 128 carries ASCII only (anything else raises from python-barcode) and cannot be empty."""
    if not text:
        raise ValueError("Code 128 cannot encode an empty string")
    code = barcode.get("code128", text, writer=ImageWriter(format="PNG"))
    with open(path, "wb") as fh:
        code.write(fh, options={"write_text": False, "dpi": 300, "module_width": 0.3, "quiet_zone": 6.5})
