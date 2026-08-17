import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.data_loader import load_core, filtered
from utils.theme import (
    inject_base_css, hero, kpi_card, section_header, status_badge,
    panel, insight_panel, PROVINCE_COLORS, CATEGORY_COLORS, PLOTLY_CONFIG, chart_or_table, pct_color,
)
from utils.filters import sidebar_filters, empty_state
from utils.anomaly import granular_series

inject_base_css()
from utils.theme import top_header
top_header()

core = load_core()
f = sidebar_filters(core)
df = filtered(core, f["provinces"], f["diseases"], f["categories"], f["date_range"])

hero(
    "Executive analytics",
    "the big picture, in plain language",
    chips={"Audience": "Everyone", "Detail": "Optional deep-dive included"},
)

if empty_state(df):
    st.stop()

# ---------------------------------------------------------------------
# Shared aggregates used across this page
# ---------------------------------------------------------------------
weekly = granular_series(df, "Weekly")
yearly_by_disease = df.groupby(["Year", "Clean Disease"], as_index=False)["Value"].sum()
top_diseases = df.groupby("Clean Disease")["Value"].sum().sort_values(ascending=False)
total_cases = float(df["Value"].sum())

# Compound annual growth rate off the yearly national total (first vs last full year in view)
by_year_total = df.groupby("Year")["Value"].sum().sort_index()
if len(by_year_total) >= 2 and by_year_total.iloc[0] > 0:
    n_years = by_year_total.index[-1] - by_year_total.index[0]
    cagr = ((by_year_total.iloc[-1] / by_year_total.iloc[0]) ** (1 / n_years) - 1) * 100 if n_years else 0
else:
    cagr = 0

# Volatility = coefficient of variation of the weekly series
volatility = (weekly["Value"].std() / weekly["Value"].mean() * 100) if weekly["Value"].mean() else 0

# Concentration = Herfindahl-Hirschman Index on disease shares (0 = perfectly spread, 1 = single disease)
shares = (top_diseases / total_cases) if total_cases else top_diseases
hhi = float((shares ** 2).sum()) if total_cases else 0

# Statistical outlier weeks = |z-score| > 2 on the national weekly series
w_mean, w_std = weekly["Value"].mean(), weekly["Value"].std()
outlier_weeks = int((((weekly["Value"] - w_mean) / w_std).abs() > 2).sum()) if w_std else 0

# =======================================================================
# EVERYDAY VIEW — plain language, no stats background needed (~90% of page)
# =======================================================================
section_header("The big picture", "What's happening, in plain terms", "🎯")
k1, k2, k3, k4 = st.columns(4)
_ex_spark = weekly.tail(12)["Value"].tolist()
kpi_card(k1, "OVERALL TREND", ("Rising" if cagr > 2 else "Falling" if cagr < -2 else "Steady"), "#2563EB", icon="trending-up", spark_values=_ex_spark)
kpi_card(k2, "HOW PREDICTABLE", ("Steady week to week" if volatility < 30 else "Some ups and downs" if volatility < 60 else "Very unpredictable"), "#F59E0B", icon="activity", spark_values=_ex_spark)
kpi_card(k3, "TOP DISEASES SHARE", f"{shares.head(3).sum()*100:.0f}%", "#7C3AED", icon="target", spark_values=_ex_spark)
kpi_card(k4, "WEEKS THAT LOOKED OFF", str(outlier_weeks), "#EF4444", icon="alert-triangle", spark_values=_ex_spark, subtitle=f"of {len(weekly):,} weeks" if len(weekly) else None)
st.caption(
    "**Overall trend** — is the yearly total going up or down. **How predictable** — do cases stay "
    "roughly the same each week, or jump around a lot. **Top diseases share** — how much of everything "
    "comes from just the 3 biggest diseases. **Weeks that looked off** — weeks where the numbers were "
    "far outside the usual pattern."
)

concentration_note = (
    "a handful of diseases drive most of the cases" if hhi > 0.25
    else "a small group of diseases make up a large part of the load" if hhi > 0.12
    else "cases are spread fairly evenly across many diseases"
)
top3_share = shares.head(3).sum() * 100 if total_cases else 0
insight_panel(
    "What this means, in one glance",
    [
        ("📈", f"Cases have been <b>{'rising' if cagr > 2 else 'falling' if cagr < -2 else 'holding steady'}</b> year over year ({cagr:+.1f}% a year on average)."),
        ("🌊", f"Week-to-week, the numbers are <b>{'very unpredictable' if volatility > 60 else 'somewhat variable' if volatility > 30 else 'fairly steady'}</b>."),
        ("🎯", f"The top 3 diseases make up <b>{top3_share:.0f}%</b> of all cases — {concentration_note}."),
        ("⚠️", f"<b>{outlier_weeks}</b> week(s) stood out as unusual and may be worth a closer look." if outlier_weeks else "No weeks stood out as unusual in this selection."),
    ],
)

