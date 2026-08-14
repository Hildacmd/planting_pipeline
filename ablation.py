#!/usr/bin/env python3
"""Ablation: how do the new onset criteria change the start of season?

Measures each criterion where it actually acts:
  PLANTING (satellite SOS):  baseline (no prior)  vs  +LTN prior (phenology+rainfall gate)
  RAINFALL ONSET:            25/20 mm rule         vs  25/20 + P/PET>=0.5 gate

Exports small GAUL admin-1 tables to Drive (national/province modal dekad, mean, calendar
hit-rate/bias). Compare the CSVs to see the effect. Light + fast (8 provinces, coarse scale).

Run: EE_PROJECT=ee-manzikye python ablation.py --year 2024 --season "Long rains"
"""
import argparse, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from src import utils, s2_preprocess as S2, s1_preprocess as S1
from src import fusion_phenometrics as FZ, planting_date as PD, wrsi_feedback as WR
from src import zonal_aggregate as ZA, skill_stats as SK, ltn as LTN


def crop_mask(ee, crop):
    wc = ee.ImageCollection("ESA/WorldCereal/2021/MODELS/v100")
    prod = "maize" if crop == "maize" else "temporarycrops"
    return wc.filter(ee.Filter.eq("product", prod)).mosaic().select("classification").eq(100).selfMask()


def export_planting_skill(ee, planting, mask, admin, win_s, win_e, desc):
    metric = SK.skill_metric_image(ee, planting, mask, win_s, win_e)   # hit/bias/abserr
    dist = SK.describe_planting(ee, planting, mask, admin, scale=250)   # mode/p10/50/90/mean
    means = metric.reduceRegions(collection=admin, reducer=ee.Reducer.mean(), scale=250)
    join = ee.Join.inner("d", "m")
    filt = ee.Filter.equals(leftField="ADM1_NAME", rightField="ADM1_NAME")
    joined = join.apply(dist, means, filt).map(
        lambda f: ee.Feature(f.get("d")).copyProperties(ee.Feature(f.get("m"))))
    ee.batch.Export.table.toDrive(collection=joined, description=desc,
                                  folder="planting_outputs", fileFormat="CSV").start()
    print(f"  export: {desc}")


def export_onset(ee, onset, admin, desc):
    feats = onset.rename("onset_dekad").reduceRegions(
        collection=admin, reducer=ee.Reducer.mode().combine(ee.Reducer.mean(), sharedInputs=True),
        scale=250)
    ee.batch.Export.table.toDrive(collection=feats, description=desc,
                                  folder="planting_outputs", fileFormat="CSV").start()
    print(f"  export: {desc}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--country", default="Kenya"); ap.add_argument("--crop", default="maize")
    ap.add_argument("--season", default="Long rains")
    ap.add_argument("--pheno-cycle", type=int, default=1,
                    help="MCD12Q2 greenup cycle: 1 = main/long rains, 2 = short (second) rains")
    ap.add_argument("--ltn-mode", choices=["phenology_led", "rainfall_led"], default="phenology_led",
                    help="LTN prior mode; use rainfall_led for the short/second rains")
    ap.add_argument("--ltn-pad", type=int, default=2, help="dekads the SOS may fall from the prior")
    ap.add_argument("--calendar", default="config/season_calendar.csv")
    args = ap.parse_args()

    ee = utils.gee_init()
    row = next(r for r in utils.viable_products(utils.load_calendar(args.calendar))
               if r["country"] == args.country and r["crop"].lower() == args.crop.lower()
               and r["season"] == args.season)
    crop = args.crop
    sctag = args.season.replace(" ", "").replace("/", "")     # season tag for unique filenames
    aoi = ZA.gaul_admin(ee, [args.country], level=0).geometry()
    admin = ZA.gaul_admin(ee, [args.country], level=1)
    s, e = utils.sos_window_dekads(row["sos_detection_window"])
    win_s, win_e = utils.sos_window_dekads(row["indicative_planting_window"])
    print(f"{args.country} {crop} {args.season} | sos win {s}-{e} | cal win {win_s}-{win_e}")

    s2 = S2.build_s2_dekadal(ee, aoi, args.year)
    s1 = S1.build_s1_dekadal(ee, aoi, args.year)
    fpar = FZ.add_fpar_dekadal(ee, aoi, args.year)
    g_ic = FZ.build_fused_greenness(ee, s2, s1, fpar)
    mask = crop_mask(ee, crop)

    # --- PLANTING: baseline vs +LTN prior ---
    sos_base = FZ.detect_sos(ee, g_ic, mask, s, e, ltn_sos=None)
    plant_base = PD.sos_to_planting(ee, sos_base, crop)
    export_planting_skill(ee, plant_base, mask, admin, win_s, win_e,
                          f"ablation_planting_baseline_{sctag}_{args.year}")

    prior = LTN.build_ltn_prior(ee, aoi, s, e, cycle=args.pheno_cycle, mode=args.ltn_mode)
    sos_ltn = FZ.detect_sos(ee, g_ic, mask, s, e, ltn_sos=prior, ltn_pad=args.ltn_pad)
    plant_ltn = PD.sos_to_planting(ee, sos_ltn, crop)
    export_planting_skill(ee, plant_ltn, mask, admin, win_s, win_e,
                          f"ablation_planting_ltn_{sctag}_{args.year}")

    # --- ONSET: 25/20 vs +P/PET ---
    chirps = WR.chirps_dekadal(ee, aoi, args.year)
    export_onset(ee, WR.wrsi_onset(ee, chirps, s, e), admin, f"ablation_onset_2520_{sctag}_{args.year}")
    pet = WR.pet_dekadal(ee, aoi, args.year)
    export_onset(ee, WR.wrsi_onset(ee, chirps, s, e, pet_ic=pet, ppet_thresh=0.5), admin,
                 f"ablation_onset_ppet_{sctag}_{args.year}")

    print("4 ablation exports started -> Drive/planting_outputs (compare when they land)")


if __name__ == "__main__":
    main()
