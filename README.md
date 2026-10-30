# Compound AI Architecture Benchmark

Does a compound system of small open-weight models, bounded by a deterministic Python bus, match a tooled frontier model on accuracy under input noise, while costing less per 1,000 rows?

- What and why: [`docs/product-spec.md`](docs/product-spec.md)
- Engineering detail: [`docs/tech-spec.md`](docs/tech-spec.md)
- Decision log: [`docs/decisions.md`](docs/decisions.md)

**Status:** Phase 1 (Build), project skeleton only.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # then add your API keys
pytest
```
