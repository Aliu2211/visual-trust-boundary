"""Measure what zbar returns for the plan's P1.3 edge cases, in its default mode and with scanner config 4 set.

Run where libzbar is installed (the Bookworm dev image, or the Pi):

    python tools/probes/decode_edge_cases.py

Capture it as evidence with:

    python tools/capture_evidence.py E-0NN -- python tools/probes/decode_edge_cases.py

One line per case and mode: symbol count, symbology, the bytes zbar returned, and whether they equal the
bytes that were rendered. It uses pyzbar's private scanner helpers (pinned at 0.1.9) because the public
decode() cannot set scanner options. Config 4 is `ZBAR_CFG_BINARY` in newer zbar headers but is named
`CFG_NUM` in pyzbar 0.1.9's enum, so this probe reports whether the library accepts it and whether it
changes any result, rather than assuming.
"""

import hashlib
import io
import sys
import tempfile
from ctypes import c_void_p, cast
from pathlib import Path

import barcode
from barcode.writer import ImageWriter
from PIL import Image
from pyzbar import pyzbar as pz

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from attacks.render import render_code128, render_qr  # noqa: E402
from decode.capture import gray_from_bytes  # noqa: E402
from decode.decoder import GrayImage  # noqa: E402

ENABLED = (pz.ZBarSymbol.QRCODE, pz.ZBarSymbol.CODE128)
CFG_ENABLE, CFG_4 = 0, 4


def scan(gray: GrayImage, config4: bool) -> tuple[list[tuple[str, bytes]], list[int]]:
    """The body of pyzbar.decode() with an optional scanner config; returns symbols and the set_config return codes."""
    codes: list[int] = []
    with pz._image_scanner() as scanner:
        for sym in set(pz.ZBarSymbol) - set(ENABLED):
            pz.zbar_image_scanner_set_config(scanner, sym, CFG_ENABLE, 0)
        for sym in ENABLED:
            pz.zbar_image_scanner_set_config(scanner, sym, CFG_ENABLE, 1)
            if config4:
                codes.append(pz.zbar_image_scanner_set_config(scanner, sym, CFG_4, 1))
        with pz._image() as img:
            pz.zbar_image_set_format(img, pz._FOURCC["L800"])
            pz.zbar_image_set_size(img, gray.width, gray.height)
            pz.zbar_image_set_data(img, cast(gray.pixels, c_void_p), len(gray.pixels), None)
            if pz.zbar_scan_image(scanner, img) < 0:
                raise RuntimeError("zbar rejected the image")
            found = [(s.type, s.data) for s in pz._decode_symbols(pz._symbols_for_image(img))]
    return found, codes


def show(data: bytes) -> str:
    """Short payloads in full; long ones as length, head and hash so the raw file stays readable."""
    if len(data) <= 48:
        return repr(data)
    return f"{len(data)} bytes, head {data[:24]!r}, sha256 {hashlib.sha256(data).hexdigest()[:16]}"


def verdict(returned: bytes, expected: bytes) -> str:
    if returned == expected:
        return "EXACT"
    first = next((i for i, (a, b) in enumerate(zip(returned, expected)) if a != b), min(len(returned), len(expected)))
    return f"DIFFERENT (returned {len(returned)} bytes, rendered {len(expected)}, first difference at byte {first})"


def report(mode: str, label: str, gray: GrayImage, expected: bytes | None) -> None:
    found, _ = scan(gray, config4=(mode == "config4"))
    if not found:
        print(f"{mode:8} {label:34} 0 symbols")
        return
    body = " | ".join(f"{t} {show(d)}" for t, d in found)
    tail = ""
    if expected is not None and len(found) == 1:
        tail = " " + verdict(found[0][1], expected)
    print(f"{mode:8} {label:34} {len(found)} symbol(s): {body}{tail}")


