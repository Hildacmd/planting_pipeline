---
title: "Crop Condition Monitoring and Forecasting for the ICPAC Region"
subtitle: "From planting dekad to risk maps to yield estimates — as-built methodology, 40 products across 10 countries and 5 crops"
date: "26 September 2026"
---

# 1. Scope and what this report is

This is an **as-built** description of the operational pipeline: what it computes, from which data,
with which parameters, and how well each output has been shown to work. It covers the whole chain —
**planting dekad → risk maps → yield estimates** — for **40 products**:
18 sorghum, 15 maize, 4 wheat, 2 millet, 1 teff, across **10 countries**
(Burundi, Eritrea, Ethiopia, Kenya, Rwanda, Somalia, South Sudan, Sudan, Tanzania, Uganda).

Where the as-built method departs from the Inception Report, §8 states the departure, the reason,
and the peer-reviewed basis for it.

**Every table here is computed from the shipped products at build time, and every figure is
regenerated from those same products by `report/make_figures.py`.** No figure is carried over from
an earlier run. Rebuild with:

```bash
python report/make_figures.py && python report/build_report.py
```

## 1.1 Headline state of the pipeline

| | |
|---|---|
| products built | **40** (18 sorghum, 15 maize, 4 wheat, 2 millet, 1 teff) |
| countries | 10 |
| yield ceilings fitted against official statistics | **22** of 40 |
| …of which rank admin units **usably** (r ≥ 0.4) | **5** |
| …of which rank admin units **backwards** (r < 0) | **8** |
| products where a rainfed balance misreads irrigation | **9** (1 invalid, 6 materially biased, 2 locally biased) |
| tier-2 metrics (SPI-3, deficit, LVPD, FCCI) | complete for sorghum, wheat, teff, millet |

**The honest summary is that planting dekad is the strongest link in the chain, risk is sound where
the crop is rainfed, and yield is the weakest — 8 of 22 fitted ceilings order admin units
backwards.** §7 and §9 give the evidence and what to do about it.

# 2. Countries, crops and coverage

The **ICPAC crop-type mask decides which crops run in which country**. A season-calendar row for a
country whose mask carries no band for that crop cannot be computed, and is dropped at planning time
rather than failing mid-build (`crop_coverage.py`).


![Figure 1. What the crop-type mask permits and what was built. 'mask only' = buildable, no calendar row yet; 'dropped' = a decision, recorded with its evidence.](figs/chart_coverage.png)


**Deliberate exclusions**, recorded in `crop_coverage.ACCEPTED` / `.DROPPED` so a decision is never
mistaken for an oversight:

- **Sudan maize, Eritrea maize** — no mask band. Maize is not a crop of consequence in either and is
  intentionally neither mapped nor run. The calendar rows are legacy placeholders.
- **South Sudan maize — dropped.** Dropped 26 Sep 2026 by decision. The crop-type mask maps 0.013 Mha of maize in South Sudan against 0.295 Mha of sorghum. On that mask the product retains 135 maize pixels country-wide against WorldCereal's 9,398, and Eastern Equatoria - 90 % of the country's maize by WorldCereal - has none at all. O…
- **Rwanda wheat (0.019 Mha), Burundi wheat (0.003 Mha)** — buildable, deferred on area.

# 3. Data inputs

| input | product | role | reference |
|---|---|---|---|
| Rainfall | CHIRPS v2.0, daily/dekadal, 0.05° | onset rule, water balance supply term, SPI-3 | Funk et al. 2015 |
| Temperature | ERA5-Land hourly → dekadal Tmin/Tmax | Hargreaves ET₀, flowering heat | Muñoz-Sabater et al. 2021 |
| Reference ET | Hargreaves–Samani from ERA5-Land | crop water requirement `Kc·ET₀` | Hargreaves & Samani 1985 |
| Soil water | SoilGrids 2.0 texture → Saxton–Rawls θ₃₃/θ₁₅₀₀ | WHC over the crop's rooting depth | Poggio et al. 2021; Saxton & Rawls 2006 |
| Optical | Sentinel-2 L2A, NDRE | green-up onset cue | Eisfelder et al. 2024 |
| Radar | Sentinel-1 GRD, VH/VV → RVI | cloud-proof onset cue | (SAR SOS literature, §11) |
| Canopy | MODIS MCD15A3H FPAR | onset cue, zFPAR anomaly | Myneni et al. |
| Biomass | MODIS MOD17A2HGF GPP → DMP | independent yield-ranking covariate | Running et al. 2004; Monteith 1972 |
| Crop area | ICPAC crop-type mask, 100 m (MapSPAM prior) | the stratum every product is computed over | IFPRI MapSPAM; §4 |
| Irrigation | MapSPAM 2020 `_I`/`_A` physical area | exposure grading (§7.3) | IFPRI MapSPAM |
| Boundaries | GADM 4.1 (GAUL where absent) | zonal reduction | GADM |
| Yield statistics | HarvestStat Africa v1.2 | Ym calibration and validation | Lee et al. 2025 |

# 4. The crop-type mask — the stratum everything is computed over

Every product is computed **inside a crop-specific mask**, not over all cropland. The ICPAC
crop-type mask is a dasymetric allocation of MapSPAM crop shares onto a four-lineage,
sixteen-source-year stable cropland vote, reweighted by agro-climatic suitability and satellite crop
evidence, and calibrated to sub-national statistics where they exist. It reproduces reported crop
area to **92–99 %** across the eight maize countries.

This **is** the Inception Report's Tier 1, built stronger than the report assumed (§8.1).

`ctm_mask.crop_mask()` **raises rather than falling back**. That matters: the generic
`run.crop_mask_image` would return the WorldCereal *temporary-crops* extent — all cropland — for any
non-maize crop. No shipped product ever ran that way, because sorghum, wheat, teff and millet used
the crop-type mask from the start; the raise is what keeps it that way.

# 5. Module 1 — Planting dekad (onset)

## 5.1 Three onset routes, chosen per product

1. **Green-up cue fusion** — Sentinel-2 NDRE + MODIS FPAR + Sentinel-1 RVI, for main seasons where
   cloud allows. Fusing an optical cue with SAR is what makes onset retrievable under cloud
   (Eisfelder et al. 2024; SAR-SOS literature).
