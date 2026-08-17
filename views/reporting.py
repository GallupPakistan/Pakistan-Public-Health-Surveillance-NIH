import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from utils.data_loader import load_core, load_reporting
from utils.theme import inject_base_css, hero, kpi_card, section_header, panel, PROVINCE_COLORS, PLOTLY_CONFIG, pct_color
from utils.filters import sidebar_filters, empty_state

inject_base_css()
from utils.theme import top_header
top_header()

core = load_core()
f = sidebar_filters(core)
rep = load_reporting()
if f["provinces"]:
    rep = rep[rep["Province"].isin(f["provinces"])]
if f["date_range"]:
    start, end = f["date_range"]
    # reporting sheet uses Year/Week, approximate join to the same range via year
    rep = rep[(rep["Year"] >= start.year) & (rep["Year"] <= end.year)]

hero("Reporting quality", "can we trust the numbers", chips={"Sites tracked": f"{int(rep['Reporting_Sites_Total'].sum()):,}" if len(rep) else "0"})

if empty_state(rep, "No reporting-compliance records match the current filters."):
    st.stop()

st.info(
    "This page uses the `IDSR reporting districts` sheet, which the PowerBI version doesn't "
    "surface at all. Low case counts can mean genuinely low disease *or* under-reporting — "
    "this page tells the difference."
)

by_prov = rep.groupby("Province", as_index=False)["Compliance_Rate_Pct"].mean().sort_values("Compliance_Rate_Pct", ascending=False)
by_district_c = rep.groupby(["District", "Province"], as_index=False)["Compliance_Rate_Pct"].mean()
avg_compliance = rep["Compliance_Rate_Pct"].mean()
best_province = by_prov.iloc[0]["Province"] if len(by_prov) else "—"
worst_row = by_district_c.sort_values("Compliance_Rate_Pct").iloc[0] if len(by_district_c) else None

# ---------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------
section_header("Snapshot", "Reporting trust at a glance", "✅")
k1, k2, k3, k4 = st.columns(4)
_rp_spark = rep.groupby(["Year", "Week"], as_index=False)["Compliance_Rate_Pct"].mean().tail(12)["Compliance_Rate_Pct"].tolist()
kpi_card(k1, "AVG COMPLIANCE", f"{avg_compliance:.0f}%", pct_color(avg_compliance, good_high=True), icon="check-circle", spark_values=_rp_spark, value_color=pct_color(avg_compliance, good_high=True))
kpi_card(k2, "BEST PROVINCE", best_province, "#2563EB", icon="trophy", spark_values=_rp_spark)
kpi_card(k3, "WORST DISTRICT", worst_row["District"] if worst_row is not None else "—", "#EF4444", icon="alert-triangle", spark_values=_rp_spark)
kpi_card(k4, "SITES TRACKED", f"{int(rep['Reporting_Sites_Total'].sum()):,}", "#F59E0B", icon="archive", spark_values=_rp_spark)

