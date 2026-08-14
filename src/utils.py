"""Shared helpers: dekad math, season windows, GEE init."""
from __future__ import annotations
import csv, os, datetime as dt

DEKADS_PER_YEAR = 36

# ---------------- dekad <-> date ----------------
def date_to_dekad(d: dt.date) -> int:
    """Return dekad-of-year 1..36. Dekads: d1=1-10, d2=11-20, d3=21-eom."""
    dk = 1 if d.day <= 10 else (2 if d.day <= 20 else 3)
    return (d.month - 1) * 3 + dk

def dekad_to_start_date(year: int, dekad: int) -> dt.date:
    month = (dekad - 1) // 3 + 1
    k = (dekad - 1) % 3
    day = [1, 11, 21][k]
    return dt.date(year, month, day)

def dekad_label(dekad: int) -> str:
    dekad = int(round(dekad))
    month = (dekad - 1) // 3 + 1
    return f"{dekad}·{dt.date(2000,month,1):%b}"      # e.g. "9·Mar" (annual dekad 1-36 + month)

def parse_dekad_token(tok: str) -> int:
    """'Mar-d3' -> dekad index 1..36."""
    mon, dk = tok.split("-d")
    month = dt.datetime.strptime(mon[:3], "%b").month
    return (month - 1) * 3 + int(dk)

# --------------- season calendar ---------------
def load_calendar(path="config/season_calendar.csv"):
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows

def load_yaml(path):
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)

def load_crop_coeffs(path="config/crop_coefficients.yaml"):
    cfg = load_yaml(path)
    soil = cfg.pop("soil")
    return cfg, soil          # (kc_by_crop, soil_cfg)

def viable_products(rows):
    """Yield (country, crop, season, plant_win, sos_win) for High/Medium viability only."""
    for r in rows:
        if r["crop_viability"] in ("High", "Medium"):
            yield r

def sos_window_dekads(sos_window: str):
    """'Jul-d1-Aug-d3' -> (start_dekad, end_dekad), handling wrap across year end."""
    parts = sos_window.split("-")
    start = parse_dekad_token(f"{parts[0]}-{parts[1]}")
    end   = parse_dekad_token(f"{parts[2]}-{parts[3]}")
    return start, end

# --------------- GEE ---------------
def gee_init(project=os.environ.get("EE_PROJECT")):
    import ee
    try:
        ee.Initialize(project=project)
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=project)
    return ee
