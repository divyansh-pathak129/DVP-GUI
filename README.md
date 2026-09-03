# Air Quality Analysis Dashboard (DVP mini-project)

A Python desktop app that loads real CPCB air-quality data, computes AQI &
seasonal statistics with pandas/numpy, and visualises everything with
matplotlib, seaborn and plotly — wrapped in a Tkinter GUI.

Ships working out-of-the-box on **Mumbai** (the Maharashtra city present in
the CPCB dataset). It is **city-agnostic**: the moment you load a CSV that
contains Pune rows, "Pune" appears in the dropdown and every chart works.
See *"Getting real Pune data"* below.

---

## 1. Setup & run

```bash
pip install -r requirements.txt          # Linux also: sudo apt install python3-tk
python app.py
```

The app auto-loads `data/city_day.csv` and opens on Mumbai. Use the **City**
dropdown to switch cities, the left buttons to draw charts, **Interactive
(Plotly)** to open a zoomable browser chart, and **Export Excel** for a
multi-sheet report.

---

## 2. Files

| File | Owner (suggested) | What it does |
|------|-------------------|--------------|
| `air_analysis.py` | Member A (data/compute) | Load CSV, exception handling, seasons, CPCB **AQI formula in numpy**, all aggregations |
| `visualizations.py` | Member B (matplotlib/seaborn) + Member C (plotly/Excel) | Every figure; interactive HTML; `.xlsx` export |
| `app.py` | Member D (GUI) | Tkinter dashboard wiring it together |
| `README.md` / slides | Member E (docs + presentation) | This file, findings, demo script |
| `data/city_day.csv` | — | Real CPCB data, 26 cities, 2015–2020 |
| `sample_charts/` | — | Slide-ready PNGs (no need to run anything) |

That's a clean 5-way split — one bullet per member for the "who did what" slide.

---

## 3. How the rubric is covered

- **GUI (Tkinter):** `app.py` — dropdown, buttons, embedded charts, file dialog, status bar.
- **numpy / pandas + control structures, functions, file handling, exceptions:**
  `air_analysis.py` — `load_data` guards missing/empty/wrong-schema files;
  `_sub_index` / `compute_aqi_row` implement the real CPCB AQI math; season
  mapping, pivots, groupbys throughout.
- **Visualisation:** matplotlib (trend, bar, categories), seaborn (correlation
  heatmap, seasonal boxplot, month×year heatmap), plotly (interactive
  time-series), Excel (`export_report` → 5-sheet `.xlsx`).

---

## 4. Getting real Pune data (optional, for a literal "Pune" title)

Pune is **not** in Kaggle's `city_day.csv`, but real Pune history exists. Two
routes — the app needs a CSV with at least `City`, `Date`, and pollutant
columns (`PM2.5, PM10, NO2, SO2, CO, O3`); an `AQI` column is optional.

**Route A — Kaggle `station_day.csv` (same dataset family):**
1. Download *Air Quality Data in India (2015–2020)* by Rohan Rao from Kaggle
   (files `station_day.csv` + `stations.csv`).
2. In `stations.csv`, Pune stations include `site_292` (Karve Road – MPCB) and
   `site_5404–5410` (IITM). Filter `station_day.csv` to those `StationId`s,
   add a `City = "Pune"` column, rename `StationId`→drop, and save as
   `data/pune.csv`.
3. Load it in the app → "Pune" appears in the dropdown.

**Route B — WAQI data platform (aqicn.org/data-platform/covid19):**
Accept the terms, download the historical city CSV, keep Pune's rows, rename
columns to match (`median`→pollutant), add `City = "Pune"`, save and load.

A tiny `merge_pune.py` helper is trivial to add once you pick a route — ask if
you want it.

---

## 5. Key findings (Mumbai — use these on your analysis slide)

- **Strong seasonality:** AQI is worst in **Winter (~163 avg)** and cleanest in
  **Monsoon (~69 avg)** — rain washes out particulates; winter inversions trap them.
- **PM10 is the dominant pollutant** by average concentration; PM2.5/PM10 drive
  the AQI on the worst days (visible in the correlation heatmap).
- The **month×year heatmap** shows Jan/Feb/Dec consistently red across years —
  a repeatable winter pollution peak, not a one-off.
- AQI mostly sits in **Satisfactory/Moderate**, with a handful of Poor days —
  Mumbai's coastal winds keep it below inland cities like Delhi (available in
  the dropdown as a data-rich contrast).

> Note: the AQI values we plot use the dataset's AQI where present and **our own
> CPCB sub-index calculation** to fill gaps — a good point to raise in the viva.

---

## 6. Demo script (2 min)

1. Launch → app opens on Mumbai. Point out rows/cities loaded in the status bar.
2. Click **Seasonal boxplot** → explain the winter-vs-monsoon story.
3. Click **Month × Year heatmap** → the repeatable winter peak.
4. Click **Correlation heatmap** → PM drives AQI.
5. **Interactive (Plotly)** → zoom into 2019 in the browser.
6. **Export Excel** → open the `.xlsx`, show the sheets.
7. Switch dropdown to **Delhi** → same code, dramatically worse air (contrast).
