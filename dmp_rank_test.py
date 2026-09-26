#!/usr/bin/env python3
"""Does DMP rank admin units against observed yield better than CPI does, where CPI ranks BACKWARDS?

Eight shipped ceilings are fitted on a CPI that is ANTI-correlated with reported yield (r < 0): the
model sets a plausible level and then orders the units wrongly, which in an early-warning product is
worse than no ordering at all. The repository already logs that dry-matter productivity "out-ranks
CPI in 4/5 tests", and that DMP was rejected as a REPLACEMENT for S_veg inside CPI (no rank gain,
Ethiopia admin-2 n=39). It has never been tested as what that evidence actually suggests: an
independent RANKING COVARIATE beside CPI.

THE TEST IS RANK-ONLY, WHICH REMOVES DMP'S BIGGEST UNCERTAINTY. Spearman rho is invariant to any
monotonic transform, so seasonal dry matter can be compared directly against observed yield without
choosing a harvest index, an above-ground fraction or a grain moisture. Those three are the dominant
uncertainty in DMP yield and none of them can change the answer here.

Method, per product: integrate MODIS-derived DMP over each pixel's OWN crop cycle (planting dekad
from the shipped rich asset, so DMP and CPI see the same season), mask to the same crop-type mask,
reduce to the same admin-2 units, aggregate onto the same HarvestStat units with the same crop-area
weights, then compare rho(obs, DMP) against rho(obs, CPI) with a paired bootstrap.

    python dmp_rank_test.py                 # all eight
    python dmp_rank_test.py --only Sudan_Kharif
"""
import argparse, os, sys
import ee, geopandas as gpd, numpy as np, pandas as pd
from scipy.stats import spearmanr
from shapely import wkt

H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H)
HS = os.path.join(H, "Cropyield-Data", "harveststat")
EQ = "ESRI:54034"
YEAR = 2024

# crop, token, reduce-CSV prefix, rich-asset prefix, HS country/season/years, cycle dekads
JOBS = [
 ("sorghum", "Sudan_Kharif",     "newcS", "sorghumX", "Sudan",   "Main",     range(2015, 2024), 15),
 ("sorghum", "Uganda_2ndrains",  "newcS", "sorghumX", "Uganda",  "Second",   range(2008, 2009),  9),
 ("sorghum", "Rwanda_SeasonB",   "newcS", "sorghumX", "Rwanda",  "Season B", range(2009, 2018),  9),
 ("sorghum", "Kenya_Shortrains", "newcS", "sorghumX", "Kenya",   "Short",    range(2016, 2018),  9),
 ("maize",   "Uganda_1strains",  "newc",  "cpiX",     "Uganda",  "First",    range(2008, 2010), 12),
 ("sorghum", "Burundi_SeasonA",  "newcS", "sorghumX", "Burundi", "Season A", range(2013, 2017),  9),
 ("maize",   "Rwanda_SeasonA",   "newc",  "cpiX",     "Rwanda",  "Season A", range(2010, 2018),  9),
 ("sorghum", "Uganda_1strains",  "newcS", "sorghumX", "Uganda",  "First",    range(2009, 2010), 13),
]


def product_units(prefix, tok):
    f = os.path.join(H, f"{prefix}_{tok}_2024_L2_skill_WKT.csv")
    n = pd.read_csv(f)
    g = gpd.GeoDataFrame(n[["name", "cpi", "crop_area_frac"]],
                         geometry=[wkt.loads(x) for x in n.geometry_wkt], crs="EPSG:4326")
    g = g[g.cpi.notna() & g.crop_area_frac.notna() & (g.crop_area_frac > 0)].copy()
    g["geometry"] = g.geometry.buffer(0)
    g["uid"] = range(len(g))
    return g


def dmp_by_unit(crop, tok, rich_pfx, g, cycle_dk):
    """Seasonal dry matter per admin-2 unit, integrated over each pixel's own cycle."""
    import ctm_mask as CTM
    from src import dmp_yield as DMP
    country = tok.rsplit("_", 1)[0] if tok.count("_") > 1 else tok.split("_")[0]
    for c in ("South_Sudan", "Sudan", "Uganda", "Rwanda", "Burundi", "Kenya", "Ethiopia",
              "Somalia", "Tanzania", "Eritrea"):
        if tok.startswith(c):
            country = c
            break
    asset = f"projects/ee-manzikye/assets/{rich_pfx}_{tok}_2024"
    img = ee.Image(asset)
    planting = img.select("planting_dekad")
    mask = CTM.crop_mask(ee, country, crop)
    fc = ee.FeatureCollection([
        ee.Feature(ee.Geometry(r.geometry.__geo_interface__), {"uid": int(r.uid)})
        for r in g.itertuples()])
    aoi = fc.geometry().bounds()
    coll = DMP.dmp_daily_collection(ee, aoi, YEAR, source="modis")
    pt = DMP.dekad_to_t(ee, planting, YEAR)
    dm = DMP.seasonal_dry_matter(ee, coll, pt, cycle_dk * 10).updateMask(mask)
    out = {}
    for scale in (500, 1000, 2500):
        try:
            res = dm.reduceRegions(fc, ee.Reducer.mean().setOutputs(["dm"]),
                                   scale=scale, tileScale=4).getInfo()["features"]
            out = {f["properties"]["uid"]: f["properties"].get("dm") for f in res}
            if sum(1 for v in out.values() if v is not None) >= 0.5 * len(g):
                return out, scale
        except Exception as e:
            print(f"      {scale} m failed: {str(e)[:70]}")
    return out, None


