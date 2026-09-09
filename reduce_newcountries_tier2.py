#!/usr/bin/env python3
"""Tier-2 metrics for the new-country apps: SPI-3 (drought), water deficit (mm), LVPD (last viable
planting + crop-viable %), and FCCI (fused canopy). Computed live from CHIRPS/ERA5/planting — the
planting_dekad comes from the already-exported cpiX_ asset, so no fusion re-run is needed for the
water balance. FCCI rebuilds the S2/S1/FPAR fusion (heavier). Columns are MERGED into the existing
newc_<product>_2024_L{1,2}_skill_WKT.csv (Tier-1 columns preserved).

  EE_PROJECT=ee-manzikye python reduce_newcountries_tier2.py [Product ...]  [--metrics spi,def,lvpd,fcci]
"""
import sys, os, csv, ee, argparse, pandas as pd, geopandas as gpd
sys.path.insert(0, os.path.dirname(__file__))
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
ROWS = {(r["country"], r["season"]): r for r in
        utils.viable_products(utils.load_calendar("config/season_calendar.csv")) if r["crop"].lower() == "maize"}
# product token (cpiX id) -> (calendar country, season)
TOK2CS = {"Uganda_1strains": ("Uganda", "1st rains"), "Uganda_2ndrains": ("Uganda", "2nd rains"),
          "Rwanda_SeasonA": ("Rwanda", "Season A"), "Rwanda_SeasonB": ("Rwanda", "Season B"),
          "Burundi_SeasonA": ("Burundi", "Season A"), "Burundi_SeasonB": ("Burundi", "Season B"),
          "Tanzania_Masika": ("Tanzania", "Masika"), "Tanzania_Msimu": ("Tanzania", "Msimu"),
          "Tanzania_Vuli": ("Tanzania", "Vuli"), "SouthSudan_Main": ("South Sudan", "Main"),
          "Somalia_Gu": ("Somalia", "Gu"), "Somalia_Deyr": ("Somalia", "Deyr"),
          "Ethiopia_Belg": ("Ethiopia", "Belg")}
PROJ = "projects/ee-manzikye/assets"


def season_window(tok):
    c, s = TOK2CS[tok]; r = ROWS[(c, s)]
    ss, se = utils.sos_window_dekads(r["sos_detection_window"])
    rain = tok in R1.RAIN_TOK
    lgp = EARLY["LGP_dekads"] if rain else KC["maize"]["LGP_dekads"]
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
        kc_use = {"maize": {**KC["maize"], **(EARLY if rain else {})}}
        whc = SOIL.get_whc(ee, aoi, SOIL_CFG, root_depth_cm=int(KC["maize"].get("root_depth_m", 1.0) * 100))
        wb = run_wrsi_fao33(ee, aoi, YEAR if not (ss > (se_use % 36 or 36)) else YEAR - 1,
                            planting, "maize", kc_use, SOIL_CFG, ss, se_use, whc_img=whc)
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
        lvpd = lgp_end.add(3).subtract(EARLY["LGP_dekads"]).rename("lvpd")
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
    c, s = TOK2CS[tok]; ctok = tok.split("_")[0]
    asset = f"{PROJ}/cpiX_{tok}_2024"
    try:
        ee.data.getAsset(asset)
    except Exception:
        print(f"  [skip] no asset cpiX_{tok}_2024"); return
    img = ee.Image(asset); planting = img.select("planting_dekad")
    print(f"== {tok} ==")
    for lvl in (1, 2):
        g = R1.admin_gdf(ctok, lvl)
        aoi = ee.Geometry(g.unary_union.__geo_interface__).bounds()
        mask = crop_mask_image(ee, c, "maize", None)
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
            try:
                for r in band.reduceRegions(fc, ee.Reducer.mean(), scale=250, tileScale=8).getInfo()["features"]:
                    red.setdefault(r["properties"]["_id"], {}).update(
                        {b: r["properties"].get(b) for b in bands})
            except Exception as e:
                print(f"  L{lvl}: {gk} FAILED ({str(e)[:60]}) — null")
        csvf = f"newc_{tok}_2024_L{lvl}_skill_WKT.csv"
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
        got = df["spi3_mean"].notna().sum() if "spi" in which else df["fcci"].notna().sum()
        print(f"  L{lvl}: merged {which} -> {got}/{len(df)} units  ({csvf})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("products", nargs="*", default=list(TOK2CS))
    ap.add_argument("--metrics", default="spi,def,lvpd,fcci")
    a = ap.parse_args()
    which = set(a.metrics.split(","))
    for p in (a.products or list(TOK2CS)):
        reduce_and_merge(p, which)
