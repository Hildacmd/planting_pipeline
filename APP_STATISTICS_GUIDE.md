# App Statistics — What Each Number Means

A guide to every statistic shown in the **Planting-Window Explorer** and the **2024 Maize Risk
Monitor**. Each value is a per-admin summary (county / constituency / ward, or region / zone / woreda)
over the **maize** area of that unit. Time is measured in **dekads** (10-day periods, 1–36 per year;
labelled `N·Mon-dN`, e.g. `9·Mar-d3`). See §8 for conventions.

---

## 1. Planting window

| Statistic (app label) | Key | What it represents |
|---|---|---|
| **Modal planting** | `md` | The most common estimated planting dekad in the unit — the headline "plant around here" date. |
| **Mean planting** | `mean` | Area-average planting dekad. |
| **Median (P50)** | `p50` | Middle planting dekad (half the maize plants earlier, half later). |
| **Earliest–Latest (P10–P90)** | `p10`,`p90` | The spread: 10% of maize plants by P10, 90% by P90. A wide gap = varied onset across the unit. |
| **Last Viable Planting (LVPD)** | `lvpd` | The **climatological latest** dekad you can plant and still have short-duration maize mature before the reliable rains end (`LGP-end + residual soil water − early-maize cycle`). A "plant **no later than**" guide. *Short rains only.* |
| **Planting viability %** | `viab` | % of the unit's maize area where **early-variety (~90-day) maize planted at the 2024 onset reaches WRSI ≥ 50** (i.e. not crop-failure). Low = the onset was too late / the land too dry to grow maize reliably. *Short rains only.* |

*Reading the window:* **plant-by (Modal) → LVPD** is the usable planting window; **viability %** says how
much of that maize area actually made it in 2024.

## 2. Calendar skill (agreement with the FEWS / FAO calendar)

| Statistic | Key | What it represents |
|---|---|---|
| **Calendar hit-rate** | `hit` | Share of maize pixels whose planting dekad falls **inside** the indicative FEWS/FAO planting window. Higher = closer to the reference calendar. |
| **Bias** | `bias` | Mean dekads **early (−)** or **late (+)** relative to the window centre. |
| **MAE** | `mae` | Mean absolute departure (in dekads) from the window centre — the typical size of the miss, regardless of direction. |

## 3. Crop extent

| Statistic | Key | What it represents |
|---|---|---|
| **Crop area fraction (CAF)** | `caf` | Share of the whole unit that is **detected maize** (maize pixels ÷ total pixels). Also the denominator for the ASAP "% of crop area" risk rule. |
| **Maize pixels** | `n` | Number of maize pixels the statistics were computed from. |

## 4. Water balance & crop-water risk

| Statistic | Key | What it represents |
|---|---|---|
| **Mean WRSI** | `wrsi` | FAO-56/33 **Water Requirement Satisfaction Index** (0–100): how much of the crop's water need was met over the season. **≥ 95** no stress · **80–95** good · **60–80** mediocre · **50–60** poor · **< 50** crop failure. |
| **Water deficit** | `def` | Season-cumulative unmet crop water demand, in **mm**. |
| **Crop-failure risk** | `fail` | % of the unit's maize area with **WRSI < 50** (failure). Shown as **ASAP classes** (§8): Watch ≥ 25% · Alert ≥ 50% · Critical ≥ 75%. |

## 5. Drought (rainfall anomaly)

| Statistic | Key | What it represents |
|---|---|---|
| **Mean SPI-3** | `spi` | 3-month **Standardized Precipitation Index** vs the 1981–2020 climatology: **− dry / + wet**. ≤ −1 moderate drought, ≤ −1.5 severe, ≥ +1 notably wet. |
| **Drought risk (SPI-3)** | `spidry` | % of maize area in **SPI-3 ≤ −1** (drought). Shown as **ASAP classes**: Watch ≥ 25% · Alert ≥ 50% · Critical ≥ 75%. |

## 6. Phenology — GDD clock (predicted stage dekads)

Per-pixel dekad each maize stage is reached, from the Growing-Degree-Day clock, summarised to the unit.

| Statistic | Key | What it represents |
|---|---|---|
| **Peak vegetative** | `pkv` | Tasseling (VT) — end of vegetative growth / canopy peak. |
| **Flowering** | `flo` | Silking (R1) — the **critical** water/heat-sensitive stage. |
| **Grain filling** | `grf` | R2/R3 — yield formation begins. |
| **Maturity** | `mat` | R6 physiological maturity — **end of season**. |

*Short rains* mature in the **next calendar year**, so these dekads can exceed 36 and are labelled with
`+1y` (e.g. `44·Mar-d2+1y` = the next year).

## 6b. Stage-resolved water balance (short rains) — how the season unfolds

The whole-season WRSI (§4) is one number; these show the water balance **evolving across the three
growth stages**, so you can see *when* stress bites. *Short rains only.*

| Statistic | Key | What it represents |
|---|---|---|
| **WRSI veg → flo → grf** | `wrv`,`wrf`,`wrg` | **Running WRSI** at the end of vegetative / flowering / grain-fill (0–100). A falling sequence (e.g. 100 → 84 → 76) shows satisfaction eroding as the season dries. |
| **Water stress veg / flo / grf** | `wsv`,`wsf`,`wsg` | The **worst dekadal water stress** within each stage (0–100, higher = worse). A spike at grain-fill = the rains quit before filling finished. |
| **Crop-failure @ flowering** | `failflo` | % of maize area with **running WRSI < 50 at flowering** — the *critical* stage (FAO-33 Ky 1.5). The headline stage risk; ASAP-classed. |

*Reading it:* `WRSI 100 → 84 → 76` with `stress 0 / 5 / 40%` says the crop was well-watered through
flowering and only stressed during grain-fill — a common short-rains pattern.

## 7. Where a statistic comes from (season by season)

- **Kenya Long rains** and **Ethiopia Meher** — planting is **green-up-led** (Sentinel-2 red-edge SOS),
  genuinely fine resolution. LVPD / viability are **not shown** (main seasons — maize fits comfortably).
- **Kenya Short rains** — planting is **rainfall-anchored** (CHIRPS onset), **LVPD-gated**, with
  **year-wrapping** GDD phenology. This is the season that carries LVPD and viability %.

## 8. Conventions & cautions

- **Dekad** = 10-day period, 1–36 per year; labelled `N·Mon-dN`. **`+1y`** = the following calendar year
  (short-rains phenology).
- **Median** is used to summarise dekad quantities (robust, returns a real dekad); **mean** for
  fractions/percentages.
- **"No signal" (grey unit)** = **no value computed here** — fewer than ~5 valid maize pixels for that
  layer (little/no mapped maize, or that layer's raster didn't resolve the unit). It is *not* zero or
  failure, and it differs from the ASAP **"None"** class, which means *has data, low risk*.
- **ASAP classes** (crop-failure, drought) grade a unit by the **% of its maize area affected**:
  Watch ≥ 25% · Alert ≥ 50% · Critical ≥ 75%.
- **Resolution honesty:** planting and phenology are genuinely **250 m** (Sentinel-2/1-driven,
  elevation-resolved); **WRSI, SPI-3 and the LVPD** carry **~5.5 km** (CHIRPS/climate) information
  content displayed on the 250 m grid — robust for admin roll-ups, not pixel-sharp.

*Full methods and citations: `ALGORITHMS_AND_REFERENCES`, `WORKFLOW`, `WORKFLOW_SHORTRAINS`,
`RISK_MONITORING_DESIGN`.*
