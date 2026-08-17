import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from utils.data_loader import load_core, filtered
from utils.theme import inject_base_css, hero, kpi_card, section_header, status_badge, panel, PROVINCE_COLORS, PLOTLY_CONFIG, pct_color
from utils.filters import sidebar_filters, empty_state
from utils.anomaly import weekly_series, add_control_limits, add_ewma, epi_week_baseline

inject_base_css()
from utils.theme import top_header
top_header()

core = load_core()
f = sidebar_filters(core)
df = filtered(core, f["provinces"], f["diseases"], f["categories"], f["date_range"])

if empty_state(df):
    st.stop()

hero("Outbreak alerts", "statistical anomaly detection", chips={"Method": "Shewhart + EWMA + Endemic channel"})

with panel():
    section_header("Detection sensitivity", "How strict should the alert system be?", "⚙️")
    c1, c2 = st.columns(2)
    window = c1.slider("Compare each week against the past how many weeks?", 4, 16, 8)
    n_std = c2.slider("How far from normal counts as unusual?", 1.5, 3.5, 2.0, 0.25)
    st.caption("A smaller window reacts faster to recent changes; a lower sensitivity number flags more weeks as unusual.")

st.write("")
diseases_for_alert = df.groupby("Clean Disease")["Value"].sum().nlargest(6).index.tolist()

flagged_all = []
per_disease_counts = {}
total_weeks_observed = 0
for disease in diseases_for_alert:
    d_df = df[df["Clean Disease"] == disease]
    ts = weekly_series(d_df)
    ts = add_control_limits(ts, window=window, n_std=n_std)
    anomalies = ts[ts["is_anomaly"]].assign(Disease=disease)
    flagged_all.append(anomalies[["Date", "Value", "rolling_mean", "upper", "Disease"]])
    per_disease_counts[disease] = len(anomalies)
    total_weeks_observed += len(ts)

flagged_table = pd.concat(flagged_all).sort_values("Date", ascending=False) if flagged_all else pd.DataFrame(
    columns=["Date", "Value", "rolling_mean", "upper", "Disease"]
)
total_anomalies = len(flagged_table)
pct_weeks_flagged = (total_anomalies / total_weeks_observed * 100) if total_weeks_observed else 0
most_anomalous = max(per_disease_counts, key=per_disease_counts.get) if per_disease_counts else "—"

# ---------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------
section_header("Snapshot", "Outbreak signal summary", "🚨")
k1, k2, k3, k4 = st.columns(4)
_ob_spark = df.groupby("Date", as_index=False)["Value"].sum().tail(12)["Value"].tolist()
kpi_card(
    k1, "WEEKS FLAGGED", f"{pct_weeks_flagged:.0f}%", pct_color(pct_weeks_flagged, good_high=False),
    icon="alert-triangle", spark_values=_ob_spark, concern=total_anomalies > 0,
    subtitle=f"{total_anomalies:,} of {total_weeks_observed:,} weeks",
    value_color=pct_color(pct_weeks_flagged, good_high=False),
)
kpi_card(k2, "MOST ANOMALOUS DISEASE", most_anomalous, "#F59E0B", icon="flame", spark_values=_ob_spark)
kpi_card(k3, "DISEASES MONITORED", str(len(diseases_for_alert)), "#2563EB", icon="dna", spark_values=_ob_spark)
kpi_card(k4, "SENSITIVITY SETTING", f"{window}-week window", "#10B981", icon="settings", spark_values=_ob_spark)

