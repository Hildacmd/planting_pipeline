#!/usr/bin/env python3
"""Re-fit the yield ceiling over RAINFED area only, and test whether the ranking recovers.

The prediction, from IRRIGATED_WATER_BALANCE.md G3: where CPI is depressed by irrigation the model
cannot see, but reported yield includes the irrigated production, the least-squares fit compensates
by inflating Ym and leaves the SPATIAL PATTERN inverted. Sudan sorghum Kharif is the visible
symptom - a ceiling shipped with **r = -0.33**, a negative correlation presented as a calibration.

If that diagnosis is right, weighting the fit by RAINFED crop area instead of total crop area should
move r up, because the units whose CPI is an irrigation artefact stop driving the ceiling. If r does
not move, the diagnosis was wrong and the problem is elsewhere.

Rainfed area per admin unit comes from the technology split
(`crop_type_mask/split_irrigated.py` -> `<ISO>_crop_fraction_tech_100m.tif`), zonal-summed over the
product's own admin-2 polygons. Everything else - targets, units, 70/30 x 200, seed - is held
identical to the shipped fit, so the only thing that changes is the weight.

    python crop_pipeline/irrigation/refit_rainfed.py
"""
import os, random, sys
import geopandas as gpd, numpy as np, pandas as pd, rasterio
from rasterio.mask import mask as rmask
from scipy.stats import spearmanr
from shapely import wkt

H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(H))
sys.path.insert(0, ROOT)
import ctm_mask as CTM
HS = os.path.join(ROOT, "Cropyield-Data", "harveststat")
EQ = "ESRI:54034"

# crop, product token, reduce prefix, HarvestStat country/season/years, shipped r
JOBS = [
 ("sorghum", "Sudan_Kharif",    "newcS", "Sudan",    "Main",     range(2015, 2024), -0.33),
 ("millet",  "Sudan_Kharif",    "newcM", "Sudan",    "Main",     range(2015, 2024), +0.24),
 ("sorghum", "Somalia_Gu",      "newcS", "Somalia",  "Gu",       range(2015, 2025), +0.26),
 ("sorghum", "Somalia_Deyr",    "newcS", "Somalia",  "Deyr",     range(2015, 2025), +0.32),
 ("maize",   "Somalia_Gu",      "newc",  "Somalia",  "Gu",       range(2015, 2025), +0.34),
 ("maize",   "Ethiopia_Meher",  None,    "Ethiopia", "Meher",    range(2012, 2022), +0.64),
]
MAIZE_STEM = {"Ethiopia_Meher": "planting_Ethiopia_maize_Meher_2024_250m"}
PROD = {"sorghum": "Sorghum", "maize": "Maize", "millet": "Millet"}


def tech_raster(country):
    iso = CTM.PROFILES[country.replace(" ", "_")][0][:2]
    return f"{ROOT}/crop_type_mask/{country}/outputs/{iso}_crop_fraction_tech_100m.tif"


def units(crop, tok, pfx):
    stem = MAIZE_STEM.get(tok) or f"{pfx}_{tok}_2024"
    d = pd.read_csv(f"{ROOT}/{stem}_L2_skill_WKT.csv")
    g = gpd.GeoDataFrame(d[["cpi", "crop_area_frac"]],
                         geometry=[wkt.loads(x) for x in d.geometry_wkt], crs="EPSG:4326")
    g = g[g.cpi.notna() & g.crop_area_frac.notna() & (g.crop_area_frac > 0)].copy()
    g["geometry"] = g.geometry.buffer(0)
    return g


def rainfed_share(country, crop, g):
    """Per-unit rainfed share of this crop's mapped area, from the technology split."""
    f = tech_raster(country)
    if not os.path.exists(f):
        return None
    with rasterio.open(f) as r:
        names = list(r.descriptions)
        bi, br = names.index(f"frac_{crop}_irr") + 1, names.index(f"frac_{crop}_rain") + 1
        out = []
        for geom in g.geometry:
            try:
                a, _ = rmask(r, [geom.__geo_interface__], crop=True, filled=True, nodata=0,
                             indexes=[bi, br])
            except ValueError:
                out.append(np.nan); continue
            i, ra = float(a[0].sum()), float(a[1].sum())
            out.append(ra / (i + ra) if (i + ra) > 0 else np.nan)
    return pd.Series(out, index=g.index)


