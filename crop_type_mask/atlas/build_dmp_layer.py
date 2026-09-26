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
import json, os, re, sys
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

# PER-CROP STRETCH. A shared scale made sorghum read as uniformly pale: its products sit in drier
# systems (median 1,857 kg DM/ha) against maize's 5,890, so three quarters of the sorghum ramp was
# never used. Each crop is now stretched to its own 98th percentile - the 98th rather than the max,
# so one outlier district cannot compress everything else.
#
# The consequence is that the two layers are NO LONGER COMPARABLE BETWEEN CROPS, and the legend has
# to say so. This builder therefore writes the legend numbers into index.html itself, so the ramp
# and its labels cannot drift apart.
PCTL = 98


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
    vmax = float(np.nanpercentile(a[ok], PCTL))
    vmax = max(500.0, round(vmax / 500.0) * 500.0)          # a round number for the legend
    rgba = np.zeros((H, W, 4), "uint8")
    rgba[ok] = (np.array(DMPC(np.clip(a[ok] / vmax, 0, 1))) * 255).astype("uint8")
    rgba[..., 3] = np.where(ok, 235, 0)
    out = os.path.join(H0, "layers", f"risk_{crop}_dmp.png")
    Image.fromarray(rgba).save(out)
    print(f"  wrote risk_{crop}_dmp.png   {n_prod} product(s), "
          f"median {np.nanmedian(a):,.0f}  p{PCTL} {np.nanpercentile(a[ok], PCTL):,.0f}  "
          f"ramp 0-{vmax:,.0f} kg DM/ha")
    return vmax


def sync_legend(crop, vmax):
    """Write this crop's own ramp numbers into index.html, so legend and image cannot disagree."""
    p = os.path.join(H0, "index.html")
    s = open(p).read()
    i = s.find(f'{{id:"risk_{crop}_dmp"')
    if i < 0:
        return print(f"  [warn] {crop}: no index.html entry to update")
    j = s.find("}},", i)
    blk = s[i:j]
    half = vmax / 2
    fmt = lambda v: f"{int(v):,}".replace(",", "\u202f")      # thin space, as the atlas uses
    # lambda replacement: a plain string would have re.sub parse the \u escapes as its own
    repl = f'labels:["0","{fmt(half)}","\\u2265 {fmt(vmax)} kg DM/ha"]'
    new = re.sub(r'labels:\[[^\]]*\]', lambda _m: repl, blk)
    # the scale is per-crop now, so say it
    new = new.replace("Drawn in kg DM/ha on one scale across both crops so they read together.", "")
    if "stretched to its own" not in new:
        new = new.replace('use:"A RANKING covariate',
                          f'use:"Scale is stretched to THIS crop\u2019s own range (0\u2013{fmt(vmax)} '
                          f'kg DM/ha, its 98th percentile), so colours are NOT comparable with the '
                          f'other crop\u2019s DMP layer. A RANKING covariate', 1)
    s = s[:i] + new + s[j:]
    open(p, "w").write(s)
    print(f"  index.html legend for {crop}: 0 - {vmax:,.0f} kg DM/ha")


if __name__ == "__main__":
    for crop, stems in JOBS.items():
        print(f"=== {crop.upper()}")
        vmax = build(crop, stems)
        if vmax:
            sync_legend(crop, vmax)
