#!/usr/bin/env python3
"""Can DMP carry a LEVEL? Test it on every representative admin-scale frame available.

The Kenya assessment left the level question open on three frames, one of them n = 6, after the
targeted ASAL drought crop-cuts were excluded as inadmissible (a sample selected toward poorly
performing areas cannot test level skill - any biomass product over-predicts against a harvest that
did not happen). Three near-unbiased frames are not enough to promote a biomass product to a
reported yield, so this widens the evidence base to every (crop, country, season) that has an
admin-scale HarvestStat target.

Per frame it reports the two diagnostics that matter for level, alongside rank skill:

    implied HI   the harvest index back-solved from the observations. Inside the agronomic
                 0.30-0.55 (Hay 1995) means the biomass and the mask are telling the truth;
                 far outside means they are not, and no HI choice rescues it.
    over         DMP-derived yield / observed, at the assumed HI of 0.45. 1.0 is unbiased.

    grain (kg/ha) = seasonal_DM x F_ABOVEGROUND x HI / (1 - moisture)

Every frame here is admin-scale statistics, so all are representative by construction - there are no
targeted campaign samples in HarvestStat.

    python dmp_levels.py
"""
import os, sys
import ee, geopandas as gpd, numpy as np, pandas as pd
from scipy.stats import spearmanr
from shapely import wkt

H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H)
HS = os.path.join(H, "Cropyield-Data", "harveststat")
EQ = "ESRI:54034"
YEAR = 2024

# crop, product token, reduce prefix, rich-asset prefix, HS country, HS season, years, cycle dekads
JOBS = [
 # ---- maize -------------------------------------------------------------------------------
 ("maize", "Kenya_Longrains",  "planting_Kenya_maize_Longrains_2024", "cpiCTMX", "Kenya", "Long", range(2015, 2025), 12),
 ("maize", "Ethiopia_Meher",   "planting_Ethiopia_maize_Meher_2024_250m", "cpiCTMX", "Ethiopia", "Meher", range(2012, 2022), 12),
 ("maize", "Rwanda_SeasonA",   "newc_Rwanda_SeasonA_2024",  "cpiX", "Rwanda",  "Season A", range(2010, 2018),  9),
 ("maize", "Burundi_SeasonA",  "newc_Burundi_SeasonA_2024", "cpiX", "Burundi", "Season A", range(2012, 2017),  9),
 ("maize", "Somalia_Gu",       "newc_Somalia_Gu_2024",      "cpiX", "Somalia", "Gu",       range(2015, 2025),  9),
 ("maize", "Uganda_1strains",  "newc_Uganda_1strains_2024", "cpiX", "Uganda",  "First",    range(2008, 2010), 12),
 # ---- sorghum -----------------------------------------------------------------------------
 ("sorghum", "Ethiopia_Meher", "newcS_Ethiopia_Meher_2024", "sorghumX", "Ethiopia", "Meher", range(2012, 2022), 13),
 ("sorghum", "Kenya_Longrains","newcS_Kenya_Longrains_2024","sorghumX", "Kenya",   "Long",  range(2015, 2017), 12),
 ("sorghum", "Somalia_Gu",     "newcS_Somalia_Gu_2024",     "sorghumX", "Somalia", "Gu",    range(2015, 2025),  9),
 ("sorghum", "Somalia_Deyr",   "newcS_Somalia_Deyr_2024",   "sorghumX", "Somalia", "Deyr",  range(2015, 2025),  9),
 ("sorghum", "Sudan_Kharif",   "newcS_Sudan_Kharif_2024",   "sorghumX", "Sudan",   "Main",  range(2015, 2024), 15),
 ("sorghum", "Rwanda_SeasonA", "newcS_Rwanda_SeasonA_2024", "sorghumX", "Rwanda",  "Season A", range(2010, 2018), 9),
 ("sorghum", "Rwanda_SeasonB", "newcS_Rwanda_SeasonB_2024", "sorghumX", "Rwanda",  "Season B", range(2009, 2018), 9),
 ("sorghum", "Burundi_SeasonB","newcS_Burundi_SeasonB_2024","sorghumX", "Burundi", "Season B", range(2012, 2015), 9),
 # ---- wheat / teff / millet ---------------------------------------------------------------
 ("wheat",  "Ethiopia_Meher",  "newcW_Ethiopia_Meher_2024", "wheatX",  "Ethiopia", "Meher",  range(2012, 2022), 12),
 ("wheat",  "Tanzania_Msimu",  "newcW_Tanzania_Msimu_2024", "wheatX",  "Tanzania", "Msimu",  range(2010, 2021), 12),
 ("teff",   "Ethiopia_Meher",  "newcT_Ethiopia_Meher_2024", "teffX",   "Ethiopia", "Meher",  range(2012, 2022),  9),
 ("millet", "Sudan_Kharif",    "newcM_Sudan_Kharif_2024",   "milletX", "Sudan",    "Main",   range(2015, 2024), 15),
 ("millet", "Eritrea_Kremti",  "newcM_Eritrea_Kremti_2024", "milletX", "Eritrea",  "Kremti", range(2010, 2021), 14),
]
PRODNAME = {"maize": "Maize", "sorghum": "Sorghum", "wheat": "Wheat", "teff": "Teff",
            "millet": "Millet"}
