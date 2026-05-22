"""
app.py — Retail Forecasting Dashboard (Main Entry Point)
---------------------------------------------------------
Owned by: Justin (Integration Lead)
Purpose:  The single Streamlit app file that wires together every team
          member's output into one cohesive dashboard. This file:
            - Loads and normalizes retail sales data (Andrew's processor)
            - Loads Alberto's LightGBM forecast predictions
            - Runs James's alert engine on the filtered dataset
            - Renders all charts, KPIs, and panels across four tabs
            - Calls Sarah's Gemini AI summary with real dashboard data

Team modules consumed:
    models/alerter.py        → James  — anomaly + demand decline detection
    utils/processor.py       → Andrew — CSV normalization + feature flags
    utils/ai_summary.py      → Sarah  — Gemini AI summary generation
    data/forecastUpdated.csv → Alberto — LightGBM predictions for 2018
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
from datetime import timedelta
import html
from textwrap import dedent
import sys
import os
from zipfile import BadZipFile

# ── Team module imports ──────────────────────────────────────────────────────
# We append to sys.path so Python can find modules in subdirectories
# without requiring an installed package structure.

sys.path.append(os.path.join(os.path.dirname(__file__), "models"))
sys.path.append(os.path.join(os.path.dirname(__file__), "utils"))

try:
    from alerter import run_all_alerts
except ImportError:
    def run_all_alerts(df, thresholds=None):
        import pandas as pd
        return pd.DataFrame()

try:
    from processor import infer_column_mapping, map_to_clean_schema, get_feature_flags, validate_uploaded_data, generate_filter_options
    from ai_summary import build_payload, generate_summary
except ImportError:
    def infer_column_mapping(df): return {col: col for col in df.columns}
    def map_to_clean_schema(df): return df
    def get_feature_flags(df): return {"profit": "Profit data missing", "region": "Region data missing", "transaction_count": "Transaction count missing"}
    def validate_uploaded_data(df): return {col: col for col in df.columns}
    def generate_filter_options(df):
        return {
            "stores": sorted(df["store_id"].dropna().unique().tolist()),
            "categories": sorted(df["category"].dropna().unique().tolist()),
            "regions": sorted(df["region"].dropna().unique().tolist()) if "region" in df.columns else [],
            "start_date": df["date"].min(),
            "end_date": df["date"].max(),
        }
    def build_payload(**kwargs): return {}
    def generate_summary(payload): return {"status": "error", "message": "AI module unavailable"}

# ── Page configuration ───────────────────────────────────────────────────────
# Must be the first Streamlit call in the file — sets browser tab title
# and uses wide layout so the dashboard fills the full screen width.

st.set_page_config(
    page_title="Retail Forecasting Dashboard",
    layout="wide"
)

# ── CSS styling ──────────────────────────────────────────────────────────────
# Google Sheets inspired design — flat, clean, professional.
# We use !important flags throughout because Streamlit injects its own
# inline styles that would otherwise override our custom CSS.
# Key design tokens:
#   #0f9d58 = Google Sheets green (primary accent)
#   #202124 = near-black (body text)
#   #5f6368 = medium gray (labels, captions)
#   #e0e0e0 = light gray (borders)
#   #f3f3f3 = off-white (page background, matching Sheets canvas)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;600&family=Roboto:wght@300;400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Google Sans', 'Roboto', sans-serif !important;
    }

    /* Top navigation bar — Google Sheets green */
    header[data-testid="stHeader"] {
        background-color: #0f9d58 !important;
        z-index: 999999 !important;
        left: 0 !important;
        width: 100vw !important;
        position: fixed !important;
        border-bottom: 1px solid #0b8043 !important;
    }

    /* Main page background — Sheets canvas gray */
    .stApp { background-color: #f3f3f3; }

    .main .block-container {
        padding-top: 3.5rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
        max-width: 100% !important;
    }

    /* Sidebar — white with right border like Sheets panel */
    [data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-right: 1px solid #e0e0e0 !important;
    }

    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div,
    [data-testid="stSidebar"] label {
        color: #3c4043 !important;
        font-family: 'Google Sans', 'Roboto', sans-serif !important;
        font-size: 0.8rem !important;
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #202124 !important;
        font-size: 0.9rem !important;
        font-weight: 500 !important;
    }

    /* Filter dropdowns — flat Sheets style */
    [data-baseweb="select"] > div:first-child,
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    [data-testid="stMultiSelect"] div[data-baseweb="select"] {
        background-color: #ffffff !important;
        border: 1px solid #dadce0 !important;
        border-radius: 4px !important;
        box-shadow: none !important;
        font-size: 0.8rem !important;
    }

    [data-baseweb="select"] span,
    [data-baseweb="select"] div,
    [data-testid="stSelectbox"] span,
    [data-testid="stMultiSelect"] span,
    input[aria-autocomplete="list"] {
        color: #3c4043 !important;
        font-size: 0.8rem !important;
    }

    [data-baseweb="popover"] {
        background-color: #ffffff !important;
        border: 1px solid #dadce0 !important;
        border-radius: 4px !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.12) !important;
    }

    [data-baseweb="popover"] li { color: #3c4043 !important; font-size: 0.8rem !important; }
    [data-baseweb="popover"] li:hover { background-color: #f1f3f4 !important; }

    /* Selected multiselect pills — green accent */
    [data-testid="stMultiSelect"] span[data-baseweb="tag"] {
        background-color: #e6f4ea !important;
        color: #0b8043 !important;
        border-radius: 2px !important;
        font-weight: 500 !important;
        font-size: 0.75rem !important;
        border: 1px solid #ceead6 !important;
    }

    [data-testid="stMultiSelect"] span[data-baseweb="tag"] svg { fill: #0b8043 !important; }

    .stSidebar label {
        color: #5f6368 !important;
        font-size: 0.72rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.02em !important;
    }

    /* File uploader: keep the older clean white upload box look. */
    [data-testid="stFileUploader"] section {
        background-color: #ffffff !important;
        border: 1px solid #dadce0 !important;
        border-radius: 4px !important;
        padding: 0.75rem !important;
    }

    /* Make the add/upload control look like a real button. */
    [data-testid="stFileUploader"] section button {
        background-color: #ffffff !important;
        color: #0f9d58 !important;
        font-weight: 500 !important;
        border: 1px solid #dadce0 !important;
        border-radius: 4px !important;
        width: 100% !important;
        min-height: 2.25rem !important;
        font-size: 0.8rem !important;
        overflow: hidden !important;
        position: relative !important;
        text-indent: -9999px !important;
    }

    [data-testid="stFileUploader"] section button::after {
        content: "Add file" !important;
        text-indent: 0 !important;
        position: absolute !important;
        left: 50% !important;
        top: 50% !important;
        transform: translate(-50%, -50%) !important;
        color: #0f9d58 !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
    }

    [data-testid="stFileUploader"] small,
    [data-testid="stFileUploader"] p,
    [data-testid="stFileUploader"] span,
    [data-testid="stFileUploader"] div {
        color: #80868b !important;
        font-size: 0.75rem !important;
    }

    /* Uploaded file chip: keep the dark pill, but make text readable. */
    [data-testid="stFileUploader"] [class*="stFileChip"],
    [data-testid="stFileUploader"] [class*="stFileChip"] * {
        color: #ffffff !important;
    }

    /* File icon should be black inside its light icon box. */
    [data-testid="stFileUploader"] [class*="stFileChip"] svg,
    [data-testid="stFileUploader"] [class*="stFileChip"] svg * {
        color: #111827 !important;
        fill: #111827 !important;
        stroke: #111827 !important;
    }

    /* The remove button should stay small and normal inside the file chip. */
    [data-testid="stFileUploader"] [class*="stFileChip"] button {
        background: transparent !important;
        border: none !important;
        width: auto !important;
        min-height: 0 !important;
        padding: 0 !important;
        text-indent: 0 !important;
        position: static !important;
        color: #ffffff !important;
        display: inline-flex !important;
        overflow: visible !important;
    }

    [data-testid="stFileUploader"] [class*="stFileChip"] button::after {
        content: none !important;
    }

    /* Strong fallback for Streamlit's uploaded-file chip markup. */
    [data-testid="stFileUploader"] small button {
        background-color: #f8fafc !important;
        border: none !important;
        border-radius: 999px !important;
        color: #111827 !important;
        width: 1.1rem !important;
        height: 1.1rem !important;
        min-height: 1.1rem !important;
        padding: 0 !important;
        text-indent: 0 !important;
        position: static !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        overflow: visible !important;
    }

    [data-testid="stFileUploader"] small button::after { content: none !important; }

    [data-testid="stFileUploader"] small button svg,
    [data-testid="stFileUploader"] small button svg *,
    [data-testid="stFileUploader"] section svg,
    [data-testid="stFileUploader"] section svg * {
        color: #111827 !important;
        fill: #111827 !important;
        stroke: #111827 !important;
    }

    /* Final file-chip cleanup: visible file icon and visible X button. */
    [data-testid="stFileUploader"] [class*="stFileChip"] > div:first-child {
        background-color: #f8fafc !important;
        border-radius: 6px !important;
        position: relative !important;
        overflow: hidden !important;
    }

    [data-testid="stFileUploader"] [class*="stFileChip"] > div:first-child svg,
    [data-testid="stFileUploader"] [class*="stFileChip"] > div:first-child svg * {
        display: none !important;
    }

    [data-testid="stFileUploader"] [class*="stFileChip"] > div:first-child::after {
        content: "CSV" !important;
        width: 1.35rem !important;
        height: 1.05rem !important;
        background-color: #e0f2fe !important;
        border: 1px solid #64748b !important;
        border-radius: 3px !important;
        color: #334155 !important;
        font-size: 0.45rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.02em !important;
        position: absolute !important;
        left: 50% !important;
        top: 50% !important;
        transform: translate(-50%, -50%) !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }

    [data-testid="stFileUploader"] [class*="stFileChip"] small button {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: #ffffff !important;
        width: 1rem !important;
        height: 1rem !important;
        min-height: 1rem !important;
        padding: 0 !important;
        text-indent: 0 !important;
        position: static !important;
        overflow: visible !important;
        font-size: 0 !important;
    }

    [data-testid="stFileUploader"] [class*="stFileChip"] small button *,
    [data-testid="stFileUploader"] [class*="stFileChip"] small button svg {
        display: none !important;
        background: transparent !important;
    }

    [data-testid="stFileUploader"] [class*="stFileChip"] small button::before {
        content: "X" !important;
        color: #ffffff !important;
        font-size: 0.75rem !important;
        font-weight: 700 !important;
        line-height: 1 !important;
    }

    [data-testid="stFileUploader"] [class*="stFileChip"] small button::after {
        content: none !important;
    }

    h1, h2, h3 {
        background-color: transparent !important;
        color: #202124 !important;
        font-family: 'Google Sans', 'Roboto', sans-serif !important;
    }

    /* KPI metric cards — flat cells with green top accent border */
    div[data-testid="metric-container"],
    div[data-testid="stMetric"],
    [data-testid="metric-container"],
    [data-testid="stMetric"] {
        background-color: #ffffff !important;
        padding: 1.25rem 1.5rem !important;
        border-radius: 0 !important;
        border: 1px solid #e0e0e0 !important;
        border-top: 3px solid #0f9d58 !important;
        box-shadow: none !important;
    }

    [data-testid="column"] div[data-testid="stVerticalBlock"] {
        background-color: #ffffff !important;
        padding: 1rem !important;
        border-radius: 0 !important;
        border: 1px solid #e0e0e0 !important;
        border-top: 3px solid #0f9d58 !important;
        box-shadow: none !important;
    }

    [data-testid="column"] { flex: 1 1 0 !important; min-width: 0 !important; }

    div[data-testid="metric-container"],
    div[data-testid="stMetric"] { width: 100% !important; }

    [data-testid="stMetricLabel"] {
        color: #5f6368 !important;
        font-size: 0.7rem !important;
        font-weight: 500 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
    }

    [data-testid="stMetricValue"] {
        color: #202124 !important;
        font-size: 1.8rem !important;
        font-weight: 400 !important;
        font-family: 'Roboto', sans-serif !important;
    }

    [data-testid="stMetricDelta"] { font-size: 0.75rem !important; font-weight: 400 !important; }

    /* Force delta text to be dark regardless of Streamlit's color injection */
    [data-testid="stMetricDelta"] span,
    [data-testid="stMetricDelta"] p,
    [data-testid="stMetricDelta"] div,
    [data-testid="stMetricDelta"] > div > div,
    [data-testid="stMetricDelta"] svg ~ div,
    [data-testid="stMetricDelta"] * { color: #202124 !important; }

    /* Buttons — outlined green, Sheets style */
    .stButton>button {
        background-color: #ffffff !important;
        color: #0f9d58 !important;
        border: 1px solid #dadce0 !important;
        border-radius: 4px !important;
        font-weight: 500 !important;
        font-size: 0.8rem !important;
        width: 100% !important;
        padding: 0.4rem 1rem !important;
    }

    .stButton>button:hover {
        background-color: #e6f4ea !important;
        border-color: #0f9d58 !important;
    }

    /* Force entire spinner container and all children to be dark */
    [data-testid="stSpinner"],
    [data-testid="stSpinner"] *,
    [data-testid="stSpinner"] p,
    [data-testid="stSpinner"] span,
    [data-testid="stSpinner"] div,
    [data-testid="stSpinner"] svg,
    [data-testid="stSpinner"] svg *,
    [data-testid="stSpinner"] svg path,
    [data-testid="stSpinner"] svg circle {
        color: #202124 !important;
        fill: #202124 !important;
        stroke: #202124 !important;
    }

    /* Tabs styling — clean Google nav bar style */
    [data-testid="stTabs"] [data-baseweb="tab-list"] {
        background-color: #ffffff !important;
        border-bottom: 2px solid #e0e0e0 !important;
        gap: 0 !important;
        padding: 0 !important;
    }

    [data-testid="stTabs"] [data-baseweb="tab"] {
        background-color: #ffffff !important;
        color: #5f6368 !important;
        font-family: 'Google Sans', Roboto, sans-serif !important;
        font-size: 0.9rem !important;
        font-weight: 500 !important;
        padding: 0.85rem 1.75rem !important;
        border: none !important;
        border-bottom: 3px solid transparent !important;
        margin-bottom: -2px !important;
    }

    [data-testid="stTabs"] [aria-selected="true"] {
        color: #0f9d58 !important;
        border-bottom: 3px solid #0f9d58 !important;
        background-color: #ffffff !important;
    }

    [data-testid="stTabs"] [data-baseweb="tab"]:hover {
        color: #0b8043 !important;
        background-color: #f1f3f4 !important;
    }

    [data-testid="stTabs"] [data-baseweb="tab-panel"] {
        background-color: #f3f3f3 !important;
        padding: 1.5rem 0 0 0 !important;
    }

    /* Dropdown menus — force white background so options are readable */
    [data-baseweb="popover"] ul { background-color: #ffffff !important; }
    [data-baseweb="popover"] li { color: #3c4043 !important; background-color: #ffffff !important; font-size: 0.8rem !important; }
    [data-baseweb="popover"] li:hover { background-color: #e6f4ea !important; color: #0b8043 !important; }
    [data-baseweb="menu"] { background-color: #ffffff !important; }
    [data-baseweb="menu"] * { color: #3c4043 !important; background-color: #ffffff !important; }

    /* Make X and chevron icons visible on select boxes */
    [data-testid="stMultiSelect"] svg { fill: #3c4043 !important; opacity: 1 !important; }
    [data-testid="stSelectbox"] svg { fill: #3c4043 !important; opacity: 1 !important; }

    </style>
""", unsafe_allow_html=True)

