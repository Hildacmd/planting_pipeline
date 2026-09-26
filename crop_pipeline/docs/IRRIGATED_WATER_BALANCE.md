# The water balance is rainfed. Where crops are irrigated, this is what it means.

**Scope:** all 41 products that exist across the five crops (maize, sorghum, wheat, teff, millet)
and eleven countries. **Status:** 1 product must not be read as crop condition, 6 more carry a
material bias, 2 a local one, and 32 are unaffected.

Everything below is computed, not asserted. The four scripts in `crop_pipeline/irrigation/`
regenerate every number, and the CSVs they write are the tables. The grades are consumed at runtime
by `irrigation_exposure.py`, which is what stamps the Earth Engine assets and drives the app banner
— so the note, the assets and the apps cannot drift apart.

> **Correction, 26 September 2026.** The first version of this note reported Sudan **maize** Kharif
> as the headline failure (ρ = −0.717). That was wrong on two counts: the asset prefix `newcM_` is
> **millet**, not maize, and **no Sudan maize product exists** — the row in `config/season_calendar.csv`
> was never built. Re-run against each product's own crop, the finding survives and moves to **Sudan
> millet Kharif** (ρ = −0.678, p = 0.005). The product inventory is now enumerated from the reduce
> CSVs on disk (`crop_pipeline/irrigation/products.py`) rather than from the calendars, so a
> never-built row cannot be graded again.

---

## 1. Why the balance cannot see irrigation

`src/wrsi_waterbalance.py` steps a single-layer FAO-56 bucket forward one dekad at a time
(`run_wrsi_fao33`, and the staged form `run_wrsi_staged` used by every product). Per dekad *t*:

```
WR(t)  = Kc(dsp) · ET0(t)                 water requirement,  Hargreaves ET0 from ERA5-Land
Wb(t)  = SW(t-1) + P(t)                   water available  ←  SOIL WATER + RAINFALL, nothing else
AET(t) = min(Wb(t), WR(t))                actual evapotranspiration
SW(t)  = clamp(Wb(t) - AET(t), 0, WHC)    carry-over, capped at water-holding capacity
WRSI   = 100 · ΣAET / ΣWR                 over the crop cycle
```

The supply term is `SW + P`. `P` is CHIRPS rainfall. **There is no irrigation term, and no
groundwater or river-diversion term.** The initial condition makes it stricter still:
`init_soil_water_frac: 0.0` (`config/crop_coefficients.yaml:16`) — a dry start at onset, the WRSI
convention. So the balance answers exactly one question: *could rainfall alone have met this crop's
demand?*

For a rainfed crop that is water stress, and the chain that follows is valid:

```
S_water = 100 · (1 − ΣAET/ΣWR) per stage → CPI = 100(1−Sw)(1−Sh)(1−Sv) → Ya = CPI/100 · Ym
```

For an irrigated crop every link is wrong, and wrong in one direction. The scheme met the shortfall;
the balance did not know; so `S_water` is high, `CPI` is low and `Ya` is low. **The deficit is real —
but it is the irrigation requirement, not crop stress.** Those are different quantities, and the
pipeline reports the first under the name of the second.

## 2. How much of each crop is actually irrigated

SPAM 2020 publishes physical area per crop under `_I` (irrigated) and `_A` (all technologies), so the
irrigated share is `I / A` summed inside a boundary. `spam_irrigated_share.py` does this per country
(GADM 4.1 ADM_0); `spam_irrigated_admin1.py` repeats it at ADM_1 for every (country, crop) pair that
has a product — never against another crop's raster.

Irrigated share of physical area, % — **SPAM 2020**:

| country | maize | sorghum | wheat | millet | teff\* |
|---|---|---|---|---|---|
| **Sudan** | *(no product)* | 4.4 | **98.4** | 0.4 | – |
| **Somalia** | **24.8** | **12.0** | – | – | – |
| South Sudan | 0.5 | 4.4 | – | – | – |
| Ethiopia | 2.1 | 1.1 | 0.4 | 0.4 | 0.4 |
| Tanzania | 1.3 | 0.0 | 0.0 | – | – |
| Kenya | 0.3 | 0.2 | 0.0 | – | – |
| Uganda | 0.2 | 0.0 | – | – | – |
| Rwanda · Burundi · Eritrea | 0.0 | 0.0 | 0.0 | 0.0 | – |

