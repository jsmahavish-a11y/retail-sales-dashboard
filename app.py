"""Interactive Retail Sales Dashboard (Streamlit + Plotly).

Data: clean_dataset.csv (cleaned retail transactions, one row per transaction).
Run locally:  streamlit run app.py
"""
import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Retail Sales Dashboard", page_icon=":bar_chart:", layout="wide")

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
GRAINS = {"Year": "YS", "Quarter": "QS", "Month": "MS", "Week": "W-MON", "Day": "D"}
ACCENT = "#2F5D8A"
PALETTE = px.colors.qualitative.T10          # one fixed colour per category, used in every chart


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
@st.cache_data
def load_data() -> pd.DataFrame:
    d = pd.read_csv(Path(__file__).parent / "clean_dataset.csv", parse_dates=["transaction_date"])
    d["year"] = d["transaction_date"].dt.year
    d["month"] = d["transaction_date"].dt.month
    d["weekday"] = d["transaction_date"].dt.day_name()
    return d


df = load_data()
cat_colors = {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(sorted(df["category"].unique()))}
data_start, data_end = df["transaction_date"].min(), df["transaction_date"].max()

# ----------------------------------------------------------------------------
# Sidebar: slicers
# ----------------------------------------------------------------------------
st.sidebar.title("Filters")
picked = st.sidebar.date_input("Date range", value=(data_start.date(), data_end.date()),
                               min_value=data_start.date(), max_value=data_end.date())
if isinstance(picked, (tuple, list)):
    start = pd.Timestamp(picked[0])
    end = pd.Timestamp(picked[1] if len(picked) > 1 else picked[0])
else:
    start = end = pd.Timestamp(picked)

all_cats = sorted(df["category"].unique())
sel_cats = st.sidebar.multiselect("Category", all_cats, default=all_cats)
all_locs = sorted(df["location"].unique())
sel_locs = st.sidebar.multiselect("Location (channel)", all_locs, default=all_locs)
all_pays = sorted(df["payment_method"].unique())
sel_pays = st.sidebar.multiselect("Payment method", all_pays, default=all_pays)
all_discs = sorted(df["discount_applied"].unique())
sel_discs = st.sidebar.multiselect("Discount applied", all_discs, default=all_discs)

st.sidebar.markdown("---")
st.sidebar.subheader("KPI settings")
churn_days = st.sidebar.slider("Churn: no purchase in the last N days", 7, 180, 30)
mkt_pct = st.sidebar.slider("Assumed marketing spend (% of revenue)", 0, 30, 10,
                            help="The data has no marketing cost, so this is an assumption used only for CAC.")


def apply_filters(d: pd.DataFrame, s: pd.Timestamp, e: pd.Timestamp) -> pd.DataFrame:
    m = (d["transaction_date"].between(s, e) & d["category"].isin(sel_cats) & d["location"].isin(sel_locs)
         & d["payment_method"].isin(sel_pays) & d["discount_applied"].isin(sel_discs))
    return d[m]


cur = apply_filters(df, start, end)
if cur.empty:
    st.title("Retail Sales Dashboard")
    st.warning("No transactions match the current filters. Widen the date range or select more options.")
    st.stop()


# ----------------------------------------------------------------------------
# KPI calculations
# ----------------------------------------------------------------------------
def basic_kpis(d: pd.DataFrame) -> dict:
    revenue = d["total_spent"].sum()
    orders = len(d)
    return {"revenue": revenue, "orders": orders, "aov": revenue / orders if orders else np.nan}


def churn_kpi(d: pd.DataFrame, ref_date: pd.Timestamp, window: int):
    people = d[d["customer_id"] != "Unknown"]
    last_seen = people.groupby("customer_id")["transaction_date"].max()
    if last_seen.empty:
        return np.nan, 0, 0
    churned = int((last_seen < ref_date - pd.Timedelta(days=window)).sum())
    return churned / len(last_seen), churned, len(last_seen)


k = basic_kpis(cur)
active_customers = cur.loc[cur["customer_id"] != "Unknown", "customer_id"].nunique()
churn_rate, churned_n, churn_base = churn_kpi(cur, end, churn_days)

# New customers = customers whose very first purchase in the whole dataset falls in the selected dates
first_purchase = df[df["customer_id"] != "Unknown"].groupby("customer_id")["transaction_date"].min()
new_customers = int(first_purchase.between(start, end).sum())
revenue_in_dates = df.loc[df["transaction_date"].between(start, end), "total_spent"].sum()
marketing_spend = revenue_in_dates * mkt_pct / 100
cac = marketing_spend / new_customers if new_customers else np.nan

