#!/usr/bin/env python3
"""Export a per-admin attribute table with EVERY input + output layer value (GEE -> Drive CSV).

Season-window means of the drivers plus the LTN normals and the model outputs, one row per admin
unit. Batch export (high memory limit) so it survives where interactive getInfo can't. Convert the
resulting .geo to WKT locally with geo_to_wkt.py after it lands in Drive.

Columns (per admin unit):
  S2:   NDVI_mean, NDRE1_mean           (Sentinel-2 red-edge phenology over the SOS window)
  S1:   VV_mean, VH_mean, RVI_mean      (Sentinel-1 SAR)
  FPAR: FPAR_mean
  fused:G_mean, G_amp                   (fused greenness + seasonal amplitude)
  LTN:  pheno_ltn_dekad, onset_ltn_dekad, onset_anom_dekad, Tnorm_C, emergence_off_dekad
  out:  SOS_dekad, planting_dekad

Run: EE_PROJECT=ee-manzikye python attributes_table.py --year 2024 --country Kenya --crop maize --gaul-level 1
"""
import argparse, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from src import utils, s2_preprocess as S2, s1_preprocess as S1
from src import fusion_phenometrics as FZ, planting_date as PD
from src import zonal_aggregate as ZA, ltn as LTN

GAUL_NAME = {"Kenya": "Kenya", "Ethiopia": "Ethiopia", "Uganda": "Uganda",
             "Tanzania": "United Republic of Tanzania", "Rwanda": "Rwanda", "Burundi": "Burundi",
             "South_Sudan": "South Sudan", "Sudan": "Sudan", "Somalia": "Somalia", "Eritrea": "Eritrea"}


def crop_mask_image(ee, crop, mask_asset):
    if mask_asset:
        return ee.Image(mask_asset).selfMask()
    wc = ee.ImageCollection("ESA/WorldCereal/2021/MODELS/v100")
    prod = "maize" if crop == "maize" else "temporarycrops"
    return wc.filter(ee.Filter.eq("product", prod)).mosaic().select("classification").eq(100).selfMask()


def win_mean(ee, ic, band, s, e):
    dks = ee.List.sequence(s, e)
    return ic.filter(ee.Filter.inList("dekad", dks)).select(band).mean().rename(band + "_mean")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--country", default="Kenya"); ap.add_argument("--crop", default="maize")
    ap.add_argument("--mask-asset", default=None); ap.add_argument("--orbit", default="DESCENDING")
    ap.add_argument("--calendar", default="config/season_calendar.csv")
    ap.add_argument("--gaul-level", type=int, default=1, help="1=provinces (cheap), 2=districts")
    ap.add_argument("--scale", type=int, default=250)
    args = ap.parse_args()

    ee = utils.gee_init()
    rows = [r for r in utils.viable_products(utils.load_calendar(args.calendar))
            if r["country"] == args.country and r["crop"].lower() == args.crop.lower()]
    adm0 = GAUL_NAME[args.country]

    for r in rows:
        crop, season = r["crop"].lower(), r["season"]
        aoi = ZA.gaul_admin(ee, [adm0], level=0).geometry()
        s, e = utils.sos_window_dekads(r["sos_detection_window"])

        s2 = S2.build_s2_dekadal(ee, aoi, args.year)
        s1 = S1.build_s1_dekadal(ee, aoi, args.year, orbit=args.orbit)
        fpar = FZ.add_fpar_dekadal(ee, aoi, args.year)
        g_ic = FZ.build_fused_greenness(ee, s2, s1, fpar)
        mask = crop_mask_image(ee, crop, args.mask_asset)
        sos = FZ.detect_sos(ee, g_ic, mask, s, e)
        planting = PD.sos_to_planting(ee, sos, crop)

        # LTN inputs
        pheno = LTN.phenology_ltn_dekad(ee, aoi).rename("pheno_ltn_dekad")
        onset = LTN.chirps_onset_ltn(ee, aoi, (1981, args.year), s, e).rename("onset_ltn_dekad")
        anom = LTN.onset_anomaly(ee, aoi, args.year, (1981, args.year), s, e).rename("onset_anom_dekad")
        tnorm = LTN.temperature_ltn_C(ee, aoi)
        off = LTN.thermal_emergence_offset(ee, PD.EMERGENCE_OFFSET.get(crop, 1), tnorm)

        gwin = g_ic.filter(ee.Filter.inList("dekad", ee.List.sequence(s, e))).select("G")
        stack = (win_mean(ee, s2, "NDVI", s, e)
                 .addBands(win_mean(ee, s2, "NDRE1", s, e))
                 .addBands(win_mean(ee, s1, "VV", s, e))
                 .addBands(win_mean(ee, s1, "VH", s, e))
                 .addBands(win_mean(ee, s1, "RVI", s, e))
                 .addBands(win_mean(ee, fpar, "FPAR", s, e))
                 .addBands(gwin.mean().rename("G_mean"))
                 .addBands(gwin.max().subtract(gwin.min()).rename("G_amp"))
                 .addBands(pheno).addBands(onset).addBands(anom)
                 .addBands(tnorm).addBands(off.rename("emergence_off_dekad"))
                 .addBands(sos.rename("SOS_dekad"))
                 .addBands(planting.rename("planting_dekad"))
                 .updateMask(mask))

        admin = ZA.gaul_admin(ee, [adm0], level=args.gaul_level)
        feats = stack.reduceRegions(collection=admin, reducer=ee.Reducer.mean(), scale=args.scale)
        desc = f"attributes_{args.country}_{crop}_{season}_{args.year}".replace(" ", "")
        ee.batch.Export.table.toDrive(collection=feats, description=desc,
                                      folder="planting_outputs", fileFormat="CSV").start()
        print(f"  export started: {desc} (GAUL L{args.gaul_level}; attributes: NDVI/NDRE1/VV/VH/RVI/"
              f"FPAR/G/G_amp + pheno/onset/anom/Tnorm/offset LTN + SOS/planting)")


if __name__ == "__main__":
    main()
