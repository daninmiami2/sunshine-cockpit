"""Business metrics and plain-English insights. Pure pandas - no Streamlit imports."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

DAY = pd.Timedelta(days=1)
BUCKETS = ["Current", "1-30 days late", "31-60 days late", "61-90 days late", "90+ days late"]


def money(x: float, signed: bool = False) -> str:
    if x != x:  # NaN
        return "n/a"
    sign = ("+" if x >= 0 else "-") if signed else ("-" if x < 0 else "")
    x = abs(x)
    if x >= 1_000_000:
        return f"{sign}${x / 1_000_000:.2f}M"
    if x >= 10_000:
        return f"{sign}${x / 1_000:.0f}K"
    if x >= 1_000:
        return f"{sign}${x / 1_000:.1f}K"
    return f"{sign}${x:,.0f}"


def pct(x: float, digits: int = 0) -> str:
    if x != x:  # NaN
        return "n/a"
    return f"{x * 100:.{digits}f}%"


def safe_div(a, b):
    return a / b if b else np.nan


def between(df: pd.DataFrame, col: str, start, end) -> pd.DataFrame:
    """Rows with start <= col <= end (both inclusive, by day)."""
    return df[(df[col] >= pd.Timestamp(start)) & (df[col] < pd.Timestamp(end) + DAY)]


def week_end(start: pd.Timestamp) -> pd.Timestamp:
    return start + pd.Timedelta(days=6)


def monday_of(ts) -> pd.Timestamp:
    ts = pd.Timestamp(ts).normalize()
    return ts - pd.Timedelta(days=ts.dayofweek)


def available_weeks(jobs: pd.DataFrame) -> list[pd.Timestamp]:
    """Mondays of every *complete* week in the data."""
    first, last = jobs.date.min(), jobs.date.max()
    start = monday_of(first)
    if start < first:
        start += pd.Timedelta(days=7)
    weeks = pd.date_range(start, last, freq="7D")
    return [w for w in weeks if week_end(w) <= last]


# ---------------------------------------------------------------- weekly KPIs
@dataclass
class WeekKPIs:
    revenue: float
    gross_profit: float
    jobs: int
    avg_ticket: float
    leads: int
    ad_spend: float
    cpl: float
    collected: float

    @property
    def margin(self) -> float:
        return safe_div(self.gross_profit, self.revenue)


def week_kpis(t: dict[str, pd.DataFrame], start: pd.Timestamp) -> WeekKPIs:
    end = week_end(start)
    j = between(t["jobs"], "date", start, end)
    a = between(t["ad_spend"], "date", start, end)
    inv = between(t["invoices"].dropna(subset=["paid_date"]), "paid_date", start, end)
    return WeekKPIs(
        revenue=j.revenue.sum(), gross_profit=j.gross_profit.sum(), jobs=len(j),
        avg_ticket=safe_div(j.revenue.sum(), len(j)), leads=int(a.leads.sum()),
        ad_spend=a.spend.sum(), cpl=safe_div(a.spend.sum(), a.leads.sum()), collected=inv.amount.sum(),
    )


def delta(cur: float, prev: float) -> float:
    return safe_div(cur - prev, prev) if prev else np.nan


# ---------------------------------------------------------------- AR
def ar_open(invoices: pd.DataFrame, asof) -> pd.DataFrame:
    """Invoices issued on/before `asof` and still unpaid at `asof`, with aging columns."""
    asof = pd.Timestamp(asof)
    o = invoices[(invoices.issue_date <= asof) & (invoices.paid_date.isna() | (invoices.paid_date > asof))].copy()
    o["days_late"] = (asof - o.due_date).dt.days.clip(lower=0)
    o["bucket"] = pd.cut(o.days_late, [-1, 0, 30, 60, 90, 10_000], labels=BUCKETS)
    return o


def late_stats(invoices: pd.DataFrame, start, end) -> dict:
    """Share of invoices due in the window that were (or are) late."""
    due = between(invoices, "due_date", start, end)
    asof = pd.Timestamp(end)
    late = due[(due.paid_date > due.due_date) | (due.paid_date.isna() & (due.due_date < asof))
               | (due.paid_date > asof)]
    paid = due.dropna(subset=["paid_date"])
    return {"n": len(due), "late_n": len(late), "late_rate": safe_div(len(late), len(due)),
            "late_amount": late.amount.sum(),
            "avg_days_to_pay": (paid.paid_date - paid.issue_date).dt.days.mean()}


# ---------------------------------------------------------------- P&L / cash
# ---------------------------------------------------------------- "View by" periods
VIEWS = ["Weekly", "Monthly", "Quarterly"]
UNIT = {"Weekly": "week", "Monthly": "month", "Quarterly": "quarter"}
AXIS_TITLE = {"Weekly": "Week beginning (Monday)", "Monthly": "Month", "Quarterly": "Calendar quarter"}
_RESAMPLE = {"Weekly": "W-MON", "Monthly": "MS", "Quarterly": "QS"}  # W-MON + closed/label left = Monday-start weeks
_STEP = {"Weekly": "7D", "Monthly": "MS", "Quarterly": "QS"}


def period_starts(start, end, view: str) -> pd.DatetimeIndex:
    """Start date of every period that touches [start, end] (empty if end < start)."""
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    if end < start:
        return pd.DatetimeIndex([])
    first = {"Weekly": monday_of(start), "Monthly": start.to_period("M").start_time,
             "Quarterly": start.to_period("Q").start_time}[view]
    return pd.date_range(first, end, freq=_STEP[view])


def period_end(ps: pd.Timestamp, view: str) -> pd.Timestamp:
    if view == "Weekly":
        return ps + pd.Timedelta(days=6)
    return ps.to_period("M" if view == "Monthly" else "Q").end_time.normalize()


def resample_sum(df: pd.DataFrame, col: str, value_cols: list[str], start, end, view: str) -> pd.DataFrame:
    """Sum `value_cols` per period (Monday weeks / calendar months / calendar quarters).
    Every period in the range is present, with 0 where there were no rows."""
    idx = period_starts(start, end, view)
    d = between(df, col, start, end)
    s = d.set_index(col)[value_cols].resample(_RESAMPLE[view], closed="left", label="left").sum()
    return s.reindex(idx, fill_value=0.0).astype(float)


def period_meta(idx: pd.DatetimeIndex, start, end, view: str) -> pd.DataFrame:
    """Axis label, hover text and partial-period flag for each period start in `idx`."""
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    rows = []
    for ps in idx:
        pe = period_end(ps, view)
        partial = ps < start or pe > end
        if view == "Weekly":
            name, hover = f"{ps:%b} {ps.day} '{ps:%y}", f"Week of {ps:%b} {ps.day}, {ps.year}"
        elif view == "Monthly":
            name = hover = f"{ps:%b %Y}"
        else:
            name = hover = f"Q{ps.quarter} {ps.year}"
        rows.append(dict(start=ps, name=name, partial=partial,
                         label=name + ("*" if partial else ""),
                         hover=hover + (" (partial period)" if partial else "")))
    return pd.DataFrame(rows, columns=["start", "name", "partial", "label", "hover"])


def partial_note(meta: pd.DataFrame, view: str) -> str:
    p = meta[meta.partial]
    if p.empty:
        return ""
    names = ", ".join(p.name)
    return (f"* Partial period: {names}. Only part of that {UNIT[view]} falls inside the selected date range, "
            f"so its totals are lower than a full {UNIT[view]}.")


def period_pnl(t: dict[str, pd.DataFrame], start, end, view: str = "Monthly") -> pd.DataFrame:
    """P&L per period. Margins are recomputed from the summed dollars, never averaged."""
    pr = t["payroll"]
    pr = pr[pr.cost_class == "overhead"].assign(overhead_payroll=lambda d: d.gross_pay + d.employer_taxes)
    df = pd.concat([
        resample_sum(t["jobs"], "date", ["revenue", "labor_cost", "materials_cost"], start, end, view),
        resample_sum(pr, "pay_date", ["overhead_payroll"], start, end, view),
        resample_sum(t["expenses"], "date", ["amount"], start, end, view).rename(columns={"amount": "operating_expenses"}),
        resample_sum(t["ad_spend"], "date", ["spend"], start, end, view).rename(columns={"spend": "advertising"}),
    ], axis=1)
    # Guarantee every column downstream code reads exists, even if a source table is empty or lacks one.
    for c in ("revenue", "labor_cost", "materials_cost", "overhead_payroll", "operating_expenses", "advertising"):
        if c not in df.columns:
            df[c] = 0.0
    df = df.fillna(0.0)
    df["direct_costs"] = df.labor_cost + df.materials_cost
    df["gross_profit"] = df.revenue - df.direct_costs
    df["net_profit"] = df.gross_profit - df.overhead_payroll - df.operating_expenses - df.advertising
    rev = df.revenue.replace(0, np.nan)
    df["gross_margin"] = df.gross_profit / rev
    df["net_margin"] = df.net_profit / rev
    return df


def monthly_cash(t: dict[str, pd.DataFrame], start, end) -> pd.DataFrame:
    """Cash in = invoices by paid date. Cash out = materials, payroll, expenses, ads on their dates."""
    m = lambda s: s.dt.to_period("M").dt.to_timestamp()
    inv = between(t["invoices"].dropna(subset=["paid_date"]), "paid_date", start, end)
    j = between(t["jobs"], "date", start, end)
    pr = between(t["payroll"], "pay_date", start, end)
    ex = between(t["expenses"], "date", start, end)
    ad = between(t["ad_spend"], "date", start, end)
    df = pd.DataFrame({
        "collections": inv.groupby(m(inv.paid_date)).amount.sum(),
        "materials": j.groupby(m(j.date)).materials_cost.sum(),
        "payroll": (pr.gross_pay + pr.employer_taxes).groupby(m(pr.pay_date)).sum(),
        "expenses": ex.groupby(m(ex.date)).amount.sum(),
        "advertising": ad.groupby(m(ad.date)).spend.sum(),
    }).fillna(0)
    df["cash_out"] = df[["materials", "payroll", "expenses", "advertising"]].sum(axis=1)
    df["net_cash"] = df.collections - df.cash_out
    df["cumulative"] = df.net_cash.cumsum()
    return df


# ---------------------------------------------------------------- marketing
def channel_periods(ads: pd.DataFrame, start, end, view: str = "Monthly") -> pd.DataFrame:
    """Spend / leads per channel per period; cost per lead = summed spend / summed leads."""
    parts = []
    for ch in sorted(ads.channel.unique()):
        g = resample_sum(ads[ads.channel == ch], "date", ["spend", "leads", "clicks", "impressions"], start, end, view)
        parts.append(g.rename_axis("period").reset_index().assign(channel=ch))
    g = pd.concat(parts, ignore_index=True)
    g["cpl"] = g.spend / g.leads.replace(0, np.nan)
    return g


def channel_summary(ads: pd.DataFrame, jobs: pd.DataFrame, start, end) -> pd.DataFrame:
    a = between(ads, "date", start, end).groupby("channel")[["spend", "leads"]].sum()
    j = between(jobs, "date", start, end)
    jb = j.groupby("lead_source").agg(booked_jobs=("job_id", "count"), revenue=("revenue", "sum"),
                                      gross_profit=("gross_profit", "sum"))
    s = a.join(jb, how="left").fillna(0)
    s["cpl"] = s.spend / s.leads
    s["cost_per_job"] = s.spend / s.booked_jobs.replace(0, np.nan)
    s["roas"] = s.revenue / s.spend
    return s.reset_index()


# ---------------------------------------------------------------- team
def tech_table(jobs: pd.DataFrame, start, end) -> pd.DataFrame:
    j = between(jobs, "date", start, end)
    g = j.groupby("tech").agg(jobs=("job_id", "count"), revenue=("revenue", "sum"),
                              gross_profit=("gross_profit", "sum"), hours=("hours", "sum"),
                              callbacks=("callback", "mean"), upsell=("upsell", "mean"))
    g["margin"] = g.gross_profit / g.revenue
    g["avg_ticket"] = g.revenue / g.jobs
    g["gp_per_hour"] = g.gross_profit / g.hours
    return g.reset_index().sort_values("gross_profit", ascending=False)


# ---------------------------------------------------------------- Monday Morning Summary
def monday_summary(t: dict[str, pd.DataFrame], start: pd.Timestamp) -> list[dict]:
    """3-4 plain-English insights for the week starting `start` (a Monday)."""
    end = week_end(start)
    cur, prev = week_kpis(t, start), week_kpis(t, start - pd.Timedelta(days=7))
    out: list[dict] = []

    # 1. Revenue & margin
    trail = [week_kpis(t, start - pd.Timedelta(days=7 * k)).revenue for k in range(1, 5)]
    d_prev, d_trail = delta(cur.revenue, prev.revenue), delta(cur.revenue, np.mean(trail))
    verb = "up" if d_prev >= 0 else "down"
    tone = "good" if d_prev >= 0 or d_trail >= 0.05 else "warn" if d_prev > -0.08 else "bad"
    out.append(dict(
        tone=tone, topic="Sales",
        headline=f"You billed {money(cur.revenue)} last week, {verb} {pct(abs(d_prev))} from the week before.",
        body=(f"That's {pct(abs(d_trail))} {'above' if d_trail >= 0 else 'below'} your 4-week average, on {cur.jobs} jobs "
              f"at {money(cur.avg_ticket)} each. Gross margin was {pct(cur.margin, 1)} "
              f"({'+' if cur.margin >= prev.margin else ''}{(cur.margin - prev.margin) * 100:.1f} pts vs. the prior week).")))

    # 2. Marketing: Meta cost per lead
    ads = t["ad_spend"]
    meta = ads[ads.channel == "Meta Ads"]
    first_m = meta[(meta.date >= meta.date.min()) & (meta.date < meta.date.min() + pd.Timedelta(days=30))]
    recent = between(meta, "date", end - pd.Timedelta(days=27), end)
    cpl_then, cpl_now = first_m.spend.sum() / first_m.leads.sum(), recent.spend.sum() / recent.leads.sum()
    rise = cpl_now / cpl_then - 1
    others = between(ads[ads.channel == "Google LSA"], "date", end - pd.Timedelta(days=27), end)
    lsa_cpl = others.spend.sum() / max(others.leads.sum(), 1)
    sources = channel_summary(ads, t["jobs"], end - pd.Timedelta(days=27), end).set_index("channel")
    meta_cpj, lsa_cpj = sources.loc["Meta Ads", "cost_per_job"], sources.loc["Google LSA", "cost_per_job"]
    out.append(dict(
        tone="bad" if rise > 0.2 else "warn" if rise > 0.05 else "good", topic="Marketing",
        headline=f"Facebook/Instagram leads now cost {money(cpl_now)} each, {pct(rise)} more than when the year started.",
        body=(f"Meta was {money(cpl_then)} per lead in the first month of data. Over the last 4 weeks it costs {money(meta_cpj)} "
              f"in ad spend to land one booked job from Meta versus {money(lsa_cpj)} from Google Local Services "
              f"({money(lsa_cpl)} per lead). Consider moving part of the Meta budget to LSA.")))

    # 3. Team: Marcus vs. everyone else (trailing 90 days, service techs on non-duct work)
    j90 = between(t["jobs"], "date", end - pd.Timedelta(days=89), end)
    j90 = j90[j90.service_type != "Duct Cleaning"]
    mr = j90[j90.tech == "Marcus Reyes"]
    rest = j90[(j90.tech != "Marcus Reyes") & j90.service_type.isin(["AC Repair", "Heating Repair", "Maintenance"])]
    m_marg, r_marg = mr.gross_profit.sum() / mr.revenue.sum(), rest.gross_profit.sum() / rest.revenue.sum()
    dc = between(t["jobs"], "date", start, end)
    dc = dc[dc.service_type == "Duct Cleaning"]
    dc_note = (f" Duct cleaning brought in {money(dc.revenue.sum())} last week but kept only "
               f"{money(dc.gross_profit.sum())} ({pct(safe_div(dc.gross_profit.sum(), dc.revenue.sum()), 0)} margin).") if len(dc) else ""
    out.append(dict(
        tone="info", topic="Team",
        headline=f"Marcus Reyes keeps {pct(m_marg)} of every dollar he sells; the other service techs keep {pct(r_marg)}.",
        body=(f"Over the last 90 days he upsold {pct(mr.upsell.mean())} of his visits (others: {pct(rest.upsell.mean())}) "
              f"with a {pct(mr.callback.mean(), 1)} callback rate (others: {pct(rest.callback.mean(), 1)}). "
              f"Ride-alongs with him are the cheapest margin lift you have.{dc_note}")))

    # 4. Cash: overdue invoices
    snap = ar_open(t["invoices"], end)
    over = snap[snap.days_late > 0]
    if len(over):
        by_c = over.groupby("customer").amount.sum().sort_values(ascending=False)
        n_severe = (over.days_late > 30).sum()
        out.append(dict(
            tone="bad" if over.amount.sum() > 40_000 else "warn", topic="Cash",
            headline=f"{money(over.amount.sum())} is past due across {len(over)} invoices.",
            body=(f"The biggest is {by_c.index[0]} at {money(by_c.iloc[0])}; {n_severe} invoices are more than 30 days late. "
                  f"A call from you on the top three accounts is worth more than any ad this week.")))
    else:
        out.append(dict(tone="good", topic="Cash", headline="No invoices are past due.",
                        body="Collections are fully current as of the end of the week."))
    return out

