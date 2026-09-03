"""
visualizations.py
=================
All plotting lives here so the GUI stays clean.

Covers the "visualisation" rubric points:
  - matplotlib : trend line, pollutant bar, bucket distribution
  - seaborn    : correlation heatmap, seasonal boxplot, month x year heatmap
  - plotly     : interactive time-series (opens in the browser)
  - Excel      : export_report() writes a multi-sheet .xlsx

Every matplotlib/seaborn function returns a Figure, so the Tkinter app can
embed it with FigureCanvasTkAgg. Nothing here calls plt.show().
"""

from __future__ import annotations
import os
import webbrowser

import numpy as np
import pandas as pd
import matplotlib
from matplotlib.figure import Figure
import seaborn as sns

import air_analysis as aa

sns.set_theme(style="whitegrid")

SEASON_ORDER = ["Winter", "Summer", "Monsoon", "Post-Monsoon"]
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# --------------------------------------------------------------------------- #
#  Matplotlib figures
# --------------------------------------------------------------------------- #
def fig_aqi_trend(df_city: pd.DataFrame, city: str) -> Figure:
    """AQI over time with a 30-day rolling average."""
    fig = Figure(figsize=(7, 4.2), dpi=100)
    ax = fig.add_subplot(111)
    d = df_city.dropna(subset=["AQI_final"])
    ax.plot(d["Date"], d["AQI_final"], color="#9ecae1", lw=0.8,
            alpha=0.7, label="Daily AQI")
    roll = d.set_index("Date")["AQI_final"].rolling("30D").mean()
    ax.plot(roll.index, roll.values, color="#08519c", lw=2,
            label="30-day average")
    ax.set_title(f"{city} — AQI trend (2015–2020)")
    ax.set_xlabel("Date"); ax.set_ylabel("AQI")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    return fig