# ── Sidebar header ───────────────────────────────────────────────────────────

st.sidebar.markdown("""
    <div style='padding: 1rem 0 1rem 0; border-bottom: 1px solid #e0e0e0; margin-bottom: 1rem;'>
        <h2 style='color: #202124; font-size: 1.1rem; font-weight: 500; margin: 0;'>
            Retail Forecast
        </h2>
    </div>
""", unsafe_allow_html=True)

# ── File uploader ────────────────────────────────────────────────────────────
# Single uploader handles two types of CSV:
#   1. Alberto's forecast file — detected by presence of 'actual' + 'prediction' columns
#   2. Retail sales file — everything else, passed through Andrew's processor
# This way the manager only needs one upload button regardless of file type.

st.sidebar.markdown("""
    <p style='color: #5f6368; font-size: 0.72rem; font-weight: 500; 
              text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem;'>
        Upload Data
    </p>
""", unsafe_allow_html=True)

uploaded_file = st.sidebar.file_uploader(
    "Upload CSV or Excel",
    type=["csv", "xlsx"],
    label_visibility="collapsed",
    key="main_uploader"
)

if uploaded_file is not None:
    # Andrew Garcia Leopold: show the uploaded file type in the custom file chip.
    # This helps users see whether they uploaded a CSV or Excel file.
    file_badge = "XLSX" if uploaded_file.name.lower().endswith(".xlsx") else "CSV"
    st.markdown(f"""
        <style>
        [data-testid="stFileUploader"] [class*="stFileChip"] > div:first-child::after {{
            content: "{file_badge}" !important;
        }}
        </style>
    """, unsafe_allow_html=True)

def read_uploaded_data(file):
    """Andrew Garcia Leopold: read either a CSV or Excel upload into a DataFrame."""
    file_name = file.name.lower()

    # Andrew Garcia Leopold: Excel files and CSV files need different pandas functions.
    # Keeping this in one helper lets the rest of the app load both formats the same way.
    if file_name.endswith(".xlsx"):
        return pd.read_excel(file)

    return pd.read_csv(file)

# Peek at the uploaded file to determine its type before loading.
# We read the first few rows, check the column names, then reset the
# file pointer so it can be fully read again below.
uploaded_forecast = None
upload_warning_message = None
rejected_upload_name = None
if uploaded_file is not None:
    try:
        peek_df = read_uploaded_data(uploaded_file)
        uploaded_file.seek(0)
        peek_columns = {str(col).strip().lower() for col in peek_df.columns}

        is_forecast_upload = {"date", "prediction"}.issubset(peek_columns)
        is_alert_export = {"alert_type", "severity", "metric"}.issubset(peek_columns)

        if is_forecast_upload:
            # Andrew Garcia Leopold: forecast uploads go to Alberto's forecast loader.
            uploaded_forecast = uploaded_file
            uploaded_file = None  # Don't pass to retail loader
        elif is_alert_export:
            # Andrew Garcia Leopold: alerts.csv is generated by the app, not uploaded into it.
            # Andrew Garcia Leopold: this prevents a confusing date/sales schema error.
            rejected_upload_name = uploaded_file.name
            upload_warning_message = (
                f"{rejected_upload_name} looks like an alert export, not a retail dataset "
                "or forecast file. The app will keep using the benchmark retail data."
            )
            uploaded_file = None
    except (ValueError, pd.errors.EmptyDataError, pd.errors.ParserError, BadZipFile) as upload_error:
        # Andrew Garcia Leopold: CSV and XLSX read errors should show the same friendly fallback.
        rejected_upload_name = uploaded_file.name
        upload_warning_message = (
            f"{rejected_upload_name} could not be read. {upload_error} "
            "The app will keep using the benchmark retail data."
        )
        uploaded_file = None

if uploaded_file is not None:
    try:
        validate_uploaded_data(peek_df)
    except ValueError as upload_error:
        # Andrew Garcia Leopold: keep the dashboard usable when a retail upload is missing key fields.
        rejected_upload_name = uploaded_file.name
        upload_warning_message = (
            f"{rejected_upload_name} could not be loaded. {upload_error} "
            "The app will keep using the benchmark retail data."
        )
        uploaded_file = None

# Andrew Garcia Leopold: keep separate names after routing the upload.
# Forecast uploads set uploaded_file to None, so the page label needs this
# separate forecast name to avoid saying only "Benchmark dataset loaded".
retail_upload_name = uploaded_file.name if uploaded_file else None
forecast_upload_name = uploaded_forecast.name if uploaded_forecast else None

# ── Data loading ─────────────────────────────────────────────────────────────
# Cached so the app doesn't re-read the CSV on every user interaction.
# If an uploaded file is missing the standard 'store_id' column, it gets
# normalized through Andrew's map_to_clean_schema() automatically.

@st.cache_data
def load_data(file=None):
    """
    Load retail sales data from an uploaded CSV or the default benchmark dataset.

    Tries uploaded file first, falls back to data/retail_clean.csv.
    If the uploaded file uses non-standard column names (e.g. 'store' instead
    of 'store_id'), Andrew's processor normalizes it to the standard schema.

    Returns:
        df (DataFrame): Clean data ready for filtering and analysis
        data_source (str): Label shown in the page subtitle
        column_mapping (dict): Clean schema field -> original uploaded column
    """
    if file is not None:
        raw_df = read_uploaded_data(file)
        # Andrew Garcia Leopold: store what the fuzzy mapper detected so the
        # sidebar can confirm how uploaded columns were interpreted.
        column_mapping = infer_column_mapping(raw_df)
        df = map_to_clean_schema(raw_df)
        data_source = "User Uploaded Data"
    else:
        df = pd.read_csv("data/retail_clean.csv")
        data_source = "Benchmark Dataset"
        column_mapping = {col: col for col in df.columns}
    df["date"] = pd.to_datetime(df["date"])
    return df, data_source, column_mapping

df, data_source, column_mapping = load_data(uploaded_file)

# Get feature flags from Andrew's processor — tells us which optional columns
# (profit, region, transaction_count) are present so we can enable/disable
# features that depend on them without crashing.
feature_flags = get_feature_flags(df)

# ── Load Alberto's forecast data ─────────────────────────────────────────────
# Alberto's LightGBM model outputs predictions per store/item/day for 2018.
# We load from an uploaded file first, then fall back to data/forecastUpdated.csv,
# and return None if neither exists so the app degrades gracefully.

@st.cache_data
def load_forecasts(file=None):
    """
    Load Alberto's forecast output (predictions per store/item/day).

    Falls back to data/forecastUpdated.csv if no file is uploaded.
    Returns None if neither source is available — the app handles this
    gracefully by falling back to the 8% growth formula for the chart.

    Expected columns: date, store, item, actual, prediction, residual, method_name
    Note: In the new forward-forecast file, actual and residual are empty
          because these sales haven't happened yet — only prediction is filled.
    """
    if file is not None:
        df_f = read_uploaded_data(file)
        df_f['date'] = pd.to_datetime(df_f['date'])
        return df_f
    forecast_paths = [
        os.path.join(os.path.dirname(__file__), "data", "forecastUpdated.csv"),
        os.path.join(os.path.dirname(__file__), "data", "updatedForecast.csv"),
    ]
    for forecast_path in forecast_paths:
        if not os.path.exists(forecast_path):
            continue
        df_f = pd.read_csv(forecast_path)
        df_f['date'] = pd.to_datetime(df_f['date'])
        return df_f
    return None

forecasts_df = load_forecasts(uploaded_forecast)


@st.cache_data
def load_model_comparison():
    """Load the saved model comparison used by the dashboard accuracy view."""
    comparison_path = os.path.join(os.path.dirname(__file__), "data", "model_comparison.csv")
    if not os.path.exists(comparison_path):
        return None

    comparison_df = pd.read_csv(comparison_path)
    if "method_name" not in comparison_df.columns:
        return None

    for col in ["mae", "rmse", "mase"]:
        if col in comparison_df.columns:
            comparison_df[col] = pd.to_numeric(comparison_df[col], errors="coerce")

    if "selected_winner" in comparison_df.columns:
        comparison_df["selected_winner"] = (
            comparison_df["selected_winner"]
            .astype(str)
            .str.lower()
            .isin(["true", "1", "yes"])
        )
    else:
        comparison_df["selected_winner"] = False
        if "mae" in comparison_df.columns and comparison_df["mae"].notna().any():
            comparison_df.loc[comparison_df["mae"].idxmin(), "selected_winner"] = True

    return comparison_df


