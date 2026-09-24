"""Seeded benign payloads (plan.md D14): badge, plate and ticket shaped ids plus awkward-but-ASCII cases.

Deterministic for a given seed, so the same set can be regenerated on any machine. The full benign
set of at least 1000 items with the hard cases comes in P3; this is the P1 decoder round-trip set.
"""

import random

HARD_ASCII = ("O'BRIEN", "a-b_c.d", "A" * 40, "0012345", "AB-1234-CD")

# QR only: Code 128 carries ASCII. zbar's default mode rewrites these (docs/decode.md).
NON_ASCII = ("José", "李雷", "Zoë O'Neil-Smith")


def benign_ascii(n: int, seed: int = 1337) -> list[str]:
    if n < len(HARD_ASCII):
        raise ValueError(f"n must be at least {len(HARD_ASCII)}, the number of fixed hard cases")
    rng = random.Random(seed)
    out = set(HARD_ASCII)
    while len(out) < n:
        kind = rng.choice("bpt")
        if kind == "b":
            out.add(f"B-{rng.randrange(10**6):06d}")
        elif kind == "p":
            out.add(f"{rng.choice('ABCDEFGH')}{rng.choice('ABCDEFGH')}-{rng.randrange(10**4):04d}")
        else:
            out.add(f"T20260924-{rng.randrange(10**4):04d}")
    return sorted(out)
