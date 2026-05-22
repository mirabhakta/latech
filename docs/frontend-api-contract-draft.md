# Frontend API Contract (Current Draft)

This is the current frontend-facing API contract based on the FastAPI **route layer** now in the repo.

**What is confirmed from route code:**
- route paths
- HTTP methods
- file upload requirement
- query parameters
- top-level error behavior

**What is still provisional and should be confirmed by James:**
- exact success-response field names returned by service functions such as `run_forecast_pipeline(...)`, `get_future_forecast(...)`, and `shape_kpi_payload(...)`
- exact field names inside each alert object returned from `run_all_alerts(...)`

The goal of this note is to let frontend work continue without guessing request format, while clearly marking which success payload details still need final confirmation.

## Shared request rules

These rules are confirmed from the current FastAPI route code:

- All listed endpoints use `POST`.
- All listed endpoints require a CSV file upload.
- The CSV is sent as `multipart/form-data` with field name **`file`**.
- Numeric controls like `horizon_days`, `future_days`, and alert thresholds are currently passed as **query parameters**.
- Current error behavior:
  - `400` = uploaded file could not be parsed as CSV.
  - `422` = business-logic or validation failure, returned in `detail`.

## 1) Forecast benchmark run

### Request
- **Route:** `/forecast/run`
- **Method:** `POST`
- **Content-Type:** `multipart/form-data`
- **Body fields:**
  - `file` (required CSV)
- **Query params:**
  - `horizon_days` (integer, default `90`)

### Success response
**Confirmed:** the route returns the output of `run_forecast_pipeline(df, horizon_days=...)`. The response is a JSON object representing forecast/benchmark results.  
**Provisional:** exact field names inside that object still need confirmation from James.

**Current expected shape for frontend planning only:**

```json
{
  "winning_model": "LightGBM",
  "benchmark": [
    {
      "model": "Prophet",
      "mae": 123.45,
      "rmse": 150.22
    }
  ],
  "forecast": [
    {
      "date": "2026-05-18",
      "predicted_sales": 245.1
    }
  ]
}
```

### Error responses
- `400`: `{"detail": "Could not parse uploaded file as CSV."}`
- `422`: `{"detail": "...validation or business logic message..."}`

***

## 2) Future forecast for dashboard chart

### Request
- **Route:** `/forecast/future`
- **Method:** `POST`
- **Content-Type:** `multipart/form-data`
- **Body fields:**
  - `file` (required CSV)
- **Query params:**
  - `future_days` (integer, default `30`)

### Success response
**Confirmed:** the route returns the output of `get_future_forecast(df, future_days=...)`.  
**Provisional:** exact response keys still need confirmation from James.

**Current expected shape for frontend planning only:**

```json
{
  "future_days": 30,
  "forecast": [
    {
      "date": "2026-05-18",
      "predicted_sales": 245.1
    }
  ],
  "direction": "up"
}
```

### Error responses
- `400`: `{"detail": "Could not parse uploaded file as CSV."}`
- `422`: `{"detail": "...validation or business logic message..."}`

***

## 3) KPI payload for dashboard cards

### Request
- **Route:** `/forecast/kpis`
- **Method:** `POST`
- **Content-Type:** `multipart/form-data`
- **Body fields:**
  - `file` (required CSV)
- **Query params:**
  - `future_days` (integer, default `30`)

### Success response
**Confirmed:** the route computes `forecast_result = get_future_forecast(...)` and then returns `shape_kpi_payload(df, forecast_result)`.  
**Confirmed from the route docstring:** intended KPI content includes total sales, forecast direction, winning model, and MAE.  
**Provisional:** exact JSON keys still need confirmation from James.

**Current expected shape for frontend planning only:**

```json
{
  "total_sales": 125000.33,
  "forecast_direction": "up",
  "winning_model": "LightGBM",
  "mae": 118.42
}
```

### Error responses
- `400`: `{"detail": "Could not parse uploaded file as CSV."}`
- `422`: `{"detail": "...validation or business logic message..."}`

***

## 4) Alerts for dashboard alert panel

### Request
- **Route:** `/alerts/run`
- **Method:** `POST`
- **Content-Type:** `multipart/form-data`
- **Body fields:**
  - `file` (required CSV)
- **Query params:**
  - `anomaly_std` (float, default `2.0`)
  - `decline_pct` (float, default `0.20`)
  - `margin_floor` (float, default `0.0`)

### Success response
**Confirmed:** if alerts exist, the route returns an object with top-level keys `alerts` and `total`.  
**Confirmed:** if no alerts exist, the route returns:

```json
{
  "alerts": [],
  "total": 0
}
```

**Confirmed:** `alerts` is a list of row objects because the route uses `alerts_df.to_dict(orient="records")`.  
**Provisional:** the exact keys inside each alert object still depend on `run_all_alerts(...)` and should be confirmed by James.

**Current expected shape for frontend planning only:**

```json
{
  "alerts": [
    {
      "alert_type": "decline",
      "severity": "high",
      "message": "Sales declined 24% week-over-week"
    }
  ],
  "total": 1
}
```

### Error responses
- `400`: `{"detail": "Could not parse uploaded file as CSV."}`
- `422`: `{"detail": "...validation or business logic message..."}`

***

## Frontend implementation notes

These are current frontend assumptions based on the API shape above:

- Keep the uploaded `File` object in memory after the user selects it, because the current backend expects the CSV to be sent again for each endpoint call.
- Frontend should call these through one shared module like `frontend/src/api/client.js` rather than making raw Axios calls inside page components.
- For errors, frontend should read `error.response?.data?.detail` first.
- For alerts, frontend can safely treat:
  - `data.alerts ?? []`
  - `data.total ?? 0`

## Open confirmations for James

These are the only things still needed to fully lock the contract:

1. Exact JSON keys returned by `run_forecast_pipeline(...)`
2. Exact JSON keys returned by `get_future_forecast(...)`
3. Exact JSON keys returned by `shape_kpi_payload(...)`
4. Exact per-alert object keys returned by `run_all_alerts(...)`

Once those are confirmed, this draft can become the final frontend/backend contract.
