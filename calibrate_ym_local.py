#!/usr/bin/env python3
"""Calibrate the attainable yield ceiling Ym for Kenya, Ethiopia, Rwanda, Burundi, Somalia and Uganda (2024 maize, main season)
from HarvestStat v1.2, without Earth Engine: the 2024 admin-2 CPI from the pipeline's
newc_<Country>_<Season>_2024_L2_skill_WKT.csv is aggregated onto the HarvestStat units (maize-area weighted by
polygon overlap), then Ym is fitted by least squares through the origin (yield = CPI/100 x Ym), 70/30 train/test
split repeated 200 times - the same model as calibrate_ym_all.py for Kenya and Ethiopia.

Observed yield per unit = median over the listed years (robust to single-year outliers); unit values above
8 t/ha are dropped as implausible for rainfed smallholder maize.
Writes Cropyield-Data/ym_calibration_local.csv and ..._units.csv (per HarvestStat unit).
"""
import os, random, numpy as np, pandas as pd, geopandas as gpd
from shapely import wkt
H = os.path.dirname(os.path.abspath(__file__))
HS = os.path.join(H, "Cropyield-Data", "harveststat")
JOBS = [  # CPI source (newc file stem, or "app:<product>" = risk monitor ward/woreda units), HarvestStat country, season, years, FNID prefix, provisional?
    ("app:ke_long",     "Kenya",    "Long",     range(2015, 2025), "KE2013A1", False),
    ("app:ke_short",    "Kenya",    "Short",    range(2016, 2025), "KE2013A1", False),
    ("app:et_meher",    "Ethiopia", "Meher",    range(2012, 2022), "ET2021R2", False),
    ("Rwanda_SeasonA",  "Rwanda",  "Season A", range(2010, 2018), "RW2006A2", False),
    ("Burundi_SeasonA", "Burundi", "Season A", range(2012, 2017), "BI1998A1", False),
    ("Somalia_Gu",      "Somalia", "Gu",       range(2015, 2025), "SO1990A2", False),
    ("Uganda_1strains", "Uganda",  "First",    range(2008, 2010), "UG2007A2", True),
]
d = pd.read_csv(os.path.join(HS, "hvstat_africa_data_v1.2.csv"), low_memory=False); d.columns = [c.lower() for c in d.columns]
b = gpd.read_file(os.path.join(HS, "hvstat_africa_boundary_v1.2.gpkg")); b.columns = [c.lower() for c in b.columns]
b = b.set_geometry("geometry")
def cpi_units(stem):
    """2024 CPI per admin unit with its maize-area fraction, as a GeoDataFrame (cpi, crop_area_frac, geometry)."""
    if stem.startswith("app:"):                      # Kenya wards / Ethiopia woredas from the risk monitor
        import json, re
        from shapely.geometry import Polygon, MultiPolygon
        s = open(os.path.join(H, "risk_app.html")).read()
        m = re.search(r'<script[^>]*type="application/json"[^>]*>', s); st = m.end()
        P = {p["id"]: p for p in json.loads(s[st:s.index("</script>", st)])["products"]}[stem[4:]]
        us = P["levels"][max(P["levels"], key=int)]["units"]
        return gpd.GeoDataFrame({"cpi": [u["a"].get("cpi") for u in us], "crop_area_frac": [u["a"].get("caf") for u in us]},
                                geometry=[MultiPolygon([Polygon(r) for r in u["g"] if len(r) >= 4]) for u in us], crs="EPSG:4326")
    n = pd.read_csv(os.path.join(H, f"newc_{stem}_2024_L2_skill_WKT.csv"))
    return gpd.GeoDataFrame(n[["cpi", "crop_area_frac"]], geometry=[wkt.loads(x) for x in n.geometry_wkt], crs="EPSG:4326")


rows = []; units = []
for stem, country, season, years, pref, prov in JOBS:
    y = d[(d["product"] == "Maize") & (d.country == country) & (d.season_name == season) & d.harvest_year.isin(years) & d["yield"].notna()]
    obs = y.groupby("fnid")["yield"].median()
    obs = obs[(obs > 0) & (obs <= 8)]
    g = cpi_units(stem)
    g = g[g.cpi.notna() & g.crop_area_frac.notna() & (g.crop_area_frac > 0)]
    g["geometry"] = g.geometry.buffer(0)
    u = b[b.fnid.isin(obs.index)][["fnid", "geometry"]]
    eq = "ESRI:54034"                                   # equal-area for overlap weights
    ov = gpd.overlay(g.to_crs(eq), u.to_crs(eq), how="intersection", keep_geom_type=True)
    ov["w"] = ov.area * ov.crop_area_frac               # maize area in the overlap
    cpi_u = ov.groupby("fnid").apply(lambda t: np.average(t.cpi, weights=t.w) if t.w.sum() > 0 else np.nan).dropna()
    j = pd.concat([obs.rename("obs"), (cpi_u / 100).rename("c")], axis=1).dropna()
    o, c = j.obs.values, j.c.values
    units.append(pd.DataFrame({"file": stem, "country": country, "fnid": j.index, "obs": o, "cpi": c * 100}))
    ym = float((o * c).sum() / (c * c).sum())
    # 70/30 repeated split: test MAE of the calibrated model vs the 6.0 t/ha default
    dflt = 4.5 if "short" in season.lower() else 6.0          # pipeline default ceiling (src/cpi.py)
    rnd = random.Random(42); mae_cal, mae_def = [], []
    idx = list(range(len(j)))
    for _ in range(200):
        rnd.shuffle(idx); k = max(1, int(round(0.7 * len(idx)))); tr, te = idx[:k], idx[k:]
        if not te: continue
        ymt = (o[tr] * c[tr]).sum() / (c[tr] ** 2).sum()
        mae_cal.append(np.abs(o[te] - ymt * c[te]).mean()); mae_def.append(np.abs(o[te] - dflt * c[te]).mean())
    r = float(np.corrcoef(o, ym * c)[0, 1]) if len(j) > 2 else np.nan
    rows.append({"file": stem, "country": country, "season": season, "years": f"{min(years)}-{max(years)}", "n_units": len(j),
                 "ym_cal": round(ym, 2), "test_mae_cal": round(float(np.mean(mae_cal)), 2), "default_ym": dflt, "test_mae_default": round(float(np.mean(mae_def)), 2),
                 "r_pred_obs": round(r, 2), "obs_median": round(float(np.median(o)), 2), "pred_median": round(float(np.median(ym * c)), 2),
                 "provisional": prov})
out = pd.DataFrame(rows)
out.to_csv(os.path.join(H, "Cropyield-Data", "ym_calibration_local.csv"), index=False)
u = pd.concat(units); u["pred_cal"] = u.cpi / 100 * u.file.map(out.set_index("file").ym_cal); u["pred_default"] = u.cpi / 100 * u.file.map(out.set_index("file").default_ym)
u.to_csv(os.path.join(H, "Cropyield-Data", "ym_calibration_local_units.csv"), index=False)
print(out.to_string(index=False))
