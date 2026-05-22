import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.processor import prepare_retail_data


def test_prepare_retail_data_returns_clean_data_and_filter_contract() -> None:
    raw_upload = pd.DataFrame({
        "Invoice Date": ["2024-01-15", "2024-01-01", "2024-02-01"],
        "Sales Amount": ["150.00", "100.00", "200.00"],
        "Store No": [2, 1, 2],
        "Product SKU": [101, 101, 102],
        "Product": [" Blue Shirt ", " Blue Shirt ", "Red Hat"],
        "Category": [" Shirts ", " Shirts ", "Accessories"],
        "Units_Sold": [3, 2, 4],
        "Market": ["South", "North", "South"],
        "Net Profit": ["30", "20", "50"],
        "Order Count": [2, 1, 3],
    })

    prepared = prepare_retail_data(raw_upload)
    clean_df = prepared["data"]
    filters = prepared["filters"]

    assert set(prepared.keys()) == {
        "data",
        "filters",
        "column_mapping",
        "optional_fields",
    }
    assert set(filters.keys()) == {
        "stores",
        "categories",
        "regions",
        "start_date",
        "end_date",
    }

    assert list(clean_df["date"]) == list(pd.to_datetime([
        "2024-01-01",
        "2024-01-15",
        "2024-02-01",
    ]))
    assert list(clean_df["sales"]) == [100.0, 150.0, 200.0]
    assert list(clean_df["quantity"]) == [2, 3, 4]
    assert list(clean_df["category"]) == ["Shirts", "Shirts", "Accessories"]
    assert list(clean_df["region"]) == ["North", "South", "South"]
    assert "sales_lag_1" in clean_df.columns
    assert "rolling_avg_4w" in clean_df.columns
    assert "quantity_velocity" in clean_df.columns

    assert filters["stores"] == [1, 2]
    assert filters["categories"] == ["Accessories", "Shirts"]
    assert filters["regions"] == ["North", "South"]
    assert filters["start_date"] == pd.Timestamp("2024-01-01")
    assert filters["end_date"] == pd.Timestamp("2024-02-01")

    assert prepared["column_mapping"]["date"] == "Invoice Date"
    assert prepared["column_mapping"]["sales"] == "Sales Amount"
    assert prepared["column_mapping"]["region"] == "Market"
    assert prepared["optional_fields"]["region"] == "active"
    assert prepared["optional_fields"]["profit"] == "active"
    assert prepared["optional_fields"]["transaction_count"] == "active"


if __name__ == "__main__":
    test_prepare_retail_data_returns_clean_data_and_filter_contract()
    print("Retail data preparation pipeline test passed.")
