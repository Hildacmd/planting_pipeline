#!/usr/bin/env python3
"""Irrigated share of each crop at ADMIN-1, for every (country, crop) pair that has a product.

The country share says how exposed a product is; this says WHERE. Driven by products.inventory(),
so the crop is the product's own crop -- never another crop's raster.
"""
import os, sys
import geopandas as gpd, numpy as np, pandas as pd, rasterio
from rasterio.mask import mask as rmask

H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H)
from products import inventory

SPAM = "/tmp/spam20/geotiff_physical"
GADM = "/Users/hildamanzi/ICPAC-WORK/ADMIN-boundaries"
ISO = {"Ethiopia": "ETH", "Kenya": "KEN", "Uganda": "UGA", "Tanzania": "TZA", "Rwanda": "RWA",
       "Burundi": "BDI", "Somalia": "SOM", "Sudan": "SDN", "South_Sudan": "SSD",
       "Eritrea": "ERI", "Djibouti": "DJI"}
SPAM_CODE = {"maize": "MAIZ", "sorghum": "SORG", "wheat": "WHEA", "millet": "PMIL", "teff": "OCER"}


def zsum(path, geom):
    with rasterio.open(path) as r:
        try:
            a, _ = rmask(r, [geom], crop=True, filled=True, nodata=0)
        except ValueError:
            return 0.0
        a = a.astype("float64"); a[~np.isfinite(a)] = 0; a[a < 0] = 0
        return float(a.sum())


pairs = sorted({(r["country"], r["crop"]) for r in inventory()})
print(f"{len(pairs)} (country, crop) pairs with a product")
rows = []
for country, crop in pairs:
    iso, code = ISO.get(country), SPAM_CODE[crop]
    if iso is None:
        print(f"  !! no ISO for {country}"); continue
    g = gpd.read_file(f"{GADM}/gadm41_{iso}.gpkg", layer="ADM_ADM_1").to_crs(4326)
    fi = f"{SPAM}/icpac_spam2020_V2r2_global_A_{code}_I.tif"
    fa = f"{SPAM}/icpac_spam2020_V2r2_global_A_{code}_A.tif"
    for _, r in g.iterrows():
        ai, aa = zsum(fi, r.geometry), zsum(fa, r.geometry)
        if aa < 50:
            continue
        rows.append(dict(country=country, crop=crop, spam_code=code, admin1=r["NAME_1"],
                         area_all_ha=round(aa), area_irr_ha=round(ai),
                         irrigated_pct=round(100 * ai / aa, 1)))
    print(f"  {country:12s} {crop:8s} done", flush=True)

d = pd.DataFrame(rows)
d.to_csv(f"{H}/spam2020_irrigated_admin1.csv", index=False)
print("\n=== admin-1 units above 20 % irrigated, for products that exist ===")
big = d[d.irrigated_pct >= 20].sort_values("irrigated_pct", ascending=False)
print(big[["country", "crop", "admin1", "area_all_ha", "area_irr_ha",
           "irrigated_pct"]].to_string(index=False) if len(big) else "  none")
print(f"\nwritten: {H}/spam2020_irrigated_admin1.csv")
