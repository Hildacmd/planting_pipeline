#!/usr/bin/env python3
"""Reduce the rich cpiX_<Country>_<Season>_2024 assets to admin-1 + admin-2 skill_WKT CSVs the apps
consume (via app_data.py). Geometry + admin names come from the LOCAL GADM 4.1 GeoPackages in
ICPAC-WORK/ADMIN-boundaries; the per-unit statistics come from GEE reduceRegions over the asset.
South Sudan has no GADM gpkg here, so it falls back to GAUL_SIMPLIFIED polygons.

Writes one CSV per (product, level):  newc_<Country>_<Season>_2024_L{1,2}_skill_WKT.csv
Columns match app_data.py's PLANT/WRSI schema (name, county, constituency, geometry_wkt, cpi,
yield_tha, total_yield_t, s_water, s_heat, s_veg, wrsi_veg/flo/grf, wsi_veg/flo/grf, modal_dekad,
mean_dekad, p10, p50, p90, n_px). Validation columns (hit/bias/mae) stay absent — no ground
reference outside Kenya, so the app's validation sub-panel is honestly blank.

  EE_PROJECT=ee-manzikye python reduce_newcountries.py                  # all ready cpiX_ assets
  EE_PROJECT=ee-manzikye python reduce_newcountries.py Uganda_1strains  # one, by <Country>_<Season>

Other crops and mask variants reuse this same reducer rather than a parallel copy, so the CSV
schema the apps consume cannot drift between crops:

  # sorghum (sorghum_pipeline), written as newcS_<product>_2024_L{1,2}_skill_WKT.csv
  EE_PROJECT=ee-manzikye python reduce_newcountries.py \
      --asset-prefix sorghumX --out-prefix newcS --project ee-manzikye \
      Sudan_Kharif Ethiopia_Meher

  # maize on the crop-type mask (maize_ctm), written as newcCTM_*
  EE_PROJECT=... python reduce_newcountries.py --asset-prefix cpiCTMX --out-prefix newcCTM ...
"""
import sys, os, csv, ee, geopandas as gpd
from shapely import wkt as shp_wkt


def gdf_to_ee(g):
    """GeoDataFrame (with '_id') -> ee.FeatureCollection, no geemap dependency."""
    feats = []
    for _, r in g.iterrows():
        feats.append(ee.Feature(ee.Geometry(r["geometry"].__geo_interface__), {"_id": int(r["_id"])}))
    return ee.FeatureCollection(feats)

def _positional(argv):
    """Product tokens only: drop each --flag AND the value that follows it."""
    out, skip = [], False
    for a in argv:
        if skip:
            skip = False; continue
        if a.startswith("--"):
            skip = True; continue
        out.append(a)
    return out


_ARGS = _positional(sys.argv[1:])


def _opt(name, default):
    """Minimal flag parser; argparse would fight the positional product list."""
    flag = f"--{name}"
    if flag in sys.argv:
        return sys.argv[sys.argv.index(flag) + 1]
    return default


ASSET_PREFIX = _opt("asset-prefix", "cpiX")      # cpiX | sorghumX | cpiCTMX
CROP = _opt("crop", "sorghum" if _opt("asset-prefix", "cpiX").startswith("sorghum") else "maize")
OUT_PREFIX = _opt("out-prefix", "newc")          # newc | newcS | newcCTM
# crop_area_frac must be measured over the SAME mask the product was computed in, or the weight and
# the product disagree. cpiCTMX_ products are computed in the ICPAC crop-type mask, so their CAF
# comes from it too; the legacy cpiX_ maize products stay on WorldCereal, which is what they were
# computed in. Override with --caf-source {auto,worldcereal,ctm}.
CAF_SOURCE = _opt("caf-source", "auto")
if CAF_SOURCE == "auto":
    CAF_SOURCE = "ctm" if (CROP != "maize" or "CTM" in ASSET_PREFIX) else "worldcereal"
EE_PROJECT = _opt("project", os.environ.get("EE_PROJECT", "ee-manzikye"))
ee.Initialize(project=EE_PROJECT)
PROJ = f"projects/{EE_PROJECT}/assets"
GADM_DIR = "/Users/hildamanzi/ICPAC-WORK/ADMIN-boundaries"
PIXEL_HA = 6.25                                    # 250 m pixel
VAL_BANDS = ["CPI", "S_water", "S_heat", "S_veg", "wrsi_veg", "wrsi_flo", "wrsi_grf",
             "wsi_veg", "wsi_flo", "wsi_grf"]
