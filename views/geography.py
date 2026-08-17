import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from utils.data_loader import load_core, filtered, DISTRICT_COORDS, PROVINCE_POPULATION, cases_per_100k
from utils.theme import inject_base_css, hero, kpi_card, section_header, panel, PROVINCE_COLORS, CATEGORY_COLORS, PLOTLY_CONFIG, chart_or_table
from utils.filters import sidebar_filters, empty_state

inject_base_css()
from utils.theme import top_header
top_header()

core = load_core()
f = sidebar_filters(core)
df = filtered(core, f["provinces"], f["diseases"], f["categories"], f["date_range"])

if empty_state(df):
    st.stop()

hero("Geography", "where cases are concentrated", chips={"Districts mapped": len(DISTRICT_COORDS)})

by_district = df.groupby(["District", "Province"], as_index=False)["Value"].sum()
by_district["lat"] = by_district["District"].map(lambda d: DISTRICT_COORDS.get(d, (None, None))[0])
by_district["lon"] = by_district["District"].map(lambda d: DISTRICT_COORDS.get(d, (None, None))[1])
mapped = by_district.dropna(subset=["lat", "lon"])
unmapped_count = len(by_district) - len(mapped)

by_province = df.groupby("Province", as_index=False)["Value"].sum().sort_values("Value", ascending=False)
top_district_row = by_district.sort_values("Value", ascending=False).iloc[0] if len(by_district) else None

# ---------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------
section_header("Snapshot", "Geographic footprint at a glance", "🧭")
c1, c2, c3, c4 = st.columns(4)
_geo_spark = df.groupby("Date", as_index=False)["Value"].sum().tail(12)["Value"].tolist()
kpi_card(c1, "DISTRICTS REPORTING", str(df["District"].nunique()), "#2563EB", icon="map-pin", spark_values=_geo_spark)
kpi_card(c2, "TOP PROVINCE", by_province.iloc[0]["Province"] if len(by_province) else "—", "#10B981", icon="trophy", spark_values=_geo_spark)
top_district_prov_pct = None
if top_district_row is not None:
    _prov_total = by_district[by_district["Province"] == top_district_row["Province"]]["Value"].sum()
    top_district_prov_pct = (top_district_row["Value"] / _prov_total * 100) if _prov_total else None

kpi_card(
    c3, "TOP DISTRICT", top_district_row["District"] if top_district_row is not None else "—",
    "#F59E0B", icon="map-pin", spark_values=_geo_spark,
    subtitle=(f"{top_district_prov_pct:.0f}% of {top_district_row['Province']}'s cases" if top_district_prov_pct is not None else None),
)
kpi_card(c4, "DISTRICTS MAPPED", f"{len(mapped)} / {len(by_district)}", "#EF4444", icon="map", spark_values=_geo_spark)

st.write("")
with panel():
    section_header("Spatial view", "District case density", "🗺️")
    if len(mapped):
        fig = px.scatter_map(
            mapped, lat="lat", lon="lon", size="Value", color="Province",
            hover_name="District", size_max=45, zoom=4.4,
            center={"lat": 30.3753, "lon": 69.3451},
            color_discrete_map=PROVINCE_COLORS,
        )
        fig.update_layout(
            map_style="carto-positron", height=600, margin=dict(l=0, r=0, t=44, b=0),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0,
                title_text="Province", font=dict(size=11),
                bgcolor="rgba(255,255,255,0.85)",
            ),
            font=dict(family="Inter, sans-serif", size=12, color="#334155"),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, width="stretch", theme=None, config=PLOTLY_CONFIG)
    else:
        st.warning("No districts in the current filter selection match the mapped centroid list.")

    st.caption(
        f"Bubble size = total cases in the filtered period. Centroids are approximate district "
        f"coordinates covering the most frequently reported districts "
        f"({unmapped_count} smaller/less common districts not yet mapped — extend "
        f"`DISTRICT_COORDS` in `utils/data_loader.py` to add more, or swap in a full "
        f"Pakistan district GeoJSON for a true choropleth)."
    )

st.write("")
col1, col2 = st.columns([1, 1])
with col1:
    with panel():
        section_header("Ranking", "Top 10 districts by case volume", "🏆")
        top10 = by_district.sort_values("Value", ascending=False).head(10)
        fig2 = px.bar(
            top10.sort_values("Value"), x="Value", y="District", orientation="h", color="Province",
            color_discrete_map=PROVINCE_COLORS,
        )
        fig2.update_layout(
            height=440, margin=dict(l=10, r=10, t=48, b=10), yaxis_title="", xaxis_title="Cases",
            font=dict(family="Inter, sans-serif", size=12, color="#334155"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                title_text="Province", font=dict(size=11), bgcolor="rgba(0,0,0,0)",
            ),
        )
        fig2.update_traces(marker_line_width=0)
        st.plotly_chart(fig2, width="stretch", theme=None, config=PLOTLY_CONFIG)

