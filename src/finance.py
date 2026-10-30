"""Shared deterministic financial functions (TS-2.4, TS-5.4, D12).

Used by BOTH ground_truth.py and the Arm C bus, so the two can never disagree.
No model calls, no randomness.

Rounding (D12): money to 2 decimal places, ratios to 4.
"""

from enum import Enum

import pandas as pd

MONEY_DP = 2
RATIO_DP = 4

# An arm's answer matches ground truth if it is within half a unit of the
# last kept decimal (D12).
MONEY_TOLERANCE = 0.5 * 10**-MONEY_DP  # 0.005
RATIO_TOLERANCE = 0.5 * 10**-RATIO_DP  # 0.00005
_FLOAT_SLACK = 1e-9  # absorbs binary float error right at the boundary


class RiskClass(str, Enum):
    NONE = "NONE"
    LATE = "LATE"
    SEVERE_LATE = "SEVERE_LATE"
    LOSS_MAKING = "LOSS_MAKING"
    FRAUD_HOLD = "FRAUD_HOLD"


SEVERE_LATE_DAYS = 3


def round_money(x: float) -> float:
    return round(float(x), MONEY_DP)


def round_ratio(x: float) -> float:
    return round(float(x), RATIO_DP)


def cost_basis(sales: float, benefit_per_order: float) -> float:
    """Sales minus profit (TS-2.4, see OQ-2 note)."""
    return round_money(sales - benefit_per_order)


def profit_ratio_recomputed(benefit_per_order: float, sales: float) -> float:
    return round_ratio(benefit_per_order / sales)


def profit_ratio_delta(benefit_per_order: float, sales: float, order_item_profit_ratio: float) -> float:
    """Our recomputed ratio minus DataCo's stored ratio."""
    recomputed = profit_ratio_recomputed(benefit_per_order, sales)
    return round_ratio(recomputed - round_ratio(order_item_profit_ratio))


def delay_days(days_shipping_real: int, days_shipping_scheduled: int) -> int:
    return int(days_shipping_real) - int(days_shipping_scheduled)


def risk_class(order_status: str, benefit_per_order: float, delay: int) -> RiskClass:
    """TS-2.4 rule, checked in this order; first match wins."""
    if order_status == "SUSPECTED_FRAUD":
        return RiskClass.FRAUD_HOLD
    if benefit_per_order < 0:
        return RiskClass.LOSS_MAKING
    if delay >= SEVERE_LATE_DAYS:
        return RiskClass.SEVERE_LATE
    if delay > 0:
        return RiskClass.LATE
    return RiskClass.NONE


def compute_row(row: dict) -> dict:
    """All derived fields for one row with canonical field names."""
    delay = delay_days(row["days_shipping_real"], row["days_shipping_scheduled"])
    return {
        "cost_basis": cost_basis(row["sales"], row["benefit_per_order"]),
        "profit_ratio_recomputed": profit_ratio_recomputed(row["benefit_per_order"], row["sales"]),
        "profit_ratio_delta": profit_ratio_delta(
            row["benefit_per_order"], row["sales"], row["order_item_profit_ratio"]
        ),
        "delay_days": delay,
        "risk_class": risk_class(row["order_status"], row["benefit_per_order"], delay).value,
    }


def compute_frame(df: pd.DataFrame) -> pd.DataFrame:
    """compute_row for every row; returns a new frame with order_item_id + derived fields."""
    derived = pd.DataFrame([compute_row(r) for r in df.to_dict("records")], index=df.index)
    return pd.concat([df[["order_item_id"]], derived], axis=1)


def money_matches(answer: float, truth: float) -> bool:
    return abs(float(answer) - float(truth)) <= MONEY_TOLERANCE + _FLOAT_SLACK


def ratio_matches(answer: float, truth: float) -> bool:
    return abs(float(answer) - float(truth)) <= RATIO_TOLERANCE + _FLOAT_SLACK
