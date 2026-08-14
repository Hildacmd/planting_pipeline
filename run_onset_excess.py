#!/usr/bin/env python3
"""Onset false-start (5+7 gate) + excess/waterlogging diagnostics — green-up seasons (Kenya Long
rains, Ethiopia Meher), 250 m. One export per season carrying:
  false_start   0/1  — inception-report 5+7 gate rejects this green-up onset (1 = false start)
  waterlog_idx  0-100 — stage-weighted waterlogging index (establishment-worst)
  spi3_wet      0/1  — SPI-3 >= +1.5 (very wet) over the season
  onset_acc_mm  mm   — rain in the first 5 days after onset (the germination trigger)
Masked to maize. Exports to Drive (planting_outputs) and, with TO_ASSET=1, to EE assets.

Run:  EE_PROJECT=ee-manzikye python run_onset_excess.py
      TO_ASSET=1 EE_PROJECT=ee-manzikye python run_onset_excess.py     # also -> assets
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from src import (utils, s2_preprocess as S2, s1_preprocess as S1, fusion_phenometrics as FZ,
                 ltn as LTN, planting_date as PD, zonal_aggregate as ZA,
                 wrsi_feedback as WR, excess as EX, soil as SOIL)
from run import crop_mask_image, GAUL_NAME

YEAR = 2024
# season -> (tag, gadm country, SPI-3 end month for the wet anomaly)
JOBS = [("Kenya", "Long rains", "Longrains", 5), ("Ethiopia", "Meher", "Meher", 9)]
MED = {"d_veg": 7, "d_flo": 10, "lgp": 12}                      # medium maize stage ends (dekads)
BANDS = ["false_start", "waterlog_idx", "spi3_wet", "onset_acc_mm"]


def main():
    ee = utils.gee_init()
    hy = SOIL.build_hydro_mm(ee, root_depth_cm=100)                 # FC/SAT/tau for the aeration balance
    FC, SAT, TAU = hy["FC_mm"], hy["SAT_mm"], hy["tau"]
    rows = {(r["country"], r["season"]): r for r in utils.viable_products(utils.load_calendar("config/season_calendar.csv"))
            if r["crop"].lower() == "maize"}
    for country, season, tag, spi_end in JOBS:
        r = rows.get((country, season))
        if not r:
            print(f"  [skip] no calendar row for {country} {season}"); continue
        aoi = ZA.gaul_admin(ee, [GAUL_NAME[country]], level=0).geometry()
        ss, se = utils.sos_window_dekads(r["sos_detection_window"])
        s2 = S2.build_s2_dekadal(ee, aoi, YEAR); s1 = S1.build_s1_dekadal(ee, aoi, YEAR, orbit="DESCENDING")
        fpar = FZ.add_fpar_dekadal(ee, aoi, YEAR)
        g = FZ.build_fused_greenness(ee, s2, s1, fpar)
        mask = crop_mask_image(ee, country, "maize", None)
        ltn = LTN.build_ltn_prior(ee, aoi, ss, se)
        sos = FZ.detect_sos(ee, g, mask, ss, se, ltn_sos=ltn, ltn_pad=2)
        planting = PD.sos_to_planting(ee, sos, "maize").toInt16()      # UNGATED green-up onset

        ok  = WR.dryspell_false_start(ee, aoi, planting, YEAR, dk_lo=ss, dk_hi=se + 2)   # 5+7 gate
        fs  = ee.Image(1).subtract(ok).rename("false_start")                            # 1 = rejected
        acc = WR.onset_accum_mm(ee, aoi, planting, YEAR, ss, se + 2, trigger_days=5).rename("onset_acc_mm")
        wl  = EX.aeration_stress_index(ee, aoi, planting, YEAR, MED["d_veg"], MED["d_flo"], MED["lgp"], ss, se, FC, SAT, TAU)
        wet = EX.spi3_wet(ee, aoi, YEAR, spi_end).rename("spi3_wet")

        out = ee.Image.cat([fs, wl, wet, acc]).updateMask(mask).updateMask(planting.mask()).toInt16().rename(BANDS)
        desc = f"onsetexcess_{country}_{tag}_2024"
        if os.environ.get("TO_ASSET"):
            ee.batch.Export.image.toAsset(image=out.clip(aoi), description=desc,
                assetId=f"projects/ee-manzikye/assets/{desc}", region=aoi, scale=250, maxPixels=int(1e13)).start()
        else:
            ee.batch.Export.image.toDrive(image=out.clip(aoi), description=desc, folder="planting_outputs",
                region=aoi, scale=250, crs="EPSG:4326", maxPixels=int(1e13)).start()
        print(f"  export started: {desc}  ({'asset' if os.environ.get('TO_ASSET') else 'drive'}; false_start + waterlog + spi_wet)")


if __name__ == "__main__":
    main()
