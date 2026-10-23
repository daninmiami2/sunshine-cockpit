# Owner's Cockpit - Sunshine Comfort HVAC (demo)

Streamlit dashboard for a fictional Fort Lauderdale HVAC company (~$6.2M revenue, 28 employees).
Tabs: This Week, Revenue & Margin, Marketing, Team, Cash & AR.

## Run locally
```
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_data.py  # optional: regenerates /data (seeded, deterministic)
streamlit run app.py
```

## Layout
- `app.py` - UI. `cockpit/metrics.py` - calculations + Monday Morning Summary.
- `cockpit/data_sources.py` - the only data-access module: `CsvSource` (demo), `QuickBooksSource` and `JobberSource` stubs.
- `data/*.csv` - synthetic jobs, payroll, ad_spend, invoices, expenses (Oct 2025 - Sep 2026).

## Deploy to Streamlit Community Cloud
1. Push this repo to GitHub.
2. share.streamlit.io > New app > pick the repo, branch `main`, main file `app.py`.
3. Advanced settings: Python 3.12. Paste secrets from `.streamlit/secrets.toml.example` if needed.
