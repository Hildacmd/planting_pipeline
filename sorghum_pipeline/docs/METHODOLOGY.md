---
title: "Sorghum Monitoring Pipeline for the ICPAC Region"
subtitle: "Planting window, water balance, crop performance index and yield for sorghum in ten Member States"
author: "ICPAC · Food Systems Resilience Programme, Additional Financing (FSRP-AF)"
date: "23 September 2026"
---

# 1. Why sorghum, and why not simply re-run the maize pipeline

Sorghum is the second cereal of the IGAD region by area and the first in its drylands. The
crop-type masks place **6.32 Mha in Sudan, 1.84 Mha in Ethiopia and 0.57 Mha in Tanzania**,
against 1.54 Mha of maize in the whole of Kenya. It is grown where the rains are least reliable,
which is exactly where anticipatory action is needed, and where a maize-shaped monitoring
product is least able to help.

The temptation is to run the existing pipeline over a sorghum mask. That would be wrong in four
specific ways, each of which is corrected here.

**The seasons are different.** GEOGLAM's Crop Monitor for Early Warning puts Kenyan sorghum
planting from **Feb-d1**, five dekads before the maize long rains, and Ethiopian sorghum from
**May-d2**, a month after maize. Running the maize window would search for green-up in the wrong
dekads and, where it found any, would date the crop wrongly.

**The cycle lengths are different, and they differ between countries.** CM4EW gives sorghum
cycles from **76 days in the Somali Deyr to 181 days in Kenya**. The maize pipeline uses one
fixed 12-dekad cycle everywhere, an assumption already shown to be wrong by 68 days for highland
maize. Imposing it on sorghum would place the flowering window, where the yield weight sits, in
the wrong part of the season.

**The water response is different, and this is the substantive point.** The FAO-33 yield
response factor for sorghum is **0.9 in total against 1.25 for maize**, and the flowering stage
carries **0.55 against 1.50**. A water deficit at flowering costs maize nearly three times what
it costs sorghum. A sorghum crop scored with maize factors would be declared failed in seasons
it comes through — the failure mode that matters most, because sorghum is grown where the rains
fail.

**The mask would fail silently.** WorldCereal has no sorghum class, and `run.crop_mask_image`
falls through to the temporary-crops extent for any crop that is not maize. A sorghum run left
on the default would compute over all cropland and label the result sorghum. This pipeline takes
the mask from the crop-type mask series instead, and raises rather than falling back if a
country has none.

# 2. Data

| Role | Dataset | Notes |
|---|---|---|
| Crop calendar | GEOGLAM Crop Monitor for Early Warning v1.3 | planting, vegetative and harvest day of year, per country and monitoring region |
| Crop mask | ICPAC crop-type masks, 100 m | `mask_sorghum` and `frac_sorghum`; ten countries |
| Crop coefficients | FAO-56, Allen et al. (1998), Tables 11, 12, 22 | stage lengths, Kc, rooting depth |
| Yield response | FAO-33, Doorenbos & Kassam (1979), Table 24 | stage Ky |
| Heat threshold | Prasad et al. (2008, 2015); Singh et al. (2015) | sorghum pollen viability at flowering |
| Rainfall | CHIRPS daily | onset rule and water balance |
| Temperature | ERA5-Land daily 2 m | Hargreaves reference evaporation, heat stress |
| Soil | SoilGrids through Saxton and Rawls | root-zone water-holding capacity |
| Phenology | Sentinel-2 NDRE, Sentinel-1 RVI, MODIS FPAR | fused green-up |
| Calibration and validation | HarvestStat Africa v1.2, sorghum | 5,340 yield records in the region |

# 3. Method

The engine is unchanged from the maize pipeline; only the crop parameters and the mask change.

## 3.1 Season calendar

CM4EW gives the day of year at which each phase begins, per country and monitoring region. The
windows are derived as

    planting window = planting DOY .. vegetative DOY - 1
    SOS window      = planting + 1 dekad .. vegetative + 3 dekads
    cycle           = harvest DOY - planting DOY, in dekads, clamped to 9 .. 18

Green-up follows planting by about two dekads, and the tail allows for the late end of a
staggered planting front, which is how the maize windows are set. Regions within a country agree
in CM4EW, so the modal day of year is taken and the number of contributing regions recorded.

