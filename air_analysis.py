"""
air_analysis.py
================
Data-loading and computation layer for the Air Quality Analysis project.

Covers the "computation" rubric points:
  - file handling + exception handling  (load_data)
  - control structures + functions      (throughout)
  - numpy + pandas                      (throughout)
  - a real CPCB AQI implementation      (compute_aqi_row / add_computed_aqi)

Everything here is pure logic and returns pandas objects, so it can be
unit-tested on its own and reused by both the GUI and the plotting module.
"""

from __future__ import annotations
import os
import numpy as np
import pandas as pd

# Pollutant columns we care about (must exist in the CSV)
POLLUTANTS = ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"]

# Map calendar month -> Indian season (used for seasonal analysis)
SEASON_OF_MONTH = {
    12: "Winter", 1: "Winter", 2: "Winter",
    3: "Summer", 4: "Summer", 5: "Summer",
    6: "Monsoon", 7: "Monsoon", 8: "Monsoon", 9: "Monsoon",
    10: "Post-Monsoon", 11: "Post-Monsoon",
}

# CPCB AQI sub-index breakpoints: pollutant -> list of
# (C_low, C_high, I_low, I_high). Concentrations in the CPCB reference units.
_BREAKPOINTS = {
    "PM2.5": [(0, 30, 0, 50), (30, 60, 51, 100), (60, 90, 101, 200),
              (90, 120, 201, 300), (120, 250, 301, 400), (250, 500, 401, 500)],
    "PM10":  [(0, 50, 0, 50), (50, 100, 51, 100), (100, 250, 101, 200),
              (250, 350, 201, 300), (350, 430, 301, 400), (430, 600, 401, 500)],
    "NO2":   [(0, 40, 0, 50), (40, 80, 51, 100), (80, 180, 101, 200),
              (180, 280, 201, 300), (280, 400, 301, 400), (400, 500, 401, 500)],
    "SO2":   [(0, 40, 0, 50), (40, 80, 51, 100), (80, 380, 101, 200),
              (380, 800, 201, 300), (800, 1600, 301, 400), (1600, 2000, 401, 500)],
    "CO":    [(0, 1.0, 0, 50), (1.0, 2.0, 51, 100), (2.0, 10, 101, 200),
              (10, 17, 201, 300), (17, 34, 301, 400), (34, 50, 401, 500)],
    "O3":    [(0, 50, 0, 50), (50, 100, 51, 100), (100, 168, 101, 200),
              (168, 208, 201, 300), (208, 748, 301, 400), (748, 1000, 401, 500)],
}

# AQI value -> descriptive bucket (CPCB categories)
_AQI_BUCKETS = [
    (0, 50, "Good"), (51, 100, "Satisfactory"), (101, 200, "Moderate"),
    (201, 300, "Poor"), (301, 400, "Very Poor"), (401, 10_000, "Severe"),
]


# --------------------------------------------------------------------------- #
#  File handling
# --------------------------------------------------------------------------- #
def load_data(path: str) -> pd.DataFrame:
    """Load the air-quality CSV with defensive error handling.

    Demonstrates file handling + exceptions: missing file, empty file,
    and wrong schema are all reported with clear messages instead of
    crashing the GUI.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dataset not found at: {path}")

    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        raise ValueError("The CSV file is empty.")
    except Exception as exc:  # malformed rows, encoding issues, etc.
        raise ValueError(f"Could not read CSV: {exc}")

    required = {"City", "Date"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing required column(s): {missing}")

    # Parse dates; drop rows where the date is unusable.
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).copy()

    # Derived time columns used everywhere downstream.
    df["Year"] = df["Date"].dt.year
    df["Month"] = df["Date"].dt.month
    df["MonthName"] = df["Date"].dt.strftime("%b")
    df["Season"] = df["Month"].map(SEASON_OF_MONTH)
    return df


def list_cities(df: pd.DataFrame) -> list[str]:
    """Return the sorted list of cities available in the dataset."""
    return sorted(df["City"].dropna().unique().tolist())


def city_frame(df: pd.DataFrame, city: str) -> pd.DataFrame:
    """Slice the data for one city, sorted by date."""
    sub = df[df["City"] == city].sort_values("Date").copy()
    if sub.empty:
        raise ValueError(f"No rows found for city '{city}'.")
    return sub


# --------------------------------------------------------------------------- #
#  CPCB AQI computation (numpy math)
# --------------------------------------------------------------------------- #
def _sub_index(concentration: float, pollutant: str) -> float:
    """Linear-interpolate a single pollutant's AQI sub-index."""
    if pd.isna(concentration) or concentration < 0:
        return np.nan
    for c_lo, c_hi, i_lo, i_hi in _BREAKPOINTS[pollutant]:
        if c_lo <= concentration <= c_hi:
            # Standard CPCB linear interpolation inside the band.
            return ((i_hi - i_lo) / (c_hi - c_lo)) * (concentration - c_lo) + i_lo
    return 500.0  # above the top band -> capped at Severe


