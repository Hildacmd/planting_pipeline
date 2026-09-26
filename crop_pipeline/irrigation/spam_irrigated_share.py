#!/usr/bin/env python3
"""How much of each crop in each country is IRRIGATED, from SPAM 2020.

The pipeline's water balance is rainfed by construction: it compares crop demand against CHIRPS
rainfall and has no irrigation term. Wherever a crop is actually irrigated, WRSI and S_water
therefore describe the **irrigation requirement** rather than crop stress, and CPI and yield built
on them are wrong in a direction that always reads as *worse* than reality.

This quantifies the exposure. SPAM 2020 publishes physical area per crop under `_I` (irrigated)
and `_A` (all technologies), so the irrigated share is simply I / A, summed inside each country.

    python crop_pipeline/irrigation/spam_irrigated_share.py
"""
import glob, os, sys
import geopandas as gpd, numpy as np, pandas as pd, rasterio
from rasterio.mask import mask as rmask

H = os.path.dirname(os.path.abspath(__file__))
SPAM = "/tmp/spam20/geotiff_physical"
GADM = "/Users/hildamanzi/ICPAC-WORK/ADMIN-boundaries"
ISO = {"Ethiopia": "ETH", "Kenya": "KEN", "Uganda": "UGA", "Tanzania": "TZA", "Rwanda": "RWA",
       "Burundi": "BDI", "Somalia": "SOM", "Sudan": "SDN", "South_Sudan": "SSD",
       "Eritrea": "ERI", "Djibouti": "DJI"}
# pipeline crop -> SPAM code. Teff has no SPAM class; the crop-type mask carries it on
# "other cereals", so the same proxy is used here and the result is flagged.
CROPS = {"maize": "MAIZ", "sorghum": "SORG", "wheat": "WHEA", "millet": "PMIL",
         "teff (via other cereals)": "OCER"}


def country_sum(path, geom):
    with rasterio.open(path) as r:
        try:
            a, _ = rmask(r, geom, crop=True, filled=True, nodata=0)
        except ValueError:
            return 0.0
        a = a.astype("float64")
        a[~np.isfinite(a)] = 0
        a[a < 0] = 0
        return float(a.sum())


def main():
    rows = []
    for country, iso in ISO.items():
        gp = f"{GADM}/gadm41_{iso}.gpkg"
        if not os.path.exists(gp):
            continue
        g = gpd.read_file(gp, layer="ADM_ADM_0").to_crs(4326)
        geom = list(g.geometry)
        for crop, code in CROPS.items():
            fi = f"{SPAM}/icpac_spam2020_V2r2_global_A_{code}_I.tif"
            fa = f"{SPAM}/icpac_spam2020_V2r2_global_A_{code}_A.tif"
            if not (os.path.exists(fi) and os.path.exists(fa)):
                continue
            ai, aa = country_sum(fi, geom), country_sum(fa, geom)
            if aa <= 0:
                continue
            rows.append(dict(country=country, crop=crop, spam_code=code,
                             area_all_ha=round(aa), area_irrigated_ha=round(ai),
                             irrigated_pct=round(100 * ai / aa, 1)))
        print(f"  {country} done", flush=True)

    d = pd.DataFrame(rows).sort_values(["crop", "irrigated_pct"], ascending=[True, False])
    d.to_csv(f"{H}/spam2020_irrigated_share.csv", index=False)
    print("\n=== irrigated share of physical area, SPAM 2020 ===")
    piv = d.pivot(index="country", columns="crop", values="irrigated_pct").fillna(0)
    print(piv.to_string())
    print("\n=== where it matters most: crop-country combinations above 10 % irrigated ===")
    big = d[d.irrigated_pct >= 10].sort_values("irrigated_pct", ascending=False)
    print(big[["country", "crop", "area_all_ha", "area_irrigated_ha",
               "irrigated_pct"]].to_string(index=False))
    print(f"\nwritten: {H}/spam2020_irrigated_share.csv")


if __name__ == "__main__":
    main()
