import streamlit as st
import streamlit.components.v1 as components
import plotly.io as pio


def _md(html: str) -> str:
    """Strip leading whitespace from every line of a multi-line HTML string.

    Markdown treats any line indented 4+ spaces as a fenced code block —
    regardless of `unsafe_allow_html`. Because our HTML snippets are built
    inside indented Python functions, the raw triple-quoted strings end up
    with exactly that kind of indentation, which is what caused literal
    `<div>...</div>` tags to leak onto the page as visible text instead of
    rendering. Every multi-line HTML string in this module is routed
    through here before being handed to st.markdown()."""
    return "\n".join(line.strip() for line in html.strip("\n").split("\n"))

# ---------------------------------------------------------------------------
# Theme engine: one palette per mode. Every color a component uses comes
# from a CSS variable defined here - nothing is hardcoded in the component
# markup itself, so flipping THEMES["dark"] vs THEMES["light"] is enough to
# re-skin the whole app (native Streamlit widgets + custom cards + Plotly).
# ---------------------------------------------------------------------------
THEMES = {
    "light": {
        "app-bg": "#F7F6F2",
        "header-bg": "rgba(255,255,255,0.75)",
        "surface-0": "#FFFFFF",
        "surface-1": "#FAF9F5",
        "surface-2": "#F1EFE9",
        "ink-900": "#191712",
        "ink-700": "#403C34",
        "ink-500": "#6E685D",
        "ink-400": "#9C9587",
        "border-soft": "rgba(25, 23, 18, 0.07)",
        "shadow-sm": "0 1px 2px rgba(25, 23, 18, 0.04)",
        "shadow-md": "0 4px 16px rgba(25, 23, 18, 0.06)",
        "shadow-lg": "0 12px 32px rgba(25, 23, 18, 0.09)",
        "scrollbar-track": "transparent",
        "scrollbar-thumb": "#D8D3C8",
        "scrollbar-thumb-hover": "#B8B2A4",
        "input-bg": "#FFFFFF",
        "input-border": "rgba(25, 23, 18, 0.14)",
        "plotly-template": "surveillance_light",
    },
}

import plotly.graph_objects as go

# Custom Plotly template: restrained dotted gridlines instead of Plotly's
# default solid ones (data should be the "ink" on an otherwise quiet
# canvas), Inter as the base chart font, and a warm-neutral axis line
# color matching the rest of the UI palette above.
pio.templates["surveillance_light"] = go.layout.Template(
    layout=go.Layout(
        font=dict(family="Inter, sans-serif", color="#403C34", size=12),
        # automargin=True is the actual fix for clipped/truncated axis labels
        # (long disease or district names getting cut off as "a)", "s)" etc.):
        # every chart in the codebase sets a small fixed margin like
        # margin=dict(l=10, ...) for a tight, consistent look, but that
        # value is a *minimum* once automargin is on — Plotly expands the
        # margin as needed to fit whatever text is actually on the axis,
        # instead of clipping it. This is set once, here, so it applies to
        # every chart in the app without editing each one individually.
        xaxis=dict(
            gridcolor="rgba(25,23,18,0.07)", griddash="dot", gridwidth=1,
            zerolinecolor="rgba(25,23,18,0.12)", linecolor="rgba(25,23,18,0.12)",
            automargin=True,
        ),
        yaxis=dict(
            gridcolor="rgba(25,23,18,0.07)", griddash="dot", gridwidth=1,
            zerolinecolor="rgba(25,23,18,0.12)", linecolor="rgba(25,23,18,0.12)",
            automargin=True,
        ),
        colorway=["#2563EB", "#0D9488", "#7C3AED", "#0EA5E9", "#D97706", "#DC2626"],
    )
)

# Shared Plotly config so every chart in the app — not just the ones that
# go through chart_or_table() — trims the toolbar down to essentials
# (zoom/pan/download) instead of showing Plotly's full default modebar.
# Import this and pass config=PLOTLY_CONFIG to any st.plotly_chart call.
PLOTLY_CONFIG = {
    "displayModeBar": "hover",
    "displaylogo": False,
    "modeBarButtonsToRemove": [
        "select2d", "lasso2d", "autoScale2d", "zoomIn2d",
        "zoomOut2d", "resetScale2d", "toggleSpikelines",
        "hoverCompareCartesian", "hoverClosestCartesian",
    ],
}

SHARED = {
    "accent": "#2563EB",
    "accent-soft-light": "#EAF2FE",
    "accent-soft-dark": "rgba(37,99,235,0.16)",
    "success": "#10B981",
    "success-soft-light": "#E7F8F1",
    "success-soft-dark": "rgba(16,185,129,0.14)",
    "warning": "#F59E0B",
    "warning-soft-light": "#FEF6E7",
    "warning-soft-dark": "rgba(245,158,11,0.14)",
    "danger": "#EF4444",
    "danger-soft-light": "#FDECEC",
    "danger-soft-dark": "rgba(239,68,68,0.14)",
}


def get_theme_mode() -> str:
    """The app is light-theme only — dark mode was removed per team lead
    request. Kept as a function (rather than inlining "light" everywhere)
    so the rest of the design-system code below doesn't need to change."""
    return "light"


PROVINCE_COLORS = {
    "Punjab": "#2563EB",
    "Sindh": "#0D9488",
    "KP": "#7C3AED",
    "Balochistan": "#0EA5E9",
}

# Deliberately warm/neutral, distinct from PROVINCE_COLORS' cool blue-green-
# purple family above, so a chart showing both dimensions at once (e.g.
# category-colored bars next to a province legend) never reads as one
# ambiguous palette.
CATEGORY_COLORS = {
    "Waterborne": "#D97706",
    "Respiratory": "#DC2626",
    "Vector-borne": "#CA8A04",
    "Zoonotic": "#EA580C",
    "Bloodborne": "#B91C1C",
    "Other / neglected tropical": "#78716C",
}

