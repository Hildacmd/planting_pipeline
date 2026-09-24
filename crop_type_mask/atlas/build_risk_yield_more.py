"""Add Rwanda, Burundi, Somalia and Uganda (provisional) to the atlas yield layer: 2024 admin-2 CPI x the Ym
calibrated to HarvestStat by calibrate_ym_local.py. Composited onto the Kenya/Ethiopia yield PNG from
build_risk_admin.py (the countries do not overlap). Same grey rule as the other risk layers."""
import os, json, numpy as np, pandas as pd
from shapely import wkt
from rasterio.features import rasterize
from rasterio.transform import from_origin
from PIL import Image
from matplotlib.colors import LinearSegmentedColormap
H0 = os.path.dirname(os.path.abspath(__file__)); PP = os.path.expanduser("~/Downloads/planting_pipeline")
g = json.load(open(os.path.join(H0, "layers", "grid.json")))
W, H = g["size"]; (S_, W_), (N_, E_) = g["bounds"]; TR = from_origin(W_, N_, g["res_deg"], g["res_deg"])
cal = pd.read_csv(os.path.join(PP, "Cropyield-Data", "ym_calibration_local.csv")).set_index("file")
cal = cal[~cal.index.str.startswith("app:")]          # Kenya/Ethiopia yields come from build_risk_admin.py
MIN = {"Somalia_Gu": 0.001}          # as in the other risk layers
ISO = {"Rwanda_SeasonA": "RWA", "Burundi_SeasonA": "BDI", "Somalia_Gu": "SOM", "Uganda_1strains": "UGA"}
base = np.array(Image.open(os.path.join(H0, "layers", "risk_yield.png"))).copy()
cm = LinearSegmentedColormap.from_list("y", ["#f7fcb9", "#78c679", "#005a32"])
summ = json.load(open(os.path.join(H0, "risk_summary.json")))
for stem, row in cal.iterrows():
    d = pd.read_csv(os.path.join(PP, f"newc_{stem}_2024_L2_skill_WKT.csv"))
    geoms = [wkt.loads(s) for s in d.geometry_wkt]
    ok = (d.crop_area_frac >= MIN.get(stem, 0.01)) & d.cpi.notna()
    yv = d.cpi / 100 * row.ym_cal
    cov = rasterize([(gm, 1) for gm in geoms], out_shape=(H, W), transform=TR).astype(bool)
    a = rasterize([(gm, float(v)) for gm, v, o in zip(geoms, yv, ok) if o], out_shape=(H, W), transform=TR, fill=0, dtype="float32")
    rgba = (cm(np.clip(a / 4.0, 0, 1)) * 255).astype("uint8")
    base[a > 0] = rgba[a > 0]; base[a > 0, 3] = 255
    base[cov & (a <= 0)] = (170, 172, 165, 150)
    w = d.crop_area_frac[ok]
    e = summ.setdefault(ISO[stem], {})
    e["yield_median"] = round(float(np.median(yv[ok])), 2)
    e["yield_note"] = (f"Yield ceiling {row.ym_cal} t/ha fitted to HarvestStat {row.season} {row.years} ({row.n_units} units; "
                       f"test error {row.test_mae_cal} t/ha vs {row.test_mae_default} uncalibrated). Level only — the ranking of units is not reliable."
                       + (" Provisional: statistics end in 2009." if row.provisional else ""))
    print(stem, "shown", int(ok.sum()), "median yield", e["yield_median"])
Image.fromarray(base, "RGBA").save(os.path.join(H0, "layers", "risk_yield.png"), optimize=True)
json.dump(summ, open(os.path.join(H0, "risk_summary.json"), "w"), indent=1)
