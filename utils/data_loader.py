import os
import pandas as pd
import streamlit as st

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# Approximate district centroids for the districts that appear most often
# in the dataset. Used for the bubble/geo map since a full shapefile join
# is out of scope for a v1 build.
DISTRICT_COORDS = {
    "Karachi East": (24.8608, 67.1414), "Karachi Malir": (24.8969, 67.2278),
    "Karachi Central": (24.9265, 67.0822), "Karachi South": (24.8500, 67.0281),
    "Karachi West": (24.9056, 66.9700), "Hyderabad": (25.3960, 68.3578),
    "Larkana": (27.5590, 68.2120), "Khairpur": (27.5295, 68.7593),
    "Sukkur": (27.7052, 68.8574), "Shikarpur": (27.9556, 68.6382),
    "Ghotki": (28.0079, 69.3153), "Tharparkar": (24.8890, 70.2600),
    "Badin": (24.6560, 68.8380), "Dadu": (26.7314, 67.7750),
    "Mirpurkhas": (25.5266, 69.0113), "Thatta": (24.7461, 67.9243),
    "Quetta": (30.1798, 66.9750), "Kech": (26.0154, 62.8228),
    "Gwadar": (25.1264, 62.3225), "Lasbela": (25.8686, 66.7133),
    "Pishin": (30.5828, 66.9959), "Khuzdar": (27.7284, 66.6428),
    "Jaffarabad": (28.2870, 68.2850), "Qilla Abdullah": (30.6383, 66.5836),
    "Usta Muhammad": (28.1667, 68.0333),
    "Peshawar": (34.0151, 71.5249), "Swat": (34.7717, 72.3604),
    "Charsadda": (34.1454, 71.7448), "Swabi": (34.1200, 72.4700),
    "Bannu": (32.9855, 70.6025), "Haripur": (33.9966, 72.9377),
    "Kohat": (33.5820, 71.4420), "Abbottabad": (34.1463, 73.2117),
    "Lakki Marwat": (32.6079, 70.9114),
    "Faisalabad": (31.4180, 73.0790), "Lahore": (31.5497, 74.3436),
    "Muzaffargarh": (30.0730, 71.1930), "Gujranwala": (32.1877, 74.1945),
    "Multan": (30.1575, 71.5249), "Attock": (33.7666, 72.3600),
}



# ---------------------------------------------------------------------
# Province populations — 2023 Pakistan digital census (approximate,
# rounded to the nearest 0.1M). Used only to convert raw case counts
# into population-adjusted rates (cases per 100,000 people) so that a
# large province isn't automatically read as "worse" than a small one.
# Source: Pakistan Bureau of Statistics, 2023 census provisional results.
# NOTE: this is province-level only — district-level population figures
# are not included here because we don't have a verified source for all
# 147 districts. If you have an official district population file, add
# a `District -> population` dict here and swap it in on the Geography
# page instead of the province-level one.
# ---------------------------------------------------------------------
PROVINCE_POPULATION = {
    "Punjab": 127_700_000,
    "Sindh": 55_700_000,
    "KP": 40_900_000,
    "Balochistan": 14_900_000,
}


def cases_per_100k(cases: float, province: str) -> float:
    """Population-adjusted rate. Returns None if the province isn't in the lookup."""
    pop = PROVINCE_POPULATION.get(province)
    if not pop:
        return None
    return cases / pop * 100_000


@st.cache_data(ttl=3600, show_spinner="Loading surveillance data...")
def load_core() -> pd.DataFrame:
    return pd.read_parquet(os.path.join(DATA_DIR, "core.parquet"))


@st.cache_data(ttl=3600, show_spinner=False)
def load_reporting() -> pd.DataFrame:
    return pd.read_parquet(os.path.join(DATA_DIR, "reporting.parquet"))


@st.cache_data(ttl=3600, show_spinner=False)
def filtered(df: pd.DataFrame, provinces, diseases, categories, date_range) -> pd.DataFrame:
    out = df
    if provinces:
        out = out[out["Province"].isin(provinces)]
    if diseases:
        out = out[out["Clean Disease"].isin(diseases)]
    if categories:
        out = out[out["Category"].isin(categories)]
    if date_range:
        start, end = date_range
        out = out[(out["Date"] >= pd.Timestamp(start)) & (out["Date"] <= pd.Timestamp(end))]
    return out


def kpi_numbers(df: pd.DataFrame) -> dict:
    return {
        "total_cases": int(df["Value"].sum()),
        "diseases": df["Clean Disease"].nunique(),
        "districts": df["District"].nunique(),
        "weeks": df["Date"].nunique(),
    }


def previous_period_df(core: pd.DataFrame, provinces, diseases, categories, date_range) -> pd.DataFrame:
    """
    Same filters as `filtered()`, but shifted to the immediately-preceding
    window of equal length. Used only to compute the +/- % deltas shown
    on the KPI cards — does not change any existing filtering logic.
    """
    if not date_range:
        return core.iloc[0:0]
    start, end = date_range
    span_days = (pd.Timestamp(end) - pd.Timestamp(start)).days + 1
    prev_end = pd.Timestamp(start) - pd.Timedelta(days=1)
    prev_start = prev_end - pd.Timedelta(days=span_days - 1)
    return filtered(core, provinces, diseases, categories, (prev_start.date(), prev_end.date()))


def pct_delta(current: float, previous: float):
    """Returns (formatted_string, direction) for a KPI delta badge."""
    if not previous:
        return None, "flat"
    change = (current - previous) / previous * 100
    direction = "up" if change > 0.5 else ("down" if change < -0.5 else "flat")
    arrow = "▲" if direction == "up" else ("▼" if direction == "down" else "▬")
    return f"{arrow} {abs(change):.1f}% vs prior period", direction