# ---------------------------------------------------------------------------
# Enterprise design system: fonts, CSS variables, and every component style.
# Nothing here touches data/filtering logic — presentation layer only.
# ---------------------------------------------------------------------------
def _build_base_css(mode: str) -> str:
    t = THEMES[mode]
    is_dark = mode == "dark"
    accent_soft = SHARED["accent-soft-dark"] if is_dark else SHARED["accent-soft-light"]
    success_soft = SHARED["success-soft-dark"] if is_dark else SHARED["success-soft-light"]
    warning_soft = SHARED["warning-soft-dark"] if is_dark else SHARED["warning-soft-light"]
    danger_soft = SHARED["danger-soft-dark"] if is_dark else SHARED["danger-soft-light"]
    # Sidebar and hero now use the same light surfaces as the rest of the
    # app — the app is light-theme only, so nothing should stay dark navy.
    navy_950, navy_900 = t["surface-1"], t["surface-0"]
    return f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Manrope:wght@500;600;700;800&family=Sora:wght@600;700;800&display=swap" rel="stylesheet">

<style>
:root {{
    --navy-950: {navy_950};
    --navy-900: {navy_900};
    --navy-800: {t["surface-2"]};
    --ink-900: {t["ink-900"]};
    --ink-700: {t["ink-700"]};
    --ink-500: {t["ink-500"]};
    --ink-400: {t["ink-400"]};
    --surface-0: {t["surface-0"]};
    --surface-1: {t["surface-1"]};
    --surface-2: {t["surface-2"]};
    --border-soft: {t["border-soft"]};
    --accent: {SHARED["accent"]};
    --accent-soft: {accent_soft};
    --success: {SHARED["success"]};
    --success-soft: {success_soft};
    --warning: {SHARED["warning"]};
    --warning-soft: {warning_soft};
    --danger: {SHARED["danger"]};
    --danger-soft: {danger_soft};
    --shadow-sm: {t["shadow-sm"]};
    --shadow-md: {t["shadow-md"]};
    --shadow-lg: {t["shadow-lg"]};
    --radius-sm: 8px;
    --radius-md: 14px;
    --radius-lg: 20px;
    --app-bg: {t["app-bg"]};
    --header-bg: {t["header-bg"]};
    --input-bg: {t["input-bg"]};
    --input-border: {t["input-border"]};
    --scrollbar-track: {t["scrollbar-track"]};
    --scrollbar-thumb: {t["scrollbar-thumb"]};
    --scrollbar-thumb-hover: {t["scrollbar-thumb-hover"]};
}}
</style>
""" + """
<style>
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}

/* ---------- Global layout ---------- */
.block-container {
    padding-top: 1.4rem !important;
    padding-bottom: 3rem !important;
    max-width: 1280px;
    animation: fadeInUp 0.35s ease;
}
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
}
[data-testid="stAppViewContainer"] { background: var(--app-bg); }
[data-testid="stHeader"] { background: var(--header-bg); backdrop-filter: blur(8px); }
[data-testid="stAppViewContainer"] p, .stMarkdown, .stMarkdown p, label,
[data-testid="stMetricLabel"], [data-testid="stMetricValue"],
h1, h2, h3, h4, h5, h6 { color: var(--ink-900); }
[data-testid="stCaptionContainer"] { color: var(--ink-500) !important; }

/* ---------- Scrollbar ---------- */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--scrollbar-track); }
::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 8px; }
::-webkit-scrollbar-thumb:hover { background: var(--scrollbar-thumb-hover); }

/* ---------- Dark-mode-aware native inputs (text stays readable both ways) ---------- */
div[data-testid="stTextInput"] input,
div[data-testid="stDateInput"] input,
div[data-testid="stMultiSelect"] > div,
div[data-testid="stSelectbox"] > div,
div[data-baseweb="select"] > div {
    background: var(--input-bg) !important;
    border-color: var(--input-border) !important;
    color: var(--ink-900) !important;
}
[data-testid="stExpander"] summary { color: var(--ink-900) !important; }

/* ---------- Multiselect tags: never truncate a disease/label name ----------
   Streamlit's default tag width clips long labels behind an ellipsis
   ("AD (Acute Diarrh...") which makes it impossible to tell selections
   apart at a glance. Let tags wrap onto their own line at full width
   instead of hiding text. */
