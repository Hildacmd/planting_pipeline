"""Sorghum risk layers for the atlas, from the 2024 admin-2 statistics.

Five layers, rasterised from `newcS_<product>_2024_L2_skill_WKT.csv` onto the atlas grid, the
same way `build_risk_merge.py` renders the seven maize countries that have no pixel export. No
Earth Engine work is needed: the reduce step has already produced everything.

    risk_sorghum_wrsi.png    season WRSI, 40 to 100
    risk_sorghum_cpi.png     crop performance index, 0 to 100
    risk_sorghum_stress.png  water stress S_water, 0 to 100 %
    risk_sorghum_yield.png   yield t/ha, rescaled to the FITTED ceiling; uncalibrated products hatched
    risk_sorghum_fail.png    crop failure at flowering, % of sorghum area

**Yield is rescaled, not re-exported.** The assets were built before the ceilings were fitted, so
they carry the uncalibrated default. Yield is CPI/100 x Ym, linear in Ym, so multiplying by
Ym_fitted / Ym_used is exact and saves nine exports.

**Three products have no fitted ceiling** — Tanzania and Eritrea have no sorghum yields in
HarvestStat at all, and South Sudan has two reporting units, too few to fit. They keep the
uncalibrated 3.0 t/ha and are drawn with a diagonal hatch, as the maize atlas does for Tanzania
and South Sudan, so they can never be read as calibrated values.

Units holding less than the minimum sorghum area are drawn grey rather than coloured: a district
that is 0.2 % sorghum should not be given a confident colour.
"""
import json, os, sys
import numpy as np, pandas as pd
from PIL import Image
from matplotlib.colors import LinearSegmentedColormap
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely import wkt

H0 = os.path.dirname(os.path.abspath(__file__))
PP = os.path.expanduser("~/Downloads/planting_pipeline")
sys.path.insert(0, os.path.join(PP, "sorghum_pipeline"))
import sorghum_params as P                                         # noqa: E402

g = json.load(open(os.path.join(H0, "layers", "grid.json")))
W, H = g["size"]; (S_, W_), (N_, E_) = g["bounds"]
TR = from_origin(W_, N_, g["res_deg"], g["res_deg"])

# product token, country, season (for the ceiling lookup), the Ym the asset was built with, and the
# minimum share of the district that must be sorghum for it to be coloured rather than greyed.
#
# The threshold is 0.1 % in the arid countries and 1 % elsewhere, and the difference matters. Their
# reporting units are enormous, so sorghum is a small fraction of almost every one even where it is
# the dominant crop: at a flat 1 % Sudan showed 10 of 72 localities, against 42 that hold any
# sorghum at all, and Sudan carries 6.32 Mha, the largest sorghum area in the region. Ethiopia,
# Kenya, Uganda and Tanzania have a median unit above 1 % and keep the stricter threshold.
# All 18 products. Later entries override earlier ones where they overlap, so the MAIN season of a
# country is listed last: a second season should not paint over the main one.
JOBS = [
    ("Ethiopia_Belg",     "Ethiopia",    "Belg",        3.0, 0.01),
    ("Ethiopia_Meher",    "Ethiopia",    "Meher",       3.0, 0.01),
    ("Tanzania_Masika",   "Tanzania",    "Masika",      3.0, 0.01),
    ("Tanzania_Msimu",    "Tanzania",    "Msimu",       3.0, 0.01),
    ("South_Sudan_2nd",   "South_Sudan", "2nd",         2.0, 0.001),
    ("South_Sudan_Main",  "South_Sudan", "Main",        3.0, 0.001),
    ("Kenya_Shortrains",  "Kenya",       "Short rains", 2.0, 0.01),
    ("Kenya_Longrains",   "Kenya",       "Long rains",  3.0, 0.01),
    ("Uganda_2ndrains",   "Uganda",      "2nd rains",   2.0, 0.01),
    ("Uganda_1strains",   "Uganda",      "1st rains",   3.0, 0.01),
    ("Rwanda_SeasonB",    "Rwanda",      "Season B",    3.0, 0.01),
    ("Rwanda_SeasonA",    "Rwanda",      "Season A",    3.0, 0.01),
    ("Burundi_SeasonB",   "Burundi",     "Season B",    3.0, 0.01),
    ("Burundi_SeasonA",   "Burundi",     "Season A",    3.0, 0.01),
    ("Somalia_Deyr",      "Somalia",     "Deyr",        2.0, 0.001),
    ("Somalia_Gu",        "Somalia",     "Gu",          3.0, 0.001),
    ("Eritrea_Kremti",    "Eritrea",     "Kremti",      3.0, 0.001),
    ("Sudan_Kharif",      "Sudan",       "Kharif",      3.0, 0.001),
]
COLS = {"wrsi": "mean_WRSI", "cpi": "cpi", "stress": "s_water",
        "yield": "yield_tha", "fail": "failflo_pct"}