2. **Rainfall-anchored onset** — the FEWS/GeoWRSI rule: 25 mm in a dekad followed by 20 mm in each of
   the next two, with a **5+7 dekad false-start gate** (Senay & Verdin 2003; Sivakumar 1988;
   Stern et al. 1982). Used for short and second seasons, and for cloudy equatorial highlands.
3. **Fixed scheme date** — for irrigated products, where planting is scheduled rather than
   rain-driven and neither detector can fire (§7.3).


![Figure 2. Detected planting window per product — median p10 to p90 across admin units, dot = p50. The spread is the product's own detected variability, not the calendar window.](figs/chart_planting_windows.png)



![Figure 3. Maize — modal planting dekad, 2024. One hue, dark to bright: dekad is an ordered quantity and a qualitative palette would invite the reader to see categories where there is a sequence.](figs/map_planting_maize.png)



![Figure 4. Sorghum — modal planting dekad, 2024, 18 products across 10 countries.](figs/map_planting_sorghum.png)



![Figure 5. Wheat — modal planting dekad, 2024.](figs/map_planting_wheat.png)



![Figure 6. Millet — modal planting dekad, 2024.](figs/map_planting_millet.png)



![Figure 7. Teff — modal planting dekad, Ethiopia Meher 2024.](figs/map_planting_teff.png)


## 5.2 Validation — the strongest link in the chain

Against **4.8 million Kenyan farmer planting records** (MAM 2024): **92.9 % of admin units within
±2 dekads**, and **100 % within the GIEWS calendar window**. Ethiopia Meher: **100 % in window**.

This is the only part of the chain with independent ground truth at scale, and it is the part that
performs best. Outside Kenya and Ethiopia there is no comparable reference, so planting dekad
elsewhere is validated only against calendar plausibility.

# 6. Module 2 — Risk monitoring

## 6.1 The water balance

A single-layer FAO-56 dekadal bucket (Allen et al. 1998), stepped over each pixel's own cycle:


$$WR_t = K_{c}(d)\cdot ET_{0,t}$$

$$W_{b,t} = SW_{t-1} + P_t$$

$$AET_t = \min\!\left(W_{b,t},\; WR_t\right)$$

$$SW_t = \min\!\left(\max\!\left(W_{b,t}-AET_t,\;0\right),\; WHC\right)$$

$$WRSI = 100\cdot\frac{\sum_{t} AET_t}{\sum_{t} WR_t}$$

where $t$ indexes dekads over the crop cycle, $d$ is dekads since planting, $K_c(d)$ is the FAO-56
crop coefficient at that stage, $ET_{0,t}$ is Hargreaves reference evapotranspiration, $P_t$ is
CHIRPS rainfall, and $WHC$ is water-holding capacity over the crop's own rooting depth. The supply
term $W_{b,t}=SW_{t-1}+P_t$ carries **no irrigation term** - see section 7.3.


with a dry start (`init_soil_water_frac = 0.0`), the WRSI convention (Verdin & Klaver 2002;
Senay & Verdin 2003).

## 6.2 Stress components


$$S_{water} = \operatorname{clamp}\!\left(\sum_{s\,\in\,\{veg,\,flo,\,grf\}} K_{y,s}\left(1-\frac{AET_s}{WR_s}\right),\;0,\;1\right)$$

$$S_{heat} = \operatorname{clamp}\!\left(k_{H}\sum_{t\,\in\,flo}\max\!\left(0,\;T_{max,t}-T_{cap}\right),\;0,\;1\right)$$

$$S_{veg} = w_{v}\left(1-\mathrm{VCI}\right), \qquad w_{v}=0.4$$

$K_{y,s}$ is the FAO-33 stage yield-response factor, $k_H$ the heat coefficient per
heat-degree-dekad, $T_{cap}$ the crop's flowering heat threshold, and $w_v$ the vegetation
down-weight - $S_{veg}$ confirms the balance rather than driving it.


Ky is the FAO-33 stage yield-response factor (Doorenbos & Kassam 1979) and is **the most
consequential parameter set in the pipeline** — maize's flowering Ky of 1.50 against sorghum's 0.55
means a flowering deficit costs maize roughly three times what it costs sorghum.


![Figure 8. What actually drives CPI in each product. Water stress dominates almost everywhere — which is exactly why unmodelled irrigation (§7.3) is the pipeline's largest systematic error.](figs/chart_stress_decomposition.png)



![Figure 9. Sorghum — WRSI at flowering, the critical stage.](figs/map_wrsiflo_sorghum.png)



![Figure 10. Maize — crop-failure risk, ASAP convention: % of crop area with stage WRSI < 50 (Rembold et al. 2019).](figs/map_risk_maize.png)



![Figure 11. Sorghum — crop-failure risk, 2024.](figs/map_risk_sorghum.png)



![Figure 12. Sorghum — cumulative season water deficit (mm). On an irrigated product this quantity is the irrigation requirement, not crop stress (§7.3).](figs/map_deficit_sorghum.png)



![Figure 13. Sorghum — SPI-3 at end of season, the meteorological drought context for the balance.](figs/map_spi_sorghum.png)



![Figure 14. Sorghum — fused canopy condition (FCCI) from Sentinel-2, Sentinel-1 and FPAR: an observation-side check on a model-side product.](figs/map_fcci_sorghum.png)



![Figure 15. Sorghum — share of crop area planted before the climatological last viable planting date (LVPD).](figs/map_viable_sorghum.png)


# 7. Module 3 — Crop Performance Index and yield

## 7.1 The model


$$CPI = 100\left(1-S_{water}\right)\left(1-S_{heat}\right)\left(1-S_{veg}\right)$$

$$Y_a = \frac{CPI}{100}\cdot Y_m$$

The combination is **multiplicative**, following FAO-33: a crop already lost to water deficit cannot
be further reduced proportionally by heat. $Y_m$ is the attainable ceiling, fitted by least squares
through the origin over HarvestStat units $i$ with reported yield $y_i$, weighted by crop area $w_i$:

$$\hat{Y}_m = \frac{\sum_i w_i\, y_i\, c_i}{\sum_i w_i\, c_i^{2}}, \qquad c_i = \frac{CPI_i}{100}$$


Ym is fitted by least squares through the origin of reported yield on CPI, with admin units weighted
by crop area, against HarvestStat Africa v1.2 (Lee et al. 2025), 70/30 split repeated 200 times. The
ceiling is the *attainable* yield in the yield-gap sense (van Ittersum et al. 2013; Lobell et al. 2009).


![Figure 16. Sorghum — Crop Performance Index, 2024.](figs/map_cpi_sorghum.png)



![Figure 17. Sorghum — estimated yield (t/ha), 2024.](figs/map_yield_sorghum.png)



![Figure 18. Maize — Crop Performance Index, 2024.](figs/map_cpi_maize.png)



![Figure 19. Maize — estimated yield (t/ha), 2024.](figs/map_yield_maize.png)


## 7.2 Yield is the weakest link, and here is the evidence


![Figure 20. Yield-pattern skill of every fitted ceiling. Bars left of zero are products where the model orders admin units BACKWARDS against reported yield.](figs/chart_ym_skill.png)


Of **22 fitted ceilings**: **5 rank usably** (r ≥ 0.4), **8 rank backwards** (r < 0).

A ceiling with r < 0 sets a plausible national average and then puts the wrong districts at the
bottom. In an early-warning product that is worse than no ranking, because it carries the authority
of a number. **These products should be read as levels, not as rankings**, until the cause is fixed.

| crop | country | season | ym | n | r |
|---|---|---|---|---|---|
| sorghum | Sudan | Kharif | 0.83 | 18 | -0.33 |
| sorghum | Uganda | 2nd rains | 1.13 | 50 | -0.23 |
| sorghum | Rwanda | Season B | 1.37 | 30 | -0.17 |
| sorghum | Kenya | Short rains | 1.09 | 24 | -0.15 |
| maize | Uganda | 1st rains | 2.34 | 74 | -0.14 |
| sorghum | Burundi | Season A | 0.55 | 7 | -0.09 |
| maize | Rwanda | Season A | 2.61 | 30 | -0.07 |
| sorghum | Uganda | 1st rains | 1.30 | 47 | -0.02 |
| wheat | Kenya | Long rains | 3.11 | 16 | 0.07 |
| wheat | Ethiopia | Meher | 2.69 | 52 | 0.15 |

## 7.3 Irrigation — the largest known systematic error

The balance is **rainfed by construction**: `Wb = SW + P` credits soil water and rainfall and
nothing else. Where a crop is irrigated, the scheme meets a shortfall the model never sees, so
WRSI and `S_water` measure the **irrigation requirement** while being reported as crop stress, and
CPI and yield come out low.

Exposure is graded per (country, crop) from MapSPAM 2020's irrigated/rainfed technology split:
**1 invalid as a rainfed product,
6 materially biased, 2 locally biased,
31 unaffected.**


![Figure 21. Admin units where the rainfed balance is reading irrigation demand as crop stress.](figs/chart_irrigation.png)


The clearest measurable case is **Sudan millet Kharif**: across its 15 states CPI ranks *negatively*
against the irrigated share (Spearman ρ = −0.678, p = 0.005) — Al Jazirah (71.9 % irrigated) and
Khartoum (95.4 %) score below fully-rainfed Darfur.

**Exposure is not proof of corruption.** Sudan sorghum has the most irrigated area of any product
(288,569 ha) yet ρ = −0.17 (p = 0.50), because the 3.3 Mha Al Qadarif bulk is rainfed. The grade
flags a product for inspection; the correlation decides.

Every Earth Engine asset carries `irrigation_exposure`; the apps show a banner; Sudan wheat Shitwi
is excluded from apps and Atlas, its asset retained because the deficit *is* the irrigation
requirement. Full treatment: `crop_pipeline/docs/IRRIGATED_WATER_BALANCE.md`.

## 7.4 DMP as a rescue for the products where the balance fails

Dry-matter productivity (MOD17 GPP → DMP; Monteith 1972; Running et al. 2004) was tested as an
independent **ranking covariate** — not as a replacement for CPI, and not as a level product, since
DMP cannot see ASAL crop failure (implied harvest index 0.02, far outside the 0.30–0.55 agronomic
range of Hay 1995).

The test is **rank-only**, which removes DMP's dominant uncertainty: Spearman ρ is invariant to
monotonic transforms, so harvest index, above-ground fraction and grain moisture cannot affect it.


![Figure 22. DMP vs CPI as a ranking covariate, paired bootstrap 95 % CI (Efron & Tibshirani 1993). Left panel: products where CPI ranks backwards. Right panel: the control set where CPI already works.](figs/chart_dmp_rank.png)


| set | DMP better | CPI better | indistinguishable | median Δρ |
|---|---|---|---|---|
| CPI ranks **backwards** (n=8) | **3** | 0 | 5 | **+0.337** |
| CPI **already works** (n=5) | 0 | 0 | 5 | +0.001 |

DMP's ρ is positive in 6 of 8 anti-correlated products; CPI's is positive in **0 of 8**. On the
control set the two are a dead heat. The supported claim is therefore the narrow one:
**DMP adds nothing where the water balance already works, and recovers a usable ranking where it
does not.**

# 8. Departures from the Inception Report, and why

Each departure states what the report proposed, what was built, and the peer-reviewed basis.

## 8.1 Crop typing: Tier 1 was built stronger than proposed, Tier 3 was not attempted

*Report:* a three-tier strategy — Tier 1 a MapSPAM area-fraction prior over a cropland mask; Tier 2
label acquisition; Tier 3 a retrained S1/S2 phenometric classifier, adopted only if it beat Tier 1
on zone-level anomaly skill against FEWS NET IPC.

*Built:* Tier 1, but as a four-lineage sixteen-source-year cropland vote with suitability
reweighting, satellite crop evidence and calibration to sub-national statistics — reproducing
reported area to 92–99 %. **Tier 2 produced no usable labels, so Tier 3 is correctly not attempted**:
the report's own gate makes Tier 3 conditional on Tier 2.

*Basis:* Van Tricht et al. 2023 (WorldCereal) confirms no global millet or teff class exists, which
is why a SPAM-prior mask is the only route to those crops; Eisfelder et al. 2024 is the S1+S2
classifier the report's Tier 3 would have been, and needs labels the region does not have.

## 8.2 WRSI computed inside Earth Engine, not GeoWRSI

*Report:* the FEWS GeoWRSI convention. *Built:* the same algorithm (Verdin & Klaver 2002;
Senay & Verdin 2003) reimplemented as a dekadal bucket in Earth Engine.

*Justification:* GeoWRSI is a desktop tool over pre-gridded inputs; running the identical recursion
in Earth Engine lets the balance use **per-pixel planting dates** and **per-pixel rooting-depth WHC**
from SoilGrids (Poggio et al. 2021; Saxton & Rawls 2006) at 250 m, which the desktop route cannot.
The algorithm is unchanged; only where it runs, and at what resolution, has changed.

## 8.3 Cue-fusion green-up onset alongside the rainfall rule

*Report:* rainfall-threshold onset. *Built:* both, chosen per product.

*Justification:* the rainfall rule cannot fire where a season is not rain-triggered — Sudan's
November-sown irrigated wheat produced **zero valid pixels** on the 25/20 mm rule. Conversely,
green-up fusion fails under persistent equatorial-highland cloud: Rwanda and Burundi Season A
returned ~64 planting pixels against 3,365 crop pixels until they were routed to the rainfall rule.
Neither detector is sufficient alone, and the failure modes are complementary — the optical/SAR
fusion literature (Eisfelder et al. 2024) is explicit that SAR is the cloud-proof cue.

## 8.4 Multiplicative CPI rather than an additive index

*Justification:* FAO-33 (Doorenbos & Kassam 1979) combines stage water-deficit effects
multiplicatively, and the same logic applies across stress types: a crop that has already failed for
water cannot be further damaged proportionally by heat. An additive index would let a good heat score
compensate a fatal water deficit.

## 8.5 `S_veg` is a down-weighted confirmation, not a driver

*Justification:* tested and rejected as a driver. DMP as `S_veg` gave no rank gain in any season
(Ethiopia admin-2, n = 39, ρ ≈ 0 for both arms). Vegetation indices are diagnostic mid-season
(Funk & Budde 2009; Rembold et al. 2013) and confirm what the balance already implies rather than
adding independent information.

## 8.6 Ethiopia Meher maize keeps the operative calendar window

*Justification:* decided by A/B test, not assertion. The operative window beats GEOGLAM CM4EW by
Δρ **+0.355 [+0.163, +0.564]** and the Inception Report window by **+0.463 [+0.229, +0.710]**
(paired bootstrap, Efron & Tibshirani 1993) — the first A/B in the project whose intervals exclude
zero. Coverage declines monotonically with the alternatives.

## 8.7 Sorghum calendars follow Inception Report Table 2.0

Not a departure but a deliberate alignment, recorded because GEOGLAM CM4EW ships a
sorghum-*specific* calendar that disagrees with the report for 6 of the 9 products it covers, by up
to 3 dekads. The CM4EW values are retained in parallel `cm4ew_*` columns for partner validation.

## 8.8 Irrigation is flagged, not corrected

*Departure:* the report assumes a rainfed balance throughout. *Built:* the same rainfed balance, plus
an explicit per-product exposure grade (§7.3), because pretending the issue does not exist would
misreport the Gezira as a crop failure.

## 8.9 Crop-type mask replaces WorldCereal as the stratum — for every crop except maize

*Status:* sorghum, wheat, teff and millet run on the crop-type mask. Maize still ships on WorldCereal.
All 16 maize products were re-run on the crop-type mask and compared.


![Figure 23. WorldCereal vs ICPAC crop-type mask for maize — same balance, same parameters, same Ym. Only the stratum differs.](figs/chart_mask_comparison.png)


Over 14 comparable products the level barely moves (mean CPI **+1.22**)
and the ranking mostly holds (median ρ **0.905**), but **2 products re-rank**
(Uganda 1st rains ρ 0.758, Burundi Season A ρ 0.734). Re-fitting Ym on the new footprint moves the
ceilings by a median **−6.7 %** yet does **not** improve skill: held-out MAE improves in only 2 of 7
and r falls in 5 of 7.

**Conclusion: do not switch wholesale.** The mask is better at what it was built for — area — but
that has not translated into better condition or yield. Switch per product, on evidence.

# 9. Known limitations

1. **Yield ranks backwards in 8 of 22 fitted products** (§7.2). Read those as levels.
2. **18 of 40 products have no fitted ceiling at all** — no sub-national statistics exist to fit against.
3. **Irrigation is unmodelled** (§7.3); 9 products carry exposure.
4. **Teff and millet parameters are first-pass analogues** — FAO-33 tabulates neither crop, so their flowering Ky is borrowed. A wrong Ky biases CPI in a way calibration cannot detect, because Ym absorbs the level and leaves the pattern wrong.
5. **MapSPAM 2020 is a 2020 snapshot.** Ethiopia's irrigated-wheat expansion post-dates it (exposure understated); Sudan's schemes have been disrupted since 2023 (possibly overstated).
6. **Total production is an upper bound** where a mask cannot distinguish season.
7. **Kenya short-rains season attribution** — ~39 % of mapped western short-rains area may be the standing long-rains crop. Both CPI and DMP fail there, which points at the mask and the season rather than at either predictor.
8. **DMP is a stand-in.** MOD17 GPP substitutes for Copernicus 300 m DMP, which is not in the Earth Engine catalogue.

# 10. Recommendations, in order of value

1. **Split the crop masks by technology** using MapSPAM `_I`/`_R`, and run irrigated and rainfed products separately. This is the single highest-value fix: it makes 9 exposed products interpretable and unblocks an honest Ym re-fit.
2. **Add DMP as a ranking covariate** on the 8 anti-correlated products (§7.4) — evidence supports it there and nowhere else.
3. **Re-fit Ym on rainfed area only** once the split exists. Sudan sorghum's r = −0.33 is the test: it should turn positive.
4. **Resolve Kenya short-rains season attribution** before that product is used for targeting.
5. **Obtain a teff Ky** from Ethiopian trial data; sensitivity-test Ky_flo over 0.4–0.8 meanwhile.
6. **Refresh the irrigation layer** against a post-2020 source.
7. **Switch maize to the crop-type mask per product, not wholesale**, re-fitting Ym each time.

# 11. References

All references below are reproduced from the project's maintained bibliography,
`REFERENCES.md`, which carries the full annotated list.

**Reader's caveat, carried over from that file:** several DOIs are foundational standards cited from
established literature, and the 2023–2026 fusion papers were surfaced through web search during
development. **Verify every DOI against your own library before formal publication or submission.**
The MapSPAM release identifier in particular should be cited from the exact Dataverse record used.


## Start-of-season / planting-date from SAR–optical fusion
- Van Tricht, K. et al. (2023). *WorldCereal: a dynamic open-source system for global-scale,
  seasonal, reproducible crop and irrigation mapping.* Earth System Science Data 15, 5491–5515.
  https://doi.org/10.5194/essd-15-5491-2023  — the 10 m global cropland/maize/cereal system;
  confirms no millet/teff class (motivates crop-specific masking).
- Eisfelder, C. et al. (2024). *Cropland and Crop Type Classification with Sentinel-1 and
  Sentinel-2 Time Series Using GEE for Agricultural Monitoring in Ethiopia.* Remote Sensing
  16(5):866. https://doi.org/10.3390/rs16050866  — S1+S2 time-series, red-edge indices, 10 m,
  three Ethiopian regions (methodological basis for feature stack).
- (2025) *A novel fusion of Sentinel-1 and Sentinel-2 with climate data for crop phenology
  estimation using machine learning.* ScienceDirect.
  https://www.sciencedirect.com/science/article/pii/S2666017225000331
- (2025) *Time-series analysis of Sentinel-1 SAR to retrieve annual rice area and long-term
  dynamics of start of season.* Scientific Reports. https://doi.org/10.1038/s41598-025-91655-z
  — SAR-only SOS retrieval; supports SAR as the cloud-proof onset cue.
- (2025) *Parcel-scale crop planting structure extraction combining time-series Sentinel-1 and
  Sentinel-2 via a semantic edge-aware multi-task network.* Int. J. Digital Earth.
  https://doi.org/10.1080/17538947.2025.2497487
- (2026) *Evaluating the impact of PlanetScope and Sentinel-2 data fusion on maize phenometrics
  retrieval.* GIScience & Remote Sensing. https://doi.org/10.1080/15481603.2026.2637207
  — supports higher-res fusion for smallholder maize phenometrics.
- Vrieling, A. et al. (2019). *Exploiting time series of Sentinel-1 and Sentinel-2 to detect
  meadow phenology.* Remote Sensing 11(5):542. https://doi.org/10.3390/rs11050542

## WRSI / crop water balance & rainfall onset
- Verdin, J. & Klaver, R. (2002). *Grid-cell-based crop water accounting for the famine early
  warning system.* Hydrological Processes 16, 1617–1630. https://doi.org/10.1002/hyp.1025
- Senay, G.B. & Verdin, J. (2003). *Characterization of yield reduction in Ethiopia using a
  GIS-based crop water balance model.* Canadian J. Remote Sensing 29(6), 687–692.
  https://doi.org/10.5589/m03-039  — WRSI onset rule (25/20 mm) and cycle water balance.
- Funk, C. et al. (2015). *The climate hazards infrared precipitation with stations (CHIRPS).*
  Scientific Data 2:150066. https://doi.org/10.1038/sdata.2015.66
- Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998). *Crop evapotranspiration — Guidelines
  for computing crop water requirements.* FAO Irrigation & Drainage Paper 56 (FAO-56); crop
  coefficients & stage lengths (Kc curve). https://www.fao.org/3/x0490e/x0490e00.htm
- Hargreaves, G.H. & Samani, Z.A. (1985). *Reference crop evapotranspiration from temperature.*
  Applied Engineering in Agriculture 1(2), 96–99. https://doi.org/10.13031/2013.26773  — the
  temperature-only ET0 used here (ERA5-Land inputs).
- Muñoz-Sabater, J. et al. (2021). *ERA5-Land.* Earth System Science Data 13, 4349–4383.
  https://doi.org/10.5194/essd-13-4349-2021  — Tmin/Tmax source for ET0.
- Saxton, K.E. & Rawls, W.J. (2006). *Soil water characteristic estimates by texture and organic
  matter for hydrologic solutions.* Soil Sci. Soc. Am. J. 70(5), 1569–1578.
  https://doi.org/10.2136/sssaj2005.0117  — field capacity (θ₃₃) & wilting point (θ₁₅₀₀) pedotransfer for WHC.
- Poggio, L. et al. (2021). *SoilGrids 2.0: producing soil information for the globe with quantified
  spatial uncertainty.* SOIL 7, 217–240. https://doi.org/10.5194/soil-7-217-2021  — sand/clay/SOC
  texture inputs to the WHC pedotransfer. (Legacy: OpenLandMap 33 kPa, https://doi.org/10.5281/zenodo.2784001.)
- Rembold, F. et al. (2019). *ASAP: a new global early warning system to detect anomaly hot spots of
  agricultural production.* Agricultural Systems 168, 247–257. https://doi.org/10.1016/j.agsy.2018.07.002
  — ASAP % -of-crop-area rule and the FPAR anomaly (zFPAR) option.
- Sivakumar, M.V.K. (1988). *Predicting rainy season potential from the onset of rains… West Africa.*
  Agric. & Forest Meteorology 42(4), 295–305. https://doi.org/10.1016/0168-1923(88)90039-1  — the
  accumulation + no-dry-spell onset criterion ("5+7" false-start gate).
- Stern, R.D., Dennett, M.D. & Dale, I.C. (1982). *Analysing daily rainfall measurements to give
  agronomically useful results.* Experimental Agriculture 18(3), 223–236.
  https://doi.org/10.1017/S001447970001379X  — onset & dry-spell risk from daily rainfall.

## Excess rain / waterlogging (wet-side risk)
- Zaidi, P.H. et al. (2004). *Tolerance to excess moisture in maize: susceptible crop stages…* Field
  Crops Research 90(2–3), 189–202. https://doi.org/10.1016/j.fcr.2004.03.002  — early-vegetative the
  most waterlogging-susceptible stage (basis for the excess stage-weighting order).
- Ren, B. et al. (2014). *Effects of waterlogging on the yield and growth of summer maize under field
  conditions.* Canadian J. Plant Science 94(1), 23–31. https://doi.org/10.4141/cjps2013-175
- Kaur, G. et al. (2020). *Impacts and management strategies for crop production in waterlogged or
  flooded soils: a review.* Agronomy Journal 112(3), 1475–1501. https://doi.org/10.1002/agj2.20093

## FPAR / phenology inputs
- Myneni, R. et al. MODIS MCD15A3H FPAR/LAI (C6.1). NASA LP DAAC.
  https://doi.org/10.5067/MODIS/MCD15A3H.061
- Copernicus Global Land Service — FPAR 300 m. https://land.copernicus.eu/global

## Regional monitoring, calendars, statistics (calibration/validation)
- Becker-Reshef, I. et al. (2020). *The GEOGLAM Crop Monitor for Early Warning.* Remote Sensing
  of Environment 237:111553. https://doi.org/10.1016/j.rse.2019.111553  |  https://cropmonitor.org
- (2021) *A review of satellite-based global agricultural monitoring systems available for
  Africa.* Global Food Security. https://www.sciencedirect.com/science/article/pii/S2211912421000523
- Lee, D. et al. (2025). *HarvestStat Africa — Harmonized Subnational Crop Statistics for
  Sub-Saharan Africa.* Scientific Data. https://doi.org/10.1038/s41597-025-05001-z
- FEWS NET crop calendars & data portal. https://fews.net/data
- FAO GIEWS Country Briefs / crop calendars. https://www.fao.org/giews/

## Reference / ground-truth labels
- Ethiopian Crop Type 2020 (EthCT2020). Data in Brief (2024).
  https://www.sciencedirect.com/science/article/pii/S2352340924003962
  Dataset: Mendeley Data https://doi.org/10.17632/mfpvmk8cnm.1

## Data-access API documentation
- Google Earth Engine — https://developers.google.com/earth-engine
- Copernicus Data Space Ecosystem APIs (openEO, Sentinel Hub, STAC/OData) —
  https://dataspace.copernicus.eu/analyse/apis
- NASA AppEEARS API — https://appeears.earthdatacloud.nasa.gov/api
- ASF HyP3 (Sentinel-1 RTC on demand) — https://hyp3-docs.asf.alaska.edu
- USGS FEWS NET / GeoWRSI software — https://earlywarning.usgs.gov/fews/software-tools

*Note: a few DOIs above are foundational standards (Verdin & Klaver, Senay & Verdin, Funk,
Myneni) cited from established literature; the 2023–2026 fusion papers were surfaced in this
session's web searches. Verify DOIs against your library before formal publication.*

## Productivity / biomass-based yield (DMP, added 2026-09)
- Monteith, J.L. (1972). *Solar radiation and productivity in tropical ecosystems.* Journal of
  Applied Ecology 9(3), 747–766. https://doi.org/10.2307/2401901  — light-use-efficiency basis of DMP.
- Running, S.W. et al. (2004). *A continuous satellite-derived measure of global terrestrial primary
  production.* BioScience 54(6), 547–560. — MOD17 GPP/NPP algorithm (the MODIS stand-in for CGLS DMP).
- Zhao, M. et al. (2005). *Improvements of the MODIS terrestrial gross and net primary production
  global data set.* Remote Sensing of Environment 95(2), 164–176.
  https://doi.org/10.1016/j.rse.2004.12.011
- Hay, R.K.M. (1995). *Harvest index: a review of its use in plant breeding and crop physiology.*
  Annals of Applied Biology 126(1), 197–216. https://doi.org/10.1111/j.1744-7348.1995.tb05015.x
  — the 0.30–0.55 agronomic range against which the implied HI is read as a mask diagnostic.

## Thermal time / phenology (added 2026-09)
- McMaster, G.S. & Wilhelm, W.W. (1997). *Growing degree-days: one equation, two interpretations.*
  Agricultural and Forest Meteorology 87(4), 291–300. https://doi.org/10.1016/S0168-1923(97)00027-0

## Yield ceiling / yield gap (added 2026-09)
- van Ittersum, M.K. et al. (2013). *Yield gap analysis with local to global relevance — a review.*
  Field Crops Research 143, 4–17. https://doi.org/10.1016/j.fcr.2012.09.009
- Lobell, D.B., Cassman, K.G. & Field, C.B. (2009). *Crop yield gaps: their importance, magnitudes,
  and causes.* Annual Review of Environment and Resources 34, 179–204.
  https://doi.org/10.1146/annurev.environ.041008.093740

## Validation statistics (added 2026-09)
- Stone, M. (1974). *Cross-validatory choice and assessment of statistical predictions.* JRSS B
  36(2), 111–147.  — leave-one-out CV.
- Efron, B. & Tibshirani, R.J. (1993). *An Introduction to the Bootstrap.* Chapman & Hall.
  — paired bootstrap CI on the arm difference.

## Agro-ecological zoning, growing period & maize maturity classes (added 2026-09)

**Agro-ecological zoning & growing period**
- FAO (1978). *Report on the Agro-ecological Zones Project, Vol. 1: Methodology and Results for Africa.* World Soil Resources Report 48, FAO, Rome. — origin of the Length of Growing Period (LGP) concept and the P/PET ≥ 0.5 moisture-adequacy criterion used in `src/agroecology.lgp_dekads`.
- Fischer, G., van Velthuizen, H., Nachtergaele, F. et al. (2021). *Global Agro-Ecological Zones (GAEZ v4) — Model Documentation.* FAO & IIASA. https://doi.org/10.4060/cb4744en — the current operational LGP/AEZ product against which a pipeline LGP should be benchmarked.

**Maize thermal time & phenology modelling**
- Jones, C.A. & Kiniry, J.R. (1986). *CERES-Maize: A Simulation Model of Maize Growth and Development.* Texas A&M University Press. — thermal-time accumulation and stage partitioning for maize.
- Kiniry, J.R. & Bonhomme, R. (1991). *Predicting maize phenology.* In: Hodges, T. (ed.) *Predicting Crop Phenology*, CRC Press, 115–131. — GDD-to-stage targets and cultivar maturity classes.

**Kenyan maize varieties, maturity classes & agro-ecological matching**
- Jaetzold, R., Schmidt, H., Hornetz, B. & Shisanya, C. (2006–2012). *Farm Management Handbook of Kenya, Vol. II: Natural Conditions and Farm Management Information* (2nd edn). Ministry of Agriculture, Kenya / GTZ. — the standard Kenyan agro-ecological zone reference, including recommended maize maturity class and variety by zone; basis for `config/maize_variety_gdd.csv`.
- Hassan, R.M. (ed.) (1998). *Maize Technology Development and Transfer: A GIS Application for Research Planning in Kenya.* CAB International, Wallingford. — GIS characterisation of Kenyan maize production systems and the altitude/maturity convention of the H5/H6 hybrid series.
- De Groote, H., Owuor, G., Doss, C., Ouma, J., Muhammad, L. & Danda, K. (2005). *The maize green revolution in Kenya revisited.* electronic Journal of Agricultural and Development Economics (eJADE) 2(1), 32–49. — adoption of hybrid maturity classes by agro-ecological zone.

**Non-parametric testing**
- Mann, H.B. & Whitney, D.R. (1947). *On a test of whether one of two random variables is stochastically larger than the other.* Annals of Mathematical Statistics 18(1), 50–60. https://doi.org/10.1214/aoms/1177730491 — used in §5.2 to test whether model error is larger where the thermal requirement exceeds the moisture window.


## Yield response to water, crop area maps, boundaries (added 2026-09-26)
- Doorenbos, J. & Kassam, A.H. (1979). *Yield response to water.* FAO Irrigation & Drainage Paper 33,
  FAO, Rome. https://www.fao.org/3/x0490e/x0490e00.htm (companion to FAO-56) — the stage yield-response
  factors Ky (vegetative / flowering / grain-fill) that weight `S_water`, and the multiplicative
  combination of stage stresses. **The single most consequential parameter set in this pipeline.**
- International Food Policy Research Institute (IFPRI). *Global Spatially-Disaggregated Crop Production
  Statistics Data (MapSPAM), version 2020.* Harvard Dataverse. https://mapspam.info — crop area shares
  by technology (irrigated `_I`, rainfed `_R`, all `_A`), the prior for the crop-type mask's dasymetric
  allocation and the basis of the irrigation-exposure grading. *Cite the exact version DOI from the
  Dataverse record used; the release identifier is not reproduced here.*
- GADM. *Database of Global Administrative Areas, version 4.1.* https://gadm.org — admin-1/2/3
  boundaries for the zonal reductions.
- FAO. *GAUL: Global Administrative Unit Layers.* https://data.apps.fao.org/catalog/ — legacy admin
  boundaries, retained only where GADM lacks a layer.

## Prognostic vs diagnostic phenology — why forecasting needs the thermal clock (added 2026-09)
- Ritchie, J.T. & NeSmith, D.S. (1991). *Temperature and crop development.* Agronomy Monograph 31,
  ASA-CSSA-SSSA, 5-29.
- Holzworth, D.P. et al. (2014). *APSIM - evolution towards a new generation of agricultural systems
  simulation.* Environmental Modelling & Software 62, 327-350.
  https://doi.org/10.1016/j.envsoft.2014.07.009
- Basso, B. & Liu, L. (2019). *Seasonal crop yield forecast: Methods, applications, and accuracies.*
  Advances in Agronomy 154, 201-255. https://doi.org/10.1016/bs.agron.2018.11.002
- Funk, C. & Budde, M.E. (2009). *Phenologically-tuned MODIS NDVI-based production anomaly estimates
  for Zimbabwe.* Remote Sensing of Environment 113(1), 115-125.
  https://doi.org/10.1016/j.rse.2008.08.015  - index-based estimation is mid-season onward.
- Becker-Reshef, I. et al. (2010). *A generalized regression-based model for forecasting winter wheat
  yields...* Remote Sensing of Environment 114(6), 1312-1323.
  https://doi.org/10.1016/j.rse.2010.01.010
- Rembold, F. et al. (2013). *Using low resolution satellite imagery for yield prediction and yield
  anomaly detection.* Remote Sensing 5(4), 1704-1733. https://doi.org/10.3390/rs5041704
- Jones, P.G. & Thornton, P.K. (2003). *The potential impacts of climate change on maize production
  in Africa and Latin America in 2055.* Global Environmental Change 13(1), 51-59.
  https://doi.org/10.1016/S0959-3780(02)00090-0  - LGP as agro-climatic screening axis.


---

*Generated 2026-09-26 by `report/build_report.py` from 40 shipped
products. Companion files: `report/product_master_table.csv` (every product, every headline metric),
`crop_products/<crop>/METHODOLOGY.md` (per-crop dossiers),
`crop_pipeline/docs/IRRIGATED_WATER_BALANCE.md`, `CPI_METHODOLOGY.md`, `ALL_COUNTRIES_2024.md`.*

# Appendix A — every product, every headline metric

Area-weighted means across admin-1 units. `r` is the yield-pattern skill of that product's fitted
ceiling; blank means no ceiling could be fitted.

| crop | country | season | units | plant_dk | CPI | t/ha | fail% | def_mm | FCCI | irrigation | Ym | r |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| maize | Burundi | SeasonA | 17 | 27.00 | 86.50 | 5.20 | 0.20 | 0.00 | 68.80 | — | 1.88 | 0.28 |
| maize | Burundi | SeasonB | 17 | 5.80 | 79.00 | 4.80 | 0.20 | 0.00 | 49.80 | — | 1.88 | 0.28 |
| maize | Ethiopia | Belg | 11 | 7.10 | 67.30 | 3.50 | 5.50 | 31.90 | 51.00 | locally biased | 4.14 | 0.64 |
| maize | Ethiopia | Meher | 11 | 11.20 | 82.10 | 4.90 | — | — | 71.00 | locally biased | 4.14 | 0.64 |
| maize | Kenya | Longrains | 44 | 9.20 | 83.90 | 5.00 | — | — | 86.30 | — | 2.34 | 0.57 |
| maize | Kenya | Shortrains | 16 | 27.20 | — | — | — | — | — | — | 2.34 | 0.57 |
| maize | Rwanda | SeasonA | 5 | 27.00 | 81.90 | 4.90 | 0.70 | 0.00 | 57.10 | — | 2.61 | -0.07 |
| maize | Rwanda | SeasonB | 5 | 6.80 | 79.40 | 4.80 | 0.70 | 0.30 | 51.00 | — | 2.61 | -0.07 |
| maize | Somalia | Deyr | 6 | 30.50 | 0.00 | 0.00 | 90.10 | 203.30 | 40.40 | materially biased | — | — |
| maize | Somalia | Gu | 9 | 9.70 | 37.50 | 2.20 | 4.00 | 69.90 | 64.00 | materially biased | — | — |
| maize | Tanzania | Masika | 20 | 6.40 | 73.90 | 4.30 | 3.10 | 23.50 | 55.40 | — | — | — |
| maize | Tanzania | Msimu | 31 | 33.90 | 80.20 | 4.80 | 0.10 | 2.70 | 56.00 | — | — | — |
| maize | Tanzania | Vuli | 30 | 30.80 | 81.80 | 4.90 | 0.10 | 3.90 | 60.30 | — | — | — |
| maize | Uganda | 1strains | 55 | 7.40 | 68.40 | 4.10 | 0.10 | 20.80 | 53.60 | — | 2.34 | -0.14 |
| maize | Uganda | 2ndrains | 55 | 23.00 | 83.50 | 5.00 | 0.10 | 2.50 | 62.90 | — | 2.34 | -0.14 |
| millet | Eritrea | Kremti | 4 | 17.70 | 75.80 | 1.60 | 0.10 | 51.90 | 87.00 | — | — | — |
| millet | Sudan | Kharif | 15 | 17.60 | 63.80 | 1.30 | 0.50 | 109.30 | 33.70 | materially biased | 0.63 | 0.24 |
| sorghum | Burundi | SeasonA | 7 | 27.00 | 72.00 | 2.20 | 1.70 | 0.00 | 58.10 | — | 0.55 | -0.09 |
| sorghum | Burundi | SeasonB | 7 | 5.30 | 77.40 | 2.40 | 1.70 | 0.50 | 86.40 | — | 0.55 | -0.09 |
| sorghum | Eritrea | Kremti | 5 | 15.40 | 91.80 | 2.70 | 1.00 | 20.30 | 85.00 | — | — | — |
| sorghum | Ethiopia | Belg | 9 | 7.10 | 70.10 | 2.10 | 2.00 | 43.40 | 47.80 | — | 2.60 | 0.22 |
| sorghum | Ethiopia | Meher | 9 | 15.00 | 87.40 | 2.60 | 0.10 | 5.80 | 83.30 | — | 2.60 | 0.22 |
| sorghum | Kenya | Longrains | 20 | 6.90 | 76.60 | 2.30 | 0.20 | 36.70 | 65.40 | — | 1.42 | 0.54 |
| sorghum | Kenya | Shortrains | 20 | 29.60 | 81.40 | 1.60 | 0.10 | 20.10 | 51.80 | — | 1.42 | 0.54 |
| sorghum | Rwanda | SeasonA | 5 | 27.00 | 76.60 | 2.30 | 0.70 | 0.00 | 64.80 | — | 1.34 | 0.43 |
| sorghum | Rwanda | SeasonB | 5 | 6.40 | 76.60 | 2.30 | 0.70 | 3.90 | 90.20 | — | 1.34 | 0.43 |
| sorghum | Somalia | Deyr | 8 | 30.40 | 16.50 | 0.30 | 50.90 | 177.90 | 56.60 | materially biased | 0.41 | 0.26 |
| sorghum | Somalia | Gu | 8 | 9.30 | 53.30 | 1.60 | 2.60 | 61.70 | 71.00 | materially biased | 0.41 | 0.26 |
| sorghum | South Sudan | 2nd | 10 | 20.00 | 80.00 | 1.60 | 0.30 | 18.40 | 80.00 | — | — | — |
| sorghum | South Sudan | Main | 10 | 15.20 | 76.10 | 2.30 | 0.20 | 53.10 | 65.50 | — | — | — |
| sorghum | Sudan | Kharif | 18 | 18.20 | 52.00 | 1.50 | 2.30 | 114.40 | 39.80 | materially biased | 0.83 | -0.33 |
| sorghum | Tanzania | Masika | 5 | 6.00 | 92.90 | 2.70 | 0.00 | 8.10 | 57.00 | — | — | — |
| sorghum | Tanzania | Msimu | 17 | 33.00 | 80.30 | 2.40 | 0.00 | 26.60 | 26.30 | — | — | — |
| sorghum | Uganda | 1strains | 24 | 7.10 | 74.50 | 2.20 | 0.70 | 20.40 | 78.60 | — | 1.30 | -0.02 |
| sorghum | Uganda | 2ndrains | 25 | 26.70 | 82.10 | 1.60 | 0.50 | 2.30 | 69.90 | — | 1.30 | -0.02 |
| teff | Ethiopia | Meher | 6 | 18.10 | 84.50 | 1.60 | 0.30 | 8.70 | 83.80 | — | 1.77 | 0.33 |
| wheat | Ethiopia | Meher | 5 | 17.20 | 85.10 | 3.40 | 0.10 | 7.90 | 83.20 | — | 2.69 | 0.15 |
| wheat | Kenya | Longrains | 16 | 11.10 | 83.60 | 3.30 | 0.00 | 0.70 | 67.80 | — | 3.11 | 0.07 |
| wheat | Sudan | Shitwi | 6 | 31.00 | 0.00 | 0.00 | 100.00 | 461.30 | 26.90 | INVALID as rainfed | — | — |
| wheat | Tanzania | Msimu | 5 | 2.40 | 88.40 | 3.50 | 0.00 | 0.20 | 58.90 | — | — | — |
