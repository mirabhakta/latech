import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.forecast_service import get_future_forecast, run_forecast_pipeline, shape_fast_kpi_payload


def small_forecast_dataset() -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=6, freq="D"),
        "store": [1, 1, 1, 1, 1, 1],
        "item": [101, 101, 101, 101, 101, 101],
        "sales": [10, 12, 11, 13, 14, 15],
    })


def test_run_forecast_pipeline_handles_small_dataset_without_lightgbm_crash() -> None:
    result = run_forecast_pipeline(small_forecast_dataset(), horizon_days=90)

    assert "winner" in result
    assert result["comparison_table"]
    assert result["winner"] in {row["method_name"] for row in result["comparison_table"]}


def test_get_future_forecast_uses_simple_fallback_for_small_dataset() -> None:
    result = get_future_forecast(small_forecast_dataset(), future_days=3)

    assert result["method"] == "simple_last_value_future"
    assert result["future_days"] == 3
    assert len(result["forecast_records"]) == 3
    assert result["forecast_records"][0]["prediction"] == 15


def test_get_future_forecast_fast_mode_skips_lightgbm_training() -> None:
    result = get_future_forecast(small_forecast_dataset(), future_days=3, fast=True)

    assert result["method"] == "simple_last_value_future"
    assert result["future_days"] == 3
    assert len(result["forecast_records"]) == 3


def test_shape_fast_kpi_payload_does_not_require_model_training() -> None:
    result = shape_fast_kpi_payload(small_forecast_dataset())

    assert result["total_sales"] == 75
    assert result["forecast_direction"] == "increasing"
    assert result["winner_model"] == "fast_upload_summary"
    assert result["mae"] is None


if __name__ == "__main__":
    test_run_forecast_pipeline_handles_small_dataset_without_lightgbm_crash()
    test_get_future_forecast_uses_simple_fallback_for_small_dataset()
    test_get_future_forecast_fast_mode_skips_lightgbm_training()
    test_shape_fast_kpi_payload_does_not_require_model_training()
    print("Small dataset forecasting tests passed.")
