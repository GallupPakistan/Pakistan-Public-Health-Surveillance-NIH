import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from utils.data_loader import load_core, filtered
from utils.theme import inject_base_css, hero, kpi_card, section_header, panel, CATEGORY_COLORS, PROVINCE_COLORS, PLOTLY_CONFIG
from utils.filters import sidebar_filters, empty_state

inject_base_css()
from utils.theme import top_header
top_header()

core = load_core()
f = sidebar_filters(core)
df = filtered(core, f["provinces"], f["diseases"], f["categories"], f["date_range"])

if empty_state(df):
    st.stop()

hero("Seasonality", "recurring patterns by month", chips={"Records": f"{len(df):,}"})

month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
by_month = df.groupby("MonthName", as_index=False)["Value"].sum()
by_month["MonthName"] = pd.Categorical(by_month["MonthName"], categories=month_order, ordered=True)
by_month = by_month.sort_values("MonthName")
peak_month = by_month.sort_values("Value", ascending=False).iloc[0]["MonthName"] if len(by_month) else "—"
peak_share = (by_month["Value"].max() / by_month["Value"].sum() * 100) if len(by_month) and by_month["Value"].sum() else 0

# peak_month above is a recurring-pattern aggregate (all years' Septembers
# summed together, say) — useful for "which month tends to peak", but on
# its own ("Sep") it doesn't say WHEN, across 6 years of data. This finds
# the single highest-volume Year+Month instance specifically, so the KPI
# card can ground the pattern with a real year, not just a repeating month.
by_year_month = df.groupby(["Year", "MonthName"], as_index=False)["Value"].sum()
if len(by_year_month):
    _peak_ym_row = by_year_month.sort_values("Value", ascending=False).iloc[0]
    peak_year_month_label = f"{_peak_ym_row['MonthName']} {int(_peak_ym_row['Year'])}"
else:
    peak_year_month_label = None

# ---------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------
section_header("Snapshot", "Seasonal pattern summary", "🌦️")
k1, k2, k3, k4 = st.columns(4)
_tr_spark = df.groupby("Date", as_index=False)["Value"].sum().tail(12)["Value"].tolist()
kpi_card(
    k1, "PEAK MONTH", peak_year_month_label if peak_year_month_label else str(peak_month),
    "#2563EB", icon="calendar", spark_values=_tr_spark,
)
kpi_card(k2, "PEAK MONTH SHARE", f"{peak_share:.0f}%", "#F59E0B", icon="flame", spark_values=_tr_spark, subtitle=f"{int(by_month['Value'].max()):,} cases" if len(by_month) else None)
kpi_card(k3, "DISEASES TRACKED", str(df["Clean Disease"].nunique()), "#10B981", icon="dna", spark_values=_tr_spark)
kpi_card(k4, "YEARS COVERED", str(df["Year"].nunique()), "#EF4444", icon="calendar", spark_values=_tr_spark)

st.write("")
with panel():
    section_header("Pattern detection", "Disease x month heatmap", "🔥")
    top_n = st.slider("Show top N diseases by volume", 5, 20, 12)
    top_diseases = df.groupby("Clean Disease")["Value"].sum().nlargest(top_n).index.tolist()
    heat_df = df[df["Clean Disease"].isin(top_diseases)]
    pivot = heat_df.pivot_table(index="Clean Disease", columns="MonthName", values="Value", aggfunc="sum", fill_value=0)
    pivot = pivot.reindex(columns=[m for m in month_order if m in pivot.columns])

    fig = px.imshow(
        pivot, aspect="auto", color_continuous_scale="Blues",
        labels=dict(color="Cases", x="Month", y="Disease"),
    )
    fig.update_layout(
        height=460, margin=dict(l=10, r=10, t=10, b=10),
        yaxis=dict(title=dict(text="Disease", standoff=18)),
        font=dict(family="Inter, sans-serif", size=12, color="#334155"),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, width="stretch", theme=None, config=PLOTLY_CONFIG)
    st.caption("Darker cells = higher case volume in that month, summed across all years in the current filter.")

