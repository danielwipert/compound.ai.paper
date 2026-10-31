# Compound AI Architecture Benchmark

Does a compound system of small open-weight models, bounded by a deterministic Python bus, match a tooled frontier model on accuracy under input noise, while costing less per 1,000 rows?

- What and why: [`docs/product-spec.md`](docs/product-spec.md)
- Engineering detail: [`docs/tech-spec.md`](docs/tech-spec.md)
- Decision log: [`docs/decisions.md`](docs/decisions.md)

**Status:** Phase 1 (Build): skeleton, data download, `finance.py` and golden set done.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # then add your API keys
pytest
```

## Get the data

```bash
python -m src.data_prep
```

This downloads the DataCo CSV (~96 MB) from Mendeley into `data/raw/`, checks its SHA-256 hash, and writes a clean 16-column UTF-8 copy to `data/raw/dataco_clean.csv`. Both files are git-ignored. Dataset licence: CC BY 4.0, see [`data/LICENSE-dataco.txt`](data/LICENSE-dataco.txt).

## Build the golden set

```bash
python -m src.golden
```

Picks the 500 test rows (TS-2.3, D14) with a fixed seed and writes `data/golden/golden_500.csv` and `data/golden/golden_500.strata.json`. These are committed; re-running gives identical files.

## Licence

Code: MIT, see [`LICENSE`](LICENSE).