# ---------------------------------------------------------------------
# Endemic channel — WHO-style calendar-week baseline & alert thresholds.
# Unlike the rolling-window control chart above (which compares each week
# to the *recent* weeks before it), this compares each week only to the
# *same calendar week* in prior years — the standard epidemic-channel
# method used in real surveillance bulletins to separate "unusual for
# the season" from "just the normal seasonal peak."
# ---------------------------------------------------------------------
st.write("")
with st.expander("🔬 Advanced: seasonal baseline comparison (optional, for epidemiologists)", expanded=False):
    st.caption(
        "This compares each week only to the *same calendar week* in prior years, instead of to the "
        "recent weeks before it — useful for telling apart 'unusual for this time of year' from "
        "'just the normal seasonal peak.'"
    )
    h1, h2 = st.columns([2.4, 1])
    with h1:
        section_header("Endemic channel", "Calendar-week baseline vs. this year", "🌡️")
    with h2:
        channel_diseases = df.groupby("Clean Disease")["Value"].sum().sort_values(ascending=False).index.tolist()
        channel_disease = st.selectbox(
            "Disease for endemic channel", channel_diseases, index=0 if channel_diseases else None,
            key="ob_channel_disease", label_visibility="collapsed",
        ) if channel_diseases else None

    if channel_disease:
        channel_df = df[df["Clean Disease"] == channel_disease]
        current_year, n_hist_years, baseline_df = epi_week_baseline(channel_df)

        if n_hist_years < 2:
            st.warning(
                f"Not enough historical years in the current filter to build a reliable baseline "
                f"for **{channel_disease}** (found {n_hist_years} prior year(s) — need at least 2). "
                "Widen the date range in the sidebar to include more history."
            )
        else:
            alert_weeks = int((baseline_df["status"] == "Alert").sum())
            epidemic_weeks = int((baseline_df["status"] == "Epidemic").sum())
            latest_row = baseline_df.dropna(subset=["hist_mean"]).sort_values("Week").tail(1)
            latest_status = latest_row["status"].iloc[0] if len(latest_row) else "No baseline"
            badge_kind = {"Epidemic": "alert", "Alert": "warn", "Normal": "live"}.get(latest_status, "live")

            b1, b2 = st.columns([3, 1])
            with b1:
                status_badge(f"Week {int(latest_row['Week'].iloc[0])}, {current_year} status: {latest_status}" if len(latest_row) else "No current-year data", badge_kind)
            with b2:
                st.caption(f"Baseline built from {n_hist_years} prior year(s)")

            fig_channel = go.Figure()
            fig_channel.add_trace(go.Scatter(
                x=baseline_df["Week"], y=baseline_df["hist_mean"], mode="lines", name="Historical average",
                line=dict(color="#94A3B8", width=1.6, dash="dash"),
            ))
            fig_channel.add_trace(go.Scatter(
                x=baseline_df["Week"], y=baseline_df["alert_threshold"], mode="lines", name="Alert threshold",
                line=dict(color="#F59E0B", width=1.6, dash="dot"),
            ))
            fig_channel.add_trace(go.Scatter(
                x=baseline_df["Week"], y=baseline_df["epidemic_threshold"], mode="lines", name="Epidemic threshold",
                line=dict(color="#EF4444", width=1.6, dash="dot"),
            ))
            status_colors = {"Normal": "#10B981", "Alert": "#F59E0B", "Epidemic": "#EF4444", "No baseline": "#94A3B8"}
            fig_channel.add_trace(go.Scatter(
                x=baseline_df["Week"], y=baseline_df["Actual"], mode="lines+markers",
                name=f"{current_year} actual",
                line=dict(color="#2563EB", width=2.4),
                marker=dict(size=8, color=[status_colors.get(s, "#2563EB") for s in baseline_df["status"]]),
            ))
            # The line above carries its own legend entry, but its marker dots are
            # also individually color-coded by status — that color coding has no
            # legend key of its own, so add invisible marker traces for it.
            statuses_in_view = [s for s in ["Normal", "Alert", "Epidemic"] if (baseline_df["status"] == s).any()]
            for s in statuses_in_view:
                fig_channel.add_trace(go.Scatter(
                    x=[None], y=[None], mode="markers", name=f"Week status: {s}",
                    marker=dict(color=status_colors[s], size=9),
                ))
            fig_channel.update_layout(
                height=420, margin=dict(l=10, r=10, t=58, b=10), xaxis_title="Epidemiological week", yaxis_title="Cases",
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(size=10.5), bgcolor="rgba(0,0,0,0)",
                ),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                hovermode="x unified", font=dict(family="Inter, sans-serif", size=12, color="#334155"),
            )
            st.plotly_chart(fig_channel, width="stretch", theme=None, config=PLOTLY_CONFIG)
            st.caption(
                f"**{alert_weeks}** week(s) in {current_year} crossed the alert threshold and **{epidemic_weeks}** "
                f"crossed the epidemic threshold for **{channel_disease}**, compared to its own {n_hist_years}-year "
                "history for this same calendar week."
            )

            flagged_channel = baseline_df[baseline_df["status"].isin(["Alert", "Epidemic"])].copy()
            if len(flagged_channel):
                if st.checkbox(f"Show flagged weeks for {channel_disease} ({len(flagged_channel)})", key="ob_channel_flagged_toggle"):
                    show_cols = flagged_channel[["Week", "Actual", "hist_mean", "alert_threshold", "epidemic_threshold", "status"]].round(1)
                    st.dataframe(show_cols, width="stretch", hide_index=True)
    else:
        st.write("No diseases available in the current filter.")