def build_accuracy_from_forecasts(forecasts):
    """Calculate model accuracy when a scored forecast file has actuals/residuals."""
    if forecasts is None or forecasts.empty:
        return None
    if "actual" not in forecasts.columns or "residual" not in forecasts.columns:
        return None

    scored = forecasts.copy()
    scored["actual"] = pd.to_numeric(scored["actual"], errors="coerce")
    scored["prediction"] = pd.to_numeric(scored["prediction"], errors="coerce")
    scored["residual"] = pd.to_numeric(scored["residual"], errors="coerce")
    scored = scored.dropna(subset=["actual", "prediction", "residual"])
    if scored.empty:
        return None

    scored["abs_error"] = scored["residual"].abs()
    scored["squared_error"] = scored["residual"] ** 2
    comparison_df = (
        scored.groupby("method_name", as_index=False)
        .agg(
            mae=("abs_error", "mean"),
            rmse=("squared_error", lambda values: values.mean() ** 0.5),
            rows=("prediction", "size"),
        )
        .sort_values(["mae", "rmse"])
        .reset_index(drop=True)
    )
    comparison_df["selected_winner"] = comparison_df.index == 0
    return comparison_df


def build_model_accuracy_table(forecasts):
    """Prefer saved comparison results, then scored residuals, then active forecast method."""
    comparison_df = load_model_comparison()
    source = "Saved model comparison"

    if comparison_df is None or comparison_df.empty:
        comparison_df = build_accuracy_from_forecasts(forecasts)
        source = "Forecast residuals"

    if (comparison_df is None or comparison_df.empty) and forecasts is not None and not forecasts.empty:
        active_method = forecasts["method_name"].iloc[0] if "method_name" in forecasts.columns else "Unknown Model"
        comparison_df = pd.DataFrame([{
            "method_name": active_method,
            "mae": pd.NA,
            "rmse": pd.NA,
            "mase": pd.NA,
            "selected_winner": True,
            "notes": "Forward forecast file has no actual/residual values, so accuracy cannot be recalculated here.",
        }])
        source = "Active forecast file"

    if comparison_df is None:
        return None, None

    comparison_df = comparison_df.copy()
    if "selected_winner" not in comparison_df.columns:
        comparison_df["selected_winner"] = False
        if "mae" in comparison_df.columns and comparison_df["mae"].notna().any():
            comparison_df.loc[comparison_df["mae"].idxmin(), "selected_winner"] = True
    return comparison_df, source


model_accuracy_df, model_accuracy_source = build_model_accuracy_table(forecasts_df)

# ── Auto-reset filters on new file upload ────────────────────────────────────
# When a new file is uploaded, the available stores/categories change.
# Without resetting, old filter selections can cause an empty dataframe crash.
# We track the last uploaded filename and increment reset_counter when it changes,
# which forces all keyed widgets to re-render with their default values.

if 'last_upload' not in st.session_state:
    st.session_state.last_upload = None

current_upload = retail_upload_name or forecast_upload_name or rejected_upload_name
if current_upload != st.session_state.last_upload:
    st.session_state.last_upload = current_upload
    st.session_state.reset_counter = st.session_state.get('reset_counter', 0) + 1
    st.rerun()

# ── Intro overlay ─────────────────────────────────────────────────────────────
# FR-35: First thing a first-time user sees — replaces the entire page content.
# Uses st.empty() so clicking Get Started clears it and reveals the dashboard.
# Never shows again for the rest of the session.

if 'show_intro' not in st.session_state:
    st.session_state.show_intro = True

