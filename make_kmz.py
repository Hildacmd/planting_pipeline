#!/usr/bin/env python3
"""Export the pipeline rasters as Google Earth KMZ ground-overlays (one KMZ per country-season, each
with toggleable, palette-styled layers). Reads the Drive GeoTIFFs, reprojects to WGS84, colorizes.

Run:  python make_kmz.py        ->  *.kmz  (double-click into Google Earth Pro / earth.google.com)
"""
import os, glob, zipfile, numpy as np, rasterio
import matplotlib.image as mpimg
from matplotlib import colormaps
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.transform import array_bounds
import caf_add

DRIVE = caf_add.DRIVE
TMP = os.path.join(os.path.dirname(__file__), "_kmz_tmp"); os.makedirs(TMP, exist_ok=True)
OUT = os.path.dirname(__file__)
MAXPX = 2200

def newest(base):
    v = glob.glob(os.path.join(DRIVE, base + ".tif")) + glob.glob(os.path.join(DRIVE, base + " (*).tif"))
    return max(v, key=os.path.getmtime) if v else None

def read_4326(tif, band):
    with rasterio.open(tif) as src:
        f = max(1, round(max(src.width, src.height) / MAXPX))
        ow, oh = max(1, src.width // f), max(1, src.height // f)
        allb = src.read(out_shape=(src.count, oh, ow), resampling=Resampling.nearest).astype("float32")  # (nb,h,w)
        arr = allb[band - 1]
        # footprint: outside-maize pixels are 0 in EVERY band (int16 0-fill) or NaN (float) -> hide them
        foot = np.any(np.nan_to_num(allb, nan=0.0) != 0, axis=0).astype("float32")
        st = src.transform * src.transform.scale(src.width / ow, src.height / oh)
        dt, dw, dh = calculate_default_transform(src.crs, "EPSG:4326", ow, oh, *src.bounds)
        dv = np.full((dh, dw), np.nan, "float32"); df = np.zeros((dh, dw), "float32")
        reproject(arr, dv, src_transform=st, src_crs=src.crs, dst_transform=dt, dst_crs="EPSG:4326",
                  src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.nearest)
        reproject(foot, df, src_transform=st, src_crs=src.crs, dst_transform=dt, dst_crs="EPSG:4326",
                  src_nodata=0, dst_nodata=0, resampling=Resampling.nearest)
        w, s, e, n = array_bounds(dh, dw, dt)
        return dv, df, (n, s, e, w)

def colorize(arr, foot, cmap, vmin, vmax, scale, png):
    v = arr * scale
    norm = np.clip((v - vmin) / ((vmax - vmin) or 1), 0, 1)
    rgba = colormaps[cmap](norm)                       # (h,w,4) floats
    rgba[..., 3] = np.where((foot > 0.5) & np.isfinite(arr), 1.0, 0.0)  # transparent outside maize
    mpimg.imsave(png, rgba)                            # row 0 = north -> GroundOverlay north-up

def kmz(path, title, overlays):
    items = ""
    for png, name, desc, (n, s, e, w) in overlays:
        items += (f"<GroundOverlay><name>{name}</name><description><![CDATA[{desc}]]></description>"
                  f"<color>c8ffffff</color><Icon><href>{png}</href></Icon>"
                  f"<LatLonBox><north>{n}</north><south>{s}</south><east>{e}</east><west>{w}</west></LatLonBox>"
                  f"</GroundOverlay>\n")
    kml = ('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
           f"<name>{title}</name><open>1</open><Folder><name>{title}</name>{items}</Folder></Document></kml>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", kml)
        for png, _, _, _ in overlays:
            z.write(os.path.join(TMP, png), arcname=png)

# ---- product specs: (base, band[1-idx], cmap, vmin, vmax, scale, layer-name) ----
JOBS = {
  "Kenya_Longrains_2024": [
    ("cpi_Kenya_Longrains_2024",       7, "RdYlGn", 0, 100, 1,    "CPI (0-100)"),
    ("cpi_Kenya_Longrains_2024",       8, "YlGn",   0, 6,   0.01, "Yield (t/ha)"),
    ("cpi_Kenya_Longrains_2024",       2, "RdYlGn", 40,100, 1,    "WRSI @flowering"),
    ("wrsi_Kenya_maize_Longrains_2024",1, "RdYlGn", 40,100, 1,    "WRSI (season)"),
    ("onsetexcess_Kenya_Longrains_2024",2,"Blues",  0, 40,  1,    "Soil waterlogging (modelled)"),
    ("onsetexcess_Kenya_Longrains_2024",3,"PuBu",   0, 1,   1,    "SPI-3 wet (0/1)"),
    ("onsetexcess_Kenya_Longrains_2024",1,"Reds",   0, 1,   1,    "False-start (5+7)"),
  ],
  "Ethiopia_Meher_2024": [
    ("cpi_Ethiopia_Meher_2024",        7, "RdYlGn", 0, 100, 1,    "CPI (0-100)"),
    ("cpi_Ethiopia_Meher_2024",        8, "YlGn",   0, 6,   0.01, "Yield (t/ha)"),
    ("cpi_Ethiopia_Meher_2024",        2, "RdYlGn", 40,100, 1,    "WRSI @flowering"),
    ("wrsi_Ethiopia_maize_Meher_2024_250m",1,"RdYlGn",40,100,1,   "WRSI (season)"),
    ("onsetexcess_Ethiopia_Meher_2024",2,"Blues",   0, 40,  1,    "Soil waterlogging (modelled)"),
    ("onsetexcess_Ethiopia_Meher_2024",3,"PuBu",    0, 1,   1,    "SPI-3 wet (0/1)"),
  ],
  "Kenya_Shortrains_2024": [
    ("cpi_Kenya_maize_Shortrains_2024",1, "RdYlGn", 0, 100, 1,    "CPI (0-100)"),
    ("cpi_Kenya_maize_Shortrains_2024",2, "YlGn",   0, 5,   0.01, "Yield (t/ha)"),
    ("stagemonitor_Kenya_maize_Shortrains_2024",2,"RdYlGn",40,100,1,"WRSI @flowering"),
    ("onsetexcess_Kenya_Shortrains_2024",1,"Blues", 0, 40,  1,    "Soil waterlogging (modelled)"),
    ("onsetexcess_Kenya_Shortrains_2024",2,"PuBu",  0, 1,   1,    "SPI-3 wet (0/1)"),
  ],
}

for job, specs in JOBS.items():
    overlays = []
    for base, band, cmap, vmin, vmax, scale, name in specs:
        tif = newest(base)
        if not tif:
            print(f"  [skip] {base} not found"); continue
        arr, foot, box = read_4326(tif, band)
        png = f"{job}__{name.split()[0].replace('(','').replace(')','')}_{band}.png".replace("/", "-")
        colorize(arr, foot, cmap, vmin, vmax, scale, os.path.join(TMP, png))
        desc = f"{name} · palette {cmap} · range {vmin}-{vmax} · source {os.path.basename(tif)}"
        overlays.append((png, name, desc, box))
        print(f"  {job}: {name}  ({cmap} {vmin}-{vmax})")
    if overlays:
        out = os.path.join(OUT, f"GoogleEarth_{job}.kmz")
        kmz(out, job.replace("_", " "), overlays)
        print(f"  -> {os.path.basename(out)}  ({len(overlays)} layers, {os.path.getsize(out)/1e6:.1f} MB)\n")
