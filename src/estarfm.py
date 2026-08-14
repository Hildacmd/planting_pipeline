"""ubESTARFM — unbiased Enhanced Spatial-Temporal Adaptive Reflectance Fusion, in pure GEE.

Purpose: replace the crude SAR-unmask gap-fill with a genuine spatiotemporal fusion that turns
the sparse-but-fine Sentinel-2 series (10 m, cloud-gapped) + dense-but-coarse MODIS series
(500 m daily, MCD43A4) into a GAP-FREE 10 m dekadal greenness series for cleaner SOS detection.

Algorithm (per target dekad tp, predicted from a fine/coarse base date t0):
  1. Local conversion coefficient V  = local regression slope of fine~coarse in a moving window
     (cov/var via reduceNeighborhood) — how fine responds to coarse change.
  2. Prediction    F(tp) = F(t0) + V · ( C(tp) − C(t0) )
  3. UNBIASED step (the 'ub'): force the coarse-aggregate of the prediction to equal the observed
     coarse at tp — residual = C(tp) − mean_coarsen(F_pred); F_ub = F_pred + residual.
     This removes ESTARFM's systematic additive bias.
  4. TWO-PAIR blend: predict from the nearest earlier base t0 and nearest later base t1, weight by
     inverse coarse-change magnitude, and combine.

GEE-tractable but HEAVY (moving-window regression at 10 m) — designed to run tiled / on a
commercial project. Nothing computes until an export/getInfo consumes the collection.

NOTE ON INDEX: MODIS has no red-edge, so the fusion runs on NDVI (available on both sensors).
The fused gap-free NDVI 'G' feeds detect_sos exactly like the previous greenness proxy. Keep the
NDRE cue for clear dates via `blend_ndre=True` if desired (optical NDRE where present).
"""
from __future__ import annotations


# ---------- dekadal fine (S2) and coarse (MODIS) NDVI ----------
def s2_ndvi_dekadal(ee, s2_ic):
    """Fine NDVI per dekad from the existing S2 composite collection (band 'F')."""
    return s2_ic.map(lambda im: im.select("NDVI").rename("F")
                     .copyProperties(im, ["dekad", "system:time_start"]))


def modis_ndvi_dekadal(ee, aoi, year, dekads=range(1, 37)):
    """Coarse gap-free NDVI per dekad from MODIS MCD43A4 (500 m, daily NBAR) -> band 'C'."""
    from .utils import dekad_to_start_date
    mc = (ee.ImageCollection("MODIS/061/MCD43A4").filterBounds(aoi)
            .filterDate(f"{year}-01-01", f"{year+1}-01-05"))

    def ndvi(img):
        nir = img.select("Nadir_Reflectance_Band2")
        red = img.select("Nadir_Reflectance_Band1")
        return nir.subtract(red).divide(nir.add(red).max(1e-6)).rename("C") \
                  .copyProperties(img, ["system:time_start"])
    mc = mc.map(ndvi)
    out = []
    for dk in dekads:
        s = ee.Date(dekad_to_start_date(year, dk).isoformat()); e = s.advance(10, "day")
        out.append(mc.filterDate(s, e).mean().rename("C")
                     .set({"dekad": dk, "system:time_start": s.millis()}))
    return ee.ImageCollection(out)


# ---------- ubESTARFM core ----------
def _rn_mean(ee, img, kernel):
    return img.reduceNeighborhood(ee.Reducer.mean(), kernel, optimization="boxcar")


def local_slope(ee, F, C, kernel):
    """Local conversion coefficient V = cov(F,C)/var(C) over the moving window."""
    mF = _rn_mean(ee, F, kernel).rename("mF")
    mC = _rn_mean(ee, C, kernel).rename("mC")
    mFC = _rn_mean(ee, F.multiply(C).rename("FC"), kernel).rename("mFC")
    mCC = _rn_mean(ee, C.multiply(C).rename("CC"), kernel).rename("mCC")
    cov = mFC.subtract(mF.multiply(mC))
    var = mCC.subtract(mC.multiply(mC)).max(1e-6)
    return cov.divide(var).clamp(0.1, 5.0).rename("V")


def predict_unbiased(ee, F0, C0, Ctp, V, coarse_proj, fine_scale=250, coarse_scale=500):
    """One-pair unbiased prediction of fine NDVI at tp.
    Unbiased step via focal-mean smoothing (approximates the coarse aggregate) rather than
    reduceResolution — the latter needs a fixed projection that a computed image lacks."""
    pred = F0.add(Ctp.subtract(C0).multiply(V)).rename("G")
    rad = max(1, int(round(coarse_scale / fine_scale)))       # window ~ one coarse cell
    pred_coarse = pred.reduceNeighborhood(ee.Reducer.mean(),
                                          ee.Kernel.square(rad, "pixels"), optimization="boxcar")
    resid = Ctp.subtract(pred_coarse)                         # coarse-grid bias
    return pred.add(resid).rename("G")                        # redistributed to the fine grid


def blend_pairs(ee, p0, p1, C0, C1, Ctp):
    """Temporal blend of the two one-pair predictions (inverse coarse-change weighting)."""
    w0 = ee.Image(1).divide(Ctp.subtract(C0).abs().add(1e-3))
    w1 = ee.Image(1).divide(Ctp.subtract(C1).abs().add(1e-3))
    W = w0.add(w1)
    return p0.multiply(w0).add(p1.multiply(w1)).divide(W).rename("G")


