#!/usr/bin/env python3
"""Orchestrator: crop-specific dekadal planting-window estimation for the 11 GHA countries.

Loops (country x crop x season) over viable products in config/season_calendar.csv and, for
each, runs: S2 red-edge + S1 SAR + FPAR fusion -> SOS (LTN-constrained) -> planting dekad
-> WRSI onset cross-check -> zonal admin aggregation -> export.

Run:  EE_PROJECT=your-gee-project  python run.py --year 2024 --country Ethiopia --crop teff
Requires: earthengine-api authenticated; crop-specific masks as GEE assets (see --mask-asset).
"""
import argparse, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from src import utils, s2_preprocess as S2, s1_preprocess as S1
from src import fusion_phenometrics as FZ, planting_date as PD, wrsi_feedback as WR
from src import zonal_aggregate as ZA, soil as SOIL, ltn as LTN

GAUL_NAME = {  # config country -> GAUL ADM0_NAME
 "Ethiopia":"Ethiopia","Kenya":"Kenya","Uganda":"Uganda","Tanzania":"United Republic of Tanzania",
 "Rwanda":"Rwanda","Burundi":"Burundi","South_Sudan":"South Sudan","Sudan":"Sudan",
 "Somalia":"Somalia","Eritrea":"Eritrea","Djibouti":"Djibouti"}

