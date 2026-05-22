from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_GROUP_COLS = ["store", "item"]
DEFAULT_TARGET_COL = "sales"
DEFAULT_DATE_COL = "date"
LIGHTGBM_METHOD = "lightgbm_global_lag"
SIMPLE_FUTURE_METHOD = "simple_last_value_future"
FEATURE_REGRESSION_METHOD = "feature_based_regression"
FEATURE_REGRESSION_LAGS = [1, 3, 7]
FEATURE_REGRESSION_ROLLING_WINDOWS = [3, 7, 28]
LIGHTGBM_LAGS = [1, 7, 14, 28, 56, 91, 364]
LIGHTGBM_ROLLING_WINDOWS = [7, 14, 28, 56]
EXPORT_COLUMNS = ["date", "store", "item", "actual", "prediction", "residual", "method_name"]


@dataclass
class ModelResult:
    method_name: str
    forecast_df: pd.DataFrame
    metrics: dict[str, float]


@dataclass
class ForecastArtifact:
    method_name: str
    forecast_df: pd.DataFrame
    metrics: dict[str, float]


# Category: Validation helpers
# Summary: Confirms a dataframe has the columns a forecasting function needs before training starts, so failures are clear instead of becoming confusing model errors later.
def validate_input_frame(
    df: pd.DataFrame,
    required_columns: list[str] | None = None,
) -> None:
    columns = required_columns or [DEFAULT_DATE_COL, *DEFAULT_GROUP_COLS, DEFAULT_TARGET_COL]
    missing_columns = [column for column in columns if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Input dataframe is missing required columns: {missing_columns}")
    if df.empty:
        raise ValueError("Input dataframe is empty.")


# Category: Evaluation helpers
# Summary: Calculates MAE and RMSE from actual versus predicted sales, giving the model comparison table simple accuracy scores without needing a separate utility module.
def evaluate_forecast(actual: pd.Series, prediction: pd.Series) -> dict[str, float]:
    actual_values = pd.to_numeric(actual, errors="coerce").astype(float)
    prediction_values = pd.to_numeric(prediction, errors="coerce").astype(float)
    valid_mask = actual_values.notna() & prediction_values.notna()
    if not valid_mask.any():
        raise ValueError("No valid actual/prediction pairs are available for evaluation.")

    errors = actual_values[valid_mask] - prediction_values[valid_mask]
    return {
        "mae": float(errors.abs().mean()),
        "rmse": float(np.sqrt(np.square(errors).mean())),
    }


# Category: Data prep
# Summary: Standardizes different retail CSV schemas so the forecasting functions can all expect date/store/item/sales columns instead of each function handling naming differences itself.
def prepare_forecast_input(
    df: pd.DataFrame,
    group_cols: list[str] | None = None,
    target_col: str = DEFAULT_TARGET_COL,
    date_col: str = DEFAULT_DATE_COL,
) -> pd.DataFrame:
    """Normalize supported retail schemas into date/store/item/sales shape."""
    prepared = df.copy()

    rename_map = {}
    if "store" not in prepared.columns and "store_id" in prepared.columns:
        rename_map["store_id"] = "store"
    if "item" not in prepared.columns and "product_id" in prepared.columns:
        rename_map["product_id"] = "item"
    if rename_map:
        prepared = prepared.rename(columns=rename_map)

    groups = group_cols or DEFAULT_GROUP_COLS
    validate_input_frame(prepared, required_columns=[date_col, *groups, target_col])

    prepared[date_col] = pd.to_datetime(prepared[date_col])
    prepared[target_col] = pd.to_numeric(prepared[target_col], errors="coerce")
    prepared = prepared.dropna(subset=[date_col, target_col, *groups]).copy()
    if prepared.empty:
        raise ValueError("Input dataframe has no usable rows after cleaning.")

    return prepared.sort_values([date_col, *groups]).reset_index(drop=True)


# Category: Data prep
# Summary: Splits historical data by time, not randomly, so the models train on older rows and are tested on newer rows like a real forecasting workflow.
def split_by_recent_dates(
    df: pd.DataFrame,
    horizon_days: int,
    date_col: str = DEFAULT_DATE_COL,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hold out the most recent N calendar days across all series."""
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive.")

    prepared = df.copy()
    prepared[date_col] = pd.to_datetime(prepared[date_col])
    max_date = prepared[date_col].max()
    cutoff = max_date - pd.Timedelta(days=horizon_days)
    train_df = prepared[prepared[date_col] <= cutoff].copy()
    test_df = prepared[prepared[date_col] > cutoff].copy()

    if train_df.empty or test_df.empty:
        raise ValueError(f"Not enough rows to split by the last {horizon_days} days.")

    return train_df, test_df


# Category: Evaluation helpers
# Summary: Calculates the scale used by MASE, which lets us say whether a model beats a simple seasonal comparison instead of only reporting raw error size.
def mase_scale(
    train_df: pd.DataFrame,
    group_cols: list[str] | None = None,
    target_col: str = DEFAULT_TARGET_COL,
    date_col: str = DEFAULT_DATE_COL,
    seasonal_period: int = 7,
) -> float:
    """Return a scale value for MASE, falling back safely when data is tiny."""
    groups = group_cols or DEFAULT_GROUP_COLS
    ordered = train_df.sort_values(date_col)
    seasonal_diffs = ordered.groupby(groups)[target_col].diff(seasonal_period).abs().dropna()
    scale = float(seasonal_diffs.mean()) if not seasonal_diffs.empty else 0.0
    if scale > 0:
        return scale

    one_step_diffs = ordered.groupby(groups)[target_col].diff(1).abs().dropna()
    fallback = float(one_step_diffs.mean()) if not one_step_diffs.empty else 0.0
    return fallback if fallback > 0 else 1.0


# Category: Evaluation helpers
# Summary: Adds MASE to every model result after MAE/RMSE are calculated, keeping all model scores comparable in one table.
def add_mase_to_results(
    results: list[ModelResult],
    train_df: pd.DataFrame,
    group_cols: list[str] | None = None,
    target_col: str = DEFAULT_TARGET_COL,
    date_col: str = DEFAULT_DATE_COL,
    seasonal_period: int = 7,
) -> None:
    scale = mase_scale(
        train_df=train_df,
        group_cols=group_cols,
        target_col=target_col,
        date_col=date_col,
        seasonal_period=seasonal_period,
    )
    for result in results:
        result.metrics["mase"] = result.metrics["mae"] / scale


# Category: Export helpers
# Summary: Wraps raw prediction values into the shared ModelResult object and calculates MAE/RMSE, so every model returns the same shape for comparison/export.
def _result_from_predictions(
    test_df: pd.DataFrame,
    predictions: pd.Series | np.ndarray,
    method_name: str,
    group_cols: list[str],
    target_col: str,
    date_col: str,
) -> ModelResult:
    forecast_df = test_df[[date_col, *group_cols, target_col]].copy()
    forecast_df["prediction"] = pd.Series(np.asarray(predictions), index=forecast_df.index).astype(float)
    forecast_df["prediction"] = forecast_df["prediction"].clip(lower=0)
    metrics = evaluate_forecast(forecast_df[target_col], forecast_df["prediction"])
    forecast_df = forecast_df.rename(columns={target_col: "actual"})

    return ModelResult(
        method_name=method_name,
        forecast_df=forecast_df,
        metrics=metrics,
    )


# Category: Required baseline models
# Summary: Predicts each store/item's next sales value using its latest known value; this is the simplest benchmark every smarter method should beat.
def run_naive_baseline(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    group_cols: list[str],
    target_col: str,
    date_col: str,
) -> ModelResult:
    validate_input_frame(train_df, required_columns=group_cols + [date_col, target_col])
    validate_input_frame(test_df, required_columns=group_cols + [date_col, target_col])

    last_seen = (
        train_df.sort_values(date_col)
        .groupby(group_cols, as_index=False)[target_col]
        .last()
        .rename(columns={target_col: "prediction"})
    )

    forecast_df = test_df[group_cols + [date_col, target_col]].merge(last_seen, on=group_cols, how="left")
    forecast_df["prediction"] = forecast_df["prediction"].fillna(train_df[target_col].median())
    metrics = evaluate_forecast(forecast_df[target_col], forecast_df["prediction"])

    return ModelResult(
        method_name="naive_last_value",
        forecast_df=forecast_df.rename(columns={target_col: "actual"}),
        metrics=metrics,
    )


# Category: Required baseline models
# Summary: Predicts future sales with each store/item's recent average, which smooths out day-to-day noise while staying easy to explain.
def run_rolling_average_baseline(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    group_cols: list[str],
    target_col: str,
    date_col: str,
    window: int = 3,
) -> ModelResult:
    validate_input_frame(train_df, required_columns=group_cols + [date_col, target_col])
    validate_input_frame(test_df, required_columns=group_cols + [date_col, target_col])
    if window <= 0:
        raise ValueError("window must be positive.")

    rolling_source = (
        train_df.sort_values(date_col)
        .groupby(group_cols)[target_col]
        .apply(lambda series: series.tail(window).mean())
        .reset_index(name="prediction")
    )

    forecast_df = test_df[group_cols + [date_col, target_col]].merge(
        rolling_source,
        on=group_cols,
        how="left",
    )
    forecast_df["prediction"] = forecast_df["prediction"].fillna(train_df[target_col].mean())
    metrics = evaluate_forecast(forecast_df[target_col], forecast_df["prediction"])

    return ModelResult(
        method_name=f"rolling_average_{window}",
        forecast_df=forecast_df.rename(columns={target_col: "actual"}),
        metrics=metrics,
    )


# Category: Shared feature engineering
# Summary: Adds calendar clues like weekday, month, and weekend flag so regression-style models can learn seasonal patterns from dates instead of treating dates as plain text.
def _add_calendar_features(data: pd.DataFrame, date_col: str) -> pd.DataFrame:
    dates = pd.to_datetime(data[date_col])
    featured = data.copy()
    featured["day_of_week"] = dates.dt.dayofweek
    featured["month"] = dates.dt.month
    featured["day_of_month"] = dates.dt.day
    featured["day_of_year"] = dates.dt.dayofyear
    featured["week_of_year"] = dates.dt.isocalendar().week.astype(int)
    featured["is_weekend"] = dates.dt.dayofweek.isin([5, 6]).astype(int)
    featured["time_index"] = (dates - dates.min()).dt.days
    return featured


# Category: Shared feature engineering
# Summary: Builds stable numeric IDs for store/item values when a model needs numbers rather than raw labels; this keeps repeated runs consistent.
def _make_group_maps(data: pd.DataFrame, group_cols: list[str]) -> dict[str, dict[Any, int]]:
    maps: dict[str, dict[Any, int]] = {}
    for col in group_cols:
        values = sorted(data[col].dropna().unique().tolist(), key=lambda value: str(value))
        maps[col] = {value: index for index, value in enumerate(values)}
    return maps


# Category: Shared feature engineering
# Summary: Adds the numeric store/item code columns created by _make_group_maps so models can use store and product identity as prediction clues.
def _add_group_code_features(
    data: pd.DataFrame,
    group_cols: list[str],
    group_maps: dict[str, dict[Any, int]],
) -> pd.DataFrame:
    featured = data.copy()
    for col in group_cols:
        featured[f"{col}_code"] = featured[col].map(group_maps[col]).fillna(-1).astype(int)
    return featured


# Category: Required baseline models
# Summary: Builds a scikit-learn regression model from lagged sales, rolling averages, and calendar indicators; this is the third required team method beyond naive and rolling average.
def run_feature_regression(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    group_cols: list[str] | None = None,
    target_col: str = DEFAULT_TARGET_COL,
    date_col: str = DEFAULT_DATE_COL,
    lags: list[int] | None = None,
    rolling_windows: list[int] | None = None,
) -> ModelResult:
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    groups = group_cols or DEFAULT_GROUP_COLS
    lag_values = lags or FEATURE_REGRESSION_LAGS
    window_values = rolling_windows or FEATURE_REGRESSION_ROLLING_WINDOWS
    train = prepare_forecast_input(train_df, groups, target_col, date_col)
    test = prepare_forecast_input(test_df, groups, target_col, date_col)

    model_frame, feature_cols, categorical_cols, numeric_cols = _build_regression_training_frame(
        data=train,
        group_cols=groups,
        target_col=target_col,
        date_col=date_col,
        lags=lag_values,
        rolling_windows=window_values,
    )
    if model_frame.empty:
        raise ValueError("Not enough history to train the feature-based regression model.")

    try:
        one_hot = OneHotEncoder(handle_unknown="ignore", sparse_output=True)
    except TypeError:
        one_hot = OneHotEncoder(handle_unknown="ignore", sparse=True)

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("one_hot", one_hot),
                    ]
                ),
                categorical_cols,
            ),
            (
                "numeric",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler(with_mean=False)),
                    ]
                ),
                numeric_cols,
            ),
        ],
        sparse_threshold=1.0,
    )
    model = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", Ridge(alpha=10.0, solver="lsqr")),
        ]
    )
    model.fit(model_frame[feature_cols], model_frame[target_col].astype(float))

    prediction_df = _recursive_regression_predictions(
        model=model,
        history_df=train,
        predict_dates=sorted(pd.to_datetime(test[date_col].unique())),
        predict_groups=test[groups].drop_duplicates().sort_values(groups).reset_index(drop=True),
        group_cols=groups,
        target_col=target_col,
        date_col=date_col,
        lags=lag_values,
        rolling_windows=window_values,
        feature_cols=feature_cols,
    )
    scored = test[[date_col, *groups, target_col]].merge(
        prediction_df[[date_col, *groups, "prediction"]],
        on=[date_col, *groups],
        how="left",
    )
    scored["prediction"] = scored["prediction"].fillna(float(train[target_col].median())).clip(lower=0)
    return _result_from_predictions(
        test_df=scored,
        predictions=scored["prediction"],
        method_name=FEATURE_REGRESSION_METHOD,
        group_cols=groups,
        target_col=target_col,
        date_col=date_col,
    )


# Category: Feature-based regression helpers
# Summary: Creates the training table for scikit-learn by adding past-sales clues and calendar/store/item indicators while keeping track of which columns are categorical versus numeric.
def _build_regression_training_frame(
    data: pd.DataFrame,
    group_cols: list[str],
    target_col: str,
    date_col: str,
    lags: list[int],
    rolling_windows: list[int],
) -> tuple[pd.DataFrame, list[str], list[str], list[str]]:
    featured = _add_calendar_features(data.sort_values([date_col, *group_cols]), date_col)
    grouped_target = featured.groupby(group_cols, group_keys=False)[target_col]

    for lag in lags:
        featured[f"lag_{lag}"] = grouped_target.shift(lag)

    shifted_target = grouped_target.shift(1)
    for window in rolling_windows:
        featured[f"rolling_mean_{window}"] = shifted_target.groupby(
            [featured[col] for col in group_cols]
        ).transform(lambda series: series.rolling(window=window, min_periods=1).mean())

    categorical_cols = [*group_cols, "day_of_week", "month"]
    numeric_cols = [
        "day_of_month",
        "day_of_year",
        "week_of_year",
        "is_weekend",
        "time_index",
        *[f"lag_{lag}" for lag in lags],
        *[f"rolling_mean_{window}" for window in rolling_windows],
    ]
    feature_cols = [*categorical_cols, *numeric_cols]
    return featured.dropna(subset=[target_col]).copy(), feature_cols, categorical_cols, numeric_cols


# Category: Feature-based regression helpers
# Summary: Builds one future/test row of scikit-learn features from the current date and that store/item's known history, without peeking at future actual sales.
def _regression_feature_row(
    group_values: dict[str, Any],
    current_date: pd.Timestamp,
    min_date: pd.Timestamp,
    history_values: list[float],
    group_cols: list[str],
    lags: list[int],
    rolling_windows: list[int],
) -> dict[str, Any]:
    row: dict[str, Any] = {col: group_values[col] for col in group_cols}
    row.update(
        {
            "day_of_week": current_date.dayofweek,
            "month": current_date.month,
            "day_of_month": current_date.day,
            "day_of_year": current_date.dayofyear,
            "week_of_year": int(current_date.isocalendar().week),
            "is_weekend": int(current_date.dayofweek in [5, 6]),
            "time_index": int((current_date - min_date).days),
        }
    )
    for lag in lags:
        row[f"lag_{lag}"] = history_values[-lag] if len(history_values) >= lag else np.nan
    for window in rolling_windows:
        if history_values:
            row[f"rolling_mean_{window}"] = float(np.mean(history_values[-window:]))
        else:
            row[f"rolling_mean_{window}"] = np.nan
    return row


# Category: Feature-based regression helpers
# Summary: Predicts each holdout date one day at a time and feeds predictions back into history, which mimics real forecasting where future actuals are unavailable.
def _recursive_regression_predictions(
    model,
    history_df: pd.DataFrame,
    predict_dates: list[pd.Timestamp],
    predict_groups: pd.DataFrame,
    group_cols: list[str],
    target_col: str,
    date_col: str,
    lags: list[int],
    rolling_windows: list[int],
    feature_cols: list[str],
) -> pd.DataFrame:
    histories = {
        tuple(group_key if isinstance(group_key, tuple) else (group_key,)): group.sort_values(date_col)[target_col].astype(float).tolist()
        for group_key, group in history_df.groupby(group_cols)
    }
    min_date = history_df[date_col].min()
    prediction_frames: list[pd.DataFrame] = []

    for current_date in predict_dates:
        current_ts = pd.Timestamp(current_date)
        rows = []
        keys = []
        for series in predict_groups.itertuples(index=False):
            group_values = {col: getattr(series, col) for col in group_cols}
            key = tuple(group_values[col] for col in group_cols)
            rows.append(
                _regression_feature_row(
                    group_values=group_values,
                    current_date=current_ts,
                    min_date=min_date,
                    history_values=histories.get(key, []),
                    group_cols=group_cols,
                    lags=lags,
                    rolling_windows=rolling_windows,
                )
            )
            keys.append(key)

        feature_df = pd.DataFrame(rows)[feature_cols]
        predictions = np.clip(model.predict(feature_df), a_min=0, a_max=None)
        date_predictions = predict_groups.copy()
        date_predictions[date_col] = current_ts
        date_predictions["prediction"] = predictions
        prediction_frames.append(date_predictions)

        for key, prediction in zip(keys, predictions):
            histories.setdefault(key, []).append(float(prediction))

    return pd.concat(prediction_frames, ignore_index=True)


# Category: LightGBM helpers
# Summary: Builds the LightGBM training table from store/item codes, calendar clues, lagged sales, and rolling statistics because LightGBM needs a flat feature table.
def _build_lightgbm_training_frame(
    data: pd.DataFrame,
    group_cols: list[str],
    target_col: str,
    date_col: str,
    lags: list[int],
    rolling_windows: list[int],
) -> tuple[pd.DataFrame, list[str], dict[str, dict[Any, int]]]:
    group_maps = _make_group_maps(data, group_cols)
    featured = _add_calendar_features(data.sort_values([date_col, *group_cols]), date_col)
    featured = _add_group_code_features(featured, group_cols, group_maps)
    grouped_target = featured.groupby(group_cols, group_keys=False)[target_col]

    for lag in lags:
        featured[f"lag_{lag}"] = grouped_target.shift(lag)

    featured["_shifted_target"] = grouped_target.shift(1)
    for window in rolling_windows:
        featured[f"rolling_mean_{window}"] = featured.groupby(group_cols)["_shifted_target"].transform(
            lambda series: series.rolling(window=window, min_periods=1).mean()
        )
        featured[f"rolling_std_{window}"] = featured.groupby(group_cols)["_shifted_target"].transform(
            lambda series: series.rolling(window=window, min_periods=2).std()
        )

    feature_cols = [
        *[f"{col}_code" for col in group_cols],
        "day_of_week",
        "month",
        "day_of_month",
        "day_of_year",
        "week_of_year",
        "is_weekend",
        "time_index",
        *[f"lag_{lag}" for lag in lags],
        *[f"rolling_mean_{window}" for window in rolling_windows],
        *[f"rolling_std_{window}" for window in rolling_windows],
    ]

    model_frame = featured.dropna(subset=feature_cols + [target_col]).copy()
    return model_frame, feature_cols, group_maps


# Category: LightGBM helpers
# Summary: Creates one LightGBM feature row for a single store/item/date using only the history available at that point in the forecast.
def _lightgbm_feature_row(
    group_values: dict[str, Any],
    current_date: pd.Timestamp,
    min_date: pd.Timestamp,
    history_values: list[float],
    group_cols: list[str],
    group_maps: dict[str, dict[Any, int]],
    lags: list[int],
    rolling_windows: list[int],
) -> dict[str, float | int]:
    row: dict[str, float | int] = {}
    for col in group_cols:
        row[f"{col}_code"] = group_maps[col].get(group_values[col], -1)

    row.update(
        {
            "day_of_week": current_date.dayofweek,
            "month": current_date.month,
            "day_of_month": current_date.day,
            "day_of_year": current_date.dayofyear,
            "week_of_year": int(current_date.isocalendar().week),
            "is_weekend": int(current_date.dayofweek in [5, 6]),
            "time_index": int((current_date - min_date).days),
        }
    )

    for lag in lags:
        row[f"lag_{lag}"] = history_values[-lag] if len(history_values) >= lag else np.nan

    for window in rolling_windows:
        if history_values:
            window_values = np.array(history_values[-window:], dtype=float)
            row[f"rolling_mean_{window}"] = float(window_values.mean())
            row[f"rolling_std_{window}"] = float(window_values.std(ddof=1)) if len(window_values) >= 2 else np.nan
        else:
            row[f"rolling_mean_{window}"] = np.nan
            row[f"rolling_std_{window}"] = np.nan

    return row


# Category: LightGBM helpers
# Summary: Trains the actual LightGBM regressor and returns the model plus metadata needed to build matching prediction rows later.
def _fit_lightgbm(
    train_df: pd.DataFrame,
    group_cols: list[str],
    target_col: str,
    date_col: str,
    lags: list[int],
    rolling_windows: list[int],
):
    try:
        from lightgbm import LGBMRegressor
    except ImportError as exc:
        raise ImportError(
            "LightGBM is not installed. Run `pip install lightgbm` or install this repo's requirements."
        ) from exc

    model_frame, feature_cols, group_maps = _build_lightgbm_training_frame(
        data=train_df,
        group_cols=group_cols,
        target_col=target_col,
        date_col=date_col,
        lags=lags,
        rolling_windows=rolling_windows,
    )
    if model_frame.empty:
        raise ValueError(
            "Not enough history to train LightGBM with the requested lag features. "
            "Use more data or smaller lags."
        )

    model = LGBMRegressor(
        objective="regression",
        n_estimators=120,
        learning_rate=0.05,
        num_leaves=63,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=0.2,
        random_state=42,
        n_jobs=-1,
        verbosity=-1,
    )
    model.fit(model_frame[feature_cols], model_frame[target_col].astype(float))
    feature_medians = model_frame[feature_cols].median(numeric_only=True)
    return model, feature_cols, feature_medians, group_maps


# Category: LightGBM helpers
# Summary: Runs LightGBM predictions through time recursively, feeding each prediction back into history so later predictions do not cheat with future actuals.
def _recursive_lightgbm_predictions(
    model,
    feature_cols: list[str],
    feature_medians: pd.Series,
    group_maps: dict[str, dict[Any, int]],
    history_df: pd.DataFrame,
    predict_dates: list[pd.Timestamp],
    predict_groups: pd.DataFrame,
    group_cols: list[str],
    target_col: str,
    date_col: str,
    lags: list[int],
    rolling_windows: list[int],
) -> pd.DataFrame:
    histories = {
        tuple(group_key if isinstance(group_key, tuple) else (group_key,)): group.sort_values(date_col)[target_col].astype(float).tolist()
        for group_key, group in history_df.groupby(group_cols)
    }
    min_date = history_df[date_col].min()
    prediction_frames: list[pd.DataFrame] = []

    for current_date in predict_dates:
        current_ts = pd.Timestamp(current_date)
        rows = []
        keys = []
        for series in predict_groups.itertuples(index=False):
            group_values = {col: getattr(series, col) for col in group_cols}
            key = tuple(group_values[col] for col in group_cols)
            history_values = histories.get(key, [])
            rows.append(
                _lightgbm_feature_row(
                    group_values=group_values,
                    current_date=current_ts,
                    min_date=min_date,
                    history_values=history_values,
                    group_cols=group_cols,
                    group_maps=group_maps,
                    lags=lags,
                    rolling_windows=rolling_windows,
                )
            )
            keys.append(key)

        feature_df = pd.DataFrame(rows)
        feature_df = feature_df[feature_cols].fillna(feature_medians)
        predictions = np.clip(model.predict(feature_df), a_min=0, a_max=None)

        date_predictions = predict_groups.copy()
        date_predictions[date_col] = current_ts
        date_predictions["prediction"] = predictions
        prediction_frames.append(date_predictions)

        for key, prediction in zip(keys, predictions):
            histories.setdefault(key, []).append(float(prediction))

    return pd.concat(prediction_frames, ignore_index=True)


# Category: LightGBM advanced model
# Summary: Fits the global LightGBM lag model on training rows and scores it on holdout rows; this is the advanced tree-based benchmark beyond the required scikit-learn methods.
def run_lightgbm_global_lag(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    group_cols: list[str] | None = None,
    target_col: str = DEFAULT_TARGET_COL,
    date_col: str = DEFAULT_DATE_COL,
    lags: list[int] | None = None,
    rolling_windows: list[int] | None = None,
) -> ModelResult:
    """Fit a global LightGBM lag model and backtest it on test_df."""
    groups = group_cols or DEFAULT_GROUP_COLS
    lag_values = lags or LIGHTGBM_LAGS
    window_values = rolling_windows or LIGHTGBM_ROLLING_WINDOWS
    train = prepare_forecast_input(train_df, groups, target_col, date_col)
    test = prepare_forecast_input(test_df, groups, target_col, date_col)

    model, feature_cols, feature_medians, group_maps = _fit_lightgbm(
        train_df=train,
        group_cols=groups,
        target_col=target_col,
        date_col=date_col,
        lags=lag_values,
        rolling_windows=window_values,
    )
    predict_groups = test[groups].drop_duplicates().sort_values(groups).reset_index(drop=True)
    predict_dates = sorted(pd.to_datetime(test[date_col].unique()))
    prediction_df = _recursive_lightgbm_predictions(
        model=model,
        feature_cols=feature_cols,
        feature_medians=feature_medians,
        group_maps=group_maps,
        history_df=train,
        predict_dates=predict_dates,
        predict_groups=predict_groups,
        group_cols=groups,
        target_col=target_col,
        date_col=date_col,
        lags=lag_values,
        rolling_windows=window_values,
    )

    scored = test[[date_col, *groups, target_col]].merge(
        prediction_df[[date_col, *groups, "prediction"]],
        on=[date_col, *groups],
        how="left",
    )
    scored["prediction"] = scored["prediction"].fillna(float(train[target_col].median()))
    return _result_from_predictions(
        test_df=scored,
        predictions=scored["prediction"],
        method_name=LIGHTGBM_METHOD,
        group_cols=groups,
        target_col=target_col,
        date_col=date_col,
    )


# Category: LightGBM advanced model
# Summary: Trains LightGBM on all known data and produces true future forecast rows for dashboard charts where actual/residual are blank because the future has not happened yet.
def build_lightgbm_future_forecast(
    df: pd.DataFrame,
    future_days: int,
    group_cols: list[str] | None = None,
    target_col: str = DEFAULT_TARGET_COL,
    date_col: str = DEFAULT_DATE_COL,
    lags: list[int] | None = None,
    rolling_windows: list[int] | None = None,
) -> pd.DataFrame:
    """Train LightGBM on all known rows and produce future-dated CSV rows."""
    if future_days <= 0:
        raise ValueError("future_days must be positive.")

    groups = group_cols or DEFAULT_GROUP_COLS
    lag_values = lags or LIGHTGBM_LAGS
    window_values = rolling_windows or LIGHTGBM_ROLLING_WINDOWS
    train = prepare_forecast_input(df, groups, target_col, date_col)
    model, feature_cols, feature_medians, group_maps = _fit_lightgbm(
        train_df=train,
        group_cols=groups,
        target_col=target_col,
        date_col=date_col,
        lags=lag_values,
        rolling_windows=window_values,
    )

    max_date = train[date_col].max()
    predict_dates = list(pd.date_range(start=max_date + pd.Timedelta(days=1), periods=future_days, freq="D"))
    predict_groups = train[groups].drop_duplicates().sort_values(groups).reset_index(drop=True)
    prediction_df = _recursive_lightgbm_predictions(
        model=model,
        feature_cols=feature_cols,
        feature_medians=feature_medians,
        group_maps=group_maps,
        history_df=train,
        predict_dates=predict_dates,
        predict_groups=predict_groups,
        group_cols=groups,
        target_col=target_col,
        date_col=date_col,
        lags=lag_values,
        rolling_windows=window_values,
    )
    return _future_predictions_to_export(prediction_df, groups, date_col, LIGHTGBM_METHOD)


def build_simple_future_forecast(
    df: pd.DataFrame,
    future_days: int,
    group_cols: list[str] | None = None,
    target_col: str = DEFAULT_TARGET_COL,
    date_col: str = DEFAULT_DATE_COL,
) -> pd.DataFrame:
    """Andrew Garcia Leopold: build a fast fallback forecast for small uploaded datasets."""
    if future_days <= 0:
        raise ValueError("future_days must be positive.")

    groups = group_cols or DEFAULT_GROUP_COLS
    prepared = prepare_forecast_input(df, groups, target_col, date_col)
    last_values = (
        prepared.sort_values(date_col)
        .groupby(groups, as_index=False)[target_col]
        .last()
        .rename(columns={target_col: "prediction"})
    )

    max_date = prepared[date_col].max()
    predict_dates = pd.date_range(start=max_date + pd.Timedelta(days=1), periods=future_days, freq="D")
    rows = []
    for current_date in predict_dates:
        day_predictions = last_values.copy()
        day_predictions[date_col] = current_date
        rows.append(day_predictions)

    prediction_df = pd.concat(rows, ignore_index=True)
    return _future_predictions_to_export(prediction_df, groups, date_col, SIMPLE_FUTURE_METHOD)


# Category: Export helpers
# Summary: Converts future prediction tables into the team's seven-column forecasts.csv contract, leaving actual/residual blank because they do not exist for future dates.
def _future_predictions_to_export(
    prediction_df: pd.DataFrame,
    group_cols: list[str],
    date_col: str,
    method_name: str,
) -> pd.DataFrame:
    export_df = prediction_df[[date_col, *group_cols, "prediction"]].copy()
    rename_map = {date_col: "date"}
    if group_cols[0] != "store":
        rename_map[group_cols[0]] = "store"
    if group_cols[1] != "item":
        rename_map[group_cols[1]] = "item"
    export_df = export_df.rename(columns=rename_map)
    export_df["actual"] = pd.NA
    export_df["residual"] = pd.NA
    export_df["method_name"] = method_name
    return export_df[EXPORT_COLUMNS].sort_values(["date", "store", "item"]).reset_index(drop=True)


# Category: Evaluation helpers
# Summary: Takes the metrics from each model, ranknig best -> worst, and marks the selected winner for the dashboard/model-accuracy view.
def compare_models(results: list[ModelResult]) -> pd.DataFrame:
    if not results:
        raise ValueError("At least one model result is required.")

    rows = []
    for result in results:
        row = {
            "method_name": result.method_name,
            "mae": result.metrics["mae"],
            "rmse": result.metrics["rmse"],
        }
        if "mase" in result.metrics:
            row["mase"] = result.metrics["mase"]
        rows.append(row)

    comparison_df = pd.DataFrame(rows)
    sort_cols = ["mase", "mae", "rmse"] if "mase" in comparison_df.columns else ["mae", "rmse"]
    comparison_df = comparison_df.sort_values(sort_cols, ascending=True).reset_index(drop=True)
    comparison_df["selected_winner"] = comparison_df.index == 0
    return comparison_df


# Category: Export helpers
# Summary: Packages a model's forecasts and metrics into a small reusable artifact object so downstream code can pass results around consistently.
def build_forecast_artifact(result: ModelResult) -> ForecastArtifact:
    return ForecastArtifact(
        method_name=result.method_name,
        forecast_df=result.forecast_df.copy(),
        metrics=result.metrics.copy(),
    )
