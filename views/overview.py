import datetime as dt

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from utils.data_loader import load_core, filtered, kpi_numbers, previous_period_df, pct_delta, cases_per_100k
from utils.theme import (
    inject_base_css, hero, kpi_card, section_header, status_badge,
    panel, insight_panel, chart_or_table, narrative_line, PROVINCE_COLORS, CATEGORY_COLORS,
)
from utils.filters import sidebar_filters, empty_state, active_filters_bar
from utils.anomaly import add_control_limits, granular_series, GRANULARITY_WINDOW
from utils.chips import disease_chip_group

inject_base_css()
from utils.theme import top_header
top_header()

try:
    core = load_core()
except FileNotFoundError:
    st.error(
        "Data files not found. Run `python prepare_data.py` first to generate "
        "`data/core.parquet` from the source Excel file."
    )
    st.stop()

f = sidebar_filters(core)
df = filtered(core, f["provinces"], f["diseases"], f["categories"], f["date_range"])

hero(
    "National disease trends",
    f"{f['date_range'][0].year}–{f['date_range'][1].year}",
    chips={
        "Records": f"{len(df):,}",
        "Diseases": df["Clean Disease"].nunique(),
        "Provinces": df["Province"].nunique(),
        "Source": "NIH IDSR",
    },
    updated=f"Data current · {dt.datetime.now().strftime('%b %d, %H:%M')}",
)

if empty_state(df):
    st.stop()

# ---------------------------------------------------------------------
# Active-filters strip — replaces the old "Filter by Province" quick row.
# That row duplicated the sidebar province chips with no indication the
# two were linked; this instead summarizes every active filter (sidebar
# chips, date range, and disease-comparison count) in one place, with
# each tag removable inline. Computed here (rather than down by the
# comparison section) so the disease-count tag reflects the current
# selection even though the picker itself renders later, in the sidebar.
# ---------------------------------------------------------------------
ranked_diseases = df.groupby("Clean Disease")["Value"].sum().sort_values(ascending=False)
ranked_names = ranked_diseases.index.tolist()
_default_disease_n = 6
_current_disease_selection = st.session_state.get("ov_disease_chip_selection", ranked_names[:_default_disease_n])


def _reset_diseases():
    st.session_state["ov_disease_chip_selection"] = ranked_names[:_default_disease_n]


active_filters_bar(
    core, f,
    extra_tags=[(f"🧬 {len(_current_disease_selection)} diseases compared", _reset_diseases)],
)

# ---------------------------------------------------------------------
# KPI row — each card now carries a vs-prior-period % delta
# ---------------------------------------------------------------------
prev_df = previous_period_df(core, f["provinces"], f["diseases"], f["categories"], f["date_range"])
k = kpi_numbers(df)
kp = kpi_numbers(prev_df) if len(prev_df) else {"total_cases": 0, "diseases": 0, "districts": 0, "weeks": 0}

top_bar_l, top_bar_r = st.columns([3, 1])
with top_bar_l:
    section_header("Overview", "Disease burden at a glance", "📈")
with top_bar_r:
    status_badge("Data current", "live")

d1, dir1 = pct_delta(k["total_cases"], kp["total_cases"])
d2, dir2 = pct_delta(k["diseases"], kp["diseases"])
d3, dir3 = pct_delta(k["districts"], kp["districts"])
d4, dir4 = pct_delta(k["weeks"], kp["weeks"])

c1, c2, c3, c4 = st.columns(4)
_spark_weekly = granular_series(df, "Weekly").tail(12)
_spark_vals = _spark_weekly["Value"].tolist() if len(_spark_weekly) else []
kpi_card(c1, "TOTAL CASES", f"{k['total_cases']:,}", "#2563EB", icon="heart-pulse", delta=d1, delta_dir=dir1, spark_values=_spark_vals)
kpi_card(c2, "DISEASES TRACKED", str(k["diseases"]), "#10B981", icon="dna", delta=d2, delta_dir=dir2, spark_values=_spark_vals)
kpi_card(c3, "DISTRICTS REPORTING", str(k["districts"]), "#F59E0B", icon="map-pin", delta=d3, delta_dir=dir3, spark_values=_spark_vals)
kpi_card(c4, "WEEKS COVERED", str(k["weeks"]), "#EF4444", icon="calendar", delta=d4, delta_dir=dir4, spark_values=_spark_vals)

