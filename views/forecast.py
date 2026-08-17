import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from utils.data_loader import load_core, filtered
from utils.theme import inject_base_css, hero, kpi_card, section_header, panel, PROVINCE_COLORS, PLOTLY_CONFIG, pct_color
from utils.filters import sidebar_filters, empty_state
from utils.anomaly import weekly_series, naive_forecast

inject_base_css()
from utils.theme import top_header
top_header()

core = load_core()
f = sidebar_filters(core)
df = filtered(core, f["provinces"], f["diseases"], f["categories"], f["date_range"])

if empty_state(df):
    st.stop()

hero("Forecast", "next 4 weeks, top diseases", chips={"Model": "Trend-blended naive"})

section_header("Projection method", "How this forecast works", "🔮")
st.caption(
    "This is a lightweight trend + recent-average projection, not a full ARIMA/Prophet model — "
    "good enough to flag direction (rising / falling) without extra dependencies. Swap in "
    "Prophet or statsmodels SARIMAX here for production-grade forecasting."
)

# ---------------------------------------------------------------------
# Compute a forecast for every disease in view (not just the top 4) so
# the KPI row and ranking chart reflect the full picture.
# ---------------------------------------------------------------------
all_diseases = df.groupby("Clean Disease")["Value"].sum().sort_values(ascending=False).index.tolist()

forecast_rows = []
per_disease_ts = {}
per_disease_fc = {}
for disease in all_diseases:
    ts = weekly_series(df[df["Clean Disease"] == disease])
    if len(ts) < 4:
        continue
    fc = naive_forecast(ts, periods=4)
    per_disease_ts[disease] = ts
    per_disease_fc[disease] = fc
    last_actual = ts["Value"].iloc[-1]
    last_forecast = fc["Value"].iloc[-1]
    pct_change = ((last_forecast - last_actual) / last_actual * 100) if last_actual else 0
    forecast_rows.append({
        "Disease": disease, "Latest actual": last_actual,
        "4-week projection": last_forecast, "% change": pct_change,
    })

forecast_df = pd.DataFrame(forecast_rows)
rising = int((forecast_df["% change"] > 5).sum()) if len(forecast_df) else 0
falling = int((forecast_df["% change"] < -5).sum()) if len(forecast_df) else 0
combined_projection = int(forecast_df["4-week projection"].sum()) if len(forecast_df) else 0

# ---------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------
section_header("Snapshot", "Forecast summary", "📦")
k1, k2, k3, k4 = st.columns(4)
_fc_spark = df.groupby("Date", as_index=False)["Value"].sum().tail(12)["Value"].tolist()
total_forecasted = len(forecast_df) if len(forecast_df) else 0
rising_pct = (rising / total_forecasted * 100) if total_forecasted else 0
falling_pct = (falling / total_forecasted * 100) if total_forecasted else 0
kpi_card(k1, "DISEASES FORECASTED", str(len(forecast_df)), "#2563EB", icon="dna", spark_values=_fc_spark)
kpi_card(
    k2, "RISING (>5%)", f"{rising_pct:.0f}%", pct_color(rising_pct, good_high=False),
    icon="trending-up", spark_values=_fc_spark, subtitle=f"{rising} of {total_forecasted} diseases",
    value_color=pct_color(rising_pct, good_high=False),
)
kpi_card(
    k3, "FALLING (<-5%)", f"{falling_pct:.0f}%", "#10B981",
    icon="trending-down", spark_values=_fc_spark, subtitle=f"{falling} of {total_forecasted} diseases",
)
kpi_card(k4, "PROJECTED NEXT-PERIOD TOTAL", f"{combined_projection:,}", "#F59E0B", icon="sparkles", spark_values=_fc_spark)

st.write("")
top_diseases = all_diseases[:4]
cols = st.columns(2)

