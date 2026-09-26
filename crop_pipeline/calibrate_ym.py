#!/usr/bin/env python3
"""Fit the attainable-yield ceiling Ym for wheat, teff and millet against HarvestStat.

    yield (t/ha) = CPI/100 x Ym,      Ym = sum(y*c) / sum(c^2)   with c = CPI/100

Same method as maize and sorghum. The admin-2 CPI is aggregated onto the HarvestStat reporting
units by polygon overlap, weighted by the crop area in each overlap and measured in an EQUAL-AREA
projection, so a unit that is 2 % of the crop cannot count the same as one that is 60 %. The target
is the median over the available years — a typical year, robust to one bad season. Skill is out of
sample: 70/30 splits repeated 200 times.

**Read r before using a ceiling.** A calibrated level with r near zero means the map has the
average right but cannot tell which unit yielded more. Across maize and sorghum that has been the
rule rather than the exception.

    python crop_pipeline/calibrate_ym.py --crop all
    python crop_pipeline/calibrate_ym.py --crop wheat --write
"""
import argparse, os, random, re, sys
import numpy as np, pandas as pd, geopandas as gpd
from shapely import wkt

H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(H)
sys.path.insert(0, ROOT); sys.path.insert(0, H)
from params import get                                                # noqa: E402

HS = os.path.join(ROOT, "Cropyield-Data", "harveststat")
YEAR, SPLITS, TRAIN = 2024, 200, 0.7
AEA = ("+proj=aea +lat_1=20 +lat_2=-23 +lat_0=0 +lon_0=25 +x_0=0 +y_0=0 "
       "+datum=WGS84 +units=m +no_defs")
PREFIX = {"wheat": "newcW", "teff": "newcT", "millet": "newcM"}
# Above this a unit value is implausible for the crop as grown here and is dropped.
MAX_YIELD = {"wheat": 8.0, "teff": 4.0, "millet": 5.0}

# crop -> [(pipeline country, pipeline season, HarvestStat country, HarvestStat season, years)]
# HarvestStat's season naming does not always match the pipeline's: Kenyan wheat and millet are
# reported as "Annual", not by season.
JOBS = {
    "wheat": [("Ethiopia", "Meher",      "Ethiopia", "Meher",  range(2012, 2022)),
              ("Kenya",    "Long rains", "Kenya",    "Annual", range(2010, 2021)),
              ("Sudan",    "Shitwi",     "Sudan",    "Main",   range(2010, 2021)),
              ("Tanzania", "Msimu",      "Tanzania", "Msimu",  range(2010, 2021))],
    "teff":  [("Ethiopia", "Meher",      "Ethiopia", "Meher",  range(2012, 2022))],
    "millet": [("Sudan",   "Kharif",     "Sudan",    "Main",   range(2015, 2024)),
               ("Eritrea", "Kremti",     "Eritrea",  "Kremti", range(2010, 2021))],
}
HSNAME = {"wheat": "Wheat", "teff": "Teff", "millet": "Millet"}


def cpi_units(crop, country, season):
    tok = f"{country}_{season}".replace(" ", "")
    f = os.path.join(ROOT, f"{PREFIX[crop]}_{tok}_{YEAR}_L2_skill_WKT.csv")
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f)
    return gpd.GeoDataFrame(d, geometry=d.geometry_wkt.map(wkt.loads), crs="EPSG:4326")


