#!/usr/bin/env python3
"""Irrigated share of each crop at ADMIN-1, for the countries where it is material.

The country-level share says how exposed a product is; this says WHERE. If the admin units the
pipeline reports as the worst-performing are the same units SPAM says are irrigated, the low CPI is
an artifact of the rainfed balance, not a crop failure.
"""
import os
import geopandas as gpd, numpy as np, pandas as pd, rasterio
from rasterio.mask import mask as rmask

H = os.path.dirname(os.path.abspath(__file__))
SPAM = "/tmp/spam20/geotiff_physical"
GADM = "/Users/hildamanzi/ICPAC-WORK/ADMIN-boundaries"
TARGETS = [("Sudan", "SDN", "wheat", "WHEA"), ("Sudan", "SDN", "maize", "MAIZ"),
           ("Sudan", "SDN", "sorghum", "SORG"), ("Somalia", "SOM", "maize", "MAIZ"),
           ("Somalia", "SOM", "sorghum", "SORG"), ("Ethiopia", "ETH", "maize", "MAIZ"),
           ("South_Sudan", "SSD", "sorghum", "SORG")]


def zsum(path, geom):
    with rasterio.open(path) as r:
        try:
            a, _ = rmask(r, [geom], crop=True, filled=True, nodata=0)
        except ValueError:
            return 0.0
        a = a.astype("float64"); a[~np.isfinite(a)] = 0; a[a < 0] = 0
        return float(a.sum())


rows = []
for country, iso, crop, code in TARGETS:
    g = gpd.read_file(f"{GADM}/gadm41_{iso}.gpkg", layer="ADM_ADM_1").to_crs(4326)
    fi = f"{SPAM}/icpac_spam2020_V2r2_global_A_{code}_I.tif"
    fa = f"{SPAM}/icpac_spam2020_V2r2_global_A_{code}_A.tif"
    for _, r in g.iterrows():
        ai, aa = zsum(fi, r.geometry), zsum(fa, r.geometry)
        if aa < 50:                     # ignore units with negligible area
            continue
        rows.append(dict(country=country, crop=crop, admin1=r["NAME_1"],
                         area_all_ha=round(aa), area_irr_ha=round(ai),
                         irrigated_pct=round(100 * ai / aa, 1)))
    print(f"  {country} {crop} done", flush=True)

d = pd.DataFrame(rows)
d.to_csv(f"{H}/spam2020_irrigated_admin1.csv", index=False)
for (c, cr), g in d.groupby(["country", "crop"]):
    g = g.sort_values("irrigated_pct", ascending=False)
    if g.irrigated_pct.max() < 5:
        print(f"\n=== {c} {cr}: no admin-1 unit above 5 % irrigated (max "
              f"{g.irrigated_pct.max():.1f} % in {g.iloc[0].admin1}) ===")
        continue
    print(f"\n=== {c} {cr} — irrigated share by admin-1 ===")
    print(g.head(10)[["admin1", "area_all_ha", "area_irr_ha", "irrigated_pct"]].to_string(index=False))
print(f"\nwritten: {H}/spam2020_irrigated_admin1.csv")
