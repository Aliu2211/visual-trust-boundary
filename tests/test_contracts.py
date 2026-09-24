import base64
import re
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from contracts import (
    APPLICABLE_PAIRS,
    VALID_MODES,
    Config,
    Control,
    DecodeStatus,
    Decision,
    Family,
    Mode,
    PayloadRecord,
    PayloadSpec,
    Reason,
    ResultRow,
    RunMetadata,
    Subset,
    Tier,
    TierId,
    TierOutcome,
    Verdict,
    load_config,
    load_payload_specs,
    read_yaml,
)

ROOT = Path(__file__).resolve().parent.parent
SHA = "a" * 64


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def spec(**over):
    base = dict(
        id="inj-001",
        family="injection",
        subset="naive",
        target_tiers=["tier1"],
        symbology="qr",
        content_text="' OR '1'='1",
        oracle_ref="t1.default",
        seed=1,
        expected_decode="ok",
    )
    base.update(over)
    return base


def record(**over):
    base = dict(
        run_id="run-1",
        payload_id="inj-001",
        raw_bytes_b64=b64(b"BADGE-1"),
        text="BADGE-1",
        decode_status="ok",
        symbology="QRCODE",
        source_image="attacks/out/inj-001.png",
        image_sha256=SHA,
        t_capture=1.0,
        t_decode_ns=1000,
    )
    base.update(over)
    return base


def row(**over):
    base = dict(
        tier="tier1",
        mode="off",
        payload_id="inj-001",
        rep=0,
        run_id="run-1",
        family="injection",
        subset="naive",
        decode_status="ok",
        verdict="crossed",
        handle_ns=5000,
    )
    base.update(over)
    return base


def config_dict(**over):
    base = read_yaml(ROOT / "config.yaml")
    base.update(over)
    return base


# --- YAML loader ---------------------------------------------------------------


def test_yaml_keeps_yaml11_boolean_words_as_strings(tmp_path):
    f = tmp_path / "x.yaml"
    f.write_text("words: [off, on, no, yes, Off, NO]\nflags: [true, false, True, FALSE]\n")
    doc = read_yaml(f)
    assert doc["words"] == ["off", "on", "no", "yes", "Off", "NO"]
    assert doc["flags"] == [True, False, True, False]


def test_unquoted_off_is_a_valid_mode_in_config(tmp_path):
    f = tmp_path / "config.yaml"
    f.write_text((ROOT / "config.yaml").read_text())
    assert Mode.OFF in load_config(f).tiers[TierId.TIER1].modes


def test_payload_text_that_looks_like_a_yaml11_boolean_survives(tmp_path):
    f = tmp_path / "payloads.yaml"
    rows = "".join(
        f"  - {{id: w-{i}, family: malformed, subset: naive, target_tiers: [tier1], symbology: qr,"
        f" content_text: {word}, oracle_ref: t1.default, seed: 1, expected_decode: ok}}\n"
        for i, word in enumerate(["no", "off", "yes", "on"])
    )
    f.write_text("payloads:\n" + rows)
    assert [s.content_text for s in load_payload_specs(f)] == ["no", "off", "yes", "on"]


# --- PayloadSpec ---------------------------------------------------------------


def test_spec_accepts_text_content():
    assert PayloadSpec(**spec()).content_bytes == b"' OR '1'='1"


def test_spec_carries_bytes_that_yaml_text_cannot():
    raw = b"a\x00\xff\xfe"
    s = PayloadSpec(**spec(family="malformed", content_text=None, content_b64=b64(raw)))
    assert s.content_bytes == raw


@pytest.mark.parametrize("content", [dict(content_b64=b64(b"x")), dict(content_text=None)])
def test_spec_needs_exactly_one_content_field(content):
    with pytest.raises(ValidationError, match="exactly one"):
        PayloadSpec(**spec(**content))


def test_spec_rejects_bad_base64():
    with pytest.raises(ValidationError, match="base64"):
        PayloadSpec(**spec(content_text=None, content_b64="not base64!"))


@pytest.mark.parametrize("bad_id", ["../x", "A", "a/b", "", "a b", "a.b", "x" * 64, "-lead"])
def test_spec_id_must_be_filename_safe(bad_id):
    with pytest.raises(ValidationError):
        PayloadSpec(**spec(id=bad_id))


