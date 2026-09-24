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

## Corrections and tooling notes

- **2026-09-24, commit `3dc1270`:** the first version of `--verify` read files in text mode, which rewrites CRLF line endings, so it reported a false `HASH MISMATCH` for E-002 (curl's `-D` output contains `\r\n`). The file was intact: its byte-exact SHA-256 matched the recorded one before the fix, and all six captures verify after it. No capture was redone. Regression tests cover CR and non-UTF-8 output.

- **2026-09-24, E-007 redacted before its first commit.** A pre-push scan found a host path on line 24 of `raw/E-007.txt` (`/Users/<name>/.../tests/test_decode_zbar.py:50: AssertionError`), which contradicted the header's claim that local paths are normalised. Cause: the container reused bytecode the host had compiled into the bind-mounted `__pycache__`, so the traceback carried the host path, and the normaliser only rewrote the container's own root and home. Change made to the capture: that one line now reads `<repo>/tests/test_decode_zbar.py:50: AssertionError`, one header line records the redaction, and the hash was recomputed. Nothing else in the file changed. Original sha256 `8b0d3e58690964e29420b626d9e36a3224e45cd347942d8d03f5c0d78a50f319`, new sha256 `3353024e45d66ed7fcc9639239f6097d11a07e864c63c05c020118b825018b66`. This is the only raw file edited after capture. The unredacted original was never published: the local commits that briefly held it were rewritten before the first push. Fixes, in the commits that follow: the normaliser scrubs any `/Users/<name>` or `/home/<name>` prefix (tested), and the Docker image sets `PYTHONPYCACHEPREFIX` so it cannot read host bytecode.

- **2026-09-24, E-010 and E-011 were each captured twice.** The first captures cited commits in the local, unpublished history. That history was rewritten before the first push so a host path (the E-007 redaction above) never entered a published commit, which changed those commits' hashes. Both captures were therefore redone at the rewritten commits (E-010 at `92b2f4f`, E-011 at `9204be4`) under the same ids; the first captures were never published and are discarded. E-010's test count rose from 160 to 168 only because the rewritten tip includes tests added after the first capture; E-011's figures were identical. Commits `a6d9470` and earlier keep their hashes, so E-001 to E-009 are unaffected.

## Pending evidence

The green test suite in the container against the final code (E-010). The same probe and tests on the Pi (Track H1), to see whether the measured decoder behaviour holds on the Pi's `libzbar0` build. The Pi bring-up will also add the VLM feasibility numbers and the model digest.