st.write("")
tabs = st.tabs(diseases_for_alert if diseases_for_alert else ["No data"])

for tab, disease in zip(tabs, diseases_for_alert):
    with tab:
        d_df = df[df["Clean Disease"] == disease]
        ts = weekly_series(d_df)
        ts = add_control_limits(ts, window=window, n_std=n_std)
        ts = add_ewma(ts)

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ts["Date"], y=ts["upper"], line=dict(width=0), hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(
            x=ts["Date"], y=ts["lower"], line=dict(width=0), fill="tonexty",
            fillcolor="rgba(236,72,153,0.10)", name="Control band", hoverinfo="skip"
        ))
        fig.add_trace(go.Scatter(x=ts["Date"], y=ts["Value"], mode="lines", name="Cases", line=dict(color="#EC4899", width=2.2)))
        anomalies = ts[ts["is_anomaly"]]
        fig.add_trace(go.Scatter(
            x=anomalies["Date"], y=anomalies["Value"], mode="markers", name="Anomaly",
            marker=dict(color="#EF4444", size=10, line=dict(color="white", width=1))
        ))
        fig.update_layout(
            height=360, margin=dict(l=10, r=10, t=48, b=10),
            xaxis_title="", yaxis_title="Cases",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                font=dict(size=11), bgcolor="rgba(0,0,0,0)",
            ),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            hovermode="x unified", font=dict(family="Inter, sans-serif", size=12, color="#334155"),
        )

        badge_kind = "alert" if len(anomalies) > 0 else "live"
        status_badge(f"{len(anomalies)} anomalies flagged", badge_kind)
        st.plotly_chart(fig, width="stretch", theme=None, config=PLOTLY_CONFIG)

