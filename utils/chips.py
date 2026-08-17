import streamlit as st

CHIP_CSS = """
<style>
.chip-count {
    font-size: 10.5px; color: var(--ink-400, #94A3B8); margin: 2px 0 8px 0;
}

/* Sidebar circle-toggle filter list: one full-width pill per row. Full
   width (rather than side-by-side columns) is deliberate — the sidebar is
   only ~300px wide, and squeezing several pills into equal-width columns
   is what previously made long names like "Balochistan" wrap one letter
   per line. Stacking removes that failure mode entirely. */
.chiprow-marker + div[data-testid="stVerticalBlock"] div[data-testid="stButton"] > button {
    text-align: left !important;
    border-radius: 999px !important;
    font-size: 12.5px !important;
    font-weight: 600 !important;
    padding: 6px 14px !important;
    margin-bottom: 4px !important;
}

/* Wide, main-content "Filter by Province" quick row (views/overview.py)
   has plenty of horizontal room, so it stays a wrapping row of pills. */
div[data-testid="stElementContainer"]:has(> div.stMarkdown .pillrow-marker) + div[data-testid="stLayoutWrapper"] div[data-testid="stHorizontalBlock"] {
    flex-wrap: wrap !important;
    row-gap: 8px !important;
    column-gap: 8px !important;
}
div[data-testid="stElementContainer"]:has(> div.stMarkdown .pillrow-marker) + div[data-testid="stLayoutWrapper"] div[data-testid="stColumn"] {
    width: auto !important;
    flex: 0 0 auto !important;
    min-width: 0 !important;
}
div[data-testid="stElementContainer"]:has(> div.stMarkdown .pillrow-marker) + div[data-testid="stLayoutWrapper"] div[data-testid="stButton"] > button {
    border-radius: 999px !important;
    width: auto !important;
    min-height: 32px !important;
    height: 32px !important;
    padding: 0 14px !important;
    font-size: 12px !important;
    font-weight: 600 !important;
}

/* Graph / Table toggle (used in every chart_or_table panel, including
   narrow ones like the Composition treemap card). Buttons must size to
   their own text — forcing them to stretch across a fixed 1/7-width
   column is what clipped "📊 Graph" down to "Gra" in narrow panels.
   Styled as a single segmented control (shared pill background, no
   individual button shadows/borders) rather than two separate buttons,
   so it reads as "one control with two states" at a glance. */
div[data-testid="stElementContainer"]:has(> div.stMarkdown .toggle-row-marker) + div[data-testid="stLayoutWrapper"] div[data-testid="stHorizontalBlock"] {
    gap: 2px !important;
    display: inline-flex !important;
    background: var(--surface-2);
    border: 1px solid var(--border-soft);
    border-radius: 999px;
    padding: 3px;
    width: auto !important;
}
div[data-testid="stElementContainer"]:has(> div.stMarkdown .toggle-row-marker) + div[data-testid="stLayoutWrapper"] div[data-testid="stColumn"]:has(div[data-testid="stButton"]) {
    width: auto !important;
    flex: 0 0 auto !important;
    min-width: 0 !important;
}
div[data-testid="stElementContainer"]:has(> div.stMarkdown .toggle-row-marker) + div[data-testid="stLayoutWrapper"] div[data-testid="stColumn"]:not(:has(div[data-testid="stButton"])) {
    display: none !important;
}
div[data-testid="stElementContainer"]:has(> div.stMarkdown .toggle-row-marker) + div[data-testid="stLayoutWrapper"] div[data-testid="stButton"] > button {
    width: auto !important;
    white-space: nowrap !important;
    padding: 6px 16px !important;
    font-size: 12.5px !important;
    font-weight: 600 !important;
    border-radius: 999px !important;
    border: none !important;
    box-shadow: none !important;
}
div[data-testid="stElementContainer"]:has(> div.stMarkdown .toggle-row-marker) + div[data-testid="stLayoutWrapper"] div[data-testid="stButton"] > button[kind="secondary"] {
    background: transparent !important;
}

/* "Compare diseases" dropdown (st.popover): with no width cap, the long
   disease-name buttons forced the floating panel to grow wide enough to
   spill out over the main Overview content behind it. Pinning it to a
   sidebar-sized width, letting button text wrap onto a second line
   instead of stretching the box, and capping the height with an internal
   scrollbar keeps the dropdown self-contained no matter how many diseases
   are in the list. */
div[data-testid="stPopoverBody"] {
    width: 300px !important;
    max-width: 300px !important;
    max-height: 60vh !important;
    overflow-y: auto !important;
}
div[data-testid="stPopoverBody"] div[data-testid="stButton"] > button {
    white-space: normal !important;
    word-break: break-word !important;
    line-height: 1.3 !important;
    font-size: 12px !important;
    padding: 7px 12px !important;
    text-align: left !important;
}
</style>
"""