st.write("")
with panel():
    section_header("Which diseases matter most", "The 20% of diseases driving 80% of all cases", "📶")
    pareto = top_diseases.reset_index()
    pareto.columns = ["Clean Disease", "Value"]
    pareto["Cumulative %"] = pareto["Value"].cumsum() / pareto["Value"].sum() * 100
    n_show = min(15, len(pareto))
    pareto_show = pareto.head(n_show)
    n_to_80 = int((pareto["Cumulative %"] <= 80).sum()) + 1

    fig_pareto = go.Figure()
    fig_pareto.add_trace(go.Bar(
        x=pareto_show["Clean Disease"], y=pareto_show["Value"], name="Cases",
        marker_color="#2563EB", yaxis="y1",
    ))
    fig_pareto.add_trace(go.Scatter(
        x=pareto_show["Clean Disease"], y=pareto_show["Cumulative %"], name="Running total %",
        mode="lines+markers", line=dict(color="#F59E0B", width=2.4), yaxis="y2",
    ))
    fig_pareto.add_hline(y=80, line=dict(color="#94A3B8", dash="dot", width=1), yref="y2")
    fig_pareto.update_layout(
        height=420, margin=dict(l=10, r=10, t=48, b=90),
        xaxis=dict(title="", tickangle=-40),
        yaxis=dict(title="Cases"),
        yaxis2=dict(title="Running total %", overlaying="y", side="right", range=[0, 105]),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            font=dict(size=11), bgcolor="rgba(0,0,0,0)",
        ),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=11, color="#334155"),
    )
    st.plotly_chart(fig_pareto, width="stretch", theme=None, config=PLOTLY_CONFIG)
    st.caption(f"**Just {n_to_80} disease(s)** account for roughly 80% of all cases in this selection — focus resources here first.")

