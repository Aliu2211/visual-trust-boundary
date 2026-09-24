import base64
import random

import pytest

from contracts import Control, DecodeStatus, PayloadRecord, Reason
from defense.boundary import check
from defense.grammar import RULES, Use

SHA = "a" * 64


def rec(text: str | None = None, *, raw: bytes | None = None, status: str = "ok") -> PayloadRecord:
    if status == "ok":
        raw = text.encode("utf-8")
        return PayloadRecord(run_id="r", payload_id="p", raw_bytes_b64=base64.b64encode(raw).decode(), text=text,
                             decode_status="ok", symbology="QRCODE", source_image="p.png", image_sha256=SHA,
                             t_capture=0.0, t_decode_ns=1)
    if status == "invalid_utf8":
        return PayloadRecord(run_id="r", payload_id="p", raw_bytes_b64=base64.b64encode(raw).decode(), text=None,
                             decode_status="invalid_utf8", symbology="QRCODE", source_image="p.png", image_sha256=SHA,
                             t_capture=0.0, t_decode_ns=1)
    return PayloadRecord(run_id="r", payload_id="p", decode_status=status, source_image="p.png", image_sha256=SHA,
                         t_capture=0.0, t_decode_ns=1)


def reason(text, use=Use.IDENTIFIER) -> Reason:
    return check(rec(text), use).reason_code


# --- accepted -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["B-000123", "A-0000", "B-00012", "ABCD-12345678", "STAF-0001", "R-000000"])
def test_identifiers_of_the_legitimate_shape_are_accepted(text):
    d = check(rec(text), Use.IDENTIFIER)
    assert d.allow and d.reason_code is Reason.OK and d.control is Control.VALIDATE


@pytest.mark.parametrize("text", ["AB-1234-CD", "A-B", "AAAA-BBBB-CCCC", "12-345"])
def test_plates_of_the_legitimate_shape_are_accepted(text):
    assert check(rec(text), Use.PLATE).allow


@pytest.mark.parametrize("text", ["T20260924-0001", "T00000000-9999"])
def test_tickets_of_the_legitimate_shape_are_accepted(text):
    assert check(rec(text), Use.TICKET).allow


# --- rejected, with the right reason ------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["B-1", "", "B-123", "ABCD-123456789", "A" * 3000])
def test_wrong_length_is_refused_as_length(text):
    assert reason(text) is Reason.LENGTH


@pytest.mark.parametrize(
    "text",
    [
        "b-000123",             # lowercase
        "B-000123\n",           # a trailing newline: `$` would allow it, fullmatch plus the charset do not
        "B-000123 ",            # space
        "B-0001'3",             # quote
        "B-0001;3",             # semicolon
        "B-00\x0013",           # NUL
        "B-000١٢٣",  # Arabic-Indic digits, which `\\d` would accept
        "B-００１２３",  # fullwidth digits
        "B‑000123",        # a non-breaking hyphen that looks like '-'
    ],
)
def test_characters_outside_the_allowlist_are_refused_as_charset(text):
    assert reason(text) is Reason.CHARSET


@pytest.mark.parametrize("text", ["BB-00-000", "0-000123", "-B-00012", "B--00012", "B-B-0001", "B0-00123", "ABCDE-000123", "B-" + "0" * 9])
def test_right_characters_in_the_wrong_shape_are_refused_as_grammar(text):
    assert reason(text) is Reason.GRAMMAR


def test_invalid_utf8_is_refused_as_encoding():
    assert check(rec(raw=b"B-00\xff\xfe", status="invalid_utf8"), Use.IDENTIFIER).reason_code is Reason.ENCODING


def test_checks_run_cheapest_first():
    # 40 apostrophes violate length and charset; length is reported, so no pattern ever runs on a long string.
    assert reason("'" * 40) is Reason.LENGTH
    # A short string with a bad character and a bad shape is a charset failure, not a grammar one.
    assert reason("b-1'23") is Reason.CHARSET


def test_a_record_that_was_never_delivered_cannot_be_checked():
    for status in ("no_symbol", "multiple_symbols"):
        with pytest.raises(ValueError, match="delivered"):
            check(rec(status=status), Use.IDENTIFIER)


# --- injection strings from the plan's attack families -----------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["' OR '1'='1", "B-000123' OR '1'='1", "x'; touch /canary/inj-001; echo '", "; $(id)", "`id`", "../../etc/passwd",
     "B-000123; drop table badges", "B-000123\n; id", "\" OR \"\"=\"", "%s%s%s%n", "{{7*7}}", "${IFS}"],
)
def test_injection_shaped_strings_are_all_refused(text):
    assert not check(rec(text), Use.IDENTIFIER).allow


# --- properties ---------------------------------------------------------------------------------------------

_DANGEROUS = set("'\";`$&|<>\\/ \t\r\n\x00*?(){}[]!#%=+,:@^~.")


_VALID = {
    Use.IDENTIFIER: ["B-000123", "A-0000", "ABCD-12345678", "R-000000"],
    Use.PLATE: ["AB-1234-CD", "A-B", "AAAA-BBBB-CCCC"],
    Use.TICKET: ["T20260924-0001", "T00000000-9999"],
}


def mutate(rng: random.Random, text: str, alphabet: str) -> str:
    chars = list(text)
    for _ in range(rng.randint(0, 3)):
        op = rng.choice("ird")
        pos = rng.randrange(len(chars) + 1) if op == "i" else (rng.randrange(len(chars)) if chars else 0)
        if op == "i":
            chars.insert(pos, rng.choice(alphabet))
        elif op == "r" and chars:
            chars[pos] = rng.choice(alphabet)
        elif op == "d" and chars:
            del chars[pos]
    return "".join(chars)


@pytest.mark.parametrize("use", list(Use))
def test_anything_accepted_contains_only_the_allowlisted_characters(use):
    rule = RULES[use]
    rng = random.Random(20260924)
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-T'; /$`\n\x00b\uff10"
    accepted = refused = 0
    for _ in range(4000):
        text = mutate(rng, rng.choice(_VALID[use]), alphabet)
        if check(rec(text), use).allow:
            accepted += 1
            assert set(text) <= rule.charset and not (set(text) & _DANGEROUS), repr(text)
            assert rule.pattern.fullmatch(text) and rule.min_len <= len(text) <= rule.max_len
        else:
            refused += 1
    # A property test that only ever accepts, or only ever refuses, proves nothing.
    assert accepted > 100 and refused > 100, (accepted, refused)


def test_decisions_are_shared_immutable_instances():
    assert check(rec("B-000123"), Use.IDENTIFIER) is check(rec("B-000456"), Use.IDENTIFIER)
    assert reason("bad") is Reason.LENGTH
    d = check(rec("bad"), Use.IDENTIFIER)
    with pytest.raises(Exception):
        d.allow = True  # frozen: sharing an instance is safe


def test_every_use_has_a_rule_and_the_bounds_are_consistent():
    assert set(RULES) == set(Use)
    for rule in RULES.values():
        assert 0 < rule.min_len <= rule.max_len <= 64
    assert DecodeStatus.INVALID_UTF8.value == "invalid_utf8"
