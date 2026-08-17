import streamlit as st
import pandas as pd

from utils.chips import inject_chip_css, circle_chip_group, square_chip_group
from utils.theme import sidebar_brand


def sidebar_filters(df: pd.DataFrame):
    inject_chip_css()
    sidebar_brand()
    st.sidebar.markdown(
        "<p style='font-size:11px;letter-spacing:0.08em;text-transform:uppercase;"
        "color:var(--ink-500,#64748B);font-weight:700;margin:2px 0 10px 0;'>Filters</p>",
        unsafe_allow_html=True,
    )

    provinces = sorted(df["Province"].unique().tolist())
    with st.sidebar:
        provinces_sel = circle_chip_group("Province", provinces, "f_province_chip")

    categories = sorted(df["Category"].unique().tolist())
    with st.sidebar:
        categories_sel = square_chip_group("Disease category", categories, "f_category_chip")

    scoped = df[df["Category"].isin(categories_sel)] if categories_sel else df
    diseases = sorted(scoped["Clean Disease"].unique().tolist())
    diseases_sel = st.sidebar.multiselect(
        "Disease (optional, narrows further)", diseases,
        default=st.session_state.get("f_disease", []),
        key="f_disease",
    )

    min_d, max_d = df["Date"].min().date(), df["Date"].max().date()
    date_sel = st.sidebar.slider(
        "Date range", min_value=min_d, max_value=max_d,
        value=st.session_state.get("f_date", (min_d, max_d)),
        key="f_date",
    )

    st.sidebar.caption(
        "Tap a circle or square to toggle it on/off. Filters persist across every "
        "page — Overview, Geography, Seasonality, Outbreak alerts, Forecast, Reporting quality."
    )

    return {
        "provinces": provinces_sel,
        "categories": categories_sel,
        "diseases": diseases_sel,
        "date_range": date_sel,
    }


def active_filters_bar(core: pd.DataFrame, f: dict, extra_tags: list = None):
    """Removable-tag strip summarizing exactly what's shaping the current
    page — provinces, categories, and date range, plus any page-specific
    extras passed in via extra_tags (e.g. Overview's disease-comparison
    count). Filters now live across several separate sidebar widgets
    (circle chips, a popover, a slider), so it's easy to lose track of
    what's actually applied without opening each one — this puts it all
    in one glanceable, editable row right under the hero. A filter that
    hasn't been narrowed from its full range shows as a plain
    informational "All ..." pill instead of listing every option.

    extra_tags: optional list of (label, remove_callback_or_None) tuples,
    same shape used internally here, so a page can add its own tags
    (remove_callback runs on click, then the page reruns).
    """
    all_provinces = sorted(core["Province"].unique().tolist())
    all_categories = sorted(core["Category"].unique().tolist())
    min_d, max_d = core["Date"].min().date(), core["Date"].max().date()

    def _remove_from(key, val):
        def _cb():
            st.session_state[key] = [o for o in st.session_state.get(key, []) if o != val]
        return _cb

    def _reset_date():
        st.session_state["f_date"] = (min_d, max_d)

    tags = []  # (label, remove_callback or None for a non-removable info pill)

    if f["provinces"] and len(f["provinces"]) < len(all_provinces):
        tags += [(f"📍 {p}", _remove_from("f_province_chip", p)) for p in f["provinces"]]
    else:
        tags.append(("📍 All provinces", None))

    if f["categories"] and len(f["categories"]) < len(all_categories):
        tags += [(f"🗂️ {c}", _remove_from("f_category_chip", c)) for c in f["categories"]]
    else:
        tags.append(("🗂️ All categories", None))

    if f["date_range"] != (min_d, max_d):
        tags.append((f"🗓️ {f['date_range'][0]}–{f['date_range'][1]}", _reset_date))

    if extra_tags:
        tags.extend(extra_tags)

    st.markdown(
        "<p style='font-size:11px;letter-spacing:0.06em;text-transform:uppercase;"
        "color:var(--ink-500,#64748B);font-weight:700;margin:0 0 6px;'>Active filters</p>",
        unsafe_allow_html=True,
    )
    # Reuses the existing wrapping-pill-row CSS (defined once in chips.py
    # for the old province quick-row) rather than adding new styles.
    st.markdown('<div class="pillrow-marker"></div>', unsafe_allow_html=True)
    cols = st.columns(len(tags))
    for i, (col, (label, cb)) in enumerate(zip(cols, tags)):
        with col:
            if cb is None:
                st.markdown(
                    "<span style='display:inline-flex;align-items:center;height:32px;padding:0 14px;"
                    "border-radius:999px;background:var(--surface-2,#EEF2F7);color:var(--ink-500,#64748B);"
                    f"font-size:12px;font-weight:600;white-space:nowrap;'>{label}</span>",
                    unsafe_allow_html=True,
                )
            else:
                if st.button(f"{label}  ✕", key=f"aftag_{i}_{label}"):
                    cb()
                    st.rerun()


def empty_state(df: pd.DataFrame, message: str = "No data matches the current filters. Try enabling more provinces or categories in the sidebar.") -> bool:
    """Returns True (and renders a friendly notice) if df is empty, so pages can `if empty_state(df): st.stop()`."""
    if df is None or len(df) == 0:
        st.warning(f":material/filter_alt_off: {message}")
        return True
    return False