# ---------- driver: gap-free dekadal fused greenness ----------
def _by_dekad(ee, ic, dk):
    return ee.Image(ic.filter(ee.Filter.eq("dekad", dk)).first())


def build_fused_greenness_estarfm(ee, s2_ic, aoi, year, sos_start, sos_end,
                                  kernel_radius=10, base_step=2, pad=1, coarse_scale=500,
                                  fine_scale=250):
    """Return an ImageCollection of gap-free fused NDVI 'G' over [sos_start-pad, sos_end+pad].

    Base dekads (assumed to carry usable fine signal) are taken every `base_step` dekads across
    the range; each target dekad is predicted from its nearest earlier & later base and blended.
    """
    fine = s2_ndvi_dekadal(ee, s2_ic)
    coarse = modis_ndvi_dekadal(ee, aoi, year)
    kernel = ee.Kernel.square(radius=kernel_radius, units="pixels")
    coarse_proj = _by_dekad(ee, coarse, sos_start).projection()

    lo, hi = max(1, sos_start - pad), min(36, sos_end + pad)
    bases = list(range(lo, hi + 1, base_step))
    if bases[-1] != hi:
        bases.append(hi)

    out = []
    for d in range(lo, hi + 1):
        Ctp = _by_dekad(ee, coarse, d)
        b0 = max([b for b in bases if b <= d], default=bases[0])
        b1 = min([b for b in bases if b >= d], default=bases[-1])
        F0, C0 = _by_dekad(ee, fine, b0), _by_dekad(ee, coarse, b0)
        # fill any fine gaps at the base with the coarse value (keeps the graph defined)
        F0 = F0.unmask(C0)
        V0 = local_slope(ee, F0, C0, kernel)
        p0 = predict_unbiased(ee, F0, C0, Ctp, V0, coarse_proj, fine_scale)
        if b1 == b0:
            g = p0
        else:
            F1, C1 = _by_dekad(ee, fine, b1), _by_dekad(ee, coarse, b1)
            F1 = F1.unmask(C1)
            V1 = local_slope(ee, F1, C1, kernel)
            p1 = predict_unbiased(ee, F1, C1, Ctp, V1, coarse_proj, fine_scale)
            g = blend_pairs(ee, p0, p1, C0, C1, Ctp)
        g = g.clamp(-0.2, 1.0).rename("G").set({"dekad": d, "system:time_start": Ctp.get("system:time_start")})
        out.append(g)
    return ee.ImageCollection(out)


def build_fused_greenness_enhanced(ee, s2_ic, s1_ic, fpar_ic, aoi, year, sos_start, sos_end,
                                   fine_scale=250, calibrate=True):
    """ubESTARFM as an ENHANCEMENT, not a replacement: NDRE + FPAR stay the primary greenness on
    clear dates; the gap-free ubESTARFM NDVI fills cloud gaps, with SAR RVI as the last resort.

    calibrate=True: map the ubESTARFM NDVI into NDRE space per pixel (moment-matching against the
    clear NDRE dates) BEFORE using it as gap-fill, so the fill inherits NDRE's baseline/amplitude
    rather than NDVI's earlier-rising curve — fixes the ~1-dekad early bias of the raw NDVI fill."""
    est = build_fused_greenness_estarfm(ee, s2_ic, aoi, year, sos_start, sos_end, fine_scale=fine_scale)
    win = ee.List.sequence(sos_start, sos_end + 1)

    # per-pixel moments of NDRE (clear only) and ubESTARFM greenness over the window, for calibration
    ndre_coll = ee.ImageCollection(win.map(
        lambda dk: ee.Image(s2_ic.filter(ee.Filter.eq("dekad", dk)).first()).select("NDRE1")))
    est_coll = ee.ImageCollection(win.map(
        lambda dk: ee.Image(est.filter(ee.Filter.eq("dekad", dk)).first()).select("G")))
    mN, sN = ndre_coll.mean(), ndre_coll.reduce(ee.Reducer.stdDev()).rename("sd")
    mE, sE = est_coll.mean(), est_coll.reduce(ee.Reducer.stdDev()).rename("sd").max(1e-3)

    def fuse(dk):
        dk = ee.Number(dk)
        s2 = ee.Image(s2_ic.filter(ee.Filter.eq("dekad", dk)).first())
        s1 = ee.Image(s1_ic.filter(ee.Filter.eq("dekad", dk)).first())
        fp = ee.Image(fpar_ic.filter(ee.Filter.eq("dekad", dk)).first())
        ndre = s2.select("NDRE1")
        opt_g = (ndre.unitScale(0.0, 0.7).clamp(0, 1)
                 .add(fp.unitScale(0.0, 0.9).clamp(0, 1)).divide(2))          # PRIMARY: red-edge + FPAR
        estd = ee.Image(est.filter(ee.Filter.eq("dekad", dk)).first()).select("G")
        if calibrate:
            est_ndre = mN.add(estd.subtract(mE).multiply(sN.divide(sE)))     # NDVI → NDRE space
            est_g = est_ndre.unitScale(0.0, 0.7).clamp(0, 1)                 # same scaling as NDRE
        else:
            est_g = estd.unitScale(0.0, 0.9).clamp(0, 1)
        sar_g = s1.select("RVI").unitScale(0.1, 0.8).clamp(0, 1)             # last-resort SAR
        g = opt_g.unmask(est_g).unmask(sar_g).rename("G")                    # NDRE+FPAR → calib-ubESTARFM → SAR
        return g.set({"dekad": dk, "system:time_start": s2.get("system:time_start")})
    return ee.ImageCollection(win.map(fuse))
