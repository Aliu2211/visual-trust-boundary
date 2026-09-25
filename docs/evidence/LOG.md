# Evidence log

Implementation results for the paper, each backed by a raw capture in [raw/](raw/). This file is the ledger; [../../status.md](../../status.md) is the project chronology and is not evidence.

## Rules

1. **Capture first, write second.** Run `python tools/capture_evidence.py E-0NN -- <command>`, then write the entry using numbers copied from the captured file. A raw file records the code commit, whether the working tree was dirty (and which files), platform, Python, package versions, the `libzbar0` package version where there is one, the exact command, the exit code, and a SHA-256 of the file.
2. **Append only.** A raw file is never edited or overwritten, with one exception: a privacy redaction (a local path or name that must not be published), which must be recorded under Corrections below with the original and new hashes. A correction is a new entry that says which one it supersedes. Check integrity with `python tools/capture_evidence.py --verify docs/evidence/raw/E-0NN.txt`. A test also checks that this ledger's hashes match the raw files.
3. **Record failures and surprises**, not only successes.
4. **Every entry has a class.** Only `result-of-record` may back a quantitative result in the paper.

| Class | Meaning | Use in the paper |
|---|---|---|
| `design` | An external fact behind a design decision (a registry page, a package's release history) | Methods, Threats to validity |
| `dev-observation` | Laptop, container or source inspection during development | Methods, Threats; not results |
| `pi-observation` | Measured on the Pi before gate G3 or before the defense is frozen | Methods, Threats; not results |
| `result-of-record` | Measured on the Pi after gate G3 and the defense freeze at G5 | Results |

Confidence is `verified` (re-runnable, and the capture is the check) or `source-read` (read from source, not executed) or `assumed` (stated, not yet checked). An entry says which parts are inference.

## Index

| Id | Topic | Class | Backs |
|---|---|---|---|
| E-001 | Test suite status | dev-observation | Methods |
| E-002 | Ollama model tags | design | D3, D11 |
| E-003 | pyzbar maintenance | design | D4 |
| E-004 | Debian zbar source and patches | design | D4, D13 |
| E-005 | pyzbar pixel and data handling | dev-observation | D5 |
| E-006 | QR payload capacity | dev-observation | Malformed family |
| E-007 | First real zbar run: non-ASCII round trip fails | dev-observation | D5, D14 |
| E-008 | zbar edge-case probe, default vs binary mode | dev-observation | D5, D14 |
| E-009 | Upstream zbar source for the text-conversion flag | design | D5 |
| E-010 | Full suite green in the Bookworm image | dev-observation | Methods |
| E-011 | Decode success by symbology and decoder mode | dev-observation | P1.2 acceptance, D14 |
| E-012 | What an injected string can do through Python's sqlite3 | dev-observation | D12, gate G2 |
| E-013 | Containment battery, first run: 3 of 14 failed | dev-observation | D12, gate G2 |
| E-014 | Containment battery on the laptop: 14 of 14 pass | dev-observation | D12, gate G2 |
| E-015 | Tier 1 through all four modes, in the sandbox | dev-observation | D6, D8, P2 acceptance |
| E-016 | The sandbox image E-015 ran in | dev-observation | D12, reproducibility |
| E-017 | Full suite in the Bookworm dev image after Tier 1 | dev-observation | Methods |
| E-018 | Full host suite with the sandbox required | dev-observation | Methods, D12 |
| E-019 | The payload set through the real decoder, before any fix | dev-observation | D5, D7, P3 |
| E-020 | The payload set through the real decoder, after the fix | dev-observation | D5, D7, P3 |
| E-021 | The payload set decoded into records files | dev-observation | P3 |
| E-022 | First Tier 1 run, default condition, before the timeout fix | dev-observation | P3.3 |
| E-023 | First Tier 1 run, raw condition, before the timeout fix | dev-observation | P3.3 |
| E-024 | Re-run of the default condition, before the fix | dev-observation | P3 |
| E-025 | The reproducibility check finds a defect | dev-observation | P3 acceptance |
| E-026 | Tier 1 run, default condition, after the fix | dev-observation | P3.3 |
| E-027 | Re-run of the default condition, after the fix | dev-observation | P3 |
| E-028 | Tier 1 run, raw condition, after the fix | dev-observation | P3.3 |
| E-029 | The reproducibility check passes | dev-observation | P3 acceptance |
| E-030 | Summary of the final default run | dev-observation | D7, D14 |
| E-031 | Summary of the final raw run | dev-observation | D5, D7 |
| E-032 | Full host suite after P3, with the sandbox required | dev-observation | Methods |
| E-033 | Dev-image suite after P3: one failure | dev-observation | Methods |

## Entries

### E-001 Test suite at commit 28f0fbb

- **Date and step:** 2026-09-24, P0 and P1.
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** the contracts, decode policy, renderer and evidence tool have an automated suite. The decoder tests that need real zbar have not run.
- **Result:** `93 passed, 7 skipped in 2.87s`. The 7 skips are all in `tests/test_decode_zbar.py` (reason shown: libzbar not available on the host).
- **Evidence:** [raw/E-001.txt](raw/E-001.txt), sha256 `f3d5a38196b0b1bff027a3b9f7623eec8cd42559c421f39da61aa8ca0443dc1f`. Code commit `28f0fbbbf8137ecf6afa47499c01bf11cd686428`, working tree dirty (four held files: `.dockerignore`, `Dockerfile`, `tests/conftest.py`, `tests/test_decode_zbar.py`). Host: macOS x86_64, Python 3.11.15.
- **Caveats:** the decoder itself was not exercised, since the skipped tests are the ones that call zbar. Counts change as tests are added, so cite the count from the capture at the release commit, not this one.
- **Paper use:** Methods (software quality), only via the release-commit capture.

### E-002 Ollama model tags (source plan tag does not exist)

- **Date and step:** 2026-09-24, planning (decision D3).
- **Class:** design. **Confidence:** verified for what the registry served at capture time.
- **Claim:** the source plan's `qwen2-vl:2b` was not available on the Ollama library. The substitute `qwen3-vl:2b` exists, but the bare tag does not identify one model: the tags page lists `2b-instruct` and `2b-thinking` variants, each in bf16, q4 and q8.
- **Result:** `library/qwen2-vl` returned `HTTP/1.1 404 Not Found` (server date `Thu, 24 Sep 2026 19:47:06 GMT`). `library/qwen3-vl` and `library/qwen3-vl:2b` returned `200 OK`. The `qwen3-vl:2b` page contains `1.9GB` (2 occurrences). The tags page lists `qwen3-vl:2b`, `2b-instruct`, `2b-instruct-bf16`, `2b-instruct-q4`, `2b-instruct-q8`, `2b-thinking`, `2b-thinking-bf16`, `2b-thinking-q4`, `2b-thinking-q8`.
- **Evidence:** [raw/E-002.txt](raw/E-002.txt), sha256 `b9757e1c5822a64fef9b17f277105b5c231c33f6a5809f97e1c27ccaf6651761`. Code commit `28f0fbbbf8137ecf6afa47499c01bf11cd686428`.
- **Caveats:** registry state at one moment. The `1.9GB` figure comes from the page text and is not tied to a downloaded file. Which variant the bare `2b` tag resolves to was not determined. Only a digest pins a model, so the digest and variant must be recorded when the model is pulled on the Pi (plan track H3). A thinking variant would also change Tier 3 latency, which matters for the edge-cost result.
- **Paper use:** Methods (model and pinning), Threats to validity (reproducibility).

### E-003 pyzbar maintenance status

- **Date and step:** 2026-09-24, planning (decision D4).
- **Class:** design. **Confidence:** verified for PyPI's listing at capture time.
- **Claim:** the newest pyzbar release is from 2022-03-15 and declares support only up to Python 3.10.
- **Result:** latest version `0.1.9`; `requires_python` empty; Python classifiers `2, 2.7, 3, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10`; the three most recent uploads are `0.1.7` (2018-05-13), `0.1.8` (2019-02-21) and `0.1.9` (2022-03-15T14:53:40Z). At capture that is about 4 years 6 months since the last upload.
- **Evidence:** [raw/E-003.txt](raw/E-003.txt), sha256 `aedb8c788feb0d076a654d0e04fceef559ee9149a635597d9b1cad763d4fbb80`. Code commit `28f0fbbbf8137ecf6afa47499c01bf11cd686428`.
- **Caveats:** this shows uploads to PyPI only. The source repository may be more active, which was not checked. Whether pyzbar works on Python 3.11 in practice is unverified until the zbar tests run (E-001 skips them).
- **Paper use:** Threats to validity (an unmaintained decoder wrapper, mitigated by the `Decoder` interface).

### E-004 Debian zbar source and patches

- **Date and step:** 2026-09-24, P1 (decisions D4 and D13).
- **Class:** design. **Confidence:** verified for checksums and patch headers. The relevance to this testbed is inference.
- **Claim:** Debian Bookworm's zbar `0.23.92-7+deb12u1` is upstream 0.23.92 plus four patches, one of which fixes an out-of-bounds access in the QR decoder (CVE-2023-40889).
- **Result:** the downloaded upstream tarball and Debian patch tarball match the sha256 values in the `.dsc` (`dffc16695cb6e42fa318a4946fd42866c0f5ab735f7eaf450b108d1c3a19b4ba` and `bb794d1466b2ba5adabbb5ac7d271e801c757d096d4838fb0f721f6ed87eb588`). The patch series is: perl shebang; Python 3.11 enum build fix; `0003-CVE-2023-40889-qrdec.c-Fix-array-out-of-bounds-acces` (touches `zbar/qrcode/qrdec.c`); `0004-Add-bounds-check-for-CVE-2023-40890` (touches `zbar/decoder/databar.c`).
- **Evidence:** [raw/E-004.txt](raw/E-004.txt), sha256 `c6523f5c66e3a049f5388e6802e8eca9ab0827b0e192175ce0e1fae318885523`. Code commit `28f0fbbbf8137ecf6afa47499c01bf11cd686428`.
- **Caveats:** the checksums were compared to a `.dsc` from the same mirror over HTTPS. The `.dsc` signature was not verified, so this shows the files are consistent with what the mirror lists, not that they are authentic. That the Pi's `libzbar0` is this exact package is assumed until `dpkg-query` runs on the Pi (every later capture header records it). That the CVE is reachable by this testbed's inputs is my inference: the testbed feeds crafted QR codes to the decoder, and the fix is in the QR decoder. CVE-2023-40890 is in DataBar code, which the testbed's decoder does not enable.
- **Paper use:** Methods (decoder version and patch level), Threats to validity (results depend on the zbar build, so malformed-input results must not be compared across builds).

### E-005 pyzbar pixel and data handling (source inspection)

- **Date and step:** 2026-09-24, P1 (decision D5).
- **Class:** dev-observation. **Confidence:** source-read, not executed.
- **Claim:** in pyzbar 0.1.9 a 3-dimensional array is reduced to its first channel, and symbol data is read by the length zbar reports.
- **Result:** in `pyzbar/pyzbar.py`, `_pixel_data` contains `# Take just the first channel` followed by `image = image[:, :, 0]` (lines 160 and 161); `_decode_symbols` reads `string_at(zbar_symbol_get_data(symbol), zbar_symbol_get_data_length(symbol))` (lines 104 to 106).
- **Evidence:** [raw/E-005.txt](raw/E-005.txt), sha256 `335e867484ff02ce930b812f9b5e2aa738e1e6664ff0ec2a83155a31460d80fa`. Code commit `28f0fbbbf8137ecf6afa47499c01bf11cd686428`.
- **Caveats:** read from source, never executed against zbar. Two inferences are not in the capture: that the first channel of an OpenCV frame is blue (OpenCV's BGR order is external knowledge), and that reading by length means a NUL byte is not truncated by pyzbar (whether zbar itself truncates or transcodes is untested). The testbed converts frames to 8-bit grayscale before decoding, so it does not depend on the first-channel behaviour.
- **Paper use:** Methods (preprocessing). The decoder's real handling of NUL bytes and invalid UTF-8 needs its own executed entry.

### E-006 QR payload capacity with the testbed's renderer

- **Date and step:** 2026-09-24, P1.
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** the largest payload the renderer can produce, in byte mode, is 2953 bytes at error correction L, which bounds the "oversized" attack family.
- **Result:** `qrcode 8.2`; maximum bytes by error-correction level: `L 2953`, `M 2331`, `Q 1663`, `H 1273`; one byte more fails at every level.
- **Evidence:** [raw/E-006.txt](raw/E-006.txt), sha256 `956bf21b86466b142a9ee948907bae9909b809e22f3a098908ff3c29f6dd51b4`. Code commit `28f0fbbbf8137ecf6afa47499c01bf11cd686428`.
- **Caveats:** these are the renderer's limits with 0x61 bytes, which use byte mode. Numeric and alphanumeric payloads hold more. Whether zbar can decode a maximum-capacity code has not been tested.
- **Paper use:** Methods (payload size bounds for the malformed family).

### E-007 First real zbar run: non-ASCII QR payloads do not round-trip

- **Date and step:** 2026-09-24, P1.2.
- **Class:** dev-observation. **Confidence:** verified (re-runnable, but the test that produced it has since been rewritten around this finding).
- **Claim:** in zbar's default mode, non-ASCII UTF-8 QR payloads came back with different bytes, while the 100 ASCII payloads came back exactly. This was a failure of my own expectation, which was that a QR round trip is exact for any UTF-8 text.
- **Result:** `1 failed, 1 passed, 6 deselected in 2.05s`. The failing assertion reads `3/103 QR round trips differ` and lists `José` returned as `b'Jos\xe7\x9f\x87'`, `李雷` returned as `b'\xe8\xad\x9a\xe6\x9c\xb1\xe5\xb3\xad'`, and `Zoë O'Neil-Smith` returned as `b"Zo\xe7\xa6\xb1 O'Neil-Smith"`. The Code 128 round-trip test passed.
- **Evidence:** [raw/E-007.txt](raw/E-007.txt), sha256 `3353024e45d66ed7fcc9639239f6097d11a07e864c63c05c020118b825018b66` (redacted once after capture and before its first commit, see Corrections; the original hash was `8b0d3e58690964e29420b626d9e36a3224e45cd347942d8d03f5c0d78a50f319`). Code commit `57f49f0e2c10b1b2877867cb36c73a58e753bd05`, working tree dirty (the decode tests and Dockerfile were not yet committed; the capture records only "dirty: yes" because git is not installed in the container). Linux x86_64 container, Python 3.11.16, `libzbar0 0.23.92-7+deb12u1`, pyzbar 0.1.9.
- **Caveats:** this capture shows that the bytes differ, not why or how widely; E-008 and E-009 do that. The first version of the test is no longer in the tree, so re-running this exact command now runs the rewritten tests (which pass); the capture is the record of the first run.
- **Paper use:** Threats to validity (decoder-level rewriting), motivation for E-008.

### E-008 zbar edge-case probe: default mode versus binary mode

- **Date and step:** 2026-09-24, P1.3 (decisions D5 and D14).
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** in default mode zbar returns different bytes for 8 of the 30 probe cases that return one symbol, all of them QR payloads containing bytes at or above 0x80; with scanner config 4 set it returns exact bytes for all 30. ASCII, NUL bytes, control characters, an empty payload and maximum-capacity payloads are exact in both modes.
- **Result:** 34 cases per mode. Default: 22 exact, 8 different, 2 no symbol (EAN-13 not enabled; blank image), 1 image with two symbols (`RIGHT` returned before `LEFT`), 1 case not rendered (empty Code 128: `ValueError: Code 128 cannot encode an empty string`). Config 4: 30 exact, 0 different, the same other 4. Config 4 was accepted by the library (`set_config return codes ... [0, 0]`). The 8 default-mode differences, as returned versus rendered bytes: `José` 6 vs 5; `李雷` 9 vs 6; `Zoë O'Neil-Smith` 18 vs 17; invalid UTF-8 `ab\xff\xfe` 6 vs 4 (`ab\xc3\xbf\xc3\xbe`, valid UTF-8); `caf\xe9` 5 vs 4 (`caf\xc3\xa9`); `a\x80b` 4 vs 3 (`a\xc2\x80b`); all 256 byte values 384 vs 256; 2953 pseudo-random bytes at ECC L 4426 vs 2953. Exact in both modes: 1000, 2331 and 2953 ASCII bytes; NUL first, middle, last and only NULs; CR LF TAB ESC; an empty QR payload (one symbol, zero bytes); Code 128 including TAB, LF, NUL, ESC and DEL.
- **Evidence:** [raw/E-008.txt](raw/E-008.txt), sha256 `157910806c5ce62facd8fe382a63d508491250be54294702802e202e9c28c0ed`. Code commit `a6d9470e9b770e8151a73e28a5c1f025ea4920fa`, working tree clean. Linux x86_64 container, Python 3.11.16, `libzbar0 0.23.92-7+deb12u1`, pyzbar 0.1.9. Probe: `tools/probes/decode_edge_cases.py`.
- **Caveats:** one zbar build, on the container's CPU; clean synthetic renders at one box size and border, with no camera noise or perspective; 34 hand-chosen cases are a probe, not a distribution. "Exact" compares with the bytes the same script rendered. The probe drives pyzbar's private scanner helpers (pyzbar pinned at 0.1.9). That config 4 is zbar's binary flag is established by E-009, not by this capture. The decoded-length growth on the pseudo-random case is shown only as a length and a prefix.
- **Paper use:** Methods (decoder configuration and its effect), Threats to validity (decoder is part of the trust boundary; build dependence). To be repeated on the Pi before any quantitative claim.

### E-009 Upstream zbar source for the text-conversion flag

- **Date and step:** 2026-09-24, P1.3 (decision D5).
- **Class:** design. **Confidence:** source-read.
- **Claim:** zbar's QR text conversion is a documented, switchable behaviour: upstream defines `ZBAR_CFG_BINARY` ("don't convert binary data to text") and, unless it is set, guesses among SJIS, Latin-1, Big-5 and UTF-8.
- **Result:** in `include/zbar.h`, `ZBAR_CFG_BINARY` is defined with the comment `don't convert binary data to text`. In `zbar/qrcode/qrdectxt.c`, line 79 reads the flag for QR into `raw_binary`; lines 85, 87, 89 and 91 open converters for ISO8859-1, SJIS, UTF-8 and BIG-5; lines 188 to 191 set the initial order (SJIS, Latin-1, Big-5, UTF-8); line 253 tests `if (raw_binary)`; line 261 reads `If there was data encoded in kanji mode, assume it's SJIS.`; line 284 reads `If the text is 8-bit clean, prefer UTF-8 over SJIS`. The tarball sha256 `dffc16695cb6e42fa318a4946fd42866c0f5ab735f7eaf450b108d1c3a19b4ba` equals the one recorded in E-004.
- **Evidence:** [raw/E-009.txt](raw/E-009.txt), sha256 `5bf4e750c807ce44f3e261bde80326362111a4cb00e954131c6bb1d285e454d1`. Code commit `a6d9470e9b770e8151a73e28a5c1f025ea4920fa`, working tree clean (captured on the host; it reads upstream source, not the Debian build).
- **Caveats:** three inferences are not in the capture. First, the flag's value is 4 by enumeration order (the capture prints only some members), which E-008 supports because library config 4 was accepted and changed results. Second, that Debian's build has an identical `qrdectxt.c`: E-004 shows the Debian patches touch `qrdec.c` and `databar.c`, and the other two patches (perl shebang, Python enum) are assumed not to. Third, that `José` returning one different character is a Big-5 reading of `c3 a9` is consistent with the converter list but was not confirmed.
- **Paper use:** Methods (why raw mode exists), Threats to validity.

### E-010 Full test suite in the Bookworm image

- **Date and step:** 2026-09-24, P1.
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** the whole suite, including every decoder test in both decoder modes, passes against the same `libzbar0` package the Pi's OS uses, with none skipped.
- **Result:** `168 passed in 10.11s`, exit 0. The image sets `VTB_REQUIRE_ZBAR=1`, so a missing library would have failed the zbar tests rather than skipped them. The suite pins the bytes measured in E-008, so this run also shows those measurements reproduce.
- **Evidence:** [raw/E-010.txt](raw/E-010.txt), sha256 `ab31c6d31b85d88536a9cc0f93969d4b2f580c2e3da8ab34a4bdf88e7e9c5062`. Code commit `92b2f4ffe75adc1996b45cfb026a84a573636f9c`, working tree clean. Linux x86_64 container (Docker Desktop VM on macOS), Python 3.11.16, `libzbar0 0.23.92-7+deb12u1`.
- **Caveats:** x86_64, not the Pi's aarch64, so it says nothing about the Pi's CPU or that the same zbar build behaves identically there; the Pi run is still to do. The pinned byte expectations were written from E-008, so agreement with E-008 is expected. This capture replaces one taken earlier the same day at a commit that was later rewritten (see Corrections). The test count changes as tests are added; the paper should cite the release-commit capture.
- **Paper use:** Methods (software quality), only via the release-commit capture.

### E-011 Decode success by symbology and decoder mode

- **Date and step:** 2026-09-24, P1.2 (acceptance figure) and decision D14.
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** on the seeded benign set, both symbologies decode exactly for ASCII payloads in both decoder modes, while non-ASCII QR payloads decode exactly only in raw mode.
- **Result:** benign set of 100 ASCII ids (seed 1337) rendered as QR and as Code 128, plus 3 non-ASCII texts as QR only. Default mode: QR ASCII `100/100`, QR non-ASCII `0/3`, Code 128 ASCII `100/100`. Raw mode: QR ASCII `100/100`, QR non-ASCII `3/3`, Code 128 ASCII `100/100`. "Exact" means one symbol whose bytes equal the rendered bytes.
- **Evidence:** [raw/E-011.txt](raw/E-011.txt), sha256 `66b0ed36241c1009186834ac5c09bed5c93e9dbaef9ab3369274775be6ae198e`. Code commit `9204be4c4e9ab6ab6ce112c80a4a0e560a56f800`, working tree clean. Linux x86_64 container, Python 3.11.16, `libzbar0 0.23.92-7+deb12u1`. Probe: `tools/probes/roundtrip_rate.py`.
- **Caveats:** 100 per symbology, so zero failures bounds the failure rate at roughly 3% (rule of three), not at zero. The non-ASCII set is 3 texts: an illustration, not a rate. Clean synthetic renders, no camera. This is not the benign set of at least 1000 items that decision D14 requires; that comes in P3. One zbar build; the Pi run is still to do. This capture replaces one taken earlier the same day at a commit that was later rewritten (see Corrections); the figures were identical.
- **Paper use:** Methods (decoder validation). It becomes a Results figure only when repeated on the Pi as a `result-of-record`.

### E-012 What an injected string can do through Python's sqlite3

- **Date and step:** 2026-09-24, planning the containment design (decision D12, gate G2).
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** through `Connection.execute()`, a string-built query cannot stack a second statement, cannot load a native extension, and cannot `ATTACH` a file, so SQL injection in the vulnerable Tier 1 handler stays inside the database.
- **Result:** Python `3.11.16`, SQLite `3.40.1`. A second statement (`DROP TABLE`) was `rejected: ProgrammingError: You can only execute one statement at a time.` and the table still existed afterwards (`True`). `select load_extension('x')` was `rejected: OperationalError: not authorized`. An `ATTACH DATABASE` appended after a `SELECT` was rejected for the same one-statement reason, and the file was not created (`False`). `Connection.enable_load_extension` exists (`True`) but was not called, so extension loading stayed at its default. A single standalone `pragma table_info(badges)` was accepted, which is the probe's positive control showing it can observe acceptance.
- **Evidence:** [raw/E-012.txt](raw/E-012.txt), sha256 `5f3f3eeff50976e92687e866a944c032ea5f5ee985371ceff8dfb2ded772fa2f`. Code commit `afd24e0dcf164caa9cb574387dacbb89f86626d5`, working tree clean. Linux x86_64 container, Python 3.11.16. Probe: `tools/probes/sqlite_injection_limits.py`.
- **Caveats:** only `execute()` was probed; `executescript()` accepts multiple statements, so the vulnerable handler must not use it. The injected string controls part of one statement, not the whole, so single-statement forms such as a `UNION` that discloses another table are still possible and are what the Tier 1 oracle signals target; they were not probed here. One SQLite and Python build; the Pi's versions are unchecked and the probe should be repeated there.
- **Paper use:** Methods (why the SQL sink is contained, and what the Tier 1 SQL oracle can and cannot see).

### E-013 Containment battery, first run: 3 of 14 failed

- **Date and step:** 2026-09-24, P2 (gate G2 condition: the sandbox is proven before any vulnerable code is written).
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** the first real run of the containment battery found two design gaps and one runner bug, all before any vulnerable code existed.
- **Result:** `3 failed, 11 passed in 48.68s`. `test_3` failed with `PermissionError: [Errno 13] Permission denied: '/audit/a'`: the `/audit` tmpfs took the permissions of its root-only mount point, so the sandbox user could not write it. `test_4b` failed with `assert not ['GPG_KEY']`: the environment check flagged a variable that comes from the base image. `test_9b` failed with `subprocess.TimeoutExpired: Command '['docker', 'rm', '-f', ...]' timed out after 30 seconds`: the runner had stopped reading a flooding container's output, and `docker rm -f` hung on the full pipe.
- **Evidence:** [raw/E-013.txt](raw/E-013.txt), sha256 `7e514666fd8d4e9aa2e3701786d28d9fa4f8189e2c35f6c79b371df58f116bb2`. Code commit `99bdd15a2648e57a8610f21db9638ada7e92b525`, working tree clean. macOS x86_64 host, Python 3.11.15, Docker Desktop.
- **Caveats:** the Docker version is not in this header (the tool did not record it yet); the tool now does, and it reports client and server 29.6.2 on this machine the same day. That the `GPG_KEY` variable is the Python image's public signing-key id is my inference from the variable's name and origin (the base image); the capture shows only that the name was flagged. Fixed in commit `b2f48c6`: tmpfs ownership stated explicitly, the runner kills the client before removing the container, the environment test compares against the image's own declared variables, and the persistence test now checks that its first call succeeded.
- **Paper use:** Methods (the sandbox was tested before use, and what that testing found).

### E-014 Containment battery on the laptop: 14 of 14 pass

- **Date and step:** 2026-09-24, P2.
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** in the laptop's Docker sandbox, the eight designed containment checks and the runner's own safety checks all hold. This meets the condition that the vulnerable Tier 1 code is not written until the battery passes on the laptop.
- **Result:** `14 passed in 18.67s`. Observed values: outbound connection to `1.1.1.1:53` failed with `OSError` errno 101, a connection to the sandbox's own loopback port failed with `ConnectionRefusedError` (111), the host alias failed name resolution (`gaierror`, -3), DNS failed, and no connection reached a listener the harness opened on the host. Writes were refused with errno 30 for `/etc`, `/usr`, `/app`, `/`, `/var`, `/run` and `/sys`, errno 2 for `/proc` and the home path, and errno 13 for `/dev`. A host file outside every mount was not visible (`path_exists: false`, found nowhere). The process ran as uid 10001 with `CapPrm`, `CapEff` and `CapBnd` all `0000000000000000` and `NoNewPrivs` 1. With the process limit at 64, 63 children started and the next fork failed (`started: 63, failed_at: 63`). A 400 MiB allocation under a 256 MiB limit was killed (exit code 137, nothing printed afterwards). A second call saw `/canary`, `/tmp` and `/audit` all empty. The SQLite lines are those of E-012 (stacked statement rejected, table intact, `load_extension` `not authorized`, no file created). A timed-out call left no running container, a runaway writer was stopped at the 1 MiB output cap without waiting for the timeout, and stdin and exit codes passed through.
- **Evidence:** [raw/E-014.txt](raw/E-014.txt), sha256 `331eb1b94b82275cd98d17bb267c86a85a1a09fe91ba3f72ee489757e6a52f50`. Code commit `b2f48c6c10e2d368bbec65b055df171c2e0d829e`, working tree clean. macOS x86_64 host, Python 3.11.15, Docker Desktop; the sandbox image is `python:3.11-slim-bookworm` (Python 3.11.16, SQLite 3.40.1 per the embedded probe).
- **Caveats:** the tests are inert and show that these attempts failed, not that no escape exists; a kernel or runtime exploit is a stated non-goal. The isolation is Docker Desktop's Linux VM plus the container, so it is not the Pi's sandbox: the Pi uses `systemd-run`, which is unverified and needs its own capture. That errno 30 means a read-only file system and 101 means network unreachable is standard Linux knowledge, not shown by the capture. The Docker version is not in this header (see E-013). Resource limits were probed at one size each. Test 3's positive control (a write to `/canary` succeeds) is recorded by the test passing; its values are not printed.
- **Paper use:** Methods (how deliberately vulnerable code was run safely, and what was verified).

### E-015 Tier 1 through all four modes, in the sandbox

- **Date and step:** 2026-09-24, P2.4 (the first real crossing and the first real block).
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** with the approved oracles and the proven sandbox, the same payloads give the expected verdicts across the four Tier 1 modes: with no control, three of them cross; with validation, all are blocked; with parameterisation alone, all are accepted with no effect; benign identifiers pass in every mode.
- **Result:** 9 payloads by 4 modes, 36 rows (verdicts as off / validate_only / parameterise_only / full). `inj-sql-001` crossed / blocked / no_effect / blocked; `inj-union-001` crossed / blocked / no_effect / blocked; `inj-shell-001` crossed / blocked / no_effect / blocked; `inj-kill-001` no_effect / blocked / no_effect / blocked; `inj-sleep-001` fault / blocked / no_effect / blocked; `mal-quote-001` fault / blocked / no_effect / blocked; and `ben-active-001`, `ben-revoked-001`, `ben-unknown-001` benign_ok in all four modes. In `off` mode the signals were: `inj-sql-001` signal A (unauthorised grant); `inj-union-001` signals A and C (a grant plus the restricted canary secret in the output); `inj-shell-001` signal D (the harness saw the file `inj-shell-001` in the canary directory from the host side); `inj-sleep-001` `error TimeoutExpired`; `mal-quote-001` `error OperationalError`; `inj-kill-001` nothing. `39 passed in 70.95s` (the 36 rows plus three further checks).
- **Evidence:** [raw/E-015.txt](raw/E-015.txt), sha256 `6b4f6ce501bcb336f989f6ad978ac12cb566db0259ccbcbfc62c5fded7723bcb`. Code commit `5d2942d27b8c6a850391ac55678420371c945564`, working tree clean. macOS x86_64 host, Docker client and server 29.6.2 (in the header). The sandbox image is identified in E-016.
- **Caveats:** these are nine hand-written, naive payloads. Validation blocking every one is what the design predicts by construction (decision D7) and says nothing about adaptive or grammar-conformant attacks, which are P6 and the held-out set. Signal T1-B (table tamper) never fired, because stacked statements are impossible through `execute()` (E-012), so it has not been exercised by an attack. The `kill -9 $PPID` payload had no effect because the tier is PID 1 in its container and the kernel ignores SIGKILL sent to a namespace's init from inside it: this is a limit on what a payload can do here, and my first expectation for this row was wrong. The sleep payload's fault comes from the tier's own 5-second shell timeout. The decode stage is bypassed (records are built from text); image-to-record decoding is validated separately (E-008, E-011) and joined in the P3 harness. Three benign cases are a demonstration, not the 1000 or more that decision D14 needs for a false-positive rate. One run per cell, on a deterministic tier. Docker Desktop on macOS, not the Pi.
- **Paper use:** Methods (a worked example of the oracle and the four-mode design). Not Results.

### E-016 The sandbox image E-015 ran in

- **Date and step:** 2026-09-24, P2.
- **Class:** dev-observation. **Confidence:** verified for what the image says about itself; the link to E-015 is assumed (see caveats).
- **Claim:** the deliberately vulnerable code ran in image `sha256:8f31726dbfd1f2cea6729055e73f512932c210a92dbacd5684d7ed3bbca1f831`, built `2026-09-24T23:02:19Z`, linux/amd64, user `10001:10001`, working directory `/app`, command `python3`, with `VTB_IN_SANDBOX=1` and `PYTHONPYCACHEPREFIX=/tmp/pycache` in its environment.
- **Result:** as above; the environment also carries the Python base image's variables (`PYTHON_VERSION=3.11.16` and others).
- **Evidence:** [raw/E-016.txt](raw/E-016.txt), sha256 `1cca5761ebfc787e5b89ac566ea6602c26efd1c08e5260116817287cf6123d64`. Code commit `1dfc1a86d87ecab72e29bd5af5ea58632e33dab5`, working tree clean; the header records the same image id.
- **Caveats:** an image id identifies the built image, not the Dockerfile that produced it. That this is the image E-015 ran in is assumed: E-015's header predates the tool recording the image id, but the image was built once before E-015 and not rebuilt before this capture (the build printed the same id). Every capture from here on records the image id in its header. That `GPG_KEY` in the environment is the base image's public signing-key fingerprint is my inference.
- **Paper use:** Methods (reproducibility of the sandbox).

### E-017 Full suite in the Bookworm dev image after Tier 1

- **Date and step:** 2026-09-24, P2.
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** everything that does not need Docker passes in the dev image with the real `libzbar0`: the contracts, decode stage, defense, badge database, verdict function, Tier 1 in its defended modes and its host-side guard, and the Tier 1 oracle.
- **Result:** `308 passed, 53 skipped in 10.13s`, exit 0. The 53 skips are the sandbox tests (the 14-test containment battery and the 39-test Tier 1 demonstration), all skipped for the same reason, `sandbox unavailable: docker is not installed here`.
- **Evidence:** [raw/E-017.txt](raw/E-017.txt), sha256 `5468910aa5e56c231e37b3b90d13dbb2943cd846be90611e0a294b3772581780`. Code commit `190735f3437cebd5cc685d54a170b2059573ddf7`, working tree clean. Linux x86_64 container, Python 3.11.16, `libzbar0 0.23.92-7+deb12u1`, Docker not installed (recorded in the header).
- **Caveats:** the sandbox tests do not run here by design; they are covered by the host run. The pinned seed-1337 database hash passes on Python 3.11.16 here and on 3.11.15 on the host, so the ground truth agrees across those two builds; the Pi's Python is unchecked. The test count changes as tests are added, so the paper should cite the release-commit capture.
- **Paper use:** Methods (software quality), only via the release-commit capture.

### E-018 Full host suite with the sandbox required

- **Date and step:** 2026-09-24, P2.
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** on the host, with Docker and the sandbox image present and `VTB_REQUIRE_SANDBOX=1` (so a missing sandbox fails instead of skipping), the whole suite passes, including the containment battery against the rebuilt image and the Tier 1 four-mode demonstration.
- **Result:** `306 passed, 55 skipped in 95.27s`, exit 0. All 55 skips are the decoder tests, skipped because the host has no `libzbar`. Together with E-017 (308 passed, 53 skipped) the two runs each account for 361 tests, and the tests skipped in one environment are the ones that ran in the other.
- **Evidence:** [raw/E-018.txt](raw/E-018.txt), sha256 `2bb73043564625a96a95ab58698a3944545109313f07d2bc47da3df8de35dee6`. Code commit `48aac9d28d6b634db41a8601a064c5474c4db63f`, working tree clean. macOS x86_64 host, Python 3.11.15, Docker client and server 29.6.2. The header records the sandbox image: `sha256:8f31726dbfd1f2cea6729055e73f512932c210a92dbacd5684d7ed3bbca1f831`, the same as in E-016, so the image was unchanged across this stage.
- **Caveats:** Docker Desktop on macOS, not the Pi. The battery, the demonstration and the decoder tests never run in one environment together, because Docker is on the host and `libzbar` is in the dev image; the two captures together cover them. The test count changes as tests are added, so the paper should cite the release-commit capture.
- **Paper use:** Methods (software quality and sandbox reproducibility), only via the release-commit capture.

### E-019 The payload set through the real decoder, before any fix

- **Date and step:** 2026-09-25, P3 (the first real decode of the generated payload set).
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** the first real decode of the payload set exposed two errors in my generator, both invisible to its own tests: a truncated Code 128 still decodes, and regenerated PNG files are not byte-identical across the two environments.
- **Result:** 143 images decoded in each condition. Default: statuses `{'no_symbol': 1, 'ok': 142}`; unexpected outcome `('mal-trunc-002', 'fail', 'ok')`; decoded bytes differ from rendered bytes for `mal-utf8-001` and `mal-utf8-002`. Raw: `{'invalid_utf8': 2, 'no_symbol': 1, 'ok': 140}`; the same unexpected outcome; no byte differences. Images regenerated in the container did not match the manifest built on the host: `False (144 differences)`, which is 143 image file hashes plus the library-version line (container Python 3.11.16, manifest Python 3.11.15; pillow 12.3.0, qrcode 8.2 and python-barcode 0.16.1 identical). The images already on disk did match the manifest's hashes (`True`).
- **Evidence:** [raw/E-019.txt](raw/E-019.txt), sha256 `b9f844939604fb91b16612b828d3fcb838e14f7e67ef1d6c7f8b1d3619abce30`. Code commit `093fa49c63ec50d24674b31b893400ca08712c2c`, working tree clean. Linux x86_64 container, Python 3.11.16, `libzbar0 0.23.92-7+deb12u1`. Probe: `tools/probes/decode_payload_set.py`.
- **Caveats:** the manifest at that commit did not record the platform, so the comparison attributed the difference to library versions; which of the platform or the Python patch version changes the PNG bytes was not isolated. The reason a truncated Code 128 decodes (a linear barcode is readable along any row, so cutting its height leaves every bar) is my explanation, supported by the fix in E-020 but not separately tested. Fixed in commit `5d9c783`.
- **Paper use:** Methods (validation of the payload set, and a reminder that image identity should be pixel content).

### E-020 The payload set through the real decoder, after the fix

- **Date and step:** 2026-09-25, P3.
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** after the fixes, every payload decodes as designed in both decoder conditions, and the images are pixel-identical across macOS and Linux even though their PNG bytes are not.
- **Result:** libraries here: platform `Linux x86_64`, Python `3.11.16`, pillow `12.3.0`, qrcode `8.2`, python-barcode `0.16.1`; the manifest was built on `Darwin x86_64` with Python `3.11.15`. `pixel hashes equal to the manifest's: 143 of 143`; `images regenerated here match the committed manifest: True` (pixel content compared, since the environment differs). Default condition: `{'no_symbol': 2, 'ok': 141}`, 141 payloads applicable, `unexpected decode outcomes: none`, decoded bytes differ from rendered only for `mal-utf8-001` and `mal-utf8-002`. Raw condition: `{'invalid_utf8': 2, 'no_symbol': 2, 'ok': 139}`, 143 applicable, `unexpected decode outcomes: none`, no byte differences. `mal-unicode-001` (fullwidth digits, valid UTF-8) came back exact in the default condition.
- **Evidence:** [raw/E-020.txt](raw/E-020.txt), sha256 `efb28e6a16bb43f2b609d426d811f42bb72237b53602a4e8c09cdc9a7ac38e6d`. Code commit `5d9c783db5990f9da1540f46db9453c28d44bad2`, working tree clean. Linux x86_64 container, Python 3.11.16, `libzbar0 0.23.92-7+deb12u1`.
- **Caveats:** one zbar build. PNG file hashes were not compared across environments, by design. Pixel equality was shown for one platform pair (macOS x86_64 and Linux x86_64); the Pi (aarch64) is unchecked. The decoder rewrote `mal-utf8-001` and `mal-utf8-002` in the default condition but not `mal-unicode-001`: one payload each, so this shows that rewriting depends on the content, not a rule for which content.
- **Paper use:** Methods (payload set validation and image reproducibility); Threats to validity (default-mode rewriting is content-dependent).

### E-021 The payload set decoded into records files

- **Date and step:** 2026-09-25, P3 (the decode stage of the pipeline).
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** the 143 generated images decode inside the dev image into three records files (default condition, raw condition, and a second default decode), each with a metadata sidecar naming the decoder build.
- **Result:** `wrote 143 records (default mode)`, `wrote 143 records (raw mode)` and a second `wrote 143 records (default mode)`. The sidecar records `decoder` `pyzbar`, `pyzbar` `0.1.9`, `libzbar0` `0.23.92-7+deb12u1`, `python` `3.11.16`, `image_dir` `attacks/out` and `records` `143`.
- **Evidence:** [raw/E-021.txt](raw/E-021.txt), sha256 `f8c41de8d6dd48bdf2b36b4b8229f5ce017f36bd8e0eb65a520b409beea8e2d1`. Code commit `c90529e30bc6c5629a9391b38c9ba3e284c6106b`, working tree dirty: no. Linux x86_64 container.
- **Caveats:** the records carry decode timestamps and decode times, so two decodes of the same images differ in those fields by design; E-020 shows the decode outcomes, statuses and bytes agree. Both sets of runs below read these records files; records depend only on the images and the decoder, not on the tier code.
- **Paper use:** Methods (the pipeline's decode stage and its provenance record).

### E-022 First Tier 1 run, default decoder condition, before the timeout fix

- **Date and step:** 2026-09-25, P3.3 (the first CSV from Tier 1 on the laptop).
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** the pipeline produced a schema-valid CSV of 564 rows (141 payloads by 4 modes).
- **Result:** verdicts per mode: `off`: benign_ok 110, crossed 15, fault 4, no_effect 10, not_delivered 2; `validate_only`: benign_ok 110, blocked 29, not_delivered 2; `parameterise_only`: benign_ok 110, no_effect 29, not_delivered 2; `full`: benign_ok 110, blocked 29, not_delivered 2. `results.csv` has 565 lines (a header and 564 rows), sha256 `cfdd45f3443fe360eb7c3f600e4b476abdb34533c11e820fcd6073e56df6fc71`.
- **Evidence:** [raw/E-022.txt](raw/E-022.txt), sha256 `3cfdcdf0024fd57ace96e4dbc2b3ab8a6aebc175607080a36f71e8fa1be6f452`. Code commit `c90529e30bc6c5629a9391b38c9ba3e284c6106b`, working tree dirty: no. macOS host, Python 3.11.15, Docker client and server 29.6.2, three sandbox calls in parallel. The run metadata is in the capture.
- **Caveats:** superseded for reproducibility by E-026 to E-029: E-025 found that this run and E-024 differ in one non-timing cell. The results file is a local, git-ignored output; its hash fingerprints it. Timing columns were recorded on a heavily loaded machine with parallel calls and are not results.
- **Paper use:** Methods (the first end-to-end run). Not Results.

### E-023 First Tier 1 run, raw decoder condition, before the timeout fix

- **Date and step:** 2026-09-25, P3.3.
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** the raw decoder condition adds the two invalid-UTF-8 payloads to the matrix: 572 rows (143 payloads by 4 modes).
- **Result:** verdicts per mode: `off`: benign_ok 110, crossed 15, fault 4, no_effect 12, not_delivered 2; `validate_only`: benign_ok 110, blocked 31, not_delivered 2; `parameterise_only`: benign_ok 110, no_effect 31, not_delivered 2; `full`: benign_ok 110, blocked 31, not_delivered 2. `results.csv` sha256 `526025ea325d10d1e5a465963ff249fb96d636d18073284eb1f35fa0a0ad9ced`, 573 lines.
- **Evidence:** [raw/E-023.txt](raw/E-023.txt), sha256 `dac75953f441a7dab1cbfbe4b1e0763c2950cc3e4048bb3dbf181145b6f3523e`. Code commit `c90529e30bc6c5629a9391b38c9ba3e284c6106b`, working tree dirty: no.
- **Caveats:** as E-022. Superseded by E-028, whose verdict counts are identical.
- **Paper use:** Methods.

### E-024 Re-run of the default condition, before the timeout fix

- **Date and step:** 2026-09-25, P3 (the reproducibility check).
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** a second independent run of the default condition gives the same verdict counts as the first.
- **Result:** the same 564 rows and the same verdict counts as E-022. `results.csv` sha256 `59d8c94cda3ddce1da4a99cc5c9c76373bc1f25b27dea3f0f05924ef03400c3e`, which differs from E-022's because timing columns and the run id differ; E-025 compares the cells.
- **Evidence:** [raw/E-024.txt](raw/E-024.txt), sha256 `4502af8cf5334aa9dc8ac5b2b578c31c9af77f1d67b0f9df4d951e72a49abce4`. Code commit `c90529e30bc6c5629a9391b38c9ba3e284c6106b`, working tree dirty: no.
- **Caveats:** see E-025.
- **Paper use:** Methods.

### E-025 The reproducibility check finds a defect

- **Date and step:** 2026-09-25, P3 acceptance ("a re-run reproduces every non-timing column exactly").
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** the comparison of E-022 with E-024 found exactly one differing non-timing cell out of 564 rows, so the acceptance check failed until the tier was fixed.
- **Result:** exit code 1, output: `('tier1', 'off', 'default', 'inj-sleep-001', 0): detail differs` between `Command 'echo x; sleep 30 >> /audit/audit.log' timed out after 4.999930853999103 seconds` and `... after 4.99997205100226 seconds`, then `1 differences (ignoring handle_ns, defense_ns, run_id)`. No verdict, signal, error or other cell differed.
- **Evidence:** [raw/E-025.txt](raw/E-025.txt), sha256 `80d8aa80c73ffbe0e822a232b6bca9476b087e59db4a1fb8d80f5e3f717daebd`. Code commit `c90529e30bc6c5629a9391b38c9ba3e284c6106b`, working tree dirty: no.
- **Caveats:** the cause is that `subprocess.TimeoutExpired`'s message embeds the measured elapsed seconds, which the tier copied into `detail`. Fixed in commit `f03af06`: the tier reports a fixed description, and a test feeds three elapsed values and requires the same text. The check found it because timing columns are the only ones excluded from comparison; any other measured value leaking into a text column would be found the same way.
- **Paper use:** Methods (reproducibility check and what it caught).

### E-026 Tier 1 run, default decoder condition, after the fix

- **Date and step:** 2026-09-25, P3.3.
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** at the fixed commit the pipeline produces a schema-valid CSV of 564 rows with the same verdict counts as before the fix.
- **Result:** verdicts per mode: `off`: benign_ok 110, crossed 15, fault 4, no_effect 10, not_delivered 2; `validate_only`: benign_ok 110, blocked 29, not_delivered 2; `parameterise_only`: benign_ok 110, no_effect 29, not_delivered 2; `full`: benign_ok 110, blocked 29, not_delivered 2. `results.csv` sha256 `5bfa954e7c98da5bca01308b879155d0d45269187a8b75ca7bf733a5d1b52a7c`.
- **Evidence:** [raw/E-026.txt](raw/E-026.txt), sha256 `bdddfd076bf4a9ca3f80da2e31faa904c58cd4b7f395690e67174c35f183c4e3`. Code commit `f03af06a934abf313fe72b2c5d3b5436587dbd76`, working tree dirty: no. The run metadata in the capture records the sandbox image and its source hash.
- **Caveats:** naive payloads only, Tier 1 only, one repetition per cell on a deterministic tier. Laptop timing columns are not results.
- **Paper use:** Methods (worked run). Not Results.

### E-027 Re-run of the default condition, after the fix

- **Date and step:** 2026-09-25, P3.
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** an independent second run at the fixed commit.
- **Result:** the same 564 rows and verdict counts as E-026. `results.csv` sha256 `c59f8094a8d14d6f8a028061d966588df2c3319456ee9332113dd298e8df797f`.
- **Evidence:** [raw/E-027.txt](raw/E-027.txt), sha256 `9d9c8e51b6323ddc0255cf7e1127f5dc7e91d7d1f1efa93a2d85df4ba0f3a5e4`. Code commit `f03af06a934abf313fe72b2c5d3b5436587dbd76`, working tree dirty: no.
- **Caveats:** as E-026.
- **Paper use:** Methods.

### E-028 Tier 1 run, raw decoder condition, after the fix

- **Date and step:** 2026-09-25, P3.3.
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** the raw condition at the fixed commit: 572 rows, with the two invalid-UTF-8 payloads delivered and refused by validation.
- **Result:** verdicts per mode: `off`: benign_ok 110, crossed 15, fault 4, no_effect 12, not_delivered 2; `validate_only`: benign_ok 110, blocked 31, not_delivered 2; `parameterise_only`: benign_ok 110, no_effect 31, not_delivered 2; `full`: benign_ok 110, blocked 31, not_delivered 2. `results.csv` sha256 `b710739d6ff19eb071cb5553d094bb257e0f1fd78ac271722780dfc8e059c40b`.
- **Evidence:** [raw/E-028.txt](raw/E-028.txt), sha256 `cdf76101bd3c014372976b80e28f76bce23b654ad3e2563931a04352f223d621`. Code commit `f03af06a934abf313fe72b2c5d3b5436587dbd76`, working tree dirty: no.
- **Caveats:** as E-026.
- **Paper use:** Methods.

### E-029 The reproducibility check passes

- **Date and step:** 2026-09-25, P3 acceptance, laptop half.
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** two independent runs of the default condition at the fixed commit agree on every non-timing column of all 564 rows.
- **Result:** exit code 0, output `0 differences (ignoring handle_ns, defense_ns, run_id)`.
- **Evidence:** [raw/E-029.txt](raw/E-029.txt), sha256 `78bccedad747bf532c09fa2b8877c86bfe6b00a4b71cf5f309d384215af9938b`. Code commit `f03af06a934abf313fe72b2c5d3b5436587dbd76`, working tree dirty: no. Compares the results of E-026 and E-027.
- **Caveats:** the acceptance criterion also requires a schema-valid CSV from the Pi; that half is not met. `run_id` is ignored because the decode step names it. One pair of runs is one sample of reproducibility, not a proof.
- **Paper use:** Methods (reproducibility of the pipeline).

### E-030 Summary of the final default run

- **Date and step:** 2026-09-25, P3.
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** across the four Tier 1 modes and 141 payloads, in the default decoder condition: with no control the SQL, disclosure and shell payloads cross; validation blocks every deliverable attack, and parameterisation alone neutralises every one; no benign payload is refused.
- **Result:** with no control (`off`), signal A fired for `inj-sql-001` to `inj-sql-006`, signals A and C for `inj-union-001` and `inj-union-002`, and signal D for `inj-shell-001` to `inj-shell-007` (15 crossed); `inj-stack-001` and `mal-nul-001` were `fault ProgrammingError`, `mal-quote-001` `fault OperationalError` and `inj-sleep-001` `fault TimeoutExpired` (4 faults); the two truncated symbols were `not_delivered` in every mode. Verdict counts per mode: off benign_ok 110, crossed 15, fault 4, no_effect 10, not_delivered 2; validate_only benign_ok 110, blocked 29, not_delivered 2; parameterise_only benign_ok 110, no_effect 29, not_delivered 2; full benign_ok 110, blocked 29, not_delivered 2. Validation blocked for `refused: length` 20 and `refused: charset` 9. Benign rows: 440, all `benign_ok`, 0 refused by the boundary.
- **Evidence:** [raw/E-030.txt](raw/E-030.txt), sha256 `7bcb40f69d5ddf54e05f2aeda1bb163d9bbf64301661c6acffbb708291df549e`. Code commit `4de0f96322a627d46dba47c2289262e1a635908e`, working tree dirty: no. Summarises the results of E-026.
- **Caveats:** the payloads are the author's naive ones, so validation and parameterisation each stopping all of them is expected by construction (decision D7) and does not say which control does the work: that needs the adaptive and held-out subsets (P6). Zero false positives in 110 benign payloads per mode bounds the rate at roughly 3% (rule of three); decision D14 needs 1000 or more. Signal B never fired (E-012). `inj-kill-001` had no effect because the tier is PID 1 (E-015).
- **Paper use:** Methods (a worked example). Not Results.

### E-031 Summary of the final raw run

- **Date and step:** 2026-09-25, P3.
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** in the raw decoder condition the boundary's encoding control is exercised, which the default condition cannot do.
- **Result:** verdict counts per mode: off benign_ok 110, crossed 15, fault 4, no_effect 12, not_delivered 2; validate_only benign_ok 110, blocked 31, not_delivered 2; parameterise_only benign_ok 110, no_effect 31, not_delivered 2; full benign_ok 110, blocked 31, not_delivered 2. The two extra payloads, `mal-utf8-001` and `mal-utf8-002`, were `no_effect` with no control and blocked with `refused: encoding` by validation. Benign rows: 440, all `benign_ok`.
- **Evidence:** [raw/E-031.txt](raw/E-031.txt), sha256 `5086e4190e9897be788080566b3b8819f034f174ea454727ab20205d1b1f1f53`. Code commit `4de0f96322a627d46dba47c2289262e1a635908e`, working tree dirty: no. Summarises the results of E-028.
- **Caveats:** as E-030. Two encoding cases are an illustration that the control is reachable, not a measurement of it.
- **Paper use:** Methods.

### E-032 Full host suite after P3, with the sandbox required

- **Date and step:** 2026-09-25, P3.
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** the whole suite passes on the host with Docker and the sandbox image present, and the earlier stall did not recur.
- **Result:** `375 passed, 58 skipped in 147.56s (0:02:27)`, exit 0. All 58 skips are the decoder tests (`libzbar not available here`). The slowest test took 9.70 seconds (`test_the_first_real_crossing_and_the_first_real_block`); nothing else exceeded 7.3 seconds.
- **Evidence:** [raw/E-032.txt](raw/E-032.txt), sha256 `f1443cb29f1af5a0ee1df002c7285c0b63456d41638dbe45e2f7ade534793c92`. Code commit `5d1e50057292201f2110298fdff19546cebb46db`, working tree clean. macOS x86_64 host, Python 3.11.15, Docker client and server 29.6.2. The header records the sandbox image, `sha256:311e6c5aa56e15b2eb19bc7404b7485bfa04db4fff2b7f63e5cfd3a714077c71`, the image the final runs used.
- **Caveats:** an earlier full-suite run stalled for over 20 minutes while the host's load average was 75 and was killed; the same tests run separately took 21 seconds, 104 seconds and 15 seconds, and this run took 147 seconds with the load in the twenties to thirties. So the stall is not reproduced and not explained: most likely Docker Desktop under host memory pressure, which is a guess. Docker on this laptop is slow under load, so laptop durations say nothing about the Pi.
- **Paper use:** Methods (software quality), only via the release-commit capture.

### E-033 Dev-image suite after P3: one failure

- **Date and step:** 2026-09-25, P3.
- **Class:** dev-observation. **Confidence:** verified.
- **Claim:** the suite passed on the host but had one failure in the dev image, because a test assumed the same environment as the manifest's.
- **Result:** `1 failed, 379 passed, 53 skipped in 35.73s`, exit 1. The failure is `test_check_mode_reports_a_match_and_a_mismatch`: `assert gen.main(["--check", "--manifest", ...]) == 1` got `0`. The 53 skips are the sandbox tests (`sandbox unavailable: docker is not installed here`).
- **Evidence:** [raw/E-033.txt](raw/E-033.txt), sha256 `a17ff045e0b6d8c73e7c6b5e02f093c00dec86db86972c7ea30bbd47c92d7d16`. Code commit `9ee63975e1cf99f4869468a643aa7490a1aef640`, working tree clean. Linux x86_64 container, Python 3.11.16.
- **Caveats:** the test tampered with a manifest entry's PNG file hash and expected `--check` to report a mismatch. `--check` deliberately compares file hashes only when the environment matches the manifest's (E-019), and the container is Linux while the manifest was built on macOS, so it correctly ignored the tampering. The defect is in the test, not in `--check`; it was invisible on the host, where the environments match. Fixed in the next commit by tampering with the pixel hash, which is compared everywhere. Superseded by E-034.
- **Paper use:** none; recorded because a check that only runs in one environment can hide a defect in another.

## Corrections and tooling notes

- **2026-09-24, commit `3dc1270`:** the first version of `--verify` read files in text mode, which rewrites CRLF line endings, so it reported a false `HASH MISMATCH` for E-002 (curl's `-D` output contains `\r\n`). The file was intact: its byte-exact SHA-256 matched the recorded one before the fix, and all six captures verify after it. No capture was redone. Regression tests cover CR and non-UTF-8 output.

- **2026-09-24, E-007 redacted before its first commit.** A pre-push scan found a host path on line 24 of `raw/E-007.txt` (`/Users/<name>/.../tests/test_decode_zbar.py:50: AssertionError`), which contradicted the header's claim that local paths are normalised. Cause: the container reused bytecode the host had compiled into the bind-mounted `__pycache__`, so the traceback carried the host path, and the normaliser only rewrote the container's own root and home. Change made to the capture: that one line now reads `<repo>/tests/test_decode_zbar.py:50: AssertionError`, one header line records the redaction, and the hash was recomputed. Nothing else in the file changed. Original sha256 `8b0d3e58690964e29420b626d9e36a3224e45cd347942d8d03f5c0d78a50f319`, new sha256 `3353024e45d66ed7fcc9639239f6097d11a07e864c63c05c020118b825018b66`. This is the only raw file edited after capture. The unredacted original was never published: the local commits that briefly held it were rewritten before the first push. Fixes, in the commits that follow: the normaliser scrubs any `/Users/<name>` or `/home/<name>` prefix (tested), and the Docker image sets `PYTHONPYCACHEPREFIX` so it cannot read host bytecode.

- **2026-09-24, E-010 and E-011 were each captured twice.** The first captures cited commits in the local, unpublished history. That history was rewritten before the first push so a host path (the E-007 redaction above) never entered a published commit, which changed those commits' hashes. Both captures were therefore redone at the rewritten commits (E-010 at `92b2f4f`, E-011 at `9204be4`) under the same ids; the first captures were never published and are discarded. E-010's test count rose from 160 to 168 only because the rewritten tip includes tests added after the first capture; E-011's figures were identical. Commits `a6d9470` and earlier keep their hashes, so E-001 to E-009 are unaffected.

- **2026-09-24, E-016 captured twice.** The first attempt used a malformed `docker image inspect` format string (`.Config.Entrypoint` does not exist on this image), so it exited 1 with no output. That capture was never committed; it was discarded and redone under the same id, as with E-010 and E-011.

- **2026-09-25, E-022 to E-025 captured twice.** The first attempt ran the harness with a bare `python` inside `sh -c`, which does not exist on the host (only the virtualenv's interpreter does), so all four exited immediately with nothing but that error. None was committed; they were discarded and redone under the same ids. E-021 succeeded the first time and is unchanged.

## Pending evidence

The green test suite in the container against the final code (E-010). The same probe and tests on the Pi (Track H1), to see whether the measured decoder behaviour holds on the Pi's `libzbar0` build. The Pi bring-up will also add the VLM feasibility numbers and the model digest.