def inject_chip_css():
    st.markdown(CHIP_CSS, unsafe_allow_html=True)


def _quick_actions(options: list, session_key: str):
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Select all", key=f"selall_{session_key}", width="stretch"):
            st.session_state[session_key] = list(options)
            st.rerun()
    with c2:
        if st.button("Clear", key=f"clear_{session_key}", width="stretch"):
            st.session_state[session_key] = []
            st.rerun()


def _toggle_group(label: str, options: list, session_key: str, n_cols: int = None):
    """
    Renders a filter as a single-column stack of ◉/○ circle-toggle pills —
    click one to flip it in/out of the current selection. Shared by both
    the Province and Disease category filters so they use one visual
    language. Rebuilt from scratch to render reliably at sidebar width
    (see CHIP_CSS: full-width rows, not equal-width columns).
    """
    if session_key not in st.session_state:
        st.session_state[session_key] = list(options)

    st.markdown(f"<p style='font-size:12px;font-weight:600;color:var(--ink-700,#334155);margin:10px 0 4px;'>{label}</p>", unsafe_allow_html=True)
    st.markdown(f"<p class='chip-count'>{len(st.session_state[session_key])} of {len(options)} selected</p>", unsafe_allow_html=True)

    st.markdown('<div class="chiprow-marker"></div>', unsafe_allow_html=True)
    for opt in options:
        active = opt in st.session_state[session_key]
        icon = "\u25c9" if active else "\u25cb"
        clicked = st.button(
            f"{icon}  {opt}", key=f"btn_{session_key}_{opt}",
            type="primary" if active else "secondary",
            width="stretch",
        )
        if clicked:
            if active:
                st.session_state[session_key] = [o for o in st.session_state[session_key] if o != opt]
            else:
                st.session_state[session_key] = st.session_state[session_key] + [opt]
            st.rerun()

    _quick_actions(options, session_key)
    return st.session_state[session_key]


def circle_chip_group(label: str, options: list, session_key: str):
    """Province filter — stacked ◉/○ circle-toggle pills."""
    return _toggle_group(label, options, session_key)


def square_chip_group(label: str, options: list, session_key: str):
    """Disease-category filter — same circle-toggle pills, longer labels wrap naturally."""
    return _toggle_group(label, options, session_key)


def disease_chip_group(display_options: list, session_key: str, all_options: list, default_n: int = 6):
    """Circle-toggle chip list for the disease comparison chart.

    Click a circle and it appears in the chart immediately, click it again
    and it disappears — same interaction as the Province/Category filters.
    This replaces st.multiselect here on purpose: a multiselect's own
    dropdown list renders as an overlay outside a popover's own box, which
    trips the popover's "click outside to close" behavior and boots you
    out before you can finish picking. Plain buttons don't have that
    problem, so the popover stays open while you toggle diseases on/off.
    """
    if session_key not in st.session_state:
        st.session_state[session_key] = list(all_options[:default_n])

    st.markdown(
        "<p style='font-size:11px;font-weight:600;color:var(--ink-500,#64748B);margin:2px 0 6px;'>Quick select</p>",
        unsafe_allow_html=True,
    )
    presets = [("Top 6", 6), ("Top 10", 10), ("Top 15", 15), ("All", None)]
    preset_cols = st.columns(len(presets))
    for col, (label, n) in zip(preset_cols, presets):
        with col:
            if st.button(label, key=f"preset_{session_key}_{label}", width="stretch"):
                st.session_state[session_key] = list(all_options) if n is None else list(all_options[:n])
                st.rerun()

    st.markdown(
        f"<p class='chip-count'>{len(st.session_state[session_key])} of {len(all_options)} selected</p>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="chiprow-marker"></div>', unsafe_allow_html=True)
    if not display_options:
        st.caption("No diseases match that search.")
    for opt in display_options:
        active = opt in st.session_state[session_key]
        icon = "\u25c9" if active else "\u25cb"
        clicked = st.button(
            f"{icon}  {opt}", key=f"btn_{session_key}_{opt}",
            type="primary" if active else "secondary",
            width="stretch",
        )
        if clicked:
            if active:
                st.session_state[session_key] = [o for o in st.session_state[session_key] if o != opt]
            else:
                st.session_state[session_key] = st.session_state[session_key] + [opt]
            st.rerun()

    return st.session_state[session_key]
