# Excess-Rain / Waterlogging Methodology — Maize, GHA / ICPAC

Monitors the **wet-side** agricultural hazard that the WRSI deficit index cannot see. Excess water
causes root hypoxia, seed rot, nitrogen loss, disease and lodging — acute in wet years (e.g. the
April–May 2024 Kenya floods). Two **complementary** metrics are computed for all three seasons (Kenya
Long + Short rains, Ethiopia Meher) and aggregated to admin units by the ASAP % -of-crop-area rule.

## 1. Why WRSI misses it

The FAO-56/33 water balance caps soil water at the water-holding capacity and lets anything above run
off (`SW = min(SW + P − AET, WHC)`), so **excess incurs no penalty** — WRSI is a *deficit* index. A wet
year therefore looks "safe" to WRSI even while crops drown. Waterlogging needs its own layer.

## 2. Workflow at a glance

![Waterlogging workflow](waterlogging_diagram.png)

Two metrics answer **two different questions**:

| Metric | Question | Basis | Status |
|---|---|---|---|
| **SPI-3 wet tail** | *Was it anomalously wet?* (surface / seasonal) | rainfall anomaly vs climatology | **VALIDATED** |
| **Aeration-stress index** | *Did the soil stay saturated in the root zone?* | soil-water balance (AquaCrop) | **MODELLED · uncalibrated** |

They are not redundant: the 2024 Ol Kalou event was largely *surface* flooding (high SPI-3-wet) on
well-draining highland soils (low modelled aeration). Reporting both separates the two hazards.

## 3. Crop impact & the critical stage

Maize is **acutely waterlogging-intolerant at establishment / early-vegetative** (roughly V1–V6): a few
days of saturated soil cause root hypoxia, seed rot, denitrification/N leaching and stand loss, often
unrecoverable [Zaidi et al. 2004; Ren et al. 2014; Kaur et al. 2020]. This is the **mirror image** of the
deficit side, where flowering is most critical:

```
deficit (yield loss to water STRESS)   Ky : veg 0.40 · flo 1.50 · grf 0.50   flowering worst   [Doorenbos & Kassam 1979]
excess  (loss to WATERLOGGING)     weight : veg 1.00 · flo 0.60 · grf 0.35   establishment worst  (first-pass)
```

**Basis of the weights.** The *ordering* (establishment > flowering > grain-fill) is literature-grounded
[Zaidi 2004; Ren 2014; Kaur 2020]. There is **no FAO-33-equivalent standardised "waterlogging Ky"**, so
the numeric weights are a **first-pass** derived from the relative yield-loss order in those studies and
are flagged for calibration (as with the CPI heat/veg parameters).

## 4. Metric ① — SPI-3 wet tail (validated, anomaly-based) — `src/excess.py`, `src/spi.py`

```
P3   = 3-month CHIRPS total (season-appropriate end month)
SPI-3 = ((P3/μ)^(1/3) − 1 + 1/(9a)) · √(9a)          # Wilson–Hilferty gamma, a = (μ/σ)²  [McKee 1993]
wet   = SPI-3 ≥ +1.5   (very wet)                     # the positive mirror of the drought tail
excess-wet % = share of maize area with wet=1  →  Watch ≥25 / Alert ≥50 / Critical ≥75  [Rembold 2019]
```

Anomaly-based, so it separates *anomalously* wet from *normally* wet. **Validated** against the April–May
2024 central-Rift-Valley floods (Ol Kalou 36 %, Bahati 35 % of maize area very wet). SPI-3 is shared with
the drought side — the wet tail vs the dry tail of the same index.

## 5. Metric ② — AquaCrop aeration-stress index (modelled, uncalibrated) — `src/excess.py`, `src/soil.py`

This is what "*soil water exceeding field capacity*" means physically. It uses the **maize water balance
and the soil's own field capacity, saturation and drainage**, so it is soil-relative — well-drained soils
drain the excess and don't flag (arid Garissa → 0), fixing the failure of a naïve fixed-mm-threshold.

