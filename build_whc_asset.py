#!/usr/bin/env python3
"""Materialise the root-zone water-holding capacity as an Earth Engine asset, per rooting depth.

WHC is static: it comes from SoilGrids texture through the Saxton and Rawls pedotransfer
functions and does not change between seasons. Computing it inside every run is pure waste, and
the pipeline already caches a 100 cm version for maize and wheat. **Sorghum roots to 1.5 m**
(FAO-56 Table 22), so every sorghum product currently falls through to a live SoilGrids build:

    [soil] whc_asset built at 100 cm but 150 cm requested -> computing WHC from SoilGrids

WHC is not linear in depth, because SoilGrids texture varies layer by layer, so the 100 cm asset
cannot simply be rescaled. It needs its own export.

    python build_whc_asset.py --depth-cm 150                     # dry run, prints the plan
    EE_PROJECT=ee-manzikye python build_whc_asset.py --depth-cm 150 --submit

**Footprint.** The existing 100 cm asset covers only lon 32.3 to 49.0 and lat -4.8 to 14.9, so
western Sudan, eastern Somalia, southern Tanzania, Rwanda and Burundi all fall outside it and are
filled live from SoilGrids on every run. This builder covers the full eleven-country extent with a
margin, so the new asset has no such gap.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src import utils, soil as SOIL                                   # noqa: E402

# Union of the eleven ICPAC country extents, with a margin:
# lon 21.84 (W Sudan) to 51.41 (E Somalia), lat -11.76 (S Tanzania) to 22.33 (N Sudan).
REGION = [20.5, -12.5, 52.5, 23.0]
DEFAULT_PROJECT = "ee-manzikye"


def asset_id(depth_cm, project):
    return f"projects/{project}/assets/whc_saxton_soilgrids_gha_{int(depth_cm)}cm_250m"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--depth-cm", type=int, default=150,
                    help="rooting depth to integrate to; sorghum 150, maize/wheat 100, teff 60")
    ap.add_argument("--scale", type=int, default=250)
    ap.add_argument("--project", default=os.environ.get("EE_PROJECT", DEFAULT_PROJECT))
    ap.add_argument("--submit", action="store_true")
    a = ap.parse_args()

    aid = asset_id(a.depth_cm, a.project)
    w, s, e, n = REGION
    px_x = int((e - w) * 111320 / a.scale * 0.94)      # rough, for the size estimate only
    px_y = int((n - s) * 110540 / a.scale)
    print(f"WHC asset, Saxton-Rawls on SoilGrids 2.0")
    print(f"  depth    : {a.depth_cm} cm")
    print(f"  region   : lon {w} to {e}, lat {s} to {n}  (all eleven countries, with margin)")
    print(f"  scale    : {a.scale} m   (about {px_x:,} x {px_y:,} pixels)")
    print(f"  asset    : {aid}")
    if not a.submit:
        print("\n(dry run — add --submit to fire)")
        print("One export. Every later run at this rooting depth then loads it instead of "
              "rebuilding WHC from SoilGrids.")
        return

    ee = utils.gee_init()
    try:
        ee.data.getAsset(aid)
        print(f"\nasset already exists: {aid}\n  delete it first if you mean to rebuild.")
        return
    except Exception:
        pass
    region = ee.Geometry.Rectangle(REGION, proj="EPSG:4326", geodesic=False)
    whc = SOIL.build_whc_saxton_mm(ee, root_depth_cm=a.depth_cm, min_whc_mm=25)
    t = SOIL.export_whc_to_asset(ee, whc, region, aid, scale=a.scale,
                                 description=f"whc_saxton_{a.depth_cm}cm_gha_{a.scale}m")
    print(f"\nstarted: {t.id}  ->  {aid}")
    print("When it succeeds, add it to config/crop_coefficients.yaml under soil.whc_assets:")
    print(f"    {a.depth_cm}: \"{aid}\"")


if __name__ == "__main__":
    main()
