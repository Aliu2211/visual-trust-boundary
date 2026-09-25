"""Decoder interface and its zbar implementation (plan.md P1; decision D4).

The rest of the testbed sees only `Decoder`, so a second decoder can replace pyzbar
if it stops working on the Pi's Python. Images enter as 8-bit grayscale so the
decoder never has to guess a colour layout.
"""

from ctypes import c_void_p, cast
from dataclasses import dataclass
from typing import Protocol

from contracts import DecoderMode


@dataclass(frozen=True)
class GrayImage:
    width: int
    height: int
    pixels: bytes  # 8-bit grayscale, row-major

    def __post_init__(self) -> None:
        if self.width < 1 or self.height < 1 or len(self.pixels) != self.width * self.height:
            raise ValueError(
                f"pixels must hold width*height bytes, got {len(self.pixels)} for {self.width}x{self.height}"
            )


@dataclass(frozen=True)
class RawSymbol:
    """One symbol as the decoder reports it. `data` is whatever the decoder emitted, which is not
    necessarily the symbol's on-the-wire bytes (see docs/decode.md)."""

    data: bytes
    symbology: str  # the decoder's own name, e.g. "QRCODE"


class Decoder(Protocol):
    name: str
    mode: DecoderMode  # recorded on every record this decoder produces

    def decode(self, image: GrayImage) -> list[RawSymbol]: ...


# zbar.h `zbar_config_e`: ZBAR_CFG_BINARY, "don't convert binary data to text" (upstream 0.23.92, docs/evidence
# E-009). pyzbar 0.1.9's own ZBarConfig enum is older and calls this value CFG_NUM.
ZBAR_CFG_BINARY = 4
_CFG_ENABLE = 0


class PyzbarDecoder:
    """zbar through pyzbar, restricted to the symbologies the experiment uses (QR and Code 128).

    Enabling only those keeps the decoder's attack surface constant: other symbologies in an
    image are ignored, not decoded.

    `raw=False` is zbar's default: for QR byte-mode data it guesses a text encoding (SJIS, Latin-1,
    UTF-8 or Big5) and returns UTF-8, so non-ASCII payloads are rewritten before the caller sees them.
    `raw=True` sets ZBAR_CFG_BINARY and returns the symbol's bytes untouched. Measurements are in
    docs/decode.md. Raw mode drives pyzbar's private scanner helpers, because its public decode()
    cannot set scanner options; pyzbar is pinned at 0.1.9 for that reason.
    """

    name = "pyzbar"

    def __init__(self, raw: bool = False) -> None:
        # Imported here so code that only needs the interface loads without libzbar installed.
        try:
            from pyzbar import pyzbar
        except ImportError as exc:
            raise ImportError(
                "pyzbar could not load libzbar. Install libzbar0 (apt on the Pi) or use the Docker dev image."
            ) from exc
        self._pyzbar = pyzbar
        self._symbols = [pyzbar.ZBarSymbol.QRCODE, pyzbar.ZBarSymbol.CODE128]
        self.raw = raw

    @property
    def mode(self) -> DecoderMode:
        return "raw" if self.raw else "default"

    def decode(self, image: GrayImage) -> list[RawSymbol]:
        if self.raw:
            return self._decode_raw(image)
        found = self._pyzbar.decode((image.pixels, image.width, image.height), symbols=self._symbols)
        return [RawSymbol(data=s.data, symbology=s.type) for s in found]

    def _decode_raw(self, image: GrayImage) -> list[RawSymbol]:
        pz = self._pyzbar
        with pz._image_scanner() as scanner:
            for symbol in set(pz.ZBarSymbol) - set(self._symbols):
                pz.zbar_image_scanner_set_config(scanner, symbol, _CFG_ENABLE, 0)
            for symbol in self._symbols:
                pz.zbar_image_scanner_set_config(scanner, symbol, _CFG_ENABLE, 1)
                if pz.zbar_image_scanner_set_config(scanner, symbol, ZBAR_CFG_BINARY, 1) != 0:
                    raise RuntimeError("this libzbar does not accept ZBAR_CFG_BINARY; raw mode is unavailable")
            with pz._image() as img:
                pz.zbar_image_set_format(img, pz._FOURCC["L800"])
                pz.zbar_image_set_size(img, image.width, image.height)
                pz.zbar_image_set_data(img, cast(image.pixels, c_void_p), len(image.pixels), None)
                if pz.zbar_scan_image(scanner, img) < 0:
                    raise RuntimeError("zbar rejected the image")
                found = pz._decode_symbols(pz._symbols_for_image(img))
                return [RawSymbol(data=s.data, symbology=s.type) for s in found]
