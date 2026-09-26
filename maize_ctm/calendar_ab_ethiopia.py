#!/usr/bin/env python3
"""Ethiopia Meher maize: does the operative planting window beat the two published calendars?

The operative window opens at Apr-d1. Inception Report Table 2.0 says Jun-d1, six dekads later,
and GEOGLAM CM4EW says May-d2, four dekads later. Ethiopia Meher maize is the largest maize
product in the region at 2.03 Mha, so the question is worth settling rather than arguing.

THREE arms, not two. Two independent sources disagree with the operative window by different
amounts, and running both says whether skill falls away monotonically as planting is pushed later
— which a single pairwise test cannot show.

    arm op      SOS Apr-d2 to Jun-d3   operative, long-cycle maize on Belg moisture
    arm cm4ew   SOS May-d3 to Aug-d2   GEOGLAM CM4EW Maize 1, planting May-d2 to Jul-d2
    arm report  SOS Jun-d2 to Aug-d3   Table 2.0, planting Jun-d1 to Jul-d3

Everything else is identical — mask, coefficients, Ky, ceiling — so a difference is attributable
to the window. The SOS windows for the two alternatives are derived from their planting months by
the operative rule (start + 1 dekad, end + 3), so the derivation rule is not a confounder.

    python maize_ctm/calendar_ab_ethiopia.py                 # dry run
    EE_PROJECT=ee-manzikye python maize_ctm/calendar_ab_ethiopia.py --submit
"""
import argparse, os, sys
H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(H)
sys.path.insert(0, ROOT)
from src import utils                                    # noqa: E402
import run_all_maize_2024 as M                           # noqa: E402

YEAR = 2024
EE_PROJECT = os.environ.get("EE_PROJECT", "ee-manzikye")
ARMS = {
    "op":     dict(sos="Apr-d2-Jun-d3", planting="Apr-d1-May-d3",
                   src="operative (config/season_calendar.csv)"),
    "cm4ew":  dict(sos="May-d3-Aug-d2", planting="May-d2-Jul-d2",
                   src="GEOGLAM CM4EW v1.3, Maize 1"),
    "report": dict(sos="Jun-d2-Aug-d3", planting="Jun-d1-Jul-d3",
                   src="Inception Report Table 2.0"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--submit", action="store_true")
    a = ap.parse_args()

    rows = {(r["country"], r["season"]): r for r in
            utils.viable_products(utils.load_calendar(f"{ROOT}/config/season_calendar.csv"))
            if r["crop"].lower() == "maize"}
    base = dict(rows[("Ethiopia", "Meher")])
    print(f"{'arm':<8}{'SOS window':<20}{'planting':<18}source")
    for k, v in ARMS.items():
        print(f"{k:<8}{v['sos']:<20}{v['planting']:<18}{v['src']}")
    print()

    if not a.submit:
        print("(dry run — add --submit to fire three rich exports)")
        print("Then: reduce each arm and score with maize_ctm/score_calendar_ab_ethiopia.py")
        return

    ee = utils.gee_init()
    kc, soil = utils.load_crop_coeffs()
    M.RICH = True
    for k, v in ARMS.items():
        desc = f"cal{k}_Ethiopia_Meher_{YEAR}"
        asset = f"projects/{EE_PROJECT}/assets/{desc}"
        try:
            ee.data.getAsset(asset); print(f"  skip (exists): {desc}"); continue
        except Exception:
            pass
        r = dict(base); r["sos_detection_window"] = v["sos"]
        out, aoi, _ = M.build_product_image(ee, r, kc, soil, rich=True)
        out = out.set({"arm": k, "sos_window": v["sos"], "planting_window": v["planting"],
                       "calendar_source": v["src"]})
        ee.batch.Export.image.toAsset(image=out.clip(aoi), description=desc, assetId=asset,
                                      region=aoi, scale=250, maxPixels=int(1e13)).start()
        print(f"  started: {desc}   SOS {v['sos']}")


if __name__ == "__main__":
    main()