\*SPAM has no teff class; the crop-type mask carries teff on *other cereals* (OCER) and this share
uses the same proxy. Indicative only.

**The national figure can badly understate the problem, because irrigation sits on schemes.**
Sudan millet is the proof: 0.4 % nationally, but 71.9 % in Al Jazirah. At ADM_1
(`spam2020_irrigated_admin1.csv`), every unit above 20 % irrigated that has a product:

| country · crop | irrigated admin-1 units |
|---|---|
| Sudan wheat | Kassala **100 %**, Khartoum 100 %, River Nile 100 %, White Nile 100 %, Al Jazirah **99.7 %**, Al Qadarif 99.7 %, Sennar 95.3 % |
| Sudan sorghum | Kassala 50.6 %, Sennar 46.3 %, White Nile 40.1 %, **Al Jazirah 31.0 % on 491,000 ha** — but Al Qadarif, the 3.3 M ha bulk, is 0.4 % |
| Sudan millet | Khartoum 95.4 % *(71 ha)*, **Al Jazirah 71.9 % on 8,917 ha**, Kassala 41.1 % |
| Somalia sorghum | Jubbada Hoose **84.2 %**, Shabeellaha Dhexe 76.5 %, Shabeellaha Hoose 28.6 % |
| Somalia maize | Shabeellaha Dhexe 46.2 %, Jubbada Hoose 33.6 %, Shabeellaha Hoose 28.9 % |
| Ethiopia maize | Afar **96.8 %** *(1,707 ha)*, Dire Dawa 48.2 % *(288 ha)* |

Note the areas in italics. **Percentage alone is not exposure** — Khartoum millet is 95 % irrigated
on 71 ha and compromises nothing; Al Jazirah sorghum is 31 % irrigated on 491,000 ha and compromises
152,000 ha. The grading in §5 weighs both.

## 3. The bias is measurable in shipped output

`cpi_vs_irrigation.py` joins each product's own admin-1 CPI to the irrigated share of **its own
crop** and takes Spearman ρ. Negative ρ = the units SPAM calls irrigated are the units the pipeline
calls failing. Products with a real irrigated gradient:

| product | n | ρ(CPI, irr %) | p | ρ(WRSI, irr %) | max irr % |
|---|---|---|---|---|---|
| **Sudan millet Kharif** | 15 | **−0.678** | **0.005** | **−0.680** | 95.4 |
| Ethiopia maize Meher | 10 | −0.520 | 0.123 | −0.587 | 96.8 |
| Ethiopia maize Belg | 10 | +0.067 | 0.854 | +0.201 | 96.8 |
| Sudan wheat Shitwi | 6 | *CPI is 0 in all 6 — undefined* | | | 100.0 |
| Somalia maize Deyr | 5 | *CPI is 0 in all 5 — undefined* | | **−1.000** | 46.2 |
| Somalia maize Gu | 5 | +0.103 | 0.870 | 0.000 | 46.2 |
| Somalia sorghum Gu | 8 | +0.262 | 0.532 | −0.381 | 84.2 |
| Somalia sorghum Deyr | 8 | −0.189 | 0.654 | +0.013 | 84.2 |
| Sudan sorghum Kharif | 18 | −0.170 | 0.501 | −0.201 | 50.6 |
| South Sudan sorghum Main | 10 | −0.267 | 0.455 | +0.134 | 13.7 |

**Sudan millet Kharif 2024 is the one demonstrable case** (ρ = −0.678, p = 0.005, n = 15):

