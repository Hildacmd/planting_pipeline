#!/usr/bin/env python3
"""Submit the ICPAC sorghum CPI/yield products as Earth Engine batch asset exports.

Same method as `run_all_maize_2024.py`, with the four things that are genuinely different for
sorghum: the crop calendar (GEOGLAM CM4EW), the FAO-56 coefficients, the FAO-33 stage yield
factors, and the crop mask (the crop-type mask series, not WorldCereal).

DRY-RUN by default. Nothing is exported unless you add --submit.

    python sorghum_pipeline/run_all_sorghum.py --stage high
    EE_PROJECT=ee-manzikye python sorghum_pipeline/run_all_sorghum.py --stage high --submit
    ... --stage medium --submit        # then stage 2

Each product -> asset `sorghum_<Country>_<Season>_<YEAR>` at 250 m, bands CPI, yield_tha_x100,
S_water, S_heat, S_veg (and with --rich, planting_dekad plus the six WRSI/WSI stage bands).

**Yield is uncalibrated until `calibrate_ym_sorghum.py` has run.** CPI is the season signal and
is usable immediately; the yield band only carries a level, and that level is a guess until a
ceiling has been fitted to HarvestStat. The asset property `ym_calibrated` records which it is.
"""
import argparse, csv, os, sys

H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(H)
sys.path.insert(0, ROOT); sys.path.insert(0, H)

from src import utils                                   # noqa: E402
import sorghum_params as P                              # noqa: E402
import irrigation_exposure as IRR                      # noqa: E402

YEAR = 2024
# arm A = the Inception Report Table 2.0 calendar; arm B = the GEOGLAM CM4EW sorghum-specific one.
# Products are prefixed so the two arms can sit side by side and be scored against each other.
CALENDARS = {"report": (f"{H}/config/season_calendar_sorghum.csv", "sorghum"),
             "cm4ew":  (f"{H}/config/season_calendar_sorghum_cm4ew.csv", "sorghumB")}
# Compute and exports run in this project; the crop-type masks are READ from wherever
# ctm_mask/sorghum_params point, which may be a different project (they are readable
# cross-project under the same Google account).
EE_PROJECT = os.environ.get("EE_PROJECT", "ee-manzikye")

# Secondary and short seasons use the rainfall-anchored onset: green-up detection is unreliable
# there (WORKFLOW_SHORTRAINS), and Season A in the Rwandan and Burundian highlands is defeated by
# persistent cloud (maize Season A: 64 green-up pixels against 3,365 from rainfall onset).
RAINFALL_ANCHORED = {"Short rains", "2nd rains", "Season A", "Season B",
                     "Vuli", "Deyr", "Belg", "2nd"}


def load_rows(stage, calendar="report", differing_only=False):
    path, _ = CALENDARS[calendar]
    with open(path) as f:
        rows = list(csv.DictReader(f))
    want = {"high": ["High"], "medium": ["Medium"], "all": ["High", "Medium", "Low"]}[stage]
    rows = [r for r in rows if r["crop_viability"] in want]
    if differing_only:
        with open(CALENDARS["report"][0]) as f:
            a = {(r["country"], r["season"]): r["sos_detection_window"] for r in csv.DictReader(f)}
        rows = [r for r in rows if a.get((r["country"], r["season"])) != r["sos_detection_window"]]
    return rows


def kc_for(row):
    """FAO-56 coefficients for this product: the sorghum curve stretched to the season's own
    cycle length, from the CM4EW planting-to-harvest span where CM4EW monitors the country."""
    p = dict(P.SORGHUM_KC)
    if row["season"] in RAINFALL_ANCHORED:
        p.update(P.SORGHUM_KC_EARLY)
    cyc = int(row.get("cycle_dekads") or p["LGP_dekads"])
    if cyc != p["LGP_dekads"]:                    # rescale the four stages onto the real cycle
        f = cyc / p["LGP_dekads"]
        ini = max(1, round(p["L_ini"] * f)); dev = max(1, round(p["L_dev"] * f))
        mid = max(1, round(p["L_mid"] * f)); late = max(1, cyc - ini - dev - mid)
        p.update(L_ini=ini, L_dev=dev, L_mid=mid, L_late=late, LGP_dekads=ini + dev + mid + late)
    return p


