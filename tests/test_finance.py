"""Tests for src/finance.py (TS-2.4, D12)."""

import pandas as pd
import pytest

from src.finance import (
    RiskClass,
    compute_frame,
    compute_row,
    cost_basis,
    delay_days,
    money_matches,
    profit_ratio_delta,
    profit_ratio_recomputed,
    ratio_matches,
    risk_class,
)

# Two real DataCo rows (values as stored, float noise included)
ROW_PROFIT = {
    "order_item_id": 180517, "sales": 327.75, "benefit_per_order": 91.25,
    "order_item_profit_ratio": 0.289999992, "days_shipping_real": 3,
    "days_shipping_scheduled": 4, "order_status": "COMPLETE",
}
ROW_LOSS = {
    "order_item_id": 179254, "sales": 327.75, "benefit_per_order": -249.0899963,
    "order_item_profit_ratio": -0.800000012, "days_shipping_real": 5,
    "days_shipping_scheduled": 4, "order_status": "PENDING",
}


def test_cost_basis_rounds_float_noise_to_cents():
    assert cost_basis(327.75, -249.0899963) == 576.84
    assert cost_basis(327.75, 91.25) == 236.5


def test_profit_ratio_recomputed_four_decimals():
    assert profit_ratio_recomputed(91.25, 327.75) == 0.2784
    assert profit_ratio_recomputed(-249.0899963, 327.75) == -0.76


def test_profit_ratio_delta():
    # 0.2784 - 0.29
    assert profit_ratio_delta(91.25, 327.75, 0.289999992) == -0.0116


def test_delay_days():
    assert delay_days(5, 4) == 1
    assert delay_days(3, 4) == -1


@pytest.mark.parametrize(
    "status, benefit, delay, expected",
    [
        ("SUSPECTED_FRAUD", -10.0, 5, RiskClass.FRAUD_HOLD),  # fraud beats everything
        ("COMPLETE", -10.0, 5, RiskClass.LOSS_MAKING),         # loss beats delay
        ("COMPLETE", 10.0, 3, RiskClass.SEVERE_LATE),          # 3 days is severe
        ("COMPLETE", 10.0, 2, RiskClass.LATE),
        ("COMPLETE", 10.0, 0, RiskClass.NONE),
        ("COMPLETE", 0.0, -1, RiskClass.NONE),                 # zero profit is not a loss
        ("CANCELED", 10.0, 0, RiskClass.NONE),                 # cancelled is not fraud
    ],
)
def test_risk_class_order(status, benefit, delay, expected):
    assert risk_class(status, benefit, delay) == expected


def test_compute_row():
    assert compute_row(ROW_LOSS) == {
        "cost_basis": 576.84,
        "profit_ratio_recomputed": -0.76,
        "profit_ratio_delta": 0.04,
        "delay_days": 1,
        "risk_class": "LOSS_MAKING",
    }


def test_compute_frame_matches_compute_row():
    df = pd.DataFrame([ROW_PROFIT, ROW_LOSS])
    out = compute_frame(df)
    assert out["order_item_id"].tolist() == [180517, 179254]
    assert out.iloc[1].drop("order_item_id").to_dict() == compute_row(ROW_LOSS)


def test_money_tolerance_half_a_cent():
    assert money_matches(576.8399963, 576.84)  # unrounded answer is fine
    assert money_matches(576.845, 576.84)      # exactly half a cent: still a match
    assert not money_matches(576.85, 576.84)   # a whole cent off: wrong


def test_ratio_tolerance():
    assert ratio_matches(-0.76001, -0.76)
    assert not ratio_matches(-0.7601, -0.76)