def fig_pollutant_bar(df_city: pd.DataFrame, city: str) -> Figure:
    """Average concentration per pollutant."""
    means = aa.pollutant_means(df_city)
    fig = Figure(figsize=(7, 4.2), dpi=100)
    ax = fig.add_subplot(111)
    colors = sns.color_palette("viridis", len(means))
    ax.bar(means.index, means.values, color=colors)
    ax.set_title(f"{city} — average pollutant levels")
    ax.set_ylabel("Concentration (µg/m³, CO in mg/m³)")
    for i, v in enumerate(means.values):
        ax.text(i, v, f"{v:.1f}", ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    return fig


def fig_bucket_distribution(df_city: pd.DataFrame, city: str) -> Figure:
    """How many days fall in each AQI category."""
    counts = aa.bucket_distribution(df_city)
    palette = {"Good": "#2ecc71", "Satisfactory": "#a3d977", "Moderate": "#f1c40f",
               "Poor": "#e67e22", "Very Poor": "#e74c3c", "Severe": "#8e44ad"}
    fig = Figure(figsize=(7, 4.2), dpi=100)
    ax = fig.add_subplot(111)
    ax.bar(counts.index, counts.values,
           color=[palette.get(b, "#888") for b in counts.index])
    ax.set_title(f"{city} — days in each AQI category")
    ax.set_ylabel("Number of days")
    ax.tick_params(axis="x", rotation=20)
    for i, v in enumerate(counts.values):
        ax.text(i, v, str(v), ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------- #
#  Seaborn figures
# --------------------------------------------------------------------------- #
def fig_correlation(df_city: pd.DataFrame, city: str) -> Figure:
    """Heatmap of correlations between pollutants and AQI."""
    corr = aa.correlation_matrix(df_city)
    fig = Figure(figsize=(6.5, 5.2), dpi=100)
    ax = fig.add_subplot(111)
    sns.heatmap(corr, annot=True, cmap="coolwarm", center=0,
                fmt=".2f", square=True, cbar_kws={"shrink": .8}, ax=ax)
    ax.set_title(f"{city} — pollutant / AQI correlation")
    fig.tight_layout()
    return fig


def fig_seasonal_box(df_city: pd.DataFrame, city: str) -> Figure:
    """Boxplot of AQI by season — the core 'seasonal trend' visual."""
    d = df_city.dropna(subset=["AQI_final"])
    fig = Figure(figsize=(7, 4.2), dpi=100)
    ax = fig.add_subplot(111)
    sns.boxplot(data=d, x="Season", y="AQI_final", order=SEASON_ORDER,
                hue="Season", palette="YlOrRd", legend=False, ax=ax)
    ax.set_title(f"{city} — AQI distribution by season")
    ax.set_xlabel("Season"); ax.set_ylabel("AQI")
    fig.tight_layout()
    return fig


def fig_month_year_heatmap(df_city: pd.DataFrame, city: str) -> Figure:
    """Year x Month heatmap of average AQI (seasonality at a glance)."""
    pivot = aa.monthly_average(df_city, "AQI_final")
    pivot.columns = [MONTH_LABELS[m - 1] for m in pivot.columns]
    fig = Figure(figsize=(7.5, 4.4), dpi=100)
    ax = fig.add_subplot(111)
    sns.heatmap(pivot, annot=True, fmt=".0f", cmap="YlOrRd",
                linewidths=.5, cbar_kws={"label": "Avg AQI"}, ax=ax)
    ax.set_title(f"{city} — average AQI by month and year")
    ax.set_xlabel("Month"); ax.set_ylabel("Year")
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------- #
#  Plotly (interactive, opens in browser)
# --------------------------------------------------------------------------- #
def plotly_interactive(df_city: pd.DataFrame, city: str,
                       out_dir: str) -> str:
    """Write an interactive AQI + pollutant time-series to HTML and open it.

    Returns the path to the generated HTML file.
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    d = df_city.sort_values("Date")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=d["Date"], y=d["AQI_final"], name="AQI",
                             line=dict(color="#08519c", width=1.5)),
                  secondary_y=False)
    for p, col in [("PM2.5", "#e74c3c"), ("PM10", "#e67e22")]:
        if p in d.columns:
            fig.add_trace(go.Scatter(x=d["Date"], y=d[p], name=p,
                                     line=dict(width=1), opacity=0.6),
                          secondary_y=True)
    fig.update_layout(title=f"{city} — interactive air-quality time series",
                      hovermode="x unified", template="plotly_white",
                      legend=dict(orientation="h"))
    fig.update_yaxes(title_text="AQI", secondary_y=False)
    fig.update_yaxes(title_text="PM concentration (µg/m³)", secondary_y=True)

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{city}_interactive.html")
    fig.write_html(path, include_plotlyjs="cdn")
    try:
        webbrowser.open("file://" + os.path.abspath(path))
    except Exception:
        pass
    return path


# --------------------------------------------------------------------------- #
#  Excel export
# --------------------------------------------------------------------------- #
def export_report(df_city: pd.DataFrame, city: str, out_dir: str) -> str:
    """Write a multi-sheet Excel report. Returns the file path."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{city}_air_quality_report.xlsx")
    with pd.ExcelWriter(path, engine="openpyxl") as xl:
        aa.summary_stats(df_city).to_excel(xl, sheet_name="Summary stats")
        aa.seasonal_average(df_city).to_frame("Avg AQI").to_excel(
            xl, sheet_name="Seasonal AQI")
        aa.monthly_average(df_city).to_excel(xl, sheet_name="Month x Year AQI")
        aa.bucket_distribution(df_city).to_frame("Days").to_excel(
            xl, sheet_name="AQI categories")
        aa.worst_days(df_city, 15).to_excel(
            xl, sheet_name="Worst days", index=False)
    return path


# --------------------------------------------------------------------------- #
#  Headless self-test: render every figure to PNG so we know they work.
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    matplotlib.use("Agg")
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "_test_output")
    os.makedirs(out, exist_ok=True)

    df = aa.add_computed_aqi(aa.load_data(os.path.join(here, "data", "city_day.csv")))
    cdf = aa.city_frame(df, "Mumbai")

    builders = {
        "trend": fig_aqi_trend, "pollutant_bar": fig_pollutant_bar,
        "buckets": fig_bucket_distribution, "correlation": fig_correlation,
        "seasonal_box": fig_seasonal_box, "month_year": fig_month_year_heatmap,
    }
    for name, fn in builders.items():
        f = fn(cdf, "Mumbai")
        f.savefig(os.path.join(out, f"{name}.png"))
        print("saved", name)

    xls = export_report(cdf, "Mumbai", out)
    print("excel:", os.path.basename(xls))
