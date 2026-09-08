#!/usr/bin/env python3
"""Prepare compact multi-product geo+attribute data for the interactive planting app (one JSON).

Emits {"products":[...]} — one entry per (country, season) layer. Each product carries its own
admin level-names (Kenya: County/Constituency/Ward · Ethiopia: Region/Zone/Woreda), calendar
window, and per-level GeoJSON+attributes. The app switches between products client-side.
"""
import json, pandas as pd, geopandas as gpd
from shapely import wkt

# --- product registry: id -> config ---
PRODUCTS = [
    {"id": "ke_long", "country": "Kenya", "season": "Long rains 2024", "crop": "maize",
     "base": "planting_Kenya_maize_Longrains_2024", "wbase": "wrsi_Kenya_maize_Longrains_2024",
     "win": [8, 12], "levelnames": {1: "County", 2: "Constituency", 3: "Ward"}, "scale": "10 m"},
    {"id": "ke_short", "country": "Kenya", "season": "Short rains 2024", "crop": "maize",
     "base": "planting_Kenya_maize_Shortrains_2024_rainfed", "wbase": "wrsi_Kenya_maize_Shortrains_2024_250m",
     "win": [28, 32], "levelnames": {1: "County", 2: "Constituency", 3: "Ward"},
     "scale": "250 m grid · rainfall-anchored (~5.5 km content)",
     "note": "rainfall-anchored (44-yr CHIRPS onset) — full coverage; green-up too sparse to lead here"},
    {"id": "et_meher", "country": "Ethiopia", "season": "Meher 2024", "crop": "maize",
     "base": "planting_Ethiopia_maize_Meher_2024_250m", "wbase": "wrsi_Ethiopia_maize_Meher_2024_250m",
     "win": [10, 15], "levelnames": {1: "Region", 2: "Zone", 3: "Woreda"}, "scale": "250 m"},
]

# ---- new-country 2024 products (reduce_newcountries.py -> newc_*_skill_WKT.csv) --------------------
# CPI/yield/stress + planting distribution + WRSI stages from the cpiX_ rich assets. Validation
# (hit/bias/mae) columns are absent (no ground reference outside Kenya) -> app leaves that panel blank.
# id, country, season-label, base token (matches cpiX_ id), win dekads, admin level names, note.
_NEW = [
    ("ug_1st",  "Uganda", "1st rains 2024",  "Uganda_1strains",  [7, 14],  ("Sub-region", "District")),
    ("ug_2nd",  "Uganda", "2nd rains 2024",  "Uganda_2ndrains",  [23, 29], ("Sub-region", "District")),
    ("rw_a",    "Rwanda", "Season A 2024",   "Rwanda_SeasonA",   [27, 32], ("Province", "District")),
    ("rw_b",    "Rwanda", "Season B 2024",   "Rwanda_SeasonB",   [5, 10],  ("Province", "District")),
    ("bi_a",    "Burundi", "Season A 2024",  "Burundi_SeasonA",  [27, 32], ("Province", "Commune")),
    ("bi_b",    "Burundi", "Season B 2024",  "Burundi_SeasonB",  [5, 10],  ("Province", "Commune")),
    ("tz_mas",  "Tanzania", "Masika 2024",   "Tanzania_Masika",  [8, 14],  ("Region", "District")),
    ("tz_msi",  "Tanzania", "Msimu 2024",    "Tanzania_Msimu",   [34, 40], ("Region", "District")),
    ("tz_vul",  "Tanzania", "Vuli 2024",     "Tanzania_Vuli",    [29, 34], ("Region", "District")),
    ("ss_main", "South Sudan", "Main 2024",  "SouthSudan_Main",  [11, 19], ("State", "County")),
    ("so_gu",   "Somalia", "Gu 2024",        "Somalia_Gu",       [11, 16], ("Region", "District")),
    ("so_deyr", "Somalia", "Deyr 2024",      "Somalia_Deyr",     [29, 34], ("Region", "District")),
    ("et_belg", "Ethiopia", "Belg 2024",     "Ethiopia_Belg",    [7, 12],  ("Region", "Zone")),
]
_RAIN = {"Uganda_2ndrains", "Rwanda_SeasonA", "Rwanda_SeasonB", "Burundi_SeasonA", "Burundi_SeasonB",
         "Tanzania_Vuli", "Somalia_Deyr", "Ethiopia_Belg"}   # Season A moved to rainfall (cloudy highlands)