# ---------------------------------------------------------------------
# AI-style insight panel — computed straight from the filtered dataframe,
# no external calls, so it's instant and never contradicts the charts.
# ---------------------------------------------------------------------
top_disease_row = df.groupby("Clean Disease")["Value"].sum().sort_values(ascending=False)
top_province_row = df.groupby("Province")["Value"].sum().sort_values(ascending=False)
top_disease_name = top_disease_row.index[0] if len(top_disease_row) else "—"
top_disease_share = (top_disease_row.iloc[0] / k["total_cases"] * 100) if k["total_cases"] else 0
top_prov_name = top_province_row.index[0] if len(top_province_row) else "—"
top_prov_share = (top_province_row.iloc[0] / k["total_cases"] * 100) if k["total_cases"] else 0
top_prov_rate = cases_per_100k(top_province_row.iloc[0], top_prov_name) if len(top_province_row) else None

_weekly_for_insight = granular_series(df, "Weekly")
_weekly_for_insight = add_control_limits(_weekly_for_insight, window=8, n_std=2.0)
anomaly_count = int(_weekly_for_insight["is_anomaly"].sum())

trend_note = "Not enough history to assess a trend."
if len(_weekly_for_insight) >= 8:
    recent = _weekly_for_insight["Value"].tail(4).mean()
    prior = _weekly_for_insight["Value"].tail(8).head(4).mean()
    if prior:
        move = (recent - prior) / prior * 100
        if move > 5:
            trend_note = f"Case volume is <b>trending up {move:.0f}%</b> over the last 4 weeks vs. the 4 before that."
        elif move < -5:
            trend_note = f"Case volume is <b>trending down {abs(move):.0f}%</b> over the last 4 weeks vs. the 4 before that."
        else:
            trend_note = "Case volume has been <b>broadly stable</b> over the last 8 weeks."

insight_panel(
    "Key takeaways for this selection",
    [
        ("🔝", f"<b>{top_disease_name}</b> is the leading disease, accounting for <b>{top_disease_share:.0f}%</b> of all cases in view."),
        ("📍", f"<b>{top_prov_name}</b> carries the largest share of the case burden at <b>{top_prov_share:.0f}%</b>"
               + (f" — that's about <b>{top_prov_rate:.0f} cases per 100,000 people</b>, adjusting for its population." if top_prov_rate else " of all cases.")),
        ("📈", trend_note),
        ("⚠️", f"<b>{anomaly_count}</b> week(s) breached the outbreak control band — see Outbreak Alerts for detail." if anomaly_count else "No weeks currently breach the outbreak control band."),
    ],
)

st.write("")
col1, col2 = st.columns([1.4, 1])

with col1:
    with panel():
        hcol1, hcol2 = st.columns([2, 1])
        with hcol1:
            section_header("Anomaly detection", "Case trend with outbreak flags", "📊")
            narrative_line(trend_note)
        with hcol2:
            try:
                granularity = st.segmented_control(
                    "Granularity", options=["Weekly", "Monthly", "Yearly"],
                    default="Weekly", key="ov_granularity", label_visibility="collapsed",
                )
            except AttributeError:
                granularity = st.radio(
                    "Granularity", options=["Weekly", "Monthly", "Yearly"],
                    index=0, horizontal=True, key="ov_granularity", label_visibility="collapsed",
                )
        granularity = granularity or "Weekly"

        ts = granular_series(df, granularity)
        ts = add_control_limits(ts, window=GRANULARITY_WINDOW[granularity], n_std=2.0)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=ts["Date"], y=ts["upper"], line=dict(width=0), showlegend=False, hoverinfo="skip"
        ))
        fig.add_trace(go.Scatter(
            x=ts["Date"], y=ts["lower"], line=dict(width=0), fill="tonexty",
            fillcolor="rgba(59,130,246,0.10)", name="Normal range", hoverinfo="skip"
        ))
        fig.add_trace(go.Scatter(
            x=ts["Date"], y=ts["Value"], mode="lines", name=f"{granularity} cases",
            line=dict(color="#2563EB", width=2.4)
        ))
        anomalies = ts[ts["is_anomaly"]]
        fig.add_trace(go.Scatter(
            x=anomalies["Date"], y=anomalies["Value"], mode="markers", name="Flagged as unusual",
            marker=dict(color="#EF4444", size=9, symbol="circle", line=dict(color="white", width=1))
        ))
        fig.update_layout(
            margin=dict(l=10, r=10, t=48, b=10),
            xaxis_title="", yaxis_title="Cases",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                font=dict(size=11), bgcolor="rgba(0,0,0,0)",
            ),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            hovermode="x unified", font=dict(family="Inter, sans-serif", size=12, color="#334155"),
        )
        chart_or_table(
            fig, ts[["Date", "Value", "is_anomaly"]].rename(columns={"is_anomaly": "Flagged"}),
            key="ov_anomaly",
            caption=(
                f"{len(anomalies)} {granularity.lower()} period(s) flagged where cases exceeded the rolling mean "
                "+ 2 standard deviations — a Shewhart-style control limit, the same logic "
                "used in real outbreak surveillance. See the Outbreak Alerts page for full detail."
            ),
        )