if st.session_state.show_intro:
    intro = st.empty()
    with intro.container():
        st.markdown("""
            <style>
            [data-testid="stSidebar"] { display: none !important; }
            [data-testid="collapsedControl"] { display: none !important; }
            .main .block-container { padding-left: 1.5rem !important; }
            body { overflow: hidden !important; }

            /* Hide the real Streamlit button visually but keep it clickable */
            div[data-testid="stButton"] > button {
                position: fixed !important;
                bottom: calc(50vh - 340px) !important;
                left: 50% !important;
                transform: translateX(-50%) !important;
                z-index: 99999 !important;
                background-color: #0f9d58 !important;
                color: #ffffff !important;
                border: none !important;
                border-radius: 4px !important;
                padding: 0.6rem 2rem !important;
                font-size: 0.9rem !important;
                font-weight: 500 !important;
                width: auto !important;
                min-width: 200px !important;
                cursor: pointer !important;
            }

            div[data-testid="stButton"] > button:hover {
                background-color: #0b8043 !important;
            }
            </style>
        """, unsafe_allow_html=True)

        st.markdown("""
            <div style='min-height: 100vh; display: flex; align-items: center;
                        justify-content: center; padding: 2rem;
                        position: fixed; top: 0; left: 0; width: 100vw;
                        background-color: #f3f3f3; z-index: 9999;'>
                <div style='background-color: #ffffff; border-top: 4px solid #0f9d58;
                            border: 1px solid #e0e0e0; border-top: 4px solid #0f9d58;
                            padding: 2rem; max-width: 600px; width: 100%;
                            box-shadow: 0 4px 24px rgba(0,0,0,0.08);'>
                    <p style='color: #0f9d58; font-size: 0.72rem; font-weight: 600;
                              text-transform: uppercase; letter-spacing: 0.1em; margin: 0 0 1rem 0;'>
                        LA Tech Rising · AI-Powered Retail
                    </p>
                    <h1 style='color: #202124; font-size: 1.75rem; font-weight: 500;
                               margin: 0 0 0.75rem 0; line-height: 1.3;'>
                        Welcome to the Retail Forecasting Engine
                    </h1>
                    <p style='color: #5f6368; font-size: 0.875rem; margin: 0 0 0.5rem 0;'>
                        Built by the LA Tech Rising team · Powered by Gemini AI
                    </p>
                    <p style='color: #3c4043; font-size: 0.9rem; line-height: 1.7;
                              margin: 0 0 1rem 0; padding-top: 0.75rem;
                              border-top: 1px solid #f1f3f4;'>
                        This dashboard turns raw retail sales data into actionable insights —
                        demand forecasts, risk alerts, and AI-generated summaries — all in one place.
                        No technical knowledge required.
                    </p>
                    <div style='background-color: #f8f9fa; border-radius: 4px;
                                padding: 1rem 1.25rem; margin-bottom: 0;'>
                        <p style='color: #3c4043; font-size: 0.85rem; line-height: 2.2; margin: 0;'>
                            📂 <b>Upload your data</b> in the sidebar, or explore the benchmark dataset<br>
                            🔍 <b>Filter</b> by store, category, or region to focus your analysis<br>
                            ✦ <b>Generate Summary</b> for an AI-written overview of what needs attention<br>
                            📊 <b>Switch tabs</b> to explore forecasts, products, and analysis
                        </p>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        col_l, col_btn, col_r = st.columns([1, 1, 1])
        with col_btn:
            if st.button("✦ Get Started →", use_container_width=True):
                st.session_state.show_intro = False
                intro.empty()
                st.rerun()
    st.stop()

# ── Page title ───────────────────────────────────────────────────────────────
# Placed AFTER data loading so dataset_label can reference data_source
# and current_upload which are now defined.

if data_source == "User Uploaded Data":
    dataset_label = f"Custom dataset loaded · {retail_upload_name}"
elif forecast_upload_name:
    dataset_label = f"Benchmark dataset loaded · Forecast file loaded: {forecast_upload_name}"
elif rejected_upload_name:
    dataset_label = f"Benchmark dataset loaded · Ignored unsupported file: {rejected_upload_name}"
else:
    dataset_label = "Benchmark dataset loaded"

st.markdown(f"""
    <div style='margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid #e0e0e0;'>
        <h1 style='font-size: 1.5rem; font-weight: 500; color: #202124; margin: 0;'>
            Sales Forecasting Dashboard
        </h1>
        <p style='color: #5f6368; font-size: 0.875rem; margin: 0.25rem 0 0 0;'>
            Retail performance overview · {dataset_label}
        </p>
    </div>
""", unsafe_allow_html=True)

if upload_warning_message:
    st.markdown(f"""
        <div style='background-color: #fef7e0; border-left: 4px solid #f9ab00;
                    color: #3c4043; padding: 0.85rem 1rem; border-radius: 4px;
                    margin-bottom: 1rem; font-size: 0.85rem; font-weight: 500;'>
            {html.escape(upload_warning_message)}
        </div>
    """, unsafe_allow_html=True)

# ── Data mapping panel ───────────────────────────────────────────────────────
# Shows the manager which fields were detected in their uploaded data.
# Green dot = field found and active. Red dot = field missing, feature disabled.
# This fulfills the spec requirement: "show a simple panel listing what was found."

st.sidebar.markdown("""
    <p style='color: #5f6368; font-size: 0.72rem; font-weight: 500; 
              text-transform: uppercase; letter-spacing: 0.05em; 
              margin: 1.25rem 0 0.5rem 0;'>
        Data Mapping
    </p>
""", unsafe_allow_html=True)

# Andrew Garcia Leopold: Required fields are the columns the dashboard needs to work.
# Optional features are extra columns that turn extra dashboard features on/off.
# Green means the field is available. Red means the related feature should stay inactive.
green_dot = "<span style='display:inline-block; width:0.7rem; height:0.7rem; border-radius:50%; background-color:#0f9d58; margin-right:0.35rem;'></span>"
red_dot   = "<span style='display:inline-block; width:0.7rem; height:0.7rem; border-radius:50%; background-color:#d93025; margin-right:0.35rem;'></span>"

date_dot        = green_dot if "date"              in df.columns else red_dot
sales_dot       = green_dot if "sales"             in df.columns else red_dot
store_dot       = green_dot if "store_id"          in df.columns else red_dot
product_dot     = green_dot if "product_id"        in df.columns else red_dot
category_dot    = green_dot if "category"          in df.columns else red_dot
quantity_dot    = green_dot if "quantity"          in df.columns else red_dot
profit_dot      = green_dot if "profit"            in df.columns else red_dot
region_dot      = green_dot if "region"            in df.columns else red_dot
transaction_dot = green_dot if "transaction_count" in df.columns else red_dot

st.sidebar.markdown(f"""
    <div style='background-color: #f8f9fa; padding: 0.75rem 1rem;
                border-radius: 4px; border: 1px solid #e0e0e0; line-height: 2;'>
        <span style='font-size: 0.72rem; color: #5f6368; font-weight: 500;'>Required Fields</span><br>
        <span style='font-size: 0.8rem; color: #3c4043;'>{date_dot} Date</span><br>
        <span style='font-size: 0.8rem; color: #3c4043;'>{sales_dot} Sales</span><br>
        <span style='font-size: 0.8rem; color: #3c4043;'>{store_dot} Store ID</span><br>
        <span style='font-size: 0.8rem; color: #3c4043;'>{product_dot} Product</span><br>
        <span style='font-size: 0.8rem; color: #3c4043;'>{category_dot} Category</span><br>
        <span style='font-size: 0.8rem; color: #3c4043;'>{quantity_dot} Quantity</span><br>
        <span style='font-size: 0.72rem; color: #5f6368; font-weight: 500;'>Optional Features</span><br>
        <span style='font-size: 0.8rem; color: #3c4043;'>{profit_dot} {feature_flags["profit"]}</span><br>
        <span style='font-size: 0.8rem; color: #3c4043;'>{region_dot} {feature_flags["region"]}</span><br>
        <span style='font-size: 0.8rem; color: #3c4043;'>{transaction_dot} {feature_flags["transaction_count"]}</span>
    </div>
""", unsafe_allow_html=True)

# Andrew Garcia Leopold: show the exact raw column each clean schema field came from.
# This is the confirmation step after upload so users can spot bad auto-matches.

# Justin Hernandez: Made sure that the column mapping panel is only visible when a user uploads their own data since
# the benchmark dataset already matches the clean schema.

if data_source == "User Uploaded Data":
    st.sidebar.markdown("""
        <p style='color: #5f6368; font-size: 0.72rem; font-weight: 500; 
                  text-transform: uppercase; letter-spacing: 0.05em; 
                  margin: 1.25rem 0 0.5rem 0;'>
            Column Mapping
        </p>
    """, unsafe_allow_html=True)
    for clean_col, raw_col in column_mapping.items():
        st.sidebar.markdown(f"""
            <div style='display:flex; justify-content:space-between;
                        border-bottom:1px solid #e8eaed; padding:0.2rem 0;
                        background-color:#f8f9fa;'>
                <span style='color:#0b8043; font-weight:500; font-size:0.78rem; padding-left:0.5rem;'>{html.escape(str(clean_col))}</span>
                <span style='color:#5f6368; font-size:0.78rem; padding-right:0.5rem;'>← {html.escape(str(raw_col))}</span>
            </div>
        """, unsafe_allow_html=True)


# ── Sidebar filters ───────────────────────────────────────────────────────────
# All filter widgets are keyed to reset_counter so that clicking Reset Filters
# or uploading a new file forces them to re-render with default values.
# This is the only reliable way to programmatically reset Streamlit widgets.

st.sidebar.markdown("""
    <p style='color: #5f6368; font-size: 0.72rem; font-weight: 500; 
              text-transform: uppercase; letter-spacing: 0.05em; 
              margin: 1.25rem 0 0.5rem 0;'>
        Filters
    </p>
""", unsafe_allow_html=True)

if 'reset_counter' not in st.session_state:
    st.session_state.reset_counter = 0

# Date range always covers all available data — the forecast horizon slider
# controls how far the orange projection line extends, not the date range.
filter_options = generate_filter_options(df)
start_date = filter_options["start_date"]
end_date   = filter_options["end_date"]

# Forecast horizon — controls how many months of predictions are shown
# on the chart and summed in the Projected Revenue KPI card.
projection_option = st.sidebar.selectbox(
    "Forecast Horizon",
    options=["Next 30 days", "Next 60 days", "Next 90 days", "Next 6 months", "Next 12 months"],
    index=2,  # Default: Next 90 days
    key=f"projection_{st.session_state.reset_counter}"
)

projection_days_map = {
    "Next 30 days": 30, "Next 60 days": 60, "Next 90 days": 90,
    "Next 6 months": 180, "Next 12 months": 365,
}
projection_days = projection_days_map[projection_option]

# Store filter — all stores selected by default
stores = filter_options["stores"]
selected_stores = st.sidebar.multiselect(
    "Store", options=stores, default=stores,
    key=f"stores_{st.session_state.reset_counter}"
)

# Category filter — all categories selected by default
categories = filter_options["categories"]
selected_categories = st.sidebar.multiselect(
    "Category", options=categories, default=categories,
    key=f"categories_{st.session_state.reset_counter}"
)

# bug fix 3:
# Region filter — only show if 'region' column is present in the dataset
# Graceful degradation. Hide geographic filters if region is absent

if 'region' in df.columns:
    regions = filter_options["regions"]
    selected_regions = st.sidebar.multiselect(
        "Region", options=regions,
        default=regions,
        key=f"regions_{st.session_state.reset_counter}"
    )
else:
    selected_regions = None

# Reset button — increments reset_counter which forces all keyed widgets
# to re-render as brand new widgets with their default values
if st.sidebar.button("Reset Filters"):
    st.session_state.reset_counter += 1
    st.session_state.ai_summary = None  # Clear stale summary when filters reset
    st.rerun()

# Alert sensitivity slider — wired directly to James's alerter thresholds.
# Lower value = more sensitive (catches smaller anomalies).
# Higher value = less sensitive (only flags obvious problems).
# Default of 2.0 matches James's built-in default threshold.
st.sidebar.markdown("""
    <p style='color: #5f6368; font-size: 0.72rem; font-weight: 500; 
              text-transform: uppercase; letter-spacing: 0.05em; 
              margin: 1rem 0 0.25rem 0;'>
        Alert Sensitivity
    </p>
""", unsafe_allow_html=True)

sensitivity = st.sidebar.slider(
    "Threshold", min_value=0.5, max_value=3.0, value=2.0, step=0.25,
    help="Lower = catches more alerts. Higher = only flags major issues.",
    key=f"sensitivity_{st.session_state.reset_counter}"
)

# ── Apply filters ─────────────────────────────────────────────────────────────
# df_filtered is the single source of truth for everything below this point.
# Every KPI, chart, alert, and table reads from this filtered dataset.
# Changing any filter updates df_filtered which triggers a full re-render.

df_filtered = df[
    (df['date'] >= pd.to_datetime(start_date)) &
    (df['date'] <= pd.to_datetime(end_date)) &
    (df['store_id'].isin(selected_stores)) &
    (df['category'].isin(selected_categories)) &
    (df['region'].isin(selected_regions) if selected_regions is not None else True)
].copy()

# Guard against empty filtered data — show a friendly message instead of crashing
if len(df_filtered) == 0:
    st.markdown("""
        <div style='background-color: #fce8e6; border-left: 4px solid #d93025; 
                    padding: 1rem 1.25rem; border-radius: 4px; color: #202124;'>
            No data matches your current filters. Please adjust your selections.
        </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── Alert engine ──────────────────────────────────────────────────────────────
# Runs James's alerter on the filtered dataset every time filters change.
# We don't cache alerts because they need to update on every filter change —
# caching was causing stale results when new files were uploaded.
# The sensitivity slider value is passed directly to James's thresholds dict
# so the manager can control alert aggressiveness without touching any code.

alerts_df = run_all_alerts(df_filtered, thresholds={
    'anomaly_std':  sensitivity,        # z-score cutoff for sales spikes/drops
    'decline_pct':  sensitivity * 0.1,  # % decline threshold scales with sensitivity
    'margin_floor': 0.0                 # margin floor uses James's default
})

# Andrew Garcia Leopold: feature_flags should affect behavior, not just sidebar dots.
# If profit is missing, margin alerts cannot be calculated, so hide them silently.
profit_data_available = "profit" in df_filtered.columns
margin_alert_notice   = ""

if not profit_data_available:
    margin_alert_notice = "Profit data is missing, so margin alerts are hidden for this dataset."
    # Safety guard: James's alerter already skips margin alerts without profit,
    # but this keeps the dashboard correct if alert data changes later.
    if not alerts_df.empty and "alert_type" in alerts_df.columns:
        alerts_df = alerts_df[alerts_df["alert_type"] != "Low Margin"].copy()

# ── Sales trend calculation ───────────────────────────────────────────────────
# Derives trend direction from the filtered historical sales data so the KPI
# reflects whatever store/category the manager is currently looking at.
# Method: split the time range in half, compare first half avg vs second half avg.
# A 2% buffer on either side prevents flat data from being mislabeled.

# Calculate MAE only if residuals are present (older validation files have them;
# the new forward-forecast file has empty residual/actual columns)
if forecasts_df is not None:
    residuals_available = forecasts_df['residual'].notna().any()
    mae           = round(abs(forecasts_df['residual']).mean(), 2) if residuals_available else None
    avg_pct_error = round((abs(forecasts_df['residual']) / forecasts_df['actual'] * 100).mean(), 1) if residuals_available else None
    method_used   = forecasts_df['method_name'].iloc[0]
else:
    mae = None
    avg_pct_error = None
    method_used = None

if model_accuracy_df is not None and not model_accuracy_df.empty:
    winner_rows = model_accuracy_df[model_accuracy_df["selected_winner"] == True]
    if winner_rows.empty and "mae" in model_accuracy_df.columns and model_accuracy_df["mae"].notna().any():
        accuracy_winner = model_accuracy_df.loc[model_accuracy_df["mae"].idxmin()]
    elif winner_rows.empty:
        accuracy_winner = model_accuracy_df.iloc[0]
    else:
        accuracy_winner = winner_rows.iloc[0]
    method_used = accuracy_winner.get("method_name", method_used)
    if mae is None and "mae" in model_accuracy_df.columns and pd.notna(accuracy_winner.get("mae", pd.NA)):
        mae = round(float(accuracy_winner.get("mae")), 3)

# Aggregate daily sales by date, split in half, compare averages
sorted_sales    = df_filtered.sort_values('date').groupby('date')['sales'].sum().tolist()
mid             = len(sorted_sales) // 2
first_half_avg  = sum(sorted_sales[:mid]) / max(len(sorted_sales[:mid]), 1)
second_half_avg = sum(sorted_sales[mid:]) / max(len(sorted_sales[mid:]), 1)
pct_change      = ((second_half_avg - first_half_avg) / first_half_avg) * 100

if pct_change > 2:
    trend_label = "Increasing"
    trend_delta = f"+{pct_change:.1f}% vs prior period"
    trend_color = "normal"   # Streamlit renders green for positive normal delta
elif pct_change < -2:
    trend_label = "Declining"
    trend_delta = f"{pct_change:.1f}% vs prior period"
    trend_color = "normal"   # Negative number + normal color = red arrow
else:
    trend_label = "Steady"
    trend_delta = f"~{pct_change:.1f}% vs prior period"
    trend_color = "off"      # Gray delta for flat/neutral

# ── Forecast values calculation ───────────────────────────────────────────────
# Calculated here (before the KPI row) so forecast_values is available for
# both the Projected Revenue KPI card (col4) and the chart below.
# Primary source: Alberto's LightGBM predictions filtered to future dates only.
# Fallback: 8% annual growth formula if Alberto's data is older than the history.

df_chart = df_filtered.groupby(
    df_filtered['date'].dt.to_period('M')
)['sales'].sum().reset_index()
df_chart.columns = ['period', 'sales']
df_chart['period'] = df_chart['period'].astype(str)

# Drop the last month if it's incomplete (less than 90% of days present).
# This prevents a misleading dip at the end of the historical line when the
# dataset cuts off mid-month (e.g. December showing $625k instead of $928k).
last_month_date    = df_filtered['date'].max()
days_in_last_month = pd.Period(last_month_date, 'M').days_in_month
days_present = df_filtered[
    df_filtered['date'].dt.to_period('M') == pd.Period(last_month_date, 'M')
]['date'].dt.day.nunique()
if days_present < days_in_last_month * 0.9:
    df_chart = df_chart.iloc[:-1]

last_period_dt = df_filtered['date'].max()
last_value     = df_chart['sales'].iloc[-1]
months_ahead   = max(1, projection_days // 30)

if forecasts_df is not None:
    # Filter Alberto's predictions to only dates AFTER the historical data ends.
    # This prevents 2018 forecasts from plotting behind a 2019-2023 historical line.
    fc = forecasts_df.copy()
    fc = fc[fc['date'] > last_period_dt]

    if len(fc) > 0:
        # Aggregate daily per-store/item predictions into monthly totals
        # to match the scale of the historical monthly line
        fc['period']   = fc['date'].dt.to_period('M').astype(str)
        fc_monthly     = fc.groupby('period')['prediction'].sum().reset_index()
        fc_monthly     = fc_monthly.sort_values('period').head(months_ahead)
        forecast_periods = fc_monthly['period'].tolist()
        forecast_values  = fc_monthly['prediction'].tolist()
    else:
        # Alberto's data is older than the historical dataset — use growth formula
        growth_per_day   = (1.08 ** (1/365))
        forecast_periods = [(last_period_dt + pd.DateOffset(months=i+1)).strftime('%Y-%m') for i in range(months_ahead)]
        forecast_values  = [last_value * (growth_per_day ** (30*(i+1))) for i in range(months_ahead)]
else:
    # Alberto's file not available at all — use growth formula as fallback
    growth_per_day   = (1.08 ** (1/365))
    forecast_periods = [(last_period_dt + pd.DateOffset(months=i+1)).strftime('%Y-%m') for i in range(months_ahead)]
    forecast_values  = [last_value * (growth_per_day ** (30*(i+1))) for i in range(months_ahead)]

last_period = df_chart['period'].iloc[-1]

# ── Top 5 Best and Worst Sellers calculation ──────────────────────────────────
# Aggregated from df_filtered so it updates when store/category filters change.
# Uses product_name if available (custom uploads), falls back to product_id
# (benchmark dataset which doesn't have a product_name column).

name_col = 'product_name' if 'product_name' in df_filtered.columns else 'product_id'
product_sales = (
    df_filtered.groupby(name_col)['sales']
    .sum()
    .reset_index()
    .rename(columns={name_col: 'product', 'sales': 'total_sales'})
    .sort_values('total_sales', ascending=False)
)

top5    = product_sales.head(5).reset_index(drop=True)
bottom5 = product_sales.tail(5).sort_values('total_sales', ascending=True).reset_index(drop=True)

# ── Category breakdown calculation ───────────────────────────────────────────
# Revenue summed per category from the filtered dataset.
# Used for both the bar chart (absolute revenue) and donut chart (% share).

category_sales = (
    df_filtered.groupby('category')['sales']
    .sum()
    .reset_index()
    .rename(columns={'sales': 'total_sales'})
    .sort_values('total_sales', ascending=False)
)

# Monthly revenue per category for the trend line chart
category_monthly = (
    df_filtered.groupby(['category', df_filtered['date'].dt.to_period('M')])['sales']
    .sum().reset_index()
)
category_monthly['period'] = category_monthly['date'].astype(str)

# Andrew Garcia Leopold: Store comparison adds up total sales for each store.
# This uses df_filtered, so it changes when the user changes store/category filters.
store_sales = (
    df_filtered.groupby('store_id')['sales']
    .sum()
    .reset_index()
    .rename(columns={'sales': 'total_sales'})
    .sort_values('total_sales', ascending=False)
)

# Distinct color palette for up to 8 categories — professional and accessible
category_colors = [
    '#0f9d58', '#1a73e8', '#f29900', '#d93025',
    '#9c27b0', '#00bcd4', '#ff5722', '#607d8b'
]

# ── AI Summary state ──────────────────────────────────────────────────────────
# Initialize AI summary cache in session state on first load.

if 'ai_summary' not in st.session_state:
    st.session_state.ai_summary = None

# ── TABS — placed immediately after page title as primary navigation ──────────
# Tab 1: Overview  — AI summary, KPIs, forecast chart, alerts
# Tab 2: Products  — Top/bottom sellers
# Tab 3: Analysis  — Category trends, charts, store comparison
# Tab 4: Model     — Alberto's model accuracy benchmarking
# 

tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "🏆 Products", "📈 Analysis", "🤖 Model"])