st.write("")
col1, col2 = st.columns(2)
with col1:
    with panel():
        section_header("Overall pattern", "Total cases by calendar month", "📆")
        fig_month = px.bar(by_month, x="MonthName", y="Value", color_discrete_sequence=["#2563EB"])
        fig_month.update_layout(
            height=300, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="", yaxis_title="Cases",
            font=dict(family="Inter, sans-serif", size=12, color="#334155"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_month, width="stretch", theme=None, config=PLOTLY_CONFIG)

with col2:
    with panel():
        section_header("By category", "Seasonal mix by disease category", "🗂️")
        cat_month = df.groupby(["MonthName", "Category"], as_index=False)["Value"].sum()
        cat_month["MonthName"] = pd.Categorical(cat_month["MonthName"], categories=month_order, ordered=True)
        cat_month = cat_month.sort_values("MonthName")
        fig_cat = px.area(
            cat_month, x="MonthName", y="Value", color="Category", color_discrete_map=CATEGORY_COLORS,
            groupnorm="fraction",
        )
        fig_cat.update_layout(
            height=340, margin=dict(l=10, r=10, t=48, b=10), xaxis_title="", yaxis_title="Share of cases",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                title_text="Category", font=dict(size=10.5), bgcolor="rgba(0,0,0,0)",
            ),
            font=dict(family="Inter, sans-serif", size=12, color="#334155"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_cat, width="stretch", theme=None, config=PLOTLY_CONFIG)

st.write("")
with panel():
    section_header("Year over year", "Same-month comparison across years", "📈")
    yoy = df.groupby(["Year", "MonthName"], as_index=False)["Value"].sum()
    yoy["MonthName"] = pd.Categorical(yoy["MonthName"], categories=month_order, ordered=True)
    yoy = yoy.sort_values("MonthName")
    fig_yoy = px.line(yoy, x="MonthName", y="Value", color="Year", markers=True)
    fig_yoy.update_layout(
        height=380, margin=dict(l=10, r=10, t=48, b=10), xaxis_title="", yaxis_title="Cases",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            title_text="Year", font=dict(size=11), bgcolor="rgba(0,0,0,0)",
        ),
        font=dict(family="Inter, sans-serif", size=12, color="#334155"),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_yoy, width="stretch", theme=None, config=PLOTLY_CONFIG)
    st.caption("Reveals whether a spike is a one-off or a recurring seasonal pattern year after year.")

st.write("")
with panel():
    section_header("By province", "Which province drives the peak month", "📍")
    peak_prov = df[df["MonthName"] == peak_month].groupby("Province", as_index=False)["Value"].sum().sort_values("Value", ascending=False)
    fig_prov = px.bar(
        peak_prov, x="Province", y="Value", color="Province", color_discrete_map=PROVINCE_COLORS,
    )
    fig_prov.update_layout(
        height=300, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="", yaxis_title=f"Cases in {peak_month}",
        showlegend=False, font=dict(family="Inter, sans-serif", size=12, color="#334155"),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_prov, width="stretch", theme=None, config=PLOTLY_CONFIG)

st.write("")
with panel():
    section_header("Detail view", "Small multiples: monthly pattern per disease", "📐")
    mm = (
        df[df["Clean Disease"].isin(top_diseases[:8])]
        .groupby(["Clean Disease", "Month"], as_index=False)["Value"].sum()
    )
    fig2 = px.line(
        mm, x="Month", y="Value", facet_col="Clean Disease", facet_col_wrap=4,
        facet_col_spacing=0.05, facet_row_spacing=0.18,
        color_discrete_sequence=["#2563EB"],
    )
    fig2.update_yaxes(matches=None, showticklabels=True)
    fig2.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1][:22]))
    fig2.update_layout(
        height=420, margin=dict(l=10, r=10, t=30, b=10), showlegend=False,
        font=dict(family="Inter, sans-serif", size=11, color="#334155"),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig2, width="stretch", theme=None, config=PLOTLY_CONFIG)
    st.caption("Y-axis is intentionally independent per facet so smaller diseases remain readable.")

