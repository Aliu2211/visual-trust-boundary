"""Allowlist grammars for the identifiers the testbed's tiers accept (plan.md section 5, control 1).

Defense v0: these are the formats the modelled system would legitimately see, written before any adaptive
attack was, and nothing more. Hardening against adaptive attacks is P6 (decision D7); each change there
gets its own commit with the reason.

Two classic bypasses are ruled out by construction: patterns are matched with `fullmatch` (a `$` anchor
also matches before a trailing newline) and use explicit ASCII classes (`\\d` matches Unicode digits).
"""

import re
from dataclasses import dataclass
from enum import StrEnum


class Use(StrEnum):
    IDENTIFIER = "identifier"  # a badge id, read by Tier 1
    PLATE = "plate"
    TICKET = "ticket"


@dataclass(frozen=True)
class Rule:
    min_len: int
    max_len: int
    charset: frozenset[str]
    pattern: re.Pattern[str]


_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_DIGITS = "0123456789"


def _rule(min_len: int, max_len: int, charset: str, pattern: str) -> Rule:
    return Rule(min_len, max_len, frozenset(charset), re.compile(pattern, re.ASCII))


RULES: dict[Use, Rule] = {
    # 1 to 4 capital letters, a hyphen, 4 to 8 digits: B-000123
    Use.IDENTIFIER: _rule(6, 13, _UPPER + _DIGITS + "-", r"[A-Z]{1,4}-[0-9]{4,8}"),
    # two or three hyphen-separated groups of 1 to 4 capitals or digits: AB-1234-CD
    Use.PLATE: _rule(3, 14, _UPPER + _DIGITS + "-", r"[A-Z0-9]{1,4}-[A-Z0-9]{1,4}(-[A-Z0-9]{1,4})?"),
    # T, an 8-digit date, a hyphen, a 4-digit sequence: T20260924-0001
    Use.TICKET: _rule(14, 14, "T" + _DIGITS + "-", r"T[0-9]{8}-[0-9]{4}"),
}
