"""The decode-time defense layer (plan.md section 5). Control 1, validation, lives here; control 2 (parameterised
calls, no shell, provenance tags) is enforced at each tier's call site; control 3, the gate, arrives with Tier 3.

`check` returns a `Decision`, never raises for hostile input: rejecting it is the normal case here (decision D9).
"""

from contracts import Control, Decision, PayloadRecord, Reason
from defense.grammar import RULES, Use

# Decisions are immutable, so one shared instance per outcome means no allocation per call, which keeps the
# layer's own cost (plan.md P6.2) honest.
_ALLOW = Decision(allow=True, reason_code=Reason.OK, control=Control.VALIDATE)
_REJECT = {
    reason: Decision(allow=False, reason_code=reason, control=Control.VALIDATE)
    for reason in (Reason.ENCODING, Reason.LENGTH, Reason.CHARSET, Reason.GRAMMAR)
}


def check(record: PayloadRecord, use: Use) -> Decision:
    """Validate a delivered record for `use`. Order: encoding, length, charset, grammar, cheapest first, so an
    oversized or hostile payload is refused before any pattern is run on it."""
    if not record.delivered:
        raise ValueError(f"only a delivered record can be checked, got decode_status {record.decode_status.value}")
    text = record.text
    if text is None:  # invalid UTF-8: the boundary sees the strict result and refuses it (decision D5)
        return _REJECT[Reason.ENCODING]
    rule = RULES[use]
    if not rule.min_len <= len(text) <= rule.max_len:
        return _REJECT[Reason.LENGTH]
    if not rule.charset.issuperset(text):
        return _REJECT[Reason.CHARSET]
    if rule.pattern.fullmatch(text) is None:
        return _REJECT[Reason.GRAMMAR]
    return _ALLOW