### 5.1 Soil hydraulics — Saxton–Rawls (2006) on SoilGrids texture — `soil.build_hydro_mm`
```
inputs per depth layer: Sa (sand), Cl (clay) fractions; OM = 1.724·SOC%           [SoilGrids 2.0; Poggio 2021]
θ33  (field capacity)   = Saxton–Rawls FC pedotransfer                              [Saxton & Rawls 2006]
θ1500(wilting point)    = Saxton–Rawls WP pedotransfer
θsat (saturation)       = θ33 + θ(S−33) − 0.097·Sa + 0.043
Ksat (mm/hr)            = 1930·(θsat − θ33)^(3 − λ),  λ = 1/B, B from the θ33/θ1500 tension curve
FC_mm, SAT_mm           = θ33, θsat integrated over the maize root zone (1 m)
τ (drainage, /day)      = 0.0866·(Ksat·24)^0.35, clamped [0,1], from the bottleneck (min-Ksat) layer
```
τ → 1 for sand (excess drains in a day) and small for heavy clay (water perches) — this is the drainage
contrast that a rainfall threshold cannot represent.

### 5.2 Daily aeration balance — `excess.aeration_stress_index`
A **daily** root-zone soil-water balance (AquaCrop convention — waterlogging is a short, acute event that
a dekadal balance smooths out):
```
each day d in [onset, onset + LGP]:
  W  = clamp( W + P_d − ET ,  0 ,  SAT_mm )                 # ET ≈ 4 mm/day (first-pass); cap at saturation
  W  = FC_mm + max(W − FC_mm, 0)·(1 − τ)                    # gravitational water drains at the soil's rate
  thr = FC_mm + AER_START·(SAT_mm − FC_mm)                  # anaerobiosis point (AER_START = ½)
  aer = clamp( (W − thr) / (SAT_mm − thr) , 0 , 1 )         # 0 below the point, 1 at saturation
  run = ( run + aer·w_stage )·[W > thr]·[in cycle]          # accumulate while saturated, RESET when it drains
  peak = max(peak, run)
waterlog index = 100 · clamp( peak / SCALE , 0 , 1 )        # SCALE ≈ 4 consecutive stage-weighted aeration-days
```
The **peak-consecutive-with-reset** design is the key: a soil that drains between storms never builds a
high `run`, so drainage (τ) genuinely discriminates — the physical fix the fixed-threshold prototype
lacked. `w_stage` applies the establishment-worst weights (§3). Aeration stress and the multiplicative-
stress framing follow AquaCrop [Raes et al. 2009; Steduto et al. 2009].

### 5.3 Admin aggregation
```
waterlog % = share of maize area with aeration index ≥ 25  →  Watch/Alert/Critical (ASAP)
```

## 6. Parameters (v1 — first-pass, uncalibrated)

| Parameter | Value | Meaning |
|---|---|---|
| Stage weights (veg/flo/grf) | 1.00 / 0.60 / 0.35 | waterlogging sensitivity (establishment worst) |
| AER_START | 0.5 | anaerobiosis point, fraction FC→SAT where stress begins |
| ET | 4 mm/day | simple crop ET (excess is rain-dominated) |
| SCALE | 4 aeration-days | consecutive stage-weighted stress for index = 100 |
| W₀ | 0.8·FC | soil water at planting (dry-ish start) |
| SPI-3 wet threshold | +1.5 | "very wet" (McKee 1993) |
| root depth | 1.0 m | FAO-56 maize rooting depth |

## 7. Validation & the honest position

