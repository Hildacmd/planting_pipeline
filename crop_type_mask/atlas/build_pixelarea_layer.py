"""Pixel-area layer for the atlas: the true hectares-per-pixel rasters of all countries, mosaicked."""
import os, json, numpy as np, rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin
from PIL import Image
from matplotlib.colors import LinearSegmentedColormap
M = os.path.expanduser("~/Downloads/planting_pipeline/crop_type_mask"); H0 = os.path.join(M, "atlas")
g = json.load(open(os.path.join(H0, "layers", "grid.json")))
W, H = g["size"]; (S_, W_), (N_, E_) = g["bounds"]; TR = from_origin(W_, N_, g["res_deg"], g["res_deg"])
REL = {"Ethiopia": "ET", "Kenya": "KE", "Uganda": "UG", "Tanzania": "TZ", "Rwanda_SPAM2020": "RW20",
       "Burundi_SPAM2020": "BI20", "Somalia_SPAM2020": "SO20", "South_Sudan": "SS", "Sudan": "SD",
       "Eritrea": "ER", "Djibouti": "DJ"}
out = np.zeros((H, W), "float32")
for folder, iso in REL.items():
    p = f"{M}/{folder}/outputs/{iso}_pixel_area_ha_100m.tif"
    if not os.path.exists(p):
        continue
    with rasterio.open(p) as r:
        dst = np.zeros((H, W), "float32")
        reproject(rasterio.band(r, 1), dst, src_transform=r.transform, src_crs=r.crs, src_nodata=0,
                  dst_transform=TR, dst_crs="EPSG:4326", dst_nodata=0, resampling=Resampling.average)
    out = np.where(dst > 0, dst, out)
    print(folder, "done", flush=True)
cm = LinearSegmentedColormap.from_list("pa", ["#3b2f6b", "#7f9bb5", "#e9e4cf"])
ok = out > 0
rgba = (cm(np.clip((out - 0.92) / (1.00 - 0.92), 0, 1)) * 255).astype("uint8"); rgba[..., 3] = np.where(ok, 255, 0)
Image.fromarray(rgba, "RGBA").save(os.path.join(H0, "layers", "pixel_area.png"), optimize=True)
print("pixel_area.png", int(ok.sum()), "cells", round(float(out[ok].min()), 3), "-", round(float(out[ok].max()), 3), "ha")
