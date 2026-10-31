"""Tests for schema drift (TS-3.2): rename pool and header renaming."""

import re

import pandas as pd
import pytest

from src.noise.inject import (
    GOLDEN_CSV,
    PROTECTED_FIELDS,
    RENAMABLE_FIELDS,
    RENAME_POOL_YAML,
    drift_headers,
    load_yaml,
    make_variant,
    n_renamed,
)
from src.schema import CANONICAL_FIELDS

POOL = load_yaml(RENAME_POOL_YAML)
LEVELS = [0.05, 0.15, 0.30]


def normalise(name: str) -> str:
    """'Profit (per order)' -> 'profitperorder', for collision checks."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


# --- rename pool ---------------------------------------------------------

def test_pool_covers_exactly_the_renamable_fields():
    assert sorted(POOL) == sorted(RENAMABLE_FIELDS)
    assert not set(PROTECTED_FIELDS) & set(POOL)


def test_pool_has_at_least_5_alternates_per_field():
    for field, alternates in POOL.items():
        assert len(alternates) >= 5, field


def test_alternates_never_collide():
    all_alternates = [a for alts in POOL.values() for a in alts]
    normalised = [normalise(a) for a in all_alternates]
    assert len(set(normalised)) == len(normalised), "two alternates look the same"
    canonical = {normalise(f) for f in CANONICAL_FIELDS}
    assert not canonical & set(normalised), "an alternate looks like a canonical name"


# --- renaming ------------------------------------------------------------

def test_rounding_rule():
    assert [n_renamed(level) for level in LEVELS] == [1, 2, 5]


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_drift_headers(level, seed):
    renames = drift_headers(level, seed, POOL)
    assert len(renames) == n_renamed(level)
    for canonical, noisy in renames.items():
        assert canonical not in PROTECTED_FIELDS
        assert noisy in POOL[canonical]


def test_same_seed_same_renames_different_seed_differs():
    assert drift_headers(0.30, 1, POOL) == drift_headers(0.30, 1, POOL)
    variants = {tuple(drift_headers(0.30, s, POOL).items()) for s in range(1, 6)}
    assert len(variants) > 1


def test_make_variant_on_golden_set():
    golden = pd.read_csv(GOLDEN_CSV)
    noised, header_map = make_variant(golden, 0.15, 3, POOL)

    # same data, only headers changed, order kept
    assert noised.values.tolist() == golden.values.tolist()
    assert len(noised.columns) == 16

    # header_map covers every noisy header and points back to the canonical name
    assert list(header_map["header_map"]) == list(noised.columns)
    assert sorted(header_map["header_map"].values()) == sorted(CANONICAL_FIELDS)

    # 'renamed' is the subset that actually changed
    assert len(header_map["renamed"]) == 2
    for noisy, canonical in header_map["renamed"].items():
        assert noisy in noised.columns and canonical not in noised.columns
        assert header_map["header_map"][noisy] == canonical
