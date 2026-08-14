"""Two-way WRSI link.

(a) wrsi_onset(): independent CHIRPS rainfall-based onset -> cross-check the RS SOS.
    Onset rule (FEWS/GeoWRSI convention): first dekad with >=25 mm, followed by two
    dekads totalling >=20 mm (no long dry spell). Rejects false starts.
(b) run_wrsi(): compute a simplified crop Water Requirement Satisfaction Index using the
    CROP-SPECIFIC planting dekad from this pipeline as the start-of-cycle, instead of a
    generic onset -> better water-balance skill. (For operational use, feed the exported
    planting dekad raster into GeoWRSI 3.x as the SOS grid.)
"""
from __future__ import annotations

def chirps_dekadal(ee, aoi, year):
    from .utils import dekad_to_start_date
    ch = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterBounds(aoi)
    out=[]
    for dk in range(1,37):
        s=ee.Date(dekad_to_start_date(year,dk).isoformat()); e=s.advance(10,"day")
        out.append(ch.filterDate(s,e).sum().rename("P")
                     .set({"dekad":dk,"system:time_start":s.millis()}))
    return ee.ImageCollection(out)

# ---- dekadal PET (for the FEWS P/PET >= 0.5 onset gate) ----
def pet_dekadal(ee, aoi, year):
    """Dekadal PET (=ET0, mm) via Hargreaves, keyed by 'dekad'. Reuses the WRSI ET0 builder."""
    from .wrsi_waterbalance import hargreaves_et0_dekadal
    return hargreaves_et0_dekadal(ee, aoi, year, 0).map(
        lambda im: im.set("dekad", im.get("gd")))

# ---- operational running dekad: 6 days observed CHIRPS + 4 days GFS forecast ----
def dekad_precip_6obs_4fc(ee, aoi, year, dekad, obs_days=6, fc_days=4):
    """Running-dekad precipitation (mm) = obs_days of CHIRPS + fc_days of NOAA/GFS forecast.
    Use for near-real-time onset on the CURRENT (incomplete) dekad; historical dekads use full CHIRPS."""
    from .utils import dekad_to_start_date
    s = ee.Date(dekad_to_start_date(year, dekad).isoformat())
    mid = s.advance(obs_days, "day"); end = s.advance(obs_days + fc_days, "day")
    obs = (ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterBounds(aoi)
             .filterDate(s, mid).select("precipitation").sum())
    gfs = (ee.ImageCollection("NOAA/GFS0P25").filterBounds(aoi)
             .filterDate(mid, end).select("total_precipitation_surface").sum())
    return obs.add(gfs).rename("P").set({"dekad": dekad, "system:time_start": s.millis()})

def chirps_dekadal_with_forecast(ee, aoi, year, current_dekad, obs_days=6, fc_days=4):
    """Full-year dekadal precip where the CURRENT dekad is the 6-obs/4-forecast blend."""
    base = chirps_dekadal(ee, aoi, year).filter(ee.Filter.neq("dekad", current_dekad))
    return base.merge(ee.ImageCollection(
        [dekad_precip_6obs_4fc(ee, aoi, year, current_dekad, obs_days, fc_days)]))

def chirps_clim_dekadal(ee, aoi, dekads, years):
    """Climatological dekadal CHIRPS (mm) — mean of the dekad sum over `years`, per dekad.
    Feeds wrsi_onset to establish the LTN (long-term-normal) rainfall onset window."""
    from .utils import dekad_to_start_date
    out = []
    for dk in dekads:
        yrs = []
        for y in years:
            s = ee.Date(dekad_to_start_date(y, dk).isoformat())
            yrs.append(ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterBounds(aoi)
                         .filterDate(s, s.advance(10, "day")).sum())
        out.append(ee.ImageCollection(yrs).mean().rename("P").set({"dekad": dk}))
    return ee.ImageCollection(out)


def wrsi_onset(ee, chirps_ic, search_start, search_end, pet_ic=None, ppet_thresh=0.5):
    """Onset dekad within the window. FEWS 25/20 mm rule, optionally AND'd with P/PET >= ppet_thresh
    (pass pet_ic from pet_dekadal to enable the agroclimatic gate)."""
    dks = ee.List.sequence(search_start, search_end)
    lst = chirps_ic.filter(ee.Filter.inList("dekad", dks)).sort("dekad").toList(999)
    def flag(i):
        i=ee.Number(i)
        p0=ee.Image(lst.get(i)).select("P")
        p1=ee.Image(lst.get(i.add(1).min(lst.size().subtract(1)))).select("P")
        p2=ee.Image(lst.get(i.add(2).min(lst.size().subtract(1)))).select("P")
        dk=ee.Image(lst.get(i)).getNumber("dekad")
        cond=p0.gte(25).And(p1.add(p2).gte(20))                     # 25/20 mm rule
        if pet_ic is not None:                                      # + P/PET >= 0.5 gate
            pet0=ee.Image(pet_ic.filter(ee.Filter.eq("dekad", dk)).first()).select("ET0")
            cond=cond.And(p0.divide(pet0.max(1e-3)).gte(ppet_thresh))
        return cond.multiply(dk).toInt16().rename("onset").selfMask()
    ic=ee.ImageCollection(ee.List.sequence(0,lst.size().subtract(3)).map(flag))
    return ic.min().rename("wrsi_onset_dekad")

