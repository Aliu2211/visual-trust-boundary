"""Decoder interface and its zbar implementation (plan.md P1; decision D4).

The rest of the testbed sees only `Decoder`, so a second decoder can replace pyzbar
if it stops working on the Pi's Python. Images enter as 8-bit grayscale so the
decoder never has to guess a colour layout.
"""

from dataclasses import dataclass
from typing import Protocol


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

    def decode(self, image: GrayImage) -> list[RawSymbol]: ...


class PyzbarDecoder:
    """zbar through pyzbar, restricted to the symbologies the experiment uses (QR and Code 128).

    Enabling only those keeps the decoder's attack surface constant: other symbologies in an
    image are ignored, not decoded.
    """

    name = "pyzbar"

    def __init__(self) -> None:
        # Imported here so code that only needs the interface loads without libzbar installed.
        try:
            from pyzbar import pyzbar
        except ImportError as exc:
            raise ImportError(
                "pyzbar could not load libzbar. Install libzbar0 (apt on the Pi) or use the Docker dev image."
            ) from exc
        self._pyzbar = pyzbar
        self._symbols = [pyzbar.ZBarSymbol.QRCODE, pyzbar.ZBarSymbol.CODE128]

    def decode(self, image: GrayImage) -> list[RawSymbol]:
        found = self._pyzbar.decode((image.pixels, image.width, image.height), symbols=self._symbols)
        return [RawSymbol(data=s.data, symbology=s.type) for s in found]
