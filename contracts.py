"""Data contracts for the VTB testbed (plan.md section 2; decisions D5 to D9, D12, D13).

Everything that crosses a module boundary is defined here, so the decoder, the
tiers, the defense and the harness can be built and tested independently.
Invariants are enforced at construction: a row that breaks one is a bug in
whatever produced it, not something the analysis code should tolerate.
Semantics of the verdicts live in docs/oracles.md.
"""

import base64
import binascii
import re
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TierId(StrEnum):
    TIER1 = "tier1"
    TIER2 = "tier2"
    TIER3 = "tier3"


class Mode(StrEnum):
    OFF = "off"
    VALIDATE_ONLY = "validate_only"
    PARAMETERISE_ONLY = "parameterise_only"
    GATE_ONLY = "gate_only"
    FULL = "full"


class Family(StrEnum):
    MALFORMED = "malformed"
    INJECTION = "injection"
    BACKEND_PARSE = "backend_parse"
    INSTRUCTION = "instruction"
    BENIGN = "benign"


class Subset(StrEnum):
    NAIVE = "naive"
    ADAPTIVE = "adaptive"
    HELDOUT = "heldout"
    BENIGN = "benign"


class Symbology(StrEnum):
    QR = "qr"
    CODE128 = "code128"


class DecodeStatus(StrEnum):
    OK = "ok"
    INVALID_UTF8 = "invalid_utf8"
    NO_SYMBOL = "no_symbol"
    MULTIPLE_SYMBOLS = "multiple_symbols"


class Control(StrEnum):
    VALIDATE = "validate"
    GATE = "gate"


class Reason(StrEnum):
    OK = "ok"
    LENGTH = "length"
    CHARSET = "charset"
    GRAMMAR = "grammar"
    ENCODING = "encoding"
    UNAPPROVED = "unapproved"


class Verdict(StrEnum):
    NOT_DELIVERED = "not_delivered"
    CROSSED = "crossed"
    BLOCKED = "blocked"
    NO_EFFECT = "no_effect"
    FAULT = "fault"
    BENIGN_OK = "benign_ok"


# Modes each tier supports (D8). `full` means every control that applies to the
# tier: validate + parameterise for tiers 1 and 2; provenance separation + gate
# (+ validate) for tier 3.
VALID_MODES: dict[TierId, frozenset[Mode]] = {
    TierId.TIER1: frozenset({Mode.OFF, Mode.VALIDATE_ONLY, Mode.PARAMETERISE_ONLY, Mode.FULL}),
    TierId.TIER2: frozenset({Mode.OFF, Mode.VALIDATE_ONLY, Mode.PARAMETERISE_ONLY, Mode.FULL}),
    TierId.TIER3: frozenset({Mode.OFF, Mode.GATE_ONLY, Mode.FULL}),
}
_VALIDATING_MODES = frozenset({Mode.VALIDATE_ONLY, Mode.FULL})
_GATING_MODES = frozenset({Mode.GATE_ONLY, Mode.FULL})

# The (family, tier) pairs the experiment runs (docs/oracles.md section 3).
APPLICABLE_PAIRS: frozenset[tuple[Family, TierId]] = frozenset(
    {(Family.MALFORMED, t) for t in TierId}
    | {(Family.BENIGN, t) for t in TierId}
    | {
        (Family.INJECTION, TierId.TIER1),
        (Family.BACKEND_PARSE, TierId.TIER2),
        (Family.INSTRUCTION, TierId.TIER3),
    }
)

# A tier is invoked only for these decode outcomes; the rest fail closed.
DELIVERED_STATUSES = frozenset({DecodeStatus.OK, DecodeStatus.INVALID_UTF8})

_BENIGN_VERDICTS = frozenset(
    {Verdict.BENIGN_OK, Verdict.BLOCKED, Verdict.NOT_DELIVERED, Verdict.FAULT}
)
_ATTACK_VERDICTS = frozenset(
    {Verdict.CROSSED, Verdict.BLOCKED, Verdict.NO_EFFECT, Verdict.NOT_DELIVERED, Verdict.FAULT}
)

# Payload ids become file names and canary names, so no separators, dots or uppercase.
_ID_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,62}$"
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class _Yaml12Loader(yaml.SafeLoader):
    """SafeLoader where only true/false are booleans, as in YAML 1.2.

    PyYAML follows YAML 1.1, where an unquoted `off`, `on`, `no` or `yes` becomes
    a boolean. `off` is a mode name and payload text can be any word, so those
    must stay strings.
    """


