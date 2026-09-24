# Working rules for this repo

Read `plan.md` (the approved contract; do not edit it), `status.md` (append-only project log) and `docs/oracles.md` first. A `[HUMAN_GATE]` in plan.md stops work until the user approves in chat.

## Evidence for the paper

This testbed feeds a paper. Every implementation result that could appear in it is recorded in `docs/evidence/LOG.md`, backed by a raw capture:

- Capture with `python tools/capture_evidence.py E-0NN -- <command>`. It stamps the code commit, dirty state, environment, exact command, exit code and a SHA-256. Quote numbers from the captured file, never from memory or from earlier chat output.
- Append only. A correction is a new entry that supersedes the old one; a raw file is never edited or overwritten (`--verify` checks the hash).
- Record failures and surprises too, not only successes.
- Each entry has a class. Only `result-of-record` (Pi, after gate G3 and the defense freeze at G5) may back a quantitative result in the paper. Laptop and container runs are `dev-observation` and support Methods and Threats to validity only.
- Run captures on a clean working tree when the claim is about code behaviour; the header lists any uncommitted files.
- Use a committed probe script for anything longer than one line, not an inline `python -c`.

## Conventions

- Python 3.11 (the Pi's). Read YAML only with `contracts.read_yaml`: PyYAML reads an unquoted `off` as a boolean.
- Tests that need `libzbar` run in the Docker dev image or on the Pi with `VTB_REQUIRE_ZBAR=1`; elsewhere they skip.
- Conventional Commits, no AI co-author trailer, stage by logical group.
- The vulnerable modes are lab-only; read `ethics/LAB_ONLY.md`.
