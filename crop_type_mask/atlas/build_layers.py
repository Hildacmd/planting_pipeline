"""Regional mosaics (~1.3 km) of the crop-type products for the HTML atlas.
Reads each released country's 100 m GeoTIFFs and resamples them onto one plate-carree grid
(average for fractions/percentages, mode for the dominant code), then writes transparent PNGs."""
import os, json, numpy as np, rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin
from PIL import Image
import matplotlib
from matplotlib.colors import LinearSegmentedColormap
M = os.path.expanduser("~/Downloads/planting_pipeline/crop_type_mask")
OUT = os.path.join(M, "atlas", "layers")
W_, S_, E_, N_ = 21.8, -11.8, 51.5, 23.2
RES = 0.012
W, H = int(round((E_ - W_) / RES)), int(round((N_ - S_) / RES))
TR = from_origin(W_, N_, RES, RES)
REL = {"Ethiopia": "ET", "Kenya": "KE", "Uganda": "UG", "Tanzania": "TZ", "Rwanda_SPAM2020": "RW20", "Burundi_SPAM2020": "BI20",
       "Somalia_SPAM2020": "SO20", "South_Sudan": "SS", "Sudan": "SD", "Eritrea": "ER"}
CROPS = ["maize", "wheat", "sorghum", "teff", "millet"]
COL = {"maize": "#2a78d6", "wheat": "#eb6834", "sorghum": "#1baf7a", "teff": "#4a3aa7", "millet": "#b5195a"}

def warp(path, band, rs, dtype="float32"):
    dst = np.zeros((H, W), dtype)
    with rasterio.open(path) as r:
        reproject(rasterio.band(r, band), dst, src_transform=r.transform, src_crs=r.crs, src_nodata=0,
                  dst_transform=TR, dst_crs="EPSG:4326", dst_nodata=0, resampling=rs)
    return dst

def bandidx(path, name):
    with rasterio.open(path) as r:
        d = list(r.descriptions)
    return d.index(name) + 1 if name in d else None

dom = np.zeros((H, W), "uint8"); frac = {c: np.zeros((H, W), "float32") for c in CROPS}
cl = np.zeros((H, W), "float32"); agree = np.zeros((H, W), "float32"); conf = np.zeros((H, W), "float32")
for folder, iso in REL.items():
    o = f"{M}/{folder}/outputs"
    mk, fr, cf, cp = (f"{o}/{iso}_crop_{k}_100m.tif" for k in ("mask", "fraction", "confidence", "cropland"))
    d = warp(mk, bandidx(mk, "dominant"), Resampling.mode, "uint8"); dom = np.where(d > 0, d, dom)
    for c in CROPS:
        b = bandidx(fr, f"frac_{c}")
        if b:
            a = warp(fr, b, Resampling.average); frac[c] = np.where(a > 0, a, frac[c])
    a = warp(cp, 1, Resampling.average); cl = np.where(a > 0, a, cl)
    a = warp(cp, 3, Resampling.average); agree = np.where(a > 0, a, agree)
    cmax = np.zeros((H, W), "float32")
    for c in CROPS:
        b = bandidx(cf, f"conf_{c}")
        if b:
            cmax = np.maximum(cmax, warp(cf, b, Resampling.average))
    conf = np.where(cmax > 0, cmax, conf)
    print(folder, "done")
# Djibouti: cropland only (any one lineage, and the vote for agreement)
dj = f"{M}/Djibouti/outputs"
djany = warp(f"{dj}/DJ_cropland_any_lineage_100m.tif", 1, Resampling.max, "uint8")
a = warp(f"{dj}/DJ_crop_cropland_100m.tif", 1, Resampling.average); cl = np.where(a > 0, a, cl)
a = warp(f"{dj}/DJ_crop_cropland_100m.tif", 3, Resampling.average); agree = np.where(a > 0, a, agree)
conf = np.where(dom > 0, conf, 0)

def rgba_from(arr, cmap, lo, hi, mask):
    t = np.clip((arr - lo) / (hi - lo), 0, 1)
    rgba = (cmap(t) * 255).astype("uint8"); rgba[..., 3] = np.where(mask, 255, 0)
    return rgba

def save(rgba, name):
    Image.fromarray(rgba, "RGBA").save(os.path.join(OUT, name), optimize=True)
    print(name, os.path.getsize(os.path.join(OUT, name)) // 1024, "KB")

# dominant (codes 1-5) + Djibouti cropland (code 9)
lut = np.zeros((10, 4), "uint8")
for c, code in zip(CROPS, [1, 2, 3, 4, 5]):
    h = COL[c].lstrip("#"); lut[code] = [int(h[i:i + 2], 16) for i in (0, 2, 4)] + [255]
lut[9] = [140, 90, 43, 255]
d2 = np.where((dom == 0) & (djany > 0), 9, dom)
save(lut[d2], "dominant.png")
for c in CROPS:
    cm = LinearSegmentedColormap.from_list(c, ["#ffffff", COL[c], "#111111"], N=256)
    cm2 = LinearSegmentedColormap.from_list(c + "2", [cm(0.18), cm(0.55), cm(0.85)])
    save(rgba_from(frac[c], cm2, 0.5, 40, frac[c] >= 0.5), f"frac_{c}.png")
brown = LinearSegmentedColormap.from_list("cl", ["#efe2c4", "#c58a3a", "#5c3510"])
save(rgba_from(cl, brown, 1, 100, cl >= 1), "cropland.png")
div = LinearSegmentedColormap.from_list("ag", ["#c2410c", "#f3efe4", "#0f766e"])
save(rgba_from(agree, div, 0, 100, (cl >= 1) | (agree > 0) & (agree < 100)), "agreement.png")
grey = LinearSegmentedColormap.from_list("cf", ["#e7e9e3", "#6b7a72", "#14201a"])
save(rgba_from(conf, grey, 30, 90, conf > 0), "confidence.png")
json.dump({"bounds": [[S_, W_], [N_, E_]], "res_deg": RES, "size": [W, H]}, open(os.path.join(OUT, "grid.json"), "w"))