def build_product_image(ee, row, soil, aoi=None, rich=False):
    """CPI / yield / stress image for one sorghum calendar row. Returns (out, aoi, meta)."""
    from src import (s2_preprocess as S2, s1_preprocess as S1, fusion_phenometrics as FZ,
                     ltn as LTN, cpi as CPI, soil as SOIL, wrsi_feedback as WR,
                     zonal_aggregate as ZA)
    from src.wrsi_waterbalance import run_wrsi_staged
    from run import GAUL_NAME

    country, season = row["country"], row["season"]
    if aoi is None:
        gname = GAUL_NAME.get(country) or GAUL_NAME.get(country.replace("_", " "), country)
        aoi = ZA.gaul_admin(ee, [gname], level=0).geometry()
    ss, se = utils.sos_window_dekads(row["sos_detection_window"])
    mask = P.sorghum_mask(ee, country)
    p = kc_for(row)
    kc_use = {"sorghum": p}
    rain = season in RAINFALL_ANCHORED
    wrsi_year, ss_use, se_use = YEAR, ss, se

    if rain:
        pet = WR.pet_dekadal(ee, aoi, YEAR); ch = WR.chirps_dekadal(ee, aoi, YEAR)
        clim = WR.chirps_clim_dekadal(ee, aoi, range(ss, 37), range(1981, 2025))
        onset = WR.wrsi_onset(ee, ch, ss, se, pet_ic=pet).unmask(
            WR.wrsi_onset(ee, clim, ss, se, pet_ic=pet))
        planting = onset.updateMask(mask).toInt16()
    else:
        cross = ss > se                                  # cross-year season, e.g. Msimu Dec->Feb
        byear = YEAR - 1 if cross else YEAR
        se_use = se + 36 if cross else se
        dks = range(ss, se_use + 1)
        s2 = S2.build_s2_dekadal(ee, aoi, byear, dekads=dks)
        s1 = S1.build_s1_dekadal(ee, aoi, byear, orbit="DESCENDING", dekads=dks)
        fpar = FZ.add_fpar_dekadal(ee, aoi, byear, dekads=dks)
        g = FZ.build_fused_greenness(ee, s2, s1, fpar)
        ltn = None if cross else LTN.build_ltn_prior(ee, aoi, ss, se)   # the prior is not wrap-safe
        sos = FZ.detect_sos(ee, g, mask, ss, se_use, ltn_sos=ltn, ltn_pad=2)
        planting = sos.subtract(P.SORGHUM_EMERGENCE_OFFSET).rename("planting_dekad").toInt16()
        wrsi_year = byear

    whc = SOIL.get_whc(ee, aoi, soil, root_depth_cm=int(p["root_depth_m"] * 100))
    d_veg = p["L_ini"] + p["L_dev"]; d_flo = d_veg + p["L_mid"]
    staged = run_wrsi_staged(ee, aoi, wrsi_year, planting, "sorghum", kc_use, soil,
                             ss_use, se_use, whc_img=whc)
    Sw = CPI.s_water(ee, staged, ky=P.SORGHUM_KY)
    Sh = CPI.s_heat(ee, aoi, wrsi_year, planting, d_veg, d_flo, ss_use, se_use,
                    tcap=P.SORGHUM_HEAT_TCAP, k=P.SORGHUM_HEAT_K)
    vss, vse = (1, max(6, se_use - 30)) if se_use > 36 else (ss_use, se_use)
    Sv = CPI.s_veg(ee, aoi, YEAR, vss, vse)
    ym = P.ym_for(country, season)
    cpi_img, yld = CPI.cpi(ee, Sw, Sh, Sv, ym=ym)

    bands = [cpi_img, yld.multiply(100), Sw.multiply(100), Sh.multiply(100), Sv.multiply(100)]
    names = ["CPI", "yield_tha_x100", "S_water", "S_heat", "S_veg"]
    if rich:
        bands += [planting, staged["wrsi_veg"], staged["wrsi_flo"], staged["wrsi_grf"],
                  staged["wsi_veg"], staged["wsi_flo"], staged["wsi_grf"]]
        names += ["planting_dekad", "wrsi_veg", "wrsi_flo", "wrsi_grf",
                  "wsi_veg", "wsi_flo", "wsi_grf"]
    out = (ee.Image.cat(bands).updateMask(mask).toInt16().rename(names)
           .set({"crop": "sorghum", "country": country, "season": season, "year": YEAR,
                 "ym_tha": ym, "ym_calibrated": P.is_calibrated(country, season),
                 "crop_calendar_source": row["crop_calendar_source"],
                 "cycle_dekads": p["LGP_dekads"],
                 "onset_method": "rainfall" if rain else "greenup",
                 "mask_asset": P.mask_asset(country),
                 # Irrigation exposure from SPAM 2020 - Somalia and Sudan sorghum are both
                 # materially irrigated; see crop_pipeline/docs/IRRIGATED_WATER_BALANCE.md
                 **IRR.asset_properties(country, "sorghum")}))
    meta = {"planting": planting, "staged": staged, "Sw": Sw, "Sh": Sh, "Sv": Sv,
            "cpi": cpi_img, "yld": yld, "mask": mask, "kc": p,
            "ss": ss_use, "se": se_use, "onset_method": "rainfall" if rain else "greenup"}
    return out, aoi, meta


