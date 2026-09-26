#!/usr/bin/env python3
"""Add DMP as a ranking covariate to the products where CPI ranks admin units BACKWARDS.

Eight shipped ceilings are fitted on a CPI anti-correlated with reported yield: the model sets a
plausible level and then orders the units wrongly. `dmp_rank_test.py` showed dry-matter productivity
beats CPI on 3 of those 8 (paired bootstrap CI excluding zero), loses none, and is positive in 6 of
8 where CPI is positive in 0 - while adding NOTHING on the five products where CPI already ranks.

This writes DMP onto those products so it can be used, and - before recommending anything - tests
whether a BLEND ranks better than either alone. Three candidates, scored identically:

    CPI     the shipped index
    DMP     seasonal dry matter over the crop's own cycle
    BLEND   mean of the two percentile ranks, equal weight

The blend is not assumed to help. If it does not beat DMP alone it is not recommended, and the
recommendation is recorded per product rather than applied blanket - the whole point of the control
set was that DMP is a rescue for specific failures, not a general improvement.

    python dmp_covariate.py --score          # decide, write nothing
    python dmp_covariate.py --write          # merge a `dmp` column into those products' CSVs
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

# the 8 products where the shipped ceiling is anti-correlated with reported yield
JOBS = [
 ("sorghum", "Sudan_Kharif",     "newcS", "sorghumX", "Sudan",       "Main",     range(2015, 2024), 15),
 ("sorghum", "Uganda_2ndrains",  "newcS", "sorghumX", "Uganda",      "Second",   range(2008, 2009),  9),
 ("sorghum", "Rwanda_SeasonB",   "newcS", "sorghumX", "Rwanda",      "Season B", range(2009, 2018),  9),
 ("sorghum", "Kenya_Shortrains", "newcS", "sorghumX", "Kenya",       "Short",    range(2016, 2018),  9),
 ("maize",   "Uganda_1strains",  "newc",  "cpiX",     "Uganda",      "First",    range(2008, 2010), 12),
 ("sorghum", "Burundi_SeasonA",  "newcS", "sorghumX", "Burundi",     "Season A", range(2013, 2017),  9),
 ("maize",   "Rwanda_SeasonA",   "newc",  "cpiX",     "Rwanda",      "Season A", range(2010, 2018),  9),
 ("sorghum", "Uganda_1strains",  "newcS", "sorghumX", "Uganda",      "First",    range(2009, 2010), 13),
]
PROD = {"sorghum": "Sorghum", "maize": "Maize"}
COUNTRIES = ["South_Sudan", "Ethiopia", "Tanzania", "Somalia", "Burundi", "Eritrea", "Rwanda",
             "Uganda", "Sudan", "Kenya"]


def country_of(tok):
    for c in COUNTRIES:
        if tok.startswith(c):
            return c
    return tok.split("_")[0]


def dmp_for(crop, tok, rich, g, cycle_dk):
    """Seasonal dry matter per polygon, integrated over each pixel's OWN cycle."""
    import ctm_mask as CTM
    from src import dmp_yield as DMP
    country = country_of(tok)
    img = ee.Image(f"projects/ee-manzikye/assets/{rich}_{tok}_2024")
    mask = CTM.crop_mask(ee, country, crop)
    fc = ee.FeatureCollection([
        ee.Feature(ee.Geometry(r.geometry.__geo_interface__), {"uid": int(r.uid)})
        for r in g.itertuples()])
    coll = DMP.dmp_daily_collection(ee, fc.geometry().bounds(), YEAR, source="modis")
    pt = DMP.dekad_to_t(ee, img.select("planting_dekad"), YEAR)
    dm = DMP.seasonal_dry_matter(ee, coll, pt, cycle_dk * 10).updateMask(mask)
    for scale in (500, 1000, 2500):
        try:
            res = dm.reduceRegions(fc, ee.Reducer.mean().setOutputs(["dm"]),
                                   scale=scale, tileScale=4).getInfo()["features"]
            out = {f["properties"]["uid"]: f["properties"].get("dm") for f in res}
            if sum(1 for v in out.values() if v is not None) >= 0.5 * len(g):
                return out, scale
        except Exception as e:
            print(f"      {scale} m: {str(e)[:60]}")
    return {}, None


def load(stem, lvl):
    f = os.path.join(H, f"{stem}_L{lvl}_skill_WKT.csv")
    if not os.path.exists(f):
        return None, None
    d = pd.read_csv(f)
    g = gpd.GeoDataFrame(d.copy(), geometry=[wkt.loads(x) for x in d.geometry_wkt], crs="EPSG:4326")
    g = g[~g.geometry.is_empty].copy()
    g["geometry"] = g.geometry.buffer(0)
    g["uid"] = range(len(g))
    return d, g


