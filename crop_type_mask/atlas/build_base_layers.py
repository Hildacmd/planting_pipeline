"""Base layers for the atlas: SRTM hillshade and permanent water (JRC Global Surface Water >= 50 % occurrence),
from the Earth Engine export atlas_base_hillshade_water.tif. Both are baked into the page as PNGs, so they work
where external map tiles are blocked."""
import glob, os, numpy as np, rasterio
from PIL import Image
H0 = os.path.dirname(os.path.abspath(__file__))
src = max(glob.glob(os.path.expanduser("~/Google Drive/My Drive/crop_type_mask/atlas_base_hillshade_water*.tif")), key=os.path.getmtime)
with rasterio.open(src) as r:
    d = list(r.descriptions)
    hill = r.read(d.index("hillshade") + 1).astype("float32")
    water = r.read(d.index("water") + 1)
    print(src, r.shape, d)
# hillshade: grey shading, transparent where flat/bright so the land tint shows through
sh = np.clip((180 - hill) / 180, 0, 1) ** 1.15            # 0 = lit, 1 = deep shadow
rgba = np.zeros(hill.shape + (4,), "uint8")
rgba[..., :3] = 40
rgba[..., 3] = (sh * 150).astype("uint8")
Image.fromarray(rgba, "RGBA").save(os.path.join(H0, "layers", "hillshade.png"), optimize=True)
w = np.zeros(water.shape + (4,), "uint8")
m = water > 0
w[m] = (122, 160, 176, 255)
Image.fromarray(w, "RGBA").save(os.path.join(H0, "layers", "water.png"), optimize=True)
for f in ("hillshade.png", "water.png"):
    print(f, os.path.getsize(os.path.join(H0, "layers", f)) // 1024, "KB")