def main():
    global YEAR
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="high", choices=["high", "medium", "all"])
    ap.add_argument("--submit", action="store_true", help="actually fire the batch exports")
    ap.add_argument("--rich", action="store_true",
                    help="also emit planting_dekad and the 6 WRSI/WSI stage bands")
    ap.add_argument("--country", help="restrict to one country")
    ap.add_argument("--year", type=int, default=YEAR)
    ap.add_argument("--calendar", default="report", choices=list(CALENDARS),
                    help="report = Inception Report Table 2.0 (arm A); "
                         "cm4ew = GEOGLAM CM4EW sorghum-specific (arm B)")
    ap.add_argument("--differing-only", action="store_true",
                    help="with --calendar cm4ew: only the products whose window actually differs "
                         "from arm A, so identical runs are not paid for twice")
    a = ap.parse_args()
    YEAR = a.year

    rows = load_rows(a.stage, a.calendar, a.differing_only)
    if a.country:
        rows = [r for r in rows if r["country"] == a.country.replace(" ", "_")]
    base = CALENDARS[a.calendar][1]
    pfx = base + "X" if a.rich else base
    print(f"{'SUBMIT' if a.submit else 'DRY-RUN'} · stage={a.stage} · year={YEAR} · "
          f"calendar={a.calendar} · {len(rows)} sorghum products (250 m)")
    print(f"{'product':<36} {'onset':<9} {'cal':<13} {'cycle':>5} {'Ym':>5} {'area Mha':>9}")

    ee = utils.gee_init() if a.submit else None
    soil = utils.load_crop_coeffs()[1] if a.submit else None
    inflight = set()
    if a.submit:
        for o in ee.data.listOperations():
            m = o.get("metadata", {})
            if m.get("state") in ("PENDING", "RUNNING"):
                inflight.add(m.get("description"))

    for r in rows:
        desc = f"{pfx}_{r['country']}_{r['season']}_{YEAR}".replace(" ", "")
        method = "rainfall" if r["season"] in RAINFALL_ANCHORED else "greenup"
        ym = P.ym_for(r["country"], r["season"])
        line = (f"{r['country'] + ' ' + r['season']:<36} {method:<9} "
                f"{r['crop_calendar_source']:<13} {kc_for(r)['LGP_dekads']:>5} "
                f"{ym:>5.2f} {r.get('mapped_area_Mha', ''):>9}")
        if not a.submit:
            print("  would submit: " + line); continue
        asset = f"projects/{EE_PROJECT}/assets/{desc}"
        try:
            ee.data.getAsset(asset); print(f"  skip (asset exists): {desc}"); continue
        except Exception:
            pass
        if desc in inflight:
            print(f"  skip (task in-flight): {desc}"); continue
        out, aoi, _ = build_product_image(ee, r, soil, rich=a.rich)
        ee.batch.Export.image.toAsset(image=out.clip(aoi), description=desc, assetId=asset,
                                      region=aoi, scale=250, maxPixels=int(1e13)).start()
        print("  started     : " + line)

    if not a.submit:
        print("\n(dry-run — add --submit to fire)")
    uncal = [r for r in rows if not P.is_calibrated(r["country"], r["season"])]
    if uncal:
        print(f"\nYield is UNCALIBRATED for {len(uncal)} of {len(rows)} products: no sorghum Ym has "
              f"been fitted yet. Report CPI, not yield, until calibrate_ym_sorghum.py has run.")


if __name__ == "__main__":
    main()