| admin-1 | millet irr % | millet area ha | CPI | mean WRSI | S_water | yield t/ha |
|---|---|---|---|---|---|---|
| Khartoum | 95.4 | 71 | **10** | 43.7 | 78 | 0.23 |
| **Al Jazirah** (Gezira) | 71.9 | 8,917 | **37** | 65.2 | 55 | 0.68 |
| White Nile | 2.6 | 55,619 | 39 | 67.3 | 55 | 0.74 |
| Red Sea | 2.0 | 16,935 | 10.5 | 49.6 | 76 | 0.21 |
| Sennar | 2.0 | 60,428 | 77 | 98.2 | 0 | 1.52 |
| Al Qadarif | 0.9 | 74,629 | 34 | 77.1 | 47 | 0.75 |
| Blue Nile | 0.0 | 20,009 | 82 | 99.3 | 0 | 1.62 |
| Central Darfur | 0.0 | 91,962 | 87 | 99.5 | 0 | 1.71 |
| South Darfur | 0.0 | 473,339 | 83 | 97.6 | 2.1 | 1.66 |
| *(6 more Darfur / Kurdufan, all 0 %)* | 0.0 | 9k–586k | 53–72 | 80–94 | 17–43 | 1.07–1.47 |

The two most-irrigated states score lowest; the nine fully-rainfed Darfur and Kurdufan states score
53–87. **Read it honestly, though:** only two units carry the signal, and Sudan's irrigated millet is
12,081 ha of 2.75 M ha. **The national millet figure is sound; two states are wrong.** That is why
this grades as *materially biased* and not *invalid*.

**Sudan wheat Shitwi** is the degenerate case — CPI 0 in all six states including the Gezira, so ρ is
undefined because there is no variance left to correlate. **Somalia maize Deyr** is the same: CPI 0
across all five riverine regions, with WRSI falling monotonically as irrigated share rises
(ρ = −1.000 over 5 units — the asymptotic p scipy reports is not trustworthy at n = 5; the exact
two-sided probability of a perfect rank ordering by chance is 1/60 ≈ 0.017).

**Two cautions on reading this table.**

1. *Exposure is not corruption.* **Sudan sorghum** has four states at 31–51 % irrigated and 288,569 ha
   under irrigation — more irrigated area than any other product here — yet ρ = −0.17 (p = 0.50).
   Sudan's sorghum is overwhelmingly rainfed mechanised farming in Al Qadarif (3.3 M ha at 0.4 %).
   The grade flags it for inspection; the correlation says the national product still ranks sensibly.
2. *Multiple testing.* Around 28 correlations were computed. At α = 0.05 roughly one false positive
   is expected, and one duly appeared: **Uganda sorghum 1st rains, ρ = −0.416, p = 0.043, on a crop
   whose most-irrigated district is 0.9 %.** There is no mechanism; it is noise, and it is not
   reported as a finding. Sudan millet is credible because it pairs a small p with a 95-point
   irrigated gradient and a named scheme.

## 4. What the pipeline does about it

**Sudan wheat Shitwi** is handled explicitly. `crop_pipeline/run_all_crop.py:52` —
`IRRIGATED = {("Sudan", "Shitwi")}`. It is scheme-irrigated winter wheat on the Nile and the Gezira,
sown in November in the dry season, with two consequences:

1. **Onset cannot be detected.** The CHIRPS 25/20 mm FEWS rule needs 25 mm in a dekad and Sudan gets
   essentially none in November, so the rainfall onset returned nothing — the first run produced an
   asset with 10,478 wheat-mask pixels and **zero valid ones**. Green-up onset fares no better: it is
   gated to a rainfall-driven climatological onset that does not exist here. The workaround fixes the
   planting dekad at the **start of the calendar's indicative window** (`Nov-d1`), because planting on
   a scheme is scheduled rather than rain-driven. It is an assumption about timing, recorded on the
   asset as `onset_method = "fixed (irrigated scheme)"`.
2. **The product is excluded from the apps and the Atlas.** With the fixed onset the run completes and
   returns WRSI 0, S_water 100 % and CPI 0 across all 18 localities including the Gezira —
   arithmetically correct and agronomically meaningless. The asset and CSV are retained, because the
   deficit *is* the irrigation requirement. The exclusion is now driven by the exposure grade
   (`app_data.py`: `IRR.grade(...) == "INVALID as rainfed"`), not by a hardcoded country-season, so a
   future product on a majority-irrigated crop is caught without anyone remembering to add it.

**Every other exposed product is flagged rather than withheld**, because its national aggregate is
still sound:

- **Earth Engine assets** carry `irrigation_exposure`, `irrigation_national_pct`, `irrigation_area_ha`,
  `irrigation_admin1_max_pct`, `irrigation_units` and `irrigation_note`. Set at export time by the
  runners; the 70 assets exported before the exposure was known were patched in place by
  `tag_assets_irrigation.py` (which merges, never replaces, the existing property map).
