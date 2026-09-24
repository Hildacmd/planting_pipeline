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

**Nine of the eighteen products have no CM4EW sorghum entry** — Kenya short rains, Uganda second
rains, Rwanda and Burundi Seasons A and B, Tanzania Msimu and Masika, and Ethiopia Belg. These
take the country's **maize** window, because sorghum shares those rains. Each row records which
source it came from in `crop_calendar_source`. **They are provisional and are the first thing to
validate with national partners.**

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

$Y_m$ is fitted to HarvestStat sorghum yields by least squares through the origin, with the
median over the available years as the target and a 70/30 split repeated 200 times for the
held-out error. The fit is not yet run: it needs the 2024 CPI to exist first.

**Until then every product carries an uncalibrated 3.0 t/ha, or 2.0 for short seasons, and the
yield band is not reportable.** On every maize country where the equivalent default could be
tested it was two to seven times what smallholders harvest. CPI carries the season signal and
is usable immediately; $Y_m$ only sets the level.

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

1. **No yield calibration yet.** The fit needs the 2024 CPI. Once it exists,
   `calibrate_ym_sorghum.py` runs in minutes. Somalia is the strongest case in the region with
   839 Gu and 757 Deyr yield records, better than its maize record.
2. **Nine provisional calendars.** Kenya short rains, Uganda second rains, Rwanda, Burundi,
   Tanzania and Ethiopia Belg use the maize window. National partners can correct these from
   their own extension calendars, and the stakeholder workshop is the place to do it.
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
