"""Decode success by symbology and decoder mode for the seeded benign set (plan.md P1.2).

Run where libzbar is installed (the Bookworm dev image, or the Pi):

    python tools/probes/roundtrip_rate.py

Capture it as evidence with:

    python tools/capture_evidence.py E-0NN -- python tools/probes/roundtrip_rate.py

"Exact" means zbar returned exactly one symbol whose bytes equal the bytes that were rendered.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from attacks.benign import NON_ASCII, benign_ascii  # noqa: E402
from attacks.render import render_code128, render_qr  # noqa: E402
from decode.capture import gray_from_bytes  # noqa: E402
from decode.decoder import PyzbarDecoder  # noqa: E402

N_ASCII, SEED = 100, 1337


def exact_count(decoder, texts, render, encode) -> int:
    tmp = Path(tempfile.mkdtemp()) / "x.png"
    exact = 0
    for text in texts:
        render(text, tmp)
        found = decoder.decode(gray_from_bytes(tmp.read_bytes()))
        exact += len(found) == 1 and found[0].data == encode(text)
    return exact


def main() -> int:
    ascii_ids = benign_ascii(N_ASCII, SEED)
    print(f"benign set: {len(ascii_ids)} ASCII ids (seed {SEED}) rendered as QR and as Code 128; {len(NON_ASCII)} non-ASCII texts as QR only")
    print(f"{'decoder mode':13} {'symbology':10} {'payload set':12} exact/total")
    for mode in ("default", "raw"):
        decoder = PyzbarDecoder(raw=(mode == "raw"))
        rows = [
            ("QR", "ascii", ascii_ids, lambda t, p: render_qr(t.encode(), p)),
            ("QR", "non-ascii", list(NON_ASCII), lambda t, p: render_qr(t.encode(), p)),
            ("Code 128", "ascii", ascii_ids, render_code128),
        ]
        for symbology, label, texts, render in rows:
            exact = exact_count(decoder, texts, render, lambda t: t.encode("utf-8"))
            print(f"{mode:13} {symbology:10} {label:12} {exact}/{len(texts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