- **The apps** (`pw_app.html`, `risk_app.html`) render a banner above the map for any product whose
  grade is not negligible, amber for biased and red for invalid, naming the affected units.
- **The Atlas stress layer** refuses to write without `mean_deficit_mm` rather than falling back to
  `S_water` %, for the same reason: a legend committed to 0–200 mm showing a percentage would be
  readable and wrong.

## 5. Per-product exposure

`product_exposure.py` grades all 41 products. Full table:
`crop_pipeline/irrigation/product_irrigation_exposure.csv`. A unit counts as **compromised** only if
it is both substantially irrigated *and* holds real area: `irrigated_pct ≥ 30 AND area_all_ha ≥ 1000`.

| grade | rule | n | products |
|---|---|---|---|
| **INVALID as rainfed** | national ≥ 40 % | **1** | Sudan wheat Shitwi (98.4 %) |
| **materially biased** | national ≥ 10 %, or ≥ 2 compromised units, or ≥ 50,000 ha irrigated | **6** | Somalia maize Gu & Deyr · Somalia sorghum Gu & Deyr · Sudan sorghum Kharif · Sudan millet Kharif |
| **locally biased** | ≥ 1 compromised unit | **2** | Ethiopia maize Meher & Belg (Afar) |
| **negligible** | none of the above | **32** | all Kenya, Uganda, Rwanda, Burundi, Tanzania and Eritrea products; Ethiopia sorghum, wheat and teff; South Sudan maize and sorghum |

**How to read each grade.** *Invalid*: do not report CPI, yield or stress; the deficit is the
irrigation requirement. *Materially biased*: report at admin-1, name the irrigated units, and do not
rank them against rainfed units in the same table. *Locally biased*: national aggregates are sound,
the named units are not. *Negligible*: report as rainfed, no caveat.

**78 % of products are unaffected**, and the exposure is concentrated in two countries. Every teff
product, every Kenyan and Tanzanian wheat product, and all of Rwanda, Burundi, Uganda and Eritrea are
rainfed to within 0.4 %.

## 6. Gaps

**G1 — No irrigation supply term (structural, affects 9 products).** `Wb = SW + P` has no place to
credit applied water. This is the root cause of everything above. The honest obstacle is that no
GHA-wide dekadal dataset of *applied* irrigation exists — only of irrigated *extent*. Any supply term
would be an assumption dressed as data.

**G2 — The crop mask does not separate irrigated from rainfed area.** `ctm_mask.crop_mask` returns one
fraction per pixel for total physical area, mixing both technologies, so a pixel in Al Jazirah is
99.7 % irrigated wheat and the pipeline treats all of it as rainfed. SPAM's `_I` and `_R` layers exist
at 10 km and would support splitting the mask in two. **This is the most tractable fix and the one to
do first** (§7).

**G3 — Ym calibration absorbs the bias where it is fitted, and fails where it is total.** Ceilings are
fitted by least squares through the origin of reported yield on CPI. Where CPI is biased low by
irrigation but reported yield includes irrigated production, the fit compensates by **inflating Ym** —
the level comes out roughly right while the spatial pattern stays inverted. Sudan sorghum Kharif is
the visible symptom: fitted Ym 0.83 t/ha with **r = −0.33** (`sorghum_params.py:74`), a negative
correlation shipped as a calibration. Sudan millet Kharif is fitted at 0.63 t/ha with r = +0.24
(`crop_pipeline/params/millet.py:41`) — positive, but fitted over states two of which are scheme
irrigated. Where CPI is 0 the fit is impossible: **Sudan wheat has no entry in
`crop_pipeline/params/wheat.py` YM_CAL** and never can under a rainfed balance.

**G4 — SPAM 2020 is a 2020 snapshot, and both directions of drift matter.** Ethiopia's irrigated wheat
programme expanded substantially after 2020, so SPAM's 0.4 % for Ethiopia wheat is likely an
**understatement** and Ethiopia wheat Meher may belong a grade higher than *negligible*. In the other
direction, Sudan's schemes have been disrupted since 2023, so the Gezira may have been **less**
irrigated in the 2024 season than SPAM says. Neither is quantified here and neither should be guessed
at — the grades are as-of-2020 exposure, which is the right prior and not a measurement of 2024.

