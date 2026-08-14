"""GDD phenology clock — THERMAL branch (maize). Pure GEE.

Implements Stages 3–5 of GDD_Phenology_Clock_Workflow.docx (v2.1) for the thermal-branch crops:
  anchor  = SOS (emergence) dekad image, from the pipeline's detect_sos (Stage 1, reused server-side)
  temp    = ERA5-Land daily air Tmax/Tmin, DEM lapse-corrected to SRTM 30 m (Stage 3)
  clock   = dekadal GDD accumulation from SOS (Stage 4a)
  stages  = flowering & maturity dekad when GDD_cum crosses the targets (Stage 5)

Thermal branch ONLY (maize; extensible to improved wheat/teff). Photoperiod-sensitive landrace
sorghum & pearl millet need the separate photoperiod branch (Stage 4b) — not implemented here.

GDD_maturity seeds from the AEZ maturity class (early 1300 / medium 1500 / late 1700 °C·d); the
EVI-peak self-calibration (Stage 6) that refines the targets is a documented follow-on.
NOTE: the DEM lapse uses a boxcar-mean SRTM as a proxy for the reanalysis-resolved elevation
(true ERA5-Land orography is a refinement); environmental lapse rate 6.5 °C/km.
"""
LAPSE = 0.0065          # °C per m
GDD_BY_CLASS = {1: 1300.0, 2: 1500.0, 3: 1700.0}   # AEZ early/medium/late → °C·d to maturity

# Stage transitions the clock predicts, as fractions of GDD-to-maturity (maize).
# The risk stage-weighting rides on the intervals between these markers (§3, RISK_MONITORING_DESIGN).
STAGE_FRACS = {
    "peak_vegetative": 0.45,   # VT tasseling — end of vegetative growth, canopy peak
    "flowering":       0.55,   # R1 silking — the critical water/heat window
    "grain_filling":   0.65,   # R2/R3 onset — yield formation begins
    "maturity":        1.00,   # R6 physiological maturity — end of season
}


def gdd_maturity_from_aez(ee, aoi, years=(2019, 2023)):
    """Per-pixel GDD-to-maturity seeded from the data-derived AEZ maturity class (agroecology.py)."""
    from . import agroecology as AG
    mc = AG.classify(ee, aoi, years=years)["maturity_class"]      # 1 early / 2 medium / 3 late
    return (ee.Image(GDD_BY_CLASS[2])
            .where(mc.eq(1), GDD_BY_CLASS[1])
            .where(mc.eq(3), GDD_BY_CLASS[3])
            .rename("gdd_maturity"))


def _dekad_air_temp(ee, aoi, year, dk, dem, dem_coarse):
    """Dekad-mean Tmax/Tmin (°C) from ERA5-Land, lapse-corrected to the 30 m DEM."""
    from .utils import dekad_to_start_date
    s = ee.Date(dekad_to_start_date(year, dk).isoformat()); e = s.advance(10, "day")
    col = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").filterDate(s, e).filterBounds(aoi)
    tmax = col.select("temperature_2m_max").mean().subtract(273.15)
    tmin = col.select("temperature_2m_min").mean().subtract(273.15)
    dz = dem.subtract(dem_coarse)                      # fine minus reanalysis-resolved elevation
    return tmax.subtract(dz.multiply(LAPSE)), tmin.subtract(dz.multiply(LAPSE))


def gdd_clock(ee, aoi, year, sos_dk, gdd_maturity, tbase=9.0, tcap=30.0,
              dk_lo=1, dk_hi=36, stages=None):
    """Predict the dekad each maize stage transition is reached, from the SOS anchor.

    Returns a multiband image: one `<stage>_dekad` band per marker in `stages`
    (peak_vegetative, flowering, grain_filling, maturity) plus `gdd_total`. The risk
    stage-weighting rides on the intervals between these markers.

    gdd_maturity may be a scalar or an ee.Image (AEZ-seeded per pixel). Accumulate only over
    dekads [dk_lo, dk_hi] (restrict to the season window to keep it light).
    """
    stages = stages or STAGE_FRACS
    gmat = ee.Image.constant(gdd_maturity) if not hasattr(gdd_maturity, "bandNames") else gdd_maturity
    thresh = {name: gmat.multiply(frac) for name, frac in stages.items()}
    dem = ee.Image("USGS/SRTMGL1_003").select("elevation").clip(aoi)
    dem_coarse = dem.reduceNeighborhood(ee.Reducer.mean(),
                                        ee.Kernel.square(25, "pixels"), optimization="boxcar")

    cum = ee.Image(0).rename("cum")
    marks = {name: ee.Image(0) for name in stages}
    for dk in range(dk_lo, dk_hi + 1):
        yr = year if dk <= 36 else year + 1          # year-wrap: dekads > 36 fall in the next year
        cdk = dk if dk <= 36 else dk - 36            # (short rains plant Oct, mature Feb-Mar next year)
        tmax, tmin = _dekad_air_temp(ee, aoi, yr, cdk, dem, dem_coarse)
        gdd = tmax.min(tcap).add(tmin).divide(2).subtract(tbase).max(0).multiply(10)   # dekad GDD
        active = ee.Image(dk).gte(sos_dk)                      # dk is ABSOLUTE (1..54); so is sos_dk
        cum = cum.add(gdd.multiply(active))
        for name in stages:
            marks[name] = marks[name].where(cum.gte(thresh[name]).And(marks[name].eq(0)), dk)

    out = None
    for name in stages:                                        # ordered by insertion (veg→maturity)
        band = marks[name].updateMask(marks[name].gt(0)).toInt16().rename(name + "_dekad")
        out = band if out is None else out.addBands(band)
    return out.addBands(cum.toInt16().rename("gdd_total"))