for i, disease in enumerate(top_diseases):
    ts = per_disease_ts.get(disease)
    fc = per_disease_fc.get(disease)
    if ts is None or fc is None:
        continue

    last_actual = ts["Value"].iloc[-1]
    last_forecast = fc["Value"].iloc[-1]
    pct_change = ((last_forecast - last_actual) / last_actual * 100) if last_actual else 0
    trend_color = "#EF4444" if pct_change > 5 else ("#10B981" if pct_change < -5 else "#F59E0B")
    trend_arrow = "▲" if pct_change > 0 else ("▼" if pct_change < 0 else "▬")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ts["Date"].tail(20), y=ts["Value"].tail(20), mode="lines", name="Actual",
        line=dict(color="#2563EB", width=2.2),
    ))
    fig.add_trace(go.Scatter(
        x=fc["Date"], y=fc["Value"], mode="lines+markers", name="Forecast",
        line=dict(color="#F59E0B", width=2.2, dash="dash"), marker=dict(size=6),
    ))
    fig.update_layout(
        height=270, margin=dict(l=10, r=10, t=36, b=10),
        xaxis_title="", yaxis_title="Cases",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1,
            font=dict(size=10), bgcolor="rgba(0,0,0,0)",
        ),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified", font=dict(family="Inter, sans-serif", size=12, color="#334155"),
    )

    with cols[i % 2]:
        with panel():
            h1, h2 = st.columns([3, 1])
            h1.markdown(f"**{disease}**")
            h2.markdown(
                f"<span style='color:{trend_color};font-size:13px;font-weight:700;float:right;"
                f"background:{trend_color}18;padding:2px 8px;border-radius:999px;'>"
                f"{trend_arrow} {abs(pct_change):.0f}%</span>",
                unsafe_allow_html=True,
            )
            st.plotly_chart(fig, width="stretch", theme=None, config=PLOTLY_CONFIG)

st.write("")
with panel():
    section_header("Overview", "All top diseases: actual vs. 4-week projection", "🧮")
    if len(forecast_df):
        combined_rows = []
        for disease in all_diseases[:8]:
            ts = per_disease_ts.get(disease)
            fc = per_disease_fc.get(disease)
            if ts is None or fc is None:
                continue
            combined_rows.append(ts.tail(12).assign(Disease=disease, Series="Actual"))
            combined_rows.append(fc.assign(Disease=disease, Series="Forecast"))
        combined = pd.concat(combined_rows, ignore_index=True) if combined_rows else pd.DataFrame()
        if len(combined):
            fig_all = px.line(
                combined, x="Date", y="Value", color="Disease", line_dash="Series",
                facet_col="Disease", facet_col_wrap=4,
            )
            fig_all.update_yaxes(matches=None, showticklabels=True)
            fig_all.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1][:20]))
            fig_all.update_layout(
                height=420, margin=dict(l=10, r=10, t=30, b=10), showlegend=False,
                font=dict(family="Inter, sans-serif", size=11, color="#334155"),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_all, width="stretch", theme=None, config=PLOTLY_CONFIG)
            st.caption("Each panel title names the disease · solid line = actual, dashed line = 4-week forecast.")
    else:
        st.write("Not enough weekly history to build a combined view.")

