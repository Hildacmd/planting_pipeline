#!/usr/bin/env python3
"""Submit wheat, teff and millet products, on the same engine as maize and sorghum.

One runner for all three, driven by `crop_pipeline/params/<crop>.py`, so the crops cannot drift
apart in anything but their parameters. The engine, the onset method, the water balance and the
CPI formulation are identical to the maize and sorghum runs; what changes per crop is the FAO-56
Kc curve and rooting depth, the FAO-33 stage yield factors, the flowering heat cap, the emergence
offset and the mask band.

    python crop_pipeline/run_all_crop.py --crop wheat                 # dry run
    EE_PROJECT=ee-manzikye python crop_pipeline/run_all_crop.py --crop wheat --rich --submit
    EE_PROJECT=ee-manzikye python crop_pipeline/run_all_crop.py --crop all --rich --submit

Assets land as `<crop>X_<Country>_<Season>_2024` with --rich, `<crop>_...` without. **Use --rich
if the products are to reach the apps**: the reducer needs planting_dekad and the six WRSI/WSI
stage bands.

**Yield is not reportable until a ceiling is fitted.** Every product starts on the uncalibrated
default from its parameter module, and the asset property `ym_calibrated` records which state it
is in.
"""
import argparse, csv, os, sys

H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(H)
sys.path.insert(0, ROOT); sys.path.insert(0, H)
from src import utils                                                 # noqa: E402
import ctm_mask as CTM                                                # noqa: E402
import irrigation_exposure as IRR                                     # noqa: E402
from params import get, CROPS                                         # noqa: E402

YEAR = 2024
CALENDAR = f"{H}/config/season_calendar_wtm.csv"
EE_PROJECT = os.environ.get("EE_PROJECT", "ee-manzikye")
# Seasons where green-up detection is unreliable and onset is taken from the CHIRPS rainfall rule.
RAINFALL_ANCHORED = {"Short rains", "2nd rains", "Season A", "Season B", "Vuli", "Deyr", "Belg",
                     "2nd"}

# IRRIGATED products get a FIXED planting dekad, because neither onset method can find them.
# Sudan's Shitwi wheat is scheme-irrigated winter wheat on the Nile and the Gezira, sown in
# November in the dry season. The CHIRPS 25/20 mm rule needs 25 mm in a dekad and Sudan gets
# essentially none in November, so the rainfall onset returned nothing and the first run produced
# an asset with 10,478 wheat mask pixels and ZERO valid ones. Green-up onset fares no better: it is
# gated to a rainfall-driven climatological onset that does not exist here.
#
# Planting on a scheme is scheduled, not rain-driven, so the start of the calendar's indicative
# window is the right anchor. It is an assumption about timing, and it is recorded on the asset.
#
# READ THE WATER BALANCE DIFFERENTLY FOR THESE. WRSI and S_water compare crop demand against
# RAINFALL. For a rainfed crop that is water stress. For an irrigated crop the shortfall is met by
# the scheme, so the deficit is not stress but the IRRIGATION REQUIREMENT - useful, and not the
# same quantity. CPI and yield for an irrigated product are therefore not comparable with a rainfed
# one and must not be pooled with them.
IRRIGATED = {("Sudan", "Shitwi")}


def ym_for(p, country, season):
    key = (country.replace(" ", "_"), season)
    if key in p.YM_CAL:
        return p.YM_CAL[key], True
    s = str(season).lower()
    short = "short" in s or "2nd" in s or "deyr" in s
    return (p.YM_SHORT_DEFAULT if short else p.YM_DEFAULT), False


def kc_for(p, row):
    """FAO-56 coefficients stretched to this product's own cycle length."""
    k = dict(p.KC)
    if row["season"] in RAINFALL_ANCHORED:
        k.update(p.KC_EARLY)
    cyc = int(row.get("cycle_dekads") or k["LGP_dekads"])
    if cyc != k["LGP_dekads"]:
        f = cyc / k["LGP_dekads"]
        ini = max(1, round(k["L_ini"] * f)); dev = max(1, round(k["L_dev"] * f))
        mid = max(1, round(k["L_mid"] * f)); late = max(1, cyc - ini - dev - mid)
        k.update(L_ini=ini, L_dev=dev, L_mid=mid, L_late=late,
                 LGP_dekads=ini + dev + mid + late)
    return k


