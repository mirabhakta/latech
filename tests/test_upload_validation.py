import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.processor import validate_uploaded_data


def expect_upload_error(df: pd.DataFrame, expected_text: str) -> None:
    try:
        validate_uploaded_data(df)
    except ValueError as error:
        assert expected_text in str(error)
        return

    raise AssertionError("Expected validate_uploaded_data() to raise ValueError.")


def test_valid_upload_accepts_common_column_names() -> None:
    df = pd.DataFrame({
        "Order Date": ["2024-01-01", "2024-01-02"],
        "Revenue": [125.50, 200.00],
        "Store": ["A", "B"],
    })

    mapping = validate_uploaded_data(df)

    assert mapping["date"] == "Order Date"
    assert mapping["sales"] == "Revenue"
    assert mapping["store_id"] == "Store"


def test_upload_rejects_missing_sales_column() -> None:
    df = pd.DataFrame({
        "Order Date": ["2024-01-01"],
        "Store": ["A"],
    })

    expect_upload_error(df, "Missing: sales")


def test_upload_rejects_invalid_dates() -> None:
    df = pd.DataFrame({
        "Order Date": ["not-a-date"],
        "Sales": [125.50],
    })

    expect_upload_error(df, "invalid dates")


def test_upload_rejects_non_numeric_sales() -> None:
    df = pd.DataFrame({
        "Order Date": ["2024-01-01"],
        "Sales": ["one hundred"],
    })

    expect_upload_error(df, "non-numeric sales")


if __name__ == "__main__":
    test_valid_upload_accepts_common_column_names()
    test_upload_rejects_missing_sales_column()
    test_upload_rejects_invalid_dates()
    test_upload_rejects_non_numeric_sales()
    print("Upload validation tests passed.")
