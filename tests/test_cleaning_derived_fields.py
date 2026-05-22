import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.processor import add_derived_fields, clean_standard_values, load_and_clean_data


def test_clean_standard_values_converts_dates_numbers_and_text() -> None:
    df = pd.DataFrame({
        "date": ["2024-01-01"],
        "sales": ["100.50"],
        "quantity": [None],
        "profit": ["20.25"],
        "transaction_count": ["3"],
        "product_name": ["  Blue Shirt  "],
        "category": [None],
        "region": ["  South  "],
    })

    clean_df = clean_standard_values(df)

    assert pd.api.types.is_datetime64_any_dtype(clean_df["date"])
    assert clean_df.loc[0, "sales"] == 100.50
    assert clean_df.loc[0, "quantity"] == 100.50
    assert clean_df.loc[0, "profit"] == 20.25
    assert clean_df.loc[0, "transaction_count"] == 3
    assert clean_df.loc[0, "product_name"] == "Blue Shirt"
    assert clean_df.loc[0, "category"] == "Unknown"
    assert clean_df.loc[0, "region"] == "South"


def test_add_derived_fields_creates_time_lag_rolling_and_velocity() -> None:
    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-01-08", "2024-01-15", "2024-01-22"]),
        "product_id": [1, 1, 1, 1],
        "store_id": [10, 10, 10, 10],
        "sales": [100.0, 120.0, 80.0, 160.0],
    })

    derived_df = add_derived_fields(df)

    assert list(derived_df["Month"]) == [1, 1, 1, 1]
    assert list(derived_df["Year"]) == [2024, 2024, 2024, 2024]
    assert pd.isna(derived_df.loc[0, "sales_lag_1"])
    assert derived_df.loc[1, "sales_lag_1"] == 100.0
    assert derived_df.loc[3, "sales_lag_3"] == 100.0
    assert list(derived_df["rolling_avg_4w"]) == [100.0, 110.0, 100.0, 115.0]
    assert pd.isna(derived_df.loc[0, "quantity_velocity"])
    assert derived_df.loc[1, "quantity_velocity"] == 20.0


def test_load_and_clean_data_returns_clean_schema_with_derived_fields() -> None:
    df = pd.DataFrame({
        "Order Date": ["2024-01-08", "2024-01-01"],
        "Sales Amount": ["120", "100"],
        "Store No": [10, 10],
        "Product SKU": [1, 1],
        "Product": ["  Blue Shirt  ", "  Blue Shirt  "],
        "Category": [" Shirts ", " Shirts "],
        "Units_Sold": [2, 1],
    })

    clean_df = load_and_clean_data(df)

    assert list(clean_df["date"]) == list(pd.to_datetime(["2024-01-01", "2024-01-08"]))
    assert list(clean_df["sales"]) == [100, 120]
    assert list(clean_df["quantity"]) == [1, 2]
    assert list(clean_df["product_name"]) == ["Blue Shirt", "Blue Shirt"]
    assert list(clean_df["category"]) == ["Shirts", "Shirts"]
    assert "sales_lag_1" in clean_df.columns
    assert "rolling_avg_4w" in clean_df.columns
    assert "quantity_velocity" in clean_df.columns


if __name__ == "__main__":
    test_clean_standard_values_converts_dates_numbers_and_text()
    test_add_derived_fields_creates_time_lag_rolling_and_velocity()
    test_load_and_clean_data_returns_clean_schema_with_derived_fields()
    print("Cleaning and derived field tests passed.")