def build_product_image(ee, row, soil, aoi=None, rich=False):
    from src import (s2_preprocess as S2, s1_preprocess as S1, fusion_phenometrics as FZ,
                     ltn as LTN, cpi as CPI, soil as SOIL, wrsi_feedback as WR,
                     zonal_aggregate as ZA)
    from src.wrsi_waterbalance import run_wrsi_staged
    from run import GAUL_NAME

    crop = row["crop"]; p = get(crop)
    country, season = row["country"], row["season"]
    if aoi is None:
        gname = GAUL_NAME.get(country) or GAUL_NAME.get(country.replace("_", " "), country)
        aoi = ZA.gaul_admin(ee, [gname], level=0).geometry()
    ss, se = utils.sos_window_dekads(row["sos_detection_window"])
    mask = CTM.crop_mask(ee, country, crop)
    k = kc_for(p, row); kc_use = {crop: k}
    rain = season in RAINFALL_ANCHORED
    irrigated = (country.replace(" ", "_"), season) in IRRIGATED
    wrsi_year, ss_use, se_use = YEAR, ss, se

    if irrigated:
        plant_dk, _ = utils.sos_window_dekads(row["indicative_planting_window"])
        planting = (ee.Image.constant(int(plant_dk)).rename("planting_dekad")
                    .updateMask(mask).toInt16())
    elif rain:
        pet = WR.pet_dekadal(ee, aoi, YEAR); ch = WR.chirps_dekadal(ee, aoi, YEAR)
        clim = WR.chirps_clim_dekadal(ee, aoi, range(ss, 37), range(1981, 2025))
        onset = WR.wrsi_onset(ee, ch, ss, se, pet_ic=pet).unmask(
            WR.wrsi_onset(ee, clim, ss, se, pet_ic=pet))
        planting = onset.updateMask(mask).toInt16()
    else:
        cross = ss > se
        byear = YEAR - 1 if cross else YEAR
        se_use = se + 36 if cross else se
        dks = range(ss, se_use + 1)
        s2 = S2.build_s2_dekadal(ee, aoi, byear, dekads=dks)
        s1 = S1.build_s1_dekadal(ee, aoi, byear, orbit="DESCENDING", dekads=dks)
        fpar = FZ.add_fpar_dekadal(ee, aoi, byear, dekads=dks)
        g = FZ.build_fused_greenness(ee, s2, s1, fpar)
        ltn = None if cross else LTN.build_ltn_prior(ee, aoi, ss, se)
        sos = FZ.detect_sos(ee, g, mask, ss, se_use, ltn_sos=ltn, ltn_pad=2)
        planting = sos.subtract(p.EMERGENCE_OFFSET).rename("planting_dekad").toInt16()
        wrsi_year = byear

    whc = SOIL.get_whc(ee, aoi, soil, root_depth_cm=int(k["root_depth_m"] * 100))
    d_veg = k["L_ini"] + k["L_dev"]; d_flo = d_veg + k["L_mid"]
    staged = run_wrsi_staged(ee, aoi, wrsi_year, planting, crop, kc_use, soil,
                             ss_use, se_use, whc_img=whc)
    Sw = CPI.s_water(ee, staged, ky=p.KY)
    Sh = CPI.s_heat(ee, aoi, wrsi_year, planting, d_veg, d_flo, ss_use, se_use,
                    tcap=p.HEAT_TCAP, k=p.HEAT_K)
    vss, vse = (1, max(6, se_use - 30)) if se_use > 36 else (ss_use, se_use)
    Sv = CPI.s_veg(ee, aoi, YEAR, vss, vse)
    ym, cal = ym_for(p, country, season)
    cpi_img, yld = CPI.cpi(ee, Sw, Sh, Sv, ym=ym)

    bands = [cpi_img, yld.multiply(100), Sw.multiply(100), Sh.multiply(100), Sv.multiply(100)]
    names = ["CPI", "yield_tha_x100", "S_water", "S_heat", "S_veg"]
    if rich:
        bands += [planting, staged["wrsi_veg"], staged["wrsi_flo"], staged["wrsi_grf"],
                  staged["wsi_veg"], staged["wsi_flo"], staged["wsi_grf"]]
        names += ["planting_dekad", "wrsi_veg", "wrsi_flo", "wrsi_grf",
                  "wsi_veg", "wsi_flo", "wsi_grf"]
    out = (ee.Image.cat(bands).updateMask(mask).toInt16().rename(names)
           .set({"crop": crop, "country": country, "season": season, "year": YEAR,
                 "ym_tha": ym, "ym_calibrated": cal, "cycle_dekads": k["LGP_dekads"],
                 "ky_flo": p.KY["flo"], "heat_tcap": p.HEAT_TCAP,
                 "root_depth_m": k["root_depth_m"],
                 "crop_calendar_source": row["crop_calendar_source"],
                 "onset_method": ("fixed (irrigated scheme)" if irrigated
                                  else "rainfall" if rain else "greenup"),
                 "irrigated": irrigated,
                 "water_balance_note": ("deficit is the IRRIGATION REQUIREMENT, not crop stress"
                                        if irrigated else "rainfed: deficit is crop water stress"),
                 "mask_asset": CTM.asset(country),
                 # Irrigation exposure of this (country, crop) from SPAM 2020, so a reader can tell
                 # from the asset alone whether CPI here is crop condition or irrigation demand.
                 **IRR.asset_properties(country, crop)}))
    return out, aoi, {"planting": planting, "staged": staged, "cpi": cpi_img, "yld": yld,
                      "mask": mask, "kc": k, "ss": ss_use, "se": se_use,
                      "onset_method": ("fixed" if irrigated else
                                       "rainfall" if rain else "greenup")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crop", default="all", choices=list(CROPS) + ["all", "wtm"])
    ap.add_argument("--submit", action="store_true")
    ap.add_argument("--rich", action="store_true")
    ap.add_argument("--country")
    a = ap.parse_args()

    rows = list(csv.DictReader(open(CALENDAR)))
    want = ["wheat", "teff", "millet"] if a.crop in ("all", "wtm") else [a.crop]
    rows = [r for r in rows if r["crop"] in want]
    if a.country:
        rows = [r for r in rows if r["country"] == a.country.replace(" ", "_")]

    print(f"{'SUBMIT' if a.submit else 'DRY-RUN'} · {len(rows)} products (250 m)")
    print(f"{'product':<28}{'onset':<9}{'cycle':>6}{'Ky flo':>8}{'Tcap':>6}{'root':>6}"
          f"{'Ym':>7}  mask")
    ee = utils.gee_init() if a.submit else None
    soil = utils.load_crop_coeffs()[1] if a.submit else None

    for r in rows:
        p = get(r["crop"]); k = kc_for(p, r); ym, cal = ym_for(p, r["country"], r["season"])
        pfx = r["crop"] + ("X" if a.rich else "")
        desc = f"{pfx}_{r['country']}_{r['season']}_{YEAR}".replace(" ", "")
        method = ("fixed-irr" if (r["country"], r["season"]) in IRRIGATED
                  else "rainfall" if r["season"] in RAINFALL_ANCHORED else "greenup")
        line = (f"{r['crop'] + ' ' + r['country'] + ' ' + r['season']:<28}{method:<9}"
                f"{k['LGP_dekads']:>6}{p.KY['flo']:>8.2f}{p.HEAT_TCAP:>6.0f}"
                f"{k['root_depth_m']:>6.1f}{ym:>7.2f}  {CTM.asset(r['country']).rsplit('/',1)[-1]}"
                + ("" if cal else "  [Ym UNCALIBRATED]"))
        if not a.submit:
            print("  would submit: " + line); continue
        asset = f"projects/{EE_PROJECT}/assets/{desc}"
        try:
            ee.data.getAsset(asset); print(f"  skip (exists): {desc}"); continue
        except Exception:
            pass
        out, aoi, _ = build_product_image(ee, r, soil, rich=a.rich)
        ee.batch.Export.image.toAsset(image=out.clip(aoi), description=desc, assetId=asset,
                                      region=aoi, scale=250, maxPixels=int(1e13)).start()
        print("  started     : " + line)

    if not a.submit:
        print("\n(dry run — add --submit; use --rich so the products can reach the apps)")


if __name__ == "__main__":
    main()