with col2:
    with panel():
        h1, h2 = st.columns([2, 1.4])
        with h1:
            section_header("Share", "Case volume by province", "🥧")
        with h2:
            view_mode = st.radio(
                "View as", options=["Raw cases", "Per 100,000 people"], index=0, horizontal=True,
                key="geo_province_view_mode", label_visibility="collapsed",
            )
        if view_mode == "Per 100,000 people":
            rate_df = by_province.copy()
            rate_df["Rate"] = rate_df.apply(lambda r: cases_per_100k(r["Value"], r["Province"]), axis=1)
            rate_df = rate_df.dropna(subset=["Rate"])
            fig3 = px.bar(
                rate_df.sort_values("Rate"), x="Rate", y="Province", orientation="h",
                color="Province", color_discrete_map=PROVINCE_COLORS,
            )
            fig3.update_layout(
                height=400, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="Cases per 100,000 people", yaxis_title="",
                font=dict(family="Inter, sans-serif", size=12, color="#334155"),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
            )
            fig3.update_traces(marker_line_width=0)
            st.plotly_chart(fig3, width="stretch", theme=None, config=PLOTLY_CONFIG)
            st.caption(
                "Adjusted for population so a large province isn't automatically read as 'worse' than a small "
                "one. Uses 2023 census province populations (approximate) — see `PROVINCE_POPULATION` in "
                "`utils/data_loader.py` to update figures or add district-level population for finer detail."
            )
        else:
            fig3 = px.bar(
                by_province.sort_values("Value"), x="Value", y="Province", orientation="h",
                color="Province", color_discrete_map=PROVINCE_COLORS, text="Value",
            )
            fig3.update_traces(texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False, marker_line_width=0)
            fig3.update_layout(
                height=400, margin=dict(l=10, r=40, t=10, b=10), xaxis_title="Cases", yaxis_title="",
                font=dict(family="Inter, sans-serif", size=12, color="#334155"),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
            )
            st.plotly_chart(fig3, width="stretch", theme=None, config=PLOTLY_CONFIG)
            st.caption("Raw case totals — switch to 'Per 100,000 people' above to see it adjusted for province population.")

st.write("")
with panel():
    section_header("Composition", "Disease category mix by province", "🗂️")
    cat_prov = df.groupby(["Province", "Category"], as_index=False)["Value"].sum()
    fig4 = px.bar(
        cat_prov, x="Province", y="Value", color="Category", barmode="stack",
        color_discrete_map=CATEGORY_COLORS,
    )
    fig4.update_layout(
        height=400, margin=dict(l=10, r=10, t=48, b=10), xaxis_title="", yaxis_title="Cases",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            title_text="Category", font=dict(size=10.5), bgcolor="rgba(0,0,0,0)",
        ),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=12, color="#334155"),
    )
    fig4.update_traces(marker_line_width=0)
    st.plotly_chart(fig4, width="stretch", theme=None, config=PLOTLY_CONFIG)

st.write("")
with panel():
    section_header("Momentum", "Weekly trend, top 4 provinces", "📐")
    top4_prov = by_province["Province"].head(4).tolist()
    trend = df[df["Province"].isin(top4_prov)].groupby(["Date", "Province"], as_index=False)["Value"].sum()
    fig5 = px.line(
        trend, x="Date", y="Value", facet_col="Province", facet_col_wrap=4,
        color="Province", color_discrete_map=PROVINCE_COLORS,
    )
    fig5.update_yaxes(matches=None, showticklabels=True)
    fig5.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    fig5.update_layout(
        height=260, margin=dict(l=10, r=10, t=30, b=10), showlegend=False,
        font=dict(family="Inter, sans-serif", size=11, color="#334155"),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig5, width="stretch", theme=None, config=PLOTLY_CONFIG)

st.write("")
with panel():
    section_header("Full detail", "All districts, ranked", "🧾")
    search = st.text_input("Search district", placeholder="🔍 Search district name…", key="geo_district_search", label_visibility="collapsed")
    full_table = by_district.sort_values("Value", ascending=False)[["District", "Province", "Value"]].rename(columns={"Value": "Cases"})
    if search:
        full_table = full_table[full_table["District"].str.contains(search, case=False, na=False)]
    st.dataframe(full_table, width="stretch", hide_index=True)

