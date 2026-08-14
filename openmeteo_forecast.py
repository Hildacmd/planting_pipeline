#!/usr/bin/env python3
"""Open-Meteo 4-day precipitation forecast -> Kenya GeoTIFF, and a 6-obs/4-forecast dekad blend.

Fetches daily precipitation_sum on a regular lat/lon grid over Kenya from the FREE, keyless
Open-Meteo forecast API, sums the next `fc_days` days, and writes a GeoTIFF. This is the
forecast component of the FEWS operational running dekad (6 days observed CHIRPS + 4 forecast).

Free tier: no API key. (Paid users: set OPENMETEO_APIKEY and the script routes to the customer
endpoint automatically — the key is read from the env, never hard-coded.)

Run:
  python openmeteo_forecast.py --res 0.25 --fc-days 4 --out om_forecast_kenya.tif
  # then blend with a 6-day observed CHIRPS raster:
  python openmeteo_forecast.py --blend --chirps6 chirps_6day.tif --forecast om_forecast_kenya.tif --out dekad_precip.tif
"""
import argparse, os, json, time, urllib.request, urllib.parse
import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling

# Kenya bounding box (lon/lat)
LON0, LON1, LAT0, LAT1 = 33.9, 41.9, -4.7, 5.5
FREE = "https://api.open-meteo.com/v1/forecast"
PAID = "https://customer-api.open-meteo.com/v1/forecast"


def _endpoint():
    key = os.environ.get("OPENMETEO_APIKEY")
    return (PAID, key) if key else (FREE, None)


def _fetch(lats, lons, fc_days):
    base, key = _endpoint()
    params = {
        "latitude": ",".join(f"{v:.4f}" for v in lats),
        "longitude": ",".join(f"{v:.4f}" for v in lons),
        "daily": "precipitation_sum", "forecast_days": fc_days, "timezone": "UTC",
    }
    if key:
        params["apikey"] = key
    url = base + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as r:
        data = json.load(r)
    if isinstance(data, dict):
        data = [data]
    return [float(np.nansum(loc["daily"]["precipitation_sum"])) for loc in data]


def fetch_grid(res=0.25, fc_days=4, batch=150, pause=0.4):
    lons = np.arange(LON0, LON1 + 1e-9, res)
    lats = np.arange(LAT1, LAT0 - 1e-9, -res)          # north->south (raster row order)
    LON, LAT = np.meshgrid(lons, lats)
    flat_lat, flat_lon = LAT.ravel(), LON.ravel()
    vals = np.full(flat_lat.size, np.nan)
    n = flat_lat.size
    print(f"grid {LAT.shape} = {n} points at {res} deg; fetching in batches of {batch}...")
    for i in range(0, n, batch):
        j = min(i + batch, n)
        got = _fetch(flat_lat[i:j], flat_lon[i:j], fc_days)
        vals[i:j] = got
        print(f"  {j}/{n}")
        time.sleep(pause)                              # be polite to the free API
    grid = vals.reshape(LAT.shape)
    transform = from_origin(LON0 - res / 2, LAT1 + res / 2, res, res)
    return grid.astype("float32"), transform


def write_tif(grid, transform, out):
    with rasterio.open(out, "w", driver="GTiff", height=grid.shape[0], width=grid.shape[1],
                       count=1, dtype="float32", crs="EPSG:4326", transform=transform,
                       nodata=np.nan) as ds:
        ds.write(grid, 1)
    print(f"forecast GeoTIFF -> {os.path.abspath(out)}  "
          f"(mean {np.nanmean(grid):.1f} mm over {int(np.isfinite(grid).sum())} cells)")


def blend(chirps6_path, forecast_path, out):
    """dekad precip = 6-day observed CHIRPS + 4-day Open-Meteo forecast (forecast resampled to CHIRPS grid)."""
    with rasterio.open(chirps6_path) as c:
        obs = c.read(1); prof = c.profile; dst_t, dst_crs = c.transform, c.crs
        H, W = obs.shape
    with rasterio.open(forecast_path) as f:
        fc = np.zeros((H, W), "float32")
        reproject(source=rasterio.band(f, 1), destination=fc,
                  src_transform=f.transform, src_crs=f.crs,
                  dst_transform=dst_t, dst_crs=dst_crs, resampling=Resampling.bilinear)
    total = np.where(np.isfinite(obs), obs, 0) + np.where(np.isfinite(fc), fc, 0)
    prof.update(dtype="float32", count=1)
    with rasterio.open(out, "w", **prof) as ds:
        ds.write(total.astype("float32"), 1)
    print(f"blended 6-obs+4-forecast dekad precip -> {os.path.abspath(out)}  "
          f"(mean {np.nanmean(total):.1f} mm)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", type=float, default=0.25, help="grid resolution (deg)")
    ap.add_argument("--fc-days", type=int, default=4)
    ap.add_argument("--out", default="om_forecast_kenya.tif")
    ap.add_argument("--blend", action="store_true", help="blend mode (needs --chirps6 and --forecast)")
    ap.add_argument("--chirps6", help="6-day observed CHIRPS GeoTIFF (mm)")
    ap.add_argument("--forecast", help="Open-Meteo forecast GeoTIFF to blend")
    args = ap.parse_args()

    if args.blend:
        blend(args.chirps6, args.forecast, args.out)
    else:
        grid, transform = fetch_grid(res=args.res, fc_days=args.fc_days)
        write_tif(grid, transform, args.out)


if __name__ == "__main__":
    main()
