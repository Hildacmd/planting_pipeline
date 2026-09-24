"""Binary crop-mask layers for the atlas: mask_<crop> = the cell reaches 10 % of that crop AND the crop is
present in SPAM there. One PNG per crop, all countries mosaicked onto the atlas grid (max = a cell counts as
masked if any source pixel in it is masked)."""
import os, json, numpy as np, rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin
from PIL import Image
M = os.path.expanduser("~/Downloads/planting_pipeline/crop_type_mask"); H0 = os.path.join(M, "atlas")
g = json.load(open(os.path.join(H0, "layers", "grid.json")))
W, H = g["size"]; (S_, W_), (N_, E_) = g["bounds"]; TR = from_origin(W_, N_, g["res_deg"], g["res_deg"])
REL = {"Ethiopia": "ET", "Kenya": "KE", "Uganda": "UG", "Tanzania": "TZ", "Rwanda_SPAM2020": "RW20",
       "Burundi_SPAM2020": "BI20", "Somalia_SPAM2020": "SO20", "South_Sudan": "SS", "Sudan": "SD", "Eritrea": "ER"}
CROPS = {"maize": "#2a78d6", "wheat": "#eb6834", "sorghum": "#1baf7a", "teff": "#4a3aa7", "millet": "#b5195a"}
acc = {c: np.zeros((H, W), "uint8") for c in CROPS}
for folder, iso in REL.items():
    p = f"{M}/{folder}/outputs/{iso}_crop_mask_100m.tif"
    with rasterio.open(p) as r:
        names = list(r.descriptions)
        for c in CROPS:
            if f"mask_{c}" not in names:
                continue
            dst = np.zeros((H, W), "uint8")
            reproject(rasterio.band(r, names.index(f"mask_{c}") + 1), dst, src_transform=r.transform, src_crs=r.crs,
                      src_nodata=0, dst_transform=TR, dst_crs="EPSG:4326", dst_nodata=0, resampling=Resampling.max)
            acc[c] = np.maximum(acc[c], dst)
    print(folder, "done")
for c, hexcol in CROPS.items():
    rgb = [int(hexcol[i:i + 2], 16) for i in (1, 3, 5)]
    rgba = np.zeros((H, W, 4), "uint8"); m = acc[c] > 0
    rgba[m] = rgb + [255]
    Image.fromarray(rgba, "RGBA").save(os.path.join(H0, "layers", f"mask_{c}.png"), optimize=True)
    print(f"mask_{c}.png", int(m.sum()), "cells")
