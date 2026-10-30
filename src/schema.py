"""Canonical columns used from DataCo (TS-2.2).

One place that maps our canonical field names to the exact DataCo headers.
Every other module imports from here.
"""

# (canonical field, exact DataCo header, type) — order matches TS-2.2
COLUMNS = [
    ("order_id", "Order Id", "int"),
    ("order_item_id", "Order Item Id", "int"),
    ("sales", "Sales", "float"),
    ("benefit_per_order", "Benefit per order", "float"),
    ("order_item_profit_ratio", "Order Item Profit Ratio", "float"),
    ("order_item_quantity", "Order Item Quantity", "int"),
    ("days_shipping_real", "Days for shipping (real)", "int"),
    ("days_shipping_scheduled", "Days for shipment (scheduled)", "int"),
    ("delivery_status", "Delivery Status", "enum"),
    ("late_delivery_risk", "Late_delivery_risk", "bool"),
    ("shipping_mode", "Shipping Mode", "enum"),
    ("order_status", "Order Status", "enum"),
    ("category_name", "Category Name", "str"),
    ("order_region", "Order Region", "str"),
    ("order_date", "order date (DateOrders)", "datetime"),
    ("shipping_date", "shipping date (DateOrders)", "datetime"),
]

CANONICAL_FIELDS = [canonical for canonical, _, _ in COLUMNS]
DATACO_TO_CANONICAL = {header: canonical for canonical, header, _ in COLUMNS}
FIELD_TYPES = {canonical: kind for canonical, _, kind in COLUMNS}
