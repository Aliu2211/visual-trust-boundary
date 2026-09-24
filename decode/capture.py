"""Turn images into PayloadRecords: replay from a folder, or live from a webcam (plan.md P1; D5).

Replay is what the experiments use, so decode-and-consume is isolated from capture noise.
The decode policy is in `record_from_symbols` and documented in docs/decode.md.

    python -m decode.capture replay attacks/out
    python -m decode.capture live --device 0 --frames 5
"""

import argparse
import base64
import hashlib
import io
import re
import sys
import time
from collections.abc import Iterable, Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

from contracts import ID_PATTERN, DecodeStatus, PayloadRecord
from decode.decoder import Decoder, GrayImage, PyzbarDecoder, RawSymbol


def gray_from_bytes(data: bytes) -> GrayImage:
    with Image.open(io.BytesIO(data)) as img:
        gray = img.convert("L")
    return GrayImage(width=gray.width, height=gray.height, pixels=gray.tobytes())


def record_from_symbols(
    symbols: Sequence[RawSymbol],
    *,
    run_id: str,
    payload_id: str | None,
    source_image: str,
    image_sha256: str,
    t_capture: float,
    t_decode_ns: int,
) -> PayloadRecord:
    """Apply the decode policy.

    No symbol, or more than one, fails closed: nothing is passed on (an ambiguous frame is not
    guessed at). A single symbol is kept as raw bytes and, if it is valid UTF-8, as text. Invalid
    UTF-8 is reported as such, not repaired, so the boundary layer decides what to do with it (D5).
    """
    common = dict(
        run_id=run_id,
        payload_id=payload_id,
        source_image=source_image,
        image_sha256=image_sha256,
        t_capture=t_capture,
        t_decode_ns=t_decode_ns,
    )
    if not symbols:
        return PayloadRecord(decode_status=DecodeStatus.NO_SYMBOL, **common)
    if len(symbols) > 1:
        return PayloadRecord(decode_status=DecodeStatus.MULTIPLE_SYMBOLS, **common)

    symbol = symbols[0]
    raw_b64 = base64.b64encode(symbol.data).decode("ascii")
    try:
        text = symbol.data.decode("utf-8")
    except UnicodeDecodeError:
        return PayloadRecord(
            decode_status=DecodeStatus.INVALID_UTF8, raw_bytes_b64=raw_b64, symbology=symbol.symbology, **common
        )
    return PayloadRecord(
        decode_status=DecodeStatus.OK, raw_bytes_b64=raw_b64, text=text, symbology=symbol.symbology, **common
    )


def _timed_decode(decoder: Decoder, image: GrayImage) -> tuple[list[RawSymbol], int]:
    start = time.perf_counter_ns()
    symbols = decoder.decode(image)
    return symbols, time.perf_counter_ns() - start


def replay_records(image_dir: Path | str, run_id: str, decoder: Decoder) -> Iterator[PayloadRecord]:
    """Decode every .png in `image_dir`, in file-name order. The file stem is the payload id.

    Misnamed files and empty or missing folders raise before any decoding, because a replay that
    silently covers fewer payloads than intended would corrupt the results.
    """
    root = Path(image_dir)
    if not root.is_dir():
        raise NotADirectoryError(f"replay folder not found: {root}")
    paths = sorted(root.glob("*.png"))
    if not paths:
        raise ValueError(f"no .png files in {root}")
    bad = [p.name for p in paths if not re.fullmatch(ID_PATTERN, p.stem)]
    if bad:
        raise ValueError(f"file names are not valid payload ids: {bad}")
    return _replay(paths, run_id, decoder)


def _replay(paths: list[Path], run_id: str, decoder: Decoder) -> Iterator[PayloadRecord]:
    for path in paths:
        data = path.read_bytes()
        t_capture = time.time()
        symbols, decode_ns = _timed_decode(decoder, gray_from_bytes(data))
        yield record_from_symbols(
            symbols,
            run_id=run_id,
            payload_id=path.stem,
            source_image=path.name,
            image_sha256=hashlib.sha256(data).hexdigest(),
            t_capture=t_capture,
            t_decode_ns=decode_ns,
        )


def live_records(
    frames: Iterable[GrayImage], run_id: str, decoder: Decoder, source_label: str = "live"
) -> Iterator[PayloadRecord]:
    for n, frame in enumerate(frames):
        t_capture = time.time()
        symbols, decode_ns = _timed_decode(decoder, frame)
        yield record_from_symbols(
            symbols,
            run_id=run_id,
            payload_id=None,
            source_image=f"{source_label}#{n}",
            image_sha256=hashlib.sha256(frame.pixels).hexdigest(),
            t_capture=t_capture,
            t_decode_ns=decode_ns,
        )


def opencv_frames(device: int = 0, count: int | None = None) -> Iterator[GrayImage]:
    """Grayscale frames from a camera through OpenCV.

    Not verified yet: it needs a webcam, so it is first exercised in Pi bring-up (plan.md H1).
    """
    import cv2  # live mode only; see requirements-live.txt

    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        raise RuntimeError(f"cannot open camera {device}")
    try:
        taken = 0
        while count is None or taken < count:
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError("camera returned no frame")
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            yield GrayImage(width=gray.shape[1], height=gray.shape[0], pixels=gray.tobytes())
            taken += 1
    finally:
        cap.release()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m decode.capture", description=__doc__.split("\n")[0])
    parser.add_argument("--run-id", default=datetime.now(UTC).strftime("run-%Y%m%dT%H%M%SZ"))
    parser.add_argument(
        "--decoder-mode",
        choices=["default", "raw"],
        default="default",
        help="raw disables zbar's text-encoding guessing (see docs/decode.md)",
    )
    sub = parser.add_subparsers(dest="mode", required=True)
    replay = sub.add_parser("replay", help="decode every .png in a folder")
    replay.add_argument("image_dir")
    live = sub.add_parser("live", help="decode frames from a webcam")
    live.add_argument("--device", type=int, default=0)
    live.add_argument("--frames", type=int, default=5)
    args = parser.parse_args(argv)

    decoder = PyzbarDecoder(raw=args.decoder_mode == "raw")
    if args.mode == "replay":
        records = replay_records(args.image_dir, args.run_id, decoder)
    else:
        records = live_records(opencv_frames(args.device, args.frames), args.run_id, decoder)
    for record in records:
        print(record.model_dump_json())
    return 0


if __name__ == "__main__":
    sys.exit(main())
