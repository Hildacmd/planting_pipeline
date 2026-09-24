"""Tanzania (Msimu over Masika) and South Sudan (main) 2024 maize yield AS PRODUCED by the pipeline (CPI x the
uncalibrated default ceiling of 6.0 t/ha - no HarvestStat maize yields exist to calibrate against), composited onto
the atlas yield layer with a diagonal hatch so they are never read as calibrated values."""
import os, json, numpy as np, pandas as pd
from shapely import wkt
from rasterio.features import rasterize
from rasterio.transform import from_origin
from PIL import Image
from matplotlib.colors import LinearSegmentedColormap
H0 = os.path.dirname(os.path.abspath(__file__)); PP = os.path.expanduser("~/Downloads/planting_pipeline")
g = json.load(open(os.path.join(H0, "layers", "grid.json")))
W, H = g["size"]; (S_, W_), (N_, E_) = g["bounds"]; TR = from_origin(W_, N_, g["res_deg"], g["res_deg"])
JOBS = [("Tanzania_Masika", "TZA", 0.01), ("Tanzania_Msimu", "TZA", 0.01), ("SouthSudan_Main", "SSD", 0.001)]  # later overrides
base = np.array(Image.open(os.path.join(H0, "layers", "risk_yield.png"))).copy()
cm = LinearSegmentedColormap.from_list("y", ["#f7fcb9", "#78c679", "#005a32"])
yy, xx = np.mgrid[0:H, 0:W]; hatch = ((xx + yy) % 9) < 2          # diagonal stripes every 9 cells
summ = json.load(open(os.path.join(H0, "risk_summary.json"))); vals = {}
for stem, iso, thr in JOBS:
    d = pd.read_csv(os.path.join(PP, f"newc_{stem}_2024_L2_skill_WKT.csv"))
    geoms = [wkt.loads(s) for s in d.geometry_wkt]
    ok = (d.crop_area_frac >= thr) & d.yield_tha.notna()
    cov = rasterize([(gm, 1) for gm in geoms], out_shape=(H, W), transform=TR).astype(bool)
    a = rasterize([(gm, float(v)) for gm, v, o in zip(geoms, d.yield_tha, ok) if o], out_shape=(H, W), transform=TR, fill=0, dtype="float32")
    rgba = (cm(np.clip(a / 4.0, 0, 1)) * 255).astype("uint8")
    m = a > 0
    base[m] = rgba[m]; base[m, 3] = 255
    base[m & hatch] = (255, 255, 255, 235)                             # hatch = uncalibrated
    base[cov & ~m & (base[..., 3] == 0)] = (170, 172, 165, 150)
    vals.setdefault(iso, []).extend(d.yield_tha[ok].tolist())
for iso, v in vals.items():
    e = summ.setdefault(iso, {})
    e["yield_median"] = round(float(np.median(v)), 2)
    e["yield_uncal"] = True
    e["yield_note"] = ("UNCALIBRATED: CPI × the default ceiling of 6.0 t/ha, shown hatched. There are no HarvestStat maize "
                       "yields to calibrate against; in Rwanda, Burundi and Somalia the default ran 3–7× above reported yields, "
                       "so read these as relative, not absolute, values.")
    print(iso, "median", e["yield_median"])
Image.fromarray(base, "RGBA").save(os.path.join(H0, "layers", "risk_yield.png"), optimize=True)
json.dump(summ, open(os.path.join(H0, "risk_summary.json"), "w"), indent=1)
