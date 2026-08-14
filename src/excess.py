"""Excess-rain / waterlogging risk for maize — the wet-side companion to the deficit WRSI/WSI.

WRSI is a DEFICIT index (soil water capped at WHC; excess just runs off, no penalty), so waterlogging
is invisible to it. This module adds a stage-weighted waterlogging index and a seasonal wet-anomaly
(SPI-3 wet tail), classed like the drought side (% of maize area affected -> Watch/Alert/Critical).

STAGE WEIGHTING — basis
  For water DEFICIT, flowering is most critical (FAO-33 Ky: veg 0.4 / flo 1.5 / grf 0.5;
  Doorenbos & Kassam 1979). For EXCESS WATER the sensitivity ORDER is reversed — young maize is
  acutely waterlogging-intolerant (root hypoxia, seed rot, denitrification/N leaching, stand loss),
  so ESTABLISHMENT / EARLY-VEGETATIVE is the most damaging window:
    Zaidi et al. (2004) Field Crops Research 90:189-202 — early-vegetative the most susceptible stage;
    Ren et al. (2014)  Can. J. Plant Sci. 94:23-31     — waterlogging at V3 most damaging vs later;
    Kaur et al. (2020) Agronomy Journal 112:1475-1501  — review; early-stage sensitivity + N loss.
  There is NO FAO-33-equivalent standardized "waterlogging Ky", so the numeric weights below are a
  FIRST-PASS derived from the relative yield-loss ORDER in those papers (veg > flo > grf) and are
  flagged for calibration — analogous to the CPI heat/veg first-pass parameters.
"""
# waterlogging sensitivity weight by stage (first-pass; ordering per Zaidi 2004 / Ren 2014 / Kaur 2020)
EXCESS_W = {"veg": 1.00, "flo": 0.60, "grf": 0.35}   # establishment/vegetative worst
WET_DEKAD_MM = 100.0                                  # heavy dekadal-rain threshold (~waterlogging-prone), first-pass
SPI_WET = 1.5                                         # SPI-3 wet-tail threshold (McKee 1993 "very wet")


def _chirps_dekad_sum(ee, aoi, year, gd):
    """Dekadal CHIRPS total (mm) for global dekad gd (1..>36, year-wrap aware)."""
    from .utils import dekad_to_start_date
    yr = year if gd <= 36 else year + 1
    cdk = gd if gd <= 36 else gd - 36
    s = ee.Date(dekad_to_start_date(yr, cdk).isoformat())
    return ee.Image(ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterBounds(aoi)
                    .filterDate(s, s.advance(10, "day")).sum()).unmask(0)


def waterlogging_index(ee, aoi, planting_dekad_img, year, d_veg, d_flo, lgp,
                       sos_start, sos_end, wet_mm=WET_DEKAD_MM):
    """EXPERIMENTAL / ROADMAP — not a shipped layer. A fixed dekadal-mm threshold conflates
    normally-wet zones and well-drained convective storms with true waterlogging (it misranks
    semi-arid vs flooded highlands in testing), so the SHIPPED excess/waterlogging metric is the
    anomaly-based SPI-3 wet tail (`spi3_wet`). A defensible stage-weighted index needs a dekadal
    WET-ANOMALY basis (rain vs local climatology mean/SD) + calibration — future work; the stage
    weighting order (establishment-worst; Zaidi 2004 / Ren 2014 / Kaur 2020) carries over to it.

    Stage-weighted waterlogging index (0-100) = the PEAK stage-weighted wet-dekad exposure over the
    cycle. Waterlogging is an acute, short event, so we take the maximum over dekads (not a cycle mean,
    which dilutes it). Per dekad: excess = clamp((P − wet_mm)/wet_mm, 0, 1) (0 at threshold, 1 at ~2×),
    weighted by the stage waterlogging sensitivity (establishment/vegetative worst); the worst dekad
    sets the index. d_veg/d_flo = last dekad of vegetative/flowering, lgp = cycle length (dekads)."""
    peak = ee.Image(0.0)
    for gd in range(max(1, sos_start), sos_end + lgp + 1):
        dsp = ee.Image.constant(gd).subtract(planting_dekad_img)              # dekads since onset
        active = dsp.gte(0).And(dsp.lt(lgp))
        veg = active.And(dsp.lt(d_veg))
        flo = active.And(dsp.gte(d_veg)).And(dsp.lt(d_flo))
        grf = active.And(dsp.gte(d_flo))
        wstage = (veg.multiply(EXCESS_W["veg"]).add(flo.multiply(EXCESS_W["flo"]))
                     .add(grf.multiply(EXCESS_W["grf"])))                     # per-pixel stage weight (0 if inactive)
        P = _chirps_dekad_sum(ee, aoi, year, gd)
        excess = P.subtract(wet_mm).divide(wet_mm).clamp(0, 1)               # fractional excess over threshold
        peak = peak.max(excess.multiply(wstage))                             # worst stage-weighted dekad
    return peak.clamp(0, 1).multiply(100).rename("waterlog_idx")


