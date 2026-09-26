#!/usr/bin/env python3
"""Atlas layer: dry-matter productivity, on the products where it is defined.

DMP (kg DM/ha over the crop's own cycle, from MODIS GPP) is carried on the EIGHT products where CPI
ranks admin units BACKWARDS against reported yield, and nowhere else - it adds nothing where the
water balance already works. So this layer is deliberately PARTIAL: it covers those products only,
and the rest of the region stays blank rather than being filled with a number that was never
computed.

It is a RANKING covariate and is drawn in kg DM/ha, never converted to a yield. Across 16
representative admin-scale frames the harvest index implied by observed yields sits inside the
agronomic 0.30-0.55 band in only 5, median 0.27, with DMP-derived yield a median 1.7x observed - so
the level is not usable even though the ranking is.

    python crop_type_mask/atlas/build_dmp_layer.py
"""
import json, os, sys
import numpy as np, pandas as pd
from PIL import Image
from matplotlib.colors import LinearSegmentedColormap
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely import wkt

H0 = os.path.dirname(os.path.abspath(__file__))
PP = os.path.expanduser("~/Downloads/planting_pipeline")
g = json.load(open(os.path.join(H0, "layers", "grid.json")))
W, H = g["size"]; (S_, W_), (N_, E_) = g["bounds"]
TR = from_origin(W_, N_, g["res_deg"], g["res_deg"])

# the 8 products that carry dmp: (crop, reduce stem)
JOBS = {
    "sorghum": ["newcS_Sudan_Kharif_2024", "newcS_Uganda_2ndrains_2024",
                "newcS_Rwanda_SeasonB_2024", "newcS_Kenya_Shortrains_2024",
                "newcS_Burundi_SeasonA_2024", "newcS_Uganda_1strains_2024"],
    "maize":   ["newc_Uganda_1strains_2024", "newc_Rwanda_SeasonA_2024"],
}
DMPC = LinearSegmentedColormap.from_list("dmp", ["#f7fcb9", "#addd8e", "#41ab5d", "#005a32"])
VMAX = 8000.0          # kg DM/ha; one scale across crops so the two layers read together


def build(crop, stems):
    a = np.full((H, W), np.nan, "float32")
    n_prod = 0
    for stem in stems:
        f = os.path.join(PP, f"{stem}_L2_skill_WKT.csv")
        if not os.path.exists(f):
            print(f"  [skip] {stem}: no reduce CSV"); continue
        d = pd.read_csv(f)
        if "dmp" not in d.columns or d.dmp.notna().sum() == 0:
            print(f"  [skip] {stem}: no dmp column"); continue
        geoms = [wkt.loads(s) for s in d.geometry_wkt]
        shp = [(gm, float(v)) for gm, v in zip(geoms, d.dmp.astype(float))
               if np.isfinite(v) and v > 0]
        if not shp:
            continue
        r = rasterize(shp, out_shape=(H, W), transform=TR, fill=np.nan, dtype="float32")
        a = np.where(np.isfinite(r), r, a)
        n_prod += 1
        print(f"  {stem:<32} units {len(d):>3}  with dmp {int(d.dmp.notna().sum()):>3}")
    ok = np.isfinite(a)
    if not ok.any():
        return print(f"  {crop}: nothing to draw")
    rgba = np.zeros((H, W, 4), "uint8")
    rgba[ok] = (np.array(DMPC(np.clip(a[ok] / VMAX, 0, 1))) * 255).astype("uint8")
    rgba[..., 3] = np.where(ok, 235, 0)
    out = os.path.join(H0, "layers", f"risk_{crop}_dmp.png")
    Image.fromarray(rgba).save(out)
    print(f"  wrote risk_{crop}_dmp.png   {n_prod} product(s), "
          f"median {np.nanmedian(a):,.0f} kg DM/ha, ramp 0-{VMAX:,.0f}")


if __name__ == "__main__":
    for crop, stems in JOBS.items():
        print(f"=== {crop.upper()}")
        build(crop, stems)
