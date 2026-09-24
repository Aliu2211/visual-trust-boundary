# Status Log

Append-only. One entry per step or event, newest at the bottom. Never edit or delete earlier entries; corrections go in a new entry.

---

## 2026-09-24: Plan drafted

**Actor:** Claude (planning pass, inline; the agent council was not invoked)
**Step:** pre-P0. Reviewed `Visual-Trust-Boundary-Implementation-Plan.md` and wrote `plan.md`.

**State found:** repo has no commits. The only file is the untracked source plan.

**Checks run (external claims verified rather than assumed):**
- Ollama library page `qwen2-vl`: HTTP 404. The source plan's `ollama pull qwen2-vl:2b` will fail. See D3.
- Ollama library page `qwen3-vl`: exists. 2B is listed at 1.9 GB, 4B at 3.3 GB, 8B at 6.1 GB; listed as vision-capable with tool calling. **Not yet verified on the Pi.** H3 confirms.
- PyPI `pyzbar`: latest 0.1.9, released 2022-03-15, classifiers Python 2.7 and 3.5 to 3.10. See D4.

**Laptop environment (dev machine):** x86_64, Python 3.14.6, zbar not installed (`brew list zbar` reports no keg), Docker 29.6.2 present, Ollama not installed. Python 3.11 is needed to match Pi OS Bookworm (D2).

**Not verified, deferred to the named step:**
- How pyzbar handles a 3-channel OpenCV frame versus explicit grayscale: H1.
- Whether `qwen3-vl:2b` runs acceptably and can call tools on the Pi CPU, and whether any small VLM can read a QR visually: H3.
- pyzbar working on Python 3.11 and aarch64: H1 and P1.

**Open items needing your input:**
1. Approve `plan.md`, or redline the decisions in section 1.
2. Is ethics sign-off already in place, and does it cover development-scale work? (G3 placement, section 3 P7.)
3. Do you have the Pi and webcam in hand now? Track H can start immediately if so.

**Nothing committed.** `plan.md` and `status.md` are new and untracked.

---

## 2026-09-24: Plan approved; assumptions recorded

**Actor:** Claude, on the user's instruction ("lets start and fix all the problems").
**Effect:** `plan.md` status changed from DRAFT to APPROVED (one-line header edit; the body is unchanged). This is the only edit made to `plan.md`; everything else is recorded here.

The three open items from the previous entry were not answered, so the plan's defaults apply:
- **Ethics (G3):** stays before P7, as written. If sign-off is needed before development-scale work, G3 moves before P2 and the user should say so.
- **Pi and webcam:** unknown. Track H is a `[HUMAN_TASK]` and waits on the user. P0 to P4 run entirely on the laptop.
- **Ollama install method:** not needed until H3.

---

## 2026-09-24: P0 complete, halted at G1

**Actor:** Claude
**Steps:** 0.1 to 0.4 (bootstrap, contracts, oracles, lab-only statement).
**Commits (local `main`, not pushed, no remote):**
- `dd7a73e` docs: source plan, execution plan, status log
- `4f080d8` chore: repo scaffolding
- `5ddf819` docs(ethics): lab-only statement
- `ae9219e` docs(oracles): verdicts and oracles for the nine (family, tier) pairs
- `38d5e05` feat(contracts): data contracts, config schema, tests

**Verification:** 61 tests pass on CPython 3.11.15 (x86_64 laptop). The oracle-document consistency test was mutation-checked: renaming one oracle heading makes it fail, and restoring it passes. Not verified: anything on the Pi (aarch64 wheels for pydantic-core and pyyaml are expected to exist but are unconfirmed until H1).

**Defect found and fixed during P0:** PyYAML follows YAML 1.1, so an unquoted `off` in `config.yaml` parsed as boolean `False` and the mode enum rejected it. The same trap applies to payload text such as `no` or `on` in `payloads.yaml`. Fixed at the root with a shared loader (`read_yaml`, only `true`/`false` are booleans) rather than quoting one file; three regression tests cover it. All YAML in this repo must be read with `read_yaml`, not `yaml.safe_load`.

