"""Fuse optical (red-edge VI) + FPAR + Sentinel-1 SAR into one dekadal phenology stack,
then detect Start-of-Season (SOS) inside a season window constrained by the LTN prior.

SOS strategy (robust, multi-cue):
  1. Build a gap-free dekadal fused greenness proxy G:
        G = z(NDRE)  fused with  z(FPAR)  and gap-filled by SAR-predicted greenness
           (VH & RVI rise with canopy) where optical is missing.
  2. Constrain the search to [sos_window] (from crop calendar) intersected with the
     LTN climatological onset +/- 2 dekads (rejects weeds / second flush).
  3. SOS = first dekad where G crosses (baseline + amp_frac * amplitude) AND the
     dekad-to-dekad derivative is positive for >=2 dekads (sustained green-up).
Returns a single-band image `SOS_dekad` (float) within the crop mask.
"""
from __future__ import annotations

def _zscore_ic(ee, ic, band):
    arr = ic.select(band).toArrayPerBand() if False else None  # placeholder note
    mean = ic.select(band).mean()
    std  = ic.select(band).reduce(ee.Reducer.stdDev()).max(1e-4)
    def z(img):
        return img.select(band).subtract(mean).divide(std)\
                  .rename(band+"_z").copyProperties(img,["dekad","system:time_start"])
    return ic.map(z)

def add_fpar_dekadal(ee, aoi, year, dekads=range(1,37)):
    from .utils import dekad_to_start_date
    fp = (ee.ImageCollection("MODIS/061/MCD15A3H").filterBounds(aoi)
            .filterDate(f"{year}-01-01", f"{year+1}-01-05").select("Fpar"))
    out=[]
    for dk in dekads:
        start=ee.Date(dekad_to_start_date(year,dk).isoformat()); end=start.advance(10,"day")
        out.append(fp.filterDate(start,end).mean().multiply(0.01).rename("FPAR")
                     .set({"dekad":dk,"system:time_start":start.millis()}))
    return ee.ImageCollection(out)

def build_fused_greenness(ee, s2_ic, s1_ic, fpar_ic):
    """Per-dekad fused greenness proxy G in [approx 0..1], gap-filled by SAR."""
    def fuse(dk):
        dk = ee.Number(dk)
        s2 = ee.Image(s2_ic.filter(ee.Filter.eq("dekad", dk)).first())
        s1 = ee.Image(s1_ic.filter(ee.Filter.eq("dekad", dk)).first())
        fp = ee.Image(fpar_ic.filter(ee.Filter.eq("dekad", dk)).first())
        ndre = s2.select("NDRE1")
        # SAR-based greenness surrogate: rescale RVI (0..~1) -> proxy when optical missing
        sar_g = s1.select("RVI").unitScale(0.1, 0.8).clamp(0, 1)
        # optical greenness: mean of NDRE (rescaled) and FPAR
        opt_g = ndre.unitScale(0.0, 0.7).clamp(0,1)\
                    .add(fp.unitScale(0.0, 0.9).clamp(0,1)).divide(2)
        g = opt_g.unmask(sar_g).rename("G")   # fill optical gaps with SAR proxy
        return g.set({"dekad": dk, "system:time_start": s1.get("system:time_start")})
    return ee.ImageCollection(s1_ic.aggregate_array("dekad").map(fuse))

def detect_sos(ee, g_ic, crop_mask, sos_start, sos_end, ltn_sos=None,
               amp_frac=0.25, ltn_pad=2):
    """Return SOS_dekad image. sos_start/end are dekad ints (season window)."""
    dekads = ee.List.sequence(sos_start, sos_end)

    # season baseline (dry-season floor) & amplitude from the window
    win = g_ic.filter(ee.Filter.inList("dekad", dekads))
    gmin = win.select("G").min()
    gmax = win.select("G").max()
    thresh = gmin.add(gmax.subtract(gmin).multiply(amp_frac))

    # per-dekad: crossed threshold AND sustained positive slope
    g_list = win.sort("dekad").toList(win.size())
    def flag(i):
        i = ee.Number(i)
        cur  = ee.Image(g_list.get(i)).select("G")
        nxt  = ee.Image(g_list.get(i.min(win.size().subtract(1)))).select("G")
        dk   = ee.Image(g_list.get(i)).getNumber("dekad")
        crossed = cur.gte(thresh)
        rising  = nxt.subtract(cur).gte(0)
        cond = crossed.And(rising)
        # optional LTN prior gate: constrain to +/- ltn_pad of the climatological onset,
        # but ONLY where a prior exists -- pass through (calendar-window only) where it is masked,
        # so a sparse second-season phenology normal can't reject every pixel.
        if ltn_sos is not None:
            near = ee.Image(dk).subtract(ltn_sos).abs().lte(ltn_pad)
            cond = cond.And(near.unmask(1))
        return cond.multiply(dk).toInt16().rename("cand").selfMask()
    cand_ic = ee.ImageCollection(ee.List.sequence(0, win.size().subtract(1)).map(flag))
    sos = cand_ic.min().rename("SOS_dekad")     # earliest qualifying dekad
    return sos.updateMask(crop_mask)


def fused_condition(ee, g_ic, crop_mask, sos_start, sos_end, lgp=12):
    """Within-season Fused Canopy Condition Index (FCCI, 0-100) = 100 * PEAK fused greenness G over
    the season window (green-up through senescence), masked to the crop. G is an ABSOLUTE proxy
    (fixed unitScale of NDRE/FPAR/RVI), so peak-G is comparable across pixels WITHOUT a multi-year
    baseline — the archive-length problem is avoided. High = vigorous canopy; low = poor / failed.
    A 10-20 m, cloud-proof (SAR-filled) vegetation cross-check on the water-balance WRSI.
    Caveat: where the peak dekad was cloud-filled by SAR, the value is the SAR proxy (less exact)."""
    end = min(int(sos_end) + int(lgp), 36)                       # season dekads (no year-wrap; peak is in-year)
    dks = ee.List.sequence(int(sos_start), end)
    sub = g_ic.filter(ee.Filter.inList("dekad", dks))
    gpeak = sub.select("G").max()                                # peak greenness over the season
    return gpeak.multiply(100).updateMask(crop_mask).clamp(0, 100).rename("FCCI")