COLMAP = {"CPI": "cpi", "S_water": "s_water", "S_heat": "s_heat", "S_veg": "s_veg",
          "wrsi_veg": "wrsi_veg", "wrsi_flo": "wrsi_flo", "wrsi_grf": "wrsi_grf",
          "wsi_veg": "wsi_veg", "wsi_flo": "wsi_flo", "wsi_grf": "wsi_grf"}
GADM3 = {"Uganda": "UGA", "Rwanda": "RWA", "Burundi": "BDI", "Somalia": "SOM",
         "Tanzania": "TZA", "Ethiopia": "ETH", "Kenya": "KEN", "SouthSudan": "SSD",
         # added for the sorghum products, which reach two countries maize never did
         "South_Sudan": "SSD", "Sudan": "SDN", "Eritrea": "ERI", "Djibouti": "DJI"}
GAUL_NAME = {}   # all countries have a local GADM gpkg now
SIMPLIFY = {1: 0.006, 2: 0.004}
# FAO-56 stage durations (dekads) to place phenology stage dekads from modal planting.
STAGES = {"greenup": dict(ini=3, dev=4, mid=3, late=2),   # standard maize (LGP 12)
          "rainfall": dict(ini=2, dev=3, mid=2, late=2)}  # short-duration EARLY maize (LGP 9)
RAIN_TOK = {"Uganda_2ndrains", "Rwanda_SeasonA", "Rwanda_SeasonB", "Burundi_SeasonA", "Burundi_SeasonB",
            "Tanzania_Vuli", "Somalia_Deyr", "Ethiopia_Belg"}   # rainfall-anchored onset (EARLY maize)
OUT_COLS = ["name", "county", "constituency", "geometry_wkt", "cpi", "yield_tha", "total_yield_t",
            "s_water", "s_heat", "s_veg", "wrsi_veg", "wrsi_flo", "wrsi_grf",
            "wsi_veg", "wsi_flo", "wsi_grf", "modal_dekad", "mean_dekad", "p10", "p50", "p90", "n_px",
            # derived from the rich stack (data already on GEE) — fill the app's risk/ASAP panels:
            "crop_area_frac", "mean_WRSI", "fail_pct", "failflo_pct",
            "pkv_dekad", "flo_dekad", "grf_dekad", "mat_dekad"]


def admin_gdf(ctok, lvl):
    """(geometry, NAME_1..NAME_lvl) as a GeoDataFrame with a stable '_id' column, EPSG:4326."""
    if ctok in GADM3:
        p = f"{GADM_DIR}/gadm41_{GADM3[ctok]}.gpkg"
        g = gpd.read_file(p, layer=f"ADM_ADM_{lvl}").to_crs("EPSG:4326")
        g["name"] = g[f"NAME_{lvl}"]
        g["county"] = g["NAME_1"] if lvl >= 2 else ""
        g["constituency"] = g["NAME_2"] if lvl >= 3 else ""
    else:                                          # GAUL fallback (South Sudan)
        fc = ee.FeatureCollection("FAO/GAUL_SIMPLIFIED_500m/2015/level%d" % lvl) \
               .filter(ee.Filter.eq("ADM0_NAME", GAUL_NAME[ctok]))
        gj = fc.map(lambda f: f.setGeometry(f.geometry().simplify(500))).getInfo()
        recs = [{**f["properties"], "geometry": f["geometry"]} for f in gj["features"]]
        g = gpd.GeoDataFrame(recs, geometry=gpd.GeoSeries.from_features(gj["features"]).values, crs="EPSG:4326")
        g["name"] = g["ADM%d_NAME" % lvl]
        g["county"] = g["ADM1_NAME"] if lvl >= 2 else ""
        g["constituency"] = ""
    g = g[g.geometry.notna()].reset_index(drop=True)
    g["_id"] = g.index.astype(int)
    g["geometry"] = g.geometry.simplify(SIMPLIFY[lvl], preserve_topology=True)
    return g[["_id", "name", "county", "constituency", "geometry"]]


