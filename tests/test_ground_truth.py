"""Tests for src/ground_truth.py against the committed golden set."""

import json

import pandas as pd
import pytest

from src.finance import compute_row
from src.ground_truth import GOLDEN_CSV, GROUND_TRUTH, build_ground_truth, load_ground_truth

STRATA_JSON = GOLDEN_CSV.with_name("golden_500.strata.json")


@pytest.fixture(scope="module")
def golden():
    return pd.read_csv(GOLDEN_CSV)


def test_one_row_per_golden_row(golden):
    gt = build_ground_truth(golden)
    assert len(gt) == 500
    assert gt["order_item_id"].tolist() == golden["order_item_id"].tolist()
    assert list(gt.columns) == [
        "order_item_id", "cost_basis", "profit_ratio_recomputed",
        "profit_ratio_delta", "delay_days", "risk_class",
    ]


def test_matches_finance_row_by_row(golden):
    gt = build_ground_truth(golden).set_index("order_item_id")
    for row in golden.head(25).to_dict("records"):
        assert gt.loc[row["order_item_id"]].to_dict() == compute_row(row)


def test_risk_class_agrees_with_strata(golden):
    gt = build_ground_truth(golden).set_index("order_item_id")
    strata = json.load(open(STRATA_JSON))["stratum_by_order_item_id"]
    for item_id, stratum in strata.items():
        risk = gt.loc[int(item_id), "risk_class"]
        if stratum == "S1":  # negative profit: fraud check runs first, so either
            assert risk in ("LOSS_MAKING", "FRAUD_HOLD")
        if stratum == "S2":  # severe delay, profit >= 0
            assert risk in ("SEVERE_LATE", "FRAUD_HOLD")


def test_frozen_file_is_up_to_date(golden):
    """The committed parquet must equal a fresh computation."""
    frozen = load_ground_truth(GROUND_TRUTH)
    fresh = build_ground_truth(golden).set_index("order_item_id")
    pd.testing.assert_frame_equal(frozen, fresh)
