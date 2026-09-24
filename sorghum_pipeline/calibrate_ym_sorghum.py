#!/usr/bin/env python3
"""Fit the sorghum attainable-yield ceiling Ym against HarvestStat, the same way as maize.

    yield (t/ha) = CPI/100 x Ym,      Ym = sum(y*c) / sum(c^2)   with c = CPI/100

The admin-2 CPI exported by `zonal_sorghum.py` is aggregated onto the HarvestStat reporting
units by polygon overlap, **weighted by the sorghum area in each overlap**, so a large unit
with little sorghum cannot dominate. The target is the **median over the available years**, a
typical year, which is robust to one bad season and applies to any season rather than only to
the one that was modelled. Skill is out of sample: 70/30 splits repeated 200 times, reporting
the mean absolute error on held-out units for the fitted ceiling and for the uncalibrated
default, plus the Pearson r between predicted and reported yield.

**Read r before using a fitted ceiling.** A calibrated level with r near zero means the map has
the average right but cannot tell which unit yielded more. On maize that was the outcome for
Rwanda, Burundi and Somalia, and those products are documented as level-only.

    python sorghum_pipeline/calibrate_ym_sorghum.py
    python sorghum_pipeline/calibrate_ym_sorghum.py --write     # also patch YM_CAL_SORGHUM

Writes work/ym_calibration_sorghum.csv and work/ym_calibration_sorghum_units.csv.
"""
import argparse, os, random, sys
import numpy as np, pandas as pd, geopandas as gpd

H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(H)
sys.path.insert(0, H)
import sorghum_params as P                                     # noqa: E402

HS = os.path.join(ROOT, "Cropyield-Data", "harveststat")
DRIVE = os.environ.get("CTM_LOCAL_DRIVE", os.path.expanduser(
    "~/Library/CloudStorage/GoogleDrive-manzikye@gmail.com/My Drive/planting_outputs"))
YEAR = 2024
# Overlap weights are areas, so they are measured in an EQUAL-AREA projection. Computing them in
# EPSG:4326 measures square degrees, which shrink with latitude: across this region, from Tanzania
# at 12 S to Sudan at 22 N, a degree cell at the northern edge is about 7 % smaller than one at the
# equator, so the same field would be weighted differently by where it happens to sit. Africa
# Albers Equal Area, as used for the crop-type mask reprojections.
AEA = ("+proj=aea +lat_1=20 +lat_2=-23 +lat_0=0 +lon_0=25 +x_0=0 +y_0=0 "
       "+datum=WGS84 +units=m +no_defs")
MAX_YIELD = 6.0        # t/ha: above this is implausible for rainfed smallholder sorghum
SPLITS, TRAIN = 200, 0.7

# (pipeline country, pipeline season, HarvestStat country, HarvestStat season_name, years)
JOBS = [
    ("Ethiopia",    "Meher",       "Ethiopia",    "Meher",    range(2012, 2022)),
    ("Kenya",       "Long rains",  "Kenya",       "Long",     range(2015, 2017)),
    ("Kenya",       "Short rains", "Kenya",       "Short",    range(2016, 2018)),
    ("Uganda",      "1st rains",   "Uganda",      "First",    range(2009, 2010)),
    ("Uganda",      "2nd rains",   "Uganda",      "Second",   range(2008, 2009)),
    ("Somalia",     "Gu",          "Somalia",     "Gu",       range(2015, 2025)),
    ("Somalia",     "Deyr",        "Somalia",     "Deyr",     range(2015, 2025)),
    ("Sudan",       "Kharif",      "Sudan",       "Main",     range(2015, 2024)),
    ("Rwanda",      "Season A",    "Rwanda",      "Season A", range(2010, 2018)),
    ("Rwanda",      "Season B",    "Rwanda",      "Season B", range(2009, 2018)),
    ("Burundi",     "Season A",    "Burundi",     "Season A", range(2013, 2017)),
    ("Burundi",     "Season B",    "Burundi",     "Season B", range(2012, 2015)),
    ("South_Sudan", "Main",        "South Sudan", "Main",     range(1990, 2011)),
]
# Tanzania and Eritrea are absent: HarvestStat holds no sorghum yields for either.


def cpi_units(country, season, prefix="newcS"):
    """Admin-2 CPI and sorghum area fraction, as a GeoDataFrame.

    Prefers the reducer output (`newcS_<product>_2024_L2_skill_WKT.csv`), which already carries
    the area-weighted CPI, `crop_area_frac` and the geometry, so `zonal_sorghum.py` is not needed
    when the app reduce has already run. Falls back to the zonal export if it has not."""
    tok = f"{country}_{season}".replace(" ", "")
    from shapely import wkt as _wkt
    import pandas as _pd
    f = os.path.join(ROOT, f"{prefix}_{tok}_{YEAR}_L2_skill_WKT.csv")
    if os.path.exists(f):
        d = _pd.read_csv(f)
        return gpd.GeoDataFrame(d, geometry=d.geometry_wkt.map(_wkt.loads), crs="EPSG:4326")
    for dd in (DRIVE, f"{H}/work"):
        p = os.path.join(dd, f"sorghum_{tok}_{YEAR}_L2.csv")
        if os.path.exists(p):
            return gpd.read_file(p)
    return None