**GEOGLAM CM4EW is carried as a second arm, and both were run.** Its shapefile holds a
sorghum-specific calendar where Table 2.0 gives one generalised calendar per country. They disagree
for six of the nine products CM4EW covers, by three dekads for Kenya, Eritrea, Uganda and South
Sudan's second season. The arms differ in exactly one thing: arm B takes CM4EW's planting window
and cycle, with the SOS window re-derived by arm A's rule, so a difference cannot be an artefact of
the rule.

**The A/B found no difference.** Scored against HarvestStat on the three products that can be
validated: Ethiopia Δρ −0.044 [−0.279, 0.187], Kenya −0.046 [−0.187, 0.073], Uganda −0.007
[−0.293, 0.274]. Arm A is nominally ahead in all three and **every interval spans zero**. The
report's calendar therefore stands on the grounds of not being beaten rather than of winning, and
the three-dekad disagreements remain a question for national partners that this test cannot close.
Eritrea and South Sudan could not be scored at all: Eritrea is absent from HarvestStat, and South
Sudan has two units.

### 3.1.1 Calendar provenance, and where a window was inferred rather than read

Every calendar row records its source in `crop_calendar_source`, and the GEOGLAM CM4EW window is
carried alongside in `cm4ew_*` so the two can be compared. Three source classes exist and they do
not carry equal weight.

**Read from Table 2.0.** The planting months are published for that country and season. Sixteen of
the eighteen sorghum products, and eighteen of the twenty maize products, are of this kind.

**Inferred from the season span.** Table 2.0 gives **one** planting column per country. Where a
country has two seasons, the published months describe the dominant one and the second has none.
For those, the rule applied is:

> planting occupies the **first two months** of the span given in the "Main season(s)" column.

**This is an assumption, not a source.** It affects one row: South Sudan's second season, where the
table gives `Apr-Jun` for the country and `2nd Jul-Nov (SW)` as the span, from which Jul to Aug was
taken. A gap between an inferred window and the operative calendar is a gap against a guess, so it
is reported separately and never counted as a disagreement between sources. In this case GEOGLAM,
which does publish a second-season maize window, gives Aug-d1 to Sep-d3 and **agrees exactly with
the operative calendar**, which is the better evidence of the two.

**Not in Table 2.0 at all.** Djibouti, which the report records as minimal cropping.

### 3.1.2 What to do about a disagreement: the Ethiopia Meher case

The maize provenance check (`build_calendar_maize.py`) puts the operative calendar, Table 2.0 and
the GEOGLAM maize calendar side by side. Three products disagree by two dekads or more, and one is
large enough to matter.

**Ethiopia Meher maize.** The operative window opens at Apr-d1; Table 2.0 says Jun-d1, six dekads
later, and GEOGLAM says May-d2, four dekads later. It is the largest maize product in the region at
2.03 Mha, so a two-month error would be consequential.

**The operative window is kept, for three reasons that should be stated together.**

1. **It is crop-specific where the others are not.** Table 2.0 gives one calendar per country
   covering every crop it monitors, and Ethiopia's row is led by the Kiremt onset that governs teff
   and short-cycle cereals. The operative row carries its own rationale: long-cycle maize planted on
   **Belg** moisture in the western and south-western highlands and the Rift, which is genuinely
   earlier than the Kiremt-onset crops.
2. **The product behaves as though the window is right.** Ethiopia Meher maize has the **best rank
   skill of any maize product in the series**: Pearson r 0.64 against reported zone yields, held-out
   error 0.71 against 1.38 t/ha for the uncalibrated ceiling. A planting window wrong by four to six
   dekads would place the modelled flowering stage, which carries three times the yield weight of
   any other, about two months from the truth. That is not consistent with the best pattern skill in
   the set.
3. **Changing it silently would move every Ethiopian maize product** and invalidate the calibration
   that currently fits.

**So the position is: operate on the current window, cite the discrepancy, and put it to Ethiopian
partners.** The discrepancy is recorded in `config/season_calendar_maize_provenance.csv` with the
gap in dekads against both independent sources, so it travels with the data rather than living only
in a conversation.

**It was settled. The A/B was run on 26 September 2026 and the operative window wins
significantly** — the first calendar comparison in this project that separates at all.

Three arms, identical in everything but the planting window, scored against 74 HarvestStat zones
matched on all three. The SOS window of each alternative was derived from its published planting
months by the operative rule, so the derivation is not a confounder.

