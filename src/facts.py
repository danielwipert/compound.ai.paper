"""Assemble the FactList for one row (TS-5.4 step 4).

Deterministic: same row + same delay facts -> same keys, same digest.
Used by the Arm C bus and to build the few-shot examples.

Key order:
  1. canonical row fields (TS-2.2 order, except order_item_id)   source BUS
  2. derived financial fields from finance.py                    source BUS
  3. each DelayFact's non-empty fields, as delay_fact_N.<name>   source NODE_B
"""

from src.contracts import DelayFact, Fact, FactList
from src.finance import compute_row
from src.schema import CANONICAL_FIELDS

DERIVED_FIELDS = ["cost_basis", "profit_ratio_recomputed", "profit_ratio_delta", "delay_days", "risk_class"]


def build_fact_list(row: dict, delay_facts: list[DelayFact]) -> FactList:
    """row: one record with canonical field names, already type-cast."""
    entries: list[tuple[str, object, str]] = []
    for field in CANONICAL_FIELDS:
        if field != "order_item_id":
            entries.append((field, row[field], "BUS"))

    derived = compute_row(row)
    for field in DERIVED_FIELDS:
        entries.append((field, derived[field], "BUS"))

    for n, fact in enumerate(delay_facts, start=1):
        for name, value in fact.model_dump(exclude_none=True).items():
            entries.append((f"delay_fact_{n}.{name}", value, "NODE_B"))

    facts = [
        Fact(key=f"F{i}", field=field, value=_plain(value), source=source)
        for i, (field, value, source) in enumerate(entries, start=1)
    ]
    return FactList.build(int(row["order_item_id"]), facts)


def _plain(value):
    """numpy / pandas scalars -> plain Python int, float or str."""
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, bool):
        return int(value)
    return value
