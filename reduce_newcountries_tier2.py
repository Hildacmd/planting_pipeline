#!/usr/bin/env python3
"""Tier-2 metrics for the new-country apps: SPI-3 (drought), water deficit (mm), LVPD (last viable
planting + crop-viable %), and FCCI (fused canopy). Computed live from CHIRPS/ERA5/planting — the
planting_dekad comes from the already-exported cpiX_ asset, so no fusion re-run is needed for the
water balance. FCCI rebuilds the S2/S1/FPAR fusion (heavier). Columns are MERGED into the existing
newc_<product>_2024_L{1,2}_skill_WKT.csv (Tier-1 columns preserved).

  EE_PROJECT=ee-manzikye python reduce_newcountries_tier2.py [Product ...] [--metrics spi,def,lvpd,fcci]
  EE_PROJECT=ee-manzikye python reduce_newcountries_tier2.py --crop sorghum

`--crop sorghum` runs the same metrics for the sorghum products, merging into
newcS_<product>_2024_L{1,2}_skill_WKT.csv. It switches the calendar, the FAO-56 coefficients (Kc
0.30/1.05/0.55 and a 1.5 m root zone, with the cycle stretched per product), the rainfall-anchored
season set, the asset prefix and the crop mask. The mask matters most: WorldCereal has no sorghum
class, so `crop_mask_image` would return the temporary-crops extent, which is all cropland.
Maize behaviour with no flag is unchanged.
"""
import sys, os, csv, ee, argparse, pandas as pd, geopandas as gpd
sys.path.insert(0, os.path.dirname(__file__))
def _opt(name, default):
    flag = f"--{name}"
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


CROP = _opt("crop", "maize")
ee.Initialize(project=os.environ.get("EE_PROJECT", "ee-manzikye"))
from src import utils, spi as SPI, soil as SOIL, wrsi_feedback as WR
from src import s2_preprocess as S2, s1_preprocess as S1, fusion_phenometrics as FZ
from src.wrsi_waterbalance import run_wrsi_fao33
from run import crop_mask_image
import reduce_newcountries as R1   # reuse admin_gdf, gdf_to_ee, GADM3, RAIN_TOK, STAGES

YEAR = 2024
CLIM_YEARS = list(range(1981, 2025))
EARLY = {"LGP_dekads": 9, "L_ini": 2, "L_dev": 3, "L_mid": 2, "L_late": 2}
KC, SOIL_CFG = utils.load_crop_coeffs()
PROJ = f"projects/{os.environ.get('EE_PROJECT', 'ee-manzikye')}/assets"

if CROP == "sorghum":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sorghum_pipeline"))
    import csv as _csv
    import sorghum_params as SP
    import run_all_sorghum as RS
    import ctm_mask as CTM
    ASSET_PREFIX, OUT_PREFIX = "sorghumX", "newcS"
    _rows = list(_csv.DictReader(open(RS.CALENDARS["report"][0])))
    ROWS = {(r["country"], r["season"]): r for r in _rows}
    TOK2CS = {f"{r['country']}_{r['season']}".replace(" ", ""): (r["country"], r["season"])
              for r in _rows}

    def _is_rain(tok):
        return TOK2CS[tok][1] in RS.RAINFALL_ANCHORED

    def _kc(tok):
        """FAO-56 sorghum coefficients for this product, cycle stretched as the runner does."""
        c, s_ = TOK2CS[tok]
        return RS.kc_for(ROWS[(c, s_)])

    def _mask(country):
        return CTM.crop_mask(ee, country, "sorghum")
else:
    ASSET_PREFIX, OUT_PREFIX = "cpiX", "newc"
    ROWS = {(r["country"], r["season"]): r for r in
            utils.viable_products(utils.load_calendar("config/season_calendar.csv"))
            if r["crop"].lower() == "maize"}
    # product token (cpiX id) -> (calendar country, season)
    TOK2CS = {"Uganda_1strains": ("Uganda", "1st rains"), "Uganda_2ndrains": ("Uganda", "2nd rains"),
              "Rwanda_SeasonA": ("Rwanda", "Season A"), "Rwanda_SeasonB": ("Rwanda", "Season B"),
              "Burundi_SeasonA": ("Burundi", "Season A"), "Burundi_SeasonB": ("Burundi", "Season B"),
              "Tanzania_Masika": ("Tanzania", "Masika"), "Tanzania_Msimu": ("Tanzania", "Msimu"),
              "Tanzania_Vuli": ("Tanzania", "Vuli"), "SouthSudan_Main": ("South Sudan", "Main"),
              "Somalia_Gu": ("Somalia", "Gu"), "Somalia_Deyr": ("Somalia", "Deyr"),
              "Ethiopia_Belg": ("Ethiopia", "Belg")}

    def _is_rain(tok):
        return tok in R1.RAIN_TOK

    def _kc(tok):
        return {**KC["maize"], **(EARLY if _is_rain(tok) else {})}

    def _mask(country):
        return crop_mask_image(ee, country, "maize", None)


