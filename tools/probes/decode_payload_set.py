"""Decode the whole payload set in both decoder conditions and list every deviation from what each payload was
designed to do. Run where libzbar is installed (the dev image, or the Pi):

    python -m attacks.generate               # the images must exist
    python tools/probes/decode_payload_set.py

Capture it as evidence with:  python tools/capture_evidence.py E-0NN -- python tools/probes/decode_payload_set.py

Reports: whether images regenerated here match the committed manifest, the decode status counts per condition,
payloads that decoded unexpectedly, and payloads whose decoded bytes differ from the bytes that were rendered.
"""

import hashlib
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from attacks import generate as gen  # noqa: E402
from attacks.payload_set import load_payload_set  # noqa: E402
from decode.capture import replay_records  # noqa: E402
from decode.decoder import PyzbarDecoder  # noqa: E402

SEED = 1337


def main() -> int:
    specs = {s.id: s for s in load_payload_set(SEED)}
    committed = json.loads(gen.DEFAULT_MANIFEST.read_text())
    with tempfile.TemporaryDirectory() as tmp:
        fresh = gen.generate(list(specs.values()), Path(tmp), SEED)
    problems = gen.compare(committed, fresh)
    print(f"libraries here: {gen.library_versions()}")
    print(f"images regenerated here match the committed manifest: {not problems}" + (f" ({len(problems)} differences)" if problems else ""))
    for problem in problems[:10]:
        print("  ", problem)

    on_disk = {p.stem: hashlib.sha256(p.read_bytes()).hexdigest() for p in gen.DEFAULT_OUT.glob("*.png")}
    print(f"images on disk: {len(on_disk)}; equal to the manifest's hashes: {on_disk == {p['id']: p['sha256'] for p in committed['payloads']}}")

    for mode in ("default", "raw"):
        records = list(replay_records(gen.DEFAULT_OUT, f"probe-{mode}", PyzbarDecoder(raw=mode == "raw")))
        print(f"--- decoder condition: {mode}")
        print(f"records: {len(records)}; statuses: {dict(sorted(Counter(r.decode_status.value for r in records).items()))}")
        applicable = [r for r in records if mode in specs[r.payload_id].decoder_modes]
        unexpected = [(r.payload_id, specs[r.payload_id].expected_decode, r.decode_status.value)
                      for r in applicable if (specs[r.payload_id].expected_decode == "ok") != r.delivered]
        print(f"payloads applicable in this condition: {len(applicable)}")
        print(f"unexpected decode outcomes (id, expected, got): {unexpected or 'none'}")
        changed = sorted(r.payload_id for r in records if r.delivered and r.raw_bytes != specs[r.payload_id].content_bytes)
        print(f"payloads whose decoded bytes differ from the rendered bytes: {changed or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
