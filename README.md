# Visual Trust Boundary Testbed

A lab testbed on a Raspberry Pi 5 that traces one crafted machine-readable code (QR or barcode) through three autonomy tiers (rule-based access node, analytics backend, edge VLM agent), with the decode-time defense off and on, and measures on the device what crosses, what is blocked, and what it costs.

**Vulnerable by design. Lab use only.** Read [ethics/LAB_ONLY.md](ethics/LAB_ONLY.md) before running anything.

## Status

Early: phase P1 of [plan.md](plan.md) is in progress. What exists today:

- [contracts.py](contracts.py): the data contracts every module shares.
- [docs/oracles.md](docs/oracles.md): the definition of "crossed", per family and tier (draft, awaiting gate G1).
- [decode/](decode/): the decode stage. zbar sits behind an interface; replay and live capture turn images into records.
- [attacks/render.py](attacks/render.py): deterministic QR and Code 128 rendering.
- [config.yaml](config.yaml): run settings, validated against the contracts.
- [docs/evidence/LOG.md](docs/evidence/LOG.md): the paper evidence ledger. Every implementation result is backed by a provenance-stamped raw capture made with [tools/capture_evidence.py](tools/capture_evidence.py).

Progress, decisions and open blockers are logged in [status.md](status.md). The original proposal is kept at [docs/source-plan.md](docs/source-plan.md).

## Development setup

The Pi runs Python 3.11 on Debian Bookworm, so develop on 3.11.

    uv venv --python 3.11 .venv
    source .venv/bin/activate
    uv pip install -r requirements-dev.txt
    pytest

Decoding needs the system library `libzbar` in addition to the Python packages (`apt install libzbar0` on Debian and the Pi). Without it the tests that need the real decoder are skipped, and the skip reason is shown. Set `VTB_REQUIRE_ZBAR=1` where zbar must be present (the Pi) so those tests fail instead of skipping.

`requirements-live.txt` adds OpenCV for webcam capture only; replay experiments do not need it.

Smoke test on a machine with zbar:

    python -m decode.capture replay <folder of .png files>

Hardware bring-up on the Pi (Track H) is described in plan.md.