def boot_delta(o, a, b, n=2000, seed=42):
    """Paired bootstrap on rho(o,b) - rho(o,a)."""
    rng = np.random.default_rng(seed); idx = np.arange(len(o)); d = []
    for _ in range(n):
        s = rng.choice(idx, len(idx), replace=True)
        if len(np.unique(o[s])) < 3:
            continue
        d.append(spearmanr(o[s], b[s]).statistic - spearmanr(o[s], a[s]).statistic)
    d = np.array([x for x in d if np.isfinite(x)])
    return (float(np.mean(d)), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))) \
        if len(d) else (np.nan, np.nan, np.nan)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--only"); a = ap.parse_args()
    ee.Initialize(project=os.environ.get("EE_PROJECT", "ee-manzikye"))
    d = pd.read_csv(os.path.join(HS, "hvstat_africa_data_v1.2.csv"), low_memory=False)
    d.columns = [c.lower() for c in d.columns]
    bnd = gpd.read_file(os.path.join(HS, "hvstat_africa_boundary_v1.2.gpkg"))
    bnd.columns = [c.lower() for c in bnd.columns]; bnd = bnd.set_geometry("geometry")
    PROD = {"sorghum": "Sorghum", "maize": "Maize"}

    rows = []
    for crop, tok, pfx, rich, hs_c, hs_s, yrs, cyc in JOBS:
        if a.only and a.only != tok:
            continue
        label = f"{crop} {tok}"
        print(f"== {label}", flush=True)
        try:
            g = product_units(pfx, tok)
        except FileNotFoundError:
            print("   no reduce CSV"); continue
        y = d[(d["product"] == PROD[crop]) & (d.country == hs_c) & (d.season_name == hs_s)
              & d.harvest_year.isin(yrs) & d["yield"].notna()]
        obs = y.groupby("fnid")["yield"].median(); obs = obs[(obs > 0) & (obs <= 8)]
        if len(obs) < 4:
            print(f"   only {len(obs)} HarvestStat units"); continue
        dm, scale = dmp_by_unit(crop, tok, rich, g, cyc)
        if not dm:
            print("   DMP reduce failed at every scale"); continue
        g["dm"] = g.uid.map(dm)
        g = g[g.dm.notna()]
        print(f"   DMP at {scale} m over {len(g)} units", flush=True)
        u = bnd[bnd.fnid.isin(obs.index)][["fnid", "geometry"]]
        ov = gpd.overlay(g.to_crs(EQ), u.to_crs(EQ), how="intersection", keep_geom_type=True)
        if not len(ov):
            print("   no overlap with HarvestStat units"); continue
        ov["w"] = ov.area * ov.crop_area_frac
        agg = ov.groupby("fnid").apply(
            lambda t: pd.Series({
                "cpi": np.average(t.cpi, weights=t.w) if t.w.sum() > 0 else np.nan,
                "dm": np.average(t.dm, weights=t.w) if t.w.sum() > 0 else np.nan}),
            include_groups=False)
        j = pd.concat([obs.rename("obs"), agg], axis=1).dropna()
        if len(j) < 5:
            print(f"   only {len(j)} matched units"); continue
        o, c, m = j.obs.values, j.cpi.values, j.dm.values
        r_cpi = spearmanr(o, c).statistic; r_dmp = spearmanr(o, m).statistic
        mu, lo, hi = boot_delta(o, c, m)
        rows.append(dict(crop=crop, product=tok, n=len(j), scale_m=scale,
                         rho_cpi=round(r_cpi, 3), rho_dmp=round(r_dmp, 3),
                         d_rho=round(r_dmp - r_cpi, 3),
                         ci_lo=round(lo, 3), ci_hi=round(hi, 3),
                         verdict=("DMP better" if lo > 0 else "CPI better" if hi < 0
                                  else "no difference")))
        print(f"   n={len(j)}  rho CPI {r_cpi:+.3f} -> DMP {r_dmp:+.3f}  "
              f"delta {r_dmp - r_cpi:+.3f} [{lo:+.3f}, {hi:+.3f}]", flush=True)

    if not rows:
        return print("\nno products scored")
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(H, "maize_ctm", "dmp_rank_test.csv"), index=False)
    print("\n=== DMP vs CPI as a ranking covariate, on the anti-correlated products ===")
    print(out.to_string(index=False))
    print(f"\n  DMP ranks better (CI excludes 0): {int((out.verdict == 'DMP better').sum())} of {len(out)}")
    print(f"  CPI ranks better                : {int((out.verdict == 'CPI better').sum())}")
    print(f"  indistinguishable               : {int((out.verdict == 'no difference').sum())}")
    print(f"  median delta rho                : {out.d_rho.median():+.3f}")
    print(f"  DMP rho positive in             : {int((out.rho_dmp > 0).sum())} of {len(out)} "
          f"(CPI positive in {int((out.rho_cpi > 0).sum())})")
    print("\nwritten: maize_ctm/dmp_rank_test.csv")


if __name__ == "__main__":
    main()