| Arm | SOS window | Spearman ρ | Pearson r | $Y_m$ fit | LOO MAE |
|---|---|---|---|---|---|
| **operative** | Apr-d2 to Jun-d3 | **0.573** | **0.583** | 4.09 | **0.660** |
| GEOGLAM CM4EW | May-d3 to Aug-d2 | 0.211 | 0.252 | 3.79 | 0.765 |
| Report Table 2.0 | Jun-d2 to Aug-d3 | 0.106 | 0.215 | 3.69 | 0.913 |

Paired bootstrap on ρ, 2000 resamples over the zones:

| Comparison | Δρ | 95 % interval | Verdict |
|---|---|---|---|
| operative − CM4EW | **+0.355** | [+0.163, +0.564] | **significant**, operative wins 100 % |
| operative − report | **+0.463** | [+0.229, +0.710] | **significant**, operative wins 100 % |
| CM4EW − report | +0.104 | [−0.074, +0.293] | not separable |

**Three things make this convincing rather than merely favourable.**

1. **Both intervals exclude zero.** Every previous A/B in this project returned an interval spanning
   zero — the water-holding-capacity test, the sorghum calendar test, the vegetation-term swap. This
   one does not.
2. **Skill falls monotonically as planting is pushed later**, 0.573 → 0.211 → 0.106, and the
   held-out error rises monotonically with it, 0.660 → 0.765 → 0.913 t/ha. A single pairwise test
   could not have shown that; it is why three arms were run rather than two.
3. **Coverage falls the same way.** The number of admin-2 units returning a valid CPI drops from 74
   to 72 to 60 as the window moves later: the later windows are not merely mis-timing the crop, they
   are missing it.

**Conclusion.** The operative window is correct for Ethiopian Meher maize, and the two published
calendars are wrong for this crop — as anticipated, because both are country-generalised and led by
the Kiremt-onset crops, while the operative row is specific to long-cycle maize on Belg moisture.
The prior reasoning from skill is confirmed rather than overturned.

**What this does and does not license.** It settles Ethiopia Meher maize. It says nothing about the
other two maize disagreements (Uganda 1st and 2nd rains), and nothing about sorghum, whose own
calendar A/B could not separate its arms. It is, though, direct evidence that a crop-specific
calendar can beat a country-generalised one by a wide margin, which is the argument for collecting
crop-specific calendars from national partners rather than adopting a published table wholesale.

## 3.2 Planting date

Main seasons use the fused green-up: a dekadal greenness proxy from Sentinel-2 red edge and
MODIS FPAR, gap-filled by the Sentinel-1 radar vegetation index, with start of season taken as
the first sustained crossing of a quarter of the season amplitude, held within two dekads of the
climatological onset. Planting is then

$$\text{planting dekad} = \mathrm{SOS} - 2 .$$

Second and short seasons use the FEWS rainfall rule, $P_t \ge 25$ mm with
$P_{t+1}+P_{t+2}\ge 20$ mm and $P_t/ET_{0,t}\ge0.5$, because green-up detection is unreliable
there and is defeated outright by cloud in the Rwandan and Burundian highlands.

The two-dekad emergence offset is **carried over from maize and is a first pass**. Sorghum
emerges in four to six days but builds canopy more slowly, so the same offset is plausible; no
sorghum-specific study was used. It is the single parameter most worth checking against farmer
records.

## 3.3 Water balance

FAO-56 dekadal balance from each pixel's own planting dekad, with Hargreaves reference
evaporation from ERA5-Land, CHIRPS rainfall and a SoilGrids root-zone bucket integrated to
**1.5 m**, the FAO-56 mid-range for sorghum against 1.0 m for maize:

$$AET_t=\min(SW_{t-1}+P_t,\ K_{c,t}ET_{0,t}),\qquad
SW_t=\min(SW_{t-1}+P_t-AET_t,\ WHC),\qquad
\mathrm{WRSI}=100\frac{\sum AET}{\sum WR}.$$

The Kc curve is FAO-56 grain sorghum, $0.30 \rightarrow 1.05 \rightarrow 0.55$ over 2, 4, 4 and
3 dekads. **Kc_end is 0.55, not the maize 0.35**, because sorghum heads are cut with the canopy
still partly green. The four stages are rescaled proportionally onto each product's own cycle
length.

## 3.4 Crop performance index

$$\mathrm{CPI}=100\,(1-S_{\text{water}})(1-S_{\text{heat}})(1-S_{\text{veg}})$$

