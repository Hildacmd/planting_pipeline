# Crop-type masks in a metric CRS

> **The EPSG:4326 set under `<Country>/outputs/` is authoritative.**
> Both reprojections are derived from it. Each warp costs about 0.03 % in resampling, and
> reprojecting a reprojection compounds that error, so always start again from the EPSG:4326
> source. Every derived raster carries this in its GDAL tags (`CTM_DERIVED_FROM`,
> `CTM_AUTHORITATIVE`, `CTM_RESAMPLING`, `CTM_NOTE`), and `reproject_crs.py` **refuses** to take a
> derived raster as input:
>
> ```
> REFUSED: .../KE_crop_fraction_100m.tif
>   is itself a derived product, reprojected from
>   Kenya/outputs/KE_crop_fraction_100m.tif in EPSG:32637 on 2026-09-24.
>   Reproject from the authoritative EPSG:4326 source instead.
> ```
>
> Check any file with `gdalinfo <file> | grep CTM_`.

`reproject_crs.py` reprojects the crop-type masks from the source EPSG:4326 grid to a metric one,
per country, at 100 m.

```bash
python reproject/reproject_crs.py                 # UTM, every country
python reproject/reproject_crs.py --crs aea       # Africa Albers Equal Area
python reproject/reproject_crs.py --country Sudan Kenya
python reproject/reproject_crs.py --verify        # area check only, writes nothing
```

Outputs land in `<Country>/outputs/<tag>/`, tagged `utm36`, `utm37` and so on, or `aea`.

## Which CRS for which job

**`utm`** gives each country the UTM zone containing its centroid. A cell is 100 by 100 m, so a
pixel reads as one hectare and everything is in metres. This is the CRS national partners work in.

**Every country in the series spans two to four UTM zones**, though, and UTM is conformal, not
equal-area, so forcing one zone inflates area away from the central meridian:

| Country | Zone used | Worst area inflation |
|---|---|---|
| Sudan | 36N | **3.54 %** (western edge) |
| Ethiopia | 37N | 2.37 % |
| South Sudan | 36N | 2.31 % |
| Tanzania | 36S | 1.62 % |
| Somalia | 38N | 1.18 % |
| Kenya | 37N | 0.72 % |
| Eritrea, Rwanda, Burundi, Uganda, Djibouti | | under 0.5 % |

**`aea`** gives Africa Albers Equal Area Conic, standard parallels 20 S and 23 N, central meridian
25 E, which preserves area exactly everywhere. **Use this when the comparison is about area**,
which most crop-mask comparisons are. Both sets are built.

In the equal-area set **every pixel is exactly 1.0000 ha**, so a pixel count and the pixel-area
raster give the same answer. That is the practical difference between the two: in AEA you may
count pixels, in UTM you may not.

| Method | Worst error | Mean error |
|---|---|---|
| AEA, either way | 0.19 % | 0.035 % |
| UTM with the pixel-area raster | 0.11 % | 0.030 % |
| **UTM by pixel count** | **0.86 %** | 0.166 % |

The residual few hundredths of a percent in both sets is resampling, not projection: it is the
near-1:1 warp landing cell centres slightly differently, and it is unbiased, with signs scattered
across countries. The one outlier, Burundi wheat at 0.19 %, is 3,024 ha in total, so a handful of
pixels moves it.

## Area stays exact in either CRS

Each output folder carries a `pixel_area_ha` raster on the same grid, computed **geodesically on
the WGS 84 ellipsoid** rather than from the projection, so it absorbs whatever distortion the
projection carries. Area is then

    area (ha) = sum( frac_crop / 100 x pixel_area_ha )

and never a pixel count. Measured against the source-CRS figure, all 27 country-crop combinations
land **within 0.11 %**, and most within 0.03 %. Treating every pixel as exactly one hectare
instead costs up to 0.86 % (Sudan millet). The full check is in `area_check_utm.csv`.

Every layer of a country sits on **one common grid**, derived from the union of the source
extents, so the fraction, mask, confidence, cropland and pixel-area rasters stack pixel for pixel.
Sudan's source fraction and confidence layers differ by eight rows, so warping each file
independently would not have stacked.

## Resampling, and a trap worth knowing about

**Nearest neighbour, for every band.** The source grid is 0.0009 degrees, about 100 m, and the
target is 100 m, so this is a near one-to-one warp with nothing to aggregate.

Averaging a near-1:1 warp does **not** conserve the quantity. It smears each value into its
neighbours, and every crop patch gains area around its edge. In testing that inflated Rwanda's
mapped crop area by 7 to 17 %, and its wheat, which sits in small scattered patches with the most
edge per hectare, by 168 %. Use `average` only when genuinely coarsening, for example 100 m to
1 km, and check the area conservation when you do.

Two related traps were hit while building this and are worth recording:

* These rasters declare **NoData = 0** so QGIS does not draw a black background, but for a crop
  fraction 0 means "no crop here". An averaging resampler skips those zeros and inflates edges.
* `src_nodata=None` in rasterio does **not** mean "no nodata". It falls back to the dataset's
  declared nodata. Forcing a sentinel value instead leaked the sentinel into the output, where it
  showed up as a constant area offset identical across all three crop bands.

## Size

677 MB for the UTM set and 661 MB for the equal-area set, across eleven countries, from Djibouti
at 0.4 MB to Ethiopia at about 240 MB in each. All outputs are DEFLATE compressed and tiled.
