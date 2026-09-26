#!/usr/bin/env python3
"""Validate the Ethiopian crop-type masks against EthCT2020 field polygons.

**EthCT2020** (`ICPAC-WORK/Teff-Crop/EthCT2020.shp`) is 2,793 *real* field polygons surveyed in
2020, every one flagged quality `very good` and location `confident`, from three independent
sources (GDCC, FHSD, WRTB). Crop classes usable here: **wheat 2,077, teff 255, maize 96,
millets 21**.

This is the strongest independent evidence available for any crop-type mask in the series. The
regional report names thin field evidence as the binding limitation, and for Ethiopia it fell back
to LSMS-ISA *enumeration areas* — 5 km cells, not fields. These are fields.

**Not to be confused with the other file in that folder.**
`ethiopia_crop_ground_truth_points.csv` holds 6,823 points of which every single row carries
`provenance = SIMULATED_reconstructed_from_published_counts_and_extent`. Its own methodology note
says in terms: *"Do not use them as authoritative in-situ truth for accuracy assessment."* They
were reconstructed from published per-class counts and figure extents, so their locations are
random draws inside a bounding box. Scoring a mask against them would measure nothing. The 82 teff
points in it are excluded here for that reason.

Metric: the separation (AUC) between the crop fraction at surveyed fields of that crop and at
fields of *other* crops. Using other crops as the background is a harder and fairer test than
using unplanted land, because it asks whether the mask distinguishes crops rather than merely
finding cropland.

    EE_PROJECT=ee-manzikye python crop_type_mask/validation_ethct/validate_ethct2020.py
"""
import os, sys
import geopandas as gpd, numpy as np, pandas as pd

H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(H))
sys.path.insert(0, ROOT)
import ee                                                              # noqa: E402
import ctm_mask as CTM                                                 # noqa: E402
from src import utils                                                  # noqa: E402

SHP = "/Users/hildamanzi/ICPAC-WORK/Teff-Crop/EthCT2020.shp"
# EthCT2020 c_class -> the band in the Ethiopian crop-type mask
CLASSES = {"wheat": "wheat", "teff": "teff", "maize": "maize"}
MIN_N = 20


def auc(pos, neg):
    """Mann-Whitney AUC: P(a random positive scores above a random negative)."""
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if len(pos) < 3 or len(neg) < 3:
        return np.nan
    allv = np.concatenate([pos, neg])
    r = pd.Series(allv).rank().values
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def boot_ci(pos, neg, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    vals = [auc(rng.choice(pos, len(pos)), rng.choice(neg, len(neg))) for _ in range(n)]
    vals = [v for v in vals if np.isfinite(v)]
    return (np.percentile(vals, 2.5), np.percentile(vals, 97.5)) if vals else (np.nan, np.nan)


def main():
    utils.gee_init()
    g = gpd.read_file(SHP).to_crs(4326)
    g = g[g.c_class.isin(CLASSES)].copy()
    print(f"EthCT2020: {len(g)} field polygons of the mapped crops, surveyed "
          f"{g.sub_dat.min()} to {g.sub_dat.max()}")
    print(g.c_class.value_counts().to_string(), "\n")

    img = ee.Image(CTM.asset("Ethiopia"))
    bands = [f"frac_{c}" for c in CLASSES.values()] + ["cl_pct"]
    pts = [ee.Feature(ee.Geometry.Point([float(r.geometry.centroid.x),
                                         float(r.geometry.centroid.y)]),
                      {"i": int(i), "c": r.c_class})
           for i, r in g.reset_index(drop=True).iterrows()]
    fc = ee.FeatureCollection(pts)
    vals = {}
    B = 500
    for i0 in range(0, len(pts), B):
        sub = ee.FeatureCollection(pts[i0:i0 + B])
        for f in img.select(bands).reduceRegions(sub, ee.Reducer.first(), scale=100
                                                 ).getInfo()["features"]:
            p = f["properties"]
            vals[p["i"]] = {b: p.get(b) for b in bands} | {"c": p["c"]}
        print(f"  sampled {min(i0+B, len(pts))}/{len(pts)}", flush=True)

    d = pd.DataFrame.from_dict(vals, orient="index")
    for b in bands:
        d[b] = pd.to_numeric(d[b], errors="coerce").fillna(0)
    d.to_csv(f"{H}/ethct2020_samples.csv", index=False)

    rows = []
    for cls, band in CLASSES.items():
        col = f"frac_{band}"
        pos = d.loc[d.c == cls, col].values
        neg = d.loc[d.c != cls, col].values
        if len(pos) < MIN_N:
            rows.append(dict(crop=cls, n_fields=len(pos), status=f"too few fields (<{MIN_N})"))
            continue
        a = auc(pos, neg); lo, hi = boot_ci(pos, neg)
        rows.append(dict(crop=cls, n_fields=len(pos), n_background=len(neg),
                         mean_frac_at_crop=round(float(pos.mean()), 2),
                         mean_frac_elsewhere=round(float(neg.mean()), 2),
                         auc=round(a, 3), ci_lo=round(lo, 3), ci_hi=round(hi, 3),
                         verdict=("separates" if lo > 0.5 else
                                  "NOT distinguishable from chance" if hi > 0.5 else
                                  "separates INVERSELY")))
    out = pd.DataFrame(rows)
    out.to_csv(f"{H}/ethct2020_validation.csv", index=False)
    print("\n" + out.to_string(index=False))
    print("\nAUC 0.5 is chance. The background is fields of OTHER crops, so this asks whether the "
          "mask tells crops apart, not merely whether it finds cropland - a harder test than the "
          "cropland-background AUC quoted in the regional report.")


if __name__ == "__main__":
    main()