# TAB 1 — OVERVIEW
# Answers: How is the business doing right now?

with tab1:

    # ── AI Summary panel ──────────────────────────────────────────────────────
    # Powered by Sarah's Gemini integration (utils/ai_summary.py).
    # The summary is cached in session_state so it doesn't re-run on every
    # filter change — only when the manager explicitly clicks Generate.
    # We pass real dashboard metrics so the AI writes something specific
    # to the current data, not a generic retail summary.

    st.markdown("""
        <div style='background-color: #ffffff; padding: 1rem 1.5rem 0.75rem 1.5rem;
                    border-radius: 0; border: 1px solid #e0e0e0;
                    border-top: 3px solid #1a73e8; margin-bottom: 1.25rem;'>
            <p style='color: #5f6368; font-size: 0.72rem; font-weight: 500;
                      text-transform: uppercase; letter-spacing: 0.05em; margin: 0 0 0.25rem 0;'>
                AI Insights
            </p>
            <p style='color: #202124; font-size: 0.8rem; margin: 0;'>
                Generate a plain-English summary of your current data
            </p>
        </div>
    """, unsafe_allow_html=True)

    col_ai_btn = st.columns([1, 5])[0]
    with col_ai_btn:
        generate_clicked = st.button("✦ Generate Summary")

    # Deleted the Clear button to simplify the interface. Also
    # it is no longer needed — st.session_state.ai_summary is set to None
    # when filter resets since it does not show up anymore.

    if generate_clicked:
        with st.spinner("Analyzing your data..."):
            # Build the payload from real dashboard data to pass to Sarah's function.
            # We gather: total revenue, trend, alert count, top product,
            # top category, projected revenue, and top 3 alert product names.
            total_sales_val   = df_filtered["sales"].sum()
            top_product_name  = top5.iloc[0]['product'] if len(top5) > 0 else "N/A"
            top_category_name = category_sales.iloc[0]['category'] if len(category_sales) > 0 else "N/A"
            projected_val     = sum(forecast_values) if forecast_values else None
            # Andrew Garcia Leopold: support either alert column name so AI testing
            # does not break the dashboard if another teammate uses "product".
            alert_product_column = (
                "product_name" if "product_name" in alerts_df.columns
                else "product" if "product" in alerts_df.columns
                else None
            )
            top_alert_names = alerts_df[alert_product_column].head(3).tolist() if alert_product_column else []

            # OLD TEST FUNCTION (kept for reference, no longer used)
            # result = test_gemini(...)

            # Andrew Garcia Leopold: make an AI-only copy instead of renaming alerts_df.
            # The Alert Center below still needs the original product_name column.
            ai_alerts_df = alerts_df.rename(columns={"product_name": "product"})

            # Build payload for Gemini (new structured approach)
            payload = build_payload(
                trend      = trend_label,
                model_name = method_used if method_used else "Unknown Model",
                accuracy   = mae if mae else "not available",
                alerts_df  = ai_alerts_df
            )

            # Generate summary using Gemini
            result = generate_summary(payload)

            if result["status"] == "success":
                st.session_state.ai_summary = result["text"]
            else:
                st.session_state.ai_summary = None
                st.markdown(f"""
                    <div style='background-color: #fce8e6; border-left: 4px solid #d93025;
                                padding: 1rem 1.25rem; border-radius: 4px; color: #202124;
                                margin-bottom: 1rem;'>
                        ⚠️ Could not generate summary — {result["message"]}
                    </div>
                """, unsafe_allow_html=True)

    # Display the cached AI summary if one exists
    if st.session_state.ai_summary:
        st.markdown(f"""
            <div style='background-color: #e8f0fe; border-left: 4px solid #1a73e8;
                        padding: 1.25rem 1.5rem; border-radius: 4px;
                        color: #202124; font-size: 0.9rem; line-height: 1.6;
                        margin-bottom: 1.25rem;'>
                {st.session_state.ai_summary}
            </div>
        """, unsafe_allow_html=True)

    # ── KPI metrics ───────────────────────────────────────────────────────────
    # Four headline numbers answering the manager's most important questions:
    #   1. How much money are we making? (Total Revenue)
    #   2. Is the business growing or shrinking? (Sales Trend)
    #   3. Is anything broken? (Active Alerts)
    #   4. How much do we expect to make? (Projected Revenue)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_sales = df_filtered["sales"].sum()
        st.metric("Total Revenue", f"${total_sales:,.0f}", delta="All stores combined")

    with col2:
        # Powered by the trend calculation above — green for up, red for down, gray for steady
        st.metric("Sales Trend", trend_label, delta=trend_delta, delta_color=trend_color)

    # Changed the Active Alerts KPI to show a green border if all alerts are positive spikes,
    # and a red border if there are any negative alerts. This gives the manager an immediate visual
    # cue about whether the alerts are mostly good news or bad news.
    with col3:
        alert_count = len(alerts_df)

        if alert_count == 0:
            delta_text        = "No issues detected"
            delta_color_alert = "off"
            bad_alerts        = 0
            good_alerts       = 0
        else:
            # Split alerts into good (sales up) vs bad (sales down / margin)
            good_alerts = 0
            bad_alerts  = 0
            for _, alert in alerts_df.iterrows():
                if alert['alert_type'] == "Sales Anomaly":
                    try:
                        parts   = alert['metric'].split()
                        current = float(parts[2])
                        mean    = float(parts[-1])
                        if current > mean:
                            good_alerts += 1
                        else:
                            bad_alerts += 1
                    except:
                        bad_alerts += 1
                else:
                    bad_alerts += 1

            if bad_alerts == 0:
                # All alerts are positive spikes
                delta_text        = f"📈 {good_alerts} positive spike{'s' if good_alerts != 1 else ''} detected"
                delta_color_alert = "normal"
            elif good_alerts == 0:
                # All alerts are negative
                delta_text        = f"-⚠️ {bad_alerts} item{'s' if bad_alerts != 1 else ''} need your attention"
                delta_color_alert = "normal"  # changed to normal because a '-' to show negative arrow will inverse the color as well.
            else:
                # Mix of good and bad
                delta_text        = f"-📈 {good_alerts} up · 📉 {bad_alerts} need attention"
                delta_color_alert = "normal"

        st.metric("Active Alerts", alert_count, delta=delta_text, delta_color=delta_color_alert)

        # Only show red border if there are actually bad alerts
        if alert_count > 0 and bad_alerts > 0:
            st.markdown("""
                <style>
                [data-testid="column"]:nth-child(3) div[data-testid="stVerticalBlock"],
                [data-testid="column"]:nth-child(3) div[data-testid="stMetric"] {
                    border-top: 3px solid #d93025 !important;
                }
                </style>
            """, unsafe_allow_html=True)
        elif alert_count > 0 and bad_alerts == 0:
            # All good alerts — show green border instead
            st.markdown("""
                <style>
                [data-testid="column"]:nth-child(3) div[data-testid="stVerticalBlock"],
                [data-testid="column"]:nth-child(3) div[data-testid="stMetric"] {
                    border-top: 3px solid #0f9d58 !important;
                }
                </style>
            """, unsafe_allow_html=True)

    with col4:
        # Sums all forecast_values for the selected horizon — updates when
        # the Forecast Horizon filter changes so the number matches the orange line.
        if forecast_values:
            projected_total = sum(forecast_values)
            st.metric(
                f"Projected Revenue ({projection_option})",
                f"${projected_total:,.0f}",
                delta="Based on forecast model"
            )
        else:
            st.metric("Projected Revenue", "—", delta="No forecast available", delta_color="off")

    st.markdown("<div style='margin: 1.5rem 0 0.5rem 0;'></div>", unsafe_allow_html=True)

    # ── Forecast chart + Alert panel ──────────────────────────────────────────
    # Two-column layout: chart takes 2/3 width, alert panel takes 1/3.

    col_chart, col_alerts = st.columns([2, 1])

    with col_chart:
        st.markdown("""
            <div style='background-color: #ffffff; padding: 1rem 1.5rem 0.5rem 1.5rem;
                        border-radius: 0; border: 1px solid #e0e0e0; 
                        border-bottom: none; border-top: 3px solid #0f9d58;'>
                <h3 style='margin: 0; color: #202124; font-size: 0.95rem; font-weight: 500;'>
                    Sales Forecast
                </h3>
                <p style='margin: 0.2rem 0 0 0; color: #5f6368; font-size: 0.8rem;'>
                    Historical performance vs. projected growth
                </p>
            </div>
        """, unsafe_allow_html=True)

        fig = go.Figure()

        # Green solid line — actual historical sales from the uploaded/benchmark dataset
        fig.add_trace(go.Scatter(
            x=df_chart['period'], y=df_chart['sales'],
            mode='lines+markers', name='Historical',
            line=dict(color='#0f9d58', width=2.5),
            marker=dict(size=6, color='#0f9d58'),
            fill='tozeroy', fillcolor='rgba(15, 157, 88, 0.06)',
            hovertemplate='<b>%{x}</b><br>Revenue: $%{y:,.0f}<extra></extra>'
        ))

        # Orange dashed line — Alberto's LightGBM predictions (or fallback growth formula).
        # Dashed style visually reinforces that this is a projection, not historical fact.
        fig.add_trace(go.Scatter(
            x=[last_period] + forecast_periods,
            y=[last_value] + forecast_values,
            mode='lines+markers', name='Projected',
            line=dict(color='#f29900', width=2.5, dash='dash'),
            marker=dict(size=6, color='#f29900'),
            hovertemplate='<b>%{x}</b><br>Projected: $%{y:,.0f}<extra></extra>'
        ))

        # Vertical dotted line separating historical from projected — visual clarity for managers
        fig.add_vline(x=last_period, line_dash="dot", line_color="#dadce0", line_width=1.5, opacity=0.8)

        fig.update_layout(
            plot_bgcolor='white', paper_bgcolor='white', height=320,
            margin=dict(l=60, r=20, t=16, b=50),
            xaxis=dict(
                showgrid=True, gridcolor='#f1f3f4',
                title=dict(text="Month", font=dict(color='#5f6368', size=11)),
                tickfont=dict(color='#5f6368', size=11),
                showline=True, linecolor='#e0e0e0'
            ),
            yaxis=dict(
                showgrid=True, gridcolor='#f1f3f4',
                title=dict(text="Revenue ($)", font=dict(color='#5f6368', size=11)),
                tickfont=dict(color='#5f6368', size=11),
                tickformat='$,.0f',
                range=[0, max(df_chart['sales'].max(), max(forecast_values) if forecast_values else 0) * 1.15]  # max(forecast_values) crashes on empty list bug fixed
            ),
            # I added this to every single fig.update_layout call to ensure that
            # all charts will have their hover labels left-aligned instead of the random
            # left and right sometimes.
            hoverlabel=dict(align="left"),
            legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5, font=dict(color='#5f6368', size=11)),
            hovermode='x unified',
            font=dict(color='#202124', family='Google Sans, Roboto')
        )

        st.plotly_chart(fig, use_container_width=True)

    # ── Alert panel ───────────────────────────────────────────────────────────
    # Powered by James's alerter. Each card shows:
    #   - Direction label (Sales Increasing / Sales Decreasing)
    #   - Product name
    #   - Estimated % change from normal range (derived from James's severity score)
    # Color coding: Green = sales spike up (good), Red = sales spike down (bad)

    margin_alert_notice_html = (
        f"<p style='color: #5f6368; font-size: 0.78rem; margin: 0.75rem 0 0 0; "
        f"border-left: 3px solid #5f6368; padding-left: 0.75rem;'>"
        f"{html.escape(margin_alert_notice)}</p>"
    ) if margin_alert_notice else ""

    with col_alerts:
        if alerts_df.empty:
            # All clear state: no flags in the filtered data.
            st.markdown(f"""
                <div style='background-color: #ffffff; padding: 1.25rem 1.5rem;
                            border-radius: 0; border: 1px solid #e0e0e0;
                            border-top: 3px solid #0f9d58; height: 100%;'>
                    <p style='color: #5f6368; font-size: 0.72rem; font-weight: 500;
                              text-transform: uppercase; letter-spacing: 0.05em;
                              margin: 0 0 1rem 0;'>Alert Center</p>
                    <div style='background-color: #e6f4ea; border-radius: 4px;
                                padding: 1.25rem; text-align: center;'>
                        <p style='color: #0b8043; font-weight: 500; font-size: 0.9rem; margin: 0;'>All Clear</p>
                        <p style='color: #5f6368; font-size: 0.8rem; margin: 0.25rem 0 0 0;'>No issues detected</p>
                    </div>
                    {margin_alert_notice_html}
                </div>
            """, unsafe_allow_html=True)
        else:
            # Browser-native details toggle: instant open/close without a Streamlit rerun.
            alert_cards_html = ""

            for _, alert in alerts_df.iterrows():
                severity = float(alert['severity'])
                pct      = round((severity - 1) * 25)

                if alert['alert_type'] == "Sales Anomaly":
                    try:
                        parts   = alert['metric'].split()
                        current = float(parts[2])
                        mean    = float(parts[-1])
                        is_up   = current > mean
                    except:
                        is_up = severity > 2.5

                    if is_up:
                        color = "#0b8043"; bg = "#e6f4ea"
                        label = "📈 Sales Increasing"
                        plain_metric = f"Up ~{pct}% above normal range"
                    else:
                        color = "#d93025"; bg = "#fce8e6"
                        label = "📉 Sales Decreasing"
                        plain_metric = f"Down ~{pct}% below normal range"

                elif alert['alert_type'] == "Demand Decline":
                    color = "#d93025"; bg = "#fce8e6"
                    label = "📉 Sales Decreasing"
                    plain_metric = f"Down ~{pct}% below normal range"

                else:
                    color = "#5f6368"; bg = "#f1f3f4"
                    label = "⚠️ Low Profit Margin"
                    plain_metric = "This product has been losing money for multiple periods"

                # Andrew Garcia Leopold: show the product name even if the alert data
                # arrives as "product" instead of "product_name".
                alert_product_name = alert.get("product_name", alert.get("product", "Unknown product"))

                alert_cards_html += dedent(f"""
                <div style='background-color: {bg}; padding: 0.75rem 1rem;
                            margin-top: 2px; border-left: 3px solid {color};'>
                    <span style='color: {color}; font-size: 0.7rem; font-weight: 500;'>
                        {html.escape(label)}
                    </span>
                    <p style='margin: 0.2rem 0 0 0; color: #202124; font-size: 0.85rem; font-weight: 500;'>
                        {html.escape(str(alert_product_name))}
                    </p>
                    <p style='margin: 0.1rem 0 0 0; color: #5f6368; font-size: 0.75rem;'>
                        {html.escape(plain_metric)}
                    </p>
                </div>
                """)

            # Andrew Garcia Leopold: use components.html to keep Alert Center working on different Streamlit versions.
            # The details tag still opens/closes instantly, and the alert list scrolls inside the card.
            components.html(dedent(f"""
                <style>
                    .alert-toggle {{
                        font-family: "Google Sans", Roboto, sans-serif;
                    }}
                    details.alert-toggle > summary {{
                        list-style: none;
                        cursor: pointer;
                    }}
                    details.alert-toggle > summary::-webkit-details-marker {{
                        display: none;
                    }}
                </style>
                <details class='alert-toggle'>
                    <summary>
                        <div style='background-color: #ffffff; padding: 1rem 1.5rem 0.75rem 1.5rem;
                                    border-radius: 0; border: 1px solid #e0e0e0;
                                    border-top: 3px solid #d93025; display: flex;
                                    align-items: center; justify-content: space-between; gap: 1rem;'>
                            <div>
                                <p style='color: #5f6368; font-size: 0.72rem; font-weight: 500;
                                          text-transform: uppercase; letter-spacing: 0.05em; margin: 0 0 0.35rem 0;'>
                                    Alert Center
                                </p>
                                <span style='background: #fce8e6; color: #d93025; font-size: 0.75rem;
                                             font-weight: 500; padding: 0.2rem 0.6rem; border-radius: 2px;'>
                                    {len(alerts_df)} Active
                                </span>
                            </div>
                            <span style='background-color: #ffffff; color: #0f9d58; border: 1px solid #dadce0;
                                         border-radius: 4px; padding: 0.35rem 0.7rem; font-size: 0.8rem;
                                         font-weight: 500; white-space: nowrap;'>
                                Show / hide details
                            </span>
                        </div>
                    </summary>
                    <div style='border-left: 1px solid #e0e0e0; border-right: 1px solid #e0e0e0;
                                border-bottom: 1px solid #e0e0e0; max-height: 280px;
                                overflow-y: auto;'>
                        {margin_alert_notice_html}
                        {alert_cards_html}
                    </div>
                </details>
            """).strip(), height=350)