def _crop_mask(ee, country):
    """The mask `crop_area_frac` is measured over — the share of the admin unit that is THIS crop.

    This used to be hard-coded to WorldCereal maize for every product, on the grounds that the
    layer is global and country-independent. It is also **crop**-independent, so every sorghum
    product was reporting the MAIZE fraction as its crop area. The giveaway was that maize and
    sorghum shared a `crop_area_frac` maximum to four decimal places in every country.

    That column is not decorative: it is the overlap weight when the yield ceiling is fitted, and
    the threshold that decides which units the atlas colours. Weighted by maize, a district that
    grows maize and no sorghum counted fully towards a sorghum ceiling.
    """
    if CAF_SOURCE == "worldcereal":
        from run import crop_mask_image
        return crop_mask_image(ee, "maize", "maize", None)
    import ctm_mask as CTM
    return CTM.crop_fraction(ee, country, CROP).divide(100)   # frac_<crop> is a percentage


print(f"[caf] crop_area_frac measured over: "
      f"{'ICPAC crop-type mask' if CAF_SOURCE == 'ctm' else 'ESA WorldCereal maize'}")


def reduce_stats(img, fc, ctok):
    """reduceRegions for value/yield/planting + derived ASAP/risk metrics, keyed by '_id'.
    `ctok` is the country token; the crop-area fraction is crop- AND country-specific."""
    plant = img.select("planting_dekad"); yld = img.select("yield_tha_x100"); vals = img.select(VAL_BANDS)
    out = {}
    for r in vals.reduceRegions(fc, ee.Reducer.median(), scale=250, tileScale=4).getInfo()["features"]:
        out.setdefault(r["properties"]["_id"], {}).update({b: r["properties"].get(b) for b in VAL_BANDS})
    for r in yld.reduceRegions(fc, ee.Reducer.mean().combine(ee.Reducer.count(), "", True),
                               scale=250, tileScale=4).getInfo()["features"]:
        out.setdefault(r["properties"]["_id"], {}).update(
            {"ymean": r["properties"].get("mean"), "npx": r["properties"].get("count")})
    for r in plant.reduceRegions(
            fc, ee.Reducer.mode().combine(ee.Reducer.percentile([10, 50, 90]), "", True)
                  .combine(ee.Reducer.mean(), "", True), scale=250, tileScale=4).getInfo()["features"]:
        pr = r["properties"]
        out.setdefault(pr["_id"], {}).update(
            {"mode": pr.get("mode"), "p10": pr.get("p10"), "p50": pr.get("p50"),
             "p90": pr.get("p90"), "pmean": pr.get("mean")})
    # derived (means of 0/1 or 0-100 images): crop-area fraction over the WHOLE admin (mask unmasked
    # to 0), and over MAIZE pixels only: seasonal-min-WRSI crop-failure, flowering failure, mean WRSI.
    wstack = img.select(["wrsi_veg", "wrsi_flo", "wrsi_grf"])
    smin = wstack.reduce(ee.Reducer.min())
    derived = ee.Image.cat([
        _crop_mask(ee, ctok).unmask(0).rename("caf"),            # fraction of admin that is THIS crop
        smin.lt(50).rename("failp"),                             # fraction of MAIZE with seasonal WRSI<50
        img.select("wrsi_flo").lt(50).rename("failflop"),        # fraction of MAIZE failing at flowering
        wstack.reduce(ee.Reducer.mean()).rename("wrsimean")])    # mean seasonal WRSI over maize
    for r in derived.reduceRegions(fc, ee.Reducer.mean(), scale=250, tileScale=4).getInfo()["features"]:
        pr = r["properties"]
        out.setdefault(pr["_id"], {}).update(
            {"caf": pr.get("caf"), "failp": pr.get("failp"), "failflop": pr.get("failflop"),
             "wrsimean": pr.get("wrsimean")})
    return out


def country_token(product):
    """Country prefix of a product token.

    Splitting on the first underscore is not enough: the maize products use `SouthSudan_Main`
    while the sorghum ones use `South_Sudan_Main`, and `"South_Sudan_Main".split("_")[0]` is
    "South", which matches nothing. Try the longest prefix that names a country, with and without
    the underscore."""
    parts = product.split("_")
    for n in range(len(parts), 0, -1):
        cand = "_".join(parts[:n])
        for key in (cand, cand.replace("_", "")):
            if key in GADM3 or key in GAUL_NAME:
                return key
    return parts[0]