**Environment:** dependencies installed in `.venv` (gitignored) on a uv-managed CPython 3.11.15 in `~/.local/share/uv`, not the system Python. Installed: pydantic 2.13.5, pyyaml 6.0.3, and for dev only pytest 9.1.1. PyPI wheel downloads are slow from this machine (about 30 s for two small wheels); a first install attempt was killed too early and had to be rerun.

**Amendments to plan.md** (refinements found while writing the contracts; none changes a decision D1 to D15):
1. **A1, verdict on the row.** `ResultRow` carries `run_id`, `family`, `subset`, `decode_status` and a single `verdict` (six values, defined in `docs/oracles.md`). `crossed` is a property of the verdict, not a separate column, so a row cannot contradict itself. Plan section 2 listed `crossed` as a field.
2. **A2, metadata once per run.** Run metadata (D13) is a `RunMetadata` record written once per run and keyed by `run_id`, not repeated on every CSV row as section 2 implied.
3. **A3, canary design.** D6's "nonce-tagged canary" becomes "canary is the payload id, with state reset before every call", because payload images are generated once and reused across repetitions, so a per-call nonce cannot be embedded.
4. **A4, tighter outcome rules.** A tier can only `gate` in tier 3, and can only `block` in a mode that validates. This encodes the default that the gate applies to Tier 3 only.
5. **A5, no empty stubs.** The package directories `decode/`, `tiers/`, `defense/`, `attacks/`, `harness/` are not scaffolded yet. Git does not track empty directories and placeholder modules would be noise; each phase creates what it fills.
6. **A6, requirements files, not extras.** D2's "optional `analysis` extra" is realised as `requirements-dev.txt` now and a `requirements-analysis.txt` created in P7. The project is not a packaged distribution, so `pyproject.toml` extras do not apply.

**Where the source plan's problems now stand:**

| Problem | Status |
|---|---|
| Wrong Ollama tag (D3) | Corrected in `config.yaml` (candidate `qwen3-vl:2b`, digest null); confirmed on the Pi in H3 |
| pyzbar risk (D4) | Open: needs H1 and P1 |
| Lossy decode (D5) | Fixed in the `PayloadRecord` contract (raw bytes plus strict text) |
| Undefined crossing (D6) | Drafted in `docs/oracles.md`; awaits G1 |
| Tautological defense (D7) | Subsets encoded in the contract; the sets themselves are P3 and P6 |
| Confounded on/off switch (D8) | Four modes encoded and validated per tier |
| Exceptions as control flow (D9) | `Decision` value type in the contract |
| Tier 3 input design and competence (D10, D11) | Drafted in oracles; awaits G1 and G4 |
| Uncontained vulnerable code (D12) | Loopback-only enforced in config; the sandbox itself awaits G2 |
| Pi measurement hygiene (D13) | `RunMetadata` contract done; capture needs P3 and hardware |
| FPR and workflow definitions (D14) | Defined in `docs/oracles.md` section 2 |
| Scope contradiction (D15) | Resolved in `ethics/LAB_ONLY.md`; awaits G3 |

**HUMAN_GATE G1 is open.** Nothing from P1 onward has been started. Needed from the user: approve or redline `docs/oracles.md`, in particular section 8 (eight overridable defaults), the mode matrix in section 3, and the Tier 3 hybrid input design (D10).

---

## 2026-09-24: Correction, remote exists; first push

**Actor:** Claude, on the user's instruction ("lets commit and push, no co authoring").

**Correction to the previous entry:** it said "not pushed, no remote". The "no remote" part was stated without checking and was wrong. `origin` is `git@github.com:Aliu2211/visual-trust-boundary.git`. The GitHub repo was empty (created 2026-09-24 10:35Z), so the first push is a plain fast-forward with no divergence. `gh` is authenticated as `Aliu2211`.

