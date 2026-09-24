#!/usr/bin/env python3
"""Reproject the crop-type masks to a metric CRS, one per country.

    python reproject/reproject_crs.py                      # UTM, every country
    python reproject/reproject_crs.py --crs aea            # Africa Albers Equal Area
    python reproject/reproject_crs.py --country Sudan Kenya
    python reproject/reproject_crs.py --verify             # area check only, writes nothing

**Two target CRS, for two different jobs.**

`utm` gives each country the UTM zone containing its centroid. A cell is 100 by 100 m, so a
pixel reads as one hectare and distances and areas are in metres. This is the CRS national
partners work in. **But every country in the series spans two to four UTM zones**, and UTM is
conformal, not equal-area, so forcing one zone inflates area away from the central meridian:
Sudan by 3.5 % at its western edge, Ethiopia 2.4 %, South Sudan 2.3 %, Tanzania 1.6 %. The
smaller countries stay under 0.5 %.

`aea` gives Africa Albers Equal Area Conic (standard parallels 20 S and 23 N, central meridian
25 E), which preserves area exactly everywhere. **Use this one when the comparison being made is
about area**, which is what the crop-type masks are mostly used for.

**Whichever CRS you pick, area stays exact**, because a `pixel_area_ha` raster is written
alongside in the same grid, computed **geodesically** on the WGS 84 ellipsoid rather than from
the projection. Area is then always

    area (ha) = sum( frac_crop / 100 x pixel_area_ha )

and never a pixel count. `--verify` prints that sum against the source-CRS figure, and against
the naive one-hectare-per-pixel count, so the size of each error is on the record rather than
assumed.

**Resampling is nearest neighbour for every band.** The source grid is 0.0009 degrees, about
100 m, and the target is 100 m, so this is a near one-to-one warp with nothing to aggregate.
Averaging a near-1:1 warp does not conserve the quantity, it smears each value into its
neighbours: in testing that inflated Rwanda's mapped crop area by 7 to 17 %, and its wheat, which
sits in small scattered patches, by 168 %. Nearest neighbour copies each value once. It is also
the only correct choice for the class codes. Use `average` only when genuinely coarsening, for
example 100 m to 1 km.
"""
import argparse, datetime as _dt, glob, os, sys
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from pyproj import Geod

H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(H)
GEOD = Geod(ellps="WGS84")
RES = 100.0                       # metres

COUNTRIES = ["Ethiopia", "Kenya", "Uganda", "Tanzania", "Rwanda_SPAM2020", "Burundi_SPAM2020",
             "Somalia_SPAM2020", "South_Sudan", "Sudan", "Eritrea", "Djibouti"]
AEA = ("+proj=aea +lat_1=20 +lat_2=-23 +lat_0=0 +lon_0=25 "
       "+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs")          # Africa Albers Equal Area
# bands resampled by nearest neighbour: class codes and counts, where an average is meaningless
CATEGORICAL = ("mask_", "dominant", "nvotes")
SKIP = ("pixel_area_ha",)         # regenerated in the target grid, never resampled
# These rasters declare NoData = 0 so that QGIS does not draw a black background, although for a
# crop fraction 0 means "no crop here" rather than "no data". That distinction matters for an
# averaging resampler, which would skip the zero neighbours and inflate every crop-patch edge.
# It does not matter for nearest neighbour, which selects a value rather than blending, so no
# sentinel or nodata juggling is needed here. Keep this in mind before changing the resampler.
AREA_BEARING = ("frac_", "cl_pct")


