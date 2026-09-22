---
title: "Maize Yield Calibration — 2024 Season"
subtitle: "Fitting the attainable-yield ceiling of the CPI yield model to HarvestStat, eight ICPAC countries"
date: "22 September 2026"
---

# 1. Purpose

The ICPAC planting pipeline estimates maize yield as

$$Y_a = \frac{CPI}{100} \times Y_m$$

where the Crop Performance Index (CPI, 0–100) is the multi-stress relative yield — $(1-S_{water})(1-S_{heat})(1-S_{veg})$, stage-weighted — and $Y_m$ is the **attainable yield ceiling** for the country and season. The CPI carries the season's signal; $Y_m$ only sets the absolute level. The pipeline ships with default ceilings of **6.0 t/ha** (medium/long-season maize) and **4.5 t/ha** (short-duration maize), which are agronomic potentials rather than what smallholders actually harvest.

This report documents how $Y_m$ was fitted to reported sub-national maize yields for every country with a 2024 maize run, how well the fitted yields reproduce held-out statistics, and which countries remain uncalibrated. It consolidates results that were previously spread across `src/cpi.py`, `Cropyield-Data/*.csv` and the atlas.

# 2. Method

## 2.1 Data

| Role | Dataset | Notes |
|---|---|---|
| Model CPI, 2024 | ICPAC planting pipeline, main maize season per country | Kenya wards and Ethiopia woredas from the 2024 risk monitor; other countries from the admin-2 statistics `newc_<Country>_<Season>_2024_L2_skill_WKT.csv` |
| Reported yield | HarvestStat Africa v1.2 (Lee et al., 2025) | FEWS NET sub-national units; maize, matching season |

## 2.2 Matching model and statistics

HarvestStat reports on FEWS NET administrative units, which differ from the pipeline's GADM units. The 2024 admin CPI (Kenya wards and Ethiopia woredas from the risk monitor; admin-2 statistics elsewhere) is aggregated onto the HarvestStat units by polygon overlap, **weighted by the maize area in each overlap** (`calibrate_ym_local.py`), so a large unit with little maize does not dominate.

For every country the reported yield is the **median over the available years** — a *typical year* — which is robust to a single bad season; unit values above 8 t/ha are discarded as implausible for rainfed smallholder maize (they occur in the Burundi and Uganda series).

## 2.3 Fit and test

$Y_m$ is the least-squares slope through the origin between reported yield $y$ and $c = CPI/100$:

$$Y_m = \frac{\sum y\,c}{\sum c^2}$$

The skill is measured out of sample: the units are split 70 % for fitting and 30 % for testing, repeated 200 times (random splits), and the **mean absolute error (MAE) on the held-out units** is reported for the calibrated ceiling and for the default ceiling. The Pearson correlation $r$ between predicted and reported yields shows whether the model also reproduces the **pattern** between units — a calibrated level with $r \approx 0$ means the map gets the average right but cannot tell which units yielded more.

This is the standard way of anchoring a relative-yield index to reported yields (Doorenbos & Kassam, 1979; Allen et al., 1998; Steduto et al., 2009); the gap between potential and actual smallholder yields that it absorbs is well documented (Lobell et al., 2009; van Ittersum et al., 2013).

# 3. Results

| Country · season | $Y_m$ used | Units (n) | Years of statistics | Test MAE, calibrated | Test MAE, default | $r$ | Status |
|---|---|---|---|---|---|---|---|
| Kenya · Long rains | **2.34** | 45 | 2015–2024 | 0.68 | 2.26 | 0.57 | Calibrated — level and pattern |
| Kenya · Short rains | **1.44** | 44 | 2016–2024 | 0.39 | 1.94 | 0.36 | Level, weak pattern |
| Ethiopia · Meher | **4.14** | 76 | 2012–2021 | 0.71 | 1.38 | 0.64 | Calibrated — level and pattern |
| Rwanda · Season A | **2.61** | 30 | 2010–2017 | 0.37 | 2.75 | −0.07 | Level only |
| Burundi · Season A | **1.88** | 16 | 2012–2016 | 0.71 | 3.57 | 0.28 | Level only |
| Somalia · Gu | **1.02** | 18 | 2015–2024 | 0.24 | 1.58 | 0.34 | Level only |
| Uganda · 1st rains | **2.34** | 74 | 2008–2009 | 1.24 | 2.90 | −0.14 | **Provisional** (statistics end 2009) |
| Tanzania · Msimu, Masika | 6.0 (default) | — | none | — | — | — | **Uncalibrated** — no maize yields in HarvestStat |
| South Sudan · Main | 6.0 (default) | — | none | — | — | — | **Uncalibrated** — no maize yields in HarvestStat |

All seven fits use the same method and the same kind of target — the **typical year** (median of the available years). The default ceiling is 6.0 t/ha, 4.5 t/ha for Kenya short rains.

![Figure 1. Predicted against reported yield, per HarvestStat unit, with the default ceiling (grey) and the calibrated ceiling (green). Dashed: 1:1. All countries use the same typical-year fit.](fig1_predicted_vs_reported.png)

![Figure 2. Mean absolute error on held-out units, default versus calibrated ceiling. \*Uganda provisional.](fig2_test_error.png)

## 3.1 What the numbers say

