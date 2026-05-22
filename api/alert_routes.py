"""FastAPI routes for the alert engine.

Thin routes - all business logic lives in models/alerter.py.
"""

from __future__ import annotations

import io
from typing import List

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File, Query

from models.alerter import run_all_alerts
from utils.processor import load_and_clean_data

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("/run")
async def run_alerts(
    file: UploadFile = File(...),
    anomaly_std: float = 2.0,
    decline_pct: float = 0.20,
    margin_floor: float = 0.0,
    store: List[int] = Query(default=[]),
    category: List[str] = Query(default=[]),
):
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="Could not parse uploaded file as CSV.")

    try:
        df = load_and_clean_data(df)
        if store:
            df = df[df['store_id'].isin(store)]
        if category:
            df = df[df['category'].isin(category)]
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    thresholds = {
        "anomaly_std": anomaly_std,
        "decline_pct": decline_pct,
        "margin_floor": margin_floor,
    }

    try:
        alerts_df = run_all_alerts(df, thresholds=thresholds)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    if alerts_df.empty:
        return {"alerts": [], "total": 0}

    return {
        "alerts": alerts_df.to_dict(orient="records"),
        "total": len(alerts_df),
    }