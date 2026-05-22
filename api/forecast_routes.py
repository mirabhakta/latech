"""FastAPI routes for the forecast pipeline.

!Thin routes! (all business logic lives in services/forecast_service.py).
"""

from __future__ import annotations

import io
from typing import List

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File, Query

from services.forecast_service import get_future_forecast, run_forecast_pipeline, shape_fast_kpi_payload
from utils.processor import load_and_clean_data

router = APIRouter(prefix="/forecast", tags=["forecast"])


@router.post("/run")
async def run_forecast(
    file: UploadFile = File(...),
    horizon_days: int = 90,
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
        result = run_forecast_pipeline(df, horizon_days=horizon_days)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return result


@router.post("/future")
async def future_forecast(
    file: UploadFile = File(...),
    future_days: int = 30,
    fast: bool = False,
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
        result = get_future_forecast(df, future_days=future_days, fast=fast)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return result


@router.post("/kpis")
async def forecast_kpis(
    file: UploadFile = File(...),
    future_days: int = 30,
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
        kpis = shape_fast_kpi_payload(df)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return kpis