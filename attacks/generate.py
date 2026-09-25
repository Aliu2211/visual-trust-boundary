"""Render the payload set to code images, with a manifest holding a SHA-256 per image and the library versions
(plan.md P3.1). Deterministic: the same payloads and library versions give byte-identical PNGs.

    python -m attacks.generate                 # write attacks/out/*.png and attacks/manifest.json
    python -m attacks.generate --check         # regenerate in a temp folder and compare with the committed manifest

The images are not committed; the manifest is. `--check` is how another machine, the Pi included, confirms it
rebuilt the same images, or learns that its library versions differ and the hashes are not comparable.
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


def library_versions() -> dict[str, str]:
    return {
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
    if spec.damage == "truncate":  # keep the upper half, so the symbol is incomplete and cannot decode
        with Image.open(path) as img:
            cropped = img.crop((0, 0, img.width, img.height // 2))
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
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    return {"seed": seed, "generated_with": library_versions(), "payloads": entries}


def compare(committed: dict, fresh: dict) -> list[str]:
    """Differences between two manifests, worded so a version mismatch is not mistaken for a bug."""
    problems: list[str] = []
    if committed["generated_with"] != fresh["generated_with"]:
        problems.append(
            f"library versions differ (committed {committed['generated_with']}, here {fresh['generated_with']}); "
            "image hashes are not comparable across versions"
        )
    old = {p["id"]: p for p in committed["payloads"]}
    new = {p["id"]: p for p in fresh["payloads"]}
    for pid in sorted(old.keys() - new.keys()):
        problems.append(f"{pid}: in the committed manifest, not generated")
    for pid in sorted(new.keys() - old.keys()):
        problems.append(f"{pid}: generated, not in the committed manifest")
    for pid in sorted(old.keys() & new.keys()):
        for key in old[pid]:
            if old[pid][key] != new[pid].get(key):
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
        problems = compare(json.loads(Path(args.manifest).read_text()), fresh)
        for problem in problems:
            print(problem)
        print(f"{len(specs)} payloads: {'MATCH' if not problems else 'MISMATCH'}")
        return 1 if problems else 0

    manifest = generate(specs, Path(args.out), args.seed)
    Path(args.manifest).write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print(f"wrote {len(specs)} images to {args.out} and {args.manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
