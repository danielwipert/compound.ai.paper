"""Tests for the held-out few-shot examples (TS-4.2, D17)."""

import json
import re

import pandas as pd
import pytest
import yaml

from src.contracts import ExceptionRecord, FactList
from src.fewshot import CLEAN_CSV, FEWSHOT_JSON, SPEC_YAML, build_example
from src.noise.inject import GOLDEN_CSV, NOTE_TEMPLATES_YAML, RENAME_POOL_YAML, load_yaml
from src.schema import CANONICAL_FIELDS

EXAMPLES = json.load(open(FEWSHOT_JSON))
SPEC = yaml.safe_load(open(SPEC_YAML))["examples"]
GOLDEN = pd.read_csv(GOLDEN_CSV)


def normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def template_regex(template: str) -> re.Pattern:
    """'Delay {days}d.' -> regex that matches any filled-in version."""
    parts = re.split(r"\{[a-z_0-9]+\}", template)
    return re.compile(".+?".join(re.escape(p) for p in parts), re.IGNORECASE)


def numbers_in(report: str) -> list[str]:
    without_keys = re.sub(r"\[F\d+\]", "", report)
    return re.findall(r"-?\d+(?:\.\d+)?", without_keys)


def number_in_facts(text: str, fact_list: FactList) -> bool:
    """'129.99' matches a fact value that rounds to it at the same decimals."""
    decimals = len(text.split(".")[1]) if "." in text else 0
    target = float(text)
    for fact in fact_list.facts:
        if isinstance(fact.value, (int, float)) and round(float(fact.value), decimals) == target:
            return True
    return False


def test_three_examples():
    assert len(EXAMPLES) == 3


def test_rows_are_held_out_from_golden():
    for ex in EXAMPLES:
        assert ex["expected"]["order_item_id"] not in set(GOLDEN["order_item_id"])
    csv_order_ids = {int(ex["input"]["csv"].splitlines()[1].split(",")[0]) for ex in EXAMPLES}
    assert not csv_order_ids & set(GOLDEN["order_id"])  # not even the same order


def test_renamed_headers_do_not_leak_from_rename_pool():
    pool = {normalise(a) for alts in load_yaml(RENAME_POOL_YAML).values() for a in alts}
    canonical = {normalise(f) for f in CANONICAL_FIELDS}
    for spec in SPEC:
        for noisy in spec["renames"].values():
            assert normalise(noisy) not in pool, noisy
            assert normalise(noisy) not in canonical, noisy


def test_notes_do_not_match_any_template():
    templates = load_yaml(NOTE_TEMPLATES_YAML)
    all_templates = templates["delay_templates"] + templates["benign_templates"]
    for spec in SPEC:
        for t in all_templates:
            assert not template_regex(t["template"]).fullmatch(spec["carrier_notes"]), (spec["id"], t["id"])


def test_expected_records_are_valid():
    for ex in EXAMPLES:
        record = ExceptionRecord(**ex["expected"])
        assert record.status == "OK"
        assert len(record.header_map) == 16


def test_reports_are_grounded_in_their_fact_list():
    """TS-5.5/5.6 rules: every sentence cites a key, keys exist, numbers come from facts."""
    for ex in EXAMPLES:
        fact_list = FactList(**ex["fact_list"])
        report = ex["expected"]["report"]
        for sentence in re.split(r"(?<=\.)\s+", report.strip()):
            assert re.search(r"\[F\d+\]", sentence), (ex["id"], sentence)
        assert set(ex["expected"]["citations"]) <= fact_list.keys()
        for number in numbers_in(report):
            assert number_in_facts(number, fact_list), (ex["id"], number)


@pytest.mark.skipif(not CLEAN_CSV.exists(), reason="needs data/raw/dataco_clean.csv")
def test_fewshot_json_is_up_to_date():
    clean = pd.read_csv(CLEAN_CSV).set_index("order_item_id", drop=False)
    for spec, ex in zip(SPEC, EXAMPLES):
        fresh = build_example(spec, clean.loc[spec["order_item_id"]].to_dict())
        assert json.loads(json.dumps(fresh)) == ex