**Commit conventions confirmed:** all six commits use Conventional Commits, carry no co-author or generated-by trailer (checked with a grep over the full history), and are authored by the configured git identity. Nothing needed rewriting.

**Visibility:** the repo is PUBLIC. Everything in it is now readable by anyone: the plans, `docs/oracles.md`, `ethics/LAB_ONLY.md`, and the contracts. There are no payloads, credentials or secrets in the tree. Commit metadata includes the author email from the git identity. If public was not intended, switch the repo to private in GitHub settings.

---

## 2026-09-24: P1 partly done; blocked on a real libzbar

**Actor:** Claude, after the user said "lets continue". G1 is still open. "lets continue" was not treated as G1 approval; P1 was started because it does not depend on any G1 decision (G1 gates tier code and the oracle contents).

**Commits (local `main`, not pushed):** `8229964` refactor(contracts): public `ID_PATTERN`; `37c3925` chore(deps); `feadee7` feat(decode); `d2f5c15` feat(attacks): renderer.

**Step 1.1 (interface, zbar adapter, replay, live): written. Steps 1.2 and 1.3 (real round trips, edge cases): NOT done. P1 acceptance ("100% round trip on laptop and Pi") is NOT met.**

**Verified:**
- 77 tests pass on CPython 3.11.15: the record policy (no symbol and multiple symbols fail closed, invalid UTF-8 reported not repaired, NUL and empty payloads kept), replay ordering and pre-flight errors, renderer determinism, and the QR capacity limit (2953 bytes at ECC L renders, 2954 raises).
- The calls in `PyzbarDecoder` were checked against the pyzbar 0.1.9 source, not executed: tuple `(pixels, width, height)` input with 8 bits per pixel, `symbols=` takes an iterable of `ZBarSymbol`, `Decoded.type` is the enum name string (`"QRCODE"`, `"CODE128"`), and `data` is read with `string_at(pointer, length)`, so pyzbar itself does not truncate at a NUL byte.

**Not verified (each needs libzbar or a webcam):** any real decode, the edge cases (NUL bytes, invalid UTF-8, empty payload, maximum-capacity QR, multi-symbol images), the `python -m decode.capture` CLI, and the OpenCV frame source.

**Defect found and fixed:** `qrcode` reports an oversized payload as `ValueError("Invalid version (was 41, ...)")`, not `DataOverflowError` as I had documented. The renderer now raises a clear `ValueError`.

**Findings:**
1. **Colour frames.** pyzbar reduces a 3-channel array to its first channel (`image[:, :, 0]`). For an OpenCV BGR frame that is the blue channel, not luminance. This answers part of H1 from source; our decoder converts to grayscale explicitly. Confirm on the Pi.
2. **Debian patches to zbar.** Bookworm's zbar 0.23.92-7+deb12u1 carries four patches. Correction to what I said in chat: I described two of them as QR-decoder fixes, but only CVE-2023-40889 is in `qrdec.c` (QR). CVE-2023-40890 is in `databar.c` (DataBar), which our decoder does not enable. So one QR out-of-bounds fix matters directly: this testbed feeds crafted QR codes to that code. Consequence: results depend on the exact zbar build, so record the `libzbar0` package version in run metadata (D13) and do not compare malformed-family results across zbar builds.

**Blocker: no libzbar on the laptop.** Tried and stopped:
- Homebrew `zbar`: the formula pulls in ImageMagick plus about 16 more formulae. Not installed (cost, and this connection is slow).
- Building from the Debian upstream tarball: checksum verified against the `.dsc`, and Debian's CVE patches applied cleanly, but the tarball has no `configure` and this machine lacks autoconf, automake, GNU libtool and gettext. Stopped.
- Docker Desktop (would give the exact Bookworm `libzbar0`): launched with `open -a Docker`, but the engine never came up in over 15 minutes. Only a backend process ran and no UI process, so it likely needs a manual start.
- The network here is slow and flaky (a 5 MB wheel took 3m41s; GitHub API calls timed out on the TLS handshake).

