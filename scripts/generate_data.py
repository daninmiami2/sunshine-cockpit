"""Generate 12 months (Oct 2025 - Sep 2026) of synthetic data for Sunshine Comfort HVAC.

Fictional company: Fort Lauderdale, FL - ~$6.2M revenue, 28 employees.
Writes jobs, payroll, ad_spend, invoices, expenses CSVs to ../data. Deterministic (seeded).

Baked-in stories:
  * Florida seasonality: AC repair peaks Jun-Sep, heating repair is a small winter bump.
  * Duct cleaning runs at ~12% gross margin (everything else 35-56%).
  * Marcus Reyes earns a ~58% margin vs. ~35-45% for peers.
  * Meta cost-per-lead climbs ~43% from Oct to Sep.
  * ~11% of invoices are paid late; two commercial accounts are chronic offenders.
"""
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(2026)
OUT = Path(__file__).resolve().parent.parent / "data"
OUT.mkdir(exist_ok=True)

START, END = pd.Timestamp("2025-10-01"), pd.Timestamp("2026-09-30")
AS_OF = END
DAYS = pd.date_range(START, END)
TARGET_REVENUE = 6_200_000

# --- service catalog: annual count, avg ticket, base margin, labor share of cost, seasonal curve (Oct..Sep)
SERVICES = {
    "AC Repair":         (2900, 620, 0.47, 0.55, [0.85, 0.65, 0.5, 0.5, 0.6, 0.8, 1.05, 1.3, 1.55, 1.7, 1.7, 1.4]),
    "Heating Repair":    (380, 480, 0.48, 0.55, [0.5, 1.3, 2.0, 2.2, 1.6, 0.8, 0.2, 0.1, 0.1, 0.1, 0.1, 0.2]),
    "AC Replacement":    (230, 9400, 0.40, 0.35, [0.9, 0.8, 0.7, 0.7, 0.8, 1.0, 1.15, 1.25, 1.3, 1.3, 1.25, 1.1]),
    "Maintenance":       (1100, 165, 0.60, 0.70, [1.2, 0.9, 0.7, 0.7, 0.9, 1.3, 1.5, 1.2, 0.9, 0.8, 0.8, 0.9]),
    "Duct Cleaning":     (720, 760, 0.12, 0.65, [1.0, 1.0, 1.1, 1.1, 1.1, 1.0, 1.0, 0.95, 0.9, 0.9, 0.9, 0.95]),
    "Commercial Service": (260, 2300, 0.42, 0.50, [0.8, 0.7, 0.6, 0.6, 0.7, 0.9, 1.1, 1.3, 1.4, 1.5, 1.5, 1.3]),
}
WEEKDAY_W = np.array([1.0, 1.05, 1.0, 1.0, 0.95, 0.45, 0.15])  # Mon..Sun

LEAD_MIX = {  # share of jobs by lead source, by service type group
    "Meta Ads": 0.17, "Google Ads": 0.13, "Google LSA": 0.11, "Yelp/Angi": 0.06,
    "Referral": 0.20, "Repeat/Plan": 0.23, "Organic/Web": 0.10,
}
PAID = ["Meta Ads", "Google Ads", "Google LSA", "Yelp/Angi"]
CLOSE_RATE = {"Meta Ads": 0.28, "Google Ads": 0.33, "Google LSA": 0.42, "Yelp/Angi": 0.30}
BASE_CPL = {"Meta Ads": 42.0, "Google Ads": 58.0, "Google LSA": 47.0, "Yelp/Angi": 64.0}