def compute_aqi_row(row: pd.Series) -> float:
    """Overall AQI for one row = max of available pollutant sub-indices.

    CPCB requires at least three pollutants (incl. one of PM2.5/PM10);
    we enforce that minimum and otherwise return NaN.
    """
    subs = []
    have_pm = False
    for p in POLLUTANTS:
        if p in row and not pd.isna(row[p]):
            si = _sub_index(row[p], p)
            if not np.isnan(si):
                subs.append(si)
                if p in ("PM2.5", "PM10"):
                    have_pm = True
    if len(subs) >= 3 and have_pm:
        return float(np.max(subs))
    return np.nan


def aqi_bucket(aqi: float) -> str:
    """Map a numeric AQI to its CPCB descriptive category."""
    if pd.isna(aqi):
        return "Unknown"
    for lo, hi, name in _AQI_BUCKETS:
        if lo <= aqi <= hi:
            return name
    return "Unknown"


def add_computed_aqi(df: pd.DataFrame) -> pd.DataFrame:
    """Add AQI_calc / Bucket_calc columns, and a merged AQI_final.

    AQI_final prefers the dataset's own AQI value and falls back to our
    computed value, which meaningfully increases coverage for cities
    (like Mumbai) where the AQI column is sparse.
    """
    out = df.copy()
    out["AQI_calc"] = out.apply(compute_aqi_row, axis=1)
    if "AQI" in out.columns:
        out["AQI_final"] = out["AQI"].fillna(out["AQI_calc"])
    else:
        out["AQI_final"] = out["AQI_calc"]
    out["Bucket_calc"] = out["AQI_final"].apply(aqi_bucket)
    return out


# --------------------------------------------------------------------------- #
#  Aggregations used by the visualisations / GUI tables
# --------------------------------------------------------------------------- #
def summary_stats(df_city: pd.DataFrame) -> pd.DataFrame:
    """Descriptive stats (mean/std/min/max/median) per pollutant + AQI."""
    cols = [c for c in POLLUTANTS + ["AQI_final"] if c in df_city.columns]
    stats = df_city[cols].agg(["mean", "std", "min", "max", "median"]).T
    return stats.round(2)


def monthly_average(df_city: pd.DataFrame, column: str = "AQI_final") -> pd.DataFrame:
    """Year x Month pivot of the given column's mean (for the heatmap)."""
    pivot = df_city.pivot_table(index="Year", columns="Month",
                                values=column, aggfunc="mean")
    return pivot.round(1)


def seasonal_average(df_city: pd.DataFrame, column: str = "AQI_final") -> pd.Series:
    """Mean value of `column` per season, ordered naturally."""
    order = ["Winter", "Summer", "Monsoon", "Post-Monsoon"]
    grp = df_city.groupby("Season")[column].mean().reindex(order)
    return grp.round(1)


def pollutant_means(df_city: pd.DataFrame) -> pd.Series:
    """Average concentration of each pollutant (for the comparison bar chart)."""
    cols = [c for c in POLLUTANTS if c in df_city.columns]
    return df_city[cols].mean().round(2)


def correlation_matrix(df_city: pd.DataFrame) -> pd.DataFrame:
    """Correlation between pollutants + AQI (for the seaborn heatmap)."""
    cols = [c for c in POLLUTANTS + ["AQI_final"] if c in df_city.columns]
    return df_city[cols].corr().round(2)


def bucket_distribution(df_city: pd.DataFrame) -> pd.Series:
    """Count of days in each AQI category, ordered from Good -> Severe."""
    order = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]
    counts = df_city["Bucket_calc"].value_counts()
    return counts.reindex([b for b in order if b in counts.index]).fillna(0).astype(int)


def worst_days(df_city: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """The n most-polluted days by AQI (nice for a GUI table / slide)."""
    cols = ["Date", "AQI_final", "Bucket_calc", "PM2.5", "PM10"]
    cols = [c for c in cols if c in df_city.columns]
    return (df_city.dropna(subset=["AQI_final"])
                   .nlargest(n, "AQI_final")[cols]
                   .reset_index(drop=True))


# --------------------------------------------------------------------------- #
#  Quick self-test when run directly
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    data = load_data(os.path.join(here, "data", "city_day.csv"))
    data = add_computed_aqi(data)
    city = "Mumbai"
    cdf = city_frame(data, city)
    print(f"== {city} ==  rows={len(cdf)}  "
          f"AQI(original)={cdf['AQI'].notna().sum()}  "
          f"AQI(final)={cdf['AQI_final'].notna().sum()}")
    print("\nSeasonal AQI:\n", seasonal_average(cdf).to_string())
    print("\nBucket distribution:\n", bucket_distribution(cdf).to_string())
    print("\nPollutant means:\n", pollutant_means(cdf).to_string())
