import streamlit as st
import os
import pandas as pd
import plotly.express as px

from utils.data_loader import load_core, load_reporting, DATA_DIR
from utils.theme import inject_base_css, hero, section_header, status_badge, panel, CATEGORY_COLORS, PLOTLY_CONFIG, legend_dots

inject_base_css()
from utils.theme import top_header
top_header()

hero("Settings", "data, cache & about", chips={"Version": "1.0"})

core = load_core()
rep = load_reporting()

with panel():
    section_header("Data source", "Current dataset status", "🗄️")
    c1, c2, c3 = st.columns(3)
    c1.metric("Core records", f"{len(core):,}")
    c2.metric("Reporting records", f"{len(rep):,}")
    c3.metric("Date range", f"{core['Date'].min().year}–{core['Date'].max().year}")
    status_badge("Loaded from local parquet cache", "live")

st.write("")
with panel():
    section_header("Cache", "Streamlit cache controls", "🧹")
    st.caption(
        "Data is cached with `@st.cache_data(ttl=3600)` — it refreshes automatically every hour, "
        "or immediately if you clear it below (useful after re-running `prepare_data.py`)."
    )
    if st.button("Clear cached data", type="primary"):
        st.cache_data.clear()
        st.success("Cache cleared. Reload the page to fetch fresh data.")

st.write("")
with panel():
    section_header("Data files", "Where everything lives on disk", "📁")
    files_info = []
    for fname in ["core.parquet", "reporting.parquet", "merge_file_cleaned.xlsx"]:
        fpath = os.path.join(DATA_DIR, fname)
        exists = os.path.exists(fpath)
        size = f"{os.path.getsize(fpath) / 1024:.0f} KB" if exists else "—"
        files_info.append({"File": fname, "Status": "✅ Found" if exists else "❌ Missing", "Size": size})
    files_df = pd.DataFrame(files_info)
    st.dataframe(files_df, width="stretch", hide_index=True)

st.write("")
col1, col2 = st.columns(2)
with col1:
    with panel():
        section_header("Coverage", "Records by year", "📊")
        st.markdown(legend_dots({"Records": "#2563EB"}), unsafe_allow_html=True)
        by_year = core.groupby("Year", as_index=False)["Value"].count().rename(columns={"Value": "Records"})
        fig_year = px.bar(by_year, x="Year", y="Records", color_discrete_sequence=["#2563EB"])
        fig_year.update_layout(
            height=280, margin=dict(l=10, r=10, t=10, b=10),
            font=dict(family="Inter, sans-serif", size=12, color="#334155"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_year, width="stretch", theme=None, config=PLOTLY_CONFIG)

with col2:
    with panel():
        section_header("Composition", "Records by disease category", "🗂️")
        by_cat = core.groupby("Category", as_index=False)["Value"].count().rename(columns={"Value": "Records"}).sort_values("Records", ascending=True)
        st.markdown(
            legend_dots(CATEGORY_COLORS, keys=sorted(by_cat["Category"].unique())),
            unsafe_allow_html=True,
        )
        fig_cat = px.bar(
            by_cat, x="Records", y="Category", orientation="h", color="Category",
            color_discrete_map=CATEGORY_COLORS, text="Records",
        )
        fig_cat.update_traces(texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
        fig_cat.update_layout(
            height=280, margin=dict(l=10, r=40, t=10, b=10), showlegend=False,
            xaxis_title="", yaxis_title="",
            font=dict(family="Inter, sans-serif", size=12, color="#334155"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_cat, width="stretch", theme=None, config=PLOTLY_CONFIG)

st.write("")
col3, col4 = st.columns(2)
with col3:
    with panel():
        section_header("Coverage", "Records by province", "📍")
        st.markdown(legend_dots({"Records": "#10B981"}), unsafe_allow_html=True)
        by_prov_rec = core.groupby("Province", as_index=False)["Value"].count().rename(columns={"Value": "Records"})
        fig_prov_rec = px.bar(by_prov_rec.sort_values("Records"), x="Records", y="Province", orientation="h", color_discrete_sequence=["#10B981"])
        fig_prov_rec.update_layout(
            height=280, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="",
            font=dict(family="Inter, sans-serif", size=12, color="#334155"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_prov_rec, width="stretch", theme=None, config=PLOTLY_CONFIG)

with col4:
    with panel():
        section_header("Freshness", "Reporting records by year", "🕒")
        st.markdown(legend_dots({"Records": "#7C3AED"}), unsafe_allow_html=True)
        by_year_rep = rep.groupby("Year", as_index=False).size().rename(columns={"size": "Records"})
        fig_year_rep = px.area(by_year_rep, x="Year", y="Records", color_discrete_sequence=["#7C3AED"])
        fig_year_rep.update_layout(
            height=280, margin=dict(l=10, r=10, t=10, b=10),
            font=dict(family="Inter, sans-serif", size=12, color="#334155"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_year_rep, width="stretch", theme=None, config=PLOTLY_CONFIG)

st.write("")
with panel():
    section_header("About", "Pakistan Public Health Surveillance dashboard", "ℹ️")
    st.markdown(
        "Built on NIH IDSR weekly surveillance data (2021–2026). "
        "Eight analytical views: Overview, Geography, Trends, Outbreaks, Forecast, Executive Analytics, "
        "Reporting quality, and Settings.\n\n"
        "**Outbreak detection**: rolling-mean control limits (Shewhart-style) + EWMA, plus a WHO-style "
        "endemic channel that compares each calendar week to its own multi-year history and flags "
        "Alert (mean + 1σ) / Epidemic (mean + 2σ) weeks.\n\n"
        "**Forecast**: lightweight trend-blended projection (swap in Prophet/SARIMAX for production use).\n\n"
        "**Executive Analytics**: CAGR, volatility (CV%), Herfindahl concentration, correlation heatmaps, "
        "Pareto (80/20) analysis, year-over-year growth, and district-level z-score outlier ranking — "
        "a higher-level statistical layer built for directors and provincial/district health officers.\n\n"
        "**Reporting quality**: surfaces the `IDSR reporting districts` compliance sheet, which prior "
        "PowerBI versions of this dashboard never used."
    )
