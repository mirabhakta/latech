# inventoryIQ - AI-Powered Retail Forecasting Engine
LA Tech Rising | Spring 2026 | Mentor: Ritesh Verma

A reusable retail forecasting engine that ingests historical sales data, forecasts future demand, flags unusual patterns, and generates plain-English summaries using the Gemini API.

## Team

| Role | Name | Primary Ownership |
|------|------|-------------------|
| Project Lead · Architecture & Infrastructure | Mira Bhakta | System design, model selection, testing suite, CI/CD, deployment, cross-role debugging |
| Co-Project Lead · Alerting Engine · Forecasting Co-Owner | James Ybarra | `models/alerter.py`, `models/forecaster.py` (co-owner) |
| Data Preparation & Schema Mapping · Dashboard Support | Andrew Garcia Leopold | `utils/processor.py` - schema mapping + derived fields |
| Data Preparation (Derived Fields) · AI Insights Support | Krisna Vega | `utils/trend.py` + derived fields in `processor.py` |
| Forecasting Engine · Alerting Co-Owner | Alberto Barboza | `models/forecaster.py`, `models/alerter.py` (co-owner) |
| AI Insights & Reporting · Dashboard Support | Sarah Abdeen | `utils/ai_summary.py` + AI Summary panel in `app.py` |
| Dashboard & Visualization · Integration Lead | Justin Hernandez | `app.py` — all views, sidebar, filters, layout, loading states |


## Tech Stack

### Backend
- Python
- FastAPI
- Uvicorn
- pandas
- NumPy
- scikit-learn
- LightGBM
- Google Gen AI SDK
- python-dotenv
- openpyxl

### Frontend
- React 19
- Vite
- React Router DOM
- Axios
- Recharts

## Local Setup

### 1. Clone the repository
```bash
git clone https://github.com/jybarra7/latech_InventoryIQ
cd latech_InventoryIQ
```

### 2. Set up the backend
Use Python 3.11 or 3.12. Python 3.14 may fail with older pinned dependencies on Windows.

```bash
python -m venv venv
```

Activate the virtual environment:

**Windows PowerShell**
```powershell
venv\Scripts\Activate
```

**macOS/Linux**
```bash
source venv/bin/activate
```

Install backend dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_api_key_here
```

Run the backend:

```bash
uvicorn main:app --reload
```

The backend should start at:
- `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

### 3. Set up the frontend

Open a second terminal and run:

```bash
cd frontend
npm install
npm run dev
```

The frontend should start at:
- `http://localhost:5173`

## Running the App

You need two terminals:

1. **Backend**
```bash
uvicorn main:app --reload
```

2. **Frontend**
```bash
cd frontend
npm run dev
```

## Features
- Upload any retail sales CSV and get an analysis-ready dashboard
- Schema mapping and clean dataset export for downstream pipeline stages
- Demand forecasts for the next 1–3 months with model accuracy comparison
- Automated alert panel flagging anomalies, declining demand, and margin losses
- Plain-English AI summary generated on demand via the Gemini API
- Interactive filters by date range, category, store, and region

## Security
Never commit your .env file. It is excluded from version control via .gitignore.
If a key is accidentally exposed, revoke it immediately in the Gemini console 
and generate a new one.
