# Visual Trust Boundary Testbed: Execution Plan

**Status:** APPROVED 2026-09-24 (in chat: "lets start and fix all the problems"). Immutable from here; changes go in `status.md` as a dated amendment, not as edits here.
**Source:** `docs/source-plan.md` (the "source plan", originally `Visual-Trust-Boundary-Implementation-Plan.md`). This plan keeps its architecture (decode stage, three tiers, one boundary layer, harness) and changes the parts listed in section 1.
**Drafted:** 2026-09-24

Markers used below:
- `[HUMAN_GATE Gn]`: execution halts until you approve in chat.
- `[HUMAN_TASK]`: needs hands on the Pi or webcam; an agent cannot do it.
- Size: S (under a day), M (a few days), L (a week or more). These are relative sizes only; no calendar is implied, because the proposal timeline is not in this repo.

---

## 1. Decisions and deltas from the source plan

| # | Source plan says | This plan does | Why |
|---|---|---|---|
| D1 | Repo root is `vtb-testbed/` | This repo is the root; source plan moves to `docs/source-plan.md` | Avoids a nested project dir in a repo meant to be released. |
| D2 | Build everything on the Pi | Develop and test on the laptop with Python 3.11; use the Pi for hardware bring-up, the VLM, and every number that goes in the paper. `pandas` and `matplotlib` become an optional `analysis` extra run on the laptop. `requests` becomes `httpx`. | Laptop iteration is much faster. Keeping analysis libraries off the Pi keeps its memory and CPU measurements clean. Pi OS Bookworm ships Python 3.11; the laptop has 3.14, which pyzbar does not list as supported (D4). `httpx` is already required by FastAPI's test client, so it replaces a second HTTP dependency. |
| D3 | `ollama pull qwen2-vl:2b` | Candidate is `qwen3-vl:2b`; fall back to MiniCPM-V. Pin the pulled model by digest. | `qwen2-vl` returns 404 on the Ollama library (checked 2026-09-24). `qwen3-vl:2b` is listed at 1.9 GB as vision-capable with tool calling, but it is unverified on the Pi, so the H3 spike must confirm it. |
| D4 | pyzbar as the decoder | Keep pyzbar, but hide it behind a `Decoder` interface and smoke-test it on 3.11 in P1. Fallback is `zxing-cpp` or OpenCV. | pyzbar 0.1.9 dates from March 2022 and lists Python 3.5 to 3.10. It is a thin wrapper over zbar, which is what real embedded readers use, so it stays the primary decoder. Do not add a second decoder unless P1 fails. |
| D5 | Decode with `"replace"`; record has no run or payload identity | The record carries raw bytes plus a strict-decode result, and adds `run_id` and `payload_id`. The boundary layer, not the decoder, decides what to do with invalid UTF-8. | Decoding with `replace` turns invalid bytes into U+FFFD before the boundary sees them. That silently removes a whole class of encoding-level attacks from the experiment, and the harness could not attribute outcomes to payloads. |
| D6 | "Crossing" means the payload reached and affected the trusted context | Each family and tier pair gets an operational oracle in `docs/oracles.md`. Oracles are nonce-tagged canary side effects observed by the harness. A tier never reports its own crossing. | Without this the headline metric is not falsifiable and a reviewer cannot reproduce it. |
| D7 | One attack set, per family | Three subsets: **naive** (the source's families), **adaptive** (written after reading the grammar: grammar-conformant payloads, Unicode normalisation, URL/base64/double encoding, NUL truncation), **held-out** (generated independently of the grammar and frozen before it is run). | In vulnerable mode the crossing rate is about 100% by construction. The informative numbers are residual crossing in defended mode, false positives, and cost. A grammar tested only against the author's own injection strings will show about 100% blocking and prove nothing. |
| D8 | Mode is `vulnerable` or `defended` | Four modes: `off`, `validate_only`, `parameterise_only`, `full`. Tier 3 uses `off` and `full`, plus `gate_only` if time allows. | In the source plan, control 2 (parameterisation) lives in tier code while control 1 lives in `boundary.py`, so one switch flips both. That confounds them. The ablation shows which control does the work. |
| D9 | `check()` and `gate()` raise on bad input | They return a `Decision` (allow or reject, with a reason code). Callers branch on it. | Rejecting hostile input is the normal case in this experiment, not an exceptional one. Return values also give per-reason rejection counts for free. |
| D10 | Tier 3 reads the code with the VLM | The decoded payload text is passed to the agent as an observation string alongside the image (a hybrid decoder plus VLM pipeline). Optional stretch: the same instruction text rendered as printed text in the scene. | VLMs generally do not decode QR symbology. That is unverified for the chosen model, and the H3 spike tests it. The hybrid design also preserves "one crafted code traced across three tiers". Confirm at G1. |
| D11 | Tier 3 result is a crossing rate | Report crossing conditional on competence. A benign-scene baseline measures whether the agent makes the correct tool call at all. Use temperature 0 and a fixed seed, N reps per payload, and Wilson intervals. Tools are inert stubs that append to an action log. | A 2B model on CPU may fail to follow any instruction. A low crossing rate would then reflect model weakness, not the defense. |
| D12 | SQLite is "contained"; the shell command is not addressed | The Tier 1 shell path runs an inert command, in a sandbox, with no network, writing only to a canary directory. Tier 2 and Tier 3 services bind to `127.0.0.1` only. On the laptop the sandbox is a Docker container. On the Pi it is an unprivileged user with systemd sandboxing or bubblewrap; do not install Docker on the measurement Pi unless it is shown not to perturb the numbers. | Deliberately vulnerable code executing shell on a machine on your LAN needs an explicit design. G2 approves it. |
| D13 | Metrics use `psutil` | Also record CPU temperature and `vcgencmd get_throttled` before and after every Pi run. Flag or discard throttled runs. Record OS, kernel, zbar (apt) version, Python, `pip freeze`, Ollama version, model digest, and git SHA in run metadata. Use active cooling. | A Pi 5 throttles under sustained VLM inference, and throttled latency is not a finding. Unpinned Ollama tags and apt packages break reproducibility even when `requirements.txt` is pinned. |
| D14 | FPR and "usability pass-through" listed as separate metrics | Two distinct definitions. **Boundary FPR**: the validator rejects a benign payload. **Workflow success**: decode, boundary and tier all succeed end to end. Benign set has at least 1000 items and includes hard cases (apostrophes, hyphens, non-ASCII names, maximum-length IDs). | Zero false positives in 1000 items only bounds FPR at roughly 0.3% (95% upper bound). A small or easy benign set makes FPR look better than it is, and apostrophes are exactly where an allowlist fails. |
| D15 | Section 9 covers disclosure for "a tested commercial device" | This repo tests only its own simulated stack. Commercial-device testing is out of scope, and the disclosure text in `LAB_ONLY.md` is marked conditional. | The source's scope note says no third-party system is touched, which contradicts the disclosure paragraph. Confirm at G3. |

---

## 2. Contracts (built in P0, before any tier code)

Schemas are pydantic models in one `contracts` module. Field lists here are the contract.

- **PayloadSpec** (one row of `attacks/payloads.yaml`): `id`, `family` (malformed, injection, backend_parse, instruction, benign), `subset` (naive, adaptive, heldout, benign), `target_tiers`, `symbology`, `content` (text, or base64 bytes), `oracle_ref`, `seed`, `expected_decode` (ok or fail), `notes`.
- **PayloadRecord** (decoder output, crosses the boundary): `run_id`, `payload_id`, `raw_bytes_b64`, `text` (strict UTF-8 or null), `decode_status` (ok, invalid_utf8, no_symbol, multiple_symbols), `symbology`, `source_image`, `image_sha256`, `t_capture`, `t_decode_ns`.
- **Tier interface:** one method taking a `PayloadRecord` and a `Mode`, returning a `TierOutcome`. Tiers are swapped without touching the harness.
- **TierOutcome:** `tier`, `mode`, `payload_id`, `rep`, `blocked` (defense rejected), `gated`, `error`, `handle_ns`, `defense_ns`, `detail`. **`crossed` is computed by the harness oracle, not the tier.**
- **Decision** (boundary output): `allow` or `reject`, `reason_code`, `control` (validate or gate).
- **ResultRow:** `TierOutcome` plus `crossed` plus run metadata (D13). The CSV schema is checked on write and the file is append-only.
- **Config:** modes, loopback ports, model tag and digest, N reps, seeds. Validated at load.

---

## 3. Phases

### P0. Bootstrap and contracts (laptop, size M)

- 0.1 Move the source plan to `docs/source-plan.md`. Scaffold the layout from the source plan (D1). Add `.gitignore` (venv, raw results, model files, `.env`). Pin Python 3.11. First commit is `docs:` or `chore:`.
- 0.2 Implement the contracts from section 2 with unit tests for validation.
- 0.3 Write `docs/oracles.md`: for each family and applicable tier, the attacker goal, the canary, how the harness observes it, and what counts as crossed, blocked, or error. Include what a failed decode counts as for the malformed family (a truncated symbol never decodes, so it tests decoder robustness, not the boundary).
- 0.4 Draft `ethics/LAB_ONLY.md` from source section 9, adjusted per D15.

**Acceptance:** `pytest` passes on the contracts; `docs/oracles.md` has an entry for every family and tier pair in the source plan's table.

**`[HUMAN_GATE G1]`** Approve the oracles, the mode matrix (D8), the attack subsets (D7), and the Tier 3 input design (D10). No tier code before this, because these choices define what the paper's numbers mean.

### Track H. Hardware bring-up (Pi, `[HUMAN_TASK]`, size M, starts now, not blocked by G1)

- H1 Flash Bookworm 64-bit, install per source section 2 but pin what you install. Confirm `v4l2-ctl --list-devices` and the zbar smoke test, **with both a colour frame and an explicit grayscale conversion** (I have not verified how pyzbar handles 3-channel numpy input; this settles it). Record the Python and zbar versions.
- H2 Fit active cooling. Record idle temperature and throttle flags.
- H3 **VLM feasibility spike**, before building anything for Tier 3. Install Ollama at a pinned version. Pull `qwen3-vl:2b` and record the digest. Measure latency for 10 images, peak RSS, and whether a trivial tool call round-trips correctly. Test three things separately: reads printed text, follows an instruction in an image, and decodes a QR visually. Log everything in `status.md`.
- Note on the Ollama install: the source uses `curl | sh` from ollama.com. On your own Pi that is a common choice, but it runs unpinned remote code as root. A versioned release archive is the more reproducible alternative. Your call; record which in `status.md`.

**Acceptance:** H1 to H3 numbers are in `status.md`. H3 feeds G4.

### P1. Decode stage (laptop then Pi, size M)

- 1.1 `Decoder` interface with a pyzbar implementation. Replay mode reads a folder in sorted order; live mode is a thin webcam wrapper. Records follow D5.
- 1.2 Round-trip test: generate a benign code set (QR and Code 128), decode, and assert byte equality. Record decode success by symbology.
- 1.3 Edge-case tests, with behaviour written down: NUL bytes, invalid UTF-8, maximum-capacity QR, multiple symbols in one image, empty payload. These set expectations for the malformed family.

**Acceptance:** 100% round-trip on the benign set on the laptop and on the Pi (from H1), with zbar version recorded.

### P2. Tier 1 and defense v0 (size M)

**`[HUMAN_GATE G2]`** before writing any vulnerable shell path: approve the containment design (D12).

- 2.1 Badge SQLite database, fixed seed, with a restricted canary row and an audit table. Vulnerable handler: string-built SQL plus an inert shell audit command, sandboxed.
- 2.2 `defense/grammar.py` (identifier, plate, ticket: length bound, charset, grammar) and `defense/boundary.py` returning `Decision` (D9).
- 2.3 Defended handler: parameterised SQL, no shell.
- 2.4 One injection payload run through all four modes as an automated test.

**Acceptance:** `off` crosses per the oracle; `validate_only` blocks; `parameterise_only` accepts but does not cross; `full` blocks. This is the source plan's "first real crossing and first block".

### P3. Attack generator and harness skeleton (size M)

- 3.1 `attacks/payloads.yaml` for the naive subset of the malformed and injection families. `generate.py` is seeded and writes PNGs plus a manifest with SHA-256 per image and library versions.
- 3.2 `harness/metrics.py` (schema-checked append-only CSV) and `harness/run_experiments.py` (tier, mode, payload, rep loop; oracle evaluation; `perf_counter_ns` timing; psutil sampling).
- 3.3 First CSV from Tier 1, on the laptop, then on the Pi.

**Acceptance:** a schema-valid CSV from the Pi; a re-run reproduces every non-timing column exactly.

### P4. Tier 2 (size M)

- 4.1 FastAPI service on loopback with two deliberately vulnerable behaviours: (a) log or field injection into a parsed audit log; (b) second-order injection, where a stored event is later concatenated into a report query. Defended: boundary, parameterised queries, and structured (JSON-encoded, not string-formatted) logging.
- 4.2 Oracles and naive payloads for the backend-parsing family.

**Acceptance:** both behaviours cross in `off` and not in `full`; the harness tolerates HTTP failures without losing rows.

### P5. Tier 3, stretch (size L)

**`[HUMAN_GATE G4]`** go or no-go, using the H3 numbers. Also confirms the model and digest, and the competence threshold (proposed: at least 90% correct tool calls on the benign baseline).

- 5.1 Agent loop with three inert tool stubs. Vulnerable mode puts the decoded text in the same channel as instructions. Defended mode uses provenance-tagged data and a gate on consequential tools; the harness defaults the approval flag to false, so the model cannot pass the gate itself.
- 5.2 Benign-scene baseline set plus instruction-family payloads.
- 5.3 Runs at temperature 0 with a fixed seed, N reps per payload, latency and memory per image.

**Acceptance:** if the benign baseline is below the threshold, Tier 3 is reported as "inconclusive: model competence", not as a defense result. Per the source plan's guiding rule, Tier 3 never blocks the thesis; Tiers 1 and 2 stand alone.

Also note honestly in the write-up: the grammar (control 1) has nothing to say about free-form scene text, so Tier 3's protection comes from provenance separation and the gate, and provenance separation is probabilistic, not a guarantee.

### P6. Defense hardening and freeze (size M)

- 6.1 Write adaptive attacks (D7 subset b) against the current grammar and fix what breaks. One commit per change, with the reason, as the defense's evolution log.
- 6.2 Cost microbenchmark on the Pi: `check()` and `gate()` per-call time at 100,000 iterations (p50 and p99) and RSS delta.
- 6.3 Build the held-out set (D7 subset c) from sources independent of the grammar, such as public payload lists and LLM-generated variants prompted without seeing the grammar. Generate and store, but do not run.
- 6.4 Tag `defense-frozen-v1`.

**`[HUMAN_GATE G5]`** Approve the frozen defense and the attack-set manifest hashes before any held-out run. After G5, any defense edit invalidates held-out results.

### P7. Full runs (Pi, size M)

**`[HUMAN_GATE G3]`** Ethics sign-off confirmed before any run whose output goes in the paper. The source says "before running"; this plan reads that as results-of-record runs, with P2 to P6 as development. If your ethics office wants sign-off before even development-scale work, G3 moves to before P2. Say so at approval.

- 7.1 Full matrix: tiers by modes by subsets. Proposed N: 1 per payload for correctness on deterministic tiers, 30 reps for timing, 10 per payload for Tier 3. Tune after the H3 spike.
- 7.2 Capture run metadata and throttle flags (D13); rerun any flagged runs.
- 7.3 Copy CSVs to the laptop. Produce figures and Wilson intervals with the `analysis` extra.

### P8. Release (size M)

- 8.1 README with exact hardware and reproduction steps.
- 8.2 `LIMITATIONS.md` (threats to validity: author-written vulnerable tiers, single decoder, small VLM, grammar built around author-known formats).
- 8.3 ADRs for decisions worth keeping, changelog, `requirements.lock` from the Pi, apt versions listed.
- 8.4 Fill the manuscripts' Results and Discussion (outside this repo).

---

## 4. Gate summary

| Gate | Before | Approves |
|---|---|---|
| G1 | Any tier code | Oracles, mode matrix, attack subsets, Tier 3 input design |
| G2 | Vulnerable shell path (P2) | Containment design for deliberately vulnerable code |
| G4 | Tier 3 build (P5) | Go or no-go, model and digest, competence threshold |
| G5 | Held-out runs | Frozen defense, attack-set manifest hashes |
| G3 | Results-of-record runs (P7) | Ethics sign-off status and scope (D15) |

---

## 5. Top risks

| Risk | Mitigation |
|---|---|
| Defense looks perfect because we wrote both sides | D7 (adaptive and held-out sets), D8 (ablation), G5 freeze |
| Tier 3 too slow or too weak to say anything | H3 spike early, G4 go or no-go, competence baseline (D11), Tiers 1 and 2 stand alone |
| Pi thermal throttling corrupts latency | Active cooling, throttle flags, rerun flagged runs (D13) |
| pyzbar breaks on Python 3.11 or aarch64 | Smoke test in H1 and P1, `Decoder` interface, fallback decoder (D4) |
| Laptop and Pi behaviour drift | Python 3.11 on both, run metadata (D2, D13), all reported numbers from the Pi |
| Ethics sign-off arrives late | Timing raised at approval (G3) |
