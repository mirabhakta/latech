import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.processor import infer_column_mapping, map_to_standard_schema, standardize_column_names


def test_standardize_column_names_handles_common_retail_headers() -> None:
    df = pd.DataFrame({
        "Invoice Date": ["2024-01-01"],
        "Sales Amount": [125.50],
        "Store No": [7],
        "Product SKU": [1001],
        "Units_Sold": [3],
        "Net Profit": [25.00],
        "Market": ["South"],
        "Order Count": [2],
        "Random Notes": ["promo"],
    })

    standardized = standardize_column_names(df)

    assert "date" in standardized.columns
    assert "sales" in standardized.columns
    assert "store_id" in standardized.columns
    assert "product_id" in standardized.columns
    assert "quantity" in standardized.columns
    assert "profit" in standardized.columns
    assert "region" in standardized.columns
    assert "transaction_count" in standardized.columns
    assert "Random Notes" in standardized.attrs["unmapped_columns"]


def test_fuzzy_mapping_handles_typos_and_camel_case_headers() -> None:
    df = pd.DataFrame({
        "OrderDate": ["2024-01-01"],
        "Sales Amnt": [125.50],
        "StoreNum": [7],
        "Prodct SKU": [1001],
        "Product Catgory": ["Shirts"],
        "UnitsSold": [3],
    })

    mapping = infer_column_mapping(df)

    assert mapping["date"] == "OrderDate"
    assert mapping["sales"] == "Sales Amnt"
    assert mapping["store_id"] == "StoreNum"
    assert mapping["product_id"] == "Prodct SKU"
    assert mapping["category"] == "Product Catgory"
    assert mapping["quantity"] == "UnitsSold"


def test_item_column_uses_numbers_as_product_id() -> None:
    df = pd.DataFrame({
        "Date": ["2024-01-01"],
        "Sales": [125.50],
        "Item": [1001],
    })

    mapping = infer_column_mapping(df)

    assert mapping["product_id"] == "Item"
    assert "product_name" not in mapping


def test_item_column_uses_text_as_product_name() -> None:
    df = pd.DataFrame({
        "Date": ["2024-01-01"],
        "Sales": [125.50],
        "Item": ["Blue Shirt"],
    })

    mapping = infer_column_mapping(df)

    assert mapping["product_name"] == "Item"
    assert "product_id" not in mapping


def test_map_to_standard_schema_creates_product_id_from_product_name() -> None:
    df = pd.DataFrame({
        "Date": ["2024-01-01", "2024-01-02"],
        "Sales": [125.50, 200.00],
        "Product": ["Blue Shirt", "Red Shirt"],
    })

    standardized = map_to_standard_schema(df)

    assert list(standardized["product_id"]) == [1, 2]
    assert list(standardized["product_name"]) == ["Blue Shirt", "Red Shirt"]


if __name__ == "__main__":
    test_standardize_column_names_handles_common_retail_headers()
    test_fuzzy_mapping_handles_typos_and_camel_case_headers()
    test_item_column_uses_numbers_as_product_id()
    test_item_column_uses_text_as_product_name()
    test_map_to_standard_schema_creates_product_id_from_product_name()
    print("Schema mapping tests passed.")
