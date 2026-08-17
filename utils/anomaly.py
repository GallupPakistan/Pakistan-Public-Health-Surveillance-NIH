import pandas as pd
import numpy as np


def weekly_series(df: pd.DataFrame, group_cols=("Date",)) -> pd.DataFrame:
    """Aggregate to a clean weekly time series."""
    g = df.groupby(list(group_cols), as_index=False)["Value"].sum()
    return g.sort_values("Date")


GRANULARITY_WINDOW = {"Weekly": 8, "Monthly": 6, "Yearly": 3}


def granular_series(df: pd.DataFrame, granularity: str = "Weekly") -> pd.DataFrame:
    """
    Aggregate the raw (already-filtered) records to a Weekly, Monthly, or
    Yearly time series. Same underlying `Value` sum as `weekly_series` —
    this only changes the calendar bucket, not any calculation logic.
    """
    d = df[["Date", "Value"]].copy()
    if granularity == "Monthly":
        d["Date"] = d["Date"].dt.to_period("M").dt.to_timestamp()
    elif granularity == "Yearly":
        d["Date"] = d["Date"].dt.to_period("Y").dt.to_timestamp()
    g = d.groupby("Date", as_index=False)["Value"].sum()
    return g.sort_values("Date")


def add_control_limits(ts: pd.DataFrame, window: int = 8, n_std: float = 2.0) -> pd.DataFrame:
    """
    Adds a rolling mean/std control band and flags points outside it.
    This mirrors the classic Shewhart control-chart approach used in
    real disease-surveillance systems (a simpler cousin of full CUSUM/EWMA).
    """
    ts = ts.copy()
    ts["rolling_mean"] = ts["Value"].rolling(window, min_periods=3).mean()
    ts["rolling_std"] = ts["Value"].rolling(window, min_periods=3).std().fillna(0)
    ts["upper"] = ts["rolling_mean"] + n_std * ts["rolling_std"]
    ts["lower"] = (ts["rolling_mean"] - n_std * ts["rolling_std"]).clip(lower=0)
    ts["is_anomaly"] = ts["Value"] > ts["upper"]
    return ts


def add_ewma(ts: pd.DataFrame, span: int = 6, n_std: float = 2.5) -> pd.DataFrame:
    ts = ts.copy()
    ts["ewma"] = ts["Value"].ewm(span=span, adjust=False).mean()
    resid_std = (ts["Value"] - ts["ewma"]).std()
    ts["ewma_upper"] = ts["ewma"] + n_std * resid_std
    ts["ewma_anomaly"] = ts["Value"] > ts["ewma_upper"]
    return ts


def naive_forecast(ts: pd.DataFrame, periods: int = 4) -> pd.DataFrame:
    """
    Lightweight forecast: recent trend + seasonal-naive blend.
    Deliberately dependency-free (no statsmodels/prophet) so it runs
    anywhere without extra installs.
    """
    ts = ts.sort_values("Date").reset_index(drop=True)
    recent = ts["Value"].tail(8).mean()
    trend = ts["Value"].tail(4).mean() - ts["Value"].tail(8).head(4).mean()
    last_date = ts["Date"].max()
    future_dates = [last_date + pd.Timedelta(weeks=i) for i in range(1, periods + 1)]
    future_vals = [max(recent + trend * i / periods, 0) for i in range(1, periods + 1)]
    return pd.DataFrame({"Date": future_dates, "Value": future_vals, "type": "forecast"})


def epi_week_baseline(df: pd.DataFrame, min_history_years: int = 2):
    """
    Builds a WHO-style "endemic channel": for each epidemiological week
    (1-52), computes the historical mean/std of case counts from every
    prior year in the filtered data, then classifies the most recent
    year's weeks against that baseline:
      - Normal   : actual <= mean + 1 SD
      - Alert    : mean + 1 SD < actual <= mean + 2 SD
      - Epidemic : actual > mean + 2 SD
    This is the same logic behind classic epidemic-channel charts used in
    real surveillance bulletins (a calendar-aware alternative to the
    rolling-window control chart, since it compares each week only
    against the *same week* in prior years rather than recent weeks).

    Returns (current_year, n_history_years, weekly_df). weekly_df has
    columns: Week, Actual, hist_mean, hist_std, alert_threshold,
    epidemic_threshold, status.
    """
    empty = pd.DataFrame(columns=[
        "Week", "Actual", "hist_mean", "hist_std",
        "alert_threshold", "epidemic_threshold", "status",
    ])
    if df is None or df.empty:
        return None, 0, empty

    g = df.groupby(["Year", "Week"], as_index=False)["Value"].sum()
    current_year = int(g["Year"].max())
    hist = g[g["Year"] < current_year]
    n_history_years = hist["Year"].nunique()

    cur = (
        g[g["Year"] == current_year][["Week", "Value"]]
        .rename(columns={"Value": "Actual"})
        .sort_values("Week")
    )

    if n_history_years < min_history_years:
        cur["hist_mean"] = None
        cur["hist_std"] = None
        cur["alert_threshold"] = None
        cur["epidemic_threshold"] = None
        cur["status"] = "No baseline"
        return current_year, n_history_years, cur

    baseline = hist.groupby("Week")["Value"].agg(["mean", "std"]).reset_index()
    baseline.columns = ["Week", "hist_mean", "hist_std"]
    baseline["hist_std"] = baseline["hist_std"].fillna(0)
    baseline["alert_threshold"] = baseline["hist_mean"] + 1.0 * baseline["hist_std"]
    baseline["epidemic_threshold"] = baseline["hist_mean"] + 2.0 * baseline["hist_std"]

    merged = cur.merge(baseline, on="Week", how="left").sort_values("Week")

    def _classify(row):
        if pd.isna(row["hist_mean"]):
            return "No baseline"
        if row["Actual"] > row["epidemic_threshold"]:
            return "Epidemic"
        if row["Actual"] > row["alert_threshold"]:
            return "Alert"
        return "Normal"

    merged["status"] = merged.apply(_classify, axis=1)
    return current_year, n_history_years, merged