* **Calibration removes the level bias everywhere it is possible.** The default ceilings over-predicted reported yields two- to sevenfold; held-out error falls by 49–87 % (Burundi 3.57 → 0.71 t/ha, Rwanda 2.75 → 0.37, Kenya long rains 2.26 → 0.68, Ethiopia 1.38 → 0.71).
* **Kenya long rains and Ethiopia Meher also reproduce the pattern** between units (r 0.57 and 0.64); Kenya short rains weakly (r 0.36). Ethiopia's fit now rests on 76 zones over ten years, instead of the 8 regions from 2021 behind the earlier value of 4.42 t/ha.
* **Rwanda, Burundi and Somalia are level-only.** Their fitted yields cluster around the national mean while reported yields spread widely (Figure 1). The 2024 CPI does not explain the multi-year differences between their units — those are driven by soils, inputs and management that a one-season water/heat/vegetation index does not see. Use these yields for national and seasonal levels, not to rank districts.
* **Typical year versus the 2024 season.** The typical-year ceilings are lower than fits to a single good season: Kenya's pipeline value, fitted to 2024 county yields alone, is 3.2/2.1 t/ha by elevation (held-out error 0.40 t/ha against 2024). The typical year is the better default because it applies to any season, including those without statistics yet. Somalia, the one other country with 2024 statistics, was also refitted on 2024 alone: the ceiling was unchanged (1.04 vs 1.02 t/ha) and the correlation lower (0.17 vs 0.34).
* **Uganda is provisional.** HarvestStat's Ugandan maize series is 2008–2009 only, fifteen years before the model season, and contains implausible district values (up to 12.7 t/ha before the 8 t/ha screen). The fitted 2.34 t/ha is a plausible level but its test error (1.24 t/ha) is the largest in the set.
* **Tanzania and South Sudan cannot be calibrated from HarvestStat**, which holds no maize yields for either. Their yields remain at the 6.0 t/ha default and — judging by every country where the default could be tested — are likely several times too high.

# 4. Where each value is used

All products use the typical-year ceilings (updated 22 September 2026):

| Place | Values |
|---|---|
| `src/cpi.py` `YM_CAL` — all future pipeline runs | Kenya 2.34 (long rains), 1.44 (short rains); Ethiopia 4.14; Rwanda 2.61; Burundi 1.88; Somalia 1.02; Uganda 2.34 (provisional) |
| `src/cpi.py` `YM_HIGHLAND` | switched off (the 3.2 / 2.1 t/ha Kenya highland split was a 2024-season fit; kept in a comment to reproduce it) |
| Crop-type atlas yield layer | same ceilings; Tanzania and South Sudan shown hatched at the 6.0 t/ha default |
| World Bank progress slide 2 | same ceilings for the Kenya and Ethiopia yield maps |

The **2024 GEE yield assets** already produced (`cpi_*_2024_aezym`) were built with the earlier values; yield is CPI × Ym, so they can be rescaled without rerunning the model (multiply by new Ym / old Ym).

# 5. Next steps

1. **Rescale or re-export the 2024 yield assets** (`cpi_*_2024_aezym`) with the typical-year ceilings if they are used downstream.
2. **Recalibrate each season** as HarvestStat adds years; `calibrate_ym_local.py` reruns in minutes.
3. **Tanzania and South Sudan:** obtain a national maize yield (FAOSTAT or the national statistics office) to set a level-only ceiling; sub-national yields for Tanzania (National Sample Census of Agriculture) would allow a full fit.
4. **Beyond level-only calibration:** the pattern between units would need either multi-year model runs (so model and statistics cover the same years) or covariates for management and soils; a single 2024 CPI cannot carry it.

# 6. Reproducibility

```bash
cd planting_pipeline
python calibrate_ym_local.py                            # all seven calibrated countries (typical-year fit)
python yield_calibration_2024/make_figures.py           # figures in this report
```

Outputs: `Cropyield-Data/ym_calibration_local.csv` (fits) and `ym_calibration_local_units.csv` (per unit); `Cropyield-Data/ym_recalibration_7030_summary.csv` and `ym_recalibrated_yields.csv` (Kenya, Ethiopia).

# References

Allen, R. G., Pereira, L. S., Raes, D., & Smith, M. (1998). *Crop Evapotranspiration — Guidelines for Computing Crop Water Requirements*. FAO Irrigation and Drainage Paper 56. FAO, Rome.

Doorenbos, J., & Kassam, A. H. (1979). *Yield Response to Water*. FAO Irrigation and Drainage Paper 33. FAO, Rome.

Lee, D., Anderson, W., Chen, X., Davenport, F., Shukla, S., Sahajpal, R., Budde, M., Rowland, J., Verdin, J., You, L., et al. (2025). HarvestStat Africa — Harmonized subnational crop statistics for Sub-Saharan Africa. *Scientific Data* (in revision); data: Dryad. https://doi.org/10.5061/dryad.vq83bk42w (v1.2, 2026).

Lobell, D. B., Cassman, K. G., & Field, C. B. (2009). Crop yield gaps: their importance, magnitudes, and causes. *Annual Review of Environment and Resources*, 34, 179–204. https://doi.org/10.1146/annurev.environ.041008.093740

Rembold, F., Meroni, M., Urbano, F., Csak, G., Kerdiles, H., Perez-Hoyos, A., Lemoine, G., Leo, O., & Negre, T. (2019). ASAP: A new global early warning system to detect anomaly hot spots of agricultural production for food security analysis. *Agricultural Systems*, 168, 247–257. https://doi.org/10.1016/j.agsy.2018.07.002

Steduto, P., Hsiao, T. C., Raes, D., & Fereres, E. (2009). AquaCrop — The FAO crop model to simulate yield response to water: I. Concepts and underlying principles. *Agronomy Journal*, 101(3), 426–437. https://doi.org/10.2134/agronj2008.0139s

van Ittersum, M. K., Cassman, K. G., Grassini, P., Wolf, J., Tittonell, P., & Hochman, Z. (2013). Yield gap analysis with local to global relevance — A review. *Field Crops Research*, 143, 4–17. https://doi.org/10.1016/j.fcr.2012.09.009
