#!/usr/bin/env python3
"""Split the crop-type mask into IRRIGATED and RAINFED fractions, using SPAM's technology layers.

The FAO-56 water balance is rainfed by construction (`Wb = SW + P`, no irrigation term), so on an
irrigated crop it reports the irrigation requirement under the name of crop stress. The fix that
does not require inventing an applied-water dataset is to stop mixing the two technologies in one
stratum: run a RAINFED product over rainfed area, where the balance is valid, and report the
irrigated area's deficit as a requirement rather than a condition.

MapSPAM 2020 publishes physical area per crop under `_I` (irrigated) and `_R` (rainfed) at ~10 km.
The irrigated SHARE is a smooth ratio, so it is resampled bilinearly onto the 100 m mask grid and
used to apportion the mask's own per-crop fraction:

    s_irr            = I / (I + R)                       per SPAM cell, 0 where both are 0
    frac_<crop>_irr  = frac_<crop> x s_irr
    frac_<crop>_rain = frac_<crop> x (1 - s_irr)

The mask's own fraction is preserved exactly: irr + rain == frac, pixel by pixel. SPAM decides only
HOW the crop area splits, never HOW MUCH there is - the crop-type mask remains the area authority,
which matters because it is the layer calibrated to sub-national statistics.

CAVEAT ON THE SCALE GAP. SPAM is ~10 km and the mask is 100 m, so the share is uniform across a
SPAM cell: this separates a scheme district from a rainfed one, not a scheme field from the rainfed
field beside it. And SPAM 2020 is a 2020 snapshot - see IRRIGATED_WATER_BALANCE.md G4.

    python crop_type_mask/split_irrigated.py --list
    python crop_type_mask/split_irrigated.py --country Sudan
    python crop_type_mask/split_irrigated.py --exposed      # every country-crop that carries exposure
"""
import argparse, os, sys
import numpy as np, rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
from rasterio.windows import Window

H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(H)
sys.path.insert(0, ROOT); sys.path.insert(0, f"{ROOT}/crop_pipeline/irrigation")
import ctm_mask as CTM
import irrigation_exposure as IRR

SPAM = "/tmp/spam20/geotiff_physical"
CODE = {"maize": "MAIZ", "sorghum": "SORG", "wheat": "WHEA", "millet": "PMIL", "teff": "OCER"}
BLOCK = 2048


def frac_path(country):
    iso = CTM.PROFILES[country.replace(" ", "_")][0]
    # the profile ISO carries a suffix for the SPAM-2020 rebuilds (RW20, BI20, SO20); the file
    # on disk uses the bare two-letter code
    return f"{H}/{country}/outputs/{iso[:2]}_crop_fraction_100m.tif"


def spam_share(crop, dst_profile, dst_transform, dst_shape):
    """SPAM irrigated share I/(I+R), bilinearly resampled onto the mask grid."""
    out = {}
    for tech in ("I", "R"):
        f = f"{SPAM}/icpac_spam2020_V2r2_global_A_{CODE[crop]}_{tech}.tif"
        with rasterio.open(f) as src:
            dst = np.zeros(dst_shape, "float32")
            reproject(source=rasterio.band(src, 1), destination=dst,
                      src_transform=src.transform, src_crs=src.crs,
                      dst_transform=dst_transform, dst_crs=dst_profile["crs"],
                      resampling=Resampling.bilinear)
            dst[~np.isfinite(dst)] = 0; dst[dst < 0] = 0
            out[tech] = dst
    tot = out["I"] + out["R"]
    s = np.zeros_like(tot)
    np.divide(out["I"], tot, out=s, where=tot > 0)
    return np.clip(s, 0, 1)


def split_country(country, crops=None, dry=False):
    key = country.replace(" ", "_")
    f = frac_path(country)
    if not os.path.exists(f):
        return print(f"  {country}: no fraction raster at {f}")
    with rasterio.open(f) as r:
        bands = list(r.descriptions)
        prof = r.profile.copy()
        want = [b for b in bands if b.startswith("frac_")
                and (crops is None or b[5:] in crops) and b[5:] in CODE]
        if not want:
            return print(f"  {country}: no matching crop bands in {bands}")
        print(f"  {country}: {f.split('/')[-1]}  bands {want}")
        if dry:
            return
        # one output file, two bands per crop
        names = [f"{b}_irr" for b in want] + [f"{b}_rain" for b in want]
        prof.update(count=len(names), dtype="uint8", compress="deflate", predictor=2,
                    tiled=True, blockxsize=512, blockysize=512, nodata=0)
        out = f.replace("_crop_fraction_100m.tif", "_crop_fraction_tech_100m.tif")
        shares = {b: spam_share(b[5:], prof, r.transform, (r.height, r.width)) for b in want}
        with rasterio.open(out, "w", **prof) as dst:
            for i, n in enumerate(names, start=1):
                dst.set_band_description(i, n)
            for yoff in range(0, r.height, BLOCK):
                h = min(BLOCK, r.height - yoff)
                w = Window(0, yoff, r.width, h)
                for j, b in enumerate(want):
                    fr = r.read(bands.index(b) + 1, window=w).astype("float32")
                    s = shares[b][yoff:yoff + h, :]
                    irr = np.rint(fr * s).astype("uint8")
                    dst.write(irr, j + 1, window=w)
                    dst.write((fr - irr).clip(0, 255).astype("uint8"), len(want) + j + 1, window=w)
        # report, and prove the split conserves the mask's own area
        with rasterio.open(out) as c:
            for j, b in enumerate(want):
                tot = r.read(bands.index(b) + 1).astype("float64").sum()
                ir = c.read(j + 1).astype("float64").sum()
                ra = c.read(len(want) + j + 1).astype("float64").sum()
                pct = 100 * ir / tot if tot else 0
                err = 100 * abs((ir + ra) - tot) / tot if tot else 0
                print(f"      {b[5:]:8s} irrigated {pct:5.1f}%   conservation error {err:.3f}%"
                      f"   (exposure: {IRR.grade(country, b[5:])})")
        print(f"      wrote {out.split('/')[-1]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--country"); ap.add_argument("--crop")
    ap.add_argument("--exposed", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        for c in sorted(CTM.PROFILES):
            p = frac_path(c)
            print(f"  {c:14s} {'OK  ' if os.path.exists(p) else 'MISS'} {p.split('/')[-1]}")
        return
    if a.exposed:
        todo = {}
        for (co, cr), v in IRR.EXPOSURE.items():
            if v[3] != "negligible":
                todo.setdefault(co, []).append(cr)
        print(f"splitting the {sum(len(v) for v in todo.values())} country-crop pairs that carry "
              f"irrigation exposure\n")
        for co, crops in sorted(todo.items()):
            split_country(co, crops)
        return
    if not a.country:
        return print("give --country, --exposed or --list")
    split_country(a.country, [a.crop] if a.crop else None)


if __name__ == "__main__":
    main()
