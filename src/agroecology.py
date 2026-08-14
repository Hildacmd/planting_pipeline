"""Country-agnostic agro-ecology → maize maturity class, derived from DATA (not national AEZ codes).

Replaces the Kenya-specific Jaetzold parser so the same logic runs across all 10 GHA/ICPAC countries:

  1. LGP  (Length of Growing Period, dekads) = number of dekads in the year where moisture is
          adequate, P/PET >= 0.5 (FAO growing-period convention), from the CHIRPS + Hargreaves-ET0
          climatology. Longer LGP -> longer-cycle maize can be grown.
  2. Thermal belt = elevation (SRTM DEM) -> cool highland / midland / warm lowland. Cooler belts
          slow development (more calendar days to mature) and usually carry a longer moist season.
  3. Maturity class = one function of (LGP, elevation):
          EARLY  (short-cycle / drought-escaping, e.g. Katumani) — short LGP, warm lowland
          MEDIUM (e.g. H513/H516)                                 — moderate LGP / midland
          LATE   (long-cycle, e.g. H614/H629)                     — long LGP or cool highland

Thresholds are indicative first-order values; calibrate against national variety catalogues.
"""
from __future__ import annotations

# LGP class breaks (dekads; x10 ≈ days) and elevation belt break (m).
# Calibrated so the data-derived split approximates Kenya's Jaetzold early/medium/late shares;
# tune per region against national variety catalogues.
LGP_EARLY_MAX = 7      # < 70 days single-season moisture -> only short-cycle / drought-escaping fits
LGP_LATE_MIN  = 15     # > 150 days -> long-cycle viable
COOL_HIGHLAND_M = 1800 # LH/UH/TA belts (cool -> long calendar cycle)


def lgp_dekads(ee, aoi, years=(2019, 2023), ppet_thresh=0.5):
    """Climatological Length of Growing Period = longest CONTINUOUS run of dekads with
    P/PET >= ppet_thresh (one growing season, not the annual total — correct for bimodal climates).
    Wrap-safe: the dekad sequence is doubled so a season crossing the year end is counted whole."""
    from .wrsi_feedback import chirps_dekadal
    from .wrsi_waterbalance import hargreaves_et0_dekadal
    yrs = list(range(years[0], years[1] + 1))
    adequate = []
    for dk in range(1, 37):
        P, E = [], []
        for y in yrs:
            P.append(ee.Image(chirps_dekadal(ee, aoi, y)
                              .filter(ee.Filter.eq("dekad", dk)).first()).select("P"))
            E.append(ee.Image(hargreaves_et0_dekadal(ee, aoi, y, 0)
                              .filter(ee.Filter.eq("gd", dk)).first()).select("ET0"))
        pmean = ee.ImageCollection(P).mean()
        emean = ee.ImageCollection(E).mean().max(1e-3)
        adequate.append(pmean.divide(emean).gte(ppet_thresh).toFloat().rename("ok"))
    # longest continuous run of 1s, computed over a doubled sequence (handles year wrap)
    seq = ee.List(adequate + adequate)

    def step(img, acc):
        acc = ee.Dictionary(acc)
        cur = ee.Image(acc.get("cur")).add(1).multiply(ee.Image(img))   # +1 if adequate, else reset to 0
        return ee.Dictionary({"cur": cur, "max": ee.Image(acc.get("max")).max(cur)})

    res = ee.Dictionary(seq.iterate(step, ee.Dictionary({"cur": ee.Image(0), "max": ee.Image(0)})))
    return ee.Image(res.get("max")).min(36).rename("LGP_dekads").clip(aoi)


def elevation(ee, aoi, dem="USGS/SRTMGL1_003"):
    return ee.Image(dem).select(0).rename("elev_m").clip(aoi)


def maturity_class_img(ee, lgp, elev):
    """Return maturity class image: 1=early, 2=medium, 3=late (country-agnostic)."""
    cool = elev.gte(COOL_HIGHLAND_M)
    late = lgp.gte(LGP_LATE_MIN).Or(cool.And(lgp.gte(12)))     # long LGP, or cool highland w/ decent LGP
    early = lgp.lt(LGP_EARLY_MAX).And(cool.Not())              # short LGP in a warm belt
    return (ee.Image(2)                                        # default medium
            .where(late, 3).where(early, 1)
            .rename("maturity_class").toInt8())


def classify(ee, aoi, years=(2019, 2023), ppet_thresh=0.5, dem="USGS/SRTMGL1_003"):
    """Convenience: returns dict with LGP, elevation, and maturity-class images."""
    lgp = lgp_dekads(ee, aoi, years, ppet_thresh)
    elev = elevation(ee, aoi, dem)
    return {"LGP_dekads": lgp, "elev_m": elev,
            "maturity_class": maturity_class_img(ee, lgp, elev)}


MATURITY_LABEL = {1: "early", 2: "medium", 3: "late"}


if __name__ == "__main__":
    # quick test: national maize maturity-class fractions over Kenya, vs the Jaetzold-derived split
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src import utils, zonal_aggregate as ZA
    ee = utils.gee_init()
    aoi = ZA.gaul_admin(ee, ["Kenya"], level=0).geometry()
    maize = (ee.ImageCollection("ESA/WorldCereal/2021/MODELS/v100")
             .filter(ee.Filter.eq("product", "maize")).mosaic()
             .select("classification").eq(100).selfMask())
    res = classify(ee, aoi)
    mc = res["maturity_class"].updateMask(maize)
    hist = mc.reduceRegion(ee.Reducer.frequencyHistogram(), aoi, scale=2000,
                           maxPixels=1e12, bestEffort=True).get("maturity_class").getInfo()
    tot = sum(hist.values())
    print("Kenya maize — data-derived maturity fractions (LGP + elevation):")
    for k in sorted(hist):
        print(f"  {MATURITY_LABEL.get(int(float(k)), k):7} {hist[k]/tot*100:5.1f}%")
    lgp_mean = res["LGP_dekads"].updateMask(maize).reduceRegion(
        ee.Reducer.mean(), aoi, scale=2000, maxPixels=1e12, bestEffort=True).get("LGP_dekads").getInfo()
    print(f"  mean LGP over maize: {lgp_mean:.1f} dekads (~{lgp_mean*10:.0f} days)")
