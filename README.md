# Visual Trust Boundary Testbed

A lab testbed on a Raspberry Pi 5 that traces one crafted machine-readable code (QR or barcode) through three autonomy tiers (rule-based access node, analytics backend, edge VLM agent), with the decode-time defense off and on, and measures on the device what crosses, what is blocked, and what it costs.

**Vulnerable by design. Lab use only.** Read [ethics/LAB_ONLY.md](ethics/LAB_ONLY.md) before running anything.

## Status

Early: phases P0 to P3 of [plan.md](plan.md) are done on the laptop (Tier 1 only); the Pi runs are still to do. What exists today:

- [contracts.py](contracts.py): the data contracts every module shares.
- [docs/oracles.md](docs/oracles.md): the definition of "crossed", per family and tier (draft, awaiting gate G1).
- [decode/](decode/): the decode stage. zbar sits behind an interface; replay and live capture turn images into records.
- [attacks/](attacks/): deterministic QR and Code 128 rendering, and the seeded benign identifier generator.
- [defense/](defense/): the decode-time boundary check (defense v0) and its grammars.
- [tiers/](tiers/): the Tier 1 access node in its four modes and its seeded badge database. The vulnerable modes run only inside the sandbox.
- [harness/](harness/): the sandbox runner ([docs/containment.md](docs/containment.md)), the verdict function, the Tier 1 oracle, the experiment runner, the schema-checked CSV writer, and the run comparison and summary tools.
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

The full suite, including the decoder tests, runs in a Debian Bookworm image that has the same `libzbar0` package as the Pi (built and run on the laptop; no zbar is installed on the host):

    docker build -t vtb-dev .
    docker run --rm -v "$PWD":/work vtb-dev

Rebuild the image when a requirements file changes. In the image the zbar tests fail rather than skip. Decoder behaviour, including how zbar rewrites non-ASCII QR payloads, is documented in [docs/decode.md](docs/decode.md).

`requirements-live.txt` adds OpenCV for webcam capture only; replay experiments do not need it.

Smoke test on a machine with zbar:

    python -m decode.capture replay <folder of .png files>

Hardware bring-up on the Pi (Track H) is described in plan.md.

## Running the pipeline

On the laptop the decode stage needs `libzbar` (the dev image) and the tier stage needs Docker (the host), so they are joined by a records file. On the Pi both run on one machine.

    python -m attacks.generate                                    # images and manifest (--check to verify)
    python -m harness.sandbox build                               # the sandbox image; a stale image is refused
    docker run --rm -v "$PWD":/work vtb-dev python -m decode.capture \
        --run-id r1 --decoder-mode default replay attacks/out --out harness/results/raw/decode/records.jsonl
    python -m harness.run_experiments --records harness/results/raw/decode/records.jsonl --jobs 3
    python -m harness.summarize harness/results/raw/r1/results.csv
    python -m harness.compare a/results.csv b/results.csv         # a re-run must reproduce every non-timing column

One run covers one decoder condition; run it once per condition (`default` and `raw`). Results are written under `harness/results/raw/` and are not committed.
