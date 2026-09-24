import os

import pytest

from decode.decoder import PyzbarDecoder


def _zbar(raw: bool) -> PyzbarDecoder:
    """The real zbar decoder. Skips where libzbar is absent, unless VTB_REQUIRE_ZBAR is set (Docker image, Pi), where it fails."""
    try:
        return PyzbarDecoder(raw=raw)
    except ImportError as exc:
        if os.environ.get("VTB_REQUIRE_ZBAR"):
            pytest.fail(f"VTB_REQUIRE_ZBAR is set but zbar is unavailable: {exc}")
        pytest.skip("libzbar not available here (apt install libzbar0 on Debian and the Pi)")


@pytest.fixture(scope="session")
def decoder():
    """zbar's default mode, which guesses a text encoding for QR byte-mode data."""
    return _zbar(raw=False)


@pytest.fixture(scope="session")
def raw_decoder():
    """zbar with ZBAR_CFG_BINARY set: the symbol's bytes, untouched."""
    return _zbar(raw=True)


@pytest.fixture(params=["default", "raw"])
def any_decoder(request, decoder, raw_decoder):
    """For behaviour that must hold in both decoder modes."""
    return decoder if request.param == "default" else raw_decoder
