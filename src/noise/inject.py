"""Noise injection: one noised copy of the golden set per (drift level, seed) (TS-3).

Run from the repo root (after `python -m src.golden`):

    python -m src.noise.inject

Currently implements schema drift (TS-3.2). Carrier notes (TS-3.3) come next.

For each variant it writes data/noised/{level}/{seed}/:
  noised.csv        golden rows with some headers renamed
  header_map.json   ground truth for field mapping (TS-7.1)
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.schema import CANONICAL_FIELDS

ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_CSV = ROOT / "data" / "golden" / "golden_500.csv"
NOISED_DIR = ROOT / "data" / "noised"
EXPERIMENT_YAML = ROOT / "config" / "experiment.yaml"
RENAME_POOL_YAML = Path(__file__).resolve().parent / "rename_pool.yaml"

# Never renamed: the join key must survive (TS-3.2)
PROTECTED_FIELDS = ["order_id", "order_item_id"]
RENAMABLE_FIELDS = [f for f in CANONICAL_FIELDS if f not in PROTECTED_FIELDS]


def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def level_name(level: float) -> str:
    """0.05 -> '05', 0.30 -> '30' (folder names sort correctly)."""
    return f"{round(level * 100):02d}"


def variant_rng(level: float, seed: int) -> np.random.Generator:
    return np.random.default_rng([seed, round(level * 100)])


def n_renamed(level: float) -> int:
    """Headers to rename at this level: round(level * 16) -> 1 / 2 / 5."""
    return round(level * len(CANONICAL_FIELDS))


def drift_headers(level: float, seed: int, pool: dict[str, list[str]]) -> dict[str, str]:
    """Pick which headers to rename and their new names: {canonical: noisy}."""
    rng = variant_rng(level, seed)
    chosen = rng.choice(RENAMABLE_FIELDS, size=n_renamed(level), replace=False)
    return {field: pool[field][rng.integers(len(pool[field]))] for field in sorted(chosen)}


def make_variant(golden: pd.DataFrame, level: float, seed: int, pool: dict) -> tuple[pd.DataFrame, dict]:
    """Return the noised rows and the header-map ground truth for one variant."""
    renames = drift_headers(level, seed, pool)
    noised = golden.rename(columns=renames)

    header_map = {
        "level": level,
        "seed": seed,
        "renamed": {noisy: canonical for canonical, noisy in renames.items()},
        # every header in the noised file -> its canonical field
        "header_map": {renames.get(f, f): f for f in CANONICAL_FIELDS},
    }
    return noised, header_map


def write_variant(noised: pd.DataFrame, header_map: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    noised.to_csv(out_dir / "noised.csv", index=False, encoding="utf-8")
    with open(out_dir / "header_map.json", "w") as f:
        json.dump(header_map, f, indent=2)


def main() -> None:
    config = load_yaml(EXPERIMENT_YAML)
    pool = load_yaml(RENAME_POOL_YAML)
    golden = pd.read_csv(GOLDEN_CSV)

    for level in config["drift_levels"]:
        for seed in config["seeds"]:
            noised, header_map = make_variant(golden, level, seed, pool)
            out_dir = NOISED_DIR / level_name(level) / str(seed)
            write_variant(noised, header_map, out_dir)
            renamed = ", ".join(f"{c} -> {n!r}" for n, c in header_map["renamed"].items())
            print(f"level {level_name(level)} seed {seed}: {renamed}")


if __name__ == "__main__":
    main()