def process(product):
    ctok = country_token(product)
    asset = f"{PROJ}/{ASSET_PREFIX}_{product}_2024"
    try:
        ee.data.getAsset(asset)
    except Exception:
        print(f"  [skip] asset not ready: {ASSET_PREFIX}_{product}_2024"); return
    img = ee.Image(asset)
    print(f"== {product} ==")
    for lvl in (1, 2):
        g = admin_gdf(ctok, lvl)
        fc = gdf_to_ee(g[["_id", "geometry"]])
        try:
            stats = reduce_stats(img, fc, ctok)
        except Exception as e:
            print(f"  L{lvl}: FAILED {str(e)[:90]}"); continue
        rows = []
        for _, gr in g.iterrows():
            s = stats.get(int(gr["_id"]), {})
            npx = s.get("npx") or 0
            if npx < 5:
                continue
            ym = s.get("ymean"); yv = round(ym / 100.0, 2) if ym is not None else None
            row = {c: None for c in OUT_COLS}
            row.update({"name": gr["name"], "county": gr["county"], "constituency": gr["constituency"],
                        "geometry_wkt": gr["geometry"].wkt, "yield_tha": yv,
                        "total_yield_t": round(yv * npx * PIXEL_HA, 0) if yv is not None else None,
                        "modal_dekad": round(s["mode"]) if s.get("mode") is not None else None,
                        "mean_dekad": round(s["pmean"], 1) if s.get("pmean") is not None else None,
                        "p10": round(s["p10"]) if s.get("p10") is not None else None,
                        "p50": round(s["p50"]) if s.get("p50") is not None else None,
                        "p90": round(s["p90"]) if s.get("p90") is not None else None, "n_px": int(npx)})
            for b, col in COLMAP.items():
                row[col] = round(s[b], 1) if s.get(b) is not None else None
            # derived ASAP/risk metrics
            row["crop_area_frac"] = round(s["caf"], 3) if s.get("caf") is not None else None
            row["mean_WRSI"] = round(s["wrsimean"], 1) if s.get("wrsimean") is not None else None
            row["fail_pct"] = round(s["failp"] * 100, 1) if s.get("failp") is not None else None
            row["failflo_pct"] = round(s["failflop"] * 100, 1) if s.get("failflop") is not None else None
            # phenology stage dekads from modal planting + FAO-56 stage durations (wrap 1..36)
            md = row["modal_dekad"]
            if md is not None:
                st = STAGES["rainfall" if product in RAIN_TOK else "greenup"]
                wrap = lambda d: (int(round(d)) - 1) % 36 + 1
                row["pkv_dekad"] = wrap(md + st["ini"] + st["dev"])                       # peak vegetative
                row["flo_dekad"] = wrap(md + st["ini"] + st["dev"] + max(1, st["mid"] // 2))  # flowering
                row["grf_dekad"] = wrap(md + st["ini"] + st["dev"] + st["mid"])           # grain fill
                row["mat_dekad"] = wrap(md + st["ini"] + st["dev"] + st["mid"] + st["late"])  # maturity
            rows.append(row)
        out = f"{OUT_PREFIX}_{product}_2024_L{lvl}_skill_WKT.csv"
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=OUT_COLS); w.writeheader(); w.writerows(rows)
        got = sum(1 for r in rows if r["cpi"] is not None)
        print(f"  L{lvl}: {got}/{len(rows)} units with CPI -> {out}")


ALL = ["Uganda_1strains", "Uganda_2ndrains", "Rwanda_SeasonA", "Rwanda_SeasonB",
       "Burundi_SeasonA", "Burundi_SeasonB", "Tanzania_Masika", "Tanzania_Msimu",
       "Tanzania_Vuli", "SouthSudan_Main", "Somalia_Gu", "Somalia_Deyr", "Ethiopia_Belg"]

SORGHUM_ALL = ["Sudan_Kharif", "Ethiopia_Meher", "Ethiopia_Belg", "Tanzania_Msimu",
               "Tanzania_Masika", "South_Sudan_Main", "South_Sudan_2nd", "Kenya_Longrains",
               "Kenya_Shortrains", "Uganda_1strains", "Uganda_2ndrains", "Somalia_Gu",
               "Somalia_Deyr", "Rwanda_SeasonA", "Rwanda_SeasonB", "Burundi_SeasonA",
               "Burundi_SeasonB", "Eritrea_Kremti"]

if __name__ == "__main__":
    default = SORGHUM_ALL if ASSET_PREFIX.startswith("sorghum") else ALL
    print(f"asset prefix {ASSET_PREFIX}_ · project {EE_PROJECT} · output {OUT_PREFIX}_*")
    for p in (_ARGS or default):
        process(p)