adm = {k: np.full((H, W), np.nan, "float32") for k in COLS}
grey = np.zeros((H, W), bool)
uncal = np.zeros((H, W), bool)          # products with no fitted ceiling, for the hatch
summary = []

for tok, country, season, ym_used, min_caf in JOBS:
    f = os.path.join(PP, f"newcS_{tok}_2024_L2_skill_WKT.csv")
    if not os.path.exists(f):
        print(f"  [skip] {tok}: no reduce CSV"); continue
    d = pd.read_csv(f)
    geoms = [wkt.loads(s) for s in d.geometry_wkt]
    ok = (d.crop_area_frac.fillna(0) >= min_caf).values
    cov = rasterize([(gm, 1) for gm in geoms], out_shape=(H, W), transform=TR).astype(bool)
    okm = (rasterize([(gm, 1) for gm, o in zip(geoms, ok) if o], out_shape=(H, W), transform=TR)
           .astype(bool) if ok.any() else np.zeros((H, W), bool))

    ym_fit = P.ym_for(country, season)
    is_cal = P.is_calibrated(country, season)
    if not is_cal:
        uncal |= okm

    for k, col in COLS.items():
        if col not in d.columns:
            continue
        v = d[col].astype(float).values
        if k == "yield":
            v = v * (ym_fit / ym_used)          # linear in Ym, so an exact rescale
        shp = [(gm, float(x)) for gm, x, o in zip(geoms, v, ok) if o and np.isfinite(x)]
        if shp:
            a = rasterize(shp, out_shape=(H, W), transform=TR, fill=np.nan, dtype="float32")
            adm[k] = np.where(okm & np.isfinite(a), a, adm[k])
    grey |= cov & ~okm
    summary.append(dict(product=tok, units=len(d), shown=int(ok.sum()),
                        ym_used=ym_used, ym_fitted=round(ym_fit, 2), calibrated=is_cal,
                        cpi_median=round(float(np.nanmedian(d.cpi)), 1)))
    print(f"  {tok:<20} units {len(d):>3}  shown {int(ok.sum()):>3}  "
          f"Ym {ym_used} -> {ym_fit:.2f}{'' if is_cal else '  (UNCALIBRATED, hatched)'}")

grey &= ~np.isfinite(adm["cpi"])
RYG = LinearSegmentedColormap.from_list("ryg", ["#a50026", "#f46d43", "#fee08b", "#a6d96a", "#1a9850"])
STRESS = LinearSegmentedColormap.from_list("st", ["#ffffcc", "#fd8d3c", "#800026"])
YLD = LinearSegmentedColormap.from_list("y", ["#f7fcb9", "#78c679", "#005a32"])
FAIL = LinearSegmentedColormap.from_list("f", ["#ffffff", "#fdae61", "#a50026"])

yy, xx = np.mgrid[0:H, 0:W]
hatch = ((xx + yy) % 9) < 2                      # same stripe as the maize uncalibrated overlay

LAYERS = [("wrsi",   RYG,    40, 100, "risk_sorghum_wrsi.png"),
          ("cpi",    RYG,     0, 100, "risk_sorghum_cpi.png"),
          ("stress", STRESS,  0, 100, "risk_sorghum_stress.png"),
          ("yield",  YLD,     0, 2.6, "risk_sorghum_yield.png"),
          ("fail",   FAIL,    0, 100, "risk_sorghum_fail.png")]

for key, cm, lo, hi, name in LAYERS:
    a = adm[key]
    ok = np.isfinite(a)
    rgba = (cm(np.clip((np.nan_to_num(a) - lo) / (hi - lo), 0, 1)) * 255).astype("uint8")
    rgba[..., 3] = np.where(ok, 255, 0)
    rgba[grey & ~ok] = (170, 172, 165, 150)      # mapped but below the area threshold
    if key == "yield":                            # stripe the uncalibrated products
        m = uncal & ok & hatch
        rgba[m] = (60, 60, 60, 255)
    Image.fromarray(rgba, "RGBA").save(os.path.join(H0, "layers", name), optimize=True)
    v = a[ok]
    print(f"{name:<28} cells {int(ok.sum()):>7}  median "
          f"{np.nanmedian(v) if v.size else float('nan'):.1f}")

json.dump(summary, open(os.path.join(H0, "risk_sorghum_summary.json"), "w"), indent=1)
print(f"\nsummary -> risk_sorghum_summary.json")