def test_spec_pairs_benign_family_with_benign_subset():
    with pytest.raises(ValidationError, match="go together"):
        PayloadSpec(**spec(family="benign", subset="naive"))
    with pytest.raises(ValidationError, match="go together"):
        PayloadSpec(**spec(family="injection", subset="benign"))


def test_spec_rejects_pair_outside_the_matrix():
    with pytest.raises(ValidationError, match="not run against"):
        PayloadSpec(**spec(target_tiers=["tier2"]))  # injection is Tier 1 only


def test_spec_rejects_duplicate_and_empty_tiers():
    with pytest.raises(ValidationError, match="duplicates"):
        PayloadSpec(**spec(family="malformed", target_tiers=["tier1", "tier1"]))
    with pytest.raises(ValidationError):
        PayloadSpec(**spec(target_tiers=[]))


def test_spec_forbids_unknown_fields():
    with pytest.raises(ValidationError):
        PayloadSpec(**spec(famly="injection"))


def test_payload_file_rejects_duplicate_ids(tmp_path):
    f = tmp_path / "payloads.yaml"
    f.write_text(yaml.safe_dump({"payloads": [spec(), spec()]}))
    with pytest.raises(ValidationError, match="duplicate payload ids"):
        load_payload_specs(f)


def test_payload_file_loads(tmp_path):
    f = tmp_path / "payloads.yaml"
    f.write_text(yaml.safe_dump({"payloads": [spec(), spec(id="inj-002")]}))
    assert [s.id for s in load_payload_specs(f)] == ["inj-001", "inj-002"]


# --- PayloadRecord -------------------------------------------------------------


def test_record_ok_is_delivered():
    r = PayloadRecord(**record())
    assert r.delivered and r.raw_bytes == b"BADGE-1"


def test_record_ok_text_must_match_raw_bytes():
    with pytest.raises(ValidationError, match="strict UTF-8"):
        PayloadRecord(**record(text="BADGE-2"))


def test_record_invalid_utf8_keeps_raw_bytes_and_no_text():
    r = PayloadRecord(**record(raw_bytes_b64=b64(b"\xff\xfe"), text=None, decode_status="invalid_utf8"))
    assert r.delivered and r.text is None


def test_record_invalid_utf8_must_actually_be_invalid():
    with pytest.raises(ValidationError, match="valid UTF-8"):
        PayloadRecord(**record(decode_status="invalid_utf8", text=None))


def test_record_invalid_utf8_must_not_carry_text():
    with pytest.raises(ValidationError, match="must not carry text"):
        PayloadRecord(**record(raw_bytes_b64=b64(b"\xff"), decode_status="invalid_utf8"))


@pytest.mark.parametrize("status", ["no_symbol", "multiple_symbols"])
def test_record_undelivered_statuses_carry_no_payload(status):
    empty = dict(raw_bytes_b64=None, text=None, symbology=None, decode_status=status)
    assert not PayloadRecord(**record(**empty)).delivered
    with pytest.raises(ValidationError, match="carries no payload"):
        PayloadRecord(**record(decode_status=status))


def test_record_rejects_bad_hash_and_bad_base64():
    with pytest.raises(ValidationError):
        PayloadRecord(**record(image_sha256="xyz"))
    with pytest.raises(ValidationError, match="base64"):
        PayloadRecord(**record(raw_bytes_b64="%%%"))


def test_record_allows_empty_payload():
    r = PayloadRecord(**record(raw_bytes_b64=b64(b""), text=""))
    assert r.delivered and r.raw_bytes == b""


# --- Decision ------------------------------------------------------------------


def test_decision_allow_iff_reason_ok():
    assert Decision(allow=True, reason_code=Reason.OK, control=Control.VALIDATE).allow
    with pytest.raises(ValidationError, match="exactly when"):
        Decision(allow=True, reason_code=Reason.LENGTH, control=Control.VALIDATE)
    with pytest.raises(ValidationError, match="exactly when"):
        Decision(allow=False, reason_code=Reason.OK, control=Control.VALIDATE)


def test_decision_reasons_match_the_control():
    Decision(allow=False, reason_code=Reason.UNAPPROVED, control=Control.GATE)
    with pytest.raises(ValidationError, match="only reject as unapproved"):
        Decision(allow=False, reason_code=Reason.GRAMMAR, control=Control.GATE)
    with pytest.raises(ValidationError, match="cannot reject as unapproved"):
        Decision(allow=False, reason_code=Reason.UNAPPROVED, control=Control.VALIDATE)