# Previous period of the same length, for the "vs previous period" change
span = (end - start).days + 1
prev_end = start - pd.Timedelta(days=1)
prev_start = prev_end - pd.Timedelta(days=span - 1)
prev = apply_filters(df, prev_start, prev_end) if prev_end >= data_start else df.iloc[0:0]
pk = basic_kpis(prev) if len(prev) else None


def change(now: float, before: float):
    if pk is None or not before or np.isnan(before):
        return None
    return f"{(now - before) / before * 100:+.1f}% vs previous period"


# ----------------------------------------------------------------------------
# Header + KPI cards
# ----------------------------------------------------------------------------
st.title("Retail Sales Dashboard")
st.caption(f"{start.date()} to {end.date()}  |  {len(cur):,} transactions shown  |  "
           f"source: clean_dataset.csv ({len(df):,} transactions)")

cols = st.columns(6)
cards = [
    ("Revenue", f"{k['revenue'] / 1e6:,.2f}M" if k["revenue"] >= 1e6 else f"{k['revenue']:,.0f}", change(k["revenue"], pk["revenue"] if pk else None)),
    ("Average order value", f"{k['aov']:,.2f}", change(k["aov"], pk["aov"] if pk else None)),
    ("Transactions", f"{k['orders']:,}", change(k["orders"], pk["orders"] if pk else None)),
    ("Active customers", f"{active_customers:,}", None),
    ("CAC (assumed)", "n/a" if np.isnan(cac) else f"{cac:,.0f}", None),
    ("Churn rate", "n/a" if np.isnan(churn_rate) else f"{churn_rate * 100:.1f}%", None),
]
for col, (label, value, delta) in zip(cols, cards):
    with col.container(border=True):
        st.metric(label, value, delta=delta)

notes = [f"**Churn:** {churned_n} of {churn_base} customers made no purchase in the {churn_days} days before {end.date()}.",
         (f"**CAC:** assumed marketing spend {marketing_spend:,.0f} ({mkt_pct}% of revenue) / {new_customers} new customers."
          if new_customers else "**CAC:** no customers made their first purchase in the selected dates, so CAC is not defined.")]
st.caption("  \n".join(notes))

# ----------------------------------------------------------------------------
# Revenue trend (area chart)
# ----------------------------------------------------------------------------
st.subheader("Revenue trend")
c1, c2 = st.columns([3, 1])
grain = c1.radio("Time grain", list(GRAINS), index=2, horizontal=True)
split = c2.toggle("Split by category", value=True)
freq = GRAINS[grain]

if split:
    t = (cur.groupby([pd.Grouper(key="transaction_date", freq=freq), "category"])["total_spent"].sum()
            .unstack("category", fill_value=0).stack().rename("total_spent").reset_index())
    fig = px.area(t, x="transaction_date", y="total_spent", color="category", color_discrete_map=cat_colors)
else:
    t = cur.groupby(pd.Grouper(key="transaction_date", freq=freq))["total_spent"].sum().reset_index()
    fig = px.area(t, x="transaction_date", y="total_spent", color_discrete_sequence=[ACCENT])
fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), xaxis_title=None, yaxis_title="Revenue",
                  legend_title_text="")
st.plotly_chart(fig, width="stretch")
st.caption("The most recent period can be incomplete if the data stops part-way through it.")

# ----------------------------------------------------------------------------
# Category and payment mix
# ----------------------------------------------------------------------------
left, right = st.columns([3, 2])
with left:
    st.subheader("Revenue by category")
    by_cat = cur.groupby("category")["total_spent"].sum().sort_values().reset_index()
    fig = px.bar(by_cat, x="total_spent", y="category", orientation="h", color="category",
                 color_discrete_map=cat_colors, text_auto=".3s")
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
                      xaxis_title="Revenue", yaxis_title=None)
    st.plotly_chart(fig, width="stretch")
with right:
    st.subheader("Payment method mix")
    by_pay = cur.groupby("payment_method")["total_spent"].sum().reset_index()
    fig = px.pie(by_pay, names="payment_method", values="total_spent", hole=0.55,
                 color_discrete_sequence=px.colors.qualitative.Set2)
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="")
    st.plotly_chart(fig, width="stretch")

# ----------------------------------------------------------------------------
# Heatmaps
# ----------------------------------------------------------------------------
st.subheader("Heatmaps")
st.caption("The dataset has no geographic fields (location is Online or In-Store), so the location heatmap "
           "compares channels instead of a map.")
h1c, h2c = st.columns(2)
with h1c:
    loc_cat = cur.pivot_table(index="location", columns="category", values="total_spent",
                              aggfunc="sum", fill_value=0)
    fig = px.imshow(loc_cat, text_auto=".3s", aspect="auto", color_continuous_scale="Blues",
                    title="Revenue: location x category")
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=40, b=10), coloraxis_showscale=False,
                      xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig, width="stretch")
