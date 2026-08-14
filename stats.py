#!/usr/bin/env python3
"""Generate statistics + skill scores for the planting-window pipeline.

For each viable (country x crop x season) product it computes the planting dekad (and,
unless --no-wrsi, the full WRSI), then four metric families (see src/skill_stats.py):
descriptive distribution, signal strength, skill vs the FEWS/FAO calendar window, and
WRSI performance. Results are:
  - exported to Google Drive as an admin-1 CSV  (planting_outputs/<desc>_stats.csv)
  - printed as a national summary, and saved locally to outputs/<desc>_national.csv

Run:
  EE_PROJECT=your-project python stats.py --year 2024 --country Kenya --crop maize
  EE_PROJECT=your-project python stats.py --year 2024 --country Kenya --crop maize --no-wrsi
  EE_PROJECT=your-project python stats.py --year 2024 --national-only --scale 500
"""
import argparse, sys, os, csv
sys.path.insert(0, os.path.dirname(__file__))
from src import utils, s2_preprocess as S2, s1_preprocess as S1
from src import fusion_phenometrics as FZ, planting_date as PD, wrsi_feedback as WR
from src import zonal_aggregate as ZA, soil as SOIL, skill_stats as SK

GAUL_NAME = {
 "Ethiopia":"Ethiopia","Kenya":"Kenya","Uganda":"Uganda","Tanzania":"United Republic of Tanzania",
 "Rwanda":"Rwanda","Burundi":"Burundi","South_Sudan":"South Sudan","Sudan":"Sudan",
 "Somalia":"Somalia","Eritrea":"Eritrea","Djibouti":"Djibouti"}


