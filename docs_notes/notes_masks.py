# -*- coding: utf-8 -*-
"""Stage notes for the crop-type-mask Colab notebooks."""

NOTES = {}

NOTES["crop_type_mask/crop_type_mask_colab.ipynb"] = [

("os.environ[\"CTM_DATA_ROOT\"]", r"""
### Stage 0 · Runtime, Drive and Earth Engine

**What runs.** Installs the packages, mounts Drive, and points four environment variables at the
inputs and outputs. The pipeline reads these rather than hard-coded paths, so the same code runs on
Colab and on a laptop.

| Variable | What it points at |
|---|---|
| `PIPE_DIR` | the `planting_pipeline` folder, which contains the `crop_type_mask` package |
| `CTM_DATA_ROOT` | the input archives: SPAM 2005 to 2020, the HarvestStat Dryad release, GROWAFRICA |
| `CTM_LOCAL_DRIVE` | where Earth Engine's Drive exports land, before stage 7 copies them into the country folder |
| `CTM_CHIRPS_LTN` | the CHIRPS v3 1991 to 2020 daily normals, used to build the rainfall envelope |
| `CTM_EE_PROJECT` | the Earth Engine cloud project that owns the assets and runs the exports |

**Expected output.** Three paths printed: `assets -> ...`, `data -> ...`, `outputs -> ...`, after the
Earth Engine sign-in prompt.

**On the project.** Keep `indigo-proxy-484220-q8`. The export queue is per project, and
`ee-manzikye` has repeatedly left exports in READY for hours; the cropland stage is the longest export
in this pipeline and is the one that suffers.
"""),

("R.use_country(COUNTRY)", r"""
### Stage 0b · Choose the country profile

**What runs.** `use_country` loads one entry of `config.COUNTRY_PROFILES` and rebinds every path,
crop list, asset name and per-country override in the package. Everything after this cell is driven
by that one choice.

**Profiles, and why some are not just a country name.**

| Profile | Crops | What is different |
|---|---|---|
| `Ethiopia`, `Kenya`, `Uganda`, `Tanzania` | up to four cereals | the default settings |
| `Rwanda_SPAM2020`, `Burundi_SPAM2020`, `Somalia_SPAM2020` | maize, sorghum (+ wheat) | crop shares from **SPAM 2020 alone**, because the older editions disagree with the recent statistics |
| `South_Sudan` | maize, sorghum | **looser cropland rule**, `STABLE_VOTE = 0.25`: any one lineage, not a majority. The majority vote left whole regions empty |
| `Sudan` | sorghum, millet, wheat | 100 m cropland vote inside the SPAM crop footprint, and `max_systems` de-duplication of the statistics |
| `Eritrea` | sorghum, millet | reporting units from GADM, because Eritrea is absent from HarvestStat; uncalibrated |
| `Djibouti` | cropland only | no crop split: SPAM places 47 ha of sorghum and 17 ha of wheat in the whole country |

**Expected output.** For example `Kenya KE ['maize', 'wheat', 'sorghum'] -> .../crop_type_mask/Kenya`.
If the crop list is not what you expect for that country, you have selected the wrong profile variant.
"""),

("R.stage_prep(ARGS)", r"""
### Stage 1 · Local preparation: SPAM, HarvestStat, validation

**What this stage does.** Three tables are built on the Colab machine, before any Earth Engine work.

**1. The SPAM cell table.** For each 5 arcminute cell, the share of each mapped crop in the cell's
total physical crop area,

$$s_c(u)=\frac{A_c(u)}{\sum_{c'} A_{c'}(u)},$$

taken as the **median over the four SPAM editions** (2005, 2010, 2017, 2020), with presence recorded
as the fraction of editions that place the crop there. The median is used because a single aberrant
edition should not move the answer. Teff has no SPAM class and is carried by SPAM *other cereals*.

**2. The calibration target.** Sub-national crop area from HarvestStat, averaged over the country's
calibration years. Sudan is the exception: its statistics report the same area twice under different
production-system schemes, so the `max_systems` rule takes the larger of the two rather than their
sum. Without it Sudan's 2016 sorghum reads 14.8 Mha instead of 8.9 Mha.

**3. The validation table.** Georeferenced field data, held out of every fitting step.

**Expected output.** A pivot of `spam_stability_<ISO>.csv`: the Spearman correlation of each SPAM
edition with the multi-year median, per crop. Values of **0.9 and above** mean the editions agree and
the median is a safe summary. Values below about 0.7 for the older editions are the signature that led
to the SPAM-2020-only profiles for Rwanda, Burundi and Somalia. If a whole column is near zero, that
edition failed to load.
"""),

("R.stage_upload(ARGS)", r"""
### Stage 2 · Upload the tables to Earth Engine

**What this stage does.** Pushes the SPAM cell table and the calibration units to Earth Engine as
table assets, so the allocation can run server-side. No Cloud Storage bucket is needed.

**Expected output.** Task lines ending in COMPLETED, typically within a minute or two. Re-running the
cell is safe: an existing asset is detected and skipped.
"""),

("R.stage_cropland(ARGS)", r"""
### Stage 3 · Stable cropland, the multi-year vote

**What this stage does.** It answers the question that binds everything else: **where can any crop
be?** Four independent mapping lineages, sixteen source-years in total, each cast a vote on a common
grid. Votes are grouped by lineage so that a lineage with many years cannot outvote the others:

$$V(x)=\frac{\sum_f w_f\,v_f(x)\,\mathbf{1}[\text{observed}_f(x)]}
{\sum_f w_f\,\mathbf{1}[\text{observed}_f(x)]},
\qquad v_f(x)=\frac{\sum_{t\in f}\text{crop}_t(x)}{\sum_{t\in f}\text{observed}_t(x)},$$

with equal weights $w_f=0.25$ for GLAD (2011, 2015, 2019), ESRI (2017 to 2025), the ESA family
(WorldCover 2020 and 2021, WorldCereal 2021) and Digital Earth Africa (2019). A masked observation,
such as the ESRI cloud class that is common in the rainy season, is removed from the denominator
rather than counted as "not cropland".

A pixel is **stable cropland** when $V\ge 0.5$, or $V\ge 0.25$ for South Sudan. Four diagnostics are
exported at 100 m so you can apply your own threshold: `cl_pct`, `vote_pct`, `agree_pct` and `nvotes`.

**This is a long export.** You can close the browser. The next cell only polls. Sudan needed a 100 m
working grid and a SPAM footprint restriction to finish at all; at 30 m it managed 2 tiles of 14 in
52 hours.

**Expected values, stable cropland.**

| Country | Mha | | Country | Mha |
|---|---|---|---|---|
| Ethiopia | 18.63 | | Somalia | 1.07 |
| Sudan | 17.29 | | Rwanda | 1.00 |
| Tanzania | 13.78 | | South Sudan | 0.82 |
| Kenya | 5.03 | | Burundi | 0.53 |
| Uganda | 4.78 | | Eritrea | 0.35 |

**The single most important caveat in this pipeline.** The four lineages disagree by factors of 2 to
15 within one country, and they systematically miss arid, coastal and shifting cultivation. Everything
downstream is capped by this layer: $\sum_c f_c \le CL$. Where a country's mapped area falls short of
its statistics, the cause is almost always here and not in the allocation.
"""),

("m.addLayer(cl.select(\"vote_pct\")", r"""
### Stage 3b · Look at the vote before trusting it

`vote_pct` is the weighted vote as a percentage and `cl_pct` is the share of the 100 m cell that
passed the threshold. Compare them against what you know of the country: the vote should light up the
known farming zones and stay dark over rangeland and forest. Whole empty regions in a farming area are
the failure mode that forced the looser rule in South Sudan.
"""),

("R.stage_climate(ARGS)", r"""
### Stage 4 · Agro-climatic suitability

**What this stage does.** Builds the surface that decides **where inside a reporting unit** a crop is
placed. Three environmental variables are each passed through a fuzzy trapezoidal membership: zero
below $a$, rising to one at $b$, one from $b$ to $c$, falling to zero at $d$.

$$S_c(x)=\max\Big(0.05,\ \mu^{\text{elev}}_c\cdot\mu^{\text{rain}}_c\cdot\mu^{\text{tmean}}_c\Big)$$

The floor of 0.05 means the envelope can never fully exclude a pixel, because SPAM and the national
statistics are better evidence than a generic envelope.

| Crop | Elevation m | Rainfall mm | Mean temperature °C |
|---|---|---|---|
| maize | 0, 500, 2300, 3000 | 350, 650, 2000, 3000 | 10, 16, 30, 35 |
| wheat | 1200, 1900, 3000, 3700 | 300, 550, 1600, 2500 | 4, 9, 20, 26 |
| sorghum | 0, 300, 1900, 2700 | 250, 450, 1300, 2200 | 13, 19, 32, 38 |
| teff | 1000, 1600, 2400, 3000 | 300, 550, 1600, 2400 | 11, 14, 22, 26 |
| millet | 0, 200, 1600, 2400 | 150, 300, 900, 1600 | 16, 22, 34, 40 |

Elevation is Copernicus GLO-30, rainfall is CHIRPS v3 1991 to 2020 normals, temperature is WorldClim.
Millet's envelope is deliberately drier and hotter than sorghum's: it is the crop grown where sorghum
fails.

Satellite crop evidence is then folded in where it exists:

$$W_c = S_c\,(1+\alpha_c\,\mathrm{WC}_c),\qquad
\alpha = 2.0\ \text{maize},\ 1.0\ \text{wheat},\ 0.5\ \text{teff},\ 0\ \text{sorghum and millet},$$

with $\mathrm{WC}$ the WorldCereal 2021 fraction. Sorghum and millet get zero weight because
WorldCereal has no layer that separates them.

**Expected output.** An asset `climate_<ISO>_250m`. Nothing to read yet; the suitability figure in
stage 9 is where you check it.
"""),

("R.stage_prior(ARGS)", r"""
### Stage 5 · Dasymetric allocation

**What this stage does.** Spreads each SPAM cell's crop area onto the cropland inside that cell,
in proportion to suitability:

$$f_c(x)=CL(x)\;s_c(u)\;\frac{W_c(x)}{\overline{W_c}(x)},
\qquad \text{subject to}\quad \sum_c f_c(x)\le CL(x),$$

where $\overline{W_c}$ is the mean of $W_c$ over a 5 km kernel, about half a SPAM cell. Normalising by
a local mean rather than a global one is what keeps the area **inside** its own SPAM cell: suitability
decides the arrangement within the cell, never the total.

This is dasymetric mapping in the classical sense. The coarse quantity is conserved; the fine detail
comes from ancillary evidence. The cap is what makes stage 3 binding.

**Expected output.** A prior asset. Its quality is measured in the next stage, as `prior_rho`.
"""),

("R.stage_calibrate(ARGS)", r"""
### Stage 6 · Calibration to the statistics

**What this stage does.** The prior knows the shape but not the level. Each reporting unit gets a
scaling factor,

$$k_z=\mathrm{clip}\!\left(\frac{\text{target}_z}{\text{allocated}_z},\ 0.2,\ 5.0\right),$$

applied over two passes, because rescaling one unit changes the neighbourhood means that set its
neighbours. Pass 0 measures the prior, passes 1 and 2 apply $k$, and the last pass reports what is
left. The clip is deliberate: a unit that needs more than a fivefold increase is telling you the
cropland base is missing, and forcing the number would hide that. Those units are counted in the
`clipped` column and they are the honest record of where the product falls short.

**Expected output.** A table of target against allocated area in Mha, by iteration and crop. By the
final iteration the two columns should be nearly equal for the well-mapped countries.

**Expected values: what calibration achieves, by country.** Spearman rank agreement across reporting
units, before and after, with the number of units that hit the clip.

| Country | Crop | Units | ρ before | ρ after | Clipped |
|---|---|---|---|---|---|
| Ethiopia | maize | 66 | 0.95 | 0.99 | 9 |
| Ethiopia | wheat | 52 | 0.96 | 1.00 | 4 |
| Kenya | maize | 47 | 0.86 | 0.97 | 12 |
| Kenya | sorghum | 47 | 0.76 | 0.89 | 13 |
| Uganda | maize | 80 | 0.74 | 0.98 | 13 |
| Tanzania | maize | 21 | 0.79 | 0.98 | 8 |
| Rwanda | maize | 30 | 0.79 | 1.00 | 0 |
| Burundi | maize | 16 | 0.82 | 0.96 | 1 |
| Somalia | maize | 38 | 0.78 | 0.85 | 15 |
| Somalia | sorghum | 37 | 0.58 | 0.65 | 14 |
| Sudan | sorghum | 18 | 0.66 | 0.93 | 9 |
| Sudan | millet | 15 | 0.61 | 0.82 | 6 |
| Sudan | wheat | 9 | 0.17 | 0.40 | 6 |

**How to read a poor row.** Somalia sorghum and Sudan wheat barely improve. That is not a calibration
failure: in both the cropland vote has nothing to scale in the places the statistics report, Somalia's
north-western sorghum belt and Sudan's Northern State irrigated wheat, where SPAM 2020 places just 5 ha
of wheat north of 17.5 N. A large `clipped` count in a row is the same signal.

**South Sudan, Eritrea and Djibouti skip this stage**, because no usable statistics exist. Their areas
are uncalibrated and are a lower bound.
"""),

("R.stage_final(ARGS)", r"""
### Stage 7 · The final product

**What this stage does.** Writes the Earth Engine asset and the GeoTIFFs, five layers per country.

| Layer | Definition |
|---|---|
| `frac_<crop>` | percentage of the 100 m cell occupied by the crop. **Compute area from this** |
| `mask_<crop>` | 1 where `frac ≥ 10 %` (about 1 ha) **and** SPAM places the crop in at least 2 of 4 editions |
| `dominant` | the crop with the largest fraction, coded maize 1, wheat 2, sorghum 3, teff 4, millet 5 |
| `conf_<crop>` | confidence index, 0 to 100 |
| cropland diagnostics | `cl_pct`, `vote_pct`, `agree_pct`, `nvotes` |

**Confidence.** A weighted statement of how much evidence stands behind each pixel:

$$\mathrm{conf}_c = 100\left(0.35\,\text{cropland vote} + 0.25\,\text{SPAM presence}
+ 0.20\,e^{-|\ln k|} + 0.20\,\text{independent evidence}\right).$$

The $e^{-|\ln k|}$ term is one when calibration left the pixel alone and falls away symmetrically
whether the area had to be scaled up or down.

**The mistake this layer invites.** The binary mask always covers more ground than the fractions,
because a whole 100 m cell turns on once the crop reaches 10 % of it. Sudan's sorghum mask is 13.1 Mha
against a mapped area of 6.3 Mha. **Never compute area from mask pixel counts.** Use
`frac_<crop> × pixel area`, and use the shipped `*_pixel_area_ha_100m.tif`, because a 100 m cell in
degrees is not 1 ha everywhere.

**Expected values: mapped area against the statistics.**

| Country | Crop | Mapped Mha | Reported Mha | Placed | Confidence |
|---|---|---|---|---|---|
| Ethiopia | maize | 2.034 | 2.048 | 99 % | 80 |
| Ethiopia | wheat | 1.585 | 1.585 | 100 % | 77 |
| Ethiopia | teff | 2.716 | 2.818 | 96 % | 71 |
| Kenya | maize | 1.539 | 1.626 | 95 % | 72 |
| Kenya | wheat | 0.151 | 0.143 | 105 % | 73 |
| Uganda | maize | 0.575 | 0.591 | 97 % | 73 |
| Tanzania | maize | 3.581 | 3.908 | 92 % | 73 |
| Rwanda | maize | 0.198 | 0.202 | 98 % | 72 |
| Burundi | maize | 0.093 | 0.094 | 98 % | 67 |
| Somalia | maize | 0.110 | 0.125 | 88 % | 70 |
| Somalia | sorghum | 0.162 | 0.225 | 72 % | 68 |
| Sudan | sorghum | 6.320 | 7.479 | 84 % | 70 |
| Sudan | millet | 2.278 | 3.316 | 69 % | 67 |
| Sudan | wheat | 0.203 | 0.263 | 77 % | 89 |

Confidence sits in the 60s and 70s almost everywhere. Sudan wheat reaches 89 because WorldCereal
independently confirms the Gezira scheme; Kenya sorghum falls to 63 because nothing independent
confirms it.
"""),

("m.addLayer(p.select(f\"frac_{c}\")", r"""
### Stage 7b · Map the product

Each crop fraction is drawn 0 to 40 % of the cell, and `dominant` is drawn over codes 1 to 5. The
dominant layer is the quickest check that a country came out right: sorghum should hold Sudan's
eastern clay plains, millet the Kordofans and Darfur, wheat the Gezira, maize the Kenyan and Ethiopian
highlands.

If the colours are wrong for a five-crop country, the palette is stale: `dominant` runs to 5 since
millet was added, not to 4.
"""),

("R.stage_download(ARGS)", r"""
### Stage 8 · Bring the GeoTIFFs down

**What this stage does.** Copies the newest Drive export of each layer into
`crop_type_mask/<Country>/outputs/`, and mosaics shards where Earth Engine split a large export.

**The trap this stage exists to avoid.** Earth Engine does not overwrite. A re-export lands as
`name (1).tif`, and the original stale file keeps the clean name. Any script reading the canonical
name then silently uses the old data. This stage sorts by modification time and takes the newest, which
is why the download must go through it rather than through a manual copy.

**Expected output.** One line per file with its size. A GeoTIFF of a few hundred kilobytes for a large
country means the export was still running when it was copied; wait and re-run.
"""),

("R.stage_validate(ARGS)", r"""
### Stage 9 · Validation against data that never entered the fit

**What this stage does.** Two independent tests.

**1. Field evidence.** Georeferenced plots that were never used in fitting: LSMS-ISA enumeration areas
for Ethiopia, Tanzania and Uganda, One Acre Fund plot registers for Kenya and Burundi, trial fields for
Rwanda and the Dalberg survey for Karamoja. The metric is the AUC separation of crop locations from
cropland background, with a bootstrap interval, compared against the product's own ingredients so the
question asked is *did fusing help?* rather than *is it better than nothing?*

**2. Zone agreement.** Mapped against reported area per reporting unit, before and after calibration.

**Expected values, and the honest reading.** The fusion beats SPAM alone for Ethiopian wheat, sorghum
and teff, and for Burundian maize. For Kenyan maize it is a near-tie, AUC **0.60 against 0.58**. For
Rwanda the trial-field test is uninformative. Independent field evidence is the thinnest part of this
whole exercise, and an AUC near 0.6 should be reported as such, not as validation.

**Countries with held-out years, which is the stronger test.** Sudan is calibrated on 2015 to 2020 and
reproduces the **2021 to 2023** state areas at **r 0.97** for sorghum, 0.94 for wheat and 0.61 for
millet. Somalia is calibrated on 2015 to 2019 and reproduces **2020 to 2024** district maize at **r
0.92**, sorghum 0.81. These are the numbers to quote when asked whether the method generalises.
"""),

("R.stage_report(ARGS)", r"""
### Stage 10 · Figures, workbook and methodology document

**What this stage does.** Produces every figure and table for the country, writes
`crop_type_mask_statistics_<ISO>.xlsx`, and builds `METHODOLOGY.md` and `.docx` from the results.

**Expected output.** Thirteen or fourteen figures, then the workbook path. The figures are numbered so
they match the methodology document: 02 statistics and SPAM totals, 03 SPAM stability, 04 SPAM share
maps, 05 suitability envelopes, 06 cropland sources, 07 calibration scatter, 08 the distribution of
$k$, 09 validation, 10 crop fraction, 11 dominant crop, 12 confidence, 13 area by region.

**The two figures worth reading first.** Figure 6 shows how far apart the cropland lineages are, which
sets the ceiling on everything. Figure 8 shows the distribution of $k$: a spike at the clip of 5 means
the prior could not find the area, and names the regions where the product is weak.

**A caching trap.** `report.py` caches its intermediate CSVs. After rebuilding an asset, the cache is
invalidated by the asset's `updateTime`; if a figure still shows old numbers, the asset timestamp did
not move, and you should delete the cache in `work/` and re-run.
"""),
]


