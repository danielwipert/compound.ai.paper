# Compound AI Architecture Benchmark

Does a compound system of small open-weight models, bounded by a deterministic Python bus, match a tooled frontier model on accuracy under input noise, while costing less per 1,000 rows?

- What and why: [`docs/product-spec.md`](docs/product-spec.md)
- Engineering detail: [`docs/tech-spec.md`](docs/tech-spec.md)
- Decision log: [`docs/decisions.md`](docs/decisions.md)

**Status:** Phase 1 (Build): skeleton and data download done.

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

## Licence

Code: MIT, see [`LICENSE`](LICENSE).