# --- TierOutcome ---------------------------------------------------------------


def outcome(**over):
    base = dict(tier="tier1", mode="off", payload_id="inj-001", rep=0)
    base.update(over)
    return base


def test_outcome_rejects_mode_invalid_for_tier():
    with pytest.raises(ValidationError, match="not valid for tier3"):
        TierOutcome(**outcome(tier="tier3", mode="parameterise_only"))
    with pytest.raises(ValidationError, match="not valid for tier1"):
        TierOutcome(**outcome(mode="gate_only"))


def test_outcome_block_needs_a_validating_mode():
    TierOutcome(**outcome(mode="validate_only", blocked=True))
    TierOutcome(**outcome(mode="full", blocked=True))
    for mode in ("off", "parameterise_only"):
        with pytest.raises(ValidationError, match="cannot block"):
            TierOutcome(**outcome(mode=mode, blocked=True))


def test_outcome_gate_is_tier3_only_and_needs_a_gating_mode():
    TierOutcome(**outcome(tier="tier3", mode="gate_only", gated=True))
    with pytest.raises(ValidationError, match="only tier 3"):
        TierOutcome(**outcome(mode="full", gated=True))
    with pytest.raises(ValidationError, match="only tier 3"):
        TierOutcome(**outcome(tier="tier3", mode="off", gated=True))


def test_outcome_blocked_and_gated_are_exclusive():
    with pytest.raises(ValidationError, match="exclusive"):
        TierOutcome(**outcome(tier="tier3", mode="full", blocked=True, gated=True))


def test_outcome_error_excludes_refusal():
    with pytest.raises(ValidationError, match="errored"):
        TierOutcome(**outcome(mode="full", blocked=True, error="TimeoutError"))


def test_outcome_bounds_free_text_and_timings():
    with pytest.raises(ValidationError):
        TierOutcome(**outcome(detail="x" * 257))
    with pytest.raises(ValidationError):
        TierOutcome(**outcome(handle_ns=-1))


# --- ResultRow -----------------------------------------------------------------


def test_row_crossed_property():
    assert ResultRow(**row()).crossed
    assert not ResultRow(**row(verdict="no_effect")).crossed


def test_row_verdict_must_fit_the_family():
    with pytest.raises(ValidationError, match="not valid for family benign"):
        ResultRow(**row(family="benign", subset="benign", verdict="crossed"))
    with pytest.raises(ValidationError, match="not valid for family injection"):
        ResultRow(**row(verdict="benign_ok"))


def test_row_pair_must_be_in_the_matrix():
    with pytest.raises(ValidationError, match="not run against"):
        ResultRow(**row(tier="tier2", mode="off"))  # injection payload against tier 2


def test_row_not_delivered_matches_decode_status():
    undelivered = dict(decode_status="no_symbol", verdict="not_delivered", handle_ns=None)
    assert not ResultRow(**row(**undelivered)).crossed
    with pytest.raises(ValidationError, match="must match an undelivered"):
        ResultRow(**row(verdict="not_delivered"))  # status ok but verdict says undelivered
    with pytest.raises(ValidationError, match="must match an undelivered"):
        ResultRow(**row(decode_status="no_symbol", verdict="crossed"))


def test_row_not_delivered_means_tier_not_invoked():
    with pytest.raises(ValidationError, match="not invoked"):
        ResultRow(**row(decode_status="no_symbol", verdict="not_delivered", handle_ns=10))


def test_row_blocked_verdict_and_flags_agree():
    ResultRow(**row(mode="full", blocked=True, verdict="blocked", handle_ns=None))
    with pytest.raises(ValidationError, match="needs the blocked or gated flag"):
        ResultRow(**row(verdict="blocked"))
    with pytest.raises(ValidationError, match="can only be blocked"):
        ResultRow(**row(mode="full", blocked=True, verdict="no_effect"))


def test_row_crossed_may_coexist_with_a_claimed_block():
    # Precedence rule 2 in docs/oracles.md: the oracle wins over the tier's claim.
    assert ResultRow(**row(mode="full", blocked=True, verdict="crossed")).crossed


