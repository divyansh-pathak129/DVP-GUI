"""Smoke test for the web backend: python test_server.py"""
import io
import os
import tempfile

os.environ["AQI_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
import server  # noqa: E402  (seeds the temp DB from data/city_day.csv)

c = server.app.test_client()

cities = c.get("/api/cities").get_json()
assert any(x["city"] == "Mumbai" for x in cities), cities

d = c.get("/api/cities/Mumbai").get_json()
assert d["days"] > 1000 and d["seasonal"]["Winter"] > d["seasonal"]["Monsoon"]
assert len(d["series"]["date"]) == d["days"] and len(d["worst"]) == 10

assert c.get("/api/cities/Atlantis").status_code == 404

csv = b"City,Date,PM2.5,PM10,NO2,SO2,CO,O3\nPune,2020-01-01,80,150,40,10,1.2,30\n"
up = lambda body: c.post("/api/upload", data={"file": (io.BytesIO(body), "p.csv")})
assert up(csv).get_json() == {"rows": 1}
assert up(csv).get_json() == {"rows": 1}           # re-upload upserts, no dupes
pune = c.get("/api/cities/Pune").get_json()
assert pune["days"] == 1 and pune["worst"][0]["Bucket_calc"] == "Moderate", pune["worst"]

assert up(b"foo,bar\n1,2\n").status_code == 400     # wrong schema rejected
assert c.post("/api/upload").status_code == 400      # no file

r = c.get("/api/cities/Pune/report.xlsx")
assert r.status_code == 200 and r.data[:2] == b"PK"  # xlsx is a zip
r.close()

print("all server checks passed")