- **SPI-3-wet is validated** against the 2024 floods and ships as the primary excess signal.
- **The aeration index behaves physically** (arid → 0; drainage-aware) but its parameters
  (τ, AER_START, ET, SCALE, stage weights) are **first-pass and UNCALIBRATED** — no waterlogging
  ground-truth (crop-cut / field reports) exists yet to certify the ranking. In testing it ranked
  tight-soil semi-arid areas above well-draining flooded highlands — plausibly correct (root-zone
  saturation ≠ surface flooding) but **unconfirmed**. It therefore ships **clearly labelled as
  indicative / modelled**, to be cross-checked against SPI-3-wet.

## 8. Calibration path (before operational reliance)
```
regress modelled aeration index vs OBSERVED waterlogging / crop-damage
  sources: crop-cut & field damage reports · FAO/GIEWS · county agriculture returns · flood extents (Sentinel-1)
  tune:    τ mapping, AER_START (anaerobiosis point), ET, SCALE, and the stage weights
validate: separately from surface-flood extent (the two hazards should NOT be forced to agree)
```
A refined τ (from Sentinel-1 flood/soil-moisture) and a proper Kc·ET₀ term are the first upgrades.

## 9. Caveats
- **Aeration index uncalibrated** — indicative until calibrated (§8).
- **Resolution:** CHIRPS ~5.5 km rainfall on the 250 m grid; the *soil* (SoilGrids/Saxton) is genuinely
  250 m. Admin-scale estimate, not field-level.
- **Two hazards, not one** — do not collapse SPI-3-wet and the aeration index into a single number; they
  answer different questions.
- **ET & antecedent moisture** are simplified (constant ET, dry-ish start) — refine in calibration.

## 10. References
- Doorenbos, J. & Kassam, A. H. (1979). *Yield response to water (Ky).* FAO Irrigation & Drainage Paper 33.
- Zaidi, P. H. et al. (2004). *Tolerance to excess moisture in maize: susceptible crop stages and identification of tolerant genotypes.* Field Crops Research 90(2–3), 189–202. https://doi.org/10.1016/j.fcr.2004.03.002
- Ren, B. et al. (2014). *Effects of waterlogging on the yield and growth of summer maize under field conditions.* Canadian J. Plant Science 94(1), 23–31. https://doi.org/10.4141/cjps2013-175
- Kaur, G. et al. (2020). *Impacts and management strategies for crop production in waterlogged or flooded soils: a review.* Agronomy Journal 112(3), 1475–1501. https://doi.org/10.1002/agj2.20093
- Raes, D. et al. (2009). *AquaCrop — the FAO crop model: II. Main algorithms and software (aeration/waterlogging stress).* Agronomy Journal 101(3), 438–447. https://doi.org/10.2134/agronj2008.0140s
- Steduto, P. et al. (2009). *AquaCrop — concepts and underlying principles.* Agronomy Journal 101(3), 426–437. https://doi.org/10.2134/agronj2008.0139s
- Saxton, K. E. & Rawls, W. J. (2006). *Soil water characteristic estimates by texture and organic matter.* Soil Sci. Soc. Am. J. 70(5), 1569–1578. https://doi.org/10.2136/sssaj2005.0117
- Poggio, L. et al. (2021). *SoilGrids 2.0.* SOIL 7, 217–240. https://doi.org/10.5194/soil-7-217-2021
- McKee, T. B. et al. (1993). *The relationship of drought frequency and duration to time scales (SPI).* 8th Conf. Applied Climatology, AMS, 179–184.
- Funk, C. et al. (2015). *CHIRPS.* Scientific Data 2:150066. https://doi.org/10.1038/sdata.2015.66
- Rembold, F. et al. (2019). *ASAP anomaly hot spots of agricultural production.* Agricultural Systems 168, 247–257. https://doi.org/10.1016/j.agsy.2018.07.002

*Code: `src/excess.py` (SPI-3-wet + aeration balance), `src/soil.py` (Saxton hydraulics), `run_onset_excess.py`,
`run_excess_shortrains.py`, `excess_admin.py`. Companion: `RISK_MONITORING_METHODOLOGY` §3.8, `CPI_METHODOLOGY`.
Verify DOIs/editions before formal use.*
