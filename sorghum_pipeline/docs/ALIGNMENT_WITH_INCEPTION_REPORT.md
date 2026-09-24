# Sorghum pipeline against the Inception Report

Source: *Inception Report — Crop Conditions Monitoring and Forecasting, ICPAC FSRP-AF*, 81 pages.
Sorghum method is in **Section 3.1, "Closing the sorghum / millet / teff crop-type gap"**
(pp. 21–22), the calendars in **Table 2.0** (pp. 16–17), and the risk register on p. 59.

## 1. The crop-type gap: what the report proposed, and where we now stand

The report sets out a **three-tier strategy** with a go/no-go gate, rather than treating the gap
as one classification task.

| Tier | The report's proposal | Status |
|---|---|---|
| **Tier 1** — area-fraction prior, "the operational default from day one" and "the benchmark for all later work". MapSPAM physical-area fractions gated by the ASAP / DE Africa cropland mask; zonal indicators as area-weighted means | **Delivered and exceeded.** The crop-type mask series is Tier 1 built properly: SPAM shares over a **four-lineage, sixteen-source-year cropland vote** rather than one cropland product, reweighted by agro-climatic suitability and satellite crop evidence, **calibrated to sub-national statistics**, at **100 m** rather than SPAM's 9 km | done |
| **Tier 2** — label acquisition, the gating step. Radiant MLHub, Lacuna Fund, Geo-Wiki, ICRISAT trial sites; weak labels bootstrapped from GEOGLAM calendars | **Not started.** No sorghum field labels have been secured anywhere in the region | open |
| **Tier 3** — targeted classification, conditional on Tier 2. Sorghum as a **temporal-shape problem**: dekadal Sentinel-2 fused with Sentinel-1 VV/VH, classified on **phenometric** features (start of season, peak, senescence rate, length of season), not a single-date composite | **Not attempted**, correctly, because Tier 2 has not delivered | blocked on Tier 2 |
| **Go / no-go gate** — Tier 3 adopted only if it beats the Tier 1 baseline on **zone-level anomaly skill against historical FEWS NET IPC phase classifications**, same metric, same held-out seasons | Not yet exercised. The gate needs a Tier 3 candidate first | pending |

**What this means in practice.** The report's own benchmark is what the pipeline now runs on, and
it is a stronger version of that benchmark than the report assumed would be available. The
sorghum products are therefore a legitimate Tier 1 delivery, not a placeholder. Tier 3 remains
open and is still gated exactly as the report specifies.

**One deviation worth stating.** The report specifies Tier 1 as **continuous area weights**, with
zonal indicators computed as area-weighted means "rather than over a hard crop mask". The pipeline
does both: the per-pixel product is computed inside the binary `mask_sorghum`, and the admin
aggregation in `zonal_sorghum.py` is weighted by `frac_sorghum`, as the report requires. The
binary mask turns a whole 100 m cell on once sorghum reaches 10 % of it, so it covers far more
ground than the crop does — Sudan's sorghum mask is 13.1 Mha over a 6.3 Mha crop. **Never compute
area from the mask.** Where a hard stratum is too generous, `sorghum_mask(ee, country,
min_fraction=25)` tightens it.

## 2. Crop calendars

The pipeline uses **Table 2.0**, as instructed. Season names are the ones FEWS NET and the
GEOGLAM Crop Monitor use operationally, which is also what HarvestStat reports against, so the
calibration matching is direct.

GEOGLAM CM4EW v1.3 also ships a **sorghum-specific** calendar in its shapefile, where Table 2.0
gives one generalised calendar per country covering every crop it monitors. They are carried in
the `cm4ew_*` columns of the calendar and **disagree for six of the nine products CM4EW covers**:

| Product | Report Table 2.0 | GEOGLAM CM4EW, sorghum-specific | Gap |
|---|---|---|---|
| Kenya Long rains | Mar-d1 to Apr-d3 | **Feb-d1** to Apr-d3 | 3 dekads earlier |
| Ethiopia Meher | Jun-d1 to Jul-d3 | **May-d2** to Jul-d2 | 2 dekads earlier |
| Eritrea Kremti | Jun-d1 to Jul-d3 | **Jul-d1** to Aug-d3 | 3 dekads later |
| Uganda 1st rains | Mar-d1 to Apr-d3 | **Apr-d1** to May-d3 | 3 dekads later |
| South Sudan Main | Apr-d1 to Jun-d3 | Apr-d2 to Jun-d3 | 1 dekad |
| South Sudan 2nd | Jul-d1 to Aug-d3 | **Aug-d1** to Sep-d3 | 3 dekads later |
| Sudan Kharif, Somalia Gu and Deyr | — | — | **agree exactly** |