NOTES["crop_type_mask/crop_type_mask_VIEWER_colab.ipynb"] = [

("ee.Authenticate()", r"""
### Stage 0 · Setup

**What this notebook is.** A read-only tour of a finished country. It builds nothing and exports
nothing, so it is safe to hand to someone who should look at the product but not rebuild it. To
rebuild, use `crop_type_mask_colab.ipynb`.

**What you set.** `PIPE_DIR`, the Earth Engine project, and `COUNTRY`. Eleven profiles exist; note that
Rwanda, Burundi and Somalia carry the `_SPAM2020` suffix, and that Djibouti is cropland only.

**Expected output.** `Kenya KE crops: ['maize', 'wheat', 'sorghum'] -> .../Kenya`.
"""),

("U.asset_exists", r"""
### Stage 1 · What exists for this country

**What this stage does.** Lists the six Earth Engine assets a finished country should have, then the
GeoTIFFs and documents on disk. A half-finished country is obvious from the `exists` column.

**Expected output.** Six `True` values for a finished country, five GeoTIFFs
(`crop_fraction`, `crop_mask`, `crop_confidence`, `crop_cropland`, `pixel_area_ha`), a `METHODOLOGY.md`
and `.docx`, a statistics workbook and a set of CSVs.

**Exceptions that are not faults.** Djibouti has cropland only, so there is no fraction, mask or
confidence file and no methodology document, only a README. South Sudan, Eritrea and Djibouti have no
calibration unit asset, because they were never calibrated.
"""),

("m.add_basemap(\"HYBRID\")", r"""
### Stage 2 · The map

**Layers, in the order they answer questions.**

1. **Cropland vote** and **agreement**: the evidence base. How many lineages saw cropland here, and did
   they agree?
2. **Crop fraction** per crop: the product. Percentage of each 100 m cell.
3. **Dominant crop**: which crop wins each cell, maize 1, wheat 2, sorghum 3, teff 4, millet 5.
4. **Confidence**: 0 to 100, from the cropland vote, SPAM presence, how far calibration had to move the
   pixel, and whether anything independent confirmed it.

**What a good country looks like.** Crop fraction concentrated in the known farming zones, dominant
crop following the agro-ecology rather than administrative boundaries, and confidence highest where the
vote was unanimous. Administrative boundaries visible in the **fraction** layer are expected, because
calibration is applied per reporting unit. Boundaries visible in the **cropland vote** are not, and
point at a source-data seam.
"""),

("show(\"final_national_summary\")", r"""
### Stage 3 · Headline numbers

**What this stage does.** Prints the national totals against the official statistics, and the
validation tables.

**How to read `final_national_summary`.** `mapped_ha` is the area the product holds, from the crop
fraction. `target_ha` is what the statistics report. `mask_ha` is the binary mask, which is always
larger and is **not an area**. `conf` is the mean confidence inside the mask.

**Expected values.** Ethiopia places 96 to 100 % of its reported area, Kenya 95 to 105 %, Uganda 83 to
97 %, Tanzania 82 to 92 %, Rwanda 89 to 98 %, Burundi 70 to 98 %, Somalia 72 to 88 %, Sudan 69 to 84 %.
South Sudan, Eritrea and Djibouti have no target, because no statistics exist; their `target_ha` is
blank and their areas are a lower bound, not an estimate.

**Validation.** `validation_zones` is agreement with the statistics, which the product was fitted to.
The `validation_*_metrics` files are the independent tests and are the ones that count. Read the AUC
against the ingredient baselines printed beside it, not on its own.
"""),

("figs = sorted(glob.glob", r"""
### Stage 4 · Every figure

Thirteen or fourteen figures per country, numbered to match the methodology document. The fastest read
is figure 6 for the cropland disagreement, figure 8 for where calibration hit its limits, and figure 11
for whether the dominant crop follows the agro-ecology.
"""),

("pd.read_excel(xl, sheet_name=None)", r"""
### Stage 5 · The statistics workbook

Every table behind the figures, one sheet each: SPAM stability, cropland by source-year, the
calibration targets, the per-unit before and after, the distribution of $k$, the national summary, and
the validation. This is the file to send when someone asks for the numbers rather than the maps.
"""),

("for country in [\"Ethiopia\"", r"""
### Stage 6 · All countries side by side

**What this stage does.** Loops every profile and concatenates the national summaries, so the eleven
products can be compared in one table.

**What the comparison shows.** The share of reported area placed falls as you move from countries with
recent statistics and dense cropland (Ethiopia, Kenya) to countries with old statistics or arid,
shifting cultivation (Sudan millet at 69 %). The pattern is a property of the **reference data**, not
of the method; the method is identical in all eleven.
"""),

("rasterio.open(f)", r"""
### Stage 7 · Read the GeoTIFFs directly

**What this stage does.** Opens the local file and previews the bands, as a check that the raster
matches the Earth Engine asset.

**What to check.** Band descriptions should name the crops in `C.CROP_NAMES` order. The CRS is
EPSG:4326 and the pixel is 0.0009 degrees, which is about 100 m at the equator but **not 1 ha
everywhere** — the cell shrinks in longitude as you move away from it. For any area calculation use the
shipped `*_pixel_area_ha_100m.tif`, which carries true geodesic hectares per pixel, and never
`count × 1 ha`.

NoData is 0 and the QML styles ship beside the GeoTIFFs, so QGIS opens them without a black background.
"""),
]