def fit(j):
    o, c = j.obs.values, j.c.values
    ym = float((o * c).sum() / (c * c).sum())
    rnd = random.Random(42); idx = list(range(len(j))); mae = []
    for _ in range(200):
        rnd.shuffle(idx); k = max(1, int(round(0.7 * len(idx)))); tr, te = idx[:k], idx[k:]
        if not te:
            continue
        ymt = (o[tr] * c[tr]).sum() / (c[tr] ** 2).sum()
        mae.append(np.abs(o[te] - ymt * c[te]).mean())
    return (ym, float(np.mean(mae)), float(np.corrcoef(o, ym * c)[0, 1]),
            float(spearmanr(o, c).statistic))


def main():
    d = pd.read_csv(os.path.join(HS, "hvstat_africa_data_v1.2.csv"), low_memory=False)
    d.columns = [x.lower() for x in d.columns]
    bnd = gpd.read_file(os.path.join(HS, "hvstat_africa_boundary_v1.2.gpkg"))
    bnd.columns = [x.lower() for x in bnd.columns]; bnd = bnd.set_geometry("geometry")

    rows = []
    for crop, tok, pfx, hs_c, hs_s, yrs, shipped_r in JOBS:
        country = tok.rsplit("_", 1)[0]
        print(f"== {crop} {tok}", flush=True)
        try:
            g = units(crop, tok, pfx)
        except FileNotFoundError:
            print("   no reduce CSV"); continue
        rs = rainfed_share(country, crop, g)
        if rs is None:
            print("   no technology split for this country"); continue
        g["rain_share"] = rs.fillna(1.0)
        y = d[(d["product"] == PROD[crop]) & (d.country == hs_c) & (d.season_name == hs_s)
              & d.harvest_year.isin(yrs) & d["yield"].notna()]
        obs = y.groupby("fnid")["yield"].median(); obs = obs[(obs > 0) & (obs <= 8)]
        u = bnd[bnd.fnid.isin(obs.index)][["fnid", "geometry"]]
        ov = gpd.overlay(g.to_crs(EQ), u.to_crs(EQ), how="intersection", keep_geom_type=True)
        if not len(ov):
            print("   no overlap"); continue
        res = {}
        for lab, w in (("total", ov.area * ov.crop_area_frac),
                       ("rainfed", ov.area * ov.crop_area_frac * ov.rain_share)):
            ovw = ov.assign(_w=w)
            cpi_u = (ovw[ovw._w > 0].groupby("fnid")
                     .apply(lambda t: np.average(t.cpi, weights=t._w), include_groups=False)
                     .dropna())
            j = pd.concat([obs.rename("obs"), (cpi_u / 100).rename("c")], axis=1).dropna()
            if len(j) < 4:
                res[lab] = None; continue
            res[lab] = fit(j) + (len(j),)
        if not (res.get("total") and res.get("rainfed")):
            print("   too few matched units"); continue
        (ym0, mae0, r0, rho0, n0) = res["total"]
        (ym1, mae1, r1, rho1, n1) = res["rainfed"]
        drop = 1 - float(ov.rain_share.mean())
        rows.append(dict(crop=crop, product=tok, n=n1, irr_frac_of_weight=round(drop, 3),
                         ym_total=round(ym0, 2), ym_rainfed=round(ym1, 2),
                         r_total=round(r0, 3), r_rainfed=round(r1, 3), d_r=round(r1 - r0, 3),
                         rho_total=round(rho0, 3), rho_rainfed=round(rho1, 3),
                         mae_total=round(mae0, 3), mae_rainfed=round(mae1, 3),
                         shipped_r=shipped_r))
        print(f"   n={n1}  r {r0:+.3f} -> {r1:+.3f}  ({r1 - r0:+.3f})   "
              f"Ym {ym0:.2f} -> {ym1:.2f}   MAE {mae0:.3f} -> {mae1:.3f}", flush=True)

    if not rows:
        return print("\nnothing fitted")
    out = pd.DataFrame(rows)
    out.to_csv(f"{H}/refit_rainfed.csv", index=False)
    print("\n=== Ym re-fit over rainfed area only ===")
    print(out[["crop", "product", "n", "ym_total", "ym_rainfed", "r_total", "r_rainfed", "d_r",
               "mae_total", "mae_rainfed"]].to_string(index=False))
    print(f"\n  r improved in {int((out.d_r > 0).sum())} of {len(out)}   "
          f"median change {out.d_r.median():+.3f}")
    flip = out[(out.r_total < 0) & (out.r_rainfed > 0)]
    if len(flip):
        print("  SIGN FLIPPED (ranking recovered) for: " + ", ".join(flip["product"]))
    print(f"\nwritten: {H}/refit_rainfed.csv")


if __name__ == "__main__":
    main()
