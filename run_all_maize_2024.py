#!/usr/bin/env python3
"""Fast-track Phase 1: submit all 11-country 2024 maize CPI/yield products as GEE batch asset
exports, staged by viability. DRY-RUN by default (prints the plan); add --submit to fire.

  python run_all_maize_2024.py --stage high                      # dry-run: list High-viability
  EE_PROJECT=ee-manzikye python run_all_maize_2024.py --stage high --submit    # fire stage 1
  EE_PROJECT=ee-manzikye python run_all_maize_2024.py --stage medium --submit  # then stage 2

Each product -> asset  cpi_<Country>_<Season>_2024  (250 m; bands CPI, yield_tha_x100, S_water,
S_heat, S_veg). Onset: green-up cue-fusion for main seasons, rainfall-anchored for short/second
seasons (green-up fails there; see WORKFLOW_SHORTRAINS). Yield uses the AEZ-aware calibrated Ym
(CPI.ym_img_for). Kenya Long/Short and Ethiopia Meher already exist; re-submitting overwrites intent
only if you export to the same id.
"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(__file__))
from src import utils

YEAR = 2024
# secondary / short seasons -> rainfall-anchored onset (green-up unreliable, WORKFLOW_SHORTRAINS).
# "Season A" (Rwanda/Burundi main season) is added because those persistently-cloudy equatorial
# highlands defeat green-up onset (Rwanda A: 64 planting px vs 3365 from rainfall onset over maize).
RAINFALL_ANCHORED = {"Short rains", "2nd rains", "Season A", "Season B", "Vuli", "Deyr", "Belg"}
EARLY = {"LGP_dekads": 9, "L_ini": 2, "L_dev": 3, "L_mid": 2, "L_late": 2}   # short-duration maize
RICH = False   # --rich: also emit planting_dekad + 6 WRSI/WSI stage bands to cpiX_* (for app full panels)


def build_product_image(ee, r, kc, soil, aoi=None, rich=False):
    """Build the CPI/yield/stress output image for one calendar row (any GHA country/season).
    Handles rainfall-anchored short/second seasons and cross-year main seasons (ss>se, e.g. Msimu).
    Returns (out, aoi, meta). `meta` carries the intermediates (planting, staged, Sw/Sh/Sv) so a
    notebook can display each module's layer. Pass `aoi` to run on a test box; default = whole country.
    Set rich=True to append planting_dekad + the 6 WRSI/WSI stage bands (app full panels)."""
    from src import (s2_preprocess as S2, s1_preprocess as S1, fusion_phenometrics as FZ,
                     ltn as LTN, planting_date as PD, cpi as CPI, soil as SOIL,
                     wrsi_feedback as WR, zonal_aggregate as ZA)
    from run import crop_mask_image, GAUL_NAME
    country, season = r["country"], r["season"]
    if aoi is None:
        gname = GAUL_NAME.get(country) or GAUL_NAME.get(country.replace(" ", "_"), country)
        aoi = ZA.gaul_admin(ee, [gname], level=0).geometry()
    ss, se = utils.sos_window_dekads(r["sos_detection_window"])
    mask = crop_mask_image(ee, country, "maize", None)
    rain = season in RAINFALL_ANCHORED
    wrsi_year, ss_use, se_use = YEAR, ss, se
    if rain:
        pet = WR.pet_dekadal(ee, aoi, YEAR); ch = WR.chirps_dekadal(ee, aoi, YEAR)
        clim = WR.chirps_clim_dekadal(ee, aoi, range(ss, 37), range(1981, 2025))
        onset = WR.wrsi_onset(ee, ch, ss, se, pet_ic=pet).unmask(WR.wrsi_onset(ee, clim, ss, se, pet_ic=pet))
        planting = onset.updateMask(mask).toInt16()
        kc_use = {**kc, "maize_use": {**kc["maize"], **EARLY}}; ck = "maize_use"
    else:
        # cross-year main season (ss > se, e.g. Msimu Dec->Feb): build prior-year Nov .. current Feb
        # with dekads extended past 36 (they wrap into YEAR); run the balance from YEAR-1.
        cross = ss > se
        byear = YEAR - 1 if cross else YEAR
        se_use = se + 36 if cross else se
        dks = range(ss, se_use + 1)
        s2 = S2.build_s2_dekadal(ee, aoi, byear, dekads=dks)
        s1 = S1.build_s1_dekadal(ee, aoi, byear, orbit="DESCENDING", dekads=dks)
        fpar = FZ.add_fpar_dekadal(ee, aoi, byear, dekads=dks)
        g = FZ.build_fused_greenness(ee, s2, s1, fpar)
        ltn = None if cross else LTN.build_ltn_prior(ee, aoi, ss, se)   # MCD12Q2 prior isn't wrap-safe
        sos = FZ.detect_sos(ee, g, mask, ss, se_use, ltn_sos=ltn, ltn_pad=2)
        planting = PD.sos_to_planting(ee, sos, "maize").toInt16()
        kc_use = {**kc, "maize_use": kc["maize"]}; ck = "maize_use"
        wrsi_year = byear
    whc = SOIL.get_whc(ee, aoi, soil, root_depth_cm=int(kc["maize"].get("root_depth_m", 1.0) * 100))
    p = kc_use[ck]; d_veg = p["L_ini"] + p["L_dev"]; d_flo = d_veg + p["L_mid"]
    staged = run_wrsi_staged(ee, aoi, wrsi_year, planting, ck, kc_use, soil, ss_use, se_use, whc_img=whc)
    Sw = CPI.s_water(ee, staged); Sh = CPI.s_heat(ee, aoi, wrsi_year, planting, d_veg, d_flo, ss_use, se_use)
    vss, vse = (1, max(6, se_use - 30)) if se_use > 36 else (ss_use, se_use)   # veg peak lands in YEAR
    Sv = CPI.s_veg(ee, aoi, YEAR, vss, vse)
    cpi_img, yld = CPI.cpi(ee, Sw, Sh, Sv, ym=CPI.ym_img_for(ee, aoi, country, season))
    bands = [cpi_img, yld.multiply(100), Sw.multiply(100), Sh.multiply(100), Sv.multiply(100)]
    names = ["CPI", "yield_tha_x100", "S_water", "S_heat", "S_veg"]
    if rich:   # planting_dekad + per-stage WRSI/WSI (0-100) for the app's full planting + WRSI-stage panels
        bands += [planting, staged["wrsi_veg"], staged["wrsi_flo"], staged["wrsi_grf"],
                  staged["wsi_veg"], staged["wsi_flo"], staged["wsi_grf"]]
        names += ["planting_dekad", "wrsi_veg", "wrsi_flo", "wrsi_grf", "wsi_veg", "wsi_flo", "wsi_grf"]
    out = ee.Image.cat(bands).updateMask(mask).toInt16().rename(names)
    meta = {"planting": planting, "staged": staged, "Sw": Sw, "Sh": Sh, "Sv": Sv,
            "cpi": cpi_img, "yld": yld, "mask": mask, "ss": ss_use, "se": se_use, "onset_method": "rainfall" if rain else "greenup"}
    return out, aoi, meta


def process_and_submit(ee, r, kc, soil):
    country, season = r["country"], r["season"]
    out, aoi, _ = build_product_image(ee, r, kc, soil, rich=RICH)
    pfx = "cpiX" if RICH else "cpi"
    desc = f"{pfx}_{country}_{season}_{YEAR}".replace(" ", "")
    ee.batch.Export.image.toAsset(image=out.clip(aoi), description=desc,
        assetId=f"projects/ee-manzikye/assets/{desc}", region=aoi, scale=250, maxPixels=int(1e13)).start()
    return desc


def main():
    from src.wrsi_waterbalance import run_wrsi_staged as _  # noqa (import check)
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="high", choices=["high", "medium", "all"])
    ap.add_argument("--submit", action="store_true", help="actually fire the batch exports")
    ap.add_argument("--rich", action="store_true",
                    help="emit planting_dekad + 6 WRSI/WSI stage bands to cpiX_* (app full panels)")
    a = ap.parse_args()
    global RICH; RICH = a.rich
    # anchors already carry fully-reduced + validated admin CSVs; don't re-export/overwrite them
    ANCHORS = {("Kenya", "Long rains"), ("Kenya", "Short rains"), ("Ethiopia", "Meher")}
    rows = [r for r in utils.viable_products(utils.load_calendar("config/season_calendar.csv"))
            if r["crop"].lower() == "maize"]
    want = {"high": ["High"], "medium": ["Medium"], "all": ["High", "Medium"]}[a.stage]
    rows = [r for r in rows if r["crop_viability"] in want]
    print(f"{'SUBMIT' if a.submit else 'DRY-RUN'} · stage={a.stage} · {len(rows)} maize products (250 m)")
    ee = utils.gee_init() if a.submit else None
    kc, soil = utils.load_crop_coeffs() if a.submit else (None, None)
    inflight = set()
    if a.submit:
        for o in ee.data.listOperations():
            m = o.get("metadata", {})
            if m.get("state") in ("PENDING", "RUNNING"):
                inflight.add(m.get("description"))
    pfx = "cpiX" if RICH else "cpi"
    for r in rows:
        if RICH and (r["country"], r["season"]) in ANCHORS:
            print(f"  skip (anchor, keep validated CSV): {r['country']} {r['season']}"); continue
        method = "rainfall" if r["season"] in RAINFALL_ANCHORED else "greenup"
        desc = f"{pfx}_{r['country']}_{r['season']}_{YEAR}".replace(" ", "")
        if a.submit:
            exists = False
            try:
                ee.data.getAsset(f"projects/ee-manzikye/assets/{desc}"); exists = True
            except Exception:
                pass
            if exists or desc in inflight:
                print(f"  skip ({'asset exists' if exists else 'task in-flight'}): {desc}"); continue
            desc = process_and_submit(ee, r, kc, soil)
            print(f"  started : {desc:38s} onset={method}  viability={r['crop_viability']}")
        else:
            print(f"  would submit: {desc:38s} onset={method}  viability={r['crop_viability']}")
    if not a.submit:
        print("\n(dry-run — add --submit to fire; then run --stage medium --submit for stage 2)")


# late import so dry-run doesn't need earthengine
from src.wrsi_waterbalance import run_wrsi_staged  # noqa: E402

if __name__ == "__main__":
    main()