def utm_epsg(bounds):
    clon, clat = (bounds.left + bounds.right) / 2, (bounds.bottom + bounds.top) / 2
    zone = int((clon + 180) // 6) + 1
    return (32600 if clat >= 0 else 32700) + zone


def pixel_area_ha(dst_crs, transform, width, height, samples=192):
    """True geodesic hectares for every cell of the target grid.

    Computed on the WGS 84 ellipsoid rather than from the projection, so it absorbs whatever
    distortion the projection carries and keeps `sum(frac x pixel_area)` exact in any CRS.

    Cell area varies smoothly across a projected grid, so it is evaluated on a coarse lattice of
    about `samples` by `samples` points and interpolated to full resolution. Evaluating every
    pixel directly is exact but needlessly slow: Ethiopia alone is over a hundred million cells.
    The interpolation error is far below the fourth decimal of a hectare.

    An equal-area projection is short-circuited: every cell is the same size by construction.
    """
    from pyproj import CRS as _CRS, Transformer
    from scipy.interpolate import RegularGridInterpolator

    if "aea" in str(dst_crs).lower() or getattr(_CRS.from_user_input(dst_crs), "name", "").lower().find("albers") >= 0:
        cell = abs(transform.a * transform.e) / 1e4                     # m2 -> ha, constant
        return np.full((height, width), cell, "float32")

    inv = Transformer.from_crs(dst_crs, 4326, always_xy=True)
    a_, b_, c_, d_, e_, f_ = (transform.a, transform.b, transform.c,
                              transform.d, transform.e, transform.f)
    rs = np.unique(np.linspace(0, height - 1, min(samples, height)).astype(int))
    cs = np.unique(np.linspace(0, width - 1, min(samples, width)).astype(int))
    C, R = np.meshgrid(cs, rs)
    x0 = c_ + a_ * C + b_ * R
    y0 = f_ + d_ * C + e_ * R
    lon0, lat0 = inv.transform(x0, y0)
    lonx, latx = inv.transform(x0 + a_, y0 + d_)        # one cell east
    lony, laty = inv.transform(x0 + b_, y0 + e_)        # one cell south
    # geodesic edge lengths; Geod.inv is vectorised, unlike polygon_area_perimeter
    _, _, wx = GEOD.inv(lon0, lat0, lonx, latx)
    _, _, wy = GEOD.inv(lon0, lat0, lony, laty)
    coarse = (np.abs(wx) * np.abs(wy) / 1e4).astype("float64")         # m2 -> ha

    interp = RegularGridInterpolator((rs.astype(float), cs.astype(float)), coarse,
                                     bounds_error=False, fill_value=None)
    rr = np.arange(height, dtype=float)
    out = np.empty((height, width), "float32")
    cc = np.arange(width, dtype=float)
    for i in range(0, height, 2048):                                   # chunked, to bound memory
        j = min(i + 2048, height)
        RR, CC = np.meshgrid(rr[i:j], cc, indexing="ij")
        out[i:j] = interp(np.stack([RR.ravel(), CC.ravel()], 1)).reshape(j - i, width)
    return out


def resampling_for(desc):
    """Nearest neighbour for every band, and the reason matters.

    The source grid is 0.0009 degrees, which is about 100 m, and the target grid is 100 m, so the
    reprojection is very nearly one cell to one cell. There is nothing to aggregate. Asking GDAL
    to `average` a near-1:1 warp does not conserve the quantity: it smears each value into the
    neighbouring cells, which inflated Rwanda's mapped crop area by 7 to 17 % in testing, and
    Rwandan wheat, which sits in small scattered patches where the smear has the most edge to
    work on, by 168 %. Nearest neighbour copies each value once and conserves the total to within
    the ratio of the cell sizes.

    Average would be the right choice when genuinely coarsening, for example 100 m to 1 km. It is
    the wrong choice here."""
    return Resampling.nearest


def zeros_are_data(desc):
    """True where a 0 means a real value (no crop) rather than absence of data. Only relevant if
    the resampler is ever changed away from nearest neighbour."""
    return any(k in (desc or "").lower() for k in AREA_BEARING)


# Provenance. Every derived raster carries these GDAL tags, and the guard below refuses to
# reproject anything that already has them. The EPSG:4326 set is the authoritative one: each
# reprojection costs about 0.03 % in resampling, and reprojecting a reprojection compounds it.
DERIVED_TAG = "CTM_DERIVED_FROM"
RULE = ("Derived product. The EPSG:4326 set under <Country>/outputs/ is authoritative. "
        "Do not reproject this file again: each warp costs about 0.03 % in resampling and the "
        "error compounds. Reproject from the EPSG:4326 source instead. "
        "Area = sum(frac/100 x pixel_area_ha), never a pixel count.")


def refuse_if_derived(path):
    """Guard: a derived raster is never a valid input to another reprojection."""
    with rasterio.open(path) as r:
        tags = r.tags()
    if DERIVED_TAG in tags:
        raise SystemExit(
            f"\nREFUSED: {path}\n  is itself a derived product, reprojected from\n"
            f"  {tags[DERIVED_TAG]}\n  in {tags.get('CTM_TARGET_CRS', '?')} on "
            f"{tags.get('CTM_CREATED', '?')}.\n"
            f"  Reproject from the authoritative EPSG:4326 source instead. Each warp costs about\n"
            f"  0.03 % in resampling and reprojecting a reprojection compounds it.\n")


def provenance(src_path, dst_crs, resampling="nearest"):
    return {
        DERIVED_TAG: os.path.relpath(src_path, ROOT),
        "CTM_SOURCE_CRS": "EPSG:4326",
        "CTM_TARGET_CRS": str(dst_crs),
        "CTM_RESAMPLING": resampling,
        "CTM_CREATED": _dt.date.today().isoformat(),
        "CTM_AUTHORITATIVE": "EPSG:4326 set under <Country>/outputs/",
        "CTM_NOTE": RULE,
    }


def common_grid(paths, dst_crs):
    """One target grid per country, from the union of the source extents.

    The source rasters of a country do not all share an extent - Sudan's fraction and confidence
    layers differ by eight rows - so warping each file on its own would produce layers that do
    not stack. Deriving the grid once means every output aligns pixel for pixel and one
    pixel-area raster serves them all."""
    lefts, bottoms, rights, tops = [], [], [], []
    for p in paths:
        with rasterio.open(p) as r:
            t, w, h = calculate_default_transform(r.crs, dst_crs, r.width, r.height,
                                                  *r.bounds, resolution=RES)
            lefts.append(t.c); tops.append(t.f)
            rights.append(t.c + w * RES); bottoms.append(t.f - h * RES)
    left, top = min(lefts), max(tops)
    right, bottom = max(rights), min(bottoms)
    width = int(round((right - left) / RES)); height = int(round((top - bottom) / RES))
    return rasterio.Affine(RES, 0, left, 0, -RES, top), width, height


def reproject_file(src_path, dst_path, dst_crs, grid):
    transform, width, height = grid
    with rasterio.open(src_path) as src:
        prof = src.profile.copy()
        prof.update(crs=dst_crs, transform=transform, width=width, height=height,
                    compress="deflate", predictor=2, tiled=True, blockxsize=512, blockysize=512,
                    BIGTIFF="IF_SAFER")
        with rasterio.open(dst_path, "w", **prof) as dst:
            for i in range(1, src.count + 1):
                desc = src.descriptions[i - 1] if src.descriptions else ""
                reproject(source=rasterio.band(src, i), destination=rasterio.band(dst, i),
                          src_transform=src.transform, src_crs=src.crs,
                          dst_transform=transform, dst_crs=dst_crs,
                          resampling=resampling_for(desc),
                          src_nodata=src.nodata, dst_nodata=src.nodata)
            dst.descriptions = src.descriptions
            dst.update_tags(**provenance(src_path, dst_crs))
        return transform, width, height, prof


def crop_area_ha(frac_path, area_path):
    """sum(frac/100 x pixel_area_ha) per band, the only correct way to get area."""
    out = {}
    with rasterio.open(frac_path) as f, rasterio.open(area_path) as a:
        for i in range(1, f.count + 1):
            name = (f.descriptions[i - 1] if f.descriptions else f"band{i}")
            fr = f.read(i, masked=True).filled(0).astype("float64") / 100.0
            ar = a.read(1, masked=True).filled(0).astype("float64")
            out[name] = float((fr * ar).sum())
    return out


def naive_area_ha(frac_path):
    """The wrong way, reported for comparison: every pixel treated as exactly one hectare."""
    out = {}
    with rasterio.open(frac_path) as f:
        for i in range(1, f.count + 1):
            name = (f.descriptions[i - 1] if f.descriptions else f"band{i}")
            fr = f.read(i, masked=True).filled(0).astype("float64") / 100.0
            out[name] = float(fr.sum())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crs", default="utm", choices=["utm", "aea"])
    ap.add_argument("--country", nargs="*", default=None)
    ap.add_argument("--verify", action="store_true", help="area check only; write nothing")
    a = ap.parse_args()
    todo = a.country or COUNTRIES
    rows = []

    for c in todo:
        src_dir = f"{ROOT}/{c}/outputs"
        tifs = sorted(p for p in glob.glob(f"{src_dir}/*.tif")
                      if not any(s in os.path.basename(p) for s in SKIP))
        for p in tifs:
            refuse_if_derived(p)
        if not tifs:
            print(f"{c:<18} no GeoTIFFs"); continue
        with rasterio.open(tifs[0]) as r:
            bounds, iso = r.bounds, os.path.basename(tifs[0]).split("_")[0]
        dst_crs = AEA if a.crs == "aea" else f"EPSG:{utm_epsg(bounds)}"
        tag = "aea" if a.crs == "aea" else f"utm{utm_epsg(bounds) % 100}"
        out_dir = f"{src_dir}/{tag}"
        os.makedirs(out_dir, exist_ok=True)

        frac_src = next((p for p in tifs if "crop_fraction" in p), None)
        print(f"\n{c}  ->  {dst_crs}   ({len(tifs)} rasters)")
        if not a.verify:
            grid = common_grid(tifs, dst_crs)
            for p in tifs:
                dst = f"{out_dir}/{os.path.basename(p).replace('_100m', f'_100m_{tag}')}"
                t, w, h, prof = reproject_file(p, dst, dst_crs, grid)
                print(f"   {os.path.basename(dst):<46} {w} x {h}")
            # the geodesic pixel-area companion, on the same grid
            t, w, h = grid
            pa = pixel_area_ha(dst_crs, t, w, h)
            ap_path = f"{out_dir}/{iso}_pixel_area_ha_100m_{tag}.tif"
            with rasterio.open(ap_path, "w", driver="GTiff", height=h, width=w, count=1,
                               dtype="float32", crs=dst_crs, transform=t, nodata=0,
                               compress="deflate", predictor=3, tiled=True,
                               blockxsize=512, blockysize=512, BIGTIFF="IF_SAFER") as d:
                d.write(pa, 1); d.set_band_description(1, "pixel_area_ha")
                d.update_tags(**provenance(f"{src_dir}/{iso}_pixel_area_ha_100m.tif", dst_crs,
                                           resampling="recomputed geodesically, not resampled"))
            print(f"   {os.path.basename(ap_path):<46} geodesic, mean {pa[pa>0].mean():.4f} ha/px")

        if frac_src:
            src_area = f"{src_dir}/{iso}_pixel_area_ha_100m.tif"
            dst_frac = f"{out_dir}/{os.path.basename(frac_src).replace('_100m', f'_100m_{tag}')}"
            dst_area = f"{out_dir}/{iso}_pixel_area_ha_100m_{tag}.tif"
            if os.path.exists(dst_frac) and os.path.exists(dst_area) and os.path.exists(src_area):
                s = crop_area_ha(frac_src, src_area)
                t_ = crop_area_ha(dst_frac, dst_area)
                n_ = naive_area_ha(dst_frac)
                for k in s:
                    rows.append(dict(country=c, crop=k, source_ha=round(s[k]),
                                     proj_ha=round(t_.get(k, 0)), naive_ha=round(n_.get(k, 0)),
                                     proj_err_pct=round(100 * (t_.get(k, 0) - s[k]) / max(s[k], 1), 2),
                                     naive_err_pct=round(100 * (n_.get(k, 0) - s[k]) / max(s[k], 1), 2)))
    if rows:
        import pandas as pd
        df = pd.DataFrame(rows)
        p = f"{H}/area_check_{a.crs}.csv"
        df.to_csv(p, index=False)
        print("\n" + "=" * 92)
        print("AREA CHECK — source CRS against the reprojected grid, hectares")
        print(df.to_string(index=False))
        print(f"\nwritten: {p}")
        print("`proj_err_pct` uses the geodesic pixel-area companion and should stay near zero.")
        print("`naive_err_pct` is what you get by treating every pixel as exactly one hectare.")


if __name__ == "__main__":
    main()