These are not errors on either side. A generalised country calendar is led by the dominant crop,
which is maize in Kenya and Uganda and teff or maize in Ethiopia, while CM4EW's shapefile is
sorghum-specific. **The four three-dekad gaps are the highest-value question to put to national
partners at the validation workshop**, because a planting window that is wrong by three dekads
puts the flowering stage — which carries the yield weight — in the wrong part of the season.

The Uganda row deserves a second look on its own terms: Table 2.0 notes Karamoja running
**Apr–Aug** separately from the national Mar–Jun first rains, and Karamoja is Uganda's main
sorghum zone. The CM4EW sorghum window of Apr-d1 to May-d3 matches Karamoja, not the national
row. A Karamoja-specific window is probably the right answer for sorghum.

## 3. Everything else, item by item

| Report | Pipeline |
|---|---|
| Onset by **cue fusion** (Sentinel-2 red edge + MODIS FPAR, Sentinel-1 filling cloud gaps), gated to the long-term-normal onset climatology; rainfall-anchored where green-up is unreliable (§3.2) | As specified. Second and short seasons route to the CHIRPS 25/20 mm rule with the P/ET₀ ≥ 0.5 gate |
| Planting dekad = SOS minus an emergence offset, **2 dekads for maize, 1 for wheat and teff** (§3.2) | **Sorghum is not specified in the report.** 2 dekads is used, flagged `FIRST PASS` in `sorghum_params.py` |
| **45-year CHIRPS false-onset screen** (§3.2, risk register p. 59) | The 5 + 7 gate is available in `src.wrsi_feedback.dryspell_false_start` but is **not yet wired into the sorghum runner**. Open item |
| Full **FAO-56/33 dekadal water balance** in Earth Engine, Hargreaves ET₀ from ERA5-Land, spatial water-holding capacity, initialised at each pixel's planting dekad (§3.2) | As specified, with sorghum's FAO-56 Kc curve 0.30 → 1.05 → 0.55 and a **1.5 m** root zone |
| **Stage-weighted** stress: flowering and grain filling weighted heavily, emergence and maturity lightly (Table 3.0) | FAO-33 **sorghum** Ky 0.2 / 0.55 / 0.45, against maize 0.4 / 1.5 / 0.5. Sorghum's flowering weight is barely a third of maize's, which is the single most important crop difference |
| Yield **version 1** = CPI / 100 × attainable ceiling; **version 2** = empirical ML on HarvestStat plus soil predictors (§3.1, p. 21) | Version 1 implemented. **The ceiling is not yet fitted**, so the yield band is not reportable. Version 2 is not started |
| GDD base temperature **~10 °C** for maize, sorghum, millet and rice, cap 30–34 °C (Table 7.0, p. 31) | The sorghum runner uses the fixed-cycle clock, not the GDD clock. Aligning the two is an open item, and the GDD work already shows the fixed cycle is the weaker assumption |
| **Photothermal extension** for photoperiod-sensitive sorghum and millet landraces, which flower on shortening days largely independent of sowing date; "documented as a roadmap item, not yet activated in code" (§3.3.3, pp. 32–33) | Not implemented, consistent with the report. **This matters most exactly where the sorghum area is** — Sudan, South Sudan and Ethiopia, where such landraces dominate. A pure thermal clock places modelled flowering weeks early there |
| HarvestStat coverage: 9 of 11 countries, **Eritrea and Djibouti absent** (Table 4.0, p. 21) | Confirmed independently. Tanzania also has **no sorghum yields** despite being in HarvestStat, so three of the ten sorghum countries cannot be calibrated |
| Prioritise data-rich countries for the yield model, treat thin-label countries as **monitors** (p. 59) | Adopted. Sudan, Ethiopia, Kenya, Uganda and Somalia can be calibrated; Tanzania, Eritrea and South Sudan are monitors |

## 4. Open items, in priority order

1. **Fit the yield ceiling.** Needs the 2024 CPI, then `zonal_sorghum.py` and
   `calibrate_ym_sorghum.py --write`. Somalia has the best sorghum yield record in the region,
   839 Gu and 757 Deyr observations, better than its maize record.
2. **Put the six calendar disagreements to national partners**, Kenya, Ethiopia, Eritrea, Uganda
   and South Sudan first, and resolve the Karamoja question for Uganda.
3. **Wire in the false-onset screen**, which the report specifies and the code already has.
4. **Tier 2 labels.** Every further improvement is gated on them, and nothing has been secured.
5. **Photothermal clock** for the northern-tier landraces, which is where most of the region's
   sorghum is.
6. **Two parameters carried over from maize** with no sorghum source: the 2-dekad emergence
   offset and the 0.06 heat loss per heat-degree-dekad. Both are marked `FIRST PASS` in code.