st.write("")
with panel():
    section_header("Ranking", "Projected % change vs. latest actual, all diseases", "📶")
    if len(forecast_df):
        ranked = forecast_df.sort_values("% change")
        fig_rank = px.bar(
            ranked, x="% change", y="Disease", orientation="h",
            color="% change", color_continuous_scale=["#10B981", "#F59E0B", "#EF4444"],
        )
        fig_rank.update_layout(
            height=max(320, 24 * len(ranked)), margin=dict(l=10, r=10, t=10, b=10),
            yaxis_title="", coloraxis_showscale=False,
            font=dict(family="Inter, sans-serif", size=12, color="#334155"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_rank, width="stretch", theme=None, config=PLOTLY_CONFIG)
        st.dataframe(
            forecast_df.round(1).sort_values("% change", ascending=False),
            width="stretch", hide_index=True,
        )
    else:
        st.write("No diseases with enough history in the current filter.")

st.write("")
col5, col6 = st.columns(2)
with col5:
    with panel():
        section_header("By province", "Projected 4-week total, split by province", "📍")
        top_disease_for_split = all_diseases[0] if all_diseases else None
        if top_disease_for_split:
            prov_shares = df[df["Clean Disease"] == top_disease_for_split].groupby("Province", as_index=False)["Value"].sum()
            prov_shares["Value"] = prov_shares["Value"] / prov_shares["Value"].sum() * combined_projection if prov_shares["Value"].sum() else 0
            prov_shares = prov_shares.sort_values("Value", ascending=True)
            fig_ps = px.bar(
                prov_shares, x="Value", y="Province", orientation="h", color="Province",
                color_discrete_map=PROVINCE_COLORS, text="Value",
            )
            fig_ps.update_traces(texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
            fig_ps.update_layout(
                height=320, margin=dict(l=10, r=40, t=10, b=10), showlegend=False,
                xaxis_title="Projected cases", yaxis_title="",
                font=dict(family="Inter, sans-serif", size=12, color="#334155"),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_ps, width="stretch", theme=None, config=PLOTLY_CONFIG)
            st.caption(f"Illustrative province split of the projected total, based on {top_disease_for_split}'s current provincial mix.")
        else:
            st.write("No data available.")

with col6:
    with panel():
        section_header("Confidence", "Model agreement", "🎯")
        confidence = max(0, min(100, 100 - abs(rising - falling) * 3)) if len(forecast_df) else 0
        # Bullet chart instead of a full gauge — same "how are we doing"
        # message (value vs. qualitative zones) in a fraction of the
        # vertical space, so it doesn't need its own dominant panel.
        fig_gauge = go.Figure(go.Indicator(
            mode="number+gauge", value=confidence,
            number=dict(suffix="%", font=dict(size=28)),
            domain=dict(x=[0.1, 1], y=[0.3, 0.7]),
            gauge=dict(
                shape="bullet",
                axis=dict(range=[0, 100]),
                bar=dict(color="#2563EB", thickness=0.5),
                steps=[
                    dict(range=[0, 40], color="#FDECEC"),
                    dict(range=[40, 70], color="#FEF6E7"),
                    dict(range=[70, 100], color="#E7F8F1"),
                ],
                threshold=dict(line=dict(color="#101828", width=2), thickness=0.8, value=70),
            ),
        ))
        fig_gauge.update_layout(
            height=140, margin=dict(l=10, r=30, t=10, b=10),
            font=dict(family="Inter, sans-serif", size=12, color="#334155"),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_gauge, width="stretch", theme=None, config=PLOTLY_CONFIG)
        st.caption("Higher = the diseases in view mostly agree on direction (rising or falling together); lower = a mixed signal. Black line marks the 70% consistency threshold.")

st.write("")
col7, col8 = st.columns(2)
with col7:
    with panel():
        section_header("Cumulative", "Projected running total, next 4 weeks", "📊")
        if len(forecast_df):
            weekly_totals = None
            for disease in all_diseases:
                fc = per_disease_fc.get(disease)
                if fc is None:
                    continue
                fc_s = fc.set_index("Date")["Value"]
                weekly_totals = fc_s if weekly_totals is None else weekly_totals.add(fc_s, fill_value=0)
            if weekly_totals is not None:
                cum_fc = weekly_totals.cumsum().reset_index()
                cum_fc.columns = ["Date", "Cumulative projected cases"]
                fig_cumfc = px.area(cum_fc, x="Date", y="Cumulative projected cases", color_discrete_sequence=["#2563EB"])
                fig_cumfc.update_layout(
                    height=300, margin=dict(l=10, r=10, t=10, b=10),
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Inter, sans-serif", size=12, color="#334155"),
                )
                st.plotly_chart(fig_cumfc, width="stretch", theme=None, config=PLOTLY_CONFIG)
        else:
            st.write("No forecast data available.")

with col8:
    with panel():
        section_header("Distribution", "Spread of projected % change across diseases", "📦")
        if len(forecast_df):
            fig_dist = px.histogram(forecast_df, x="% change", nbins=14, color_discrete_sequence=["#7C3AED"])
            fig_dist.update_layout(
                height=300, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="Diseases",
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, sans-serif", size=12, color="#334155"),
            )
            st.plotly_chart(fig_dist, width="stretch", theme=None, config=PLOTLY_CONFIG)
        else:
            st.write("No forecast data available.")