def fit(y, c):
    return float((y * c).sum() / max((c * c).sum(), 1e-9))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crop", default="all", choices=["wheat", "teff", "millet", "all"])
    ap.add_argument("--write", action="store_true",
                    help="patch YM_CAL in the crop's params module")
    a = ap.parse_args()
    crops = ["wheat", "teff", "millet"] if a.crop == "all" else [a.crop]

    d = pd.read_csv(os.path.join(HS, "hvstat_africa_data_v1.2.csv"), low_memory=False)
    d.columns = [c.lower() for c in d.columns]
    b = gpd.read_file(os.path.join(HS, "hvstat_africa_boundary_v1.2.gpkg"))
    b.columns = [c.lower() for c in b.columns]

    allrows = {}
    for crop in crops:
        p = get(crop); rows = []
        for country, season, hsc, hss, years in JOBS[crop]:
            g = cpi_units(crop, country, season)
            if g is None:
                rows.append(dict(country=country, season=season,
                                 status="no CPI reduce yet")); continue
            y = d[(d["product"] == HSNAME[crop]) & (d.country == hsc)
                  & (d.season_name == hss) & d.harvest_year.isin(years) & d["yield"].notna()]
            obs = y.groupby("fnid")["yield"].median().rename("y").reset_index()
            obs = obs[obs.y <= MAX_YIELD[crop]]
            if not len(obs):
                rows.append(dict(country=country, season=season,
                                 status=f"no HarvestStat {HSNAME[crop]} for {hsc} {hss}")); continue
            units = b.merge(obs, on="fnid").to_crs(4326)
            g = g[g.cpi.notna() & g.crop_area_frac.notna() & (g.crop_area_frac > 0)].to_crs(4326)
            ov = gpd.overlay(units[["fnid", "y", "geometry"]],
                             g[["cpi", "crop_area_frac", "geometry"]],
                             how="intersection").to_crs(AEA)
            ov["w"] = ov.area * ov.crop_area_frac
            agg = (ov.groupby("fnid")[["cpi", "y", "w"]]
                     .apply(lambda t: pd.Series({
                         "cpi": np.average(t.cpi, weights=t.w) if t.w.sum() > 0 else np.nan,
                         "y": t.y.iloc[0], "w": t.w.sum()})).dropna().reset_index())
            agg = agg[agg.w > 0]
            if len(agg) < 5:
                rows.append(dict(country=country, season=season, units=len(agg),
                                 status="too few matched units")); continue
            c = (agg.cpi / 100).values; yv = agg.y.values
            ym = fit(yv, c)
            s_ = str(season).lower()
            dflt = (p.YM_SHORT_DEFAULT if ("short" in s_ or "2nd" in s_ or "deyr" in s_)
                    else p.YM_DEFAULT)
            rnd = random.Random(0); mc, md = [], []
            idx = list(range(len(agg)))
            for _ in range(SPLITS):
                rnd.shuffle(idx)
                k = max(2, int(TRAIN * len(idx))); tr, te = idx[:k], idx[k:]
                if not te:
                    continue
                m_ = fit(yv[tr], c[tr])
                mc.append(np.abs(c[te] * m_ - yv[te]).mean())
                md.append(np.abs(c[te] * dflt - yv[te]).mean())
            r = float(np.corrcoef(c * ym, yv)[0, 1]) if len(agg) > 2 else float("nan")
            rows.append(dict(country=country, season=season, units=len(agg),
                             years=f"{min(years)}-{max(years)}", ym_fitted=round(ym, 2),
                             ym_default=dflt, test_mae_calibrated=round(np.mean(mc), 2),
                             test_mae_default=round(np.mean(md), 2), r=round(r, 2),
                             status=("level and pattern" if r >= 0.45 else
                                     "level, weak pattern" if r >= 0.25 else "level only")))
        out = pd.DataFrame(rows)
        out.insert(0, "crop", crop)
        allrows[crop] = out
        print(f"\n=== {crop.upper()} ===")
        print(out.to_string(index=False))
        os.makedirs(f"{H}/work", exist_ok=True)
        out.to_csv(f"{H}/work/ym_calibration_{crop}.csv", index=False)

        if a.write and "ym_fitted" in out:
            ok = out.dropna(subset=["ym_fitted"])
            if not len(ok):
                continue
            body = "\n".join(
                f'    ("{r.country}", "{r.season}"): {r.ym_fitted:.2f},'
                f'   # n{int(r.units)} {r.years}  MAE {r.test_mae_calibrated} vs '
                f'{r.test_mae_default}  r {r.r}  {r.status}' for r in ok.itertuples())
            pth = f"{H}/params/{crop}.py"; s = open(pth).read()
            s2, n = re.subn(r"^YM_CAL = \{.*?\}|^YM_CAL = \{\}",
                            "YM_CAL = {\n" + body + "\n}", s, count=1, flags=re.S | re.M)
            if n != 1:
                raise SystemExit(f"could not locate YM_CAL in {pth}")
            open(pth, "w").write(s2)
            print(f"  patched {crop}.YM_CAL with {len(ok)} ceilings")


if __name__ == "__main__":
    main()
