"""Tests for src/golden.py using a synthetic population (no download needed)."""

import numpy as np
import pandas as pd
import pytest

from src.finance import delay_days
from src.golden import BLOCK_SIZE, PER_BLOCK, assign_strata, build_golden
from src.schema import CANONICAL_FIELDS


def make_population(n: int = 6000, seed: int = 1) -> pd.DataFrame:
    """Random rows with every canonical column, enough for all six strata."""
    rng = np.random.default_rng(seed)
    real = rng.integers(0, 7, n)
    return pd.DataFrame({
        "order_id": rng.integers(1, 10**6, n),
        "order_item_id": np.arange(1, n + 1),
        "sales": rng.uniform(10, 500, n).round(2),
        "benefit_per_order": rng.uniform(-100, 150, n).round(2),
        "order_item_profit_ratio": rng.uniform(-1, 0.5, n).round(2),
        "order_item_quantity": rng.integers(1, 5, n),
        "days_shipping_real": real,
        "days_shipping_scheduled": rng.integers(0, 5, n),
        "delivery_status": "Shipping on time",
        "late_delivery_risk": rng.integers(0, 2, n),
        "shipping_mode": "Standard Class",
        "order_status": rng.choice(["COMPLETE", "CANCELED", "SUSPECTED_FRAUD"], n, p=[0.9, 0.05, 0.05]),
        "category_name": "Cleats",
        "order_region": "Europe",
        "order_date": "2018-01-01T00:00",
        "shipping_date": "2018-01-02T00:00",
    })[CANONICAL_FIELDS]


def test_first_matching_stratum_wins():
    df = make_population(4)
    df.loc[0, ["benefit_per_order", "days_shipping_real", "days_shipping_scheduled"]] = [-5, 9, 1]
    df.loc[1, ["benefit_per_order", "days_shipping_real", "days_shipping_scheduled"]] = [5, 9, 1]
    df.loc[2, ["benefit_per_order", "days_shipping_real", "days_shipping_scheduled", "late_delivery_risk"]] = [5, 3, 2, 0]
    df.loc[3, ["benefit_per_order", "days_shipping_real", "days_shipping_scheduled", "order_status"]] = [5, 1, 2, "COMPLETE"]
    df.loc[3, "sales"] = 1.0
    strata, _ = assign_strata(df)
    assert strata.tolist()[:3] == ["S1", "S2", "S3"]  # loss beats delay; delay of 1 with flag 0 is S3


def test_golden_size_columns_and_unique_ids():
    golden, meta = build_golden(make_population())
    assert len(golden) == 500
    assert list(golden.columns) == CANONICAL_FIELDS  # no stratum column leaks to arms
    assert golden["order_item_id"].is_unique
    assert len(meta["stratum_by_order_item_id"]) == 500


def test_every_block_of_100_has_exact_shares():
    golden, meta = build_golden(make_population())
    labels = [meta["stratum_by_order_item_id"][str(i)] for i in golden["order_item_id"]]
    for start in range(0, 500, BLOCK_SIZE):
        counts = pd.Series(labels[start:start + BLOCK_SIZE]).value_counts().to_dict()
        assert counts == PER_BLOCK


def test_rows_really_belong_to_their_stratum():
    golden, meta = build_golden(make_population())
    for row in golden.to_dict("records"):
        s = meta["stratum_by_order_item_id"][str(row["order_item_id"])]
        delay = delay_days(row["days_shipping_real"], row["days_shipping_scheduled"])
        if s == "S1":
            assert row["benefit_per_order"] < 0
        if s == "S2":
            assert delay >= 3
        if s == "S3":
            assert delay > 0 and row["late_delivery_risk"] == 0


def test_same_seed_same_result_different_seed_different_result():
    pop = make_population()
    a, _ = build_golden(pop)
    b, _ = build_golden(pop.sample(frac=1, random_state=7))  # input order must not matter
    c, _ = build_golden(pop, seed=123)
    assert a.equals(b)
    assert not a.equals(c)


def test_too_small_stratum_is_an_error():
    pop = make_population()
    pop["order_status"] = "COMPLETE"  # empties S4
    with pytest.raises(ValueError, match="S4"):
        build_golden(pop)
