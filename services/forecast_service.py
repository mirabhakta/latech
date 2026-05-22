"""Forecast service layer for the InventoryIQ FastAPI backend.

utils/forecasting.py functions into clean service calls 
that FastAPI routes can call, avoiding any business logic.
"""

from __future__ import annotations

import pandas as pd

from utils.forecasting import (
    FEATURE_REGRESSION_LAGS,
    FEATURE_REGRESSION_ROLLING_WINDOWS,
    LIGHTGBM_LAGS,
    LIGHTGBM_ROLLING_WINDOWS,
    SIMPLE_FUTURE_METHOD,
    add_mase_to_results,
    build_lightgbm_future_forecast,
    build_simple_future_forecast,
    compare_models,
    prepare_forecast_input,
    run_feature_regression,
    run_lightgbm_global_lag,
    run_naive_baseline,
    run_rolling_average_baseline,
)


DEFAULT_HORIZON_DAYS = 90
DEFAULT_FUTURE_DAYS = 30


def split_for_available_history(df: pd.DataFrame, horizon_days: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Andrew Garcia Leopold: hold out a smaller test window when uploads have limited history."""
    unique_dates = pd.Series(pd.to_datetime(df["date"]).dropna().unique()).sort_values().tolist()
    if len(unique_dates) < 2:
        raise ValueError("Need at least two dates to run a forecast comparison.")

    test_date_count = max(1, min(horizon_days, max(1, len(unique_dates) // 3)))
    test_dates = set(unique_dates[-test_date_count:])
    train_df = df[~df["date"].isin(test_dates)].copy()
    test_df = df[df["date"].isin(test_dates)].copy()

    if train_df.empty or test_df.empty:
        raise ValueError("Not enough rows to create a train/test forecast split.")

    return train_df, test_df


def choose_lightgbm_features(train_df: pd.DataFrame, group_cols: list[str]) -> tuple[list[int], list[int]]:
    """Andrew Garcia Leopold: use only lag features that the uploaded history can support."""
    max_group_rows = int(train_df.groupby(group_cols).size().max())
    lags = [lag for lag in LIGHTGBM_LAGS if lag < max_group_rows]
    windows = [window for window in LIGHTGBM_ROLLING_WINDOWS if window <= max_group_rows]
    return lags, windows


def choose_regression_features(train_df: pd.DataFrame, group_cols: list[str]) -> tuple[list[int], list[int]]:
    """Andrew Garcia Leopold: keep regression features small enough for short upload history."""
    max_group_rows = int(train_df.groupby(group_cols).size().max())
    lags = [lag for lag in FEATURE_REGRESSION_LAGS if lag < max_group_rows]
    windows = [window for window in FEATURE_REGRESSION_ROLLING_WINDOWS if window <= max_group_rows]
    return lags or [1], windows or [1]


def run_forecast_pipeline(df: pd.DataFrame, horizon_days: int = DEFAULT_HORIZON_DAYS) -> dict:
    """
    Runs all four forecasting models on DataFrame,
    benchmarks them, selects the strongest, and returns
    a payload the API route can return as JSON.

    Args:
        df: Clean retail DataFrame (retail_clean.csv schema)
        horizon_days: Number of days to hold out for testing (default 90)

    Returns:
        dict with keys: comparison_table, winner, metrics
    """
    prepared = prepare_forecast_input(df)

    group_cols = ["store", "item"]
    target_col = "sales"
    date_col = "date"
    train_df, test_df = split_for_available_history(prepared, horizon_days=horizon_days)

    naive = run_naive_baseline(train_df, test_df, group_cols, target_col, date_col)
    rolling = run_rolling_average_baseline(train_df, test_df, group_cols, target_col, date_col)
    results = [naive, rolling]

    regression_lags, regression_windows = choose_regression_features(train_df, group_cols)
    try:
        regression = run_feature_regression(
            train_df,
            test_df,
            group_cols,
            target_col,
            date_col,
            lags=regression_lags,
            rolling_windows=regression_windows,
        )
        results.append(regression)
    except ValueError:
        pass

    lightgbm_lags, lightgbm_windows = choose_lightgbm_features(train_df, group_cols)
    if lightgbm_lags and lightgbm_windows:
        try:
            lightgbm = run_lightgbm_global_lag(
                train_df,
                test_df,
                group_cols,
                target_col,
                date_col,
                lags=lightgbm_lags,
                rolling_windows=lightgbm_windows,
            )
            results.append(lightgbm)
        except ValueError:
            pass

    add_mase_to_results(results, train_df, group_cols, target_col, date_col)

    comparison = compare_models(results)
    winner_row = comparison[comparison["selected_winner"]].iloc[0]

    return {
        "winner": winner_row["method_name"],
        "metrics": {
            "mae": round(winner_row["mae"], 3),
            "rmse": round(winner_row["rmse"], 3),
            "mase": round(winner_row["mase"], 3) if "mase" in winner_row else None,
        },
        "comparison_table": comparison.drop(columns=["selected_winner"]).round(3).to_dict(orient="records"),
    }


def get_future_forecast(df: pd.DataFrame, future_days: int = DEFAULT_FUTURE_DAYS, fast: bool = False) -> dict:
    """
    Generates a forward-looking forecast using LightGBM trained
    on all available data. Used for the dashboard forecast chart.

    Args:
        df: Clean retail DataFrame (retail_clean.csv schema)
        future_days: Number of days to project forward (default 30)

    Returns:
        dict with keys: forecast_records, future_days, method
    """
    if fast:
        forecast_df = build_simple_future_forecast(df, future_days=future_days)
        return {
            "method": SIMPLE_FUTURE_METHOD,
            "future_days": future_days,
            "forecast_records": forecast_df.to_dict(orient="records"),
        }

    try:
        forecast_df = build_lightgbm_future_forecast(df, future_days=future_days)
        method = "lightgbm_global_lag"
    except ValueError:
        forecast_df = build_simple_future_forecast(df, future_days=future_days)
        method = SIMPLE_FUTURE_METHOD

    return {
        "method": method,
        "future_days": future_days,
        "forecast_records": forecast_df.to_dict(orient="records"),
    }


def shape_kpi_payload(df: pd.DataFrame, forecast_result: dict) -> dict:
    """
    KPI summary row for the dashboard from the DataFrame +
    forecast result. Returns total sales, forecast direction,
    and used model name.

    Args:
        df: Clean retail DataFrame
        forecast_result: Output from run_forecast_pipeline()

    Returns:
        dict with keys: total_sales, forecast_direction, winner_model, mae
    """
    total_sales = round(float(df["sales"].sum()), 2)

    forecast_records = forecast_result.get("forecast_records", [])
    if forecast_records:
        first_val = forecast_records[0].get("prediction", 0)
        last_val = forecast_records[-1].get("prediction", 0)
        if last_val > first_val * 1.05:
            direction = "increasing"
        elif last_val < first_val * 0.95:
            direction = "declining"
        else:
            direction = "flat"
    else:
        direction = "flat"

    return {
        "total_sales": total_sales,
        "forecast_direction": direction,
        "winner_model": forecast_result.get("winner", "unknown"),
        "mae": forecast_result.get("metrics", {}).get("mae"),
    }


def shape_fast_kpi_payload(df: pd.DataFrame) -> dict:
    """Andrew Garcia Leopold: build KPI cards without training a forecast model first."""
    prepared = prepare_forecast_input(df)
    total_sales = round(float(prepared["sales"].sum()), 2)

    daily_sales = prepared.groupby("date")["sales"].sum().sort_index()
    if len(daily_sales) >= 2:
        midpoint = max(1, len(daily_sales) // 2)
        earlier_average = float(daily_sales.iloc[:midpoint].mean())
        recent_average = float(daily_sales.iloc[midpoint:].mean())
        if recent_average > earlier_average * 1.05:
            direction = "increasing"
        elif recent_average < earlier_average * 0.95:
            direction = "declining"
        else:
            direction = "flat"
    else:
        direction = "flat"

    return {
        "total_sales": total_sales,
        "forecast_direction": direction,
        "winner_model": "fast_upload_summary",
        "mae": None,
    }
