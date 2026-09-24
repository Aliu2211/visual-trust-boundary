# Visual Trust Boundary Testbed

A lab testbed on a Raspberry Pi 5 that traces one crafted machine-readable code (QR or barcode) through three autonomy tiers (rule-based access node, analytics backend, edge VLM agent), with the decode-time defense off and on, and measures on the device what crosses, what is blocked, and what it costs.

**Vulnerable by design. Lab use only.** Read [ethics/LAB_ONLY.md](ethics/LAB_ONLY.md) before running anything.

## Status

Early: phase P0 of [plan.md](plan.md). What exists today:

- [contracts.py](contracts.py): the data contracts every module will share.
- [docs/oracles.md](docs/oracles.md): the definition of "crossed", per family and tier.
- [config.yaml](config.yaml): run settings, validated against the contracts.

Progress and decisions are logged in [status.md](status.md). The original proposal is kept at [docs/source-plan.md](docs/source-plan.md).

## Development setup (laptop)

The Pi runs Python 3.11, so develop on 3.11 too.

    uv venv --python 3.11 .venv
    source .venv/bin/activate
    uv pip install -r requirements-dev.txt
    pytest

Hardware bring-up (webcam, zbar, Ollama) is Pi-only and tracked in plan.md as Track H.