# --- team -----------------------------------------------------------------
# (name, role, dept, class, annual salary or None for tech-derived)
TECHS = {  # margin offset vs. service base; 'Marcus Reyes' overridden to 58%
    "Marcus Reyes": 0.0, "Danny Ortiz": 0.02, "Kevin Brandt": -0.03, "Luis Herrera": 0.01,
    "Tyrone Jackson": -0.05, "Aaron Pike": -0.07, "Sam Delgado": 0.0, "Brian Choi": 0.01,
    "Carlos Mendez": -0.02, "Jake Sullivan": 0.01, "Victor Alvarez": -0.01, "Ray Thompson": 0.0,
}
ROLE = {
    "Marcus Reyes": "Senior Service Tech", "Danny Ortiz": "Service Tech", "Kevin Brandt": "Service Tech",
    "Luis Herrera": "Service Tech", "Tyrone Jackson": "Service Tech", "Aaron Pike": "Service Tech",
    "Sam Delgado": "Service Tech", "Brian Choi": "Install Tech", "Carlos Mendez": "Service Tech",
    "Jake Sullivan": "Install Lead", "Victor Alvarez": "Install Lead", "Ray Thompson": "Duct Crew Lead",
}
OFFICE = [
    ("Tom Whitfield", "Owner", "Management", 120000), ("Angela Brooks", "General Manager", "Management", 98000),
    ("Mike Dunlap", "Service Manager", "Operations", 72000), ("Priya Nair", "Dispatcher", "Operations", 46000),
    ("Rosa Medina", "Membership Coordinator", "Office", 43000),
    ("Jessica Lowe", "CSR", "Office", 42000),("Monica Reyes", "CSR", "Office", 41000),
    ("Harold Finch", "Bookkeeper", "Office", 58000), ("Chloe Martin", "Marketing Manager", "Marketing", 62000),
    ("Greg Sandoval", "Comfort Advisor (Sales)", "Sales", 68000), ("Nina Patel", "Comfort Advisor (Sales)", "Sales", 64000),
    ("Walt Henderson", "Warehouse / Parts", "Operations", 44000), ("Dee Ramsey", "Fleet & Safety Coordinator", "Operations", 46000),
    ("Eli Torres", "Install Helper", "Install Crew", 47000), ("Josh Whelan", "Install Helper", "Install Crew", 46000),
    ("Andre Wilkins", "Install Helper", "Install Crew", 47500),
]
assert len(TECHS) + len(OFFICE) == 28

SERVICE_TECHS = ["Marcus Reyes", "Danny Ortiz", "Kevin Brandt", "Luis Herrera", "Tyrone Jackson",
                 "Aaron Pike", "Sam Delgado", "Carlos Mendez"]