**Side effects on the user's machine:** my `open -a Docker` left Docker Desktop's backend process running; quit it if unwanted. The zbar source, patches and `probe.py` are in the session scratchpad, not in the repo.

**Held back, uncommitted, because unverified:** `Dockerfile`, `.dockerignore`, `tests/conftest.py` and `tests/test_decode_zbar.py` (7 tests that skip without zbar; the round-trip, replay, multi-symbol, ignored-symbology, blank-image and CLI tests). They are in the working tree.

**To unblock, any one of:**
1. Start Docker Desktop by hand, then `docker build -t vtb-dev .` and `docker run --rm -v "$PWD":/work vtb-dev`. I then run the edge-case probe, write `docs/decode.md` and the measured-behaviour tests, and commit the held files.
2. Run the same tests on the Pi (Track H1) with `libzbar0` installed and `VTB_REQUIRE_ZBAR=1`.
3. `brew install zbar` (heavy).

**Next after P1:** P2 needs G1 (oracles) and G2 (containment) approved.

---

## 2026-09-24: Correction; Docker unblocked

**Actor:** Claude, after the user reported that `open -a Docker` failed in their own terminal with error -1712 (Launch Services timed out waiting for the app).

**Correction to the previous entry:** it said my `open -a Docker` "left Docker Desktop's backend process running". That was wrong. The two `com.docker.backend` processes had been running for 8 days 21 hours, so they predate my launch. They were orphans from a Docker Desktop crash on 2026-09-17 (its log records "recovering from engine crash"), and they were what made every fresh launch time out. My launch earlier today never started the UI or the engine.

**What was done:** confirmed there was no VM process (no vfkit) and so nothing running to lose, then stopped the orphaned user-owned backend (PID 45391 with SIGTERM; PID 45387 ignored SIGTERM and was stopped with SIGKILL). The root-owned helper `com.docker.vmnetd` was left alone. After relaunching, the engine answered within 5 seconds: Docker 29.6.2, x86_64.