def main() -> int:
    tmp = Path(tempfile.mkdtemp())

    qr_cases = [
        ("qr ascii", b"BADGE-0001"),
        ("qr numeric mode, leading zeros", b"0012345"),
        ("qr apostrophe", b"O'BRIEN"),
        ("qr padded spaces", b"  padded  "),
        ("qr utf-8 accent (Jose)", "José".encode()),
        ("qr utf-8 CJK", "李雷".encode()),
        ("qr utf-8 mixed", "Zoë O'Neil-Smith".encode()),
        ("qr control chars CR LF TAB ESC", b"a\r\nb\tc\x1b[0m"),
        ("qr NUL in the middle", b"a\x00b"),
        ("qr NUL first", b"\x00abc"),
        ("qr NUL last", b"abc\x00"),
        ("qr only NULs", b"\x00\x00\x00"),
        ("qr invalid utf-8 (ff fe)", b"ab\xff\xfe"),
        ("qr latin-1 (caf e9)", b"caf\xe9"),
        ("qr lone continuation byte", b"a\x80b"),
        ("qr all 256 byte values", bytes(range(256))),
        ("qr empty", b""),
        ("qr 1000 bytes", b"a" * 1000),
    ]
    code_cases = [
        ("c128 ascii", "BADGE-0001"),
        ("c128 digits", "0012345"),
        ("c128 apostrophe", "O'BRIEN"),
        ("c128 tab", "a\tb"),
        ("c128 newline", "a\nb"),
        ("c128 NUL", "a\x00b"),
        ("c128 ESC", "a\x1bb"),
        ("c128 DEL", "a\x7fb"),
        ("c128 empty", ""),
        ("c128 200 chars", "A" * 200),
    ]
    cases: list[tuple[str, GrayImage | None, bytes | None, str]] = []

    def add(label: str, make, expected: bytes | None) -> None:
        path = tmp / "case.png"
        try:
            make(path)
        except Exception as exc:  # noqa: BLE001 - a case that cannot be rendered is itself a result
            cases.append((label, None, expected, f"cannot be rendered: {type(exc).__name__}: {exc}"))
            return
        cases.append((label, gray_from_bytes(path.read_bytes()), expected, ""))

    for label, data in qr_cases:
        add(label, lambda p, d=data: render_qr(d, p), data)
    add("qr 2331 bytes (max at ECC M)", lambda p: render_qr(b"a" * 2331, p), b"a" * 2331)
    add("qr 2953 bytes (max at ECC L)", lambda p: render_qr(b"a" * 2953, p, ecc="L"), b"a" * 2953)
    add(
        "qr 2953 mixed bytes (ECC L)",
        lambda p: render_qr(bytes((i * 7 + 3) % 256 for i in range(2953)), p, ecc="L"),
        bytes((i * 7 + 3) % 256 for i in range(2953)),
    )
    for label, text in code_cases:
        add(label, lambda p, t=text: render_code128(t, p), text.encode("latin-1"))

    render_qr(b"LEFT", tmp / "l.png")
    render_qr(b"RIGHT", tmp / "r.png")
    left, right = Image.open(tmp / "l.png").convert("L"), Image.open(tmp / "r.png").convert("L")
    canvas = Image.new("L", (left.width + right.width + 40, max(left.height, right.height)), 255)
    canvas.paste(left, (0, 0))
    canvas.paste(right, (left.width + 40, 0))
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    cases.append(("two QR codes side by side", gray_from_bytes(buf.getvalue()), None, ""))

    with open(tmp / "ean.png", "wb") as fh:
        barcode.get("ean13", "590123412345", writer=ImageWriter(format="PNG")).write(fh, options={"write_text": False})
    cases.append(("EAN-13 (symbology not enabled)", gray_from_bytes((tmp / "ean.png").read_bytes()), None, ""))

    blank = io.BytesIO()
    Image.new("L", (300, 300), 255).save(blank, format="PNG")
    cases.append(("blank image", gray_from_bytes(blank.getvalue()), None, ""))

    _, codes = scan(cases[0][1], config4=True)
    print(f"config 4 set_config return codes (0 means accepted), one per enabled symbology: {codes}")
    for mode in ("default", "config4"):
        print(f"--- mode: {mode}")
        for label, gray, expected, note in cases:
            if gray is None:
                print(f"{mode:8} {label:34} {note}")
            else:
                report(mode, label, gray, expected)
    return 0


if __name__ == "__main__":
    sys.exit(main())