def fit(y, c):
    """Least squares through the origin: Ym = sum(y*c) / sum(c^2)."""
    c = np.asarray(c, float); y = np.asarray(y, float)
    return float((y * c).sum() / max((c * c).sum(), 1e-9))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="patch YM_CAL_SORGHUM in sorghum_params.py with the fitted ceilings")
    a = ap.parse_args()

    d = pd.read_csv(os.path.join(HS, "hvstat_africa_data_v1.2.csv"), low_memory=False)
    d.columns = [c.lower() for c in d.columns]
    b = gpd.read_file(os.path.join(HS, "hvstat_africa_boundary_v1.2.gpkg"))
    b.columns = [c.lower() for c in b.columns]

    rows, units = [], []
    for country, season, hs_country, hs_season, years in JOBS:
        g = cpi_units(country, season)
        if g is None:
            rows.append(dict(country=country, season=season, status="no CPI export yet"))
            continue
        y = d[(d["product"] == "Sorghum") & (d.country == hs_country)
              & (d.season_name == hs_season) & d.harvest_year.isin(years) & d["yield"].notna()]
        obs = (y.groupby("fnid")["yield"].median().rename("y").reset_index())
        obs = obs[obs.y <= MAX_YIELD]
        u = b.merge(obs, on="fnid").to_crs(4326)
        if len(u) < 5:
            rows.append(dict(country=country, season=season, units=len(u),
                             status="too few HarvestStat units")); continue

        g = g[g.cpi.notna() & g.crop_area_frac.notna() & (g.crop_area_frac > 0)].to_crs(4326)
        ov = gpd.overlay(u[["fnid", "y", "geometry"]], g[["cpi", "crop_area_frac", "geometry"]],
                         how="intersection").to_crs(AEA)
        ov["w"] = ov.area * ov.crop_area_frac                     # sorghum area in the overlap, m2
        agg = (ov.groupby("fnid")[["cpi", "y", "w"]].apply(
            lambda t: pd.Series({"cpi": np.average(t.cpi, weights=t.w) if t.w.sum() > 0 else np.nan,
                                 "y": t.y.iloc[0], "w": t.w.sum()}))
               .dropna().reset_index())
        agg = agg[agg.w > 0]
        if len(agg) < 5:
            rows.append(dict(country=country, season=season, units=len(agg),
                             status="too few matched units")); continue

        c = (agg.cpi / 100).values; yv = agg.y.values
        ym = fit(yv, c)
        # Compare against the UNCALIBRATED default, not against whatever YM_CAL_SORGHUM currently
        # holds. Using ym_for here made the second run compare each fitted ceiling with itself, so
        # the "default" column silently stopped meaning anything.
        _s = str(season).lower()
        dflt = (P.SORGHUM_YM_SHORT_DEFAULT
                if ("short" in _s or "2nd" in _s or "deyr" in _s) else P.SORGHUM_YM_DEFAULT)
        rnd = random.Random(0); mae_c, mae_d = [], []
        idx = list(range(len(agg)))
        for _ in range(SPLITS):
            rnd.shuffle(idx)
            k = max(2, int(TRAIN * len(idx)))
            tr, te = idx[:k], idx[k:]
            if not te:
                continue
            m = fit(yv[tr], c[tr])
            mae_c.append(np.abs(c[te] * m - yv[te]).mean())
            mae_d.append(np.abs(c[te] * dflt - yv[te]).mean())
        r = float(np.corrcoef(c * ym, yv)[0, 1]) if len(agg) > 2 else float("nan")
        rows.append(dict(country=country, season=season, units=len(agg),
                         years=f"{min(years)}-{max(years)}", ym_fitted=round(ym, 2),
                         ym_default=dflt, test_mae_calibrated=round(np.mean(mae_c), 2),
                         test_mae_default=round(np.mean(mae_d), 2), r=round(r, 2),
                         status="level and pattern" if r >= 0.45 else
                                "level, weak pattern" if r >= 0.25 else "level only"))
        agg["country"], agg["season"] = country, season
        units.append(agg)

    out = pd.DataFrame(rows)
    out.to_csv(f"{H}/work/ym_calibration_sorghum.csv", index=False)
    if units:
        pd.concat(units, ignore_index=True).to_csv(
            f"{H}/work/ym_calibration_sorghum_units.csv", index=False)
    print(out.to_string(index=False))

    if a.write and "ym_fitted" in out:
        fitted = out.dropna(subset=["ym_fitted"])
        body = "\n".join(f'    ("{r.country}", "{r.season}"): {r.ym_fitted:.2f},'
                         f'   # n{int(r.units)} {r.years}  MAE {r.test_mae_calibrated} vs '
                         f'{r.test_mae_default}  r {r.r}  {r.status}'
                         for r in fitted.itertuples())
        import re as _re
        p = f"{H}/sorghum_params.py"; s = open(p).read()
        # Replace the whole block, however it currently reads. Matching the literal
        # "YM_CAL_SORGHUM = {}" worked once and then silently did nothing on every later run,
        # while still printing success, because the dict was no longer empty.
        new_block = "YM_CAL_SORGHUM = {\n" + body + "\n}"
        s2, n = _re.subn(r"^YM_CAL_SORGHUM = \{.*?^\}", new_block, s,
                         count=1, flags=_re.S | _re.M)
        if n != 1:
            raise SystemExit("could not locate the YM_CAL_SORGHUM block in sorghum_params.py")
        open(p, "w").write(s2)
        print(f"\npatched YM_CAL_SORGHUM with {len(fitted)} ceilings")


if __name__ == "__main__":
    main()