$$S_{\text{water}}=\sum_s K_{y,s}\Big(1-\frac{AET_s}{WR_s}\Big),\qquad
K_y = 0.2,\ 0.55,\ 0.45 \quad (\text{maize: } 0.4,\ 1.5,\ 0.5)$$

$$S_{\text{heat}}=\min\Big(1,\ 0.06\!\!\sum_{\text{flowering}}\!\!\max(T_{\max}-36,\,0)\Big),
\qquad S_{\text{veg}}=0.4\,(1-\mathrm{VCI})$$

The heat cap of 36 °C reflects sorghum's higher tolerance; it is applied to a dekad-mean maximum,
so it fires only where a whole dekad averages above it. **The slope of 0.06 per heat-degree-dekad
is the maize value and is a first pass**: no sorghum-specific loss rate was found in the
literature reviewed. Heat results should not be reported on their own until it is calibrated.

## 3.5 Yield

$$Y_a=\frac{\mathrm{CPI}}{100}\times Y_m$$

$Y_m$ is fitted to HarvestStat sorghum yields by least squares through the origin, with the median
over the available years as the target and a 70/30 split repeated 200 times for the held-out error.
The admin-2 CPI is aggregated onto the HarvestStat units by polygon overlap, weighted by the
sorghum area in each overlap and measured in an equal-area projection.

**Fitted ceilings, 24 September 2026. Twelve of eighteen products.**

| Country · season | $Y_m$ t/ha | Units | Years | Held-out MAE, fitted vs uncalibrated | $r$ | Status |
|---|---|---|---|---|---|---|
| Ethiopia · Meher | 2.60 | 64 | 2012 to 2021 | 0.43 vs 0.52 | 0.21 | level only |
| **Kenya · Long rains** | **1.41** | 27 | 2015 to 2016 | **0.27 vs 1.16** | **0.54** | **level and pattern** |
| Kenya · Short rains | 1.09 | 24 | 2016 to 2017 | 0.19 vs 0.73 | −0.15 | level only |
| Uganda · 1st rains | 1.31 | 47 | 2009 | 0.67 vs 1.45 | −0.02 | level only |
| Uganda · 2nd rains | 1.14 | 50 | 2008 | 0.64 vs 1.03 | −0.21 | level only |
| Rwanda · Season A | 1.34 | 23 | 2010 to 2017 | 0.48 vs 1.32 | 0.43 | level, weak pattern |
| Rwanda · Season B | 1.37 | 30 | 2009 to 2017 | 0.32 vs 1.22 | −0.17 | level only |
| Burundi · Season A | 0.55 | 7 | 2013 to 2016 | 0.28 vs 2.00 | −0.17 | level only |
| Burundi · Season B | 0.90 | 9 | 2012 to 2014 | 0.13 vs 1.70 | 0.37 | level, weak pattern |
| Somalia · Gu | 0.41 | 12 | 2015 to 2024 | 0.16 vs 1.52 | 0.36 | level, weak pattern |
| Somalia · Deyr | 0.87 | 12 | 2015 to 2024 | 0.21 vs 0.26 | −0.04 | level only |
| Sudan · Kharif | 0.80 | 16 | 2015 to 2023 | 0.27 vs 1.08 | −0.14 | level only |

**Six products have no fitted ceiling.** South Sudan Main has two HarvestStat reporting units and
its second season none; Tanzania and Eritrea have no sorghum yields in HarvestStat at all; Ethiopia
Belg has two records from a single unit. They keep the uncalibrated default and their atlas yield
layers are hatched.

Calibration removes a large level error everywhere it is possible. The uncalibrated default
over-predicted by factors of two to four, and the held-out error falls by 17 to 92 %.

**Only Kenya carries rank skill, and one product ranks backwards.** This is the most important
result in the set. Across the twelve fitted products the Pearson $r$ between predicted and reported yield is above
0.45 in **one**: Kenya long rains. It is negative in five — Kenya short rains, Uganda both seasons,
Rwanda Season B and Burundi Season A. A negative rank correlation is worse than no information. The
Ethiopian case is explained by the asset diagnostics: Meher sorghum runs at WRSI 99 with
$S_{\text{water}}$ of 1.3 %, so the water balance carries almost no signal and the index is driven
by the vegetation term alone. **Report Ethiopian and Ugandan sorghum CPI as a level, not a
ranking.**

# 4. Coverage

