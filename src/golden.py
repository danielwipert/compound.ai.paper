"""Build the 500-row Golden Test Set (TS-2.3, D14).

Run from the repo root (after `python -m src.data_prep`):

    python -m src.golden

Steps:
  1. Assign every DataCo row to exactly one stratum S1..S6 (first match wins).
  2. Sample the target number of rows from each stratum with a fixed seed.
  3. Order the 500 rows in 5 blocks of 100. Each block holds the exact stratum
     shares, shuffled inside the block, so the pilot's first 100 rows are
     stratified too.
  4. Write data/golden/golden_500.csv (16 canonical columns only, so arms never
     see the stratum) and data/golden/golden_500.strata.json.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.schema import CANONICAL_FIELDS

ROOT = Path(__file__).resolve().parent.parent
CLEAN_CSV = ROOT / "data" / "raw" / "dataco_clean.csv"
GOLDEN_DIR = ROOT / "data" / "golden"

SEED = 20261029
N_ROWS = 500
BLOCK_SIZE = 100

# Stratum -> rows per block of 100 (TS-2.3 shares: 20/20/10/10/10/30%)
PER_BLOCK = {"S1": 20, "S2": 20, "S3": 10, "S4": 10, "S5": 10, "S6": 30}

DESCRIPTIONS = {
    "S1": "negative profit: benefit_per_order < 0",
    "S2": "severe delay: delay_days >= 3",
    "S3": "risk flag contradicts delay: delay_days > 0 AND late_delivery_risk == 0 (D14)",
    "S4": "cancelled / suspected fraud: order_status in (CANCELED, SUSPECTED_FRAUD)",
    "S5": "high-value: sales >= p95(sales)",
    "S6": "baseline: none of the above",
}


def assign_strata(df: pd.DataFrame) -> tuple[pd.Series, float]:
    """Return one stratum label per row, and the p95 sales threshold used."""
    # Same formula as finance.delay_days, applied to the whole column at once
    delay = df["days_shipping_real"] - df["days_shipping_scheduled"]
    p95_sales = float(df["sales"].quantile(0.95))

    rules = {
        "S1": df["benefit_per_order"] < 0,
        "S2": delay >= 3,
        "S3": (delay > 0) & (df["late_delivery_risk"] == 0),
        "S4": df["order_status"].isin(["CANCELED", "SUSPECTED_FRAUD"]),
        "S5": df["sales"] >= p95_sales,
    }
    strata = pd.Series("S6", index=df.index)
    unassigned = pd.Series(True, index=df.index)
    for name, matches in rules.items():  # table order: first match wins
        hit = matches & unassigned
        strata[hit] = name
        unassigned &= ~hit
    return strata, p95_sales


def build_golden(df: pd.DataFrame, seed: int = SEED) -> tuple[pd.DataFrame, dict]:
    """Return the 500 golden rows (in final order) and the strata metadata."""
    n_blocks = N_ROWS // BLOCK_SIZE
    rng = np.random.default_rng(seed)

    # Sort first so the result depends only on the data and the seed
    df = df.sort_values("order_item_id").reset_index(drop=True)
    strata, p95_sales = assign_strata(df)

    # Sample each stratum, then cut its sample into one slice per block
    slices = {}
    for name, per_block in PER_BLOCK.items():
        pool = df.index[strata == name].to_numpy()
        need = per_block * n_blocks
        if len(pool) < need:
            raise ValueError(f"Stratum {name} has {len(pool)} rows, needs {need}")
        picked = rng.choice(pool, size=need, replace=False)
        slices[name] = np.split(picked, n_blocks)

    # Assemble blocks: each holds every stratum's share, shuffled inside
    order = []
    for b in range(n_blocks):
        block = np.concatenate([slices[name][b] for name in PER_BLOCK])
        order.extend(rng.permutation(block))

    golden = df.loc[order, CANONICAL_FIELDS].reset_index(drop=True)
    golden_strata = strata[order].tolist()

    meta = {
        "seed": seed,
        "source_rows": len(df),
        "p95_sales": p95_sales,
        "block_size": BLOCK_SIZE,
        "per_block": PER_BLOCK,
        "descriptions": DESCRIPTIONS,
        "population": {name: int((strata == name).sum()) for name in PER_BLOCK},
        "stratum_by_order_item_id": {
            str(int(i)): s for i, s in zip(golden["order_item_id"], golden_strata)
        },
    }
    return golden, meta


def main() -> None:
    df = pd.read_csv(CLEAN_CSV)
    golden, meta = build_golden(df)

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    golden.to_csv(GOLDEN_DIR / "golden_500.csv", index=False, encoding="utf-8")
    with open(GOLDEN_DIR / "golden_500.strata.json", "w") as f:
        json.dump(meta, f, indent=2)

    counts = pd.Series(meta["stratum_by_order_item_id"]).value_counts().sort_index()
    print(f"Wrote {len(golden)} rows to {GOLDEN_DIR / 'golden_500.csv'}")
    print("Rows per stratum:", counts.to_dict())


if __name__ == "__main__":
    main()
