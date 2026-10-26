"""Owner's Cockpit - Sunshine Comfort HVAC (demo). Run: streamlit run app.py"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from cockpit import data_sources
from cockpit import metrics as M

st.set_page_config(page_title="Owner's Cockpit - Sunshine Comfort HVAC", page_icon="☀️", layout="wide")

# ---------------------------------------------------------------- style
INK, MUTED, GRID = "#0b0b0b", "#898781", "#e1e0d9"
BLUE, ORANGE, AQUA, MAGENTA, YELLOW, VIOLET = "#2a78d6", "#eb6834", "#1baf7a", "#e87ba4", "#eda100", "#6250d6"
GREY = "#c3c2b7"
CHANNEL_COLORS = {"Meta Ads": BLUE, "Google Ads": ORANGE, "Google LSA": AQUA, "Yelp/Angi": MAGENTA}
SERVICE_COLORS = {"AC Replacement": BLUE, "AC Repair": ORANGE, "Commercial Service": AQUA,
                  "Duct Cleaning": MAGENTA, "Maintenance": YELLOW, "Heating Repair": VIOLET}
TONES = {"good": ("✅", "On track", "#006300"), "warn": ("⚠️", "Watch", "#8a5a00"),
         "bad": ("🔴", "Needs attention", "#b02a2a"), "info": ("💡", "Opportunity", "#184f95")}

st.markdown("""
<style>
  .block-container {padding-top: 2.2rem; max-width: 1280px;}
  h1 {font-weight: 700; letter-spacing: -0.02em; margin-bottom: 0;}
  div[data-testid="stMetric"] {background: #fcfcfb; border: 1px solid #e1e0d9; border-radius: 10px; padding: 12px 16px;}
  div[data-testid="stMetricLabel"] p {color: #52514e; font-size: 0.82rem;}
  .insight {padding: 10px 0 10px 14px; border-left: 4px solid var(--c); margin: 6px 0 14px 0;}
  .insight .tag {font-size: 0.72rem; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; color: var(--c);}
  .insight .head {font-size: 1.08rem; font-weight: 650; margin: 2px 0 4px 0;}
  .insight .body {color: #52514e; font-size: 0.95rem; line-height: 1.45;}
  .sub {color: #52514e; margin-top: 0; margin-bottom: 1rem;}
</style>
""", unsafe_allow_html=True)


def style(fig: go.Figure, height: int = 340, legend: bool = True, ytitle: str | None = None,
          yfmt: str | None = None, xfmt: str | None = None) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=28, b=8), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif", color="#52514e", size=12),
        showlegend=legend, legend=dict(orientation="h", y=1.12, x=0, title=None),
        hoverlabel=dict(bgcolor="#fcfcfb", font_color=INK, bordercolor=GRID), bargap=0.3,
    )
    fig.update_xaxes(showgrid=False, linecolor=GREY, tickfont=dict(color=MUTED), tickformat=xfmt)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont=dict(color=MUTED), title=ytitle, tickformat=yfmt)
    return fig


def show(fig: go.Figure, key: str) -> None:
    st.plotly_chart(fig, width='stretch', config={"displayModeBar": False}, key=key)


def bar_round(fig):  # thin bars, no outline
    fig.update_traces(marker_line_width=0, selector=dict(type="bar"))
    return fig


def view_picker(key: str) -> str:
    """Weekly / Monthly / Quarterly toggle; only regroups time-series charts."""
    return st.radio("View by", M.VIEWS, index=1, horizontal=True, key=key,
                    help="Changes how the charts below are grouped. Headline numbers and the date range stay the same.")


def period_axis(fig: go.Figure, pm: pd.DataFrame, view: str) -> go.Figure:
    """Categorical x-axis in period order with a clear title and thinned ticks for weekly."""
    labels = list(pm.label)
    ticks = labels[::4] if view == "Weekly" else labels
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=labels, tickmode="array",
                     tickvals=ticks, ticktext=ticks, title=dict(text=M.AXIS_TITLE[view], font=dict(color=MUTED, size=11)),
                     tickangle=-45 if view == "Weekly" or len(labels) > 12 else 0)
    return fig


# ---------------------------------------------------------------- data
@st.cache_data(show_spinner="Loading data...")
def get_data():
    return data_sources.load_all()


try:
    tables, source_name = get_data()
except Exception as e:  # surface connector problems in the UI instead of a stack trace
    st.error(f"Could not load data: {e}")
    st.stop()

jobs, payroll, ads, invoices, expenses = (tables[k] for k in ("jobs", "payroll", "ad_spend", "invoices", "expenses"))
d_min, d_max = jobs.date.min().date(), jobs.date.max().date()

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### ☀️ Sunshine Comfort HVAC")
    st.caption("Fort Lauderdale, FL · 28 employees")
    st.markdown("**Date range**  \n<span style='color:#52514e;font-size:.85rem'>Applies to every tab except This Week.</span>",
                unsafe_allow_html=True)
    picked = st.date_input("Date range", value=(d_min, d_max), min_value=d_min, max_value=d_max,
                           format="MM/DD/YYYY", label_visibility="collapsed")
    if isinstance(picked, (tuple, list)) and len(picked) == 2:
        f_start, f_end = pd.Timestamp(picked[0]), pd.Timestamp(picked[1])
    else:  # user is mid-selection: keep full range until both ends are chosen
        f_start, f_end = pd.Timestamp(d_min), pd.Timestamp(d_max)

    st.divider()
    weeks = M.available_weeks(jobs)
    default_week = M.monday_of(pd.Timestamp("2026-08-24"))
    idx = weeks.index(default_week) if default_week in weeks else len(weeks) - 1
    st.markdown("**'This Week' reference week**  \n<span style='color:#52514e;font-size:.85rem'>"
                "Pretend it's the Monday after this week.</span>", unsafe_allow_html=True)
    ref = st.selectbox("Reference week", weeks, index=idx, label_visibility="collapsed",
                       format_func=lambda w: f"{w:%b %d} – {M.week_end(w):%b %d, %Y}")
    st.divider()
    st.caption(f"Data source: **{source_name}**")
    st.caption("Demo company and numbers are fictional.")

# filtered views
J = M.between(jobs, "date", f_start, f_end)
A = M.between(ads, "date", f_start, f_end)

st.title("Owner's Cockpit")
st.markdown(f"<p class='sub'>Sunshine Comfort HVAC · {f_start:%b %d, %Y} – {f_end:%b %d, %Y}</p>", unsafe_allow_html=True)
tab_week, tab_rev, tab_mkt, tab_team, tab_cash = st.tabs(
    ["This Week", "Revenue & Margin", "Marketing", "Team", "Cash & AR"])

# ================================================================ THIS WEEK
with tab_week:
    w_end = M.week_end(ref)
    prev = ref - pd.Timedelta(days=7)
    cur, pre = M.week_kpis(tables, ref), M.week_kpis(tables, prev)

    st.subheader(f"Monday Morning Summary · week of {ref:%b %d} – {w_end:%b %d, %Y}")
    with st.container(border=True):
        for ins in M.monday_summary(tables, ref):
            icon, label, color = TONES[ins["tone"]]
            st.markdown(
                f"<div class='insight' style='--c:{color}'><div class='tag'>{icon} {ins['topic']} · {label}</div>"
                f"<div class='head'>{ins['headline']}</div><div class='body'>{ins['body']}</div></div>",
                unsafe_allow_html=True)

    k = st.columns(6)
    k[0].metric("Revenue", M.money(cur.revenue), f"{M.delta(cur.revenue, pre.revenue):+.0%} vs prior wk")
    k[1].metric("Gross profit", M.money(cur.gross_profit), f"{M.delta(cur.gross_profit, pre.gross_profit):+.0%}")
    k[2].metric("Gross margin", M.pct(cur.margin, 1), f"{(cur.margin - pre.margin) * 100:+.1f} pts")
    k[3].metric("Jobs completed", f"{cur.jobs}", f"{cur.jobs - pre.jobs:+d}")
    k[4].metric("Cost per lead", f"${cur.cpl:,.0f}", f"{M.delta(cur.cpl, pre.cpl):+.0%}", delta_color="inverse")
    k[5].metric("Cash collected", M.money(cur.collected), f"{M.delta(cur.collected, pre.collected):+.0%}")

    left, right = st.columns([3, 2])
    with left:
        st.markdown("**Daily revenue: this week vs. the week before**")
        days = pd.date_range(ref, w_end)
        dc = M.between(jobs, "date", ref, w_end).groupby("date").revenue.sum().reindex(days, fill_value=0)
        dp = M.between(jobs, "date", prev, prev + pd.Timedelta(days=6)).groupby("date").revenue.sum()
        dp = dp.reindex(pd.date_range(prev, prev + pd.Timedelta(days=6)), fill_value=0)
        lab = [d.strftime("%a %d") for d in days]
        fig = go.Figure()
        fig.add_bar(x=lab, y=dc.values, name="This week", marker_color=BLUE,
                    hovertemplate="%{x}<br>This week: $%{y:,.0f}<extra></extra>")
        fig.add_scatter(x=lab, y=dp.values, name="Week before", mode="lines+markers",
                        line=dict(color=ORANGE, width=2), marker=dict(size=8, line=dict(color="#fcfcfb", width=2)),
                        hovertemplate="%{x}<br>Week before: $%{y:,.0f}<extra></extra>")
        show(bar_round(style(fig, 300, yfmt="$,.0f")), "wk_daily")
    with right:
        st.markdown("**Where the week's revenue came from**")
        svc = M.between(jobs, "date", ref, w_end).groupby("service_type").agg(
            Jobs=("job_id", "count"), Revenue=("revenue", "sum"), GP=("gross_profit", "sum")).reset_index()
        svc["Margin"] = svc.GP / svc.Revenue
        st.dataframe(svc.sort_values("Revenue", ascending=False).rename(columns={"service_type": "Service", "GP": "Gross profit"}),
                     hide_index=True, width='stretch',
                     column_config={"Revenue": st.column_config.NumberColumn(format="$%,.0f"),
                                    "Gross profit": st.column_config.NumberColumn(format="$%,.0f"),
                                    "Margin": st.column_config.NumberColumn(format="percent")})

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Technician scoreboard (this week)**")
        tt = M.tech_table(jobs, ref, w_end)
        st.dataframe(tt[["tech", "jobs", "revenue", "margin", "callbacks"]].rename(
            columns={"tech": "Tech", "jobs": "Jobs", "revenue": "Revenue", "margin": "Margin", "callbacks": "Callbacks"}),
            hide_index=True, width='stretch',
            column_config={"Revenue": st.column_config.NumberColumn(format="$%,.0f"),
                           "Margin": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=0.7),
                           "Callbacks": st.column_config.NumberColumn(format="percent")})
    with c2:
        st.markdown("**Past-due invoices to chase (as of Sunday)**")
        od = M.ar_open(invoices, w_end)
        od = od[od.days_late > 0].sort_values("amount", ascending=False).head(8)
        st.dataframe(od[["customer", "amount", "due_date", "days_late"]].rename(
            columns={"customer": "Customer", "amount": "Amount", "due_date": "Due", "days_late": "Days late"}),
            hide_index=True, width='stretch',
            column_config={"Amount": st.column_config.NumberColumn(format="$%,.0f"),
                           "Due": st.column_config.DateColumn(format="MMM D")})

# ================================================================ REVENUE & MARGIN
with tab_rev:
    rev, gp = J.revenue.sum(), J.gross_profit.sum()
    net = M.period_pnl(tables, f_start, f_end, "Monthly").net_profit.sum()  # headline: independent of the toggle
    k = st.columns(4)
    k[0].metric("Revenue", M.money(rev))
    k[1].metric("Gross profit", M.money(gp))
    k[2].metric("Gross margin", M.pct(M.safe_div(gp, rev), 1))
    k[3].metric("Est. net profit", M.money(net), f"{M.pct(M.safe_div(net, rev), 1)} of revenue", delta_color="off")

    view = view_picker("view_rev")
    unit = M.UNIT[view]
    pnl = M.period_pnl(tables, f_start, f_end, view)
    pm = M.period_meta(pnl.index, f_start, f_end, view)
    if pnl.empty:
        st.info("No data in the selected date range.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Revenue by {unit}**")
        fig = go.Figure(go.Bar(x=pm.label, y=pnl.revenue, marker_color=BLUE, customdata=pm.hover,
                               hovertemplate="%{customdata}<br>$%{y:,.0f}<extra></extra>"))
        show(bar_round(period_axis(style(fig, 300, legend=False, yfmt="$,.0s"), pm, view)), "rev_period")
        st.caption("Florida pattern: AC repair surges May–Sep; winter is slow outside of installs and duct work.")
    with c2:
        st.markdown(f"**Gross margin by {unit}**")
        fig = go.Figure(go.Scatter(x=pm.label, y=pnl.gross_margin, mode="lines+markers", line=dict(color=BLUE, width=2),
                                   marker=dict(size=8, line=dict(color="#fcfcfb", width=2)), customdata=pm.hover,
                                   hovertemplate="%{customdata}<br>%{y:.1%}<extra></extra>", name="Gross margin"))
        fig.update_yaxes(rangemode="tozero")
        show(period_axis(style(fig, 300, legend=False, yfmt=".0%"), pm, view), "margin_period")
        st.caption("Margin = gross profit ÷ revenue, recomputed from each period's totals. "
                   "Summer mix shifts toward lower-margin installs and commercial work, so margin dips as revenue peaks.")

    c1, c2 = st.columns(2)
    sv = J.groupby("service_type").agg(jobs=("job_id", "count"), revenue=("revenue", "sum"),
                                      gross_profit=("gross_profit", "sum")).reset_index()
    sv["margin"] = sv.gross_profit / sv.revenue
    with c1:
        st.markdown("**Gross margin by service**")
        s = sv.sort_values("margin")
        fig = go.Figure(go.Bar(
            y=s.service_type, x=s.margin, orientation="h",
            marker_color=[ORANGE if x == "Duct Cleaning" else BLUE for x in s.service_type],
            text=[f"{m:.0%}" for m in s.margin], textposition="outside", cliponaxis=False,
            hovertemplate="%{y}<br>Margin %{x:.1%}<extra></extra>"))
        fig.update_xaxes(range=[0, 0.7], tickformat=".0%")
        fig.update_yaxes(showgrid=False)
        show(bar_round(style(fig, 300, legend=False)), "svc_margin")
        dcl = sv[sv.service_type == "Duct Cleaning"]
        if len(dcl):
            r = dcl.iloc[0]
            st.caption(f"Duct cleaning is {r.revenue / rev:.0%} of revenue but only {r.gross_profit / gp:.0%} of gross profit "
                       f"({r.margin:.0%} margin).")
    with c2:
        st.markdown(f"**Revenue mix by {unit}**")
        fig = go.Figure()
        for sname in SERVICE_COLORS:
            d = M.resample_sum(J[J.service_type == sname], "date", ["revenue"], f_start, f_end, view)
            fig.add_bar(x=pm.label, y=d.revenue, name=sname, marker_color=SERVICE_COLORS[sname],
                        marker_line=dict(color="#fcfcfb", width=1.5), customdata=pm.hover,
                        hovertemplate=f"{sname}<br>%{{customdata}}<br>$%{{y:,.0f}}<extra></extra>")
        fig.update_layout(barmode="stack")
        show(period_axis(style(fig, 300, yfmt="$,.0s"), pm, view), "rev_mix")

    note = M.partial_note(pm, view)
    if note:
        st.caption(note)

    st.markdown(f"**Profit & loss by {unit} (estimate)**")
    tbl = pnl.reset_index(drop=True)
    tbl.insert(0, unit.capitalize(), list(pm.label))
    tbl = tbl[[unit.capitalize(), "revenue", "direct_costs", "gross_profit", "overhead_payroll", "operating_expenses",
               "advertising", "net_profit", "net_margin"]]
    tbl.columns = [M.AXIS_TITLE[view] if view == "Weekly" else unit.capitalize(), "Revenue", "Job costs", "Gross profit",
                   "Office payroll", "Operating expenses", "Advertising", "Net profit", "Net margin"]
    money_cfg = {c: st.column_config.NumberColumn(format="$%,.0f") for c in tbl.columns[1:-1]}
    st.dataframe(tbl, hide_index=True, width='stretch',
                 column_config=money_cfg | {"Net margin": st.column_config.NumberColumn(format="percent")})
    st.caption("Job costs = field labor + materials. Office payroll includes owner, sales, install helpers and employer taxes."
               + (" Payroll posts on the 15th and month-end, so weekly profit is lumpy." if view == "Weekly" else ""))

# ================================================================ MARKETING
with tab_mkt:
    cs = M.channel_summary(ads, jobs, f_start, f_end)
    meta_m = M.channel_periods(ads, f_start, f_end, "Monthly").query("channel == 'Meta Ads'").cpl.dropna()  # headline: fixed monthly
    meta_chg = M.safe_div(meta_m.iloc[-1], meta_m.iloc[0]) - 1 if len(meta_m) > 1 else np.nan
    k = st.columns(4)
    k[0].metric("Ad spend", M.money(A.spend.sum()))
    k[1].metric("Leads", f"{int(A.leads.sum()):,}")
    k[2].metric("Blended cost per lead", f"${M.safe_div(A.spend.sum(), A.leads.sum()):,.0f}" if A.leads.sum() else "n/a")
    k[3].metric("Meta cost per lead", f"${meta_m.iloc[-1]:,.0f}" if len(meta_m) else "n/a",
                f"{meta_chg:+.0%} first→last month" if meta_chg == meta_chg else None, delta_color="inverse")

    view = view_picker("view_mkt")
    unit = M.UNIT[view]
    cm = M.channel_periods(ads, f_start, f_end, view)
    pm = M.period_meta(pd.DatetimeIndex(sorted(cm.period.unique())), f_start, f_end, view)
    if A.empty:
        st.info("No ad data in the selected date range.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Cost per lead by channel, per {unit}**")
        fig = go.Figure()
        for ch, col in CHANNEL_COLORS.items():
            d = cm[cm.channel == ch].sort_values("period")
            fig.add_scatter(x=pm.label, y=d.cpl, name=ch, mode="lines+markers", line=dict(color=col, width=3 if ch == "Meta Ads" else 2),
                            marker=dict(size=8, line=dict(color="#fcfcfb", width=2)), customdata=pm.hover,
                            hovertemplate=f"{ch}<br>%{{customdata}}<br>$%{{y:,.2f}} per lead<extra></extra>")
        fig.update_yaxes(rangemode="tozero")
        show(period_axis(style(fig, 330, yfmt="$,.0f"), pm, view), "cpl")
        st.caption("Cost per lead = spend ÷ leads, recomputed from each period's totals. "
                   "Meta is the only channel whose cost per lead trends steadily up.")
    with c2:
        st.markdown(f"**Ad spend by channel, per {unit}**")
        fig = go.Figure()
        for ch, col in CHANNEL_COLORS.items():
            d = cm[cm.channel == ch].sort_values("period")
            fig.add_bar(x=pm.label, y=d.spend, name=ch, marker_color=col, marker_line=dict(color="#fcfcfb", width=1.5),
                        customdata=pm.hover, hovertemplate=f"{ch}<br>%{{customdata}}<br>$%{{y:,.0f}}<extra></extra>")
        fig.update_layout(barmode="stack")
        show(period_axis(style(fig, 330, yfmt="$,.0s"), pm, view), "ad_spend")
    note = M.partial_note(pm, view)
    if note:
        st.caption(note)

    st.markdown("**Channel scorecard**")
    cs2 = cs.rename(columns={"channel": "Channel", "spend": "Spend", "leads": "Leads", "cpl": "Cost / lead",
                             "booked_jobs": "Booked jobs", "cost_per_job": "Ad cost / booked job",
                             "revenue": "Revenue won", "roas": "Revenue per ad $"})
    st.dataframe(cs2[["Channel", "Spend", "Leads", "Cost / lead", "Booked jobs", "Ad cost / booked job", "Revenue won", "Revenue per ad $"]],
                 hide_index=True, width='stretch',
                 column_config={"Spend": st.column_config.NumberColumn(format="$%,.0f"),
                                "Leads": st.column_config.NumberColumn(format="%d"),
                                "Cost / lead": st.column_config.NumberColumn(format="$%.2f"),
                                "Booked jobs": st.column_config.NumberColumn(format="%d"),
                                "Ad cost / booked job": st.column_config.NumberColumn(format="$%.0f"),
                                "Revenue won": st.column_config.NumberColumn(format="$%,.0f"),
                                "Revenue per ad $": st.column_config.NumberColumn(format="$%.1f")})
    free = J[~J.lead_source.isin(CHANNEL_COLORS)].groupby("lead_source").revenue.sum().sort_values(ascending=False)
    st.caption("Free sources also drove revenue: " + ", ".join(f"{k} {M.money(v)}" for k, v in free.items()) + ".")

# ================================================================ TEAM
with tab_team:
    tt = M.tech_table(jobs, f_start, f_end)
    ms = tt[tt.tech == "Marcus Reyes"]
    peers = tt[(tt.tech != "Marcus Reyes") & (tt.tech != "Ray Thompson")]
    k = st.columns(4)
    k[0].metric("Headcount", f"{payroll.employee.nunique()}")
    k[1].metric("Marcus Reyes margin", M.pct(ms.margin.iloc[0], 1) if len(ms) else "n/a")
    k[2].metric("Peer tech margin", M.pct(peers.gross_profit.sum() / peers.revenue.sum(), 1) if len(peers) else "n/a")
    k[3].metric("Revenue per tech", M.money(tt.revenue.mean()))

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Gross margin by technician**")
        s = tt.sort_values("margin")
        fig = go.Figure(go.Bar(
            y=s.tech, x=s.margin, orientation="h",
            marker_color=[ORANGE if t == "Marcus Reyes" else GREY if t == "Ray Thompson" else BLUE for t in s.tech],
            text=[f"{m:.0%}" for m in s.margin], textposition="outside", cliponaxis=False,
            hovertemplate="%{y}<br>Margin %{x:.1%}<extra></extra>"))
        fig.update_xaxes(range=[0, 0.7], tickformat=".0%")
        fig.update_yaxes(showgrid=False)
        show(bar_round(style(fig, 400, legend=False)), "tech_margin")
        st.caption("Orange = Marcus Reyes. Grey = Ray Thompson, who runs the duct-cleaning crew (a 12% margin service).")
    with c2:
        st.markdown("**Revenue vs. margin per tech**")
        fig = go.Figure(go.Scatter(
            x=tt.revenue, y=tt.margin, mode="markers+text", text=tt.tech.str.split().str[0], textposition="top center",
            textfont=dict(size=11, color="#52514e"),
            marker=dict(size=14, color=[ORANGE if t == "Marcus Reyes" else BLUE for t in tt.tech],
                        line=dict(color="#fcfcfb", width=2)),
            customdata=np.stack([tt.tech, tt.jobs], axis=-1),
            hovertemplate="%{customdata[0]}<br>Revenue $%{x:,.0f}<br>Margin %{y:.1%}<br>%{customdata[1]} jobs<extra></extra>"))
        fig.update_yaxes(tickformat=".0%", title="Gross margin")
        fig.update_xaxes(tickformat="$,.0s", title="Revenue")
        show(style(fig, 400, legend=False), "tech_scatter")

    st.markdown("**Technician detail**")
    td = tt[["tech", "jobs", "revenue", "avg_ticket", "margin", "gp_per_hour", "upsell", "callbacks"]]
    td.columns = ["Tech", "Jobs", "Revenue", "Avg ticket", "Margin", "Gross profit / hr", "Upsell rate", "Callback rate"]
    st.dataframe(td, hide_index=True, width='stretch', column_config={
        "Revenue": st.column_config.NumberColumn(format="$%,.0f"), "Avg ticket": st.column_config.NumberColumn(format="$%,.0f"),
        "Margin": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=0.7),
        "Gross profit / hr": st.column_config.NumberColumn(format="$%,.0f"),
        "Upsell rate": st.column_config.NumberColumn(format="percent"),
        "Callback rate": st.column_config.NumberColumn(format="percent")})

    pr = M.between(payroll, "pay_date", f_start, f_end)
    pr = pr.assign(total=pr.gross_pay + pr.employer_taxes).groupby("department").total.sum().sort_values()
    st.markdown("**Payroll by department** (wages + employer taxes)")
    fig = go.Figure(go.Bar(y=pr.index, x=pr.values, orientation="h", marker_color=BLUE,
                           text=[M.money(v) for v in pr.values], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}<br>$%{x:,.0f}<extra></extra>"))
    fig.update_yaxes(showgrid=False)
    fig.update_xaxes(tickformat="$,.0s")
    show(bar_round(style(fig, 280, legend=False)), "payroll_dept")

# ================================================================ CASH & AR
with tab_cash:
    asof = f_end
    snap = M.ar_open(invoices, asof)
    over = snap[snap.days_late > 0]
    ls = M.late_stats(invoices, f_start, f_end)
    cash = M.monthly_cash(tables, f_start, f_end)
    k = st.columns(5)
    k[0].metric("Open receivables", M.money(snap.amount.sum()))
    k[1].metric("Past due", M.money(over.amount.sum()), f"{M.safe_div(over.amount.sum(), snap.amount.sum()):.0%} of open AR", delta_color="off")
    k[2].metric("Invoices paid late", M.pct(ls["late_rate"], 1))
    k[3].metric("Avg days to get paid", f"{ls['avg_days_to_pay']:.0f}")
    k[4].metric("Net cash flow", M.money(cash.net_cash.sum(), signed=True), "collections − all outflows", delta_color="off")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Receivables aging (as of {asof:%b %d, %Y})**")
        ag = snap.groupby("bucket", observed=False).amount.sum().reindex(M.BUCKETS).fillna(0)
        fig = go.Figure(go.Bar(x=ag.index.astype(str), y=ag.values, marker_color=[BLUE] + [ORANGE] * 4,
                               text=[M.money(v) for v in ag.values], textposition="outside", cliponaxis=False,
                               hovertemplate="%{x}<br>$%{y:,.0f}<extra></extra>"))
        show(bar_round(style(fig, 320, legend=False, yfmt="$,.0s")), "aging")
        st.caption("Blue = not yet due. Orange = past due.")
    with c2:
        st.markdown("**Monthly cash: in vs. out**")
        fig = go.Figure()
        fig.add_bar(x=cash.index, y=cash.collections, name="Collections", marker_color=BLUE,
                    hovertemplate="Collections<br>%{x|%b %Y}<br>$%{y:,.0f}<extra></extra>")
        fig.add_bar(x=cash.index, y=cash.cash_out, name="Cash out", marker_color=ORANGE,
                    hovertemplate="Cash out<br>%{x|%b %Y}<br>$%{y:,.0f}<extra></extra>")
        fig.update_layout(barmode="group")
        show(bar_round(style(fig, 320, yfmt="$,.0s", xfmt="%b")), "cash_io")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Cumulative net cash since start of range**")
        fig = go.Figure(go.Scatter(x=cash.index, y=cash.cumulative, mode="lines+markers", line=dict(color=BLUE, width=2),
                                   marker=dict(size=8, line=dict(color="#fcfcfb", width=2)), fill="tozeroy",
                                   fillcolor="rgba(42,120,214,0.10)", name="Cumulative net cash",
                                   hovertemplate="%{x|%b %Y}<br>$%{y:,.0f}<extra></extra>"))
        show(style(fig, 300, legend=False, yfmt="$,.0s", xfmt="%b"), "cash_cum")
        st.caption("Outflows = job materials, all payroll with taxes, operating expenses and advertising.")
    with c2:
        st.markdown("**Past-due balance by customer**")
        if len(over):
            by = over.groupby("customer").agg(Invoices=("invoice_id", "count"), Amount=("amount", "sum"),
                                              Oldest=("days_late", "max")).sort_values("Amount", ascending=False).head(10).reset_index()
            st.dataframe(by.rename(columns={"customer": "Customer", "Oldest": "Oldest (days late)"}), hide_index=True,
                         width='stretch', column_config={"Amount": st.column_config.NumberColumn(format="$%,.0f")})
        else:
            st.success("Nothing past due.")
    chronic = invoices.assign(late=invoices.paid_late | (invoices.status == "Overdue")).groupby("customer").agg(
        n=("invoice_id", "count"), late=("late", "mean"))
    chronic = chronic[(chronic.n >= 8) & (chronic.late >= 0.3)].sort_values("late", ascending=False)
    if len(chronic):
        st.warning("Chronic late payers (30%+ of invoices late): " +
                   ", ".join(f"**{c}** ({r.late:.0%} of {int(r.n)})" for c, r in chronic.iterrows()) +
                   ". Consider tighter terms or deposits.")

