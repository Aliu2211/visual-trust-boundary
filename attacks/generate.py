"""Render the payload set to code images, with a manifest holding a SHA-256 per image and the library versions
(plan.md P3.1). Deterministic: the same payloads and library versions give byte-identical PNGs.

    python -m attacks.generate                 # write attacks/out/*.png and attacks/manifest.json
    python -m attacks.generate --check         # regenerate in a temp folder and compare with the committed manifest

The images are not committed; the manifest is. `--check` is how another machine, the Pi included, confirms it
rebuilt the same images. Each image is identified by its pixel content, which does not depend on the platform, and
by its PNG file hash, which does (the compressor differs between platforms, E-019), so file hashes are compared only
when the environment matches.
"""

import argparse
import hashlib
import json
import platform
import sys
import tempfile
from importlib import metadata
from pathlib import Path

from PIL import Image

from attacks.payload_set import load_payload_set
from attacks.render import render_code128, render_qr
from contracts import PayloadSpec

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "attacks" / "out"
DEFAULT_MANIFEST = ROOT / "attacks" / "manifest.json"
DEFAULT_SEED = 1337


def pixel_sha256(path: Path) -> str:
    """Hash of what the image shows (size, mode and pixel bytes), not of how the PNG happens to be compressed."""
    with Image.open(path) as img:
        return hashlib.sha256(f"{img.width}x{img.height}:{img.mode}:".encode() + img.tobytes()).hexdigest()


def library_versions() -> dict[str, str]:
    return {
        "platform": f"{platform.system()} {platform.machine()}",
        "python": platform.python_version(),
        **{name: metadata.version(name) for name in ("pillow", "qrcode", "python-barcode")},
    }


def render_spec(spec: PayloadSpec, path: Path) -> str:
    """Render one payload and return the error-correction level used ('-' for Code 128).

    A QR payload uses level M, or L when it does not fit, so the largest payloads still render."""
    if spec.symbology.value == "code128":
        render_code128(spec.content_bytes.decode("ascii"), path)
        ecc = "-"
    else:
        try:
            render_qr(spec.content_bytes, path, ecc="M")
            ecc = "M"
        except ValueError:
            try:
                render_qr(spec.content_bytes, path, ecc="L")
                ecc = "L"
            except ValueError as exc:
                raise ValueError(f"{spec.id}: {len(spec.content_bytes)} bytes do not fit in any QR code") from exc
    if spec.damage == "truncate":
        # A QR code needs its whole area, so keep the upper half. A linear barcode can be read along any single row,
        # so cutting its height leaves it decodable (E-019); cut its width instead, keeping the left half.
        with Image.open(path) as img:
            box = (0, 0, img.width // 2, img.height) if spec.symbology.value == "code128" else (0, 0, img.width, img.height // 2)
            cropped = img.crop(box)
        cropped.save(path)
    return ecc


def generate(specs: list[PayloadSpec], out_dir: Path, seed: int) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for spec in specs:
        path = out_dir / f"{spec.id}.png"
        ecc = render_spec(spec, path)
        entries.append({
            "id": spec.id,
            "family": spec.family.value,
            "subset": spec.subset.value,
            "symbology": spec.symbology.value,
            "ecc": ecc,
            "content_bytes": len(spec.content_bytes),
            "decoder_modes": list(spec.decoder_modes),
            "expected_decode": spec.expected_decode,
            "damage": spec.damage,
            "pixel_sha256": pixel_sha256(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    return {"seed": seed, "generated_with": library_versions(), "payloads": entries}


def same_environment(committed: dict, fresh: dict) -> bool:
    return committed["generated_with"] == fresh["generated_with"]


def compare(committed: dict, fresh: dict) -> list[str]:
    """Real differences between two manifests. Pixel content is always compared; the PNG file hash only when both
    were generated in the same environment, because the compressed bytes differ between platforms (E-019)."""
    problems: list[str] = []
    old = {p["id"]: p for p in committed["payloads"]}
    new = {p["id"]: p for p in fresh["payloads"]}
    for pid in sorted(old.keys() - new.keys()):
        problems.append(f"{pid}: in the committed manifest, not generated")
    for pid in sorted(new.keys() - old.keys()):
        problems.append(f"{pid}: generated, not in the committed manifest")
    skip = set() if same_environment(committed, fresh) else {"sha256"}
    for pid in sorted(old.keys() & new.keys()):
        for key in old[pid]:
            if key not in skip and old[pid][key] != new[pid].get(key):
                problems.append(f"{pid}: {key} differs ({old[pid][key]!r} committed, {new[pid].get(key)!r} here)")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m attacks.generate", description=__doc__.split("\n")[0])
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--check", action="store_true", help="compare against the committed manifest instead of writing")
    args = parser.parse_args(argv)

    specs = load_payload_set(args.seed)
    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            fresh = generate(specs, Path(tmp), args.seed)
        committed = json.loads(Path(args.manifest).read_text())
        problems = compare(committed, fresh)
        for problem in problems:
            print(problem)
        if not same_environment(committed, fresh):
            print(f"environment differs (committed {committed['generated_with']}, here {fresh['generated_with']}): "
                  "PNG file hashes were not compared; pixel content was")
        print(f"{len(specs)} payloads: {'MATCH' if not problems else 'MISMATCH'}")
        return 1 if problems else 0

    manifest = generate(specs, Path(args.out), args.seed)
    Path(args.manifest).write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print(f"wrote {len(specs)} images to {args.out} and {args.manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