def season_window(tok):
    c, s = TOK2CS[tok]; r = ROWS[(c, s)]
    ss, se = utils.sos_window_dekads(r["sos_detection_window"])
    rain = _is_rain(tok)
    lgp = _kc(tok)["LGP_dekads"]
    se_use = se + 36 if ss > se else se               # cross-year unwrap
    return ss, se_use, lgp, rain


def end_month(se_use, lgp):
    d = se_use + lgp                                   # ~ season end dekad (may exceed 36)
    return ((d - 1) // 3) % 12 + 1


def metric_images(tok, aoi, mask, planting, which):
    ss, se_use, lgp, rain = season_window(tok)
    em = end_month(se_use, lgp)
    imgs = {}
    if "spi" in which:                                                  # SPI-3 drought (CHIRPS, cheap)
        spi = SPI.spi3(ee, aoi, YEAR if se_use <= 36 else YEAR + (0 if em >= 7 else 1), em)
        imgs["spi3_mean"] = spi.updateMask(mask)
        imgs["spi3_dry"] = spi.lte(-1).updateMask(mask)                 # fraction with SPI-3 <= -1
    if "def" in which:                                                  # water deficit (planting from asset)
        p_ = _kc(tok)
        kc_use = {CROP: p_}
        whc = SOIL.get_whc(ee, aoi, SOIL_CFG, root_depth_cm=int(p_.get("root_depth_m", 1.0) * 100))
        wb = run_wrsi_fao33(ee, aoi, YEAR if not (ss > (se_use % 36 or 36)) else YEAR - 1,
                            planting, CROP, kc_use, SOIL_CFG, ss, se_use, whc_img=whc)
        imgs["deficit"] = wb["deficit_mm"].updateMask(mask)
    if "lvpd" in which:                                                 # climatological last-viable-planting
        pet = WR.pet_dekadal(ee, aoi, YEAR)
        def clim_P(dk):
            d = dk if dk <= 36 else dk - 36
            s = [ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterBounds(aoi)
                   .filterDate(ee.Date.fromYMD(y if dk <= 36 else y + 1, 1, 1).advance((d - 1) * 10, "day"),
                               ee.Date.fromYMD(y if dk <= 36 else y + 1, 1, 1).advance((d - 1) * 10 + 10, "day")).sum()
                 for y in CLIM_YEARS]
            return ee.ImageCollection(s).mean()
        def petd(dk):
            d = dk if dk <= 36 else dk - 36
            return ee.Image(pet.filter(ee.Filter.eq("dekad", d)).first()).select("ET0")
        lgp_end = ee.Image(0)
        for dk in range(ss, se_use + lgp + 1):
            lgp_end = lgp_end.where(clim_P(dk).divide(petd(dk).max(1e-3)).gte(0.5), dk)
        lvpd = lgp_end.add(3).subtract(lgp).rename("lvpd")
        imgs["lvpd"] = lvpd.updateMask(mask)
        imgs["viable"] = planting.lte(lvpd).updateMask(mask)
    if "fcci" in which:                                                 # peak fused greenness (heavier)
        byear = YEAR - 1 if ss > (se_use % 36 or 36) else YEAR
        dks = range(ss, se_use + 1)
        s2 = S2.build_s2_dekadal(ee, aoi, byear, dekads=dks)
        s1 = S1.build_s1_dekadal(ee, aoi, byear, orbit="DESCENDING", dekads=dks)
        fpar = FZ.add_fpar_dekadal(ee, aoi, byear, dekads=dks)
        gg = FZ.build_fused_greenness(ee, s2, s1, fpar)
        imgs["fcci"] = FZ.fused_condition(ee, gg, mask, ss, min(se_use, 36), lgp=lgp)
    if "vci" in which:                                                  # Vegetation Condition Index (cheap, MODIS NDVI)
        from src import cpi as CPI
        coll, bnd, scale = CPI.VEG_CFG["ndvi"]
        peak = lambda yr: CPI._seasonal_peak(ee, aoi, yr, ss, min(se_use, 36), coll, bnd, scale)
        hist = ee.ImageCollection([peak(y) for y in range(2003, 2024)])
        vmin, vmax = hist.min(), hist.max()
        vci = peak(YEAR).subtract(vmin).divide(vmax.subtract(vmin).max(1e-3)).clamp(0, 1).multiply(100)  # Kogan VCI
        # collection arithmetic drops the projection to ~1 deg; pin 250 m so reduceRegions samples small admins
        imgs["vci"] = vci.setDefaultProjection("EPSG:4326", None, 250).updateMask(mask).rename("vci")
    return imgs


NEWCOLS = ["spi3_mean", "spi3_dry_pct", "mean_deficit_mm", "lvpd_dekad", "crop_viable_pct", "fcci"]


def reduce_and_merge(tok, which):
    c, s = TOK2CS[tok]
    ctok = R1.country_token(tok)          # longest matching prefix: South_Sudan_Main works too
    asset = f"{PROJ}/{ASSET_PREFIX}_{tok}_2024"
    try:
        ee.data.getAsset(asset)
    except Exception:
        print(f"  [skip] no asset {ASSET_PREFIX}_{tok}_2024"); return
    img = ee.Image(asset); planting = img.select("planting_dekad")
    print(f"== {tok} ==")
    for lvl in (1, 2):
        g = R1.admin_gdf(ctok, lvl)
        aoi = ee.Geometry(g.unary_union.__geo_interface__).bounds()
        mask = _mask(c)
        imgs = metric_images(tok, aoi, mask, planting, which)
        fc = R1.gdf_to_ee(g[["_id", "geometry"]])
        # ONE reduceRegions per metric GROUP (keeps each request light; a heavy group can fail alone)
        groups = {"spi": ["spi3_mean", "spi3_dry"], "def": ["deficit"],
                  "lvpd": ["lvpd", "viable"], "fcci": ["fcci"], "vci": ["vci"]}
        red = {}
        for gk, bands in groups.items():
            if gk not in which or not all(b in imgs for b in bands):
                continue
            band = ee.Image.cat([imgs[b].rename(b) for b in bands])
            # Level 1 units are whole states and regions, and a mean over one of them at 250 m can
            # exceed the Earth Engine budget: Sudan's 18 states timed out on SPI-3. Retry coarser
            # before giving up. Coarsening a MEAN costs little here, and SPI-3 is 5.5 km CHIRPS
            # and ERA5 anyway, so 250 m was oversampling it in the first place.
            for scale, tile in ((250, 8), (1000, 16), (2500, 16)):
                try:
                    # A MULTI-band image already names its outputs after the bands. A
                    # SINGLE-band one comes back as {"mean": ...}, so get(band_name) found
                    # nothing and every unit was written null while the run reported success -
                    # which is why only deficit, fcci and vci were silently empty. setOutputs
                    # pins the name, but Reducer.mean has exactly ONE output, so passing it two
                    # names is an error: apply it only in the single-band case.
                    rd = (ee.Reducer.mean().setOutputs(bands) if len(bands) == 1
                          else ee.Reducer.mean())
                    feats = band.reduceRegions(fc, rd, scale=scale,
                                               tileScale=tile).getInfo()["features"]
                    for r in feats:
                        red.setdefault(r["properties"]["_id"], {}).update(
                            {b: r["properties"].get(b) for b in bands})
                    if scale != 250:
                        print(f"  L{lvl}: {gk} needed {scale} m")
                    break
                except Exception as e:
                    last = e
                    if scale != 2500:
                        continue
                    # Coarsening does not help a MEMORY limit, only a time limit: the request is
                    # too big whatever the pixel size. Sudan's 72 localities exceeded it on FCCI,
                    # which rebuilds the Sentinel-2, Sentinel-1 and FPAR fusion. Splitting the
                    # units into batches cuts the per-request footprint instead.
                    # Batching the REGIONS alone is not enough: the metric image is built over
                    # the whole country, and for FCCI that means the Sentinel-2, Sentinel-1 and
                    # FPAR fusion across Sudan, which blows the memory limit before any region is
                    # touched. Rebuild the metric over each batch's OWN extent as well.
                    # Smaller batches shrink the AOI, and a smaller AOI may fit 250 m where the
                    # whole country does not, so try the FULL resolution at each batch size before
                    # giving up any precision. Only fall back to 1000 m if even 4 units at 250 m
                    # will not fit.
                    n = g.shape[0]
                    done = False
                    for bscale in (250, 1000):
                        for batch in (16, 8, 4):
                            try:
                                got = {}
                                for i0 in range(0, n, batch):
                                    gb = g.iloc[i0:i0 + batch]
                                    sub_aoi = ee.Geometry(gb.unary_union.__geo_interface__).bounds()
                                    imgs_b = metric_images(tok, sub_aoi, mask, planting, {gk})
                                    band_b = ee.Image.cat([imgs_b[b].rename(b) for b in bands])
                                    sub = R1.gdf_to_ee(gb[["_id", "geometry"]])
                                    for r in band_b.reduceRegions(sub, rd, scale=bscale,
                                                                  tileScale=16).getInfo()["features"]:
                                        got[r["properties"]["_id"]] = {
                                            b: r["properties"].get(b) for b in bands}
                                for k, v in got.items():
                                    red.setdefault(k, {}).update(v)
                                print(f"  L{lvl}: {gk} needed per-batch extents, "
                                      f"{batch} units at {bscale} m")
                                done = True
                                break
                            except Exception as e2:
                                last = e2
                        if done:
                            break
                    if not done:
                        print(f"  L{lvl}: {gk} FAILED at every scale and batch size "
                              f"({str(last)[:60]}) — null")
        csvf = f"{OUT_PREFIX}_{tok}_2024_L{lvl}_skill_WKT.csv"
        df = pd.read_csv(csvf)
        gi = g.set_index("_id")
        # match CSV rows to admin _id by (name, county)
        key2id = {(gi.loc[i, "name"], gi.loc[i, "county"]): i for i in gi.index}
        for col in NEWCOLS:
            if col not in df.columns: df[col] = None
        for idx, r in df.iterrows():
            aid = key2id.get((r["name"], r.get("county") if pd.notna(r.get("county")) else ""))
            p = red.get(aid, {}) if aid is not None else {}
            if "spi" in which:
                df.at[idx, "spi3_mean"] = round(p["spi3_mean"], 2) if p.get("spi3_mean") is not None else df.at[idx, "spi3_mean"]
                df.at[idx, "spi3_dry_pct"] = round(p["spi3_dry"] * 100, 1) if p.get("spi3_dry") is not None else df.at[idx, "spi3_dry_pct"]
            if "def" in which and p.get("deficit") is not None:
                df.at[idx, "mean_deficit_mm"] = round(p["deficit"], 1)
            if "lvpd" in which:
                if p.get("lvpd") is not None: df.at[idx, "lvpd_dekad"] = int(round(p["lvpd"]))
                if p.get("viable") is not None: df.at[idx, "crop_viable_pct"] = round(p["viable"] * 100, 1)
            if "fcci" in which and p.get("fcci") is not None:
                df.at[idx, "fcci"] = round(p["fcci"], 1)
            if "vci" in which and p.get("vci") is not None:
                df.at[idx, "fcci"] = round(p["vci"], 1)   # VCI fills the canopy-condition (fcci) column
        df.to_csv(csvf, index=False)
        # report the column each requested metric actually writes, not a fixed one: with
        # --metrics def this counted fcci and printed 0/N for a run that had worked.
        checks = {"spi": "spi3_mean", "def": "mean_deficit_mm", "lvpd": "lvpd_dekad",
                  "fcci": "fcci", "vci": "fcci"}
        got = {k: int(df[checks[k]].notna().sum()) for k in sorted(which) if k in checks}
        # NOTE: this is the column total after the merge, not what this run contributed. On a
        # re-run a failed group still shows the values that were already in the CSV.
        print(f"  L{lvl}: {got} of {len(df)} units non-null  ({csvf})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("products", nargs="*", default=list(TOK2CS))
    ap.add_argument("--metrics", default="spi,def,lvpd,fcci")
    ap.add_argument("--crop", default="maize", choices=["maize", "sorghum"])
    a = ap.parse_args()
    print(f"crop={CROP} · assets {ASSET_PREFIX}_* · output {OUT_PREFIX}_* · metrics {a.metrics}")
    which = set(a.metrics.split(","))
    for p in (a.products or list(TOK2CS)):
        reduce_and_merge(p, which)