st.write("")
with panel():
    section_header("Growing or shrinking, year by year", "How each top disease changed vs. the year before", "📅")
    top_yoy_diseases = top_diseases.head(10).index.tolist()
    yoy = yearly_by_disease[yearly_by_disease["Clean Disease"].isin(top_yoy_diseases)].copy()
    yoy_pivot = yoy.pivot(index="Clean Disease", columns="Year", values="Value").reindex(top_yoy_diseases)
    growth = yoy_pivot.pct_change(axis=1, fill_method=None) * 100
    growth = growth.iloc[:, 1:]  # drop first year (no prior-year comparison)
    if growth.shape[1] >= 1:
        fig_yoy = px.imshow(
            growth.round(0), text_auto=True, color_continuous_scale="RdYlGn_r",
            zmin=-50, zmax=50, aspect="auto",
            labels=dict(color="% change", x="Year", y="Disease"),
        )
        fig_yoy.update_layout(
            height=380, margin=dict(l=10, r=10, t=10, b=10),
            font=dict(family="Inter, sans-serif", size=11, color="#334155"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_yoy, width="stretch", theme=None, config=PLOTLY_CONFIG)
        st.caption("Red = went up compared to the year before, green = went down. Needs at least two years selected to show.")
    else:
        st.write("Select a date range spanning at least two years to see year-over-year change.")

st.write("")
with panel():
    section_header("Where to look first", "Districts with the most unusual weeks", "🚨")
    dist_weekly = df.groupby(["District", "Province", "Date"], as_index=False)["Value"].sum()
    dist_weekly["z"] = dist_weekly.groupby("District")["Value"].transform(
        lambda s: (s - s.mean()) / s.std() if s.std() else 0
    )
    outliers = dist_weekly.replace([np.inf, -np.inf], np.nan).dropna(subset=["z"])
    outliers = outliers.reindex(outliers["z"].abs().sort_values(ascending=False).index).head(10)
    outliers_display = outliers[["District", "Province", "Date", "Value"]].rename(columns={"Value": "Cases that week"})
    outliers_display["Date"] = outliers_display["Date"].dt.date
    st.dataframe(outliers_display, width="stretch", hide_index=True)
    st.caption("These are the district-weeks that looked most out of the ordinary compared to that district's own usual pattern — a good starting list for follow-up.")

# =======================================================================
# ADVANCED VIEW — optional deep-dive for analysts/statisticians (~10%)
# =======================================================================
st.write("")
with st.expander("🔬 Advanced statistics — click to explore the numbers behind the summary above", expanded=False):
    status_badge("For analysts & statisticians", "info")
    st.caption(
        "Everything above is the plain-language summary. This section shows the underlying statistical "
        "detail (CAGR, CV, HHI, correlation, z-scores) for anyone who wants to verify or dig deeper."
    )

    st.write("")
    h1, h2 = st.columns([3, 1])
    with h1:
        section_header("Descriptive statistics", "Per-disease weekly statistics", "📊")
    with h2:
        top_n_stats = st.selectbox("Diseases", [5, 10, 15, 20], index=1, key="exec_topn_stats", label_visibility="collapsed")

    stat_rows = []
    for disease in top_diseases.head(top_n_stats).index:
        s = granular_series(df[df["Clean Disease"] == disease], "Weekly")["Value"]
        if len(s) < 4:
            continue
        mean_v, std_v = s.mean(), s.std()
        stat_rows.append({
            "Disease": disease,
            "Mean": round(mean_v, 1),
            "Median": round(s.median(), 1),
            "Std dev": round(std_v, 1),
            "CV %": round((std_v / mean_v * 100) if mean_v else 0, 1),
            "Skewness": round(s.skew(), 2),
            "Kurtosis": round(s.kurt(), 2),
            "Min": round(s.min(), 1),
            "Max": round(s.max(), 1),
        })
    stats_df = pd.DataFrame(stat_rows)
    st.dataframe(stats_df, width="stretch", hide_index=True)
    if len(stats_df):
        st.download_button(
            "Download statistical summary as CSV",
            stats_df.to_csv(index=False).encode("utf-8"),
            "executive_statistical_summary.csv", "text/csv",
        )

    st.write("")
    col1, col2 = st.columns(2)
    with col1:
        section_header("Correlation", "Which diseases move together (Pearson r)", "🔗")
        corr_diseases = top_diseases.head(10).index.tolist()
        pivot = (
            df[df["Clean Disease"].isin(corr_diseases)]
            .groupby(["Date", "Clean Disease"])["Value"].sum()
            .unstack(fill_value=0)
        )
        if pivot.shape[1] >= 2 and len(pivot) >= 3:
            corr = pivot.corr().round(2)
            fig_corr = px.imshow(
                corr, text_auto=True, color_continuous_scale="RdBu_r", zmin=-1, zmax=1, aspect="auto",
                labels=dict(color="Correlation", x="Disease", y="Disease"),
            )
            fig_corr.update_layout(
                height=420, margin=dict(l=10, r=10, t=10, b=10),
                font=dict(family="Inter, sans-serif", size=10.5, color="#334155"),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_corr, width="stretch", theme=None, config=PLOTLY_CONFIG)
            st.caption("Near +1 = rise and fall together; near −1 = move in opposite directions.")
        else:
            st.write("Not enough overlapping history to compute correlations for the current filter.")

    with col2:
        section_header("Provincial profile", "Category composition by province (normalized)", "🕸️")
        provs_in_view = sorted(df["Province"].unique().tolist())
        cats_in_view = sorted(df["Category"].unique().tolist())
        if provs_in_view and cats_in_view:
            comp = df.groupby(["Province", "Category"])["Value"].sum().unstack(fill_value=0)
            comp_norm = comp.div(comp.sum(axis=1), axis=0).fillna(0)
            # Grouped bar instead of a radar/spider chart: radar charts distort
            # area-based comparison across axes, especially with 4 overlapping
            # provinces — a grouped bar keeps each category's cross-province
            # comparison on one shared, readable scale.
            comp_long = comp_norm.loc[[p for p in provs_in_view if p in comp_norm.index], cats_in_view].reset_index().melt(
                id_vars="Province", var_name="Category", value_name="Share"
            )
            fig_radar = px.bar(
                comp_long, x="Category", y="Share", color="Province", barmode="group",
                color_discrete_map=PROVINCE_COLORS,
            )
            fig_radar.update_layout(
                height=380, margin=dict(l=10, r=10, t=20, b=80),
                yaxis=dict(title="Share of province's cases", tickformat=".0%"),
                xaxis_title="",
                legend=dict(
                    orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5,
                    title_text="", font=dict(size=10.5),
                ),
                font=dict(family="Inter, sans-serif", size=11, color="#334155"),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_radar, width="stretch", theme=None, config=PLOTLY_CONFIG)
            st.caption("Each province's own mix (sums to 100%) — compares category profile, not raw volume.")
        else:
            st.write("Not enough data to build provincial profiles for the current filter.")

    st.write("")
    section_header("Statistical spread", "Weekly case distribution by province (box plot)", "📦")
    prov_weekly = df.groupby(["Province", "Date"], as_index=False)["Value"].sum()
    fig_box = px.box(
        prov_weekly, x="Province", y="Value", color="Province",
        color_discrete_map=PROVINCE_COLORS, points="outliers",
    )
    fig_box.update_layout(
        height=340, margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
        xaxis_title="", yaxis_title="Weekly cases",
        font=dict(family="Inter, sans-serif", size=11, color="#334155"),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_box, width="stretch", theme=None, config=PLOTLY_CONFIG)
    st.caption("Box = middle 50% of weeks, line = median, dots = statistical outlier weeks (beyond 1.5×IQR).")

    st.caption(
        f"Raw values behind the summary cards above — CAGR: {cagr:+.2f}%, CV: {volatility:.1f}%, "
        f"HHI: {hhi:.3f}, outlier weeks (|z|>2): {outlier_weeks}."
    )

st.write("")
with panel():
    section_header("Composition", "Case share by disease category", "🗂️")
    cat_totals = df.groupby("Category", as_index=False)["Value"].sum().sort_values("Value", ascending=True)
    cat_totals["Share"] = cat_totals["Value"] / cat_totals["Value"].sum() * 100 if cat_totals["Value"].sum() else 0
    fig_cat_tree = px.bar(
        cat_totals, x="Share", y="Category", orientation="h", color="Category",
        color_discrete_map=CATEGORY_COLORS, text="Share", custom_data=["Value"],
    )
    fig_cat_tree.update_traces(
        texttemplate="%{text:.0f}%", textposition="outside", cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>Share: %{x:.1f}%<br>Cases: %{customdata[0]:,.0f}<extra></extra>",
    )
    fig_cat_tree.update_layout(
        height=300, margin=dict(l=4, r=40, t=6, b=4), showlegend=False,
        xaxis_title="Share of cases (%)", yaxis_title="",
        font=dict(family="Inter, sans-serif", size=12, color="#334155"),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    cat_table = cat_totals[["Category", "Share", "Value"]].rename(
        columns={"Share": "Share %", "Value": "Cases"}
    ).sort_values("Share %", ascending=False)
    chart_or_table(fig_cat_tree, cat_table, key="ex_cat_share")

st.write("")
col_a, col_b = st.columns(2)
with col_a:
    with panel():
        section_header("Momentum", "Year-over-year change, national total", "📶")
        yoy_nat = by_year_total.reset_index()
        yoy_nat.columns = ["Year", "Value"]
        yoy_nat["Change"] = yoy_nat["Value"].diff()
        fig_wf = go.Figure(go.Waterfall(
            x=yoy_nat["Year"].astype(str), y=yoy_nat["Change"].fillna(yoy_nat["Value"]),
            connector=dict(line=dict(color="#CBD5E1")),
            increasing=dict(marker=dict(color="#EF4444")), decreasing=dict(marker=dict(color="#10B981")),
            showlegend=False,
        ))
        # Waterfall traces don't expose increasing/decreasing as separate legend
        # entries on their own, so add two invisible marker traces purely to
        # surface a legend explaining what red vs. green means here.
        fig_wf.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers", name="Increase vs. prior year",
            marker=dict(color="#EF4444", size=10, symbol="square"),
        ))
        fig_wf.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers", name="Decrease vs. prior year",
            marker=dict(color="#10B981", size=10, symbol="square"),
        ))
        fig_wf.update_layout(
            height=360, margin=dict(l=10, r=10, t=48, b=10), yaxis_title="Change in cases",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                font=dict(size=11), bgcolor="rgba(0,0,0,0)",
            ),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", size=11, color="#334155"),
        )
        st.plotly_chart(fig_wf, width="stretch", theme=None, config=PLOTLY_CONFIG)
        st.caption("Red bars = more cases than the prior year, green bars = fewer.")

