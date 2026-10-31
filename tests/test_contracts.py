"""Tests for src/contracts.py and src/facts.py."""

import pytest
from pydantic import ValidationError

from src.contracts import DelayFact, ExceptionRecord, Fact, FactList, HeaderMap, Verdict
from src.facts import build_fact_list

OK_FIELDS = dict(cost_basis=1.0, profit_ratio_recomputed=0.1, delay_days=0, risk_class="NONE")

ROW = {
    "order_id": 1, "order_item_id": 2, "sales": 100.0, "benefit_per_order": 10.0,
    "order_item_profit_ratio": 0.1, "order_item_quantity": 1, "days_shipping_real": 3,
    "days_shipping_scheduled": 2, "delivery_status": "Late delivery", "late_delivery_risk": 1,
    "shipping_mode": "First Class", "order_status": "COMPLETE", "category_name": "Cleats",
    "order_region": "Europe", "order_date": "2018-01-01T00:00", "shipping_date": "2018-01-04T00:00",
}


# --- ExceptionRecord -----------------------------------------------------

def test_ok_record_needs_all_answer_fields():
    ExceptionRecord(order_item_id=1, status="OK", **OK_FIELDS)
    with pytest.raises(ValidationError, match="missing"):
        ExceptionRecord(order_item_id=1, status="OK", cost_basis=1.0)


def test_halt_record_needs_a_known_reason():
    ExceptionRecord(order_item_id=1, status="HALT", halt_reason="PARSE_FAIL")
    with pytest.raises(ValidationError):
        ExceptionRecord(order_item_id=1, status="HALT")
    with pytest.raises(ValidationError):
        ExceptionRecord(order_item_id=1, status="HALT", halt_reason="TIRED")


def test_report_word_limit():
    ExceptionRecord(order_item_id=1, status="OK", report="word " * 120, **OK_FIELDS)
    with pytest.raises(ValidationError, match="120"):
        ExceptionRecord(order_item_id=1, status="OK", report="word " * 121, **OK_FIELDS)


def test_unknown_risk_class_and_cause_rejected():
    with pytest.raises(ValidationError):
        ExceptionRecord(order_item_id=1, status="OK", **{**OK_FIELDS, "risk_class": "MEDIUM"})
    with pytest.raises(ValidationError):
        DelayFact(cause="ALIENS")


# --- HeaderMap, Verdict --------------------------------------------------

def test_header_map_only_accepts_canonical_fields():
    HeaderMap(mapping={"sls_amt": "sales"})
    with pytest.raises(ValidationError):
        HeaderMap(mapping={"sls_amt": "revenue"})


def test_verdict_defaults():
    assert Verdict(accept=True).unsupported_claims == []


# --- FactList ------------------------------------------------------------

def test_fact_list_is_frozen_and_hashed():
    fl = FactList.build(2, [Fact(key="F1", field="sales", value=100.0, source="BUS")])
    with pytest.raises(ValidationError):
        fl.order_item_id = 3
    with pytest.raises(ValidationError, match="digest"):
        FactList(order_item_id=2, facts=fl.facts, digest="0" * 64)


def test_build_fact_list_keys_and_order():
    fl = build_fact_list(ROW, [DelayFact(cause="WEATHER", delay_days=1)])
    fields = [f.field for f in fl.facts]
    assert fields[0] == "order_id" and "order_item_id" not in fields
    assert fields[15:20] == ["cost_basis", "profit_ratio_recomputed", "profit_ratio_delta", "delay_days", "risk_class"]
    assert fields[20:] == ["delay_fact_1.cause", "delay_fact_1.delay_days"]
    assert [f.key for f in fl.facts] == [f"F{i}" for i in range(1, 23)]
    assert {f.source for f in fl.facts[20:]} == {"NODE_B"}


def test_build_fact_list_is_deterministic():
    a = build_fact_list(ROW, [])
    b = build_fact_list(dict(ROW), [])
    assert a.digest == b.digest
    c = build_fact_list({**ROW, "sales": 101.0}, [])
    assert a.digest != c.digest