**Next:** build the `vtb-dev` image (Bookworm base, `libzbar0` from Debian's repo, the Python deps), run the full suite in it, then the edge-case probe. Progress is recorded in the next entry.

---

## 2026-09-24: Evidence discipline for the paper

**Actor:** Claude, on the user's instruction ("so have to be noting the implentation results down with evidence for use in the paper writing").

**Added:** `docs/evidence/LOG.md` (the ledger), `docs/evidence/raw/` (captures E-001 to E-006), `tools/capture_evidence.py` with tests, `tests/test_evidence_log.py`, and a repo `CLAUDE.md` stating the rule for future sessions. A memory note was saved for the same reason.

**Amendment A7 (plan.md unchanged):** every step that yields a result ends with an evidence capture and a ledger entry, and a phase's acceptance includes those entries. Only entries of class `result-of-record` (Pi, after G3 and the defense freeze at G5) may back a quantitative claim in the paper; laptop and container runs are `dev-observation` and support Methods and Threats to validity.

**How it works:** the tool stamps each capture with the code commit and dirty state, platform, Python, package versions, the `libzbar0` package version where there is one, the exact command, the exit code and a SHA-256. It never overwrites a file, and `--verify` checks a file. A test fails if a raw capture has no ledger entry, a capture does not verify, or the hash quoted in the ledger differs from the file's.

**Backfill:** E-001 to E-006 were re-captured from commands run today, not copied from earlier chat output. They already corrected one chat figure: the suite is 93 passed and 7 skipped at capture, not the 77 quoted earlier, because tests were added in between.

**Defect found on first use:** `--verify` read files in text mode, which rewrites CRLF, so it reported a false `HASH MISMATCH` on E-002 (curl's header dump contains `\r\n`). The file was intact. Fixed in `3dc1270`; all six captures verify; no capture was redone.

**Kept out of the ledger on purpose** (project chronology only): the Docker orphan process, the YAML `off` boolean defect, and the qrcode exception type. The user may want the last two added as implementation notes; say so and they get captures.

**Still pending:** the `vtb-dev` image build (at the apt step when last checked). Once it finishes, the zbar tests run in the container and their results become E-007 onward.

---

## 2026-09-24: P1 done on the laptop; a decoder finding that changes the design

**Actor:** Claude. Evidence: E-007 to E-011 (see `docs/evidence/LOG.md`); the narrative and consequences are in `docs/decode.md`.

**P1 acceptance ("100% round trip on laptop and Pi"):** met for the laptop, in a Bookworm container with `libzbar0 0.23.92-7+deb12u1` (E-011: 100/100 QR and 100/100 Code 128 for the seeded ASCII set, in both decoder modes; full suite 168 passed with none skipped, E-010). **Not met for the Pi**: that run is Track H1. Steps 1.1 to 1.3 are done.

**The finding.** In zbar's default mode, QR payloads with bytes at or above 0x80 are rewritten before the caller sees them: 8 of the 30 single-symbol probe cases differ (E-008), the non-ASCII benign texts round-trip 0/3 (E-011), and with `ZBAR_CFG_BINARY` set every case is exact (E-008). Upstream source shows the mechanism, a guess among SJIS, Latin-1, Big-5 and UTF-8 (E-009). Consequences, each detailed in `docs/decode.md`:
- decision D5's premise ("raw bytes preserved") holds only in raw mode; in default mode `invalid_utf8` looks unreachable through QR (three invalid inputs came back as valid UTF-8);
- decision D14's non-ASCII benign cases cannot round-trip in default mode, whatever the defense does;
- decoded length can exceed what the code carried (4426 bytes from a 2953-byte payload), which matters to any length bound in the boundary.

**Amendments to plan.md (plan unchanged):**
- **A8, decoder mode.** `PyzbarDecoder(raw=...)`, `decode.decoder_mode` in the config (default `default`, no behaviour change), the CLI flag `--decoder-mode`, and a required `RunMetadata.decoder_mode` so every run records which mode produced it. Raw mode uses pyzbar's private scanner helpers, so pyzbar stays pinned at 0.1.9.
- **A9, additions found necessary.** `attacks/benign.py` (the seeded benign generator moved out of a test), `tools/probes/` (probe scripts run through the evidence tool), a clear error for an empty Code 128 payload (python-barcode leaked an `IndexError`), and the evidence tool now ignores other captures when deciding whether the tree is dirty.

**Docker:** the Dockerfile and `.dockerignore` are committed and the image builds; they were held back until this run verified them.

**Open decision for the user (G1):** which decoder mode(s) do results of record use? Recommendation in `docs/decode.md`: `default` as the primary condition with an ASCII-only benign set, and `raw` as a second condition for Tiers 1 and 2, which doubles their cheap deterministic correctness runs. `docs/oracles.md` is unchanged until this is decided.

**Not verified, and why:** the Pi (aarch64, its own zbar package); the OpenCV live-frame source (needs a webcam); anything with camera noise, since all images are clean renders.

**Next:** G1 and G2 gate P2. Track H (Pi bring-up, VLM feasibility spike, running the probes and tests on the Pi) needs the hardware.

---

## 2026-09-24: A host path was found before the first push; history rewritten before publication

**Actor:** Claude, after the user said "yes push" and then chose "Rewrite unpushed history, then push".

**Found:** the pre-push scan of tracked files found one host path, on line 24 of `docs/evidence/raw/E-007.txt`: `/Users/<macOS username>/Work/personal/visual-trust-boundary/tests/test_decode_zbar.py:50`. I had told the user the evidence tool strips local paths; that was not true for this case.

**Cause:** the Docker container reused bytecode the host had compiled into the bind-mounted `__pycache__`, so pytest's failure trace carried the host path. The tool's normaliser only rewrote the container's own root (`/work`) and home (`/root`).

**Fixes:** the normaliser now scrubs any `/Users/<name>` or `/home/<name>` prefix (tested); the Dockerfile sets `PYTHONPYCACHEPREFIX`, which I verified moves the cache to `/tmp/pycache` and removes host bytecode from the traceback; E-007 was redacted (one path line replaced, one header note added, hash recomputed, original and new hashes recorded in the ledger).

**Why history was rewritten, not just the tip:** a push publishes every commit, and the original blob sat in a local commit. Nothing had been pushed, so this was cheap and left no public trace. The eight commits after `a6d9470` were rebuilt on a new branch; `a6d9470` and everything before it keep their hashes, so evidence E-001 to E-009 still cite valid commits and the push is a plain fast-forward of `origin/main`. The E-007 redaction was folded into the commit that first adds it; the E-010, E-011 and separate-redaction commits were dropped and E-010 and E-011 were captured again at the rewritten commits. Their figures matched, except that E-010 counts 168 tests, not 160, because the rewritten tip includes tests added after the first capture. The ledger's Corrections section records this.

**Verified:** across every commit in the range to be pushed, `git log -S` finds no commit that adds or removes the macOS username, a `/Users/...` home path, an email address or a session directory, and `git grep` over every reachable commit finds no occurrence of the username. Host suite: 113 passed, 55 skipped (zbar tests skip without libzbar). Container suite: 168 passed, none skipped.

**Local backup:** the branch `backup/pre-rewrite` holds the old history, including the leaking blob. It is local only. It should be deleted after the push so it cannot be published by accident (`git push --all`); it stays recoverable through the reflog for a while.

---

## 2026-09-24: Decoder-condition decision recorded

**Actor:** Claude, on the user's instruction ("alright lets go with that"), taken as the answer to the one open question, the decoder-mode recommendation in `docs/decode.md`. It was **not** taken as approval of the rest of G1: the oracle contents and the other defaults in `docs/oracles.md` section 8 are still unconfirmed.

**Decision:** `default` is the primary decoder condition. `raw` is a second condition for Tiers 1 and 2. Tier 3 runs in `default` only. The Tier 1 and 2 correctness matrix doubles; runs there are deterministic and cheap.

**Amendment A10 (plan.md unchanged):**
- `decoder_modes` moves from a single `decode.decoder_mode` (amendment A8, which nothing consumed yet) to a per-tier setting in `config.yaml`. The config rejects Tier 3 with `raw`, and rejects an enabled tier that lacks `default`, so the decision cannot drift silently.
- `ResultRow` gains a required `decoder_mode`. Without it the same (tier, mode, payload, rep) appears once per condition with nothing to tell the rows apart. A row is now identified by (run, tier, mode, decoder_mode, payload, rep).
- `docs/oracles.md` records the condition in sections 2 and 3, the metrics are per condition, and the benign set is ASCII-only in `default`; non-ASCII benign texts and invalid-UTF-8 malformed payloads run in `raw` only. `docs/decode.md` turns the open question into the recorded decision and lists what follows.

**Verified:** host suite 119 passed, 55 skipped (the zbar tests skip without libzbar); container suite 174 passed, none skipped. No evidence capture was taken: this step is a design decision and its plumbing, not a measured result. The release-commit suite capture is the one the paper will cite.

**Next, needs the user:** the rest of G1 (oracles, the mode matrix, attack subsets, the Tier 3 input design, and the seven remaining defaults in `docs/oracles.md` section 8) and G2 (containment) before P2. Payload specs need a per-payload decoder-condition field, which is added in P3.