st.write("")
col3, col4 = st.columns(2)
with col3:
    with panel():
        section_header("Quarterly view", "Cases by quarter", "🧮")
        qdf = df.copy()
        qdf["Quarter"] = "Q" + qdf["Date"].dt.quarter.astype(str)
        by_q = qdf.groupby("Quarter", as_index=False)["Value"].sum().sort_values("Quarter")
        fig_q = px.bar(by_q, x="Quarter", y="Value", color_discrete_sequence=["#7C3AED"])
        fig_q.update_layout(
            height=300, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="", yaxis_title="Cases",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", size=12, color="#334155"),
        )
        st.plotly_chart(fig_q, width="stretch", theme=None, config=PLOTLY_CONFIG)

with col4:
    with panel():
        section_header("Smoothed", "4-week rolling average of total cases", "📉")
        roll = df.groupby("Date", as_index=False)["Value"].sum().sort_values("Date")
        roll["Rolling 4wk"] = roll["Value"].rolling(4, min_periods=1).mean()
        fig_roll = go.Figure()
        fig_roll.add_trace(go.Scatter(x=roll["Date"], y=roll["Value"], name="Weekly", line=dict(color="#CBD5E1", width=1)))
        fig_roll.add_trace(go.Scatter(x=roll["Date"], y=roll["Rolling 4wk"], name="4wk avg", line=dict(color="#2563EB", width=2.5)))
        fig_roll.update_layout(
            height=340, margin=dict(l=10, r=10, t=48, b=10), xaxis_title="", yaxis_title="Cases",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                font=dict(size=10.5), bgcolor="rgba(0,0,0,0)",
            ),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", size=12, color="#334155"),
        )
        st.plotly_chart(fig_roll, width="stretch", theme=None, config=PLOTLY_CONFIG)

st.write("")
col5, col6 = st.columns(2)
with col5:
    with panel():
        h1, h2 = st.columns([2, 1.4])
        with h1:
            section_header("Seasonality shape", "Monthly pattern, radial or linear", "🎯")
        with h2:
            shape_mode = st.radio(
                "View as", options=["Radial", "Linear"], index=0, horizontal=True,
                key="tr_polar_mode", label_visibility="collapsed",
            )
        radial = by_month.copy()
        if shape_mode == "Radial":
            fig_polar = px.line_polar(radial, r="Value", theta="MonthName", line_close=True)
            fig_polar.update_traces(fill="toself", line_color="#2563EB")
            fig_polar.update_layout(
                height=360, margin=dict(l=20, r=20, t=20, b=20),
                font=dict(family="Inter, sans-serif", size=11, color="#334155"),
                paper_bgcolor="rgba(0,0,0,0)",
            )
        else:
            # Plain line version of the same monthly-shape data — polar/rose
            # charts are unfamiliar to a lot of readers and hard to read
            # exact values off, so this gives the same "shape across the
            # year" story in a more universally legible format.
            fig_polar = px.line(radial, x="MonthName", y="Value", markers=True)
            fig_polar.update_traces(line_color="#2563EB", fill="tozeroy", fillcolor="rgba(37,99,235,0.10)")
            fig_polar.update_layout(
                height=360, margin=dict(l=10, r=10, t=20, b=10), xaxis_title="", yaxis_title="Cases",
                font=dict(family="Inter, sans-serif", size=11, color="#334155"),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
        st.plotly_chart(fig_polar, width="stretch", theme=None, config=PLOTLY_CONFIG)

with col6:
    with panel():
        section_header("Category trend", "Category share over time", "🗂️")
        cat_time = df.groupby(["Date", "Category"], as_index=False)["Value"].sum()
        fig_cat_time = px.area(
            cat_time, x="Date", y="Value", color="Category", color_discrete_map=CATEGORY_COLORS,
        )
        fig_cat_time.update_layout(
            height=400, margin=dict(l=10, r=10, t=48, b=10), xaxis_title="", yaxis_title="Cases",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                title_text="Category", font=dict(size=10.5), bgcolor="rgba(0,0,0,0)",
            ),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", size=12, color="#334155"),
        )
        st.plotly_chart(fig_cat_time, width="stretch", theme=None, config=PLOTLY_CONFIG)