TECH_POOL = {
    "AC Repair": (SERVICE_TECHS, [1.5, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
    "Heating Repair": (SERVICE_TECHS, [1.5, 1, 1, 1, 1, 1, 1, 1]),
    "Maintenance": (SERVICE_TECHS, [1.0, 1, 1, 1, 1, 1, 1.2, 1]),
    "AC Replacement": (["Jake Sullivan", "Victor Alvarez", "Brian Choi"], [1, 1, 0.7]),
    "Duct Cleaning": (["Ray Thompson", "Sam Delgado", "Brian Choi", "Carlos Mendez"], [3, 1, 1, 1]),
    "Commercial Service": (["Marcus Reyes", "Danny Ortiz", "Kevin Brandt"], [1.4, 1, 1]),
}
CALLBACK_RATE = {t: 0.03 for t in TECHS} | {"Marcus Reyes": 0.01, "Aaron Pike": 0.11, "Tyrone Jackson": 0.08}
UPSELL_RATE = {t: 0.20 for t in TECHS} | {"Marcus Reyes": 0.52, "Aaron Pike": 0.10, "Danny Ortiz": 0.28}

FIRST = ["James", "Maria", "Robert", "Linda", "Carlos", "Ana", "David", "Susan", "Luis", "Karen", "Michael", "Sofia",
         "Daniel", "Patricia", "Jose", "Jennifer", "Frank", "Laura", "Tony", "Rachel", "Gary", "Elena", "Paul", "Denise"]
LAST = ["Alvarez", "Johnson", "Garcia", "Smith", "Rodriguez", "Williams", "Martinez", "Brown", "Lopez", "Davis",
        "Hernandez", "Miller", "Gonzalez", "Wilson", "Perez", "Anderson", "Thomas", "Moore", "Jackson", "Taylor"]
CITIES = ["Fort Lauderdale", "Wilton Manors", "Oakland Park", "Pompano Beach", "Plantation", "Sunrise",
          "Lauderhill", "Davie", "Dania Beach", "Hollywood"]
COMMERCIAL = ["Las Olas Property Mgmt", "Harbor Point Condos", "Riverwalk Dental Group", "Seabreeze Hotel",
              "Broward Medical Plaza", "Galleria Retail Holdings", "Pelican Bay HOA", "Coastal Fitness",
              "Sistrunk Brewing Co.", "Marina Mile Offices", "Palm Court Restaurants", "Oakwood Self Storage"]
CHRONIC = {"Harbor Point Condos": 0.65, "Galleria Retail Holdings": 0.55}


def season_weights(curve):
    """Per-day weights for a service: monthly curve x weekday curve, normalised to sum 1."""
    month_idx = ((DAYS.month - 10) % 12).values
    w = np.array(curve)[month_idx] * WEEKDAY_W[DAYS.dayofweek.values]
    return w / w.sum()


# ---------------------------------------------------------------- jobs
rows = []
for svc, (n, ticket, base_m, labor_share, curve) in SERVICES.items():
    counts = rng.multinomial(n, season_weights(curve))
    techs, tw = TECH_POOL[svc]
    tw = np.array(tw) / np.sum(tw)
    for day, c in zip(DAYS, counts):
        for _ in range(c):
            tech = rng.choice(techs, p=tw)
            sigma = 0.45 if svc in ("AC Replacement", "Commercial Service") else 0.30
            revenue = ticket * rng.lognormal(-sigma**2 / 2, sigma)
            upsell = rng.random() < UPSELL_RATE[tech] and svc not in ("Duct Cleaning", "AC Replacement")
            if upsell:
                revenue *= 1.35
            callback = rng.random() < CALLBACK_RATE[tech] and svc not in ("AC Replacement",)
            if tech == "Marcus Reyes" and svc != "Duct Cleaning":
                margin = rng.normal(0.58, 0.025)
            elif svc == "Duct Cleaning":
                margin = rng.normal(0.125, 0.02)
            else:
                margin = base_m + TECHS[tech] + rng.normal(0, 0.03)
            if callback:
                margin -= 0.20  # return trip eats the margin
            margin = min(margin, 0.75)
            cost = revenue * (1 - margin)
            labor = cost * labor_share * rng.normal(1, 0.05)
            hours = max(0.5, labor / 62.0)
            if svc in ("AC Replacement", "Commercial Service"):
                customer = rng.choice(COMMERCIAL) if svc == "Commercial Service" else None
            else:
                customer = None
            if customer is None:
                customer = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
            source = rng.choice(list(LEAD_MIX), p=np.array(list(LEAD_MIX.values())) / sum(LEAD_MIX.values()))
            rows.append(dict(date=day, service_type=svc, tech=tech, customer=customer,
                             city=rng.choice(CITIES), lead_source=source, revenue=revenue,
                             labor_cost=labor, materials_cost=cost - labor, hours=hours,
                             upsell=upsell, callback=callback))
jobs = pd.DataFrame(rows).sort_values("date", kind="stable").reset_index(drop=True)

scale = TARGET_REVENUE / jobs["revenue"].sum()  # hit ~$6.2M
for c in ["revenue", "labor_cost", "materials_cost", "hours"]:
    jobs[c] = jobs[c] * scale
jobs.insert(0, "job_id", [f"J-{10000 + i}" for i in range(len(jobs))])
jobs["gross_profit"] = jobs.revenue - jobs.labor_cost - jobs.materials_cost
for c in ["revenue", "labor_cost", "materials_cost", "hours", "gross_profit"]:
    jobs[c] = jobs[c].round(2)

# ---------------------------------------------------------------- ad_spend
jobs["ym"] = jobs.date.dt.to_period("M")
months = pd.period_range("2025-10", "2026-09", freq="M")
ad_rows = []
for ch in PAID:
    for k, m in enumerate(months):
        n_jobs = ((jobs.lead_source == ch) & (jobs.ym == m)).sum()
        trend = 1 + (0.42 * k / 11 if ch == "Meta Ads" else 0.03 * np.sin(k))
        cpl = BASE_CPL[ch] * trend
        target_leads = n_jobs / CLOSE_RATE[ch]
        monthly_budget = target_leads * cpl
        days = pd.date_range(m.start_time, m.end_time.normalize())
        for d in days:
            spend = monthly_budget / len(days) * rng.normal(1, 0.12) * (0.8 if d.weekday() >= 5 else 1.1)
            leads = rng.poisson(max(spend, 0) / cpl)
            ctr = rng.normal(0.019 if ch == "Meta Ads" else 0.045, 0.002)
            clicks = int(spend / rng.normal(1.6 if ch == "Meta Ads" else 5.5, 0.2))
            ad_rows.append(dict(date=d, channel=ch, spend=round(spend, 2),
                                impressions=int(clicks / max(ctr, 0.005)), clicks=clicks, leads=int(leads)))
ads = pd.DataFrame(ad_rows).sort_values(["date", "channel"]).reset_index(drop=True)

# ---------------------------------------------------------------- invoices
def terms(svc):
    return {"Commercial Service": 30, "AC Replacement": 10}.get(svc, 14)

inv_rows = []
for i, j in jobs.iterrows():
    issue = j.date + pd.Timedelta(days=int(rng.integers(0, 3)))
    term = terms(j.service_type)
    due = issue + pd.Timedelta(days=term)
    if j.service_type == "Commercial Service":
        late_p = CHRONIC.get(j.customer, 0.12)
    elif j.service_type == "AC Replacement":
        late_p = 0.16
    else:
        late_p = 0.118
    if rng.random() < late_p:
        slip = rng.integers(25, 75) if j.customer in CHRONIC else rng.integers(3, 40)
        paid = due + pd.Timedelta(days=int(slip))
    else:
        paid = issue + pd.Timedelta(days=int(rng.integers(0, term + 1)))
    if paid > AS_OF:
        paid = pd.NaT
    inv_rows.append(dict(invoice_id=f"INV-{20000 + i}", job_id=j.job_id, customer=j.customer,
                         service_type=j.service_type, issue_date=issue, due_date=due,
                         amount=j.revenue, paid_date=paid))
invoices = pd.DataFrame(inv_rows)
invoices["status"] = np.where(invoices.paid_date.notna(), "Paid",
                              np.where(invoices.due_date < AS_OF, "Overdue", "Open"))
invoices["paid_late"] = invoices.paid_date.notna() & (invoices.paid_date > invoices.due_date)

# ---------------------------------------------------------------- payroll (semi-monthly)
pay_dates = []
for m in months:
    pay_dates += [pd.Timestamp(m.year, m.month, 15), m.end_time.normalize()]
TAX = 0.095
pr_rows = []
jobs["period_end"] = jobs.date.apply(lambda d: pd.Timestamp(d.year, d.month, 15) if d.day <= 15 else d + pd.offsets.MonthEnd(0))
tech_period = jobs.groupby(["tech", "period_end"])[["labor_cost", "hours"]].sum()
for t in TECHS:
    for pdte in pay_dates:
        lab, hrs = tech_period.loc[(t, pdte)] if (t, pdte) in tech_period.index else (0, 0)
        gross = lab / (1 + TAX)
        gross = max(gross, 1800)  # guaranteed base
        pr_rows.append(dict(pay_date=pdte, employee=t, role=ROLE[t], department="Field Techs",
                            cost_class="direct", hours=round(max(hrs / 0.72, 40), 1),
                            gross_pay=round(gross, 2), employer_taxes=round(gross * TAX, 2)))
for name, role, dept, sal in OFFICE:
    for pdte in pay_dates:
        gross = sal / 24
        pr_rows.append(dict(pay_date=pdte, employee=name, role=role, department=dept, cost_class="overhead",
                            hours=86.7, gross_pay=round(gross, 2), employer_taxes=round(gross * TAX, 2)))
payroll = pd.DataFrame(pr_rows).sort_values(["pay_date", "employee"]).reset_index(drop=True)

# ---------------------------------------------------------------- expenses
exp_rows = []
monthly_rev = jobs.groupby("ym").revenue.sum()
fixed = [("Rent - shop & office", "Sunrise Industrial Park LLC", 9500), ("Vehicle leases & maintenance", "Fleet Partners", 11000),
         ("Insurance (GL / WC / auto)", "Everglades Mutual", 9800), ("Software & subscriptions", "Jobber / QuickBooks / misc", 1800),
         ("Utilities & phones", "FPL / Verizon", 2200), ("Professional fees", "CPA & legal", 2400),
         ("Licensing & training", "EPA / NATE", 800)]
for m in months:
    d0, d1 = m.start_time, m.end_time.normalize()
    for cat, vendor, amt in fixed:
        exp_rows.append(dict(date=d0 + pd.Timedelta(days=int(rng.integers(0, 5))), category=cat, vendor=vendor,
                             amount=round(amt * rng.normal(1, 0.03), 2)))
    exp_rows.append(dict(date=d1, category="Fuel", vendor="Shell Fleet Card",
                         amount=round(monthly_rev[m] * 0.019 * rng.normal(1, 0.05), 2)))
    exp_rows.append(dict(date=d1, category="Merchant & financing fees", vendor="Stripe / GreenSky",
                         amount=round(monthly_rev[m] * 0.019 * rng.normal(1, 0.04), 2)))
    exp_rows.append(dict(date=d0 + pd.Timedelta(days=int(rng.integers(8, 22))), category="Tools & equipment",
                         vendor="Ferguson / Johnstone Supply", amount=round(rng.uniform(2500, 6500), 2)))
    exp_rows.append(dict(date=d0 + pd.Timedelta(days=int(rng.integers(8, 22))), category="Misc / warranty",
                         vendor="Various", amount=round(rng.uniform(900, 3200), 2)))
exp_rows.append(dict(date=pd.Timestamp("2026-04-14"), category="Vehicle purchase (down payment)",
                     vendor="Ford of Pembroke Pines", amount=22000.0))
expenses = pd.DataFrame(exp_rows).sort_values("date").reset_index(drop=True)

# ---------------------------------------------------------------- write
jobs.drop(columns=["ym", "period_end"]).to_csv(OUT / "jobs.csv", index=False, encoding="utf-8")
payroll.to_csv(OUT / "payroll.csv", index=False, encoding="utf-8")
ads.to_csv(OUT / "ad_spend.csv", index=False, encoding="utf-8")
invoices.to_csv(OUT / "invoices.csv", index=False, encoding="utf-8")
expenses.to_csv(OUT / "expenses.csv", index=False, encoding="utf-8")

# ---------------------------------------------------------------- sanity report
rev = jobs.revenue.sum()
gp = jobs.gross_profit.sum()
print(f"jobs={len(jobs):,}  revenue=${rev:,.0f}  gross margin={gp / rev:.1%}")
print((jobs.groupby("service_type")[["revenue", "gross_profit"]].sum().assign(m=lambda x: x.gross_profit / x.revenue)).round(3))
t = jobs.groupby("tech")[["revenue", "gross_profit"]].sum()
print((t.gross_profit / t.revenue).round(3).sort_values(ascending=False))
meta = ads[ads.channel == "Meta Ads"].assign(m=lambda x: x.date.dt.to_period("M")).groupby("m")[["spend", "leads"]].sum()
cpl = meta.spend / meta.leads
print(f"Meta CPL {cpl.iloc[0]:.2f} -> {cpl.iloc[-1]:.2f} ({cpl.iloc[-1] / cpl.iloc[0] - 1:+.0%})")
print(f"late invoices: {invoices.paid_late.mean():.1%} of all; overdue open: ${invoices[invoices.status == 'Overdue'].amount.sum():,.0f}")
pay = payroll.gross_pay.sum() + payroll.employer_taxes.sum()
net = gp - payroll[payroll.cost_class == 'overhead'][['gross_pay', 'employer_taxes']].sum().sum() - expenses.amount.sum() - ads.spend.sum()
print(f"payroll=${pay:,.0f} expenses=${expenses.amount.sum():,.0f} ads=${ads.spend.sum():,.0f} est. net=${net:,.0f} ({net / rev:.1%})")