Eighteen products across ten countries.

| Country | Seasons | Calendar source | Mapped sorghum, Mha | HarvestStat units |
|---|---|---|---|---|
| Sudan | Kharif | GEOGLAM | 6.320 | 18, 1975 to 2023 |
| Ethiopia | Meher, Belg | GEOGLAM, maize | 1.836 | 76, 1993 to 2021 |
| Tanzania | Msimu, Masika | maize | 0.573 | **none** |
| South Sudan | Main, 2nd | GEOGLAM | 0.295 | 2, 1975 to 2010 |
| Kenya | Long rains, Short rains | GEOGLAM, maize | 0.209 | 44 and 35 |
| Uganda | 1st rains, 2nd rains | GEOGLAM, maize | 0.199 | 70 and 70, 2008 to 2009 |
| Somalia | Gu, Deyr | GEOGLAM | 0.162 | 40 and 39, 1995 to 2025 |
| Rwanda | Season A, Season B | maize | 0.156 | 23 and 30 |
| Eritrea | Kremti | GEOGLAM | 0.133 | **none** |
| Burundi | Season A, Season B | maize | 0.023 | 9 and 13 |

Djibouti is excluded: SPAM 2020 places 47 ha of sorghum in the country and no crop-type mask was
produced.

# 5. Gaps, and what would close them

1. **Nine of the eighteen products are not yet run** — the Medium and Low viability seasons: Kenya
   short rains, Uganda second rains, Rwanda and Burundi Seasons A and B, Tanzania Masika, Ethiopia
   Belg and South Sudan's second season.
2. **CPI has no rank skill outside Kenya.** Ethiopia is flat and Uganda is negative. Until that is
   understood, those products support level statements only. The Ethiopian cause is identified —
   WRSI saturation — and points at the water balance rather than the calendar or the mask.
3. **Two parameters carried over from maize.** The emergence offset of two dekads and the heat
   loss rate of 0.06 per heat-degree-dekad have no sorghum-specific source. Both are flagged
   `FIRST PASS` in the code.
4. **Tanzania and Eritrea cannot be calibrated** from HarvestStat, which holds no sorghum yields
   for either. A national yield figure from the statistics office or FAOSTAT would give a
   level-only ceiling.
5. **No independent field validation.** The maize planting estimate is tested against farmer
   records for Kenya 2024, giving a mean absolute error of 1.02 dekads. Nothing equivalent
   exists for sorghum anywhere in the region. Collecting sorghum planting dates is the highest
   value field activity available.
6. **The cropland base still binds.** Sudan's map holds 6.32 of 7.48 Mha of reported sorghum,
   and the shortfall is concentrated in the Darfur and Kordofan sand sheets that the global
   cropland products miss. A sorghum product cannot be better than the mask it runs on.

# References

Allen, R. G., Pereira, L. S., Raes, D., & Smith, M. (1998). *Crop Evapotranspiration: Guidelines
for Computing Crop Water Requirements*. FAO Irrigation and Drainage Paper 56. FAO, Rome.

Doorenbos, J., & Kassam, A. H. (1979). *Yield Response to Water*. FAO Irrigation and Drainage
Paper 33. FAO, Rome.

Funk, C., Peterson, P., Landsfeld, M., et al. (2015). The climate hazards infrared precipitation
with stations. *Scientific Data*, 2, 150066.

GEOGLAM Crop Monitor (2024). *Crop Monitor for Early Warning crop calendars, version 1.3*.

Lee, D., Anderson, W., Chen, X., et al. (2025). HarvestStat Africa: harmonized subnational crop
statistics for Sub-Saharan Africa. *Scientific Data*.

Prasad, P. V. V., Pisipati, S. R., Mutava, R. N., & Tuinstra, M. R. (2008). Sensitivity of grain
sorghum to high temperature stress during reproductive development. *Crop Science*, 48(5),
1911–1917.

Prasad, P. V. V., Djanaguiraman, M., Perumal, R., & Ciampitti, I. A. (2015). Impact of high
temperature stress on floret fertility and individual grain weight of grain sorghum.
*Frontiers in Plant Science*, 6, 820.

Singh, V., Nguyen, C. T., van Oosterom, E. J., Chapman, S. C., Jordan, D. R., & Hammer, G. L.
(2015). Sorghum genotypes differ in high temperature responses for seed set. *Field Crops
Research*, 171, 32–40.
