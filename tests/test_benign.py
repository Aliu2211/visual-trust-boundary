import pytest

from attacks.benign import HARD_ASCII, NON_ASCII, benign_ascii


def test_the_set_is_reproducible_and_seed_dependent():
    assert benign_ascii(50) == benign_ascii(50)
    assert benign_ascii(50, seed=1) != benign_ascii(50, seed=2)


def test_the_set_has_the_requested_size_unique_short_ascii_ids_and_the_hard_cases():
    ids = benign_ascii(100)
    assert len(ids) == len(set(ids)) == 100
    assert all(0 < len(t) <= 64 and t.isascii() for t in ids)
    assert set(HARD_ASCII) <= set(ids)


def test_a_set_smaller_than_the_fixed_hard_cases_is_rejected():
    with pytest.raises(ValueError, match="at least"):
        benign_ascii(len(HARD_ASCII) - 1)


def test_the_non_ascii_texts_really_are_not_ascii():
    assert NON_ASCII and not any(t.isascii() for t in NON_ASCII)