for _id, _c, _s, _tok, _win, _ln in _NEW:
    PRODUCTS.append({
        "id": _id, "country": _c, "season": _s, "crop": "maize",
        "base": f"newc_{_tok}_2024", "wbase": f"newc_{_tok}_2024_wrsi",  # wbase absent -> null WRSI merge
        "win": _win, "levelnames": {1: _ln[0], 2: _ln[1]}, "scale": "250 m",
        "note": ("rainfall-anchored onset" if _tok in _RAIN else "green-up cue-fusion onset")
                + " · yield on fallback Ym (no HarvestStat match yet)",
    })
KEYS = {1: ["name"], 2: ["county", "name"], 3: ["county", "constituency", "name"]}
SIMPLIFY = {1: 0.008, 2: 0.006, 3: 0.004}
PLANT = {"modal_dekad": "md", "mean_dekad": "mean", "p10": "p10", "p50": "p50", "p90": "p90",
         "hit_rate": "hit", "bias_dek": "bias", "mae_dek": "mae", "n_px": "n",
         "crop_area_frac": "caf", "spi3_dry_pct": "spidry", "spi3_mean": "spi",
         "pkv_dekad": "pkv", "flo_dekad": "flo", "grf_dekad": "grf", "mat_dekad": "mat",
         "crop_viable_pct": "viab", "lvpd_dekad": "lvpd",
         "wrsi_veg": "wrv", "wrsi_flo": "wrf", "wrsi_grf": "wrg",
         "wsi_veg": "wsv", "wsi_flo": "wsf", "wsi_grf": "wsg", "failflo_pct": "failflo",
         "cpi": "cpi", "yield_tha": "yld", "total_yield_t": "tyld",
         "s_water": "sw", "s_heat": "sh", "s_veg": "sv",
         "false_start_pct": "fstart", "waterlog_idx": "wlog", "waterlog_pct": "wlogp", "spi_wet_pct": "spiwet",
         "obs_plant_dk": "obs", "plant_err": "perr", "fcci": "fcci"}
WRSI = {"mean_WRSI": "wrsi", "mean_deficit_mm": "def", "fail_pct": "fail"}


def gload(path):
    df = pd.read_csv(path)
    g = gpd.GeoDataFrame(df, geometry=df["geometry_wkt"].map(wkt.loads), crs="EPSG:4326")
    return g.drop(columns=["geometry_wkt"])


def coords(geom, tol):
    geom = geom.simplify(tol, preserve_topology=True)
    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    out = []
    for p in polys:
        ring = [[round(x, 3), round(y, 3)] for x, y in p.exterior.coords]
        if len(ring) >= 4:
            out.append(ring)
    return out


def build_product(cfg):
    prod = {"id": cfg["id"], "country": cfg["country"], "season": cfg["season"],
            "crop": cfg["crop"], "scale": cfg["scale"], "win": cfg["win"],
            "note": cfg.get("note", ""), "levels": {}}
    for lvl in (1, 2, 3):
        try:
            pl = gload(f"{cfg['base']}_L{lvl}_skill_WKT.csv")
        except FileNotFoundError:
            print(f"  [skip] {cfg['id']} L{lvl}: no skill WKT"); continue
        try:
            wr = gload(f"{cfg['wbase']}_L{lvl}_admin_WKT.csv")[KEYS[lvl] + list(WRSI)]
            m = pl.merge(wr, on=KEYS[lvl], how="left")
        except (FileNotFoundError, KeyError):
            m = pl.copy()
            for k in WRSI:
                if k not in m.columns:          # keep WRSI cols the skill CSV already carries (new countries)
                    m[k] = None
        units = []
        for _, r in m.iterrows():
            a = {v: (round(float(r[k]), 3) if k in r and pd.notna(r[k]) else None)
                 for k, v in {**PLANT, **WRSI}.items()}
            sv = lambda k: (str(r[k]) if k in r and pd.notna(r[k]) else "")   # NaN/empty -> "" (valid JSON)
            units.append({"n": sv("name"), "p": sv("county"),
                          "c": sv("constituency") if lvl == 3 else "",
                          "a": a, "g": coords(r.geometry, SIMPLIFY[lvl])})
        prod["levels"][str(lvl)] = {"label": cfg["levelnames"][lvl], "units": units}
        print(f"  {cfg['id']} L{lvl} {cfg['levelnames'][lvl]}: {len(units)} units")
    return prod


data = {"products": [], "default": PRODUCTS[0]["id"]}
for cfg in PRODUCTS:
    print(f"== {cfg['country']} · {cfg['season']} ({cfg['scale']}) ==")
    data["products"].append(build_product(cfg))

js = json.dumps(data, separators=(",", ":"), allow_nan=False)   # NaN is invalid JSON -> fail loudly
open("app_data.json", "w").write(js)
print(f"\napp_data.json — {len(js)/1e6:.2f} MB · {len(data['products'])} products")