st.write("")
with panel():
    section_header("Trust score", "Compliance rate by province", "✅")
    cols = st.columns(len(by_prov)) if len(by_prov) else [st]
    for col, (_, row) in zip(cols, by_prov.iterrows()):
        pct = row["Compliance_Rate_Pct"]
        color = "#10B981" if pct >= 70 else ("#F59E0B" if pct >= 50 else "#EF4444")
        fig = go.Figure(go.Indicator(
            mode="number+gauge",
            value=pct,
            number={"suffix": "%", "font": {"size": 22, "family": "Manrope, sans-serif"}},
            domain=dict(x=[0.05, 0.95], y=[0.35, 0.65]),
            gauge={
                "shape": "bullet",
                "axis": {"range": [0, 100], "visible": False},
                "bar": {"color": color, "thickness": 0.6},
                "bgcolor": "rgba(0,0,0,0.04)",
                "borderwidth": 0,
                "threshold": {"line": {"color": "#101828", "width": 2}, "thickness": 0.9, "value": 70},
            },
        ))
        fig.update_layout(
            height=90, margin=dict(l=10, r=10, t=10, b=10),
            font=dict(family="Inter, sans-serif", color="#334155"),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        col.plotly_chart(fig, width="stretch", theme=None, config=PLOTLY_CONFIG)
        col.markdown(f"<p style='text-align:center;font-size:13px;font-weight:600;color:#334155;'>{row['Province']}</p>", unsafe_allow_html=True)

st.write("")
col1, col2 = st.columns(2)
with col1:
    with panel():
        section_header("Distribution", "District compliance spread", "📊")
        fig_hist = px.histogram(
            by_district_c, x="Compliance_Rate_Pct", nbins=16, color_discrete_sequence=["#2563EB"],
        )
        fig_hist.add_vline(x=70, line_dash="dot", line_color="#94A3B8")
        fig_hist.update_layout(
            height=300, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="Compliance %", yaxis_title="Districts",
            font=dict(family="Inter, sans-serif", size=12, color="#334155"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_hist, width="stretch", theme=None, config=PLOTLY_CONFIG)

with col2:
    with panel():
        section_header("Ratio", "Sites reporting vs. agreed sites", "🧾")
        sites = rep[["Sites_Reported_Current_Week", "Agreed_Reporting_Sites"]].sum()
        fig_pie = px.pie(
            names=["Reported this week", "Not yet reporting"],
            values=[sites["Sites_Reported_Current_Week"], max(sites["Agreed_Reporting_Sites"] - sites["Sites_Reported_Current_Week"], 0)],
            hole=0.55, color_discrete_sequence=["#10B981", "#EF4444"],
        )
        fig_pie.update_traces(textinfo="percent+label")
        fig_pie.update_layout(
            height=300, margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
            font=dict(family="Inter, sans-serif", size=12, color="#334155"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_pie, width="stretch", theme=None, config=PLOTLY_CONFIG)

st.write("")
with panel():
    section_header("Time trend", "Compliance trend over time", "📉")
    trend = rep.groupby(["Year", "Week", "Province"], as_index=False)["Compliance_Rate_Pct"].mean()
    trend["Date"] = pd.to_datetime(trend["Year"].astype(str) + trend["Week"].astype(str) + "1", format="%Y%W%w", errors="coerce")
    fig2 = px.line(
        trend.dropna(subset=["Date"]), x="Date", y="Compliance_Rate_Pct", color="Province",
        color_discrete_map=PROVINCE_COLORS,
    )
    fig2.add_hline(y=70, line_dash="dot", line_color="#94A3B8", annotation_text="70% target")
    fig2.update_layout(
        height=420, margin=dict(l=10, r=10, t=48, b=10), yaxis_title="Compliance %",
        font=dict(family="Inter, sans-serif", size=12, color="#334155"),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            title_text="Province", font=dict(size=11), bgcolor="rgba(0,0,0,0)",
        ),
    )
    st.plotly_chart(fig2, width="stretch", theme=None, config=PLOTLY_CONFIG)

st.write("")
with panel():
    section_header("Ranking", "Compliance by district, best to worst", "🏅")
    ranked_districts = by_district_c.sort_values("Compliance_Rate_Pct", ascending=False)
    fig3 = px.bar(
        ranked_districts.head(15).sort_values("Compliance_Rate_Pct"),
        x="Compliance_Rate_Pct", y="District", orientation="h", color="Province",
        color_discrete_map=PROVINCE_COLORS,
    )
    fig3.add_vline(x=70, line_dash="dot", line_color="#94A3B8")
    fig3.update_layout(
        height=460, margin=dict(l=10, r=10, t=48, b=10), yaxis_title="", xaxis_title="Compliance %",
        font=dict(family="Inter, sans-serif", size=12, color="#334155"),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            title_text="Province", font=dict(size=11), bgcolor="rgba(0,0,0,0)",
        ),
    )
    fig3.update_traces(marker_line_width=0)
    st.plotly_chart(fig3, width="stretch", theme=None, config=PLOTLY_CONFIG)

st.write("")
with panel():
    section_header("Needs attention", "Lowest-compliance districts (current filter)", "⚠️")
    worst = by_district_c.sort_values("Compliance_Rate_Pct").head(10)
    st.dataframe(worst, width="stretch", hide_index=True)

st.write("")
col3, col4 = st.columns(2)
with col3:
    with panel():
        section_header("Spread", "Compliance distribution by province (box plot)", "📦")
        fig_box = px.box(
            rep, x="Province", y="Compliance_Rate_Pct", color="Province",
            color_discrete_map=PROVINCE_COLORS, points="outliers",
        )
        fig_box.add_hline(y=70, line_dash="dot", line_color="#94A3B8")
        fig_box.update_layout(
            height=340, margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
            xaxis_title="", yaxis_title="Compliance %",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", size=11, color="#334155"),
        )
        st.plotly_chart(fig_box, width="stretch", theme=None, config=PLOTLY_CONFIG)

with col4:
    with panel():
        section_header("Seasonality", "Compliance heatmap: province × week", "🔥")
        heat_rep = rep.groupby(["Province", "Week"], as_index=False)["Compliance_Rate_Pct"].mean()
        heat_rep_pivot = heat_rep.pivot(index="Province", columns="Week", values="Compliance_Rate_Pct").fillna(0)
        fig_heat_rep = px.imshow(heat_rep_pivot, aspect="auto", color_continuous_scale="RdYlGn", labels=dict(color="Compliance %"))
        fig_heat_rep.update_layout(
            height=340, margin=dict(l=10, r=10, t=10, b=10),
            font=dict(family="Inter, sans-serif", size=11, color="#334155"),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_heat_rep, width="stretch", theme=None, config=PLOTLY_CONFIG)

st.write("")
with panel():
    section_header("Relationship", "Sites reporting vs. compliance rate, by district", "🔗")
    scatter_df = rep.groupby(["District", "Province"], as_index=False).agg(
        Compliance_Rate_Pct=("Compliance_Rate_Pct", "mean"),
        Sites=("Reporting_Sites_Total", "sum"),
    )
    fig_scatter = px.scatter(
        scatter_df, x="Sites", y="Compliance_Rate_Pct", color="Province", size="Sites",
        color_discrete_map=PROVINCE_COLORS, hover_name="District",
    )
    fig_scatter.add_hline(y=70, line_dash="dot", line_color="#94A3B8")
    fig_scatter.update_layout(
        height=360, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="Total reporting sites", yaxis_title="Avg compliance %",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=12, color="#334155"),
    )
    st.plotly_chart(fig_scatter, width="stretch", theme=None, config=PLOTLY_CONFIG)
