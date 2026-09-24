#!/usr/bin/env python3
"""Re-run the 2024 maize products on the ICPAC crop-type mask instead of WorldCereal.

The shipped maize products are computed inside the **ESA WorldCereal 2021 maize layer**, because
that is what `run.crop_mask_image` returns by default. WorldCereal is a single global model year,
is not calibrated to any national statistics, and its maize class was trained largely on
large-field systems. The ICPAC crop-type mask is a dasymetric allocation of MapSPAM shares onto a
four-lineage, sixteen-source-year cropland vote, reweighted by suitability and satellite evidence
and **calibrated to sub-national statistics**, which reproduces reported maize area to 92 to 99 %
across the eight countries that have a maize mask.

Nothing about the water balance, the stresses, the CPI or the yield ceiling changes. Only the set
of pixels the product is computed over changes, so the two runs are directly comparable and the
difference is attributable to the mask.

**Outputs go to their own asset prefix and their own folder**, so the existing products are
untouched:

    assets   cpiCTM_<Country>_<Season>_2024      (cpiCTMX_ with --rich)
    folder   maize_ctm/

    python maize_ctm/run_maize_ctm.py --stage high                       # dry run
    EE_PROJECT=... python maize_ctm/run_maize_ctm.py --stage high --submit
    python maize_ctm/compare_masks.py                                    # WorldCereal vs crop-type
"""
import argparse, os, sys

H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(H)
sys.path.insert(0, ROOT)

from src import utils                                   # noqa: E402
import ctm_mask as CTM                                   # noqa: E402
import run_all_maize_2024 as M                           # noqa: E402

EE_PROJECT = os.environ.get("EE_PROJECT", "ee-manzikye")
YEAR = M.YEAR


def eligible(rows):
    """Maize products in a country that has a maize band in the crop-type mask."""
    out, skipped = [], []
    for r in rows:
        (out if CTM.has(r["country"], "maize") else skipped).append(r)
    return out, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="high", choices=["high", "medium", "all"])
    ap.add_argument("--submit", action="store_true")
    ap.add_argument("--rich", action="store_true",
                    help="also emit planting_dekad and the 6 WRSI/WSI stage bands")
    ap.add_argument("--country")
    ap.add_argument("--min-fraction", type=float, default=None,
                    help="use frac_maize >= this percent of the cell instead of the shipped 10 %% "
                         "binary mask, to tighten the stratum")
    a = ap.parse_args()

    rows = [r for r in utils.viable_products(utils.load_calendar(f"{ROOT}/config/season_calendar.csv"))
            if r["crop"].lower() == "maize"]
    want = {"high": ["High"], "medium": ["Medium"], "all": ["High", "Medium"]}[a.stage]
    rows = [r for r in rows if r["crop_viability"] in want]
    if a.country:
        rows = [r for r in rows if r["country"].replace(" ", "_") == a.country.replace(" ", "_")]
    rows, skipped = eligible(rows)

    pfx = "cpiCTMX" if a.rich else "cpiCTM"
    print(f"{'SUBMIT' if a.submit else 'DRY-RUN'} · stage={a.stage} · {len(rows)} maize products "
          f"on the crop-type mask (250 m)")
    if skipped:
        print(f"  skipping {len(skipped)}: no maize band in the crop-type mask — "
              f"{', '.join(sorted({r['country'] for r in skipped}))}")
    print(f"{'product':<34} {'onset':<9} {'mapped maize Mha':>17}  mask")

    ee = utils.gee_init() if a.submit else None
    kc, soil = utils.load_crop_coeffs() if a.submit else (None, None)
    inflight = set()
    if a.submit:
        for o in ee.data.listOperations():
            m = o.get("metadata", {})
            if m.get("state") in ("PENDING", "RUNNING"):
                inflight.add(m.get("description"))

    for r in rows:
        c, s = r["country"], r["season"]
        desc = f"{pfx}_{c}_{s}_{YEAR}".replace(" ", "")
        method = "rainfall" if s in M.RAINFALL_ANCHORED else "greenup"
        area = CTM.AREA_MHA.get((c.replace(" ", "_"), "maize"))
        line = (f"{c + ' ' + s:<34} {method:<9} {area if area else '-':>17}  "
                f"{CTM.asset(c).rsplit('/', 1)[-1]}"
                + (f" frac>={a.min_fraction:g}%" if a.min_fraction else ""))
        if not a.submit:
            print("  would submit: " + line); continue
        asset_id = f"projects/{EE_PROJECT}/assets/{desc}"
        try:
            ee.data.getAsset(asset_id); print(f"  skip (asset exists): {desc}"); continue
        except Exception:
            pass
        if desc in inflight:
            print(f"  skip (task in-flight): {desc}"); continue
        mask = CTM.crop_mask(ee, c, "maize", a.min_fraction)
        M.RICH = a.rich
        out, aoi, _ = M.build_product_image(ee, r, kc, soil, rich=a.rich, mask=mask)
        out = out.set({"crop_mask": "ICPAC crop-type mask", "mask_asset": CTM.asset(c),
                       "mask_min_fraction": a.min_fraction or 10})
        ee.batch.Export.image.toAsset(image=out.clip(aoi), description=desc, assetId=asset_id,
                                      region=aoi, scale=250, maxPixels=int(1e13)).start()
        print("  started     : " + line)

    if not a.submit:
        print("\n(dry-run — add --submit to fire)")
        print("The shipped cpi_* products use WorldCereal; these cpiCTM_* products differ only in "
              "the mask, so compare_masks.py attributes any difference to it.")


if __name__ == "__main__":
    main()
