"""Tests for src/data_prep.py using a tiny fake DataCo file (no download needed)."""

import io

import pandas as pd
import pytest

from src.data_prep import check_headers, prepare
from src.schema import CANONICAL_FIELDS, COLUMNS

# A two-row stand-in for DataCo: the 16 real headers plus one column we drop.
FAKE_CSV = (
    "Type,Days for shipping (real),Days for shipment (scheduled),Benefit per order,"
    "Delivery Status,Late_delivery_risk,Category Name,order date (DateOrders),Order Id,"
    "Order Item Id,Order Item Profit Ratio,Order Item Quantity,Sales,Order Region,"
    "Order Status,shipping date (DateOrders),Shipping Mode\r\n"
    "DEBIT,3,4,91.25,Advance shipping,0,Sporting Goods,1/31/2018 22:56,77202,"
    "180517,0.29,1,327.75,Southeast Asia,COMPLETE,2/3/2018 22:56,Standard Class\r\n"
    "CASH,6,2,-12.5,Late delivery,1,Caf\xe9 Gear,12/5/2017 9:03,1001,"
    "2002,-0.04,2,300.0,Europe,SUSPECTED_FRAUD,12/11/2017 9:03,Second Class\r\n"
)


def load_fake() -> pd.DataFrame:
    # Encode as latin-1, like the real file
    return pd.read_csv(io.BytesIO(FAKE_CSV.encode("latin-1")), encoding="latin-1")


def test_prepare_keeps_16_canonical_columns():
    clean = prepare(load_fake())
    assert list(clean.columns) == CANONICAL_FIELDS
    assert len(CANONICAL_FIELDS) == 16


def test_prepare_converts_dates_to_iso():
    clean = prepare(load_fake())
    assert clean["order_date"].tolist() == ["2018-01-31T22:56", "2017-12-05T09:03"]
    assert clean["shipping_date"].tolist() == ["2018-02-03T22:56", "2017-12-11T09:03"]


def test_prepare_decodes_latin1():
    clean = prepare(load_fake())
    assert clean["category_name"].tolist()[1] == "Café Gear"


def test_missing_header_is_an_error():
    headers = [h for _, h, _ in COLUMNS if h != "Sales"]
    with pytest.raises(ValueError, match="Sales"):
        check_headers(headers)


def test_duplicate_item_id_is_an_error():
    raw = load_fake()
    raw.loc[1, "Order Item Id"] = raw.loc[0, "Order Item Id"]
    with pytest.raises(ValueError, match="not unique"):
        prepare(raw)
