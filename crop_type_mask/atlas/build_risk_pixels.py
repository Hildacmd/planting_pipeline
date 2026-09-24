"""Pixel risk layers for the atlas from the Earth Engine export atlas_risk_2024.tif
(bands CPI, S_water, wrsi_flo, yield; mean of 250 m maize pixels in each 0.012 deg cell)."""
import glob, os, numpy as np, rasterio
from PIL import Image
from matplotlib.colors import LinearSegmentedColormap
H0 = os.path.dirname(os.path.abspath(__file__))
src = max(glob.glob(os.path.expanduser("~/Google Drive/My Drive/crop_type_mask/atlas_risk_2024*.tif")), key=os.path.getmtime)
with rasterio.open(src) as r:
    b = {d: r.read(i + 1).astype("float32") for i, d in enumerate(r.descriptions)}
    print(src, r.shape, r.descriptions)
RYG = LinearSegmentedColormap.from_list("ryg", ["#a50026", "#f46d43", "#fee08b", "#a6d96a", "#1a9850"])
STRESS = LinearSegmentedColormap.from_list("st", ["#ffffcc", "#fd8d3c", "#800026"])
def save(arr, cm, lo, hi, name):
    ok = np.isfinite(arr) & (arr != 0) if name != "risk_stress.png" else np.isfinite(arr)
    t = np.clip((np.nan_to_num(arr) - lo) / (hi - lo), 0, 1)
    rgba = (cm(t) * 255).astype("uint8"); rgba[..., 3] = np.where(ok & ~np.isnan(arr), 255, 0)
    Image.fromarray(rgba, "RGBA").save(os.path.join(H0, "layers", name), optimize=True)
    v = arr[ok]; print(name, "px", ok.sum(), "median", np.nanmedian(v) if v.size else None)
valid = np.isfinite(b["CPI"])
save(np.where(valid, b["CPI"], np.nan), RYG, 0, 100, "risk_cpi.png")
save(np.where(valid, b["wrsi_flo"], np.nan), RYG, 40, 100, "risk_wrsi.png")
save(np.where(valid, b["S_water"], np.nan), STRESS, 0, 60, "risk_stress.png")
