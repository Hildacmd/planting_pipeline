"""Per-crop confidence layers (conf_<crop>, inside that crop's mask) and the two cropland diagnostic bands
not yet shown (vote_pct, nvotes), so every band of the crop-type mask products is visualised."""
import os, json, numpy as np, rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin
from PIL import Image
from matplotlib.colors import LinearSegmentedColormap
M = os.path.expanduser("~/Downloads/planting_pipeline/crop_type_mask"); H0 = os.path.join(M, "atlas")
g = json.load(open(os.path.join(H0, "layers", "grid.json")))
W, H = g["size"]; (S_, W_), (N_, E_) = g["bounds"]; TR = from_origin(W_, N_, g["res_deg"], g["res_deg"])
REL = {"Ethiopia": "ET", "Kenya": "KE", "Uganda": "UG", "Tanzania": "TZ", "Rwanda_SPAM2020": "RW20",
       "Burundi_SPAM2020": "BI20", "Somalia_SPAM2020": "SO20", "South_Sudan": "SS", "Sudan": "SD", "Eritrea": "ER"}
CROPS = ["maize", "wheat", "sorghum", "teff", "millet"]
conf = {c: np.zeros((H, W), "float32") for c in CROPS}
vote = np.zeros((H, W), "float32"); nvotes = np.zeros((H, W), "float32")

def warp(r, band, rs=Resampling.average):
    dst = np.zeros((H, W), "float32")
    reproject(rasterio.band(r, band), dst, src_transform=r.transform, src_crs=r.crs, src_nodata=0,
              dst_transform=TR, dst_crs="EPSG:4326", dst_nodata=0, resampling=rs)
    return dst

for folder, iso in REL.items():
    o = f"{M}/{folder}/outputs"
    with rasterio.open(f"{o}/{iso}_crop_confidence_100m.tif") as rc, rasterio.open(f"{o}/{iso}_crop_mask_100m.tif") as rm:
        cn, mn = list(rc.descriptions), list(rm.descriptions)
        for c in CROPS:
            if f"conf_{c}" not in cn or f"mask_{c}" not in mn:
                continue
            a = warp(rc, cn.index(f"conf_{c}") + 1)
            m = warp(rm, mn.index(f"mask_{c}") + 1, Resampling.max)
            a = np.where(m > 0, a, 0)
            conf[c] = np.where(a > 0, a, conf[c])
    with rasterio.open(f"{o}/{iso}_crop_cropland_100m.tif") as r:
        d = list(r.descriptions)
        v = warp(r, d.index("vote_pct") + 1); vote = np.where(v > 0, v, vote)
        n = warp(r, d.index("nvotes") + 1, Resampling.max); nvotes = np.where(n > 0, n, nvotes)
    print(folder, "done", flush=True)

def save(arr, cmap, lo, hi, name):
    ok = arr > 0
    rgba = (cmap(np.clip((arr - lo) / (hi - lo), 0, 1)) * 255).astype("uint8"); rgba[..., 3] = np.where(ok, 255, 0)
    Image.fromarray(rgba, "RGBA").save(os.path.join(H0, "layers", name), optimize=True)
    print(name, int(ok.sum()), "cells")

COL = {"maize": "#2a78d6", "wheat": "#eb6834", "sorghum": "#1baf7a", "teff": "#4a3aa7", "millet": "#b5195a"}
for c in CROPS:
    cm = LinearSegmentedColormap.from_list("c", ["#e9ebe7", COL[c], "#10150f"])
    save(conf[c], cm, 30, 90, f"conf_{c}.png")
save(vote, LinearSegmentedColormap.from_list("v", ["#f3f2ee", "#8c6d31", "#0b0b0b"]), 0, 100, "vote.png")
save(nvotes, LinearSegmentedColormap.from_list("n", ["#e34948", "#f3f2ee", "#1f4e3d"]), 8, 16, "nvotes.png")
