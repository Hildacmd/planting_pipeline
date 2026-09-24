"""Fill the six countries without 2024 pixel exports (UG, TZ, RW, BI, SO, SS) into the atlas WRSI / CPI /
water-deficit layers from the pipeline's admin-level statistics (newc_<Country>_<Season>_2024_L2_skill_WKT.csv:
mean_WRSI, cpi, mean_deficit_mm per admin-2 unit). Kenya and Ethiopia stay at pixel level (build_risk_drive.py).
Units with < 1 % maize area are grey, as in the crop-failure layer."""
import os, json, numpy as np, pandas as pd
from shapely import wkt
from rasterio.features import rasterize
from rasterio.transform import from_origin
from PIL import Image
from matplotlib.colors import LinearSegmentedColormap
H0 = os.path.dirname(os.path.abspath(__file__)); PP = os.path.expanduser("~/Downloads/planting_pipeline")
g = json.load(open(os.path.join(H0, "layers", "grid.json")))
W, H = g["size"]; (S_, W_), (N_, E_) = g["bounds"]; TR = from_origin(W_, N_, g["res_deg"], g["res_deg"])
px = dict(np.load(os.path.join(H0, "risk_drive_KE_ET.npz")))
adm = {k: np.full((H, W), np.nan, "float32") for k in px}; grey = np.zeros((H, W), bool)
FILES = ["Uganda_1strains", "Tanzania_Masika", "Tanzania_Msimu", "Rwanda_SeasonA", "Burundi_SeasonA", "Somalia_Gu", "SouthSudan_Main"]  # later overrides earlier
COLS = {"wrsi": "mean_WRSI", "cpi": "cpi", "deficit": "mean_deficit_mm"}
MIN_CAF = 0.01
# Somalia and South Sudan: maize is < 1 % of almost every (very large) district -> show any unit with >= 0.1 %
MIN_CAF_BY = {"Somalia_Gu": 0.001, "SouthSudan_Main": 0.001}
for f in FILES:
    d = pd.read_csv(os.path.join(PP, f"newc_{f}_2024_L2_skill_WKT.csv"))
    geoms = [wkt.loads(s) for s in d.geometry_wkt]
    ok = (d.crop_area_frac >= MIN_CAF_BY.get(f, MIN_CAF)).values
    cov = rasterize([(gm, 1) for gm in geoms], out_shape=(H, W), transform=TR).astype(bool)
    okm = rasterize([(gm, 1) for gm, o in zip(geoms, ok) if o], out_shape=(H, W), transform=TR).astype(bool) if ok.any() else np.zeros((H, W), bool)
    for k, c in COLS.items():
        v = d[c].values
        shp = [(gm, float(x)) for gm, x, o in zip(geoms, v, ok) if o and np.isfinite(x)]
        if shp:
            a = rasterize(shp, out_shape=(H, W), transform=TR, fill=np.nan, dtype="float32")
            adm[k] = np.where(okm & np.isfinite(a), a, np.where(cov & ~okm & ~np.isfinite(adm[k]), np.nan, adm[k]))
    grey = (grey | (cov & ~okm)) & ~np.isfinite(adm["cpi"])
    print(f, "units", len(d), "shown", int(ok.sum()))
RYG = LinearSegmentedColormap.from_list("ryg", ["#a50026", "#f46d43", "#fee08b", "#a6d96a", "#1a9850"])
STRESS = LinearSegmentedColormap.from_list("st", ["#ffffcc", "#fd8d3c", "#800026"])
for key, cm, lo, hi, name in (("wrsi", RYG, 40, 100, "risk_wrsi.png"), ("cpi", RYG, 0, 100, "risk_cpi.png"),
                              ("deficit", STRESS, 0, 200, "risk_stress.png")):
    a = np.where(np.isfinite(px[key]), px[key], adm[key])   # pixels (KE, ET) win; admin fills the rest
    ok = np.isfinite(a)
    rgba = (cm(np.clip((np.nan_to_num(a) - lo) / (hi - lo), 0, 1)) * 255).astype("uint8"); rgba[..., 3] = np.where(ok, 255, 0)
    gmask = grey & ~ok & ~np.isfinite(px[key]); rgba[gmask] = (170, 172, 165, 150)
    Image.fromarray(rgba, "RGBA").save(os.path.join(H0, "layers", name), optimize=True)
    print(name, "cells", int(ok.sum()))