def test_row_error_only_with_fault_or_crossed():
    ResultRow(**row(error="TimeoutError", verdict="fault"))
    with pytest.raises(ValidationError, match="errored"):
        ResultRow(**row(error="TimeoutError", verdict="no_effect"))


def test_row_is_csv_flat():
    dumped = ResultRow(**row()).model_dump(mode="json")
    assert all(v is None or isinstance(v, (str, int, float, bool)) for v in dumped.values())


# --- Tier protocol and metadata ------------------------------------------------


def test_tier_protocol_is_structural():
    class Dummy:
        tier_id = TierId.TIER1

        def handle(self, record, mode, rep):
            return TierOutcome(tier=self.tier_id, mode=mode, payload_id="inj-001", rep=rep)

    assert isinstance(Dummy(), Tier)
    assert not isinstance(object(), Tier)


def test_run_metadata_accepts_laptop_run_without_pi_fields():
    meta = RunMetadata(
        run_id="run-1",
        started_at="2026-09-24T10:00:00Z",
        git_sha="abc1234",
        git_dirty=False,
        config_sha256=SHA,
        host_label="laptop",
        os="darwin",
        kernel="25.5.0",
        python="3.11.9",
    )
    assert meta.throttled_start is None


def test_run_metadata_rejects_malformed_throttle_flag():
    with pytest.raises(ValidationError):
        RunMetadata(
            run_id="r",
            started_at="2026-09-24T10:00:00Z",
            git_sha="abc1234",
            git_dirty=False,
            config_sha256=SHA,
            host_label="pi",
            os="linux",
            kernel="6.6",
            python="3.11",
            throttled_start="not-hex",
        )


# --- Config --------------------------------------------------------------------


def test_repo_config_loads():
    cfg = load_config(ROOT / "config.yaml")
    assert cfg.tiers[TierId.TIER3].enabled is False
    assert cfg.model.name == "qwen3-vl:2b"


def test_config_rejects_non_loopback_host():
    d = config_dict()
    d["tiers"]["tier2"]["host"] = "0.0.0.0"
    with pytest.raises(ValidationError, match="loopback"):
        Config.model_validate(d)


def test_config_rejects_mode_invalid_for_tier():
    d = config_dict()
    d["tiers"]["tier3"]["modes"] = ["off", "parameterise_only"]
    with pytest.raises(ValidationError, match="not valid for this tier"):
        Config.model_validate(d)


def test_config_requires_pinned_model_when_tier3_enabled():
    d = config_dict()
    d["tiers"]["tier3"]["enabled"] = True
    with pytest.raises(ValidationError, match="pin the model"):
        Config.model_validate(d)
    d["model"]["digest"] = "0" * 12
    assert Config.model_validate(d).tiers[TierId.TIER3].enabled


def test_config_requires_a_port_for_enabled_service_tiers():
    d = config_dict()
    del d["tiers"]["tier2"]["port"]
    with pytest.raises(ValidationError, match="needs a port"):
        Config.model_validate(d)


def test_config_requires_all_tiers_and_forbids_typos():
    d = config_dict()
    del d["tiers"]["tier1"]
    with pytest.raises(ValidationError, match="tiers missing"):
        Config.model_validate(d)
    with pytest.raises(ValidationError):
        Config.model_validate(config_dict(sead=1))


# --- docs/oracles.md stays in step with the matrix -----------------------------


def test_oracles_doc_has_exactly_one_section_per_applicable_pair():
    text = (ROOT / "docs" / "oracles.md").read_text()
    found = re.findall(r"^#{2,4}\s+O-([a-z_]+)-(tier[123])\s*$", text, flags=re.MULTILINE)
    assert len(found) == len(set(found)), "duplicate oracle section"
    assert {(Family(f), TierId(t)) for f, t in found} == set(APPLICABLE_PAIRS)


def test_every_tier_has_a_full_and_off_mode():
    for tier, modes in VALID_MODES.items():
        assert {Mode.OFF, Mode.FULL} <= modes, tier


def test_verdict_and_status_enums_cover_the_oracle_doc():
    text = (ROOT / "docs" / "oracles.md").read_text()
    for name in [v.value for v in Verdict] + [s.value for s in DecodeStatus]:
        assert f"`{name}`" in text, f"{name} is not defined in docs/oracles.md"


def test_subset_values_match_the_plan():
    assert {s.value for s in Subset} == {"naive", "adaptive", "heldout", "benign"}
