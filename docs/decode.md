# Decode stage: policy and measured behaviour

Every measurement here has a raw capture in [evidence/raw/](evidence/raw/) and an entry in [evidence/LOG.md](evidence/LOG.md). They were taken with zbar `libzbar0 0.23.92-7+deb12u1` (Debian Bookworm, the Pi's package source), pyzbar 0.1.9, on synthetic clean renders. They have **not** yet been repeated on the Pi.

## Policy

Implemented in `record_from_symbols` ([decode/capture.py](../decode/capture.py)):

| Decoder returns | `decode_status` | Payload passed on |
|---|---|---|
| no symbol | `no_symbol` | none |
| more than one symbol | `multiple_symbols` | none (fail closed; the decoder's symbol order is not spatial, see below) |
| one symbol, valid UTF-8 (including empty) | `ok` | raw bytes and text |
| one symbol, invalid UTF-8 | `invalid_utf8` | raw bytes only; never repaired |

Only QR and Code 128 are enabled. Other symbologies in an image are ignored (an EAN-13 image returned no symbol in both modes).

## Two decoder modes

| Mode | What zbar does with QR byte-mode data | Use |
|---|---|---|
| `default` | Guesses a text encoding and returns UTF-8. Upstream source tries SJIS, Latin-1, Big5 and UTF-8 with heuristics. | What an unmodified reader does. |
| `raw` | Sets `ZBAR_CFG_BINARY` ("don't convert binary data to text") and returns the symbol's bytes untouched. | Isolates the boundary layer from decoder rewriting; the only mode in which the `encoding` control can see invalid UTF-8. |

`config.yaml` selects the mode (`decode.decoder_mode`, default `default`); every run's `RunMetadata` records it. Code 128 is unaffected by the mode.

## Measured behaviour

From the probe run E-008 (34 cases per mode).

| Input | default mode | raw mode |
|---|---|---|
| ASCII ids, apostrophes, spaces, leading zeros, CR LF TAB ESC | exact | exact |
| NUL bytes (first, middle, last, only NULs) | exact | exact |
| Empty QR payload | one symbol, zero bytes | same |
| Max-capacity ASCII (1000, 2331 at ECC M, 2953 at ECC L) | exact | exact |
| Code 128 (ASCII incl. TAB, LF, NUL, ESC, DEL; 200 chars) | exact | exact |
| UTF-8 `José` (5 bytes) | returned 6 different bytes | exact |
| UTF-8 `李雷` (6 bytes) | returned 9 different bytes | exact |
| UTF-8 `Zoë O'Neil-Smith` (17 bytes) | returned 18 different bytes | exact |
| Invalid UTF-8 `ab\xff\xfe` | returned `ab\xc3\xbf\xc3\xbe` (valid UTF-8, 6 bytes) | exact |
| Latin-1 `caf\xe9` | returned `caf\xc3\xa9` | exact |
| Lone continuation byte `a\x80b` | returned `a\xc2\x80b` | exact |
| All 256 byte values | 384 bytes | exact (256) |
| 2953 pseudo-random bytes (ECC L) | 4426 bytes | exact (2953) |
| Two QR codes in one image | 2 symbols, `RIGHT` before `LEFT` | same |
| EAN-13, blank image | no symbol | same |

Totals: default mode 22 exact, 8 different; raw mode 30 exact, 0 different. The other 4 rows are the same in both modes: the EAN-13 and blank images (no symbol), the two-QR image, and an empty Code 128, which python-barcode cannot render, so it is a renderer limit and not a decoder result.

## What it means for the experiment

1. **The decoder is part of the trust boundary.** In default mode a QR payload's non-ASCII bytes are rewritten by encoding inference before the boundary layer sees them, so validation runs on what zbar chose to output, not on what the code carries.
2. **`invalid_utf8` looks unreachable through the QR path in default mode.** All three invalid inputs came back as valid UTF-8 (visible in E-008), and the test suite asserts the same for the all-256-bytes output (E-010). This is from the probed cases, not a proof for every input. The `encoding` reason (decision D5) can only be exercised in raw mode.
3. **Non-ASCII benign payloads cannot round-trip in default mode** (decision D14's hard cases such as accented names). The decoder corrupts them regardless of any defense, so counting them as boundary false positives would be wrong. Options: ASCII-only benign set in default mode, and non-ASCII cases only in raw runs.
4. **Length changes after decoding.** Default mode returned about 1.5 times the payload length on the pseudo-random and all-bytes cases (4426 for 2953; 384 for 256). The all-bytes result is exactly what doubling each of the 128 bytes at or above 0x80 gives, and the pseudo-random one is consistent with it (not shown byte by byte in E-008). A length limit in the boundary applies to the decoder's output, which can exceed what the code could hold.
5. **Symbol order is not spatial.** With `LEFT` and `RIGHT` side by side, zbar returned `RIGHT` first in both modes, so the fail-closed rule for multiple symbols avoids depending on order.
6. **Build dependence.** All of this is for one zbar build. The test suite pins the measured bytes; if a different build (the Pi's) changes any of them, that is a finding to capture, not a number to update.

## Why default mode rewrites (upstream source, E-009)

`qrdectxt.c` reads `ZBAR_CFG_BINARY` (line 79) and otherwise opens converters for SJIS, Latin-1, Big-5 and UTF-8 (lines 85 to 91; the initial order is set at 188 to 191), which it then reorders with rules such as "if there was data encoded in kanji mode, assume it's SJIS" and "if the text is 8-bit clean, prefer UTF-8 over SJIS". That the two bytes `c3 a9` of `José` came out as one different character is consistent with a Big-5 reading, but which converter ran was not confirmed.

## Decision needed (gate G1)

Which mode(s) do results of record use? Recommendation: **`default` as the primary condition** (it is what an unmodified reader does, and it keeps the decoder's behaviour inside the measurement) with an ASCII-only benign set, **and `raw` as a documented second condition** for Tiers 1 and 2, where runs are deterministic and cheap, so the `encoding` control and the invalid-UTF-8 cases are exercised. Tier 3 would run in `default` only. This doubles the Tier 1 and 2 correctness matrix; it does not change the plan's structure. The alternative, `raw` only, is simpler but measures a decoder configuration few deployments use.

## Reproduce

Inside the dev image (`docker build -t vtb-dev .` then `docker run --rm -v "$PWD":/work vtb-dev`), or on the Pi with `libzbar0` installed:

    python tools/probes/decode_edge_cases.py
    python tools/capture_evidence.py E-0NN -- python tools/probes/decode_edge_cases.py