# TAB 2 — PRODUCTS
# Answers: Which products should I care about?

with tab2:

    # ── Top 5 Best & Worst Sellers ────────────────────────────────────────────
    # Quick scan cards — green for winners, red for underperformers.

    col_best, col_worst = st.columns(2)

    with col_best:
        st.markdown("""
            <div style='background-color: #ffffff; padding: 1rem 1.5rem 0.75rem 1.5rem;
                        border-radius: 0; border: 1px solid #e0e0e0;
                        border-top: 3px solid #0f9d58; border-bottom: none;'>
                <p style='color: #5f6368; font-size: 0.72rem; font-weight: 500;
                          text-transform: uppercase; letter-spacing: 0.05em; margin: 0 0 0.25rem 0;'>
                    Top Performers
                </p>
                <p style='color: #202124; font-size: 0.8rem; margin: 0;'>
                    Products driving the most revenue
                </p>
            </div>
        """, unsafe_allow_html=True)

        for i, row in top5.iterrows():
            rank = i + 1
            st.markdown(f"""
                <div style='background-color: #ffffff; padding: 0.75rem 1.5rem;
                            border-left: 1px solid #e0e0e0; border-right: 1px solid #e0e0e0;
                            border-bottom: 1px solid #f1f3f4;
                            display: flex; justify-content: space-between; align-items: center;'>
                    <div style='display: flex; align-items: center; gap: 0.75rem;'>
                        <span style='background-color: #e6f4ea; color: #0b8043;
                                     font-size: 0.7rem; font-weight: 600;
                                     width: 1.4rem; height: 1.4rem; border-radius: 50%;
                                     display: inline-flex; align-items: center; justify-content: center;'>
                            {rank}
                        </span>
                        <span style='color: #202124; font-size: 0.875rem; font-weight: 500;'>
                            {row['product']}
                        </span>
                    </div>
                    <span style='color: #0b8043; font-size: 0.875rem; font-weight: 500;'>
                        ${row['total_sales']:,.0f}
                    </span>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("""
            <div style='background-color: #ffffff; height: 0.75rem;
                        border-left: 1px solid #e0e0e0; border-right: 1px solid #e0e0e0;
                        border-bottom: 1px solid #e0e0e0;'>
            </div>
        """, unsafe_allow_html=True)

    with col_worst:
        st.markdown("""
            <div style='background-color: #ffffff; padding: 1rem 1.5rem 0.75rem 1.5rem;
                        border-radius: 0; border: 1px solid #e0e0e0;
                        border-top: 3px solid #d93025; border-bottom: none;'>
                <p style='color: #5f6368; font-size: 0.72rem; font-weight: 500;
                          text-transform: uppercase; letter-spacing: 0.05em; margin: 0 0 0.25rem 0;'>
                    Underperformers
                </p>
                <p style='color: #202124; font-size: 0.8rem; margin: 0;'>
                    Products generating the least revenue
                </p>
            </div>
        """, unsafe_allow_html=True)

        for i, row in bottom5.iterrows():
            rank = i + 1
            st.markdown(f"""
                <div style='background-color: #ffffff; padding: 0.75rem 1.5rem;
                            border-left: 1px solid #e0e0e0; border-right: 1px solid #e0e0e0;
                            border-bottom: 1px solid #f1f3f4;
                            display: flex; justify-content: space-between; align-items: center;'>
                    <div style='display: flex; align-items: center; gap: 0.75rem;'>
                        <span style='background-color: #fce8e6; color: #d93025;
                                     font-size: 0.7rem; font-weight: 600;
                                     width: 1.4rem; height: 1.4rem; border-radius: 50%;
                                     display: inline-flex; align-items: center; justify-content: center;'>
                            {rank}
                        </span>
                        <span style='color: #202124; font-size: 0.875rem; font-weight: 500;'>
                            {row['product']}
                        </span>
                    </div>
                    <span style='color: #d93025; font-size: 0.875rem; font-weight: 500;'>
                        ${row['total_sales']:,.0f}
                    </span>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("""
            <div style='background-color: #ffffff; height: 0.75rem;
                        border-left: 1px solid #e0e0e0; border-right: 1px solid #e0e0e0;
                        border-bottom: 1px solid #e0e0e0;'>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin: 1.5rem 0 0.5rem 0;'></div>", unsafe_allow_html=True)

    # ── Top 5 Product Trend Lines + MoM Change ────────────────────────────────
    # Left: are my best products growing or declining over time?
    # Right: which products had the biggest jump or drop last month?

    col_trend, col_mom = st.columns([3, 2])

    with col_trend:
        st.markdown("""
            <div style='background-color: #ffffff; padding: 1rem 1.5rem 0.5rem 1.5rem;
                        border-radius: 0; border: 1px solid #e0e0e0;
                        border-bottom: none; border-top: 3px solid #0f9d58;'>
                <p style='color: #5f6368; font-size: 0.72rem; font-weight: 500;
                          text-transform: uppercase; letter-spacing: 0.05em; margin: 0 0 0.25rem 0;'>
                    Top 5 Product Trends
                </p>
                <p style='color: #202124; font-size: 0.8rem; margin: 0;'>
                    Are your best sellers growing or declining month over month?
                </p>
            </div>
        """, unsafe_allow_html=True)

        # Build monthly sales per product for top 5
        top5_names = top5['product'].tolist()
        product_monthly = (
            df_filtered[df_filtered[name_col].isin(top5_names)]
            .groupby([name_col, df_filtered[df_filtered[name_col].isin(top5_names)]['date'].dt.to_period('M')])['sales']
            .sum().reset_index()
        )
        product_monthly['period'] = product_monthly['date'].astype(str)
        product_monthly = product_monthly.rename(columns={name_col: 'product'})

        fig_prod_trend = go.Figure()
        for i, prod in enumerate(top5_names):
            prod_data = product_monthly[product_monthly['product'] == prod]
            fig_prod_trend.add_trace(go.Scatter(
                x=prod_data['period'], y=prod_data['sales'],
                mode='lines', name=str(prod),
                line=dict(color=category_colors[i % len(category_colors)], width=2),
                hovertemplate=f'<b>{prod}</b><br>%{{x}}<br>Revenue: $%{{y:,.0f}}<extra></extra>'
            ))

        fig_prod_trend.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            height=360, margin=dict(l=60, r=20, t=16, b=60),
            xaxis=dict(showgrid=True, gridcolor='#f1f3f4',
                       tickfont=dict(color='#5f6368', size=10),
                       title=dict(text="Month", font=dict(color='#5f6368', size=11))),
            yaxis=dict(showgrid=True, gridcolor='#f1f3f4',
                       tickfont=dict(color='#5f6368', size=11), tickformat='$,.0f',
                       title=dict(text="Revenue ($)", font=dict(color='#5f6368', size=11))),
            hoverlabel=dict(align="left"),
            legend=dict(orientation="h", yanchor="top", y=-0.2,
                        xanchor="center", x=0.5, font=dict(color='#5f6368', size=10)),
            hovermode='x unified',
            font=dict(color='#202124', family='Google Sans, Roboto')
        )

        st.plotly_chart(fig_prod_trend, use_container_width=True, key="tab2_prod_trend")

    with col_mom:
        st.markdown("""
            <div style='background-color: #ffffff; padding: 1rem 1.5rem 0.75rem 1.5rem;
                        border-radius: 0; border: 1px solid #e0e0e0;
                        border-top: 3px solid #1a73e8; border-bottom: none;'>
                <p style='color: #5f6368; font-size: 0.72rem; font-weight: 500;
                          text-transform: uppercase; letter-spacing: 0.05em; margin: 0 0 0.25rem 0;'>
                    Month-over-Month Change
                </p>
                <p style='color: #202124; font-size: 0.8rem; margin: 0;'>
                    Biggest movers vs the previous month
                </p>
            </div>
        """, unsafe_allow_html=True)

        # Calculate MoM % change per product — last month vs month before
        df_filtered_copy = df_filtered.copy()
        df_filtered_copy['period'] = df_filtered_copy['date'].dt.to_period('M')
        product_period = (
            df_filtered_copy.groupby([name_col, 'period'])['sales']
            .sum().reset_index()
        )
        product_period = product_period.rename(columns={name_col: 'product'})

        all_periods = sorted(product_period['period'].unique())

        if len(all_periods) >= 2:
            last_period_p  = all_periods[-1]
            prev_period_p  = all_periods[-2]

            last_sales = product_period[product_period['period'] == last_period_p].set_index('product')['sales']
            prev_sales = product_period[product_period['period'] == prev_period_p].set_index('product')['sales']

            mom_df = pd.DataFrame({'last': last_sales, 'prev': prev_sales}).dropna()
            mom_df['pct_change'] = ((mom_df['last'] - mom_df['prev']) / mom_df['prev'] * 100).round(1)
            mom_df = mom_df.sort_values('pct_change', ascending=False).reset_index()

            # Show top 4 gainers and top 4 decliners
            gainers  = mom_df.head(4)
            decliners = mom_df.tail(4).sort_values('pct_change')

            for _, row in gainers.iterrows():
                arrow = "↑"
                st.markdown(f"""
                    <div style='background-color: #f8fff9; padding: 0.6rem 1.5rem;
                                border-left: 1px solid #e0e0e0; border-right: 1px solid #e0e0e0;
                                border-bottom: 1px solid #f1f3f4;
                                display: flex; justify-content: space-between; align-items: center;'>
                        <span style='color: #202124; font-size: 0.8rem; font-weight: 500;
                                     white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
                                     max-width: 60%;'>
                            {str(row['product'])}
                        </span>
                        <span style='color: #0b8043; font-size: 0.85rem; font-weight: 600;
                                     white-space: nowrap;'>
                            {arrow} {row['pct_change']:+.1f}%
                        </span>
                    </div>
                """, unsafe_allow_html=True)

            st.markdown("""
                <div style='background-color: #f1f3f4; padding: 0.3rem 1.5rem;
                            border-left: 1px solid #e0e0e0; border-right: 1px solid #e0e0e0;
                            border-bottom: 1px solid #e0e0e0;'>
                    <span style='color: #5f6368; font-size: 0.68rem; font-weight: 500;
                                 text-transform: uppercase; letter-spacing: 0.05em;'>
                        Biggest Declines
                    </span>
                </div>
            """, unsafe_allow_html=True)

            for _, row in decliners.iterrows():
                arrow = "↓"
                st.markdown(f"""
                    <div style='background-color: #ffffff; padding: 0.6rem 1.5rem;
                                border-left: 1px solid #e0e0e0; border-right: 1px solid #e0e0e0;
                                border-bottom: 1px solid #f1f3f4;
                                display: flex; justify-content: space-between; align-items: center;'>
                        <span style='color: #202124; font-size: 0.8rem; font-weight: 500;
                                     white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
                                     max-width: 60%;'>
                            {str(row['product'])}
                        </span>
                        <span style='color: #d93025; font-size: 0.85rem; font-weight: 600;
                                     white-space: nowrap;'>
                            {arrow} {row['pct_change']:+.1f}%
                        </span>
                    </div>
                """, unsafe_allow_html=True)

            st.markdown("""
                <div style='background-color: #ffffff; height: 0.75rem;
                            border-left: 1px solid #e0e0e0; border-right: 1px solid #e0e0e0;
                            border-bottom: 1px solid #e0e0e0;'>
                </div>
            """, unsafe_allow_html=True)

        else:
            st.markdown("""
                <div style='background-color: #f8f9fa; padding: 1.25rem; text-align: center;
                            border: 1px solid #e0e0e0; border-top: none;'>
                    <p style='color: #5f6368; font-size: 0.85rem; margin: 0;'>
                        Need at least 2 months of data to show month-over-month change.
                    </p>
                </div>
            """, unsafe_allow_html=True)

# TAB 3 — ANALYSIS
# Answers: Where is the money coming from?

with tab3:
    # ── Category Breakdown ────────────────────────────────────────────────────
    # Two charts side by side answering different but complementary questions:
    #   Bar chart  → "How much revenue does each category generate?" (absolute $)
    #   Donut chart → "What share of total revenue does each category represent?" (%)
    # Together they give a complete picture of category performance.
    # Both update with store/category filters.

    col_bar, col_pie = st.columns(2)

    with col_bar:
        st.markdown("""
            <div style='background-color: #ffffff; padding: 1rem 1.5rem 0.5rem 1.5rem;
                        border-radius: 0; border: 1px solid #e0e0e0;
                        border-bottom: none; border-top: 3px solid #0f9d58;'>
                <p style='color: #5f6368; font-size: 0.72rem; font-weight: 500;
                          text-transform: uppercase; letter-spacing: 0.05em; margin: 0 0 0.25rem 0;'>
                    Revenue by Category
                </p>
                <p style='color: #202124; font-size: 0.8rem; margin: 0;'>
                    Total revenue generated per category
                </p>
            </div>
        """, unsafe_allow_html=True)

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=category_sales['category'],
            y=category_sales['total_sales'],
            marker_color=category_colors[:len(category_sales)],
            # Labels shown on/above each bar so small bars are still readable
            text=[f"${v:,.0f}" for v in category_sales['total_sales']],
            textposition='auto',   # Plotly decides inside vs outside per bar
            cliponaxis=False,      # Prevents labels from being cut off at chart edge
            textfont=dict(size=10, color='#202124'),
            hovertemplate='<b>%{x}</b><br>Revenue: $%{y:,.0f}<extra></extra>'
        ))

        fig_bar.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            height=360, margin=dict(l=60, r=20, t=16, b=50),
            xaxis=dict(
                showgrid=False,
                tickfont=dict(color='#5f6368', size=11),
                showline=True, linecolor='#e0e0e0'
            ),
            yaxis=dict(
                showgrid=True, gridcolor='#f1f3f4',
                title=dict(text="Revenue ($)", font=dict(color='#5f6368', size=11)),
                tickfont=dict(color='#5f6368', size=11),
                tickformat='$,.0f',
                # 25% headroom above tallest bar so outside labels are never clipped
                range=[0, category_sales['total_sales'].max() * 1.25]
            ),
            hoverlabel=dict(align="left"),
            showlegend=False,
            font=dict(color='#202124', family='Google Sans, Roboto')
        )

        st.plotly_chart(fig_bar, use_container_width=True)

    with col_pie:
        st.markdown("""
            <div style='background-color: #ffffff; padding: 1rem 1.5rem 0.5rem 1.5rem;
                        border-radius: 0; border: 1px solid #e0e0e0;
                        border-bottom: none; border-top: 3px solid #1a73e8;'>
                <p style='color: #5f6368; font-size: 0.72rem; font-weight: 500;
                          text-transform: uppercase; letter-spacing: 0.05em; margin: 0 0 0.25rem 0;'>
                    Revenue Share
                </p>
                <p style='color: #202124; font-size: 0.8rem; margin: 0;'>
                    Each category as a % of total revenue
                </p>
            </div>
        """, unsafe_allow_html=True)

        fig_pie = go.Figure()
        fig_pie.add_trace(go.Pie(
            labels=category_sales['category'],
            values=category_sales['total_sales'],
            marker=dict(colors=category_colors[:len(category_sales)]),
            hole=0.4,  # Donut style — cleaner and more modern than a full pie
            hovertemplate='<b>%{label}</b><br>Revenue: $%{value:,.0f}<br>Share: %{percent}<extra></extra>'
        ))

        fig_pie.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            height=360, margin=dict(l=20, r=20, t=16, b=50),
            legend=dict(
                orientation="h", yanchor="top", y=-0.15,
                xanchor="center", x=0.5,
                font=dict(color='#5f6368', size=10)
            ),
            hoverlabel=dict(align="left"),
            font=dict(color='#202124', family='Google Sans, Roboto')
        )

        st.plotly_chart(fig_pie, use_container_width=True)

    # Andrew Garcia Leopold: Store Breakdown / Store Comparison.
    # This shows stores side by side using total sales from the filtered data.
    # It supports the Segment Analysis task by making store performance easy to compare.
    st.markdown("<div style='margin: 1.5rem 0 0.5rem 0;'></div>", unsafe_allow_html=True)

    st.markdown("""
        <div style='background-color: #ffffff; padding: 1rem 1.5rem 0.5rem 1.5rem;
                    border-radius: 0; border: 1px solid #e0e0e0;
                    border-bottom: none; border-top: 3px solid #0f9d58;'>
            <p style='color: #5f6368; font-size: 0.72rem; font-weight: 500;
                      text-transform: uppercase; letter-spacing: 0.05em; margin: 0 0 0.25rem 0;'>
                Store Comparison
            </p>
            <p style='color: #202124; font-size: 0.8rem; margin: 0;'>
                Total revenue by store for the selected filters
            </p>
        </div>
    """, unsafe_allow_html=True)

    fig_store = go.Figure()
    fig_store.add_trace(go.Bar(
        x=store_sales['store_id'].astype(str),
        y=store_sales['total_sales'],
        # Made it so that the colors on the store comparison will differ for each store
        # With the number of colors being the number of stores in the filtered data.
        marker_color=category_colors[:len(store_sales)],
        text=[f"${v:,.0f}" for v in store_sales['total_sales']],
        textposition='auto',
        cliponaxis=False,
        textfont=dict(size=10, color='#202124'),
        hovertemplate='<b>Store %{x}</b><br>Revenue: $%{y:,.0f}<extra></extra>'
    ))

    fig_store.update_layout(
        plot_bgcolor='white', paper_bgcolor='white',
        height=360, margin=dict(l=60, r=20, t=16, b=50),
        xaxis=dict(
            title=dict(text="Store ID", font=dict(color='#5f6368', size=11)),
            showgrid=False,
            tickfont=dict(color='#5f6368', size=11),
            showline=True, linecolor='#e0e0e0'
        ),
        yaxis=dict(
            title=dict(text="Revenue ($)", font=dict(color='#5f6368', size=11)),
            showgrid=True, gridcolor='#f1f3f4',
            tickfont=dict(color='#5f6368', size=11),
            tickformat='$,.0f',
            range=[0, store_sales['total_sales'].max() * 1.25]
        ),
        hoverlabel=dict(align="left"),
        showlegend=False,
        font=dict(color='#202124', family='Google Sans, Roboto')
    )

    st.plotly_chart(fig_store, use_container_width=True)

# TAB 4 — MODEL
# Answers: Which forecasting model is the most accurate and why?
# Shows Alberto's model benchmarking results in a clean card layout.

with tab4:

    # ── Model Accuracy panel ──────────────────────────────────────────────────
    # Reads from model_comparison.csv if available, falls back to forecast residuals.
    # Replaces the ugly default st.dataframe with styled card rows matching the
    # rest of the dashboard aesthetic.

    st.markdown("""
        <div style='background-color: #ffffff; padding: 1rem 1.5rem 0.5rem 1.5rem;
                    border-radius: 0; border: 1px solid #e0e0e0;
                    border-bottom: none; border-top: 3px solid #1a73e8;'>
            <p style='color: #5f6368; font-size: 0.72rem; font-weight: 500;
                      text-transform: uppercase; letter-spacing: 0.05em; margin: 0 0 0.25rem 0;'>
                Model Accuracy
            </p>
            <p style='color: #202124; font-size: 0.8rem; margin: 0;'>
                Forecast methods compared — lower MAE and RMSE is better
            </p>
        </div>
    """, unsafe_allow_html=True)

    if model_accuracy_df is None or model_accuracy_df.empty:
        st.markdown("""
            <div style='background-color: #f8f9fa; border: 1px solid #e0e0e0; border-top: none;
                        padding: 1.5rem; text-align: center;'>
                <p style='color: #5f6368; font-size: 0.875rem; margin: 0;'>
                    No model accuracy data available yet.
                </p>
            </div>
        """, unsafe_allow_html=True)
    else:
        accuracy_view = model_accuracy_df.copy()
        winner_rows   = accuracy_view[accuracy_view["selected_winner"] == True]
        if winner_rows.empty and "mae" in accuracy_view.columns and accuracy_view["mae"].notna().any():
            winner_row = accuracy_view.loc[accuracy_view["mae"].idxmin()]
        elif winner_rows.empty:
            winner_row = accuracy_view.iloc[0]
        else:
            winner_row = winner_rows.iloc[0]

        winner_name = str(winner_row.get("method_name", method_used or "Unknown"))
        winner_mae  = winner_row.get("mae", pd.NA)
        winner_rmse = winner_row.get("rmse", pd.NA)
        mae_str     = f"{float(winner_mae):,.3f}"  if pd.notna(winner_mae)  else "N/A"
        rmse_str    = f"{float(winner_rmse):,.3f}" if pd.notna(winner_rmse) else "N/A"

        # ── Winner highlight banner ───────────────────────────────────────────
        # Shows the winning model prominently with key metrics at a glance.

        st.markdown(f"""
            <div style='background-color: #e6f4ea; border: 1px solid #ceead6;
                        border-top: none; padding: 1rem 1.5rem; margin-bottom: 1px;
                        display: flex; align-items: center;
                        justify-content: space-between; flex-wrap: wrap; gap: 1rem;'>
                <div style='display: flex; align-items: center; gap: 0.75rem;'>
                    <span style='background-color: #0f9d58; color: #ffffff; font-size: 0.7rem;
                                 font-weight: 600; padding: 0.2rem 0.6rem; border-radius: 2px;
                                 text-transform: uppercase; letter-spacing: 0.05em;'>
                        ✓ Winner
                    </span>
                    <span style='color: #202124; font-size: 1rem; font-weight: 500;'>
                        {winner_name}
                    </span>
                </div>
                <div style='display: flex; gap: 2.5rem;'>
                    <div style='text-align: center;'>
                        <p style='color: #5f6368; font-size: 0.7rem; font-weight: 500;
                                  text-transform: uppercase; letter-spacing: 0.06em; margin: 0;'>MAE</p>
                        <p style='color: #0b8043; font-size: 1.2rem; font-weight: 500; margin: 0;'>{mae_str}</p>
                    </div>
                    <div style='text-align: center;'>
                        <p style='color: #5f6368; font-size: 0.7rem; font-weight: 500;
                                  text-transform: uppercase; letter-spacing: 0.06em; margin: 0;'>RMSE</p>
                        <p style='color: #0b8043; font-size: 1.2rem; font-weight: 500; margin: 0;'>{rmse_str}</p>
                    </div>
                    <div style='text-align: center;'>
                        <p style='color: #5f6368; font-size: 0.7rem; font-weight: 500;
                                  text-transform: uppercase; letter-spacing: 0.06em; margin: 0;'>Models</p>
                        <p style='color: #0b8043; font-size: 1.2rem; font-weight: 500; margin: 0;'>{len(accuracy_view)}</p>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # ── Model comparison rows — styled like top/bottom sellers ────────────
        # One row per model, winner highlighted in green, others in neutral.

        for _, model_row in accuracy_view.iterrows():
            is_winner  = bool(model_row.get("selected_winner", False))
            m_name     = str(model_row.get("method_name", "Unknown"))
            m_mae      = model_row.get("mae", pd.NA)
            m_rmse     = model_row.get("rmse", pd.NA)
            m_mae_str  = f"{float(m_mae):,.3f}"  if pd.notna(m_mae)  else "—"
            m_rmse_str = f"{float(m_rmse):,.3f}" if pd.notna(m_rmse) else "—"

            row_bg     = "#f8fff9" if is_winner else "#ffffff"
            name_color = "#0b8043" if is_winner else "#202124"
            name_weight = "600" if is_winner else "400"
            best_badge  = "<span style='background-color:#e6f4ea; color:#0b8043; font-size:0.68rem; font-weight:600; padding:0.15rem 0.5rem; border-radius:2px; margin-left:0.5rem;'>✓ Best</span>" if is_winner else ""

            st.markdown(f"""
                <div style='background-color: {row_bg}; padding: 0.75rem 1.5rem;
                            border-left: 1px solid #e0e0e0; border-right: 1px solid #e0e0e0;
                            border-bottom: 1px solid #f1f3f4;
                            display: flex; justify-content: space-between; align-items: center;'>
                    <span style='color: {name_color}; font-size: 0.875rem; font-weight: {name_weight};'>
                        {m_name}{best_badge}
                    </span>
                    <div style='display: flex; gap: 2.5rem;'>
                        <div style='text-align: right;'>
                            <p style='color: #5f6368; font-size: 0.68rem; text-transform: uppercase;
                                      letter-spacing: 0.05em; margin: 0;'>MAE</p>
                            <p style='color: {name_color}; font-size: 0.875rem;
                                      font-weight: 500; margin: 0;'>{m_mae_str}</p>
                        </div>
                        <div style='text-align: right;'>
                            <p style='color: #5f6368; font-size: 0.68rem; text-transform: uppercase;
                                      letter-spacing: 0.05em; margin: 0;'>RMSE</p>
                            <p style='color: {name_color}; font-size: 0.875rem;
                                      font-weight: 500; margin: 0;'>{m_rmse_str}</p>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

        # Bottom border to close the card visually
        st.markdown("""
            <div style='background-color: #ffffff; height: 0.75rem;
                        border-left: 1px solid #e0e0e0; border-right: 1px solid #e0e0e0;
                        border-bottom: 1px solid #e0e0e0; margin-bottom: 1.5rem;'>
            </div>
        """, unsafe_allow_html=True)

        # ── MAE comparison bar chart — wrapped in a card ──────────────────────
        # Visual comparison of all models — green bar = winner, gray = others.

        if "mae" in accuracy_view.columns and accuracy_view["mae"].notna().any():
            st.markdown("""
                <div style='background-color: #ffffff; padding: 1rem 1.5rem 0.5rem 1.5rem;
                            border-radius: 0; border: 1px solid #e0e0e0;
                            border-bottom: none; border-top: 3px solid #0f9d58;'>
                    <p style='color: #5f6368; font-size: 0.72rem; font-weight: 500;
                              text-transform: uppercase; letter-spacing: 0.05em; margin: 0 0 0.25rem 0;'>
                        MAE Comparison
                    </p>
                    <p style='color: #202124; font-size: 0.8rem; margin: 0;'>
                        Lower is better — green bar is the winning model
                    </p>
                </div>
            """, unsafe_allow_html=True)

            chart_df = accuracy_view.dropna(subset=["mae"]).sort_values("mae")
            fig_accuracy = go.Figure()
            fig_accuracy.add_trace(go.Bar(
                x=chart_df["method_name"],
                y=chart_df["mae"],
                marker_color=["#0f9d58" if s else "#dadce0" for s in chart_df["selected_winner"]],
                text=[f"{v:.3f}" for v in chart_df["mae"]],
                textposition="outside",
                cliponaxis=False,
                textfont=dict(size=11, color='#202124'),
                hovertemplate="<b>%{x}</b><br>MAE: %{y:.3f}<extra></extra>",
            ))
            fig_accuracy.update_layout(
                plot_bgcolor="white", paper_bgcolor="white",
                height=280, margin=dict(l=40, r=20, t=16, b=50),
                xaxis=dict(tickfont=dict(color="#5f6368", size=11), showgrid=False,
                           showline=True, linecolor='#e0e0e0'),
                yaxis=dict(
                    title=dict(text="MAE (lower is better)", font=dict(color="#5f6368", size=11)),
                    tickfont=dict(color="#5f6368", size=11), showgrid=True, gridcolor="#f1f3f4",
                    range=[0, chart_df["mae"].max() * 1.3]
                ),
                hoverlabel=dict(align="left"),
                showlegend=False,
                font=dict(color="#202124", family="Google Sans, Roboto"),
            )
            st.plotly_chart(fig_accuracy, use_container_width=True)

        st.markdown(f"""
            <p style='color: #9aa0a6; font-size: 0.72rem; margin: 0.5rem 0 0 0;'>
                Accuracy source: {model_accuracy_source}
            </p>
        """, unsafe_allow_html=True)