COUNTRIES = ["South_Sudan", "Ethiopia", "Tanzania", "Somalia", "Burundi", "Eritrea", "Rwanda",
             "Uganda", "Sudan", "Kenya"]


def country_of(tok):
    for c in COUNTRIES:
        if tok.startswith(c):
            return c
    return tok.split("_")[0]


def main():
    from src import dmp_yield as DMP
    import ctm_mask as CTM
    ee.Initialize(project=os.environ.get("EE_PROJECT", "ee-manzikye"))
    d_hs = pd.read_csv(os.path.join(HS, "hvstat_africa_data_v1.2.csv"), low_memory=False)
    d_hs.columns = [c.lower() for c in d_hs.columns]
    bnd = gpd.read_file(os.path.join(HS, "hvstat_africa_boundary_v1.2.gpkg"))
    bnd.columns = [c.lower() for c in bnd.columns]; bnd = bnd.set_geometry("geometry")

    rows = []
    for crop, tok, stem, rich, hs_c, hs_s, yrs, cyc in JOBS:
        tag = f"{crop} {tok}"
        f = os.path.join(H, f"{stem}_L2_skill_WKT.csv")
        if not os.path.exists(f):
            print(f"  {tag}: no L2 CSV"); continue
        d = pd.read_csv(f)
        g = gpd.GeoDataFrame(d.copy(), geometry=[wkt.loads(x) for x in d.geometry_wkt],
                             crs="EPSG:4326")
        g = g[~g.geometry.is_empty & g.crop_area_frac.notna() & (g.crop_area_frac > 0)].copy()
        g["geometry"] = g.geometry.buffer(0); g["uid"] = range(len(g))
        country = country_of(tok)
        try:
            asset = f"projects/ee-manzikye/assets/{rich}_{tok}_2024"
            ee.data.getAsset(asset)
        except Exception:
            print(f"  {tag}: no rich asset {rich}_{tok}_2024"); continue
        fc = ee.FeatureCollection([
            ee.Feature(ee.Geometry(r.geometry.__geo_interface__), {"uid": int(r.uid)})
            for r in g.itertuples()])
        try:
            mask = CTM.crop_mask(ee, country, crop)
            coll = DMP.dmp_daily_collection(ee, fc.geometry().bounds(), YEAR, source="modis")
            pt = DMP.dekad_to_t(ee, ee.Image(asset).select("planting_dekad"), YEAR)
            dm = DMP.seasonal_dry_matter(ee, coll, pt, cyc * 10).updateMask(mask)
            got = {}
            for sc in (500, 1000, 2500):
                res = dm.reduceRegions(fc, ee.Reducer.mean().setOutputs(["dm"]), scale=sc,
                                       tileScale=4).getInfo()["features"]
                got = {x["properties"]["uid"]: x["properties"].get("dm") for x in res}
                if sum(1 for v in got.values() if v is not None) >= 0.5 * len(g):
                    break
        except Exception as e:
            print(f"  {tag}: EE failed - {str(e)[:70]}"); continue
        g["dm"] = g.uid.map(got)
        g = g[g.dm.notna() & (g.dm > 0)]
        if not len(g):
            print(f"  {tag}: no DMP"); continue

        y = d_hs[(d_hs["product"] == PRODNAME[crop]) & (d_hs.country == hs_c)
                 & (d_hs.season_name == hs_s) & d_hs.harvest_year.isin(yrs) & d_hs["yield"].notna()]
        obs = y.groupby("fnid")["yield"].median(); obs = obs[(obs > 0) & (obs <= 8)]
        u = bnd[bnd.fnid.isin(obs.index)][["fnid", "geometry"]]
        if not len(u):
            print(f"  {tag}: no HarvestStat units"); continue
        ov = gpd.overlay(g.to_crs(EQ), u.to_crs(EQ), how="intersection", keep_geom_type=True)
        if not len(ov):
            print(f"  {tag}: no overlap"); continue
        ov["w"] = ov.area * ov.crop_area_frac
        agg = ov[ov.w > 0].groupby("fnid").apply(
            lambda t: pd.Series({"dm": np.average(t.dm, weights=t.w),
                                 "cpi": np.average(t.cpi, weights=t.w)
                                 if t.cpi.notna().all() else np.nan}), include_groups=False)
        j = pd.concat([obs.rename("obs"), agg], axis=1).dropna(subset=["obs", "dm"])
        if len(j) < 5:
            print(f"  {tag}: only {len(j)} matched units"); continue
        o, DMv = j.obs.values, j.dm.values
        dy = DMP.F_ABOVEGROUND * DMP.HARVEST_INDEX * DMv / (1 - DMP.GRAIN_MOISTURE) / 1000.0
        denom = DMv * DMP.F_ABOVEGROUND / (1 - DMP.GRAIN_MOISTURE) / 1000.0
        hi = float(np.sum(denom * o) / np.sum(denom ** 2))
        r = dict(crop=crop, product=tok, n=len(j), obs_mean=round(float(o.mean()), 2),
                 dm_mean=round(float(DMv.mean())),
                 dmp_mae=round(float(np.abs(dy - o).mean()), 3),
                 dmp_bias=round(float((dy - o).mean()), 3),
                 dmp_rho=round(float(spearmanr(o, DMv).statistic), 2),
                 hi_implied=round(hi, 3), overpred=round(float(dy.mean() / o.mean()), 2),
                 hi_in_range=bool(0.30 <= hi <= 0.55))
        if j.cpi.notna().sum() > 4:
            m = j.cpi.notna()
            r["cpi_rho"] = round(float(spearmanr(o[m.values], j.cpi[m].values).statistic), 2)
        rows.append(r)
        print(f"  {tag:28s} n={len(j):3d}  HI {hi:.3f} {'OK ' if r['hi_in_range'] else 'OUT'}"
              f"  over {r['overpred']:.2f}x  rho_dmp {r['dmp_rho']:+.2f}", flush=True)

    if not rows:
        return print("\nnothing scored")
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(H, "Cropyield-Data", "dmp_levels_summary.csv"), index=False)
    print("\n=== DMP level skill across every representative admin-scale frame ===")
    cols = [c for c in ("crop", "product", "n", "obs_mean", "dm_mean", "dmp_mae", "dmp_bias",
                        "hi_implied", "hi_in_range", "overpred", "dmp_rho", "cpi_rho")
            if c in out.columns]
    print(out[cols].to_string(index=False))
    ok = int(out.hi_in_range.sum())
    print(f"\n  frames: {len(out)}")
    print(f"  implied HI inside the agronomic 0.30-0.55 band: {ok} of {len(out)}")
    print(f"  median implied HI: {out.hi_implied.median():.3f}   "
          f"median over-prediction: {out.overpred.median():.2f}x")
    if "cpi_rho" in out.columns:
        c = out.dropna(subset=["cpi_rho"])
        print(f"  DMP out-ranks CPI in {int((c.dmp_rho > c.cpi_rho).sum())} of {len(c)} frames")
    print(f"\nwritten: Cropyield-Data/dmp_levels_summary.csv")


if __name__ == "__main__":
    main()
