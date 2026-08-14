"""Long-Term-Normal (LTN) constraints to sharpen Start-of-Season, all GEE-native.

Three climatological priors, fused into the SOS search so satellite green-up can't wander to
weed flushes / second-season false starts and so the planting offset varies with temperature:

  1. Phenology LTN  — MODIS MCD12Q2 Greenup normal (2001->, ~24 yr), converted to a dekad grid.
                      Gates detect_sos to +/- ltn_pad dekads around the climatological onset.
                      PLUGGABLE: pass `greenup_asset` (e.g. an ingested USGS/FEWS eMODIS 250 m
                      phenology asset already expressed in dekads) to swap MODIS out one-for-one.
  2. Rainfall LTN   — CHIRPS (1981->, ~45 yr) 25/20 mm onset normal. Fills phenology gaps and
                      gives a this-year onset ANOMALY (early/late season flag).
  3. Temperature LTN— ERA5-Land 1991-2020 mean-T normal -> a spatially varying emergence offset
                      (cooler highlands germinate slower -> longer SOS->planting lag).

Nothing here forces computation until an export/getInfo consumes it (EE is lazy).
"""
from __future__ import annotations

# ---------------- 1. Phenology LTN (MCD12Q2 greenup -> dekad) ----------------
def _greenup_to_dekad(ee, img, cycle):
    """One annual MCD12Q2 image -> greenup dekad (1..36). Greenup_c is days since 1970-01-01."""
    yr = ee.Date(img.get("system:time_start")).get("year")
    year_start = ee.Date.fromYMD(yr, 1, 1).difference(ee.Date("1970-01-01"), "day")
    g = img.select(f"Greenup_{cycle}")
    g = g.updateMask(g.neq(32767))                       # 32767 = fill / no cycle
    doy = g.subtract(year_start)                         # day-of-year of greenup
    # dekads average 365/36 = 10.14 days; ceil gives 1..36 (approx month-dekad within ~2 days)
    dekad = doy.divide(10.139).ceil().clamp(1, 36)
    return dekad.rename("ltn_dekad").copyProperties(img, ["system:time_start"])


def phenology_ltn_dekad(ee, aoi, years=(2001, 2024), cycle=1, greenup_asset=None):
    """LTN greenup dekad image. If greenup_asset is given (already in dekads), use it directly."""
    if greenup_asset:
        return ee.Image(greenup_asset).rename("ltn_sos_dekad").clip(aoi)
    ic = (ee.ImageCollection("MODIS/061/MCD12Q2").filterBounds(aoi)
            .filter(ee.Filter.calendarRange(years[0], years[1], "year")))
    dek = ic.map(lambda im: _greenup_to_dekad(ee, im, cycle))
    return dek.median().rename("ltn_sos_dekad").clip(aoi)


# ---------------- 2. Rainfall LTN (CHIRPS onset normal + anomaly) ----------------
def chirps_onset_ltn(ee, aoi, years, search_start, search_end):
    """Median CHIRPS 25/20 mm onset dekad over `years` (inclusive tuple) = rainfall onset normal."""
    from .wrsi_feedback import chirps_dekadal, wrsi_onset
    imgs = []
    for y in range(years[0], years[1] + 1):
        ch = chirps_dekadal(ee, aoi, y)
        imgs.append(wrsi_onset(ee, ch, search_start, search_end))
    return ee.ImageCollection(imgs).median().rename("onset_ltn_dekad").clip(aoi)


def onset_anomaly(ee, aoi, year, years_ltn, search_start, search_end):
    """This-year onset minus LTN onset (dekads): + = late season, - = early season."""
    from .wrsi_feedback import chirps_dekadal, wrsi_onset
    this = wrsi_onset(ee, chirps_dekadal(ee, aoi, year), search_start, search_end)
    ltn = chirps_onset_ltn(ee, aoi, years_ltn, search_start, search_end)
    return this.subtract(ltn).rename("onset_anom_dekads")


# ---------------- 3. Temperature LTN (thermal emergence offset) ----------------
def temperature_ltn_C(ee, aoi, years=(1991, 2020)):
    """Mean 2 m air-temperature normal (deg C) over the climatology period."""
    era = (ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").filterBounds(aoi)
             .filter(ee.Filter.calendarRange(years[0], years[1], "year"))
             .select("temperature_2m"))
    return era.mean().subtract(273.15).rename("T_norm_C").clip(aoi)


def thermal_emergence_offset(ee, base_off, t_norm_C, t_ref=22.0, dT=6.0, lo=1, hi=3):
    """Emergence offset (dekads) that lengthens in cooler areas.
    off = base + round((t_ref - T)/dT), clamped to [lo, hi]. At 22C -> base; cooler -> longer."""
    adj = ee.Image(t_ref).subtract(t_norm_C).divide(dT).round()
    return ee.Image(base_off).add(adj).clamp(lo, hi).rename("emergence_off_dekads")


def sos_to_planting_thermal(ee, sos_img, base_off, t_norm_C):
    """planting = SOS - spatially varying (temperature-based) emergence offset."""
    off = thermal_emergence_offset(ee, base_off, t_norm_C)
    return sos_img.subtract(off).rename("planting_dekad")


# ---------------- fuse phenology + rainfall into one SOS prior ----------------
def combined_ltn(ee, pheno_ltn_dekad, chirps_onset_ltn_dekad):
    """Phenology normal where available; fall back to rainfall-onset normal in its gaps."""
    return pheno_ltn_dekad.unmask(chirps_onset_ltn_dekad).rename("ltn_sos_dekad")


def build_ltn_prior(ee, aoi, sos_start, sos_end, years_pheno=(2001, 2024),
                    years_chirps=(2015, 2024), cycle=1, greenup_asset=None,
                    mode="rainfall_led"):
    """CHIRPS-onset LTN anchored, greenness/phenology-confirmed prior -> gating image (dekads).

    UNIFIED design (works for BOTH long and short rains): the DENSE CHIRPS rainfall-onset normal
    is the backbone/anchor; the phenology normal only CONFIRMS/refines it where it exists. This
    fronts the rainfall caveat (planting needs rain) and lets greenness enhance the detail, so a
    sparse second-cycle phenology can never mask the season out.

    mode:
      'rainfall_led'   (default, both seasons) -- rainfall onset primary; phenology averaged in
                       only where present. Robust when Greenup_2 (short rains) is sparse.
      'phenology_led'  (legacy) -- phenology primary, rainfall gap-fill. Only where Greenup is dense.

    years_chirps defaults to a recent ~10-yr window (fast); the 44-yr window is far heavier.
    """
    rain = chirps_onset_ltn(ee, aoi, years_chirps, sos_start, sos_end)
    pheno = phenology_ltn_dekad(ee, aoi, years_pheno, cycle, greenup_asset)
    if mode == "rainfall_led":
        # rainfall onset everywhere it exists; average with phenology only where both are present
        blended = rain.add(pheno).divide(2)          # masked where pheno absent
        return blended.unmask(rain).rename("ltn_sos_dekad")
    return combined_ltn(ee, pheno, rain)             # phenology primary, rainfall gap-fill