def crop_mask_image(ee, country, crop, mask_asset):
    """Load the crop-specific mask (1=crop). Falls back to WorldCereal maize / cropland."""
    if mask_asset:
        return ee.Image(mask_asset).selfMask()
    wc = ee.ImageCollection("ESA/WorldCereal/2021/MODELS/v100")
    if crop == "maize":
        return wc.filter(ee.Filter.eq("product","maize")).mosaic().select("classification").eq(100).selfMask()
    # teff/wheat: no global class -> use temporary-crops extent as placeholder stratum
    return wc.filter(ee.Filter.eq("product","temporarycrops")).mosaic().select("classification").eq(100).selfMask()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--country"); ap.add_argument("--crop")
    ap.add_argument("--season", default=None, help="filter to one season, e.g. 'Short rains'")
    ap.add_argument("--mask-asset", default=None)
    ap.add_argument("--orbit", default="DESCENDING")
    ap.add_argument("--calendar", default="config/season_calendar.csv")
    # ---- LTN (long-term-normal) constraints to sharpen SOS ----
    ap.add_argument("--no-ltn", dest="use_ltn", action="store_false", default=True,
                    help="disable the phenology/rainfall/temperature LTN constraints")
    ap.add_argument("--ltn-pad", type=int, default=2,
                    help="dekads around the phenology normal that SOS may fall within")
    ap.add_argument("--pheno-asset", default=None,
                    help="optional eMODIS/other phenology asset (in dekads) to replace MCD12Q2")
    ap.add_argument("--pheno-cycle", type=int, default=1,
                    help="MCD12Q2 greenup cycle: 1=main season, 2=second (bimodal) season")
    # ---- FEWS onset: add the P/PET >= threshold gate to the 25/20 mm rule ----
    ap.add_argument("--no-ppet-onset", dest="ppet_onset", action="store_false", default=True,
                    help="disable the P/PET agroclimatic gate (keep 25/20 mm rainfall rule only)")
    ap.add_argument("--ppet-thresh", type=float, default=0.5,
                    help="minimum precipitation/PET ratio for onset (FEWS convention = 0.5)")
    # ---- export controls ----
    ap.add_argument("--wrsi-scale", type=int, default=250,
                    help="WRSI export scale (m); its climate inputs are 5-11 km so 250 m is ample")
    ap.add_argument("--no-planting-export", dest="planting_export", action="store_false", default=True,
                    help="export only WRSI (skip planting + zonal) - e.g. to re-run just WRSI")
    ap.add_argument("--fusion", choices=["cue", "estarfm"], default="cue",
                    help="greenness fusion: 'cue' (default, light) or 'estarfm' (ubESTARFM)")
    ap.add_argument("--planting-scale", type=int, default=10,
                    help="planting-dekad export scale (m); use 250 for ubESTARFM (MODIS-native)")
    ap.add_argument("--tag", default=None, help="suffix to distinguish fusion variants in Drive")
    args = ap.parse_args()

    ee = utils.gee_init()
    kc_cfg, soil_cfg = utils.load_crop_coeffs()
    rows = list(utils.viable_products(utils.load_calendar(args.calendar)))
    if args.country: rows = [r for r in rows if r["country"] == args.country]
    if args.crop:    rows = [r for r in rows if r["crop"].lower() == args.crop.lower()]
    if args.season: rows = [r for r in rows if r["season"] == args.season]
    if not rows:
        print("No viable (country,crop,season) products match filters."); return

    for r in rows:
        c, crop, season = r["country"], r["crop"].lower(), r["season"]
        print(f"\n=== {c} | {crop} | {season} | plant {r['indicative_planting_window']} ===")
        adm0 = GAUL_NAME[c]
        aoi = ZA.gaul_admin(ee, [adm0], level=0).geometry()
        sos_start, sos_end = utils.sos_window_dekads(r["sos_detection_window"])

        s2_ic  = S2.build_s2_dekadal(ee, aoi, args.year)
        s1_ic  = S1.build_s1_dekadal(ee, aoi, args.year, orbit=args.orbit)
        fpar_ic= FZ.add_fpar_dekadal(ee, aoi, args.year)
        if args.fusion == "estarfm":
            from src import estarfm as EF          # NDRE+FPAR primary, ubESTARFM NDVI gap-fill, SAR last
            g_ic = EF.build_fused_greenness_enhanced(ee, s2_ic, s1_ic, fpar_ic, aoi, args.year,
                                                     sos_start, sos_end, fine_scale=args.planting_scale)
        else:
            g_ic = FZ.build_fused_greenness(ee, s2_ic, s1_ic, fpar_ic)   # default cue fusion

        mask = crop_mask_image(ee, c, crop, args.mask_asset)
        # LTN prior: phenology (MCD12Q2 or eMODIS asset) fused with CHIRPS rainfall-onset normal
        ltn = None
        if args.use_ltn:
            ltn = LTN.build_ltn_prior(ee, aoi, sos_start, sos_end,
                                      cycle=args.pheno_cycle, greenup_asset=args.pheno_asset)

        sos = FZ.detect_sos(ee, g_ic, mask, sos_start, sos_end,
                            ltn_sos=ltn, ltn_pad=args.ltn_pad)
        # planting offset: temperature-LTN-varying where LTN is on, else fixed crop offset
        if args.use_ltn:
            tnorm = LTN.temperature_ltn_C(ee, aoi)
            planting = LTN.sos_to_planting_thermal(
                ee, sos, PD.EMERGENCE_OFFSET.get(crop, 1), tnorm)
        else:
            planting = PD.sos_to_planting(ee, sos, crop)
        if os.environ.get("DRYSPELL_GATE", "1") != "0":              # inception-report 5+7 false-start gate
            _ok = WR.dryspell_false_start(ee, aoi, planting, args.year, dk_lo=sos_start, dk_hi=sos_end + 2)
            planting = planting.updateMask(_ok)

        # WRSI rainfall onset cross-check: FEWS 25/20 mm rule (+ optional P/PET >= thresh gate)
        chirps = WR.chirps_dekadal(ee, aoi, args.year)
        pet    = WR.pet_dekadal(ee, aoi, args.year) if args.ppet_onset else None
        onset  = WR.wrsi_onset(ee, chirps, sos_start, sos_end,
                               pet_ic=pet, ppet_thresh=args.ppet_thresh)

        # spatial WHC from OpenLandMap (field capacity - wilting point, over root zone)
        whc_img = None
        if soil_cfg.get("use_spatial_whc"):
            rd_cm = int(kc_cfg[crop].get("root_depth_m", 1.0) * 100)
            whc_img = SOIL.get_whc(ee, aoi, soil_cfg, root_depth_cm=rd_cm)  # Saxton/SoilGrids default

        # FULL FAO-56/33 WRSI in GEE, started from the crop-specific planting dekad
        wrsi = WR.run_wrsi(ee, aoi, args.year, planting, crop, kc_cfg, soil_cfg,
                           sos_start, sos_end, whc_img=whc_img)

        # zonal admin-1 planting window
        adm1 = ZA.gaul_admin(ee, [adm0], level=1)
        zstats = ZA.zonal_planting_stats(ee, planting, adm1)

        desc = f"planting_{c}_{crop}_{season}_{args.year}".replace(" ","")
        if args.tag: desc += "_" + args.tag           # distinguish fusion variants in Drive
        started = []
        if args.planting_export:
            PD.export_planting(ee, planting, aoi, desc, scale=args.planting_scale)
            ee.batch.Export.table.toDrive(collection=zstats,
                description=desc+"_zonal", folder="planting_outputs",
                fileFormat="CSV").start()
            started.append(f"{desc} (planting @ {args.planting_scale} m) + zonal CSV")
        # WRSI + deficit + class as a multiband raster (climate-driven -> coarse scale is enough)
        wrsi_stack = (wrsi["WRSI"].addBands(wrsi["deficit_mm"])
                        .addBands(wrsi["wrsi_class"]))
        PD.export_planting(ee, wrsi_stack, aoi, desc.replace("planting_","wrsi_"),
                           scale=args.wrsi_scale)
        started.append(f"wrsi_{desc[9:]} @ {args.wrsi_scale} m")
        print("  exports started: " + " + ".join(started))

if __name__ == "__main__":
    main()