with col2:
    with panel():
        section_header("Composition", "Disease burden by category", "🗂️")
        cat = df.groupby("Category", as_index=False)["Value"].sum().sort_values("Value", ascending=True)
        cat["Share"] = cat["Value"] / cat["Value"].sum() * 100
        # Top disease within each category — real detail computed from the
        # same filtered dataframe, shown on hover so "which color is which
        # category" AND "what's actually driving that category" are both
        # answered without a separate lookup.
        top_disease_per_cat = (
            df.groupby(["Category", "Clean Disease"])["Value"].sum()
            .sort_values(ascending=False)
            .reset_index()
            .drop_duplicates("Category")
            .set_index("Category")["Clean Disease"]
        )
        cat["Top disease"] = cat["Category"].map(top_disease_per_cat).fillna("—")

        # Explicit color legend — bars are already grouped by category
        # name on the y-axis, but a colored-dot key (same pattern as the
        # hero header) makes color→category unambiguous at a glance too.
        legend_html = "".join(
            f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:14px;font-size:11.5px;color:var(--ink-700);">'
            f'<span style="width:9px;height:9px;border-radius:50%;background:{CATEGORY_COLORS.get(c, "#94A3B8")};display:inline-block;"></span>{c}</span>'
            for c in cat.sort_values("Value", ascending=False)["Category"]
        )
        st.markdown(f'<div style="margin:2px 0 10px 0;">{legend_html}</div>', unsafe_allow_html=True)

        # Horizontal bar instead of a treemap: with 6 categories and
        # skewed values (a few large, several small), a treemap squeezes
        # the small ones into slivers too thin to read a label on — every
        # category gets equal legibility on a bar chart regardless of size.
        fig2 = px.bar(
            cat, x="Value", y="Category", orientation="h", color="Category",
            color_discrete_map=CATEGORY_COLORS, text="Share",
            custom_data=["Top disease"],
        )
        fig2.update_traces(
            texttemplate="%{text:.0f}%", textposition="outside", cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>Cases: %{x:,.0f}<br>Top disease: %{customdata[0]}<extra></extra>",
        )
        fig2.update_layout(
            height=300, margin=dict(l=4, r=50, t=10, b=10), showlegend=False,
            xaxis_title="Cases", yaxis_title="",
            font=dict(family="Inter, sans-serif", size=12, color="#334155"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        chart_or_table(fig2, cat[["Category", "Value", "Share", "Top disease"]].rename(columns={"Value": "Cases", "Share": "Share %"}), key="ov_composition")

# ---------------------------------------------------------------------
# Disease comparison — search, quick Top-N, and the disease multiselect
# now live in the sidebar (grouped with the other filters) so the main
# panel is just the chart; only the scale toggle stays up top since it's
# a chart-display option, not a filter. `ranked_names` was already
# computed above, for the active-filters strip.
# ---------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        "<hr style='margin:18px 0 14px;border-color:var(--border-soft);'>"
        "<p style='font-size:11px;letter-spacing:0.08em;text-transform:uppercase;"
        "color:var(--ink-500,#64748B);font-weight:700;margin:2px 0 10px 0;'>Compare diseases</p>",
        unsafe_allow_html=True,
    )
    # A real dropdown (popover) instead of an always-open block — the search
    # box and chip list only appear once you click the button, so the
    # sidebar stays short when you're not actively editing the comparison.
    # The button label always shows the current count so you don't have to
    # open it just to see how many are selected.
    _prior_selection = st.session_state.get("ov_disease_chip_selection", ranked_names[:6])
    _popover_label = f"🧬 {len(_prior_selection)} disease(s) selected  ▾"
    with st.popover(_popover_label, width="stretch"):
        search_term = st.text_input(
            "Search diseases", placeholder="🔍 Search (e.g. Malaria, TB, Dengue)…",
            key="ov_disease_search",
        )
        matches = [d for d in ranked_names if search_term.lower() in d.lower()] if search_term else ranked_names
        selected_diseases = disease_chip_group(
            matches, "ov_disease_chip_selection", ranked_names, default_n=6,
        )
    st.caption(f"{len(selected_diseases)} of {len(ranked_names)} diseases selected for the chart below.")

st.write("")
with panel():
    head_l, head_r = st.columns([3, 1])
    with head_l:
        section_header("Comparison", "Case volume by province, selected diseases", "📶")
    with head_r:
        scale_mode = st.selectbox(
            "Scale", options=["Linear", "Log"], key="ov_scale_mode", label_visibility="collapsed",
        )

    if selected_diseases:
        grp = (
            df[df["Clean Disease"].isin(selected_diseases)]
            .groupby(["Clean Disease", "Province"], as_index=False)["Value"].sum()
        )
        # Ranked so the biggest disease sits at the top of a horizontal bar chart.
        order = [d for d in ranked_names if d in selected_diseases]

        # Horizontal bars: with many/long disease names, a vertical chart forces
        # diagonally-rotated x-axis labels that overlap and become unreadable.
        # Putting disease names on the y-axis keeps every label horizontal and
        # fully legible regardless of how many diseases are selected.
        fig3 = px.bar(
            grp, y="Clean Disease", x="Value", color="Province", barmode="group",
            orientation="h",
            color_discrete_map=PROVINCE_COLORS,
            category_orders={"Clean Disease": list(reversed(order))},
        )
        fig3.update_layout(
            margin=dict(l=10, r=10, t=48, b=10), xaxis_title="Cases", yaxis_title="",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                title_text="Province", font=dict(size=11), bgcolor="rgba(0,0,0,0)",
            ),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", size=12, color="#334155"),
        )
        if scale_mode == "Log":
            # Sindh's case volume can be 10-20x the smaller provinces, which
            # flattens Balochistan/KP/Punjab bars to near-invisible slivers on
            # a linear scale. Log scale keeps every province's bar readable.
            fig3.update_xaxes(type="log")
        fig3.update_traces(marker_line_width=0)

        # Chart grows with the number of diseases selected so bars never get
        # squished together, and shrinks back down when only a few are picked.
        chart_height = max(300, 46 * len(selected_diseases) + 60)
        chart_or_table(fig3, grp, key="ov_comparison", height=chart_height, table_height=min(chart_height, 420))
    else:
        st.info("No diseases match that search — try a different term or clear the search box in the sidebar.")

# ---------------------------------------------------------------------
# Overview stays high-level on purpose: total cases, category mix, trend,
# and a diseases-vs-provinces comparison above. Province distribution,
# reporting-rate efficiency, per-100k rates, weekly spread, and category
# momentum all have dedicated, deeper pages — duplicating them here just
# made this page long without adding anything new to read.
# ---------------------------------------------------------------------
st.write("")
with panel():
    section_header("Detail", "Top 10 diseases — raw numbers", "🧾")
    detail_table = top_disease_row.head(10).reset_index()
    detail_table.columns = ["Disease", "Cases"]
    detail_table["Share of total"] = (detail_table["Cases"] / k["total_cases"] * 100).round(1).astype(str) + "%"
    st.dataframe(detail_table, width="stretch", hide_index=True)

st.info(
    "Use the pages in the left sidebar for the deeper views: **Geography** (map), "
    "**Trends** (seasonality heatmap), **Outbreak Alerts** (anomaly detail + table), "
    "**Forecast** (next 4 periods), **Executive Analytics** (advanced statistics for leadership), "
    "and **Reporting Quality** (data trust)."
)
