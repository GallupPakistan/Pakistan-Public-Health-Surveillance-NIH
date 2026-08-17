"""
Run once to convert merge_file_cleaned.xlsx into fast-loading parquet files.
Usage: python prepare_data.py
"""
import pandas as pd
import numpy as np
import os

SRC = os.path.join(os.path.dirname(__file__), "data", "merge_file_cleaned.xlsx")
OUT = os.path.join(os.path.dirname(__file__), "data")

# ---------------------------------------------------------------------------
# Disease -> category mapping (used for treemap / category filters)
# ---------------------------------------------------------------------------
DISEASE_CATEGORY = {
    "AD (Acute Diarrhea, Non-Cholera)": "Waterborne",
    "AWD (Acute Watery Diarrhea, Suspected Cholera)": "Waterborne",
    "B. Diarrhea (Bloody Diarrhea)": "Waterborne",
    "Typhoid": "Waterborne",
    "AVH (Acute Viral Hepatitis, A & E)": "Waterborne",
    "VH (Viral Hepatitis B, C & D)": "Bloodborne",
    "ALRI (Acute Lower Respiratory Infection, <5 years)": "Respiratory",
    "ILI (Influenza-like Illness)": "Respiratory",
    "SARI (Severe Acute Respiratory Infection)": "Respiratory",
    "TB (Tuberculosis)": "Respiratory",
    "Measles": "Respiratory",
    "Malaria": "Vector-borne",
    "Dengue": "Vector-borne",
    "CL (Cutaneous Leishmaniasis)": "Vector-borne",
    "Dog/Animal Bite (Rabies)": "Zoonotic",
}

def categorize(disease: str) -> str:
    return DISEASE_CATEGORY.get(disease, "Other / neglected tropical")


def week_to_date(year: int, week: int) -> pd.Timestamp:
    # ISO-week based approximation, good enough for monthly/seasonal aggregation
    try:
        return pd.Timestamp.fromisocalendar(int(year), int(week), 1)
    except Exception:
        return pd.NaT


def main():
    xls = pd.ExcelFile(SRC)

    frames = []
    for sheet, prov_col in [
        ("province wise", "Province"),
        ("Sindh District", "Province"),
        ("KP District wise", "Province"),
        ("Balochistan District wise", "Province"),
    ]:
        df = pd.read_excel(xls, sheet)
        col = "District" if "District" in df.columns else "Attribute"
        df = df.rename(columns={col: "District"})
        df = df[["Year", "Week", "Disease", "Clean Disease", "District", "Value", prov_col]]
        df = df.rename(columns={prov_col: "Province"})
        frames.append(df)

    # Punjab (sparse, attribute = district)
    punjab = pd.read_excel(xls, "Punjab District wise")
    punjab = punjab.rename(columns={"Attribute": "District", "Diseases": "Disease"})
    punjab["Clean Disease"] = punjab["Disease"]
    punjab["Province"] = "Punjab"
    punjab = punjab[["Year", "Week", "Disease", "Clean Disease", "District", "Value", "Province"]]
    frames.append(punjab)

    core = pd.concat(frames, ignore_index=True)
    core["Value"] = pd.to_numeric(core["Value"], errors="coerce").fillna(0)
    core["Province"] = core["Province"].replace({"Khyber Pakhtunkhwa": "KP"})
    core["Category"] = core["Clean Disease"].map(categorize)
    core["Date"] = core.apply(lambda r: week_to_date(r["Year"], r["Week"]), axis=1)
    core["Month"] = core["Date"].dt.month
    core["MonthName"] = core["Date"].dt.strftime("%b")

    core.to_parquet(os.path.join(OUT, "core.parquet"), index=False)

    # Reporting quality sheet
    rep = pd.read_excel(xls, "IDSR reporting districts")
    rep["Province"] = rep["Province"].replace({"Khyber Pakhtunkhwa": "KP"})
    rep.to_parquet(os.path.join(OUT, "reporting.parquet"), index=False)

    print("core rows:", len(core))
    print("reporting rows:", len(rep))
    print("provinces:", core.Province.unique())
    print("categories:", core.Category.unique())
    print("date range:", core.Date.min(), "-", core.Date.max())


if __name__ == "__main__":
    main()