def pct_rank(x):
    s = pd.Series(x, dtype="float64")
    return s.rank(pct=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--score", action="store_true")
    a = ap.parse_args()
    ee.Initialize(project=os.environ.get("EE_PROJECT", "ee-manzikye"))
    d_hs = pd.read_csv(os.path.join(HS, "hvstat_africa_data_v1.2.csv"), low_memory=False)
    d_hs.columns = [c.lower() for c in d_hs.columns]
    bnd = gpd.read_file(os.path.join(HS, "hvstat_africa_boundary_v1.2.gpkg"))
    bnd.columns = [c.lower() for c in bnd.columns]; bnd = bnd.set_geometry("geometry")

    rows = []
    for crop, tok, pfx, rich, hs_c, hs_s, yrs, cyc in JOBS:
        stem = f"{pfx}_{tok}_2024"
        print(f"== {crop} {tok}", flush=True)
        for lvl in (1, 2):
            d, g = load(stem, lvl)
            if d is None:
                continue
            dm, scale = dmp_for(crop, tok, rich, g, cyc)
            if not dm:
                print(f"   L{lvl}: DMP failed at every scale"); continue
            d["dmp"] = pd.Series(g.uid.map(dm).values, index=g.index).reindex(d.index)
            n = int(d.dmp.notna().sum())
            print(f"   L{lvl}: dmp {n}/{len(d)} at {scale} m", flush=True)
            if a.write:
                d.to_csv(os.path.join(H, f"{stem}_L{lvl}_skill_WKT.csv"), index=False)
            if lvl == 2:
                g2 = g.assign(dmp=g.uid.map(dm))
                y = d_hs[(d_hs["product"] == PROD[crop]) & (d_hs.country == hs_c)
                         & (d_hs.season_name == hs_s) & d_hs.harvest_year.isin(yrs)
                         & d_hs["yield"].notna()]
                obs = y.groupby("fnid")["yield"].median(); obs = obs[(obs > 0) & (obs <= 8)]
                u = bnd[bnd.fnid.isin(obs.index)][["fnid", "geometry"]]
                gg = g2[g2.cpi.notna() & g2.dmp.notna() & g2.crop_area_frac.notna()
                        & (g2.crop_area_frac > 0)]
                if not len(gg):
                    continue
                ov = gpd.overlay(gg.to_crs(EQ), u.to_crs(EQ), how="intersection",
                                 keep_geom_type=True)
                if not len(ov):
                    continue
                ov["w"] = ov.area * ov.crop_area_frac
                agg = ov[ov.w > 0].groupby("fnid").apply(
                    lambda t: pd.Series({"cpi": np.average(t.cpi, weights=t.w),
                                         "dmp": np.average(t.dmp, weights=t.w)}),
                    include_groups=False)
                j = pd.concat([obs.rename("obs"), agg], axis=1).dropna()
                if len(j) < 5:
                    continue
                j["blend"] = (pct_rank(j.cpi) + pct_rank(j.dmp)) / 2
                r = {k: float(spearmanr(j.obs, j[k]).statistic) for k in ("cpi", "dmp", "blend")}
                best = max(r, key=r.get)
                rows.append(dict(crop=crop, product=tok, n=len(j),
                                 rho_cpi=round(r["cpi"], 3), rho_dmp=round(r["dmp"], 3),
                                 rho_blend=round(r["blend"], 3), best=best,
                                 gain_over_cpi=round(r[best] - r["cpi"], 3)))
                print(f"        rho  CPI {r['cpi']:+.3f}  DMP {r['dmp']:+.3f}  "
                      f"BLEND {r['blend']:+.3f}  -> {best}", flush=True)

    if not rows:
        return print("\nnothing scored")
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(H, "maize_ctm", "dmp_covariate_choice.csv"), index=False)
    print("\n=== which index ranks these products best? ===")
    print(out.to_string(index=False))
    print(f"\n  best index: " + ", ".join(f"{k} {v}" for k, v in out.best.value_counts().items()))
    print(f"  median gain over CPI: {out.gain_over_cpi.median():+.3f}")
    print(f"  CPI still positive in {int((out.rho_cpi > 0).sum())} of {len(out)}; "
          f"chosen index positive in {int((out[['rho_cpi','rho_dmp','rho_blend']].max(axis=1) > 0).sum())}")
    print(f"\nwritten: maize_ctm/dmp_covariate_choice.csv")


if __name__ == "__main__":
    main()
