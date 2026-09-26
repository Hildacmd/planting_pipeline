"""Atlas risk layers for wheat, teff and millet, from the 2024 admin-2 statistics.

Same construction as `build_risk_sorghum.py`: rasterised from the reduce CSVs onto the atlas grid,
no further Earth Engine work. Five layers per crop — CPI, WRSI, water deficit (mm), yield, crop
failure — with yield RESCALED to the fitted ceiling, which is exact because yield is linear in Ym.

**Sudan's Shitwi wheat is excluded.** It is scheme-irrigated, the rainfed water balance returns
WRSI 0 and CPI 0 across all 18 localities including the Gezira, and drawing that as a crop-failure
layer would state a regional catastrophe that is not happening.

    python crop_type_mask/atlas/build_risk_crop.py --crop wheat
    python crop_type_mask/atlas/build_risk_crop.py --crop all
"""
import argparse, json, os, sys
import numpy as np, pandas as pd
from PIL import Image
from matplotlib.colors import LinearSegmentedColormap
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely import wkt

H0 = os.path.dirname(os.path.abspath(__file__))
PP = os.path.expanduser("~/Downloads/planting_pipeline")
sys.path.insert(0, os.path.join(PP, "crop_pipeline"))
from params import get                                                # noqa: E402

g = json.load(open(os.path.join(H0, "layers", "grid.json")))
W, H = g["size"]; (S_, W_), (N_, E_) = g["bounds"]
TR = from_origin(W_, N_, g["res_deg"], g["res_deg"])

PREFIX = {"wheat": "newcW", "teff": "newcT", "millet": "newcM"}
# crop -> [(token, country, season, Ym the asset was built with, min crop share to colour)]
JOBS = {
    "wheat":  [("Tanzania_Msimu",  "Tanzania", "Msimu",      4.0, 0.001),
               ("Kenya_Longrains", "Kenya",    "Long rains", 4.0, 0.001),
               ("Ethiopia_Meher",  "Ethiopia", "Meher",      4.0, 0.001)],
    "teff":   [("Ethiopia_Meher",  "Ethiopia", "Meher",      2.0, 0.001)],
    "millet": [("Eritrea_Kremti",  "Eritrea",  "Kremti",     2.0, 0.001),
               ("Sudan_Kharif",    "Sudan",    "Kharif",     2.0, 0.001)],
}
COLS = {"wrsi": "mean_WRSI", "cpi": "cpi", "stress": "mean_deficit_mm",
        "yield": "yield_tha", "fail": "failflo_pct"}
RYG = LinearSegmentedColormap.from_list("ryg", ["#a50026", "#f46d43", "#fee08b", "#a6d96a", "#1a9850"])
STRESS = LinearSegmentedColormap.from_list("st", ["#ffffcc", "#fd8d3c", "#800026"])
YLD = LinearSegmentedColormap.from_list("y", ["#f7fcb9", "#78c679", "#005a32"])
FAIL = LinearSegmentedColormap.from_list("f", ["#ffffff", "#fdae61", "#a50026"])
yy, xx = np.mgrid[0:H, 0:W]
HATCH = ((xx + yy) % 9) < 2


def build(crop):
    p = get(crop)
    adm = {k: np.full((H, W), np.nan, "float32") for k in COLS}
    grey = np.zeros((H, W), bool); uncal = np.zeros((H, W), bool); nodef = set()
    ymax = 0.0
    for tok, country, season, ym_used, min_caf in JOBS[crop]:
        f = os.path.join(PP, f"{PREFIX[crop]}_{tok}_2024_L2_skill_WKT.csv")
        if not os.path.exists(f):
            print(f"  [skip] {tok}: no reduce CSV"); continue
        d = pd.read_csv(f)
        geoms = [wkt.loads(s) for s in d.geometry_wkt]
        ok = (d.crop_area_frac.fillna(0) >= min_caf).values
        cov = rasterize([(gm, 1) for gm in geoms], out_shape=(H, W), transform=TR).astype(bool)
        okm = (rasterize([(gm, 1) for gm, o in zip(geoms, ok) if o], out_shape=(H, W),
                         transform=TR).astype(bool) if ok.any() else np.zeros((H, W), bool))
        ym_fit = p.YM_CAL.get((country.replace(" ", "_"), season))
        if ym_fit is None:
            uncal |= okm
        ymax = max(ymax, ym_fit or ym_used)
        for k, col in COLS.items():
            if k == "stress" and (col not in d.columns or d[col].notna().sum() == 0):
                nodef.add(tok); continue
            if col not in d.columns:
                continue
            v = d[col].astype(float).values
            if k == "yield" and ym_fit is not None:
                v = v * (ym_fit / ym_used)
            shp = [(gm, float(x)) for gm, x, o in zip(geoms, v, ok) if o and np.isfinite(x)]
            if shp:
                a = rasterize(shp, out_shape=(H, W), transform=TR, fill=np.nan, dtype="float32")
                adm[k] = np.where(okm & np.isfinite(a), a, adm[k])
        grey |= cov & ~okm
        print(f"  {tok:<20} units {len(d):>3}  shown {int(ok.sum()):>3}  "
              f"Ym {ym_used} -> {ym_fit if ym_fit else 'UNCALIBRATED (hatched)'}")
    grey &= ~np.isfinite(adm["cpi"])

    layers = [("wrsi", RYG, 40, 100), ("cpi", RYG, 0, 100), ("stress", STRESS, 0, 200),
              ("yield", YLD, 0, round(ymax, 1)), ("fail", FAIL, 0, 100)]
    for key, cm, lo, hi in layers:
        name = f"risk_{crop}_{key}.png"
        if key == "stress" and nodef:
            print(f"  SKIPPED {name}: {sorted(nodef)} have no mean_deficit_mm; the legend commits "
                  f"to millimetres and drawing a percentage under it would be wrong")
            continue
        a = adm[key]; okm = np.isfinite(a)
        rgba = (cm(np.clip((np.nan_to_num(a) - lo) / max(hi - lo, 1e-6), 0, 1)) * 255).astype("uint8")
        rgba[..., 3] = np.where(okm, 255, 0)
        rgba[grey & ~okm] = (170, 172, 165, 150)
        if key == "yield":
            rgba[uncal & okm & HATCH] = (60, 60, 60, 255)
        Image.fromarray(rgba, "RGBA").save(os.path.join(H0, "layers", name), optimize=True)
        v = a[okm]
        print(f"  {name:<28} cells {int(okm.sum()):>7}  median "
              f"{np.nanmedian(v) if v.size else float('nan'):.1f}  (ramp 0 to {hi})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--crop", default="all", choices=["wheat", "teff", "millet", "all"])
    a = ap.parse_args()
    for c in (["wheat", "teff", "millet"] if a.crop == "all" else [a.crop]):
        print(f"\n=== {c.upper()} ===")
        build(c)
