"""
server.py
=========
Web version of the dashboard: Flask API + SQLite database + static frontend.

    python server.py      ->  http://127.0.0.1:5000

First run creates aqi.db and seeds it from data/city_day.csv (a few seconds).
Uploaded CSVs are upserted into the same table (one row per city+date), so
re-uploading overlapping data replaces rows instead of duplicating them.

All the maths is reused from air_analysis.py; this file only moves data
between SQLite, pandas and JSON.
"""

from __future__ import annotations
import json
import os
import sqlite3
import tempfile

import matplotlib
matplotlib.use("Agg")  # no GUI backend inside a web server

import pandas as pd
from flask import Flask, abort, jsonify, request, send_file
from werkzeug.utils import secure_filename

import air_analysis as aa
import visualizations as viz

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("AQI_DB", os.path.join(HERE, "aqi.db"))
SEED_CSV = os.path.join(HERE, "data", "city_day.csv")
OUT_DIR = os.path.join(HERE, "output")

# DB column -> column name used by air_analysis (order matches the table)
COLS = {"pm25": "PM2.5", "pm10": "PM10", "no2": "NO2", "so2": "SO2",
        "co": "CO", "o3": "O3", "aqi": "AQI_final", "bucket": "Bucket_calc"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    city   TEXT NOT NULL,
    date   TEXT NOT NULL,          -- YYYY-MM-DD
    pm25 REAL, pm10 REAL, no2 REAL, so2 REAL, co REAL, o3 REAL,
    aqi    REAL,                   -- dataset AQI, gaps filled by our CPCB calc
    bucket TEXT,
    PRIMARY KEY (city, date)
)"""

app = Flask(__name__, static_folder="static", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB upload cap
app.json.sort_keys = False  # keep Good->Severe, season, pollutant order


# --------------------------------------------------------------------------- #
#  Database
# --------------------------------------------------------------------------- #
def connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db(seed_csv: str | None = SEED_CSV) -> None:
    """Create the table; seed it from the bundled CSV if it is empty."""
    con = connect()
    try:
        con.execute(SCHEMA)
        empty = con.execute("SELECT 1 FROM readings LIMIT 1").fetchone() is None
    finally:
        con.close()
    if empty and seed_csv and os.path.exists(seed_csv):
        print(f"Seeding {os.path.basename(DB_PATH)} from {seed_csv} ...")
        print(f"  {import_csv(seed_csv):,} rows imported.")


def import_csv(path: str) -> int:
    """Validate + compute AQI with air_analysis, then upsert into SQLite."""
    df = aa.add_computed_aqi(aa.load_data(path))
    df = df.reindex(columns=["City", "Date", *COLS.values()])
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    rows = df.astype(object).where(df.notna(), None).values.tolist()
    con = connect()
    try:
        with con:
            con.executemany(
                f"INSERT OR REPLACE INTO readings VALUES ({','.join('?' * 10)})", rows)
    finally:
        con.close()
    return len(rows)


def load_city(city: str) -> pd.DataFrame:
    """One city's rows as the DataFrame shape air_analysis expects."""
    con = connect()
    try:
        df = pd.read_sql("SELECT * FROM readings WHERE city = ? ORDER BY date",
                         con, params=(city,), parse_dates=["date"])
    finally:
        con.close()
    if df.empty:
        abort(404, f"No data for city '{city}'.")
    df = df.rename(columns={"city": "City", "date": "Date", **COLS})
    df["Year"] = df["Date"].dt.year
    df["Month"] = df["Date"].dt.month
    df["Season"] = df["Month"].map(aa.SEASON_OF_MONTH)
    return df


def js(obj, **kw):
    """pandas object -> plain JSON-able Python (NaN becomes null)."""
    return json.loads(obj.to_json(date_format="iso", **kw))


# --------------------------------------------------------------------------- #
#  API
# --------------------------------------------------------------------------- #
@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/api/cities")
def cities():
    con = connect()
    try:
        rows = con.execute("SELECT city, COUNT(*), MIN(date), MAX(date) "
                           "FROM readings GROUP BY city ORDER BY city").fetchall()
    finally:
        con.close()
    return jsonify([dict(city=c, days=n, start=a, end=b) for c, n, a, b in rows])


@app.get("/api/cities/<city>")
def city_detail(city):
    df = load_city(city)
    heat = aa.monthly_average(df)
    corr = aa.correlation_matrix(df)
    series_cols = {"date": "Date", "aqi": "AQI_final", "pm25": "PM2.5",
                   "pm10": "PM10", "season": "Season"}
    return jsonify(
        city=city,
        days=len(df),
        aqi_days=int(df["AQI_final"].notna().sum()),
        stats=js(aa.summary_stats(df), orient="index"),
        seasonal=js(aa.seasonal_average(df)),
        buckets=js(aa.bucket_distribution(df)),
        pollutants=js(aa.pollutant_means(df)),
        heatmap=dict(years=heat.index.tolist(), months=heat.columns.tolist(),
                     z=js(heat, orient="values")),
        correlation=dict(labels=corr.columns.tolist(), z=js(corr, orient="values")),
        worst=js(aa.worst_days(df, 10), orient="records"),
        series={k: js(df[c], orient="values") for k, c in series_cols.items()},
    )


@app.get("/api/cities/<city>/report.xlsx")
def report(city):
    # secure_filename: city names come from uploaded CSVs, keep them out of paths
    path = viz.export_report(load_city(city), secure_filename(city) or "city", OUT_DIR)
    return send_file(path, as_attachment=True)


@app.post("/api/upload")
def upload():
    f = request.files.get("file")
    if not f or not f.filename.lower().endswith(".csv"):
        return jsonify(error="Attach a .csv file in the 'file' field."), 400
    fd, tmp = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        f.save(tmp)
        n = import_csv(tmp)
    except (FileNotFoundError, ValueError) as exc:
        return jsonify(error=str(exc)), 400
    finally:
        os.remove(tmp)
    return jsonify(rows=n)


@app.errorhandler(404)
def not_found(e):
    return jsonify(error=e.description), 404


@app.errorhandler(413)
def too_large(e):
    return jsonify(error="File too large (50 MB max)."), 413


init_db()

if __name__ == "__main__":
    app.run(debug=False)