**G5 — The deficit overstates the net irrigation requirement.** Reinterpreting `deficit_mm` as the
irrigation requirement is right in kind but not calibrated in amount: it starts from a dry profile
(`init_soil_water_frac = 0.0`) and credits no application efficiency, no capillary rise from shallow
Nile-valley water tables, and no scheme scheduling. Treat it as an upper bound on net requirement, not
a scheme water order.

**G6 — Teff has no SPAM class.** Its exposure is inferred from *other cereals*. Ethiopian teff is close
to entirely rainfed, so the conclusion is almost certainly safe, but it rests on a proxy.

**G7 — Statistical power is thin where it matters most.** The products with the worst exposure have the
fewest admin-1 units (Somalia maize n = 5, Sudan wheat n = 6). ρ cannot demonstrate a problem at that
size, and in two cases cannot be computed at all because CPI has collapsed to a constant 0. **Absence
of a significant ρ is not evidence of absence of bias** — that is what §5's area-based grading is for.

**G8 — `IRRIGATED` is a hand-maintained set of one.** Adding a future irrigated product means knowing
to add it, or getting a zero-valid-pixel asset and having to diagnose why. The app exclusion is now
grade-driven, but the *onset* workaround is not.

## 7. What would close it, in order of value per unit of work

1. **Split the mask by technology (closes G2, mitigates G1 and G3).** Derive `frac_<crop>_irr` and
   `frac_<crop>_rain` by apportioning the 100 m crop-type mask with the SPAM `_I`/`_R` ratio, then run
   two products per exposed country-season. The rainfed product becomes valid everywhere; the irrigated
   one reports `deficit_mm` as requirement with no condition claim. Nine products need this; one is
   currently unusable without it.
2. **Re-fit Ym on the rainfed split only (closes G3).** Once rainfed area is separable, regress reported
   yield on rainfed CPI over rainfed area alone. Sudan sorghum's r = −0.33 is the test case: if the
   split is working, that correlation should turn positive.
3. ~~**Carry the exposure grade onto every asset and app panel.**~~ **Done, 26 September 2026** — see §4.
4. **Drive the onset workaround off the grade too (closes G8).** `IRRIGATED` should be derived from
   `irrigation_exposure.grade(...) == "INVALID as rainfed"` rather than hand-listed.
5. **Refresh the exposure layer (closes G4).** Re-run §2 against a post-2020 irrigated-extent source
   when one exists, and against any Sudan scheme-status assessment for 2024.
6. **Only then consider a supply term (G1).** A dekadal irrigation term is theoretically correct and
   least defensible in practice, because the applied-water data does not exist regionally. The split in
   step 1 gets most of the benefit without inventing a number.

---

### Reproducing this note

```bash
python crop_pipeline/irrigation/products.py               # the 41-product inventory, from disk
python crop_pipeline/irrigation/spam_irrigated_share.py   # → spam2020_irrigated_share.csv     (§2)
python crop_pipeline/irrigation/spam_irrigated_admin1.py  # → spam2020_irrigated_admin1.csv    (§2)
python crop_pipeline/irrigation/cpi_vs_irrigation.py      # → cpi_vs_irrigation.csv            (§3)
python crop_pipeline/irrigation/product_exposure.py       # → product_irrigation_exposure.csv  (§5)
python irrigation_exposure.py                             # the lookup the assets and apps use
python tag_assets_irrigation.py --apply                   # stamp the exported EE assets        (§4)
```

Inputs: SPAM 2020 V2r2 physical-area GeoTIFFs (`/tmp/spam20/geotiff_physical/`), GADM 4.1
(`~/ICPAC-WORK/ADMIN-boundaries/`), and the pipeline's own `*_L1_skill_WKT.csv` admin-1 outputs.

**Related:** `CPI_METHODOLOGY.md` §3.1 and §6 · `ALL_COUNTRIES_2024.md` §6 and §7 ·
`sorghum_pipeline/docs/METHODOLOGY.md` · `config/crop_coefficients.yaml`.