def crop_mask_image(ee, crop, mask_asset):
    if mask_asset:
        return ee.Image(mask_asset).selfMask()
    wc = ee.ImageCollection("ESA/WorldCereal/2021/MODELS/v100")
    prod = "maize" if crop == "maize" else "temporarycrops"
    return wc.filter(ee.Filter.eq("product", prod)).mosaic().select("classification").eq(100).selfMask()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--country"); ap.add_argument("--crop")
    ap.add_argument("--mask-asset", default=None)
    ap.add_argument("--orbit", default="DESCENDING")
    ap.add_argument("--calendar", default="config/season_calendar.csv")
    ap.add_argument("--no-wrsi", action="store_true", help="skip heavy WRSI (faster, less quota)")
    ap.add_argument("--national-only", action="store_true", help="export only the national row, not admin-1")
    ap.add_argument("--print-national", action="store_true",
                    help="also try an interactive getInfo print (coarse; may hit memory limit)")
    ap.add_argument("--scale", type=int, default=None, help="reduction scale (m); default 100 admin / 250 national")
    args = ap.parse_args()

    ee = utils.gee_init()
    kc_cfg, soil_cfg = utils.load_crop_coeffs()
    rows = list(utils.viable_products(utils.load_calendar(args.calendar)))
    if args.country: rows = [r for r in rows if r["country"] == args.country]
    if args.crop:    rows = [r for r in rows if r["crop"].lower() == args.crop.lower()]
    if not rows:
        print("No viable (country,crop,season) products match filters."); return

    os.makedirs("outputs", exist_ok=True)
    adm_scale = args.scale or 100
    nat_scale = args.scale or 250

    for r in rows:
        c, crop, season = r["country"], r["crop"].lower(), r["season"]
        desc = f"planting_{c}_{crop}_{season}_{args.year}".replace(" ", "")
        print(f"\n=== {c} | {crop} | {season} | plant {r['indicative_planting_window']} ===")
        adm0 = GAUL_NAME[c]
        aoi = ZA.gaul_admin(ee, [adm0], level=0).geometry()
        sos_start, sos_end = utils.sos_window_dekads(r["sos_detection_window"])
        # FEWS/FAO indicative PLANTING window -> benchmark for skill (same 4-part token format)
        win_start, win_end = utils.sos_window_dekads(r["indicative_planting_window"])
        centre = (win_start + win_end) / 2.0
        print(f"    calendar planting window: dekads {win_start}-{win_end} (centre {centre:g})")

        s2_ic  = S2.build_s2_dekadal(ee, aoi, args.year)
        s1_ic  = S1.build_s1_dekadal(ee, aoi, args.year, orbit=args.orbit)
        fpar_ic= FZ.add_fpar_dekadal(ee, aoi, args.year)
        g_ic   = FZ.build_fused_greenness(ee, s2_ic, s1_ic, fpar_ic)
        mask   = crop_mask_image(ee, crop, args.mask_asset)
        sos    = FZ.detect_sos(ee, g_ic, mask, sos_start, sos_end, ltn_sos=None)
        planting = PD.sos_to_planting(ee, sos, crop)
        if os.environ.get("DRYSPELL_GATE", "1") != "0":              # inception-report 5+7 false-start gate
            _ok = WR.dryspell_false_start(ee, aoi, planting, args.year, dk_lo=sos_start, dk_hi=sos_end + 2)
            planting = planting.updateMask(_ok)

        wrsi_img = deficit_img = wrsi_class_img = None
        if not args.no_wrsi:
            whc_img = None
            if soil_cfg.get("use_spatial_whc"):
                rd_cm = int(kc_cfg[crop].get("root_depth_m", 1.0) * 100)
                whc_img = SOIL.get_whc(ee, aoi, soil_cfg, root_depth_cm=rd_cm)  # Saxton/SoilGrids default
            wrsi = WR.run_wrsi(ee, aoi, args.year, planting, crop, kc_cfg, soil_cfg,
                               sos_start, sos_end, whc_img=whc_img)
            from src.wrsi_waterbalance import classify_wrsi
            wrsi_img = wrsi["WRSI"]; deficit_img = wrsi["deficit_mm"]
            wrsi_class_img = classify_wrsi(ee, wrsi_img)

        metric_img = SK.means_metric_image(
            ee, planting, mask, win_start, win_end,
            g_ic=g_ic, sos_img=sos,
            wrsi_img=wrsi_img, deficit_img=deficit_img, wrsi_class_img=wrsi_class_img,
            sos_start=sos_start, sos_end=sos_end)

        # ---- national summary as a 1-row batch export (avoids interactive memory limit) ----
        nat_dict = SK.national_summary(ee, planting, metric_img, mask, aoi, scale=nat_scale)
        nat_feat = ee.FeatureCollection([ee.Feature(None, nat_dict).set(
            {"country": c, "crop": crop, "season": season, "year": args.year,
             "cal_win_start": win_start, "cal_win_end": win_end, "cal_win_centre": centre})])
        ee.batch.Export.table.toDrive(
            collection=nat_feat, description=desc + "_national_stats",
            folder="planting_outputs", fileFormat="CSV").start()
        print(f"      national stats export started: {desc}_national_stats (Drive/planting_outputs)")

        # optional immediate print (interactive; coarse; may exceed memory on big countries)
        if args.print_national:
            try:
                nat = nat_dict.getInfo()
                def g(k):
                    v = nat.get(k); return round(v, 3) if isinstance(v, (int, float)) else v
                print("      NATIONAL (interactive):")
                print(f"        planting dekad  mode={g('pd_mode')}  P50={g('pd_p50')}  mean={g('pd_mean')}  n={g('pd_count')}")
                print(f"        skill vs cal    hit_rate={g('hit')}  bias_dek={g('bias')}  mae_dek={g('abserr')}")
                if 'amp' in nat:  print(f"        signal          amp={g('amp')}  detected_frac={g('detected')}")
                if 'WRSI' in nat: print(f"        WRSI            mean={g('WRSI')}  fail_frac={g('fail')}")
            except Exception as e:
                print(f"        (interactive print skipped: {e})")

        # ---- admin-1 stats batch export to Drive ----
        if not args.national_only:
            adm1 = ZA.gaul_admin(ee, [adm0], level=1)
            describe = SK.describe_planting(ee, planting, mask, adm1, scale=adm_scale)
            means = SK.zonal_means(ee, metric_img, adm1, scale=adm_scale)
            # join describe + means on ADM1_NAME into one table
            join = ee.Join.inner("d", "m")
            filt = ee.Filter.equals(leftField="ADM1_NAME", rightField="ADM1_NAME")
            joined = join.apply(describe, means, filt).map(
                lambda f: ee.Feature(f.get("d")).copyProperties(ee.Feature(f.get("m"))))
            ee.batch.Export.table.toDrive(
                collection=joined, description=desc + "_stats",
                folder="planting_outputs", fileFormat="CSV").start()
            print(f"      admin-1 stats export started: {desc}_stats (Drive/planting_outputs)")


if __name__ == "__main__":
    main()