AER_ET_MM_DAY = 4.0     # simple crop ET during the season (mm/day) — excess is rain-dominated
AER_START = 0.5         # anaerobiosis point: stress begins halfway from FC toward saturation
AER_SCALE_DAYS = 4.0    # peak consecutive stage-weighted aeration-days for a full (100) index (calibratable)
AER_W0 = 0.8            # soil water at planting, as a fraction of FC (dry-ish start)


def aeration_stress_index(ee, aoi, planting_dekad_img, year, d_veg, d_flo, lgp, sos_start, sos_end,
                          fc_mm, sat_mm, tau, et_mm_day=AER_ET_MM_DAY, scale_days=AER_SCALE_DAYS):
    """AquaCrop-style waterlogging index (0-100), soil-water-balance based [Raes et al. 2009].
    A DAILY root-zone balance (daily CHIRPS − ET, capped at saturation, gravitational water above FC
    draining at the soil's rate `tau`) tracks soil water W. Aeration stress starts near saturation
    (anaerobiosis point, AER_START of the way from FC to SAT) and is 1 at saturation. The metric is the
    PEAK of a CONSECUTIVE stage-weighted stress run that RESETS whenever the soil drains below the
    anaerobiosis point — so a soil that drains between storms never builds up (well-drained/sandy stays
    low), while one that stays saturated for days scores high. ~`scale_days` consecutive fully-saturated
    establishment-days = 100. fc_mm/sat_mm/tau from soil.build_hydro_mm."""
    from .utils import dekad_to_start_date
    ch = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterBounds(aoi)
    onset_day = planting_dekad_img.subtract(sos_start).multiply(10)
    start = ee.Date(dekad_to_start_date(year, sos_start).isoformat())
    ndays = int((sos_end - sos_start + lgp) * 10 + 2)
    thr = fc_mm.add(sat_mm.subtract(fc_mm).multiply(AER_START))            # anaerobiosis threshold (mm)
    W = fc_mm.multiply(AER_W0)                                             # dry-ish start
    run = ee.Image(0.0); peak = ee.Image(0.0)
    for i in range(ndays):
        d = start.advance(i, "day")
        P = ee.Image(ch.filterDate(d, d.advance(1, "day")).sum()).unmask(0)
        dsp = ee.Image.constant(i).subtract(onset_day)
        active = dsp.gte(0).And(dsp.lt(lgp * 10))
        W = W.add(P.subtract(et_mm_day)).max(0).min(sat_mm)
        above = W.subtract(fc_mm).max(0)
        W = fc_mm.add(above.multiply(ee.Image(1).subtract(tau)))          # drain at the soil's rate
        wet = W.gt(thr)                                                    # above anaerobiosis point?
        aer = W.subtract(thr).divide(sat_mm.subtract(thr).max(1e-3)).clamp(0, 1)
        ddk = dsp.divide(10)
        wstage = (ddk.lt(d_veg).multiply(EXCESS_W["veg"])
                  .add(ddk.gte(d_veg).And(ddk.lt(d_flo)).multiply(EXCESS_W["flo"]))
                  .add(ddk.gte(d_flo).multiply(EXCESS_W["grf"])))
        run = run.add(aer.multiply(wstage)).multiply(wet).multiply(active)  # accumulate; reset when it drains
        peak = peak.max(run)
    return peak.divide(scale_days).clamp(0, 1).multiply(100).rename("waterlog_idx")


def spi3_wet(ee, aoi, year, end_month, thresh=SPI_WET, clim_start=1981, clim_end=2020):
    """Seasonal wet-anomaly mask: SPI-3 >= thresh (very wet). Uses the same SPI-3 as the drought side."""
    from .spi import spi3
    return spi3(ee, aoi, year, end_month, clim_start, clim_end).gte(thresh).rename("spi3_wet")


def heavy_rain_days(ee, aoi, planting_dekad_img, year, sos_start, sos_end, lgp,
                    heavy_mm=50.0, window_stage=None, d_veg=None, d_flo=None):
    """Count of heavy-rain days (daily CHIRPS > heavy_mm) over the cycle, optionally restricted to a
    stage ('veg'|'flo'|'grf') via d_veg/d_flo. Intensity companion to the SPI-3 wet tail."""
    from .utils import dekad_to_start_date
    ch = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterBounds(aoi)
    onset_idx = planting_dekad_img.subtract(sos_start).multiply(10)
    start = ee.Date(dekad_to_start_date(year, sos_start).isoformat())
    ndays = int((sos_end - sos_start + lgp) * 10 + 2)
    lo = 0 if window_stage is None else (0 if window_stage == "veg" else d_veg * 10 if window_stage == "flo" else d_flo * 10)
    hi = lgp * 10 if window_stage is None else (d_veg * 10 if window_stage == "veg" else d_flo * 10 if window_stage == "flo" else lgp * 10)
    cnt = ee.Image(0)
    for i in range(ndays):
        d = start.advance(i, "day")
        p = ee.Image(ch.filterDate(d, d.advance(1, "day")).sum()).unmask(0)
        dsp = ee.Image.constant(i).subtract(onset_idx)
        inwin = dsp.gte(lo).And(dsp.lt(hi))
        cnt = cnt.add(p.gt(heavy_mm).And(inwin))
    return cnt.rename("heavy_rain_days")