st.write("")
col3, col4 = st.columns(2)
with col3:
    with panel():
        section_header("Hierarchy", "Top districts within each province", "🌳")
        tmap = by_district.copy()
        tmap["Province"] = tmap["Province"].astype(str)

        # Explicit color legend — each row is already labeled with its
        # province name, but spelling out color→province with the same
        # colored-dot pattern used in the hero header removes any need
        # to cross-reference the row label with the bar color.
        legend_html = "".join(
            f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:16px;font-size:12px;color:var(--ink-700);">'
            f'<span style="width:10px;height:10px;border-radius:50%;background:{PROVINCE_COLORS.get(p, "#94A3B8")};display:inline-block;"></span>{p}</span>'
            for p in sorted(tmap["Province"].unique())
        )
        st.markdown(f'<div style="margin:2px 0 10px 0;">{legend_html}</div>', unsafe_allow_html=True)

        top_n_per_prov = (
            tmap.sort_values("Value", ascending=False)
            .groupby("Province", group_keys=False)
            .head(5)
        )
        fig6 = px.bar(
            top_n_per_prov, x="Value", y="District", orientation="h",
            facet_row="Province", facet_row_spacing=0.09, color="Province",
            color_discrete_map=PROVINCE_COLORS,
            category_orders={"Province": sorted(top_n_per_prov["Province"].unique())},
        )
        # facet_row (one province per full-width row) instead of a 2x2
        # facet_col grid — side-by-side panels didn't leave enough room
        # for district names + value labels, which bled into the
        # neighboring panel. Stacking vertically gives each province the
        # full chart width, so nothing overlaps.
        #
        # Two follow-up fixes beyond the row-vs-column change itself:
        # 1) Each row previously got its own "Cases" x-axis title, and with
        #    4 tightly-packed rows those titles landed inside the bars of
        #    the row below. Only the bottom-most row (row=1 in Plotly's
        #    facet numbering) gets the title now.
        # 2) Rows were too short for Plotly to fit every y-axis tick label,
        #    so it silently dropped some district names. More height per
        #    row (via facet_row_spacing + fewer districts, 5 instead of 6)
        #    gives every label room to actually render.
        fig6.update_yaxes(matches=None, showticklabels=True, title="")
        fig6.update_xaxes(matches=None, title="")
        fig6.update_xaxes(title="Cases", row=1, col=1)
        fig6.for_each_annotation(lambda a: a.update(
            text=a.text.split("=")[-1], font=dict(size=13, family="Inter, sans-serif"),
            x=1.045, xanchor="left", textangle=0,
        ))
        fig6.update_traces(texttemplate="%{x:,.0f}", textposition="outside", cliponaxis=False, textfont_size=10)
        fig6.update_layout(
            height=980, margin=dict(l=4, r=95, t=20, b=40), showlegend=False,
            font=dict(family="Inter, sans-serif", size=11, color="#334155"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        table_data = tmap[["Province", "District", "Value"]].rename(columns={"Value": "Cases"}).sort_values(
            ["Province", "Cases"], ascending=[True, False]
        )
        chart_or_table(
            fig6, table_data, key="geo_hierarchy", table_height=460,
            caption="Top 5 districts shown per province — switch to Table for the full district list.",
        )

with col4:
    with panel():
        section_header("Concentration", "Cases by category × province", "🔥")
        heat = df.groupby(["Province", "Category"], as_index=False)["Value"].sum()
        heat_pivot = heat.pivot(index="Category", columns="Province", values="Value").fillna(0)
        fig7 = px.imshow(
            heat_pivot, aspect="auto", color_continuous_scale="Blues",
            labels=dict(color="Cases"),
        )
        fig7.update_layout(
            height=380, margin=dict(l=10, r=10, t=6, b=10),
            font=dict(family="Inter, sans-serif", size=11, color="#334155"),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig7, width="stretch", theme=None, config=PLOTLY_CONFIG)

st.write("")
col5, col6 = st.columns(2)
with col5:
    with panel():
        section_header("Spread", "District-level case distribution by province", "📦")
        fig8 = px.box(
            by_district, x="Province", y="Value", color="Province",
            color_discrete_map=PROVINCE_COLORS, points="outliers",
        )
        fig8.update_layout(
            height=360, margin=dict(l=10, r=10, t=6, b=10), showlegend=False,
            xaxis_title="", yaxis_title="Cases per district",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", size=11, color="#334155"),
        )
        st.plotly_chart(fig8, width="stretch", theme=None, config=PLOTLY_CONFIG)

with col6:
    with panel():
        section_header("Cumulative", "Share of national cases as provinces stack up", "📶")
        cum = by_province.sort_values("Value", ascending=False).reset_index(drop=True)
        cum["Cumulative %"] = cum["Value"].cumsum() / cum["Value"].sum() * 100
        fig9 = go.Figure()
        fig9.add_trace(go.Bar(x=cum["Province"], y=cum["Value"], name="Cases", marker_color="#2563EB"))
        fig9.add_trace(go.Scatter(x=cum["Province"], y=cum["Cumulative %"], name="Cumulative %", yaxis="y2", mode="lines+markers", line=dict(color="#F59E0B", width=2)))
        fig9.update_layout(
            height=400, margin=dict(l=10, r=10, t=48, b=10),
            yaxis=dict(title="Cases"), yaxis2=dict(title="Cumulative %", overlaying="y", side="right", range=[0, 105]),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                font=dict(size=11), bgcolor="rgba(0,0,0,0)",
            ),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", size=11, color="#334155"),
        )
        st.plotly_chart(fig9, width="stretch", theme=None, config=PLOTLY_CONFIG)
