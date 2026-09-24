"""Pixel risk layers for the 2024 main maize season from the GeoTIFFs already on Google Drive
(planting_outputs/): season WRSI and season water deficit (wrsi_*, 250 m Mollweide) and CPI (cpi_*, 250 m WGS84).
Mean of 250 m maize pixels in each atlas cell. The other six countries are added from the Earth Engine export later."""
import glob, os, numpy as np, rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin
from PIL import Image
from matplotlib.colors import LinearSegmentedColormap
import json
H0 = os.path.dirname(os.path.abspath(__file__))
g = json.load(open(os.path.join(H0, "layers", "grid.json")))
W, H = g["size"]; (S_, W_), (N_, E_) = g["bounds"]; TR = from_origin(W_, N_, g["res_deg"], g["res_deg"])
DRV = os.path.expanduser("~/Google Drive/My Drive/planting_outputs")
def newest(pat):
    fs = [f for f in glob.glob(os.path.join(DRV, pat)) if "estcal" not in f]
    return max(fs, key=os.path.getmtime)
SRC = {"KE": {"wrsi": newest("wrsi_Kenya_maize_Longrains_2024*.tif"), "cpi": newest("cpi_Kenya_Longrains_2024*.tif")},
       "ET": {"wrsi": newest("wrsi_Ethiopia_maize_Meher_2024_250m*.tif"), "cpi": newest("cpi_Ethiopia_Meher_2024*.tif")}}
# the six countries exported 2026-09-22 (export_wrsi_newcountries.py + the CPI band of cpiX_*); Masika under Msimu
for _tok, _k in [("Tanzania_Masika", "TZm"), ("Tanzania_Msimu", "TZ"), ("Uganda_1strains", "UG"), ("Rwanda_SeasonA", "RW"),
                 ("Burundi_SeasonA", "BI"), ("Somalia_Gu", "SO"), ("SouthSudan_Main", "SS")]:
    _w = sorted(glob.glob(os.path.join(DRV, f"wrsi_{_tok}_2024_250m*.tif")), key=os.path.getmtime)
    _c = sorted(glob.glob(os.path.join(DRV, f"cpi_{_tok}_2024_250m*.tif")), key=os.path.getmtime)
    if _c:
        SRC[_k] = {"wrsi": _w[-1] if _w else None, "cpi": _c[-1]}
def warp(path, band):
    dst = np.full((H, W), np.nan, "float32")
    with rasterio.open(path) as r:
        a = r.read(band).astype("float32")
        if r.count == 1 or r.descriptions[band - 1] == "CPI":
            a[a <= 0] = np.nan                 # outside the maize mask
        else:
            wr = r.read(1).astype("float32"); a[~np.isfinite(wr) | (wr <= 0)] = np.nan
        reproject(a, dst, src_transform=r.transform, src_crs=r.crs, src_nodata=np.nan, dst_transform=TR,
                  dst_crs="EPSG:4326", dst_nodata=np.nan, resampling=Resampling.average)
    return dst
out = {k: np.full((H, W), np.nan, "float32") for k in ("wrsi", "deficit", "cpi")}
for c, f in SRC.items():
    print(c, os.path.basename(f["wrsi"]) if f["wrsi"] else "-", os.path.basename(f["cpi"]))
    with rasterio.open(f["cpi"]) as r:
        d = list(r.descriptions); cpi_b = d.index("CPI") + 1 if "CPI" in d else 1
    jobs = [("cpi", f["cpi"], cpi_b)]
    if f["wrsi"]:
        jobs += [("wrsi", f["wrsi"], 1), ("deficit", f["wrsi"], 2)]
    else:
        print(f"  {c}: no WRSI raster yet - keeps the admin-2 means")
    for key, path, band in jobs:
        a = warp(path, band); out[key] = np.where(np.isfinite(a), a, out[key])
np.savez_compressed(os.path.join(H0, "risk_drive_KE_ET.npz"), **out)     # kept so the EE export can be merged later
RYG = LinearSegmentedColormap.from_list("ryg", ["#a50026", "#f46d43", "#fee08b", "#a6d96a", "#1a9850"])
STRESS = LinearSegmentedColormap.from_list("st", ["#ffffcc", "#fd8d3c", "#800026"])
for key, cm, lo, hi, name in (("wrsi", RYG, 40, 100, "risk_wrsi.png"), ("cpi", RYG, 0, 100, "risk_cpi.png"),
                              ("deficit", STRESS, 0, 200, "risk_stress.png")):
    a = out[key]; ok = np.isfinite(a)
    rgba = (cm(np.clip((np.nan_to_num(a) - lo) / (hi - lo), 0, 1)) * 255).astype("uint8"); rgba[..., 3] = np.where(ok, 255, 0)
    Image.fromarray(rgba, "RGBA").save(os.path.join(H0, "layers", name), optimize=True)
    print(name, "cells", int(ok.sum()), "median %.1f" % np.nanmedian(a))
