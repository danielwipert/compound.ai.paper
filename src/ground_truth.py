"""Compute and freeze the financial ground truth for the golden set (TS-2.4).

Run from the repo root (after `python -m src.golden`):

    python -m src.ground_truth

Reads data/golden/golden_500.csv, applies src/finance.py to every row, and
writes data/golden/ground_truth.parquet with one row per order_item_id:

    order_item_id, cost_basis, profit_ratio_recomputed, profit_ratio_delta,
    delay_days, risk_class

The other two TS-2.4 fields, header_map and delay_facts, differ per noised
variant, so the noise injector writes them to data/noised/{level}/{seed}/
(TS-3.2, TS-3.3).
"""

from pathlib import Path

import pandas as pd

from src.finance import compute_frame

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_CSV = ROOT / "data" / "golden" / "golden_500.csv"
GROUND_TRUTH = ROOT / "data" / "golden" / "ground_truth.parquet"


def build_ground_truth(golden: pd.DataFrame) -> pd.DataFrame:
    gt = compute_frame(golden)
    gt["delay_days"] = gt["delay_days"].astype("int64")
    gt["risk_class"] = gt["risk_class"].astype("string")
    return gt.reset_index(drop=True)


def load_ground_truth(path: Path = GROUND_TRUTH) -> pd.DataFrame:
    """Frozen ground truth, indexed by order_item_id (for metrics later)."""
    return pd.read_parquet(path).set_index("order_item_id")


def main() -> None:
    golden = pd.read_csv(GOLDEN_CSV)
    gt = build_ground_truth(golden)
    gt.to_parquet(GROUND_TRUTH, index=False)
    print(f"Wrote {len(gt)} rows to {GROUND_TRUTH}")
    print("Risk classes:", gt["risk_class"].value_counts().to_dict())


if __name__ == "__main__":
    main()