with h2c:
    wk = (cur.pivot_table(index="weekday", columns="month", values="total_spent", aggfunc="sum", fill_value=0)
             .reindex(index=WEEKDAYS, columns=range(1, 13), fill_value=0))
    wk.columns = MONTHS
    fig = px.imshow(wk, aspect="auto", color_continuous_scale="YlGnBu", title="Revenue: weekday x month")
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=40, b=10), coloraxis_showscale=False,
                      xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig, width="stretch")

# ----------------------------------------------------------------------------
# Drill-down
# ----------------------------------------------------------------------------
st.subheader("Drill down")
tab_time, tab_cat = st.tabs(["By time: year > month > day", "By category: category > item"])

with tab_time:
    years = sorted(cur["year"].unique())
    ysel = st.selectbox("Year", ["All years"] + [int(y) for y in years])
    if ysel == "All years":
        yr = cur.groupby("year")["total_spent"].sum().reset_index()
        fig = px.bar(yr, x="year", y="total_spent", text_auto=".3s", color_discrete_sequence=[ACCENT])
        fig.update_xaxes(type="category")
        st.plotly_chart(fig.update_layout(height=320, yaxis_title="Revenue", xaxis_title=None,
                                          margin=dict(l=10, r=10, t=10, b=10)), width="stretch")
        st.caption("Pick a year to see its months.")
    else:
        dy = cur[cur["year"] == ysel]
        mo = dy.groupby("month")["total_spent"].sum().reindex(range(1, 13), fill_value=0).reset_index()
        mo["month"] = MONTHS
        present = [MONTHS[m - 1] for m in sorted(dy["month"].unique())]
        msel = st.selectbox("Month", ["All months"] + present)
        if msel == "All months":
            fig = px.bar(mo, x="month", y="total_spent", text_auto=".3s", color_discrete_sequence=[ACCENT])
        else:
            dm = dy[dy["month"] == MONTHS.index(msel) + 1]
            day = dm.groupby(dm["transaction_date"].dt.date)["total_spent"].sum().reset_index()
            day.columns = ["date", "total_spent"]
            fig = px.line(day, x="date", y="total_spent", markers=True, color_discrete_sequence=[ACCENT])
        st.plotly_chart(fig.update_layout(height=320, yaxis_title="Revenue", xaxis_title=None,
                                          margin=dict(l=10, r=10, t=10, b=10)), width="stretch")

with tab_cat:
    csel = st.selectbox("Category", sorted(cur["category"].unique()))
    dc = cur[cur["category"] == csel]
    items = (dc.groupby("item")["total_spent"].agg(revenue="sum", transactions="count", avg_order="mean")
               .sort_values("revenue", ascending=False))
    top = items.head(15).reset_index().sort_values("revenue")
    fig = px.bar(top, x="revenue", y="item", orientation="h", text_auto=".3s",
                 color_discrete_sequence=[cat_colors.get(csel, ACCENT)])
    st.plotly_chart(fig.update_layout(height=max(280, 24 * len(top) + 60), xaxis_title="Revenue",
                                      yaxis_title=None, margin=dict(l=10, r=10, t=10, b=10)),
                    width="stretch")
    st.dataframe(items.round(2).reset_index(), width="stretch", hide_index=True)