div[data-baseweb="tag"] {
    max-width: none !important;
    height: auto !important;
}
div[data-baseweb="tag"] span[title] {
    max-width: none !important;
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: unset !important;
}
[data-testid="stDataFrame"] { color: var(--ink-900); background: var(--surface-0); }
div[data-testid="stSlider"] label, div[data-testid="stMultiSelect"] label { color: var(--ink-700) !important; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {
    background: var(--surface-0);
    border-right: 1px solid var(--border-soft);
}
[data-testid="stSidebar"] * { color: var(--ink-900) !important; }
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span { color: var(--ink-700) !important; }
[data-testid="stSidebarNav"] a {
    border-radius: 999px !important;
    margin: 2px 10px !important;
    padding-left: 14px !important;
    font-weight: 500 !important;
    font-size: 13.5px !important;
    transition: background 0.15s ease, color 0.15s ease !important;
}
[data-testid="stSidebarNav"] a:hover { background: var(--surface-2) !important; }
[data-testid="stSidebarNav"] a[aria-selected="true"] {
    background: var(--accent) !important;
    color: #FFFFFF !important;
}
[data-testid="stSidebarNav"] a[aria-selected="true"] span { color: #FFFFFF !important; }
[data-testid="stSidebar"] hr { border-color: var(--border-soft) !important; }

/* Sidebar buttons (chips) */
[data-testid="stSidebar"] div[data-testid="stButton"] > button {
    background: var(--surface-0) !important;
    border: 1.5px solid var(--border-soft) !important;
    color: var(--ink-700) !important;
    white-space: nowrap !important;
}
[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
    border-color: var(--accent) !important;
    color: var(--accent) !important;
}
[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="primary"] {
    background: var(--accent) !important;
    border-color: var(--accent) !important;
    color: #FFFFFF !important;
}

/* ---------- Sidebar brand block ---------- */
.brand-block {
    display: flex; align-items: center; gap: 10px;
    padding: 4px 4px 18px 4px;
    margin-bottom: 6px;
    border-bottom: 1px solid var(--border-soft);
}
.brand-icon {
    width: 36px; height: 36px; border-radius: 10px;
    background: linear-gradient(135deg, #2563EB, #60A5FA);
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; flex-shrink: 0;
}
.brand-text { line-height: 1.2; }
.brand-title { font-size: 13.5px; font-weight: 700; color: var(--ink-900) !important; }
.brand-sub { font-size: 10.5px; color: var(--ink-500) !important; letter-spacing: 0.03em; }

/* ---------- Hero header (compact, info-dense) ---------- */
.hero {
    background:
        radial-gradient(ellipse 480px 220px at 15% -20%, rgba(37,99,235,0.10), transparent 70%),
        linear-gradient(135deg, var(--accent-soft) 0%, var(--surface-0) 60%);
    padding: 1.15rem 1.5rem;
    border-radius: var(--radius-md);
    margin-bottom: 1.1rem;
    box-shadow: var(--shadow-md);
    border: 1px solid var(--border-soft);
    position: sticky;
    top: 0.5rem;
    z-index: 20;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
}
.hero-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.hero-updated {
    font-size: 11px; color: var(--ink-700); display: flex; align-items: center; gap: 6px;
    background: var(--surface-0); border: 1px solid var(--border-soft);
    border-radius: 999px; padding: 5px 12px; white-space: nowrap;
}
.hero-live-dot {
    display: inline-block; width: 6px; height: 6px; border-radius: 50%;
    background: var(--success); box-shadow: 0 0 6px var(--success);
}
.hero-kicker {
    font-size: 25px; letter-spacing: -0.015em; text-transform: none;
    color: var(--ink-900); margin: 0 0 5px 0; font-weight: 700;
    font-family: 'Sora', 'Manrope', sans-serif; line-height: 1.2;
}
.hero-title {
    font-family: 'Inter', sans-serif;
    font-size: 14px; font-weight: 500; color: var(--ink-500); margin: 0 0 8px 0;
    letter-spacing: 0; line-height: 1.4;
}
.hero-left { flex: 1 1 auto; min-width: 260px; }
.hero-right { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; }
.hero-title .accent-italic { color: var(--accent); font-weight: 600; font-style: italic; font-size: 14px; }
.hero-chip {
    display: inline-flex; align-items: center; gap: 5px;
    font-size: 10.5px; color: var(--ink-700);
    background: var(--surface-0);
    border: 1px solid var(--border-soft);
    border-radius: 999px; padding: 4px 11px; margin-right: 6px;
}
.hero-chip b { color: var(--ink-900); font-weight: 600; }
.hero-legend { margin-top: 6px; color: var(--ink-700); font-size: 11px; }
.legend-dot {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%;
    margin-right: 5px; box-shadow: 0 0 6px currentColor;
}

/* ---------- KPI cards ---------- */
.kpi-card {
    background: var(--surface-0);
    border: 1px solid var(--border-soft);
    border-top: 3px solid #2563EB;
    border-radius: var(--radius-md);
    padding: 1rem 1.1rem;
    box-shadow: var(--shadow-sm), inset 0 1px 0 rgba(255,255,255,0.6);
    transition: transform 0.18s ease, box-shadow 0.18s ease;
    position: relative;
}
.kpi-card:hover {
    transform: translateY(-3px) scale(1.008);
    box-shadow: var(--shadow-md), inset 0 1px 0 rgba(255,255,255,0.6);
}
.kpi-top { display: flex; justify-content: space-between; align-items: flex-start; }
.kpi-icon {
    width: 30px; height: 30px; border-radius: 9px;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px; background: var(--surface-2);
}
.kpi-icon svg { display: block; }
.kpi-label {
    font-size: 10.5px; letter-spacing: 0.05em; color: var(--ink-500);
    margin: 10px 0 4px 0; text-transform: uppercase; font-weight: 600;
}
.kpi-value {
    font-family: 'Sora', 'Manrope', sans-serif;
    font-size: 26px; font-weight: 700; margin: 0; color: var(--ink-900);
    letter-spacing: -0.02em; font-variant-numeric: tabular-nums;
}
.kpi-subtitle {
    font-size: 11.5px; color: var(--ink-500); margin: 3px 0 0 0; font-weight: 500;
}
.kpi-delta {
    font-size: 11px; font-weight: 600; margin-top: 4px; display: inline-block;
    padding: 2px 8px; border-radius: 999px;
}
.kpi-delta.up { color: var(--success); background: var(--success-soft); }
.kpi-delta.down { color: var(--danger); background: var(--danger-soft); }
.kpi-delta.flat { color: var(--ink-500); background: var(--surface-2); }

/* The first KPI card in a row is, on every page, that page's single
   headline number (Total Cases, Overall Trend, Total Anomalies...). It's
   currently styled identically to the other three, so the eye has no
   natural place to land first. Giving it a soft tinted wash + a slightly
   larger value establishes hierarchy without needing a "primary" flag
   threaded through every page's call site — :first-child is scoped to
   its own row, so this only ever touches the lead card. */
div[data-testid="stColumn"]:first-child .kpi-card {
    background: linear-gradient(160deg, var(--accent-soft) 0%, var(--surface-0) 70%);
}
div[data-testid="stColumn"]:first-child .kpi-card .kpi-value {
    font-size: 29px;
}

/* Concerning-state edge glow: when a KPI's delta direction signals
   something worth attention (e.g. rising anomalies, falling compliance),
   kpi_card() adds this class so the eye catches it even before reading
   the delta badge text. Purely visual — the direction itself is still
   computed by the caller, this just renders it more prominently. */
.kpi-card.kpi-concern {
    box-shadow: 0 0 0 1px var(--danger-soft), var(--shadow-sm);
}
.kpi-card.kpi-concern::before {
    content: "";
    position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
    background: var(--danger); border-radius: var(--radius-md) 0 0 var(--radius-md);
}

/* Narrow viewports (laptop/tablet): a 4-across KPI row squeezes into
   unreadably narrow cards. Fall back to a 2x2 grid instead. */
@media (max-width: 900px) {
    div[data-testid="stHorizontalBlock"]:has(.kpi-card) {
        flex-wrap: wrap !important;
    }
    div[data-testid="stHorizontalBlock"]:has(.kpi-card) > div[data-testid="stColumn"] {
        min-width: 46% !important;
        flex: 1 1 46% !important;
    }
}

/* ---------- Empty state ---------- */
.empty-state {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 8px; padding: 2.4rem 1rem; text-align: center;
}
.empty-state-icon { font-size: 26px; opacity: 0.5; }
.empty-state-text { font-size: 12.5px; color: var(--ink-500); max-width: 380px; margin: 0; }

/* ---------- Section headers ---------- */
.section-head { display: flex; align-items: center; gap: 10px; margin: 4px 0 14px 0; }
.section-eyebrow {
    font-size: 9.5px; letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--ink-400); font-weight: 700; margin: 0 0 3px 0;
}
.section-title {
    font-family: 'Sora', 'Manrope', sans-serif;
    font-size: 17px; font-weight: 700; color: var(--ink-900); margin: 0;
    letter-spacing: -0.01em;
}
/* Consistent icon treatment: every section_header() icon now sits in the
   same small rounded badge used for KPI-card icons, instead of floating
   as a bare, inconsistently-sized emoji next to the title. */
.section-icon-badge {
    display: inline-flex; align-items: center; justify-content: center;
    width: 30px; height: 30px; border-radius: 9px; font-size: 14px;
    background: var(--surface-2); flex-shrink: 0;
}


/* ---------- Glass panel wrapper for chart blocks (real st.container(border=True)) ---------- */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--surface-0);
    border: 1px solid var(--border-soft) !important;
    border-radius: var(--radius-md) !important;
    padding: 1.1rem 1.2rem;
    box-shadow: var(--shadow-sm), inset 0 1px 0 rgba(255,255,255,0.6);
    transition: box-shadow 0.18s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover { box-shadow: var(--shadow-md), inset 0 1px 0 rgba(255,255,255,0.6); }
/* Streamlit nests one extra nameless wrapper inside a bordered container;
   strip its default padding so our own .panel padding above is the only one. */
[data-testid="stVerticalBlockBorderWrapper"] > div { padding: 0 !important; }

/* ---------- AI insight panel ---------- */
.insight-panel {
    background: var(--surface-0);
    border-radius: var(--radius-md);
    padding: 1rem 1.2rem;
    box-shadow: var(--shadow-sm);
    border: 1px solid var(--border-soft);
}
.insight-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.insight-badge {
    font-size: 10.5px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;
    color: var(--accent); background: var(--accent-soft); border-radius: 999px;
    padding: 3px 10px;
}
.insight-title { color: var(--ink-900); font-weight: 700; font-size: 14px; font-family: 'Manrope', sans-serif; }
.insight-list { margin: 0; padding: 0; list-style: none; }
.insight-item {
    display: flex; gap: 8px; align-items: flex-start;
    font-size: 12.5px; color: var(--ink-700); padding: 6px 0;
    border-top: 1px dashed var(--border-soft);
}
.insight-item:first-child { border-top: none; }
.insight-icon { flex-shrink: 0; }
.insight-item b { color: var(--ink-900); }

/* ---------- Status badges ---------- */
.status-badge {
    display: inline-flex; align-items: center; gap: 6px;
    font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 999px;
}
.status-badge.live { color: var(--success); background: var(--success-soft); }
.status-badge.warn { color: var(--warning); background: var(--warning-soft); }
.status-badge.alert { color: var(--danger); background: var(--danger-soft); }
.status-dot {
    width: 6px; height: 6px; border-radius: 50%; background: currentColor;
    box-shadow: 0 0 0 3px currentColor22;
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%   { opacity: 1; }
    50%  { opacity: 0.4; }
    100% { opacity: 1; }
}

/* ---------- Native Streamlit component polish ---------- */
[data-testid="stMetric"] {
    background: var(--surface-0); border: 1px solid var(--border-soft);
    border-radius: var(--radius-md); padding: 0.8rem 1rem; box-shadow: var(--shadow-sm);
}
.stPlotlyChart, .js-plotly-plot { border-radius: var(--radius-md); overflow: hidden; }
[data-testid="stDataFrame"] { border-radius: var(--radius-md); overflow: hidden; border: 1px solid var(--border-soft); }
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--border-soft); }
.stTabs [data-baseweb="tab"] {
    border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important;
    font-weight: 600 !important; font-size: 13px !important;
    padding: 8px 16px !important;
}
.stTabs [aria-selected="true"] { color: var(--accent) !important; }
div[data-testid="stExpander"] {
    border: 1px solid var(--border-soft) !important; border-radius: var(--radius-md) !important;
    box-shadow: var(--shadow-sm);
}
.stAlert { border-radius: var(--radius-md) !important; }
[data-testid="stDownloadButton"] > button, div[data-testid="stButton"] > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    transition: all 0.15s ease !important;
    white-space: nowrap !important;
}
div[data-testid="stSlider"] [role="slider"] { box-shadow: 0 0 0 4px rgba(37,99,235,0.15) !important; }