st.write("")
col1, col2 = st.columns(2)
with col1:
    with panel():
        section_header("Comparison", "Anomalies flagged per disease", "📊")
        counts_df = pd.DataFrame(
            {"Disease": list(per_disease_counts.keys()), "Anomalies": list(per_disease_counts.values())}
        ).sort_values("Anomalies", ascending=True)
        fig_counts = px.bar(
            counts_df, x="Anomalies", y="Disease", orientation="h",
            color="Anomalies", color_continuous_scale=["#FEF6E7", "#EF4444"],
        )
        fig_counts.update_layout(
            height=300, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="", coloraxis_showscale=False,
            font=dict(family="Inter, sans-serif", size=12, color="#334155"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_counts, width="stretch", theme=None, config=PLOTLY_CONFIG)

with col2:
    with panel():
        section_header("Severity", "How far above the control band", "📈")
        if len(flagged_table):
            sev = flagged_table.copy()
            sev["Severity %"] = ((sev["Value"] - sev["upper"]) / sev["upper"] * 100).clip(lower=0)
            fig_hist = px.histogram(sev, x="Severity %", nbins=12, color_discrete_sequence=["#EF4444"])
            fig_hist.update_layout(
                height=300, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="Weeks",
                font=dict(family="Inter, sans-serif", size=12, color="#334155"),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_hist, width="stretch", theme=None, config=PLOTLY_CONFIG)
        else:
            st.write("No anomalies to summarize under current settings.")

st.write("")
with panel():
    section_header("Where", "Province contribution during flagged weeks", "📍")
    if len(flagged_table):
        flagged_keys = flagged_table[["Date", "Disease"]].drop_duplicates()
        joined = df.merge(
            flagged_keys, left_on=["Date", "Clean Disease"], right_on=["Date", "Disease"], how="inner"
        )
        by_prov_flagged = joined.groupby("Province", as_index=False)["Value"].sum().sort_values("Value", ascending=False)
        fig_prov = px.bar(
            by_prov_flagged, x="Province", y="Value", color="Province", color_discrete_map=PROVINCE_COLORS,
        )
        fig_prov.update_layout(
            height=300, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="", yaxis_title="Cases in flagged weeks",
            showlegend=False, font=dict(family="Inter, sans-serif", size=12, color="#334155"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_prov, width="stretch", theme=None, config=PLOTLY_CONFIG)
    else:
        st.write("No anomalies to break down under current settings.")

st.write("")
with panel():
    section_header("Audit log", "All flagged weeks across selected diseases", "🧾")
    if len(flagged_table):
        display_table = flagged_table.rename(columns={"rolling_mean": "Expected (rolling avg)", "upper": "Control limit"})
        display_table["Date"] = display_table["Date"].dt.date
        st.dataframe(display_table, width="stretch", hide_index=True)
        st.download_button(
            "Download flagged weeks as CSV",
            display_table.to_csv(index=False).encode("utf-8"),
            "outbreak_alerts.csv", "text/csv",
        )
    else:
        st.write("No diseases in current filter.")

st.write("")
col3, col4 = st.columns(2)
with col3:
    with panel():
        section_header("Timeline", "Every flagged week, plotted by date", "🕒")
        if len(flagged_table):
            fig_tl = px.scatter(
                flagged_table, x="Date", y="Disease", size="Value", color="Disease",
                size_max=22,
            )
            fig_tl.update_layout(
                height=320, margin=dict(l=10, r=10, t=10, b=10), showlegend=False, yaxis_title="",
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, sans-serif", size=12, color="#334155"),
            )
            st.plotly_chart(fig_tl, width="stretch", theme=None, config=PLOTLY_CONFIG)
        else:
            st.write("No anomalies to plot under current settings.")

with col4:
    with panel():
        section_header("Frequency", "Flagged weeks by calendar month", "📆")
        if len(flagged_table):
            ft = flagged_table.copy()
            ft["Month"] = pd.to_datetime(ft["Date"]).dt.strftime("%b")
            month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            by_flag_month = ft.groupby("Month", as_index=False).size().rename(columns={"size": "Flagged weeks"})
            by_flag_month["Month"] = pd.Categorical(by_flag_month["Month"], categories=month_order, ordered=True)
            by_flag_month = by_flag_month.sort_values("Month")
            fig_fm = px.bar(by_flag_month, x="Month", y="Flagged weeks", color_discrete_sequence=["#EF4444"])
            fig_fm.update_layout(
                height=320, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="",
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, sans-serif", size=12, color="#334155"),
            )
            st.plotly_chart(fig_fm, width="stretch", theme=None, config=PLOTLY_CONFIG)
        else:
            st.write("No anomalies to summarize under current settings.")
