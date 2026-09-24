# Maize on the validated crop-type mask

The shipped 2024 maize products are computed inside the **ESA WorldCereal 2021 maize layer**,
because that is what `run.crop_mask_image` returns by default. This folder re-runs the same 16
products inside the **ICPAC crop-type mask** instead, to its own asset prefix and its own folder,
so the existing products are untouched and the two are directly comparable.

## Why the mask is worth changing

| | WorldCereal 2021 maize | ICPAC crop-type mask |
|---|---|---|
| Basis | one global model year, 10 m | SPAM shares on a four-lineage, sixteen-source-year cropland vote, 100 m |
| Calibrated to national statistics | no | **yes**, where statistics exist |
| Reproduces reported maize area | not measured | **92 to 99 %** across the eight maize countries |
| Suitability and satellite reweighting | no | yes |
| Confidence layer | no | yes, `conf_maize` |

Nothing else changes. The water balance, the stresses, the CPI and the yield ceiling are
identical, so any difference between `cpi_*` and `cpiCTM_*` is attributable to the mask alone.

## Run

```bash
python maize_ctm/run_maize_ctm.py --stage all                        # dry run, prints the plan
EE_PROJECT=ee-manzikye python maize_ctm/run_maize_ctm.py --stage high --submit --rich
python maize_ctm/run_maize_ctm.py --min-fraction 25 --stage high     # tighter stratum
```

Assets land as `cpiCTM_<Country>_<Season>_2024`, or `cpiCTMX_*` with `--rich`.

**Use `--rich` if the products are to reach the apps.** The reducer that feeds `pw_app.html` and
`risk_app.html` needs `planting_dekad` and the six WRSI and WSI stage bands, which only the rich
export carries.

All 16 maize products are eligible: every country with a maize product also has a maize band in
the crop-type mask. Sudan, Eritrea and Djibouti have no maize product and no maize band.

## Then

```bash
EE_PROJECT=... python reduce_newcountries.py --asset-prefix cpiCTMX --out-prefix newcCTM \
    --project ee-manzikye
```

## A note on the binary mask

The crop-type mask turns a whole 100 m cell on once maize reaches 10 % of it, so it covers more
ground than the crop does. That is the right behaviour for a computation stratum and the wrong
number for an area. `--min-fraction 25` tightens it if the stratum looks too generous. For area,
always use `frac_maize` with the pixel-area raster, never a pixel count.
