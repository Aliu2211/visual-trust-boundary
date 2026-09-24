# Evidence log

Implementation results for the paper, each backed by a raw capture in [raw/](raw/). This file is the ledger; [../../status.md](../../status.md) is the project chronology and is not evidence.

## Rules

1. **Capture first, write second.** Run `python tools/capture_evidence.py E-0NN -- <command>`, then write the entry using numbers copied from the captured file. A raw file records the code commit, whether the working tree was dirty (and which files), platform, Python, package versions, the `libzbar0` package version where there is one, the exact command, the exit code, and a SHA-256 of the file.
2. **Append only.** A raw file is never edited or overwritten. A correction is a new entry that says which one it supersedes. Check integrity with `python tools/capture_evidence.py --verify docs/evidence/raw/E-0NN.txt`. A test also checks that this ledger's hashes match the raw files.
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

## Corrections and tooling notes

- **2026-09-24, commit `3dc1270`:** the first version of `--verify` read files in text mode, which rewrites CRLF line endings, so it reported a false `HASH MISMATCH` for E-002 (curl's `-D` output contains `\r\n`). The file was intact: its byte-exact SHA-256 matched the recorded one before the fix, and all six captures verify after it. No capture was redone. Regression tests cover CR and non-UTF-8 output.

## Pending evidence

Entries to add once real zbar has run (Docker image or the Pi): exact round-trip results for QR and Code 128 (plan P1.2); decoder behaviour on NUL bytes, invalid UTF-8, empty payloads, maximum-capacity codes and multi-symbol images (P1.3). Pi bring-up (Track H) will add the `libzbar0` package version and the VLM feasibility numbers.
