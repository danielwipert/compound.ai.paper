"""Tests for carrier notes (TS-3.3, D16)."""

import string
from collections import Counter

import numpy as np
import pandas as pd
import pytest

from src.contracts import DelayFact
from src.noise.inject import (
    GOLDEN_CSV,
    NOTE_TEMPLATES_YAML,
    RENAME_POOL_YAML,
    load_yaml,
    make_note,
    make_notes,
    make_variant,
)

TEMPLATES = load_yaml(NOTE_TEMPLATES_YAML)
POOL = load_yaml(RENAME_POOL_YAML)
CAUSES = ["PORT_CONGESTION", "CUSTOMS", "WEATHER", "LABOUR", "MECHANICAL", "ADDRESS_ISSUE", "CAPACITY", "UNKNOWN"]


@pytest.fixture(scope="module")
def golden():
    return pd.read_csv(GOLDEN_CSV)


def placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


# --- templates -----------------------------------------------------------

def test_at_least_25_delay_templates_and_every_cause_covered():
    delay_templates = TEMPLATES["delay_templates"]
    assert len(delay_templates) >= 25
    causes = {f["cause"] for t in delay_templates for f in t["facts"]}
    assert causes == set(CAUSES)


def test_template_ids_unique():
    ids = [t["id"] for t in TEMPLATES["delay_templates"] + TEMPLATES["benign_templates"]]
    assert len(ids) == len(set(ids))


def test_facts_only_use_placeholders_the_text_shows():
    """A fact may not state a number or place the note never mentions."""
    for t in TEMPLATES["delay_templates"]:
        in_text = placeholders(t["template"])
        if "days_word" in in_text:
            in_text.add("days")  # "two" in the text is the number 2 in the facts
        for fact in t["facts"]:
            for value in fact.values():
                assert placeholders(str(value)) <= in_text, t["id"]


# --- one note ------------------------------------------------------------

@pytest.mark.parametrize("delay", [1, 2, 3, 4])
def test_late_note_numbers_agree_with_delay(delay):
    rng = np.random.default_rng(0)
    for _ in range(200):
        note, facts, template_id = make_note(delay, rng, TEMPLATES)
        assert note and template_id.startswith("T")
        assert "{" not in note
        for fact in facts:
            DelayFact(**fact)  # valid against the schema
        days = [f["delay_days"] for f in facts if "delay_days" in f]
        hours = [f["delay_hours"] for f in facts if "delay_hours" in f]
        if days:
            assert sum(days) == delay  # two-fact templates split the delay
        for h in hours:
            assert (delay - 1) * 24 < h <= delay * 24  # rounds up to the delay


def test_two_fact_templates_need_two_days():
    rng = np.random.default_rng(0)
    ids = {make_note(1, rng, TEMPLATES)[2] for _ in range(500)}
    assert not ids & {"T28", "T29", "T30"}


def test_on_time_rows_get_empty_or_benign_notes():
    rng = np.random.default_rng(0)
    results = [make_note(0, rng, TEMPLATES) for _ in range(2000)]
    assert all(facts == [] for _, facts, _ in results)
    benign_share = sum(1 for note, _, _ in results if note) / len(results)
    assert 0.17 < benign_share < 0.23  # TS-3.3: about 20%


# --- whole variant -------------------------------------------------------

def test_notes_depend_on_seed_not_level(golden):
    a, _, facts_a = make_variant(golden, 0.05, 2, POOL, TEMPLATES)
    b, _, facts_b = make_variant(golden, 0.30, 2, POOL, TEMPLATES)
    c, _, _ = make_variant(golden, 0.05, 3, POOL, TEMPLATES)
    assert a["carrier_notes"].tolist() == b["carrier_notes"].tolist()
    assert facts_a == facts_b
    assert a["carrier_notes"].tolist() != c["carrier_notes"].tolist()


def test_delay_facts_line_up_with_rows(golden):
    notes, records = make_notes(golden, 1, TEMPLATES)
    assert [r["order_item_id"] for r in records] == golden["order_item_id"].tolist()
    late = (golden["days_shipping_real"] - golden["days_shipping_scheduled"]) > 0
    for is_late, note, record in zip(late, notes, records):
        if is_late:
            assert note and record["delay_facts"]
        else:
            assert record["delay_facts"] == []


def test_templates_are_spread_out(golden):
    _, records = make_notes(golden, 1, TEMPLATES)
    used = Counter(r["template_id"] for r in records if r["template_id"] and r["template_id"].startswith("T"))
    assert len(used) >= 20  # most templates appear in a 500-row variant