def run_wrsi(ee, aoi, year, planting_dekad_img, crop, kc_cfg, soil_cfg,
             sos_start, sos_end, chirps_ic=None, whc_img=None):
    """Full FAO-56/33 WRSI in pure GEE (no GeoWRSI hand-off).
    Delegates to wrsi_waterbalance.run_wrsi_fao33 -> dict of images incl. WRSI + classes."""
    from .wrsi_waterbalance import run_wrsi_fao33, classify_wrsi
    res = run_wrsi_fao33(ee, aoi, year, planting_dekad_img, crop, kc_cfg, soil_cfg,
                         sos_start, sos_end, chirps_ic=chirps_ic, whc_img=whc_img)
    res["wrsi_class"] = classify_wrsi(ee, res["WRSI"])
    return res


# ---- inception-report false-start rejection: post-onset dry-spell length gate --------------------
def max_dry_spell_after_onset(ee, aoi, planting_dekad_img, year, dk_lo, dk_hi,
                              window_days=20, dry_mm=1.0):
    """Per-pixel LONGEST run of consecutive dry days (daily CHIRPS < dry_mm) within `window_days`
    after the pixel's planting dekad. dk_lo..dk_hi bound the daily scan to the plausible onset dekads.

    A contiguous [onset, onset+window) block per pixel: the running streak `cur` increments on dry
    days and resets on wet days *inside* the window, and is forced to 0 outside it (so pre/post-window
    days can't corrupt the streak); `mx` keeps the maximum. Returns an image 'max_dry_days'."""
    from .utils import dekad_to_start_date
    ch = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterBounds(aoi)
    onset_idx = planting_dekad_img.subtract(dk_lo).multiply(10)      # day-index of onset within scan
    start = ee.Date(dekad_to_start_date(year, dk_lo).isoformat())
    ndays = int((dk_hi - dk_lo) * 10 + window_days + 2)
    cur = ee.Image(0); mx = ee.Image(0)
    for i in range(ndays):
        d = start.advance(i, "day")
        p = ee.Image(ch.filterDate(d, d.advance(1, "day")).sum()).unmask(0)
        dry = p.lt(dry_mm)
        dsp = ee.Image.constant(i).subtract(onset_idx)              # days since this pixel's onset
        active = dsp.gte(0).And(dsp.lt(window_days))
        cur = cur.add(1).multiply(dry).multiply(active)            # streak within window; 0 outside
        mx = mx.max(cur)
    return mx.rename("max_dry_days")


def onset_accum_mm(ee, aoi, planting_dekad_img, year, dk_lo, dk_hi, trigger_days=5):
    """Per-pixel rain total (mm) over the first `trigger_days` days after the pixel's onset dekad
    (the 'high-confidence 5-day' germination window)."""
    from .utils import dekad_to_start_date
    ch = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterBounds(aoi)
    onset_idx = planting_dekad_img.subtract(dk_lo).multiply(10)
    start = ee.Date(dekad_to_start_date(year, dk_lo).isoformat())
    ndays = int((dk_hi - dk_lo) * 10 + trigger_days + 2)
    acc = ee.Image(0)
    for i in range(ndays):
        d = start.advance(i, "day")
        p = ee.Image(ch.filterDate(d, d.advance(1, "day")).sum()).unmask(0)
        dsp = ee.Image.constant(i).subtract(onset_idx)
        acc = acc.add(p.multiply(dsp.gte(0).And(dsp.lt(trigger_days))))   # sum only the trigger window
    return acc.rename("onset_accum_mm")


def dryspell_false_start(ee, aoi, planting_dekad_img, year, dk_lo, dk_hi,
                         max_dry_days=7, window_days=20, dry_mm=1.0,
                         trigger_days=5, trigger_mm=20.0):
    """False-start mask (1 = keep, 0 = reject) — inception-report "5 + 7" rule, both halves:
      (a) germination trigger : >= trigger_mm rain over the first trigger_days (default 20 mm / 5 d)
      (b) continuity          : NO dry spell > max_dry_days within window_days (default 7 d / 20 d)
    Complements the P/PET onset gate (adequacy). Set trigger_mm=0 to disable the accumulation half."""
    mds = max_dry_spell_after_onset(ee, aoi, planting_dekad_img, year, dk_lo, dk_hi,
                                    window_days=window_days, dry_mm=dry_mm)
    ok = mds.lte(max_dry_days)                                            # (b) continuity
    if trigger_mm and trigger_mm > 0:
        acc = onset_accum_mm(ee, aoi, planting_dekad_img, year, dk_lo, dk_hi, trigger_days=trigger_days)
        ok = ok.And(acc.gte(trigger_mm))                                 # (a) germination trigger
    return ok.rename("dryspell_ok")