with col_b:
    with panel():
        section_header("Balance", "Province share of national burden", "⚖️")
        prov_share = df.groupby("Province", as_index=False)["Value"].sum().sort_values("Value", ascending=True)
        prov_share["Share"] = prov_share["Value"] / prov_share["Value"].sum() * 100 if prov_share["Value"].sum() else 0
        fig_prov_share = px.bar(
            prov_share, x="Share", y="Province", orientation="h", color="Province",
            color_discrete_map=PROVINCE_COLORS, text="Share", custom_data=["Value"],
        )
        fig_prov_share.update_traces(
            texttemplate="%{text:.0f}%", textposition="outside", cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>Share: %{x:.1f}%<br>Cases: %{customdata[0]:,.0f}<extra></extra>",
        )
        fig_prov_share.update_layout(
            height=320, margin=dict(l=10, r=40, t=10, b=10), showlegend=False,
            xaxis_title="Share of national cases (%)", yaxis_title="",
            font=dict(family="Inter, sans-serif", size=11, color="#334155"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        table_data = prov_share[["Province", "Share", "Value"]].rename(
            columns={"Share": "Share %", "Value": "Cases"}
        ).sort_values("Share %", ascending=False)
        chart_or_table(fig_prov_share, table_data, key="ex_prov_share")

st.info(
    "This page leads with the plain-language summary anyone can read at a glance — the technical "
    "detail behind it (for analysts and statisticians) is tucked into the expandable section above."
)