/* Segmented control (granularity toggle) + quick-filter pill rows */
div[data-testid="stSegmentedControl"] label {
    font-weight: 600 !important; font-size: 12.5px !important;
}
.stRadio[role="radiogroup"] { gap: 6px; }
div[data-testid="stTextInput"] input {
    border-radius: 10px !important;
}
h5, .stMarkdown h5 { font-family: 'Manrope', sans-serif; letter-spacing: 0.01em; }

/* ---------- Motion: soften Streamlit's hard-cut reruns ---------- */
@keyframes fadeInUp { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
.hero, div[data-testid="stVerticalBlockBorderWrapper"], .kpi-card {
    animation: fadeInUp 0.32s ease both;
}
div[data-testid="stColumn"]:nth-child(2) .kpi-card { animation-delay: 0.03s; }
div[data-testid="stColumn"]:nth-child(3) .kpi-card { animation-delay: 0.06s; }
div[data-testid="stColumn"]:nth-child(4) .kpi-card { animation-delay: 0.09s; }
@media (prefers-reduced-motion: reduce) {
    .hero, div[data-testid="stVerticalBlockBorderWrapper"], .kpi-card { animation: none; }
}

/* ---------- Narrative line (one-line "so what" above a chart) ---------- */
.narrative-line {
    font-size: 12.5px; color: var(--ink-700); background: var(--accent-soft);
    border-left: 3px solid var(--accent); padding: 7px 12px; border-radius: 8px;
    margin: 2px 0 12px 0;
}

/* ---------- Print stylesheet: strip interactive chrome for handouts ---------- */
@media print {
    [data-testid="stSidebar"], [data-testid="stHeader"], .toggle-row-marker,
    div[data-testid="stElementContainer"]:has(.toggle-row-marker),
    div[data-testid="stElementContainer"]:has(> div.stMarkdown .topheader-marker),
    .modebar, div[data-testid="stButton"] { display: none !important; }
    [data-testid="stAppViewContainer"], [data-testid="stMain"], .main {
        margin: 0 !important; padding: 0 !important; width: 100% !important;
    }
    .hero { position: static !important; box-shadow: none !important; border: 1px solid #ddd !important; }
    .kpi-card, div[data-testid="stVerticalBlockBorderWrapper"] {
        box-shadow: none !important; border: 1px solid #ddd !important;
        break-inside: avoid; animation: none !important;
    }
    body, .stApp { background: #fff !important; }
}
</style>
"""


def narrative_line(text_html: str, icon: str = "💡"):
    """One-line 'so what' callout meant to sit directly above a chart —
    e.g. narrative_line(trend_note) using a sentence a page has already
    computed from its own filtered dataframe. Intentionally takes
    pre-built text rather than raw numbers, so it never invents a claim
    the caller didn't already derive from real data."""
    st.markdown(f'<p class="narrative-line">{icon} {text_html}</p>', unsafe_allow_html=True)


def add_event_annotations(fig, events: list):
    """Overlay known-event markers (outbreak declarations, policy changes,
    holidays, etc.) on a Plotly time-series figure, so a spike/dip has
    visible context instead of looking unexplained.

    events: list of dicts, each {"date": <x-value>, "label": <str>}.
    No events are pre-populated here — this dashboard doesn't have a
    verified source of dated health-policy/outbreak-declaration events
    to hardcode, so wiring real dates in is left to whoever maintains
    that calendar. Usage once you have a list:

        add_event_annotations(fig, [
            {"date": "2023-07-01", "label": "Flood response scale-up"},
        ])
    """
    for ev in events:
        fig.add_vline(
            x=ev["date"], line_width=1, line_dash="dot", line_color="#94A3B8",
        )
        fig.add_annotation(
            x=ev["date"], y=1, yref="paper", showarrow=False,
            text=ev["label"], textangle=-90, xanchor="left", yanchor="top",
            font=dict(size=9, color="#64748B"),
        )
    return fig


def inject_base_css():
    mode = get_theme_mode()
    st.markdown(_build_base_css(mode), unsafe_allow_html=True)
    pio.templates.default = THEMES[mode]["plotly-template"]
    # Theme is toggled from the top header's moon/sun button only — keeping
    # a single control avoids two switches that can drift out of sync.


# ---------------------------------------------------------------------------
# KPI icon set — inline Lucide-style SVGs (24x24, stroke=currentColor) so
# every KPI card across every page draws from one consistent icon family
# instead of mismatched platform emoji. `icon` in kpi_card() looks a key
# up here first; anything not found here falls back to being rendered
# as-is (so raw emoji still works if ever passed directly).
# ---------------------------------------------------------------------------
KPI_ICONS = {
    "heart-pulse": '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.29 1.51 4.04 3 5.5l7 7Z"/><path d="M3.22 12H9.5l.5-1 2 4.5 2-7 1.5 3.5h5.27"/>',
    "dna": '<path d="M2 15c6.667-6 13.333 0 20-6"/><path d="M9 22c1.798-1.998 2.518-3.995 2.807-5.993"/><path d="M15 2c-1.798 1.998-2.518 3.995-2.807 5.993"/><path d="m17 6-2.5-2.5"/><path d="m14 8-1-1"/><path d="m7 18 2.5 2.5"/><path d="m3.5 14.5.5.5"/><path d="m20 9 .5.5"/><path d="m6.5 12.5 1 1"/><path d="m16.5 10.5 1 1"/><path d="m10 16 1.5 1.5"/>',
    "map-pin": '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "trending-up": '<path d="M22 7 13.5 15.5l-5-5L2 17"/><path d="M16 7h6v6"/>',
    "trending-down": '<path d="M22 17 13.5 8.5l-5 5L2 7"/><path d="M16 17h6v-6"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    "alert-triangle": '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/><path d="M12 9v4M12 17h.01"/>',
    "activity": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "trophy": '<path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0V4Z"/><path d="M17 4h3a2 2 0 0 1 2 2c0 2-2 4-4 4M7 4H4a2 2 0 0 0-2 2c0 2 2 4 4 4"/>',
    "map": '<path d="M15 5.764v15M9 3.236v15M3 6l6-2.764L15 6l6-2.236v15L15 21l-6-2.764L3 21Z"/>',
    "flame": '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5Z"/>',
    "settings": '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2Z"/><circle cx="12" cy="12" r="3"/>',
    "check-circle": '<path d="M21.801 10A10 10 0 1 1 17 3.335"/><path d="m9 11 3 3L22 4"/>',
    "archive": '<rect x="2" y="3" width="20" height="5" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8M10 12h4"/>',
    "sparkles": '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0Z"/><path d="M20 3v4M22 5h-4M4 17v2M5 18H3"/>',
}


def _kpi_icon_html(icon: str, color: str) -> str:
    """Render a KPI icon: SVG if `icon` is a known key in KPI_ICONS,
    otherwise pass the value through unchanged (keeps emoji working if
    ever passed directly)."""
    path = KPI_ICONS.get(icon)
    if not path:
        return icon
    return (
        f'<svg width="17" height="17" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="2" stroke-linecap="round" '
        f'stroke-linejoin="round" role="img" aria-label="{icon.replace("-", " ")}">{path}</svg>'
    )


def sparkline_svg(values, color: str = "#2563EB", width: int = 120, height: int = 38) -> str:
    """Tiny inline SVG sparkline (no JS/plotly overhead) for KPI cards.
    Draws the actual last-12-period trend passed in via `values` — this
    is real data from each page's own dataframe, not a placeholder."""
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    n = len(vals)
    pts = [
        f"{(i / (n - 1)) * (width - 4) + 2:.1f},{height - 4 - ((v - lo) / span) * (height - 8):.1f}"
        for i, v in enumerate(vals)
    ]
    path = " ".join(pts)
    area = f"2,{height - 2} " + path + f" {width - 2},{height - 2}"
    last_x, last_y = pts[-1].split(",")
    trend_word = "rising" if vals[-1] > vals[0] else ("falling" if vals[-1] < vals[0] else "flat")
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'preserveAspectRatio="none" style="display:block;margin-top:8px;" '
        f'role="img" aria-label="Trend over last {len(vals)} periods: {trend_word}">'
        f'<polyline points="{area}" fill="{color}22" stroke="none"></polyline>'
        f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round"></polyline>'
        f'<circle cx="{last_x}" cy="{last_y}" r="2.5" fill="{color}"></circle>'
        f'</svg>'
    )


HEADER_CSS = """
<style>
.topheader-marker + div[data-testid="stHorizontalBlock"] div[data-testid="column"] { display:flex; align-items:center; }
.topheader-updated { font-size:10.5px; color:var(--ink-500); white-space:nowrap; text-align:right; line-height:1.4; }
.topheader-updated b { color:var(--ink-700); }
</style>
"""


def top_header(updated: str = None):
    """Global utility bar — last-updated only. The old search bar, bell,
    export, and avatar icons were decorative (not wired to any action),
    so they were removed rather than shipped as dead UI. Page-to-page
    navigation lives solely in the left sidebar, so this strip never
    duplicates it. Light theme only — the app no longer offers a dark
    mode toggle."""
    if not updated:
        return
    st.markdown(HEADER_CSS, unsafe_allow_html=True)
    st.markdown('<div class="topheader-marker"></div>', unsafe_allow_html=True)
    st.markdown(
        f'<div style="text-align:right;"><div class="topheader-updated">Last updated<br><b>{updated}</b></div></div>',
        unsafe_allow_html=True,
    )


def sidebar_brand(page_label: str = ""):
    brand_svg = _kpi_icon_html("heart-pulse", "#FFFFFF")
    st.sidebar.markdown(
        _md(f"""
        <div class="brand-block">
            <div class="brand-icon">{brand_svg}</div>
            <div class="brand-text">
                <div class="brand-title">IDSR Analytics</div>
                <div class="brand-sub">Pakistan Health Surveillance</div>
            </div>
        </div>
        """),
        unsafe_allow_html=True,
    )
    onboarding_tip()
    quick_search()
    mode_controls()


# Page index for quick_search — mirrors app.py's st.navigation list. Kept as
# a plain constant rather than introspecting st.navigation at runtime, since
# that list is small, static, and rarely changes.
PAGE_INDEX = [
    ("🏠", "Overview", "overview"),
    ("📍", "Geography", "geography"),
    ("📈", "Trends", "trends"),
    ("⚠️", "Outbreaks", "outbreaks"),
    ("🔮", "Forecast", "forecast"),
    ("🎯", "Executive Analytics", "executive"),
    ("📋", "Reporting", "reporting"),
    ("⚙️", "Settings", "settings"),
]


def quick_search():
    """Real, working quick-navigation: type to filter pages, click to jump.
    Note: this intentionally indexes *pages* only, not provinces/diseases —
    filters live in st.session_state rather than the URL, so there's no
    real deep-link target a 'search for Sindh' result could jump to
    without misleadingly appearing to work. A true Ctrl+K global shortcut
    isn't reliable in plain Streamlit (script tags injected via
    st.markdown don't execute), so this renders as a small always-visible
    sidebar search box via a sandboxed HTML component instead."""
    items_js = ",".join(
        f'{{"icon":"{i}","label":"{l}","path":"{p}"}}' for i, l, p in PAGE_INDEX
    )
    components.html(
        f"""
        <div style="font-family:Inter,sans-serif;">
        <input id="qs-input" placeholder="🔍 Jump to page…" style="
            width:100%; box-sizing:border-box; padding:8px 12px; font-size:12.5px;
            border:1px solid #E2E8F0; border-radius:8px; outline:none;">
        <div id="qs-results" style="margin-top:4px;"></div>
        </div>
        <script>
        const items = [{items_js}];
        const input = document.getElementById('qs-input');
        const results = document.getElementById('qs-results');
        function render(list) {{
            results.innerHTML = list.map(i => `
                <div class="qs-item" data-path="${{i.path}}" style="
                    padding:6px 10px; font-size:12.5px; cursor:pointer; border-radius:6px;
                    color:#3B4657;">${{i.icon}} ${{i.label}}</div>
            `).join('');
            document.querySelectorAll('.qs-item').forEach(el => {{
                el.onmouseover = () => el.style.background = '#EEF2F7';
                el.onmouseout = () => el.style.background = 'transparent';
                el.onclick = () => {{ window.top.location.href = '/' + el.dataset.path; }};
            }});
        }}
        input.addEventListener('input', () => {{
            const q = input.value.toLowerCase();
            render(q ? items.filter(i => i.label.toLowerCase().includes(q)) : []);
        }});
        </script>
        """,
        height=90,
    )


def mode_controls():
    """Compact/Comfortable density toggle + a distraction-free Presentation
    Mode. Implemented via CSS `zoom` on the main content area rather than
    re-deriving every hardcoded padding/font-size in the stylesheet — a
    pragmatic scale, not a full design-token rewrite. `zoom` works in
    Chromium-based browsers (Chrome/Edge, the common case for Streamlit
    users); it degrades to normal 100% size in browsers that ignore it
    (e.g. Firefox), so nothing breaks there — it just won't resize."""
    if "_density" not in st.session_state:
        st.session_state["_density"] = "Comfortable"
    with st.sidebar.expander("🖥️ Display", expanded=False):
        density = st.radio(
            "Density", ["Compact", "Comfortable"], horizontal=True,
            key="_density", label_visibility="collapsed",
        )
        presentation = st.toggle("Presentation mode", key="_presentation", value=False)
    zoom = 0.88 if density == "Compact" else 1.0
    if presentation:
        zoom = 1.16
    st.markdown(f'<style>[data-testid="stMain"] {{ zoom: {zoom}; }}</style>', unsafe_allow_html=True)
    if presentation:
        st.markdown(
            """<style>
            [data-testid="stSidebar"] { opacity: 0.5; transition: opacity 0.2s ease; }
            [data-testid="stSidebar"]:hover { opacity: 1; }
            div[data-testid="stElementContainer"]:has(.toggle-row-marker) { display: none !important; }
            </style>""",
            unsafe_allow_html=True,
        )


def onboarding_tip():
    """One-time, dismissible 'how to read this dashboard' note — collapsed
    for the rest of the session once dismissed, not shown again on rerun."""
    if st.session_state.get("_onboarding_dismissed"):
        return
    with st.sidebar.expander("ℹ️ How to read this dashboard", expanded=False):
        st.caption(
            "**KPI cards** show the current value plus a mini trend line "
            "(last 12 periods) and a %-change badge vs. the prior period.\n\n"
            "**Graph / Table** toggle switches any chart to its underlying "
            "data without duplicating space.\n\n"
            "Use the sidebar filters to narrow by province, disease, or date."
        )
        if st.button("Got it, don't show again", key="_dismiss_onboarding"):
            st.session_state["_onboarding_dismissed"] = True
            st.rerun()


def hero(title: str, subtitle_html: str, chips: dict, provinces=True, updated: str = None):
    dots = "".join(
        f'<span class="legend-dot" style="background:{c};color:{c}"></span>{p} &nbsp;&nbsp;'
        for p, c in PROVINCE_COLORS.items()
    ) if provinces else ""
    chip_html = "".join(
        f'<span class="hero-chip">{k} <b>{v}</b></span>' for k, v in chips.items()
    )
    updated_html = (
        f'<div class="hero-updated"><span class="hero-live-dot"></span>{updated}</div>' if updated else ""
    )
    st.markdown(
        _md(f"""
        <div class="hero">
            <div class="hero-left">
                <p class="hero-kicker">Pakistan Public Health Surveillance &nbsp;·&nbsp; Enterprise Analytics</p>
                <p class="hero-title">{title} <span class="accent-italic">{subtitle_html}</span></p>
                <div>{chip_html}</div>
                {f'<div class="hero-legend">{dots}</div>' if dots else ''}
            </div>
            <div class="hero-right">
                {updated_html}
            </div>
        </div>
        """),
        unsafe_allow_html=True,
    )


def insight_panel(title: str, items: list):
    """
    items: list of (icon, html_text) tuples. Purely presentational — the
    caller computes the actual figures from the already-filtered dataframe,
    this just renders them as an executive-style insight card.
    """
    rows = "".join(
        f'<li class="insight-item"><span class="insight-icon">{icon}</span><span>{text}</span></li>'
        for icon, text in items
    )
    st.markdown(
        _md(f"""
        <div class="insight-panel">
            <div class="insight-head">
                <span class="insight-badge">AI Summary</span>
                <span class="insight-title">{title}</span>
            </div>
            <ul class="insight-list">{rows}</ul>
        </div>
        """),
        unsafe_allow_html=True,
    )


def section_header(eyebrow: str, title: str, icon: str = ""):
    st.markdown(
        _md(f"""
        <div class="section-head">
            <div>
                <p class="section-eyebrow">{eyebrow}</p>
                <p class="section-title">{icon + " " if icon else ""}{title}</p>
            </div>
        </div>
        """),
        unsafe_allow_html=True,
    )


def status_badge(text: str, kind: str = "live"):
    st.markdown(
        f'<span class="status-badge {kind}"><span class="status-dot" role="img" aria-label="{kind} status"></span>{text}</span>',
        unsafe_allow_html=True,
    )


def legend_dots(colors: dict, keys: list = None) -> str:
    """Build an inline HTML legend of colored dots + labels, for placing
    above a chart (reuses the same `.legend-dot` style as the hero banner).

    `colors` maps label -> hex color (e.g. CATEGORY_COLORS, or a one-off
    dict like {"Records": "#2563EB"}). Pass `keys` to control which
    entries render and in what order (e.g. only categories present in the
    current filtered view); otherwise every key in `colors` is shown.
    """
    keys = keys if keys is not None else list(colors.keys())
    dots = "".join(
        f'<span class="legend-dot" style="background:{colors[k]};color:{colors[k]}"></span>{k} &nbsp;&nbsp;'
        for k in keys if k in colors
    )
    return f'<div class="hero-legend">{dots}</div>'


def pct_color(pct: float, good_high: bool = True, good: float = 70, warn: float = 40) -> str:
    """Return a green/amber/red hex for a percentage value against two
    thresholds. good_high=True means higher is better (e.g. compliance);
    good_high=False means lower is better (e.g. % of weeks flagged as
    anomalous). Callers decide polarity explicitly — same reasoning as
    kpi_card's `concern` flag: a threshold color is only meaningful once
    someone who knows the metric's direction has set it, not inferred."""
    if not good_high:
        pct = 100 - pct
    if pct >= good:
        return "#10B981"
    if pct >= warn:
        return "#F59E0B"
    return "#EF4444"


def kpi_card(col, label: str, value: str, border_color: str = "#2563EB", icon: str = "📊", delta: str = None, delta_dir: str = "flat", spark_values=None, concern: bool = False, subtitle: str = None, value_color: str = None):
    """`concern` is an explicit opt-in (default False) rather than
    inferred from delta_dir — "down" means something different on a
    "falling anomalies" card vs. a "falling compliance" card, so only the
    caller (who knows the metric's polarity) should decide whether to
    flag it. Pass concern=True from a page when a KPI value is in a
    state worth the reader's attention.

    `subtitle`: small secondary line under the main value — the standard
    place for a raw count when `value` itself is a percentage (the
    dashboard's primary/secondary convention: percentage leads as the
    big bold number, the raw count that produced it is the smaller
    supporting detail underneath, not the other way around).

    `value_color`: optional override for the big value's text color —
    defaults to None (the normal dark ink color, unchanged from before).
    Pass pct_color(...) here to make a percentage-led card's number
    itself carry a green/amber/red read, on cards where that's wanted;
    left off, every existing card renders exactly as it did before."""
    delta_html = f'<div class="kpi-delta {delta_dir}">{delta}</div>' if delta else ""
    subtitle_html = f'<p class="kpi-subtitle">{subtitle}</p>' if subtitle else ""
    spark_html = _md(sparkline_svg(spark_values, border_color)) if spark_values else ""
    icon_html = _kpi_icon_html(icon, border_color)
    card_class = "kpi-card kpi-concern" if concern else "kpi-card"
    value_style = f' style="color:{value_color};"' if value_color else ""
    col.markdown(
        _md(f"""
        <div class="{card_class}" style="border-top-color:{border_color};">
            <div class="kpi-top">
                <div class="kpi-icon" style="background:{border_color}1F; color:{border_color};">{icon_html}</div>
            </div>
            <p class="kpi-label">{label}</p>
            <p class="kpi-value"{value_style}>{value}</p>
            {subtitle_html}
            {delta_html}
            {spark_html}
        </div>
        """),
        unsafe_allow_html=True,
    )


def chart_or_table(fig, data, key: str, caption: str = None, height: int = 300, table_height: int = 320):
    """Compact Graph / Table toggle for a chart section.

    Only ONE view renders at a time (default: Graph), instead of a chart
    plus a separate always-visible table — this is what keeps a page from
    ballooning in height when it holds several data-heavy sections.
    Usage:
        with panel():
            section_header(...)
            chart_or_table(fig, underlying_df, key="anomaly_trend")
    """
    view_key = f"_view_{key}"
    if view_key not in st.session_state:
        st.session_state[view_key] = "Graph"

    is_empty = data is None or (hasattr(data, "empty") and data.empty) or (hasattr(data, "__len__") and len(data) == 0)

    st.markdown('<div class="toggle-row-marker"></div>', unsafe_allow_html=True)
    b1, b2, _sp = st.columns([1, 1, 5])
    with b1:
        if st.button(
            "📊 Graph", key=f"{key}_graph_btn", width="content",
            type="primary" if st.session_state[view_key] == "Graph" else "secondary",
        ):
            st.session_state[view_key] = "Graph"
            st.rerun()
    with b2:
        if st.button(
            "📋 Table", key=f"{key}_table_btn", width="content",
            type="primary" if st.session_state[view_key] == "Table" else "secondary",
        ):
            st.session_state[view_key] = "Table"
            st.rerun()

    if is_empty:
        empty_state("No data for this selection — try widening your filters (province, disease, or date range).")
    elif st.session_state[view_key] == "Graph":
        fig.update_layout(height=height)
        st.plotly_chart(
            fig, width="stretch", key=f"{key}_fig", theme=None,
            config=PLOTLY_CONFIG,
        )
    else:
        st.dataframe(data, width="stretch", hide_index=True, height=table_height)

    if caption:
        st.caption(caption)


def empty_state(message: str = "No data for this selection."):
    """Deliberate empty-state message instead of a blank chart/table, so a
    filtered-to-nothing selection reads as "nothing matched" rather than
    looking like something broke."""
    st.markdown(
        _md(f"""
        <div class="empty-state">
            <div class="empty-state-icon">🔍</div>
            <p class="empty-state-text">{message}</p>
        </div>
        """),
        unsafe_allow_html=True,
    )


def panel():
    """Bordered card wrapper for chart/table blocks.

    Uses Streamlit's real `st.container(border=True)` (not a raw HTML
    open/close-tag pair split across two separate st.markdown calls) so the
    box genuinely encloses whatever widgets are placed inside it — charts,
    tables, buttons — instead of relying on the browser to guess how two
    disconnected HTML fragments should nest. Usage:

        with panel():
            section_header(...)
            st.plotly_chart(..., theme=None)
    """
    return st.container(border=True)
