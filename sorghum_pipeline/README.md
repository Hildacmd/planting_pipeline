# Sorghum pipeline — ICPAC / FSRP-AF

Crop-specific planting window, water balance, crop performance index and yield for **sorghum**
across ten ICPAC Member States, built on the same engine as the maize pipeline.

Sorghum is the **second cereal of the region by area and the first in its drylands**: 6.32 Mha
mapped in Sudan alone, against 1.54 Mha of maize in the whole of Kenya. It is also the crop
whose seasons, water response and heat tolerance differ most from maize, which is why running
the maize pipeline over a sorghum mask would be wrong rather than merely approximate.

## What is sorghum-specific, and why

| | Maize | Sorghum | Source |
|---|---|---|---|
| Season calendar | `config/season_calendar.csv` | **Inception Report Table 2.0**, all 18 | report pp. 16-17 |
| Cycle length | fixed 12 dekads | 9 to 18 dekads, per product | CM4EW planting to harvest |
| Kc curve | 0.30 → 1.20 → 0.35 | **0.30 → 1.05 → 0.55** | FAO-56 Tables 11, 12 |
| Rooting depth | 1.0 m | **1.5 m** | FAO-56 Table 22 |
| FAO-33 Ky veg/flo/grf | 0.4 / **1.5** / 0.5 | 0.2 / **0.55** / 0.45 | FAO-33 Table 24 |
| Heat cap at flowering | 33 °C | **36 °C** | Prasad et al. 2008, 2015 |
| Crop mask | WorldCereal maize | **crop-type mask** `mask_sorghum` | this project |

The **Ky row is the substantive difference**. Sorghum's total yield-response factor is 0.9
against maize's 1.25, and its flowering peak is 0.55 against 1.50. A water deficit at flowering
costs maize nearly three times what it costs sorghum. A CPI computed with maize factors would
declare a sorghum crop failed in seasons it survives — which is the failure mode that matters
most, because sorghum is grown precisely where the rains fail.

The **mask row is the one that would break silently**. WorldCereal has no sorghum class, and
`run.crop_mask_image` falls through to the temporary-crops extent for any crop that is not
maize. A sorghum run left on the default would compute over all cropland and report it as
sorghum.

## Files

| File | What it does |
|---|---|
| `build_calendar.py` | derives `config/season_calendar_sorghum.csv` from Inception Report Table 2.0, carrying the GEOGLAM CM4EW sorghum calendar alongside for comparison |
| `config/season_calendar_sorghum.csv` | 18 products, each tagged with its calendar source |
| `sorghum_params.py` | FAO-56 / FAO-33 parameters, the heat cap, the mask wiring, the Ym table |
| `run_all_sorghum.py` | submits the Earth Engine products. **Dry-run unless `--submit`** |
| `zonal_sorghum.py` | reduces a product to admin-2, sorghum-area weighted, for calibration |
| `calibrate_ym_sorghum.py` | fits the yield ceiling against HarvestStat, 70/30 × 200 held out |
| `docs/METHODOLOGY.md` | the method, the sources, and what is still provisional |
| `docs/ALIGNMENT_WITH_INCEPTION_REPORT.md` | the pipeline against the report's proposed sorghum methodology, item by item |

## Run it

```bash
python sorghum_pipeline/build_calendar.py                                   # rebuild the calendar
python sorghum_pipeline/run_all_sorghum.py --stage all                      # dry run, prints the plan
EE_PROJECT=indigo-proxy-484220-q8 python sorghum_pipeline/run_all_sorghum.py --stage high --submit
EE_PROJECT=indigo-proxy-484220-q8 python sorghum_pipeline/zonal_sorghum.py  # once the assets exist
python sorghum_pipeline/calibrate_ym_sorghum.py --write                     # fit and record Ym
```

## Status

**CPI is ready to run. Yield is not yet reportable.** `YM_CAL_SORGHUM` is empty, so every
product falls back to an uncalibrated 3.0 t/ha (2.0 for short seasons). On every maize country
where the equivalent default could be tested it was two to seven times what smallholders
actually harvest, and there is no reason to expect better here. Report CPI until
`calibrate_ym_sorghum.py` has run; the asset property `ym_calibrated` records which state a
product is in.

All eighteen calendars come from the Inception Report's Table 2.0. GEOGLAM CM4EW also ships a
**sorghum-specific** calendar, which covers nine of the products and **disagrees with the report
for six of them** — by three dekads for Kenya, Eritrea, Uganda and South Sudan's second season.
Those differences are kept in the `cm4ew_*` columns and are the first thing to put to national
partners. See `docs/ALIGNMENT_WITH_INCEPTION_REPORT.md`.

Tanzania and Eritrea can never be calibrated from HarvestStat: it holds no sorghum yields for
either, although both have a mapped sorghum area (0.573 and 0.133 Mha).

## Calendar A/B test

The Inception Report's Table 2.0 calendar and the GEOGLAM CM4EW sorghum-specific calendar
disagree for six products. Rather than choose between them on authority, both are run and scored
against HarvestStat sorghum yields.

```bash
python sorghum_pipeline/build_calendar.py                 # writes both calendars
EE_PROJECT=... python sorghum_pipeline/run_all_sorghum.py --stage all --submit                          # arm A
EE_PROJECT=... python sorghum_pipeline/run_all_sorghum.py --calendar cm4ew --differing-only --submit    # arm B
EE_PROJECT=... python sorghum_pipeline/zonal_sorghum.py             # arm A
EE_PROJECT=... python sorghum_pipeline/zonal_sorghum.py --arm B     # arm B
python sorghum_pipeline/score_calendar_ab.py
```

**The arms differ in exactly one thing.** Arm B takes CM4EW's planting window and cycle, but its
SOS window is re-derived with arm A's rule. Deriving each arm's SOS by its own source's rule would
have made Sudan and Somalia differ too, although their planting windows agree exactly, and any
result would then have been partly an artefact of the rule rather than of the calendar.

**Scoring.** The primary metric is the Spearman correlation between CPI and reported sorghum
yield across reporting units, which needs **no yield ceiling** and so cannot be contaminated by a
fitted Ym. Mean absolute error is reported as a secondary metric with the ceiling **held fixed
across the arms**, under three regimes, because refitting a ceiling per arm absorbs a level shift
by construction — that is how the WHC A/B in this project produced a win that vanished once both
arms shared a ceiling. A paired bootstrap over units gives the interval.

**Four of the six differing products can be scored**: Ethiopia Meher (76 units), Kenya Long rains
(44), Uganda 1st rains (70) and South Sudan Main (2, almost certainly too few). Eritrea Kremti
cannot — Eritrea is absent from HarvestStat — and there is no second-season sorghum series for
South Sudan.
