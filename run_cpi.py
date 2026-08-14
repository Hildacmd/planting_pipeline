#!/usr/bin/env python3
"""Stage-resolved WRSI/WSI + Crop Performance Index + yield for the MAIN seasons —
Kenya Long rains and Ethiopia Meher. Green-up-led planting (cue fusion + LTN + detect_sos),
medium-maturity maize. One export carries both the stage-monitor and CPI bands.

Run:  EE_PROJECT=ee-manzikye python run_cpi.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from src import (utils, s2_preprocess as S2, s1_preprocess as S1, fusion_phenometrics as FZ,
                 ltn as LTN, planting_date as PD, zonal_aggregate as ZA, cpi as CPI, soil as SOIL,
                 wrsi_feedback as WR)

DRYSPELL = os.environ.get("DRYSPELL_GATE", "1") != "0"   # inception-report false-start rejection (green-up seasons)
from src.wrsi_waterbalance import run_wrsi_staged
from run import crop_mask_image, GAUL_NAME

YEAR = 2024
YM_MAIN = 6.0                                   # medium/long maize reference potential (t/ha)
VEG_INDEX = os.environ.get("VEG_INDEX", "ndvi") # 'ndvi' (VCI) | 'fpar' (zFPAR, ASAP-aligned)
JOBS = [("Kenya", "Long rains", "Longrains"), ("Ethiopia", "Meher", "Meher")]
BANDS = ["wrsi_veg", "wrsi_flo", "wrsi_grf", "wsi_veg", "wsi_flo", "wsi_grf",
         "CPI", "yield_tha_x100", "S_water", "S_heat", "S_veg"]


def main():
    ee = utils.gee_init()
    kc, soil = utils.load_crop_coeffs()
    p = kc["maize"]; d_veg = p["L_ini"] + p["L_dev"]; d_flo = d_veg + p["L_mid"]   # medium maize: 7, 10
    whc = SOIL.get_whc(ee, None, soil, root_depth_cm=int(p.get("root_depth_m", 1.0) * 100))  # Saxton/SoilGrids
    rows = {(r["country"], r["season"]): r for r in utils.viable_products(utils.load_calendar("config/season_calendar.csv"))
            if r["crop"].lower() == "maize"}
    for country, season, tag in JOBS:
        r = rows.get((country, season))
        if not r:
            print(f"  [skip] no calendar row for {country} {season}"); continue
        aoi = ZA.gaul_admin(ee, [GAUL_NAME[country]], level=0).geometry()
        ss, se = utils.sos_window_dekads(r["sos_detection_window"])
        s2 = S2.build_s2_dekadal(ee, aoi, YEAR)
        s1 = S1.build_s1_dekadal(ee, aoi, YEAR, orbit="DESCENDING")
        fpar = FZ.add_fpar_dekadal(ee, aoi, YEAR)
        g = FZ.build_fused_greenness(ee, s2, s1, fpar)               # cue fusion (production)
        mask = crop_mask_image(ee, country, "maize", None)
        ltn = LTN.build_ltn_prior(ee, aoi, ss, se)
        sos = FZ.detect_sos(ee, g, mask, ss, se, ltn_sos=ltn, ltn_pad=2)
        planting = PD.sos_to_planting(ee, sos, "maize").toInt16()
        if DRYSPELL:                                                  # inception-report false-start gate
            ok = WR.dryspell_false_start(ee, aoi, planting, YEAR, dk_lo=ss, dk_hi=se + 2)
            planting = planting.updateMask(ok)                       # reject onsets a >7-day dry spell follows

        staged = run_wrsi_staged(ee, aoi, YEAR, planting, "maize", kc, soil, ss, se, whc_img=whc)
        Sw = CPI.s_water(ee, staged)
        Sh = CPI.s_heat(ee, aoi, YEAR, planting, d_veg, d_flo, ss, se)
        Sv = CPI.s_veg(ee, aoi, YEAR, ss, se, source=VEG_INDEX)
        cpi_img, yld = CPI.cpi(ee, Sw, Sh, Sv, ym=YM_MAIN)
        out = ee.Image.cat([staged["wrsi_veg"], staged["wrsi_flo"], staged["wrsi_grf"],
                            staged["wsi_veg"], staged["wsi_flo"], staged["wsi_grf"],
                            cpi_img, yld.multiply(100), Sw.multiply(100), Sh.multiply(100),
                            Sv.multiply(100)]).updateMask(mask).toInt16().rename(BANDS)
        desc = f"cpi_{country}_{tag}_2024"
        if os.environ.get("TO_ASSET"):
            ee.batch.Export.image.toAsset(image=out.clip(aoi), description=desc,
                assetId=f"projects/ee-manzikye/assets/{desc}", region=aoi, scale=250,
                maxPixels=int(1e13)).start()
        else:
            ee.batch.Export.image.toDrive(image=out.clip(aoi), description=desc, folder="planting_outputs",
                region=aoi, scale=250, crs="EPSG:4326", maxPixels=int(1e13)).start()
        print(f"  export started: {desc}  ({'asset' if os.environ.get('TO_ASSET') else 'drive'}; stage WRSI/WSI + CPI + yield)")


if __name__ == "__main__":
    main()
