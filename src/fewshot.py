"""Build the 3 held-out few-shot examples (TS-4.2, D17).

Run from the repo root (needs data/raw/dataco_clean.csv from `python -m src.data_prep`):

    python -m src.fewshot

Reads the hand-written parts from data/fewshot/spec.yaml, looks up each row in
DataCo, and writes data/fewshot/fewshot.json. Each example holds:
  input      the noised header row and data row, exactly as an arm sees them
  fact_list  the FactList (src/facts.py) the report cites
  expected   the correct ExceptionRecord
"""

import io
import json
import re
from pathlib import Path

import pandas as pd
import yaml

from src.contracts import DelayFact, ExceptionRecord
from src.facts import build_fact_list
from src.finance import compute_row
from src.schema import CANONICAL_FIELDS

ROOT = Path(__file__).resolve().parent.parent
CLEAN_CSV = ROOT / "data" / "raw" / "dataco_clean.csv"
FEWSHOT_DIR = ROOT / "data" / "fewshot"
SPEC_YAML = FEWSHOT_DIR / "spec.yaml"
FEWSHOT_JSON = FEWSHOT_DIR / "fewshot.json"


def cited_keys(report: str) -> list[str]:
    """['F20', 'F6', ...] in order of first appearance."""
    keys = re.findall(r"\[(F\d+)\]", report)
    return list(dict.fromkeys(keys))


def build_example(spec: dict, row: dict) -> dict:
    renames = spec["renames"]
    header = [renames.get(f, f) for f in CANONICAL_FIELDS] + ["carrier_notes"]
    values = [row[f] for f in CANONICAL_FIELDS] + [spec["carrier_notes"]]

    # The CSV text exactly as an arm receives it (header line + one data line)
    buffer = io.StringIO()
    pd.DataFrame([values], columns=header).to_csv(buffer, index=False, lineterminator="\n")

    delay_facts = [DelayFact(**f) for f in spec["delay_facts"]]
    fact_list = build_fact_list(row, delay_facts)
    derived = compute_row(row)

    expected = ExceptionRecord(
        order_item_id=int(row["order_item_id"]),
        header_map={renames.get(f, f): f for f in CANONICAL_FIELDS},
        delay_facts=delay_facts,
        cost_basis=derived["cost_basis"],
        profit_ratio_recomputed=derived["profit_ratio_recomputed"],
        delay_days=derived["delay_days"],
        risk_class=derived["risk_class"],
        report=spec["report"],
        citations=cited_keys(spec["report"]),
        status="OK",
    )
    return {
        "id": spec["id"],
        "situation": spec["situation"],
        "input": {"header": header, "csv": buffer.getvalue()},
        "fact_list": fact_list.model_dump(),
        "expected": expected.model_dump(mode="json"),
    }


def main() -> None:
    spec = yaml.safe_load(open(SPEC_YAML))
    clean = pd.read_csv(CLEAN_CSV).set_index("order_item_id", drop=False)

    examples = []
    for example_spec in spec["examples"]:
        row = clean.loc[example_spec["order_item_id"]].to_dict()
        examples.append(build_example(example_spec, row))

    with open(FEWSHOT_JSON, "w") as f:
        json.dump(examples, f, indent=2)
    print(f"Wrote {len(examples)} examples to {FEWSHOT_JSON}")


if __name__ == "__main__":
    main()