_Yaml12Loader.yaml_implicit_resolvers = {
    first_char: [(tag, rx) for tag, rx in resolvers if tag != "tag:yaml.org,2002:bool"]
    for first_char, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_Yaml12Loader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF")
)


def read_yaml(path: Path | str) -> object:
    """Parse a YAML file with the repo's loader. Use this, not yaml.safe_load."""
    with open(path, encoding="utf-8") as fh:
        return yaml.load(fh, Loader=_Yaml12Loader)  # noqa: S506 (subclass of SafeLoader)


def _b64decode(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("not valid base64") from exc


def _is_utf8(data: bytes) -> bool:
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


# --- attack set ---------------------------------------------------------------


class PayloadSpec(_Frozen):
    """One row of attacks/payloads.yaml: what to render into a code, and how to judge it.

    Content is either text or base64 bytes, because YAML text cannot carry NUL
    bytes or invalid UTF-8. `oracle_ref` names the oracle parameter set (for
    tier 3, the scenario) in the harness ground truth.
    """

    id: str = Field(pattern=_ID_PATTERN)
    family: Family
    subset: Subset
    target_tiers: tuple[TierId, ...] = Field(min_length=1)
    symbology: Symbology
    content_text: str | None = None
    content_b64: str | None = None
    oracle_ref: str = Field(min_length=1)
    seed: int
    expected_decode: Literal["ok", "fail"]
    notes: str = ""

    @model_validator(mode="after")
    def _check_spec(self) -> "PayloadSpec":
        if (self.content_text is None) == (self.content_b64 is None):
            raise ValueError("exactly one of content_text and content_b64 is required")
        if self.content_b64 is not None:
            _b64decode(self.content_b64)
        if (self.family is Family.BENIGN) != (self.subset is Subset.BENIGN):
            raise ValueError("family 'benign' and subset 'benign' go together")
        if len(set(self.target_tiers)) != len(self.target_tiers):
            raise ValueError("target_tiers has duplicates")
        for tier in self.target_tiers:
            if (self.family, tier) not in APPLICABLE_PAIRS:
                raise ValueError(f"family {self.family.value} is not run against {tier.value}")
        return self

    @property
    def content_bytes(self) -> bytes:
        if self.content_text is not None:
            return self.content_text.encode("utf-8")
        return _b64decode(self.content_b64 or "")


class PayloadFile(_Frozen):
    payloads: tuple[PayloadSpec, ...]

    @field_validator("payloads")
    @classmethod
    def _unique_ids(cls, specs: tuple[PayloadSpec, ...]) -> tuple[PayloadSpec, ...]:
        ids = [s.id for s in specs]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate payload ids: {dupes}")
        return specs


def load_payload_specs(path: Path | str) -> list[PayloadSpec]:
    return list(PayloadFile.model_validate(read_yaml(path)).payloads)


# --- decode stage output ------------------------------------------------------


class PayloadRecord(_Frozen):
    """What the decoder emits, and the only thing a tier ever sees (D5).

    Raw bytes are kept alongside the strict-UTF-8 text so the boundary layer,
    not the decoder, decides what to do with bad encodings. `payload_id` is set
    in replay mode (derived from the file name) and null for live frames.
    """

    run_id: str = Field(min_length=1)
    payload_id: str | None = Field(default=None, pattern=_ID_PATTERN)
    raw_bytes_b64: str | None = None
    text: str | None = None
    decode_status: DecodeStatus
    symbology: str | None = None
    source_image: str
    image_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    t_capture: float
    t_decode_ns: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_record(self) -> "PayloadRecord":
        raw = _b64decode(self.raw_bytes_b64) if self.raw_bytes_b64 is not None else None
        if self.decode_status is DecodeStatus.OK:
            if raw is None or self.text is None or self.symbology is None:
                raise ValueError("status ok needs raw bytes, text and symbology")
            if not _is_utf8(raw) or raw.decode("utf-8") != self.text:
                raise ValueError("status ok but text is not the strict UTF-8 decoding of the raw bytes")
        elif self.decode_status is DecodeStatus.INVALID_UTF8:
            if raw is None or self.symbology is None:
                raise ValueError("status invalid_utf8 needs raw bytes and symbology")
            if self.text is not None:
                raise ValueError("status invalid_utf8 must not carry text")
            if _is_utf8(raw):
                raise ValueError("status invalid_utf8 but the raw bytes are valid UTF-8")
        elif raw is not None or self.text is not None or self.symbology is not None:
            raise ValueError(f"status {self.decode_status.value} carries no payload")
        return self

    @property
    def raw_bytes(self) -> bytes | None:
        return None if self.raw_bytes_b64 is None else _b64decode(self.raw_bytes_b64)

    @property
    def delivered(self) -> bool:
        return self.decode_status in DELIVERED_STATUSES


# --- defense output -----------------------------------------------------------


class Decision(_Frozen):
    """Result of a defense control. Rejection is the normal case here, so it is a value, not an exception (D9)."""

    allow: bool
    reason_code: Reason
    control: Control

    @model_validator(mode="after")
    def _check_decision(self) -> "Decision":
        if self.allow != (self.reason_code is Reason.OK):
            raise ValueError("allow is true exactly when reason_code is ok")
        if self.control is Control.GATE and self.reason_code not in {Reason.OK, Reason.UNAPPROVED}:
            raise ValueError("the gate can only reject as unapproved")
        if self.control is Control.VALIDATE and self.reason_code is Reason.UNAPPROVED:
            raise ValueError("the validator cannot reject as unapproved")
        return self


# --- tier output and result rows ---------------------------------------------


class TierOutcome(_Frozen):
    """What a tier reports about one call. It never says whether the payload crossed; the harness oracle does."""

    tier: TierId
    mode: Mode
    payload_id: str = Field(pattern=_ID_PATTERN)
    rep: int = Field(ge=0)
    blocked: bool = False  # the validator refused the input
    gated: bool = False  # the gate refused the action
    error: str | None = Field(default=None, max_length=128)
    handle_ns: int | None = Field(default=None, ge=0)
    defense_ns: int | None = Field(default=None, ge=0)  # null when no defense ran
    detail: str = Field(default="", max_length=256)

    @model_validator(mode="after")
    def _check_outcome(self) -> "TierOutcome":
        if self.mode not in VALID_MODES[self.tier]:
            raise ValueError(f"mode {self.mode.value} is not valid for {self.tier.value}")
        if self.blocked and self.gated:
            raise ValueError("blocked and gated are exclusive: the first control to refuse stops the call")
        if self.blocked and self.mode not in _VALIDATING_MODES:
            raise ValueError(f"mode {self.mode.value} has no validation, so it cannot block")
        if self.gated and (self.mode not in _GATING_MODES or self.tier is not TierId.TIER3):
            raise ValueError("only tier 3 in a gating mode can gate")
        if self.error is not None and (self.blocked or self.gated):
            raise ValueError("a call that errored cannot also be blocked or gated")
        return self


class ResultRow(TierOutcome):
    """One CSV row: a tier outcome, the ground-truth labels, and the harness verdict.

    Run-level metadata lives once per run in RunMetadata, keyed by `run_id`.
    Every field is a scalar so the row is CSV-safe.
    """

    run_id: str = Field(min_length=1)
    family: Family
    subset: Subset
    decode_status: DecodeStatus
    verdict: Verdict

    @model_validator(mode="after")
    def _check_row(self) -> "ResultRow":
        if (self.family, self.tier) not in APPLICABLE_PAIRS:
            raise ValueError(f"family {self.family.value} is not run against {self.tier.value}")
        delivered = self.decode_status in DELIVERED_STATUSES
        if (self.verdict is Verdict.NOT_DELIVERED) == delivered:
            raise ValueError("verdict not_delivered must match an undelivered decode_status")
        allowed = _BENIGN_VERDICTS if self.family is Family.BENIGN else _ATTACK_VERDICTS
        if self.verdict not in allowed:
            raise ValueError(f"verdict {self.verdict.value} is not valid for family {self.family.value}")
        refused = self.blocked or self.gated
        if self.verdict is Verdict.NOT_DELIVERED and (
            refused or self.error is not None or self.handle_ns is not None or self.defense_ns is not None
        ):
            raise ValueError("a not_delivered row means the tier was not invoked")
        if self.verdict is Verdict.BLOCKED and not refused:
            raise ValueError("verdict blocked needs the blocked or gated flag")
        if refused and self.verdict not in {Verdict.BLOCKED, Verdict.CROSSED}:
            raise ValueError("a refused call can only be blocked, or crossed if the oracle fired anyway")
        if self.error is not None and self.verdict not in {Verdict.FAULT, Verdict.CROSSED}:
            raise ValueError("a call that errored can only be a fault, or crossed if the oracle fired anyway")
        return self

    @property
    def crossed(self) -> bool:
        return self.verdict is Verdict.CROSSED


@runtime_checkable
class Tier(Protocol):
    """A tier handler. It sees only the record, never the labels (docs/oracles.md principle 1)."""

    tier_id: TierId

    def handle(self, record: PayloadRecord, mode: Mode, rep: int) -> TierOutcome: ...


class RunMetadata(_Frozen):
    """Reproducibility record, written once per run next to the CSV (D13). Null where a field does not apply, such as Pi-only readings on a laptop."""

    run_id: str = Field(min_length=1)
    started_at: datetime
    git_sha: str = Field(pattern=r"^[0-9a-f]{7,40}$")
    git_dirty: bool
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    host_label: str = Field(min_length=1)
    os: str
    kernel: str
    python: str
    requirements_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    zbar_version: str | None = None
    ollama_version: str | None = None
    model_digest: str | None = None
    cpu_temp_c_start: float | None = None
    cpu_temp_c_end: float | None = None
    throttled_start: str | None = Field(default=None, pattern=r"^0x[0-9a-f]+$")
    throttled_end: str | None = Field(default=None, pattern=r"^0x[0-9a-f]+$")


# --- run configuration --------------------------------------------------------


class TierConfig(_Frozen):
    enabled: bool = True
    modes: tuple[Mode, ...] = Field(min_length=1)
    host: str = "127.0.0.1"
    port: int | None = Field(default=None, ge=1024, le=65535)

    @field_validator("host")
    @classmethod
    def _loopback_only(cls, host: str) -> str:
        if host not in _LOOPBACK_HOSTS:
            raise ValueError("services must bind to loopback only (D12)")
        return host

    @field_validator("modes")
    @classmethod
    def _unique_modes(cls, modes: tuple[Mode, ...]) -> tuple[Mode, ...]:
        if len(set(modes)) != len(modes):
            raise ValueError("modes has duplicates")
        return modes


class ModelConfig(_Frozen):
    name: str = Field(min_length=1)
    digest: str | None = Field(default=None, min_length=12)  # exact Ollama digest format confirmed in H3
    temperature: float = Field(default=0.0, ge=0.0)


class RepsConfig(_Frozen):
    """Proposed repetition counts (plan.md P7.1); tune after the H3 spike."""

    correctness: int = Field(default=1, ge=1)
    timing: int = Field(default=30, ge=1)
    tier3: int = Field(default=10, ge=1)


class DecodeConfig(_Frozen):
    source: Literal["replay", "live"]
    image_dir: str = Field(min_length=1)


class PathsConfig(_Frozen):
    canary_dir: str = Field(min_length=1)
    results_dir: str = Field(min_length=1)


class Config(_Frozen):
    seed: int
    decode: DecodeConfig
    tiers: dict[TierId, TierConfig]
    model: ModelConfig
    reps: RepsConfig = RepsConfig()
    paths: PathsConfig

    @model_validator(mode="after")
    def _check_config(self) -> "Config":
        missing = set(TierId) - set(self.tiers)
        if missing:
            raise ValueError(f"tiers missing: {sorted(t.value for t in missing)}")
        for tier_id, tier in self.tiers.items():
            bad = [m.value for m in tier.modes if m not in VALID_MODES[tier_id]]
            if bad:
                raise ValueError(f"{tier_id.value}: modes {bad} are not valid for this tier")
            if tier.enabled and tier_id is not TierId.TIER1 and tier.port is None:
                raise ValueError(f"{tier_id.value}: an enabled service tier needs a port")
        if self.tiers[TierId.TIER3].enabled and self.model.digest is None:
            raise ValueError("tier3 is enabled: pin the model by digest (D3, D13)")
        return self


def load_config(path: Path | str) -> Config:
    return Config.model_validate(read_yaml(path))
