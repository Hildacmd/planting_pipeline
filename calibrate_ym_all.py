#!/usr/bin/env python3
"""Fast-track Phase 2: calibrate the attainable ceiling Ym per (country, season) from HarvestStat
Africa, for every 2024 CPI asset that exists. Reduces the CPI band to the HarvestStat FEWS-NET
admin units (so units match the yield data exactly), fits Ym by least squares on 70% of units,
validates on the held-out 30%, and tests a highland (elevation >= 1800 m) split — keeping it only
where it beats the single Ym. Prints the YM_CAL / YM_HIGHLAND lines to paste into src/cpi.py.

Yield rescaling is free (yield = CPI x Ym), so this NEVER recomputes the fusion.
  EE_PROJECT=ee-manzikye python calibrate_ym_all.py
"""
import sys, os, statistics as st, random
sys.path.insert(0, os.path.dirname(__file__))
import geopandas as gpd, pandas as pd
from src import utils

HS = os.path.join(os.path.dirname(__file__), "Cropyield-Data", "harveststat")
GPKG = os.path.join(HS, "hvstat_africa_boundary_v1.2.gpkg")
CSV = os.path.join(HS, "hvstat_africa_data_v1.2.csv")
# (asset_id, pipeline country, HarvestStat season_name, try highland split?)
JOBS = [
    ("cpi_Kenya_Longrains_2024",        "Kenya",    "Long",   True),
    ("cpi_Kenya_Shortrains_2024",       "Kenya",    "Short",  False),
    ("cpi_Ethiopia_Meher_2024",         "Ethiopia", "Meher",  True),
    ("cpi_Somalia_Gu_2024",             "Somalia",  "Gu",     False),
    ("cpi_Somalia_Deyr_2024",           "Somalia",  "Deyr",   False),
    ("cpi_Ethiopia_Belg_2024",          "Ethiopia", "Belg",   True),
]

def pear(a, b):
    n = len(a)
    if n < 3: return float("nan")
    ma, mb = sum(a)/n, sum(b)/n
    num = sum((x-ma)*(y-mb) for x, y in zip(a, b))
    da = sum((x-ma)**2 for x in a)**.5; db = sum((y-mb)**2 for y in b)**.5
    return num/(da*db) if da*db else float("nan")
def mae(a, b): return sum(abs(x-y) for x, y in zip(a, b))/len(a)
def fit_ym(o, f): return sum(a*b for a, b in zip(o, f))/sum(b*b for b in f) if sum(b*b for b in f) else float("nan")

def main():
    ee = utils.gee_init()
    bnd = gpd.read_file(GPKG)
    hs = pd.read_csv(CSV, low_memory=False)
    hs = hs[hs["product"].str.contains("aize", case=False, na=False)].dropna(subset=["yield"])
    ym_cal, ym_high, skipped = {}, {}, []
    for asset, country, season, hl in JOBS:
        aid = f"projects/ee-manzikye/assets/{asset}"
        try:
            img = ee.Image(aid); img.bandNames().getInfo()
        except Exception:
            skipped.append(f"{country}/{season} (no asset {asset})"); continue
        s = hs[(hs["country"] == country) & (hs["season_name"] == season)]
        if len(s) == 0:
            skipped.append(f"{country}/{season} (no HarvestStat)"); continue
        yr = 2024 if 2024 in set(s["harvest_year"]) else int(s["harvest_year"].max())
        obs = s[s["harvest_year"] == yr].groupby("admin_1")["yield"].median()
        units = bnd[bnd["country"] == country][["admin_1", "geometry"]]
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry(r.geometry.simplify(0.01).__geo_interface__),
                                               {"a": r["admin_1"]}) for _, r in units.iterrows()])
        cpi = img.select("CPI")
        red = cpi.reduceRegions(fc, ee.Reducer.mean(), scale=250, tileScale=8).getInfo()
        elev = ee.Image("USGS/SRTMGL1_003").select(0).reduceRegions(fc, ee.Reducer.mean(), scale=2000, tileScale=8).getInfo()
        cpm = {f["properties"]["a"]: f["properties"].get("mean") for f in red["features"]}
        elm = {f["properties"]["a"]: (f["properties"].get("mean") or 0) for f in elev["features"]}
        rows = [(a, obs[a], cpm[a]/100.0, elm.get(a, 0)) for a in obs.index
                if a in cpm and cpm[a] and cpm[a] > 5]
        if len(rows) < 5:
            skipped.append(f"{country}/{season} (only {len(rows)} matched units)"); continue
        random.seed(42); idx = list(range(len(rows))); random.shuffle(idx); ntr = round(0.7*len(rows))
        tr = [rows[i] for i in idx[:ntr]]; te = [rows[i] for i in idx[ntr:]]
        ymS = fit_ym([r[1] for r in tr], [r[2] for r in tr])
        maeS = mae([r[1] for r in te], [r[2]*ymS for r in te])
        r_all = pear([r[1] for r in rows], [r[2] for r in rows])
        line = f"{country:9s} {season:6s} yr{yr}  n={len(rows):2d}  Ym={ymS:.2f}  test-MAE={maeS:.2f}  r={r_all:+.2f}"
        ym_cal[(country, season)] = float(round(ymS, 2))
        if hl:
            hi = [r for r in tr if r[3] >= 1800]; lo = [r for r in tr if r[3] < 1800]
            if len(hi) >= 2 and len(lo) >= 2:
                ymH = fit_ym([r[1] for r in hi], [r[2] for r in hi]); ymL = fit_ym([r[1] for r in lo], [r[2] for r in lo])
                maeSplit = mae([r[1] for r in te], [r[2]*(ymH if r[3] >= 1800 else ymL) for r in te])
                if maeSplit < maeS:
                    ym_high[(country, season)] = (float(round(ymH, 1)), float(round(ymL, 1)))
                    line += f"  | HIGHLAND SPLIT wins: hi={ymH:.1f}/lo={ymL:.1f} MAE={maeSplit:.2f}"
                else:
                    line += f"  | highland split loses ({maeSplit:.2f}), keep single"
        print(line)

    print("\n--- paste into src/cpi.py ---")
    print("YM_CAL = {")
    for k, v in ym_cal.items(): print(f'    {k}: {v},')
    print("    # uncalibrated country/seasons fall back to 6.0 main / 4.5 short")
    print("}")
    if ym_high:
        print("YM_HIGHLAND = {")
        for k, v in ym_high.items(): print(f'    {k}: {v},   # (highland >=1800 m, rest)')
        print("}")
    print("\nSKIPPED (no asset / no HarvestStat / too few units — use fallback Ym or FEWS FDW):")
    for x in skipped: print("  -", x)

if __name__ == "__main__":
    main()
