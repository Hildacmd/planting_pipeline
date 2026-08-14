"""Statistics + skill scoring for the planting-window pipeline.

Four metric families, all aggregated to GAUL admin-1 and to a national row:

  1. Descriptive     - planting-dekad distribution: mode / P10 / P50 / P90 / mean / std / count
  2. Signal strength - SOS detection confidence: seasonal greenness amplitude, % crop pixels detected
  3. Skill vs FEWS/FAO calendar - estimate vs the indicative planting window (from season_calendar.csv):
        hit_rate   = fraction of crop pixels whose planting dekad falls inside the calendar window
        bias_dek   = mean(estimate - window_centre)   (+ = later than calendar, - = earlier)
        mae_dek    = mean(|estimate - window_centre|)  (magnitude of departure, in dekads)
  4. WRSI performance - mean WRSI, mean deficit (mm), % crop area failing (class<=2) / good (class>=4)

`describe_planting` uses mode/percentile reducers; `means_metric_image` bundles every
mean-reducible metric into one multiband image so the whole lot is one reduceRegions pass.
"""
from __future__ import annotations


# ---------------- pixel-level metric images ----------------
def signal_amplitude(ee, g_ic, sos_img, crop_mask, sos_start, sos_end):
    """Seasonal greenness amplitude (gmax-gmin in the SOS window) + SOS-detected flag,
    both masked to the crop. amplitude ~ clarity of the green-up signal."""
    dekads = ee.List.sequence(sos_start, sos_end)
    win = g_ic.filter(ee.Filter.inList("dekad", dekads)).select("G")
    amp = win.max().subtract(win.min()).updateMask(crop_mask).rename("amp")
    # 1 where an SOS was detected inside the crop mask, 0 elsewhere in the crop
    detected = sos_img.mask().rename("detected").unmask(0).updateMask(crop_mask)
    return amp.addBands(detected)


def skill_metric_image(ee, planting_img, crop_mask, win_start, win_end):
    """Per-pixel skill vs the indicative calendar window [win_start, win_end] (dekads)."""
    centre = (win_start + win_end) / 2.0
    pl = planting_img.updateMask(crop_mask)
    in_window = pl.gte(win_start).And(pl.lte(win_end)).rename("hit")
    bias = pl.subtract(centre).rename("bias")
    abserr = pl.subtract(centre).abs().rename("abserr")
    return in_window.addBands(bias).addBands(abserr)


def wrsi_metric_image(ee, wrsi_img, deficit_img, wrsi_class_img, crop_mask):
    """Per-pixel WRSI performance metrics, masked to the crop."""
    fail = wrsi_class_img.lte(2).rename("fail")     # poor / failure
    good = wrsi_class_img.gte(4).rename("good")     # good / no deficit
    return (wrsi_img.rename("WRSI")
            .addBands(deficit_img.rename("deficit_mm"))
            .addBands(fail).addBands(good)
            .updateMask(crop_mask))


def means_metric_image(ee, planting_img, crop_mask, win_start, win_end,
                       g_ic=None, sos_img=None,
                       wrsi_img=None, deficit_img=None, wrsi_class_img=None,
                       sos_start=None, sos_end=None):
    """One multiband image of every mean-reducible metric (skill + signal + WRSI).
    WRSI / signal bands are added only if their inputs are supplied."""
    img = skill_metric_image(ee, planting_img, crop_mask, win_start, win_end)
    if g_ic is not None and sos_img is not None:
        img = img.addBands(signal_amplitude(ee, g_ic, sos_img, crop_mask, sos_start, sos_end))
    if wrsi_img is not None:
        img = img.addBands(wrsi_metric_image(ee, wrsi_img, deficit_img, wrsi_class_img, crop_mask))
    return img


# ---------------- zonal reductions ----------------
def describe_planting(ee, planting_img, crop_mask, admin_fc, scale=100):
    """Planting-dekad distribution per admin (mode/p10/p50/p90/mean/std/count)."""
    r = (ee.Reducer.mode()
         .combine(ee.Reducer.percentile([10, 50, 90]), sharedInputs=True)
         .combine(ee.Reducer.mean(), sharedInputs=True)
         .combine(ee.Reducer.stdDev(), sharedInputs=True)
         .combine(ee.Reducer.count(), sharedInputs=True))
    return (planting_img.updateMask(crop_mask).rename("pd")
            .reduceRegions(collection=admin_fc, reducer=r, scale=scale))


def zonal_means(ee, metric_img, admin_fc, scale=100):
    """Mean of every band in metric_img per admin (hit/bias/abserr/amp/detected/WRSI/...)."""
    return metric_img.reduceRegions(collection=admin_fc,
                                    reducer=ee.Reducer.mean(), scale=scale)


# ---------------- national rollup (small, getInfo-able) ----------------
def national_summary(ee, planting_img, metric_img, crop_mask, aoi, scale=250):
    """Return a plain dict of national numbers (triggers compute; keep scale coarse)."""
    pl = planting_img.updateMask(crop_mask).rename("pd")
    dist = pl.reduceRegion(
        reducer=(ee.Reducer.mode()
                 .combine(ee.Reducer.percentile([10, 50, 90]), sharedInputs=True)
                 .combine(ee.Reducer.mean(), sharedInputs=True)
                 .combine(ee.Reducer.count(), sharedInputs=True)),
        geometry=aoi, scale=scale, maxPixels=1e12, bestEffort=True)
    means = metric_img.reduceRegion(
        reducer=ee.Reducer.mean(), geometry=aoi, scale=scale,
        maxPixels=1e12, bestEffort=True)
    return ee.Dictionary(dist).combine(ee.Dictionary(means), overwrite=False)
