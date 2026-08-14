#!/usr/bin/env python3
"""Render downloaded planting/WRSI GeoTIFFs (from Google Drive) into a styled PDF map report.

Runs fully locally (rasterio + matplotlib) on GeoTIFF tiles already exported by the pipeline
-- no Earth Engine compute, so it is unaffected by the GEE quota throttle.

Tiles are downsampled on read (each is ~32k x 32k) and reprojected into a compact canvas,
so memory stays small. Products are auto-detected by filename in --outputs-dir.

Run:
  python render_maps_pdf.py                       # auto-detect everything in ~/Downloads/planting_outputs
  python render_maps_pdf.py --outputs-dir PATH --out report.pdf
"""
import argparse, os, glob, re, sys
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_bounds
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.backends.backend_pdf import PdfPages

sys.path.insert(0, os.path.dirname(__file__))
try:
    from src.utils import dekad_label
except Exception:
    def dekad_label(d):
        import datetime as dt
        d = int(round(d)); m = (d - 1) // 3 + 1
        return f"{d}·{dt.date(2000, m, 1):%b}"

# dekad palette (early -> late), 7 classes covers a typical season spread
DEKAD_COLORS = ['#2b83ba', '#80bfab', '#c7e8ad', '#ffffbf', '#fdc980', '#ec6e43', '#d7191c']


def group_products(outputs_dir):
    """Return {product_name: [tile_paths]} grouped by stripping the -R-C tile suffix."""
    prods = {}
    for p in glob.glob(os.path.join(outputs_dir, "*.tif")):
        name = re.sub(r"-\d+-\d+\.tif$", "", os.path.basename(p))
        name = re.sub(r"\.tif$", "", name)
        prods.setdefault(name, []).append(p)
    return prods


def mosaic_downsampled(tiles, target_px=2000):
    """Reproject all tiles into one small canvas. Returns (array, extent) or (None, None)."""
    lefts, bots, rights, tops = [], [], [], []
    crs = None
    for t in tiles:
        with rasterio.open(t) as ds:
            b = ds.bounds; crs = ds.crs
            lefts.append(b.left); bots.append(b.bottom); rights.append(b.right); tops.append(b.top)
    left, bottom, right, top = min(lefts), min(bots), max(rights), max(tops)
    aspect = (top - bottom) / (right - left)
    W = target_px
    H = max(1, int(round(W * aspect)))
    dst_transform = from_bounds(left, bottom, right, top, W, H)
    dest = np.zeros((H, W), dtype="float32")
    for t in tiles:
        with rasterio.open(t) as ds:
            tmp = np.zeros((H, W), dtype="float32")
            reproject(
                source=rasterio.band(ds, 1), destination=tmp,
                src_transform=ds.transform, src_crs=ds.crs,
                dst_transform=dst_transform, dst_crs=crs,
                resampling=Resampling.nearest)
        dest = np.where(tmp > 0, tmp, dest)      # accumulate valid (non-zero) pixels
    return dest, (left, right, bottom, top)


def render_planting_page(pdf, name, arr, extent):
    valid = arr[(arr >= 1) & (arr <= 36)]
    if valid.size == 0:
        return
    dmin, dmax = int(np.floor(valid.min())), int(np.ceil(valid.max()))
    dmin, dmax = max(1, dmin), min(36, dmax)
    ncls = dmax - dmin + 1
    # sample the palette to the number of dekad classes present
    idx = np.linspace(0, len(DEKAD_COLORS) - 1, ncls).round().astype(int)
    cmap = ListedColormap([DEKAD_COLORS[i] for i in idx])
    bounds = np.arange(dmin - 0.5, dmax + 1.5, 1)
    norm = BoundaryNorm(bounds, cmap.N)

    masked = np.ma.masked_where((arr < dmin) | (arr > dmax), arr)
    fig, ax = plt.subplots(figsize=(8.27, 9.5))   # A4-ish portrait
    im = ax.imshow(masked, extent=extent, origin="upper", cmap=cmap, norm=norm,
                   interpolation="nearest")
    ax.set_facecolor("#f4f6f8")
    pretty = name.replace("_", " ")
    ax.set_title(f"Planting dekad — {pretty}", fontsize=13, color="#1a3a5c", pad=12)
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
    cbar = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03,
                        ticks=range(dmin, dmax + 1))
    cbar.ax.set_yticklabels([dekad_label(d) for d in range(dmin, dmax + 1)])
    cbar.set_label("Estimated planting dekad (1–36 · month-dekad)")
    fig.text(0.5, 0.02,
             "Per-pixel estimated planting date within the crop mask. "
             "Sentinel-2 red-edge + FPAR + Sentinel-1 SAR fusion → SOS → planting offset.",
             ha="center", fontsize=7.5, color="grey")
    pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)
    return (dmin, dmax, valid)


def render_wrsi_page(pdf, name, arr, extent):
    valid = arr[(arr >= 0) & (arr <= 100)]
    if valid.size == 0:
        return
    fig, ax = plt.subplots(figsize=(8.27, 9.5))
    masked = np.ma.masked_where((arr < 0) | (arr > 100) | (arr == 0), arr)
    im = ax.imshow(masked, extent=extent, origin="upper", cmap="RdYlGn",
                   vmin=0, vmax=100, interpolation="nearest")
    ax.set_facecolor("#f4f6f8")
    ax.set_title(f"WRSI — {name.replace('_',' ')}", fontsize=13, color="#1a3a5c", pad=12)
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
    cbar = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03)
    cbar.set_label("WRSI (0 = failure, 100 = fully satisfied)")
    pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs-dir", default=os.path.expanduser("~/Downloads/planting_outputs"))
    ap.add_argument("--out", default="Planting_Maps_Report.pdf")
    ap.add_argument("--px", type=int, default=2000, help="canvas width in px")
    args = ap.parse_args()

    prods = group_products(args.outputs_dir)
    if not prods:
        print(f"No GeoTIFFs found in {args.outputs_dir}"); return
    print(f"Found {len(prods)} product(s):")
    for n, t in prods.items():
        print(f"  {n}  ({len(t)} tiles)")

    with PdfPages(args.out) as pdf:
        # cover
        fig = plt.figure(figsize=(8.27, 11.69)); fig.clf()
        fig.text(0.5, 0.62, "Crop Planting-Window\nMap Report", ha="center",
                 fontsize=24, color="#1a3a5c", weight="bold")
        fig.text(0.5, 0.50, "Rendered locally from Earth Engine GeoTIFF exports",
                 ha="center", fontsize=12, color="#2d6a9f")
        fig.text(0.5, 0.45, "TomorrowNow / ICPAC", ha="center", fontsize=11, color="grey")
        pdf.savefig(fig); plt.close(fig)

        for name in sorted(prods):
            print(f"rendering {name} ...")
            arr, extent = mosaic_downsampled(prods[name], target_px=args.px)
            if arr is None:
                continue
            if name.lower().startswith("wrsi"):
                render_wrsi_page(pdf, name, arr, extent)
            else:
                info = render_planting_page(pdf, name, arr, extent)
                if info:
                    dmin, dmax, valid = info
                    print(f"    planting dekads {dmin}-{dmax}; "
                          f"valid pixels {valid.size:,}; modal {int(np.bincount(valid.astype(int)).argmax())}")
    print(f"\nPDF saved: {os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()
