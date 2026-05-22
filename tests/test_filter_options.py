import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.processor import FILTER_OPTION_KEYS, generate_filter_options, validate_filter_options_shape


def test_generate_filter_options_returns_sorted_values_and_date_range() -> None:
    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-02-01", "2024-01-01", "2024-03-01"]),
        "store_id": [2, 1, 2],
        "category": ["Shirts", "Accessories", "Shirts"],
        "region": ["South", "North", "South"],
    })

    options = generate_filter_options(df)

    assert options["stores"] == [1, 2]
    assert options["categories"] == ["Accessories", "Shirts"]
    assert options["regions"] == ["North", "South"]
    assert options["start_date"] == pd.Timestamp("2024-01-01")
    assert options["end_date"] == pd.Timestamp("2024-03-01")
    assert list(options.keys()) == FILTER_OPTION_KEYS
    assert validate_filter_options_shape(options) is True


def test_generate_filter_options_handles_missing_region_column() -> None:
    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01"]),
        "store_id": [1],
        "category": ["Shirts"],
    })

    options = generate_filter_options(df)

    assert options["regions"] == []
    assert options["start_date"] == pd.Timestamp("2024-01-01")
    assert options["end_date"] == pd.Timestamp("2024-01-01")
    assert validate_filter_options_shape(options) is True


def test_generate_filter_options_ignores_blank_filter_values() -> None:
    df = pd.DataFrame({
        "date": ["2024-01-01", None],
        "store_id": [1, None],
        "category": ["Shirts", None],
        "region": ["South", None],
    })

    options = generate_filter_options(df)

    assert options["stores"] == [1]
    assert options["categories"] == ["Shirts"]
    assert options["regions"] == ["South"]
    assert options["start_date"] == pd.Timestamp("2024-01-01")
    assert options["end_date"] == pd.Timestamp("2024-01-01")
    assert validate_filter_options_shape(options) is True


def test_validate_filter_options_shape_rejects_missing_keys() -> None:
    bad_options = {
        "stores": [1],
        "categories": ["Shirts"],
        "regions": [],
        "start_date": pd.Timestamp("2024-01-01"),
    }

    try:
        validate_filter_options_shape(bad_options)
    except ValueError as error:
        assert "exactly these keys" in str(error)
        return

    raise AssertionError("Expected missing filter key to raise ValueError.")


def test_validate_filter_options_shape_rejects_wrong_value_types() -> None:
    bad_options = {
        "stores": "1",
        "categories": ["Shirts"],
        "regions": [],
        "start_date": pd.Timestamp("2024-01-01"),
        "end_date": pd.Timestamp("2024-01-01"),
    }

    try:
        validate_filter_options_shape(bad_options)
    except ValueError as error:
        assert "'stores' must be a list" in str(error)
        return

    raise AssertionError("Expected wrong filter value type to raise ValueError.")


if __name__ == "__main__":
    test_generate_filter_options_returns_sorted_values_and_date_range()
    test_generate_filter_options_handles_missing_region_column()
    test_generate_filter_options_ignores_blank_filter_values()
    test_validate_filter_options_shape_rejects_missing_keys()
    test_validate_filter_options_shape_rejects_wrong_value_types()
    print("Filter option tests passed.")
