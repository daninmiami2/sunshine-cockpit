"""Data access layer for the Owner's Cockpit.

The app only ever calls ``load_all()``; where the numbers come from is decided here.

* ``CsvSource``        - the synthetic demo data in /data (default).
* ``QuickBooksSource`` - stub: invoices, expenses, payroll from QuickBooks Online.
* ``JobberSource``     - stub: jobs / visits / clients from Jobber.

Every source returns the same five DataFrames with the same columns (see ``SCHEMA``),
so swapping in live data never touches the UI code.
Select a source with the ``COCKPIT_SOURCE`` env var or Streamlit secret
(``csv`` | ``live``). ``live`` combines Jobber (jobs) + QuickBooks (money) and uses the
CSV for ad spend until a Meta/Google connector is added.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SCHEMA = {
    "jobs": ["job_id", "date", "service_type", "tech", "customer", "city", "lead_source", "revenue",
             "labor_cost", "materials_cost", "hours", "upsell", "callback", "gross_profit"],
    "payroll": ["pay_date", "employee", "role", "department", "cost_class", "hours", "gross_pay", "employer_taxes"],
    "ad_spend": ["date", "channel", "spend", "impressions", "clicks", "leads"],
    "invoices": ["invoice_id", "job_id", "customer", "service_type", "issue_date", "due_date", "amount",
                 "paid_date", "status", "paid_late"],
    "expenses": ["date", "category", "vendor", "amount"],
}
DATE_COLS = {
    "jobs": ["date"], "payroll": ["pay_date"], "ad_spend": ["date"],
    "invoices": ["issue_date", "due_date", "paid_date"], "expenses": ["date"],
}


def _setting(name: str, default: str = "") -> str:
    """Read a setting from env vars first, then Streamlit secrets (if running under Streamlit)."""
    if name in os.environ:
        return os.environ[name]
    try:
        import streamlit as st
        return str(st.secrets.get(name, default))
    except Exception:
        return default


class DataSource(ABC):
    name = "base"

    @abstractmethod
    def jobs(self) -> pd.DataFrame: ...
    @abstractmethod
    def payroll(self) -> pd.DataFrame: ...
    @abstractmethod
    def ad_spend(self) -> pd.DataFrame: ...
    @abstractmethod
    def invoices(self) -> pd.DataFrame: ...
    @abstractmethod
    def expenses(self) -> pd.DataFrame: ...

    def load_all(self) -> dict[str, pd.DataFrame]:
        return {k: getattr(self, k)() for k in SCHEMA}


class CsvSource(DataSource):
    name = "Demo CSV data"

    def __init__(self, directory: Path = DATA_DIR):
        self.dir = Path(directory)

    def _read(self, table: str) -> pd.DataFrame:
        path = self.dir / f"{table}.csv"
        if not path.exists():
            raise FileNotFoundError(f"{path} missing - run `python scripts/generate_data.py`")
        return pd.read_csv(path, parse_dates=DATE_COLS[table], encoding="utf-8")

    def jobs(self): return self._read("jobs")
    def payroll(self): return self._read("payroll")
    def ad_spend(self): return self._read("ad_spend")
    def invoices(self): return self._read("invoices")
    def expenses(self): return self._read("expenses")


class QuickBooksSource:
    """STUB - QuickBooks Online (Accounting API v3, OAuth2).

    Secrets expected: QBO_CLIENT_ID, QBO_CLIENT_SECRET, QBO_REFRESH_TOKEN, QBO_REALM_ID.
    Mapping to cockpit tables:
      invoices -> ``Invoice`` entity (Id, CustomerRef, TxnDate, DueDate, TotalAmt, Balance;
                  paid_date comes from the linked ``Payment`` entity's TxnDate).
      expenses -> ``Purchase`` / ``Bill`` entities, category from AccountRef.
      payroll  -> QuickBooks Payroll reports (or a Gusto/ADP export) - not in the core API.
    """
    name = "QuickBooks Online"

    def __init__(self):
        self.realm_id = _setting("QBO_REALM_ID")

    def _not_ready(self, what: str):
        raise NotImplementedError(f"QuickBooks connector not implemented yet ({what}). See class docstring.")

    def invoices(self) -> pd.DataFrame: self._not_ready("invoices")
    def expenses(self) -> pd.DataFrame: self._not_ready("expenses")
    def payroll(self) -> pd.DataFrame: self._not_ready("payroll")


class JobberSource:
    """STUB - Jobber (GraphQL API, OAuth2).

    Secrets expected: JOBBER_ACCESS_TOKEN.
    Mapping: ``jobs`` query -> jobs table (completed visits; ``total`` = revenue,
    line-item costs -> materials_cost, ``visits.assignedUsers`` -> tech, ``client`` -> customer,
    ``jobType`` -> service_type, request ``source`` -> lead_source). Labor cost = timesheet
    hours x loaded rate. Payments/invoices can also be read from Jobber if QuickBooks isn't used.
    """
    name = "Jobber"

    def __init__(self):
        self.token = _setting("JOBBER_ACCESS_TOKEN")

    def jobs(self) -> pd.DataFrame:
        raise NotImplementedError("Jobber connector not implemented yet. See class docstring.")


class LiveSource(CsvSource):
    """Jobber for jobs + QuickBooks for money; falls back to CSV for anything not yet wired up."""
    name = "Live (Jobber + QuickBooks)"

    def __init__(self):
        super().__init__()
        self.qbo, self.jobber = QuickBooksSource(), JobberSource()

    def jobs(self): return self.jobber.jobs()
    def invoices(self): return self.qbo.invoices()
    def expenses(self): return self.qbo.expenses()
    def payroll(self): return self.qbo.payroll()


def get_source() -> DataSource:
    return LiveSource() if _setting("COCKPIT_SOURCE", "csv").lower() == "live" else CsvSource()


def load_all() -> tuple[dict[str, pd.DataFrame], str]:
    """Return (tables, source_name). Validates columns so a bad connector fails loudly."""
    src = get_source()
    tables = src.load_all()
    for table, cols in SCHEMA.items():
        missing = set(cols) - set(tables[table].columns)
        if missing:
            raise ValueError(f"{src.name}: '{table}' is missing columns {sorted(missing)}")
    return tables, src.name
