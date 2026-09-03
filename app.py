"""
app.py  —  Air Quality Analysis Dashboard (Tkinter GUI)
=======================================================
The presentation layer. It wires the compute module (air_analysis) and the
plotting module (visualizations) into a clickable desktop dashboard.

Rubric coverage from this file:
  - GUI with a Python GUI library (Tkinter + ttk)
  - file handling / exceptions surfaced as friendly dialogs
  - embeds matplotlib/seaborn figures via FigureCanvasTkAgg
  - launches the Plotly interactive chart and the Excel export

Run:  python app.py
"""

from __future__ import annotations
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import matplotlib
matplotlib.use("TkAgg")  # embed inside Tkinter
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import air_analysis as aa
import visualizations as viz

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV = os.path.join(HERE, "data", "city_day.csv")
OUT_DIR = os.path.join(HERE, "output")
DEFAULT_CITY = "Mumbai"   # change to "Pune" once a Pune CSV is loaded

# (button label, visualizations function) — drives the chart buttons.
CHART_BUILDERS = [
    ("AQI trend",            viz.fig_aqi_trend),
    ("Seasonal boxplot",     viz.fig_seasonal_box),
    ("Month × Year heatmap", viz.fig_month_year_heatmap),
    ("Pollutant averages",   viz.fig_pollutant_bar),
    ("Correlation heatmap",  viz.fig_correlation),
    ("AQI categories",       viz.fig_bucket_distribution),
]


class AirQualityApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Air Quality Analysis Dashboard")
        self.geometry("1080x680")
        self.minsize(940, 600)

        self.df = None            # full dataset (all cities)
        self.city_df = None       # current city's slice
        self.canvas = None        # current matplotlib canvas

        self._build_layout()
        # Try to auto-load the bundled dataset on startup.
        self._load_path(DEFAULT_CSV, announce=False)

    # ---------------------------------------------------------------- layout
    def _build_layout(self):
        # --- top control bar ---
        top = ttk.Frame(self, padding=8)
        top.pack(side="top", fill="x")

        ttk.Button(top, text="Load CSV…", command=self.on_load).pack(side="left")
        ttk.Label(top, text="   City:").pack(side="left")
        self.city_var = tk.StringVar()
        self.city_combo = ttk.Combobox(top, textvariable=self.city_var,
                                        state="readonly", width=20)
        self.city_combo.pack(side="left", padx=4)
        self.city_combo.bind("<<ComboboxSelected>>", lambda e: self.on_city_change())

        ttk.Button(top, text="Interactive (Plotly)",
                   command=self.on_plotly).pack(side="right")
        ttk.Button(top, text="Export Excel",
                   command=self.on_export).pack(side="right", padx=6)

        # --- main split: left = chart buttons + stats, right = chart canvas ---
        body = ttk.Frame(self, padding=(8, 0))
        body.pack(side="top", fill="both", expand=True)

        left = ttk.Frame(body, width=280)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        ttk.Label(left, text="Charts", font=("TkDefaultFont", 11, "bold")
                  ).pack(anchor="w", pady=(4, 2))
        for label, fn in CHART_BUILDERS:
            ttk.Button(left, text=label,
                       command=lambda f=fn: self.show_chart(f)
                       ).pack(fill="x", pady=2)

        ttk.Separator(left).pack(fill="x", pady=8)
        ttk.Label(left, text="Summary statistics",
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        self.stats_box = tk.Text(left, height=16, width=34, font=("Courier", 8))
        self.stats_box.pack(fill="both", expand=True, pady=4)

        self.chart_frame = ttk.Frame(body, relief="groove", borderwidth=1)
        self.chart_frame.pack(side="left", fill="both", expand=True, padx=(8, 0))

        # --- status bar ---
        self.status = tk.StringVar(value="Ready.")
        ttk.Label(self, textvariable=self.status, relief="sunken",
                  anchor="w", padding=4).pack(side="bottom", fill="x")

    # -------------------------------------------------------------- data load
    def on_load(self):
        path = filedialog.askopenfilename(
            title="Select an air-quality CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if path:
            self._load_path(path)

    def _load_path(self, path, announce=True):
        try:
            df = aa.load_data(path)
            df = aa.add_computed_aqi(df)
        except (FileNotFoundError, ValueError) as exc:
            messagebox.showerror("Could not load data", str(exc))
            self.status.set("Load failed.")
            return

        self.df = df
        cities = aa.list_cities(df)
        self.city_combo["values"] = cities
        # Prefer Pune, then the default city, else the first available.
        pick = ("Pune" if "Pune" in cities else
                DEFAULT_CITY if DEFAULT_CITY in cities else cities[0])
        self.city_var.set(pick)
        self.on_city_change()
        msg = f"Loaded {len(df):,} rows · {len(cities)} cities · {os.path.basename(path)}"
        self.status.set(msg)
        if announce:
            messagebox.showinfo("Data loaded", msg)

    def on_city_change(self):
        city = self.city_var.get()
        try:
            self.city_df = aa.city_frame(self.df, city)
        except ValueError as exc:
            messagebox.showwarning("No data", str(exc))
            return
        self._refresh_stats(city)
        self.show_chart(viz.fig_seasonal_box)  # sensible default view

    # ----------------------------------------------------------------- charts
    def show_chart(self, builder):
        if self.city_df is None:
            return
        city = self.city_var.get()
        try:
            fig = builder(self.city_df, city)
        except Exception as exc:                       # never crash the GUI
            messagebox.showerror("Chart error", f"{builder.__name__}: {exc}")
            return
        # Clear previous canvas, draw the new figure.
        for w in self.chart_frame.winfo_children():
            w.destroy()
        self.canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.status.set(f"Showing: {builder.__name__}  ({city})")

    def _refresh_stats(self, city):
        stats = aa.summary_stats(self.city_df)
        n_days = len(self.city_df)
        n_aqi = int(self.city_df["AQI_final"].notna().sum())
        self.stats_box.delete("1.0", "end")
        self.stats_box.insert("end", f"{city}\n{'-'*30}\n")
        self.stats_box.insert("end", f"days: {n_days}   AQI days: {n_aqi}\n\n")
        self.stats_box.insert("end", stats.to_string())

    # ------------------------------------------------------------- extra tools
    def on_plotly(self):
        if self.city_df is None:
            return
        try:
            path = viz.plotly_interactive(self.city_df, self.city_var.get(), OUT_DIR)
            self.status.set(f"Opened interactive chart: {os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror("Plotly error", str(exc))

    def on_export(self):
        if self.city_df is None:
            return
        try:
            path = viz.export_report(self.city_df, self.city_var.get(), OUT_DIR)
            messagebox.showinfo("Excel exported", f"Saved to:\n{path}")
            self.status.set(f"Exported: {os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror("Export error", str(exc))


if __name__ == "__main__":
    AirQualityApp().mainloop()