# ----------------------------------------------------------------------------
# PDF export
# ----------------------------------------------------------------------------
def build_pdf() -> bytes:
    """Two-page PDF of the current view (same numbers as the dashboard)."""
    buf = io.BytesIO()
    cat_list = sorted(cur["category"].unique())
    with PdfPages(buf) as pdf:
        # ---- page 1: KPIs, trend, categories
        fig = plt.figure(figsize=(11.69, 8.27))
        fig.text(0.04, 0.95, "Retail Sales Dashboard", fontsize=20, fontweight="bold", color="#1f2d3d")
        fig.text(0.04, 0.92, f"{start.date()} to {end.date()}  |  {len(cur):,} transactions", fontsize=10, color="#555")
        for i, (label, value, _) in enumerate(cards):
            ax = fig.add_axes([0.04 + i * 0.1575, 0.79, 0.145, 0.10])
            ax.set_facecolor("#f4f6f9")
            ax.set_xticks([]); ax.set_yticks([])
            for s in ax.spines.values():
                s.set_color("#d0d7e2")
            ax.text(0.5, 0.64, value, ha="center", va="center", fontsize=15, fontweight="bold", color=ACCENT)
            ax.text(0.5, 0.25, label, ha="center", va="center", fontsize=8, color="#444")

        ax = fig.add_axes([0.07, 0.40, 0.88, 0.33])
        tm = (cur.groupby([pd.Grouper(key="transaction_date", freq="MS"), "category"])["total_spent"].sum()
                 .unstack("category", fill_value=0))
        ax.stackplot(tm.index, [tm[c] for c in tm.columns], labels=list(tm.columns),
                     colors=[cat_colors[c] for c in tm.columns], alpha=0.9)
        ax.set_title("Monthly revenue by category", loc="left", fontsize=11)
        ax.legend(ncol=len(tm.columns), fontsize=7, frameon=False, loc="upper left")
        ax.grid(alpha=0.25)

        ax = fig.add_axes([0.14, 0.07, 0.34, 0.25])
        bc = cur.groupby("category")["total_spent"].sum().sort_values()
        ax.barh(bc.index, bc.values, color=[cat_colors[c] for c in bc.index])
        ax.set_title("Revenue by category", loc="left", fontsize=11)
        ax.grid(axis="x", alpha=0.25)

        ax = fig.add_axes([0.60, 0.07, 0.34, 0.25])
        bp = cur.groupby("payment_method")["total_spent"].sum().sort_values()
        ax.barh(bp.index, bp.values, color=ACCENT)
        ax.set_title("Revenue by payment method", loc="left", fontsize=11)
        ax.grid(axis="x", alpha=0.25)
        pdf.savefig(fig)
        plt.close(fig)

        # ---- page 2: heatmaps + definitions
        fig = plt.figure(figsize=(11.69, 8.27))
        fig.text(0.04, 0.95, "Heatmaps and KPI definitions", fontsize=16, fontweight="bold", color="#1f2d3d")

        def heat(ax, data, title, fmt):
            im = ax.imshow(data.values, cmap="YlGnBu", aspect="auto")
            ax.set_xticks(range(data.shape[1])); ax.set_xticklabels(data.columns, rotation=30, ha="right", fontsize=8)
            ax.set_yticks(range(data.shape[0])); ax.set_yticklabels(data.index, fontsize=8)
            mid = (data.values.min() + data.values.max()) / 2
            for r in range(data.shape[0]):
                for c in range(data.shape[1]):
                    v = data.values[r, c]
                    ax.text(c, r, fmt(v), ha="center", va="center", fontsize=7, color="white" if v > mid else "black")
            ax.set_title(title, loc="left", fontsize=11)
            fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)

        heat(fig.add_axes([0.07, 0.58, 0.38, 0.30]), loc_cat, "Revenue: location x category", lambda v: f"{v / 1000:.0f}k")
        heat(fig.add_axes([0.56, 0.58, 0.38, 0.30]), wk, "Revenue: weekday x month", lambda v: f"{v / 1000:.0f}k")

        definitions = [
            "KPI definitions",
            "Revenue = sum of total_spent (price x quantity) over the transactions shown.",
            "Average order value = revenue / number of transactions.",
            f"Churn rate = customers with no purchase in the {churn_days} days before {end.date()} / customers seen in the period.",
            f"CAC = assumed marketing spend ({mkt_pct}% of revenue in the selected dates) / customers whose first purchase is in the selected dates.",
            "The data has no marketing cost and no geographic fields, so CAC uses an assumption and the location heatmap compares channels.",
            "Revenue changes are compared with the previous period of the same length.",
        ]
        for i, line in enumerate(definitions):
            fig.text(0.04, 0.46 - i * 0.045, line, fontsize=10 if i else 12, fontweight="bold" if i == 0 else "normal",
                     color="#222", wrap=True)
        pdf.savefig(fig)
        plt.close(fig)
    return buf.getvalue()


st.sidebar.markdown("---")
st.sidebar.subheader("Export")
if st.sidebar.button("Prepare PDF of this view"):
    st.session_state["pdf_bytes"] = build_pdf()
if "pdf_bytes" in st.session_state:
    st.sidebar.download_button("Download dashboard PDF", data=st.session_state["pdf_bytes"],
                               file_name="dashboard_export.pdf", mime="application/pdf")
    st.sidebar.caption("Prepare the PDF again after changing filters.")

with st.expander("KPI definitions and assumptions"):
    st.markdown(
        f"""
- **Revenue:** sum of `total_spent` (price x quantity) for the transactions shown.
- **Average order value:** revenue divided by the number of transactions.
- **Customer acquisition cost:** assumed marketing spend ({mkt_pct}% of revenue in the selected dates, adjustable in the sidebar) divided by customers whose first purchase falls in the selected dates. The data has no marketing cost, so this is illustrative.
- **Churn rate:** customers with no purchase in the last {churn_days} days of the selected period, divided by all customers seen in the period.
- **Previous period:** the period of the same length immediately before the selected dates.
- **Limits of the data:** only {df.loc[df['customer_id'] != 'Unknown', 'customer_id'].nunique()} distinct customers exist, and location is Online or In-Store, so there is no geographic map.
"""
    )
