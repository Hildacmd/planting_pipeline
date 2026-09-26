# The water balance is rainfed. Where crops are irrigated, this is what it means.

**Scope:** all 44 products across the five crops (maize, sorghum, wheat, teff, millet) and eleven
countries currently in the pipeline. **Status:** 2 products must not be read as crop condition, 7
more carry a material bias, 2 a local one, and 33 are unaffected.

Everything below is computed, not asserted. The three scripts in `crop_pipeline/irrigation/`
regenerate every number in this note, and the CSVs they write are the tables.

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

The supply term is `SW + P`. `P` is CHIRPS rainfall. **There is no irrigation term, and there is no
groundwater, capillary-rise or river-diversion term.** The initial condition makes this stricter
still: `init_soil_water_frac: 0.0` (`config/crop_coefficients.yaml:16`) — a dry start at onset, the
WRSI convention. So the balance answers exactly one question: *could rainfall alone have met this
crop's demand?*

For a rainfed crop that is water stress, and the chain that follows is valid:

```
S_water = 100 · (1 − ΣAET/ΣWR) per stage → CPI = 100(1−Sw)(1−Sh)(1−Sv) → Ya = CPI/100 · Ym
```

For an irrigated crop every link in that chain is wrong, and wrong in one direction. The scheme
met the shortfall; the balance did not know; so `S_water` is high, `CPI` is low and `Ya` is low.
**The deficit is real — but it is the irrigation requirement, not crop stress.** Those are different
quantities with different units of meaning, and the pipeline currently reports the first under the
name of the second.

## 2. How much of each crop is actually irrigated

SPAM 2020 publishes physical area per crop under `_I` (irrigated) and `_A` (all technologies), so
the irrigated share is `I / A` summed inside a boundary. `spam_irrigated_share.py` does this per
country (GADM 4.1 ADM_0); `spam_irrigated_admin1.py` repeats it at ADM_1.

Irrigated share of physical area, % — **SPAM 2020**:

| country | maize | sorghum | wheat | millet | teff\* |
|---|---|---|---|---|---|
| **Sudan** | **49.2** | 4.4 | **98.4** | 0.4 | – |
| **Somalia** | **24.8** | **12.0** | – | – | – |
| South Sudan | 0.5 | 4.4 | – | 0.4 | – |
| Ethiopia | 2.1 | 1.1 | 0.4 | – | 0.4 |
| Tanzania | 1.3 | 0.0 | 0.0 | – | – |
| Kenya | 0.3 | 0.2 | 0.0 | – | – |
| Uganda | 0.2 | 0.0 | – | – | – |
| Rwanda · Burundi · Eritrea · Djibouti | 0.0 | 0.0 | 0.0 | 0.0 | – |

\*SPAM has no teff class; the crop-type mask carries teff on *other cereals* (OCER) and this share
uses the same proxy. Treat it as indicative only.

The national figure understates the problem, because irrigation is not spread evenly — it sits on
schemes. At ADM_1 (`spam2020_irrigated_admin1.csv`):

| country · crop | most-irrigated admin-1 units |
|---|---|
| Sudan wheat | Kassala **100 %**, Khartoum 100 %, River Nile 100 %, White Nile 100 %, Al Jazirah **99.7 %**, Al Qadarif 99.7 %, Sennar 95.3 % |
| Sudan maize | Khartoum **100 %**, Red Sea 100 %, Al Jazirah **99.5 %**, Kassala 99.1 %, White Nile 70.3 %, Sennar 58.4 % |
| Sudan sorghum | Kassala 50.6 %, Sennar 46.3 %, White Nile 40.1 %, Al Jazirah 31.0 % — but Al Qadarif, the 3.3 M ha bulk, is 0.4 % |
| Somalia sorghum | Jubbada Hoose **84.2 %**, Shabeellaha Dhexe 76.5 %, Shabeellaha Hoose 28.6 % |
| Somalia maize | Shabeellaha Dhexe 46.2 %, Jubbada Hoose 33.6 %, Shabeellaha Hoose 28.9 % |
| Ethiopia maize | Afar **96.8 %**, Dire Dawa 48.2 % — but only 1,707 ha and 288 ha respectively |
| South Sudan sorghum | West Equatoria 13.7 %, West Bahr-al-Ghazal 11.4 %, Jungoli 8.7 % |

## 3. The bias is not hypothetical — it is measurable in shipped output

`cpi_vs_irrigation.py` joins the pipeline's own admin-1 CPI to the SPAM irrigated share and takes
Spearman ρ. If the units SPAM calls irrigated are the units the pipeline calls failing, ρ is
negative.

| product | n | ρ(CPI, irr %) | p | ρ(WRSI, irr %) |
|---|---|---|---|---|
| **Sudan maize Kharif** | 15 | **−0.717** | **0.003** | **−0.712** |
| Sudan sorghum Kharif | 18 | −0.170 | 0.501 | −0.201 |
| Sudan wheat Shitwi | 6 | *n/a* — CPI is 0 in all 6 | | |
| Somalia maize Deyr | 5 | *n/a* — CPI is 0 in all 5 | | **−1.000** |
| Somalia maize Gu | 5 | +0.103 | 0.870 | 0.000 |
| Somalia sorghum Gu | 8 | +0.262 | 0.531 | −0.381 |
| Somalia sorghum Deyr | 8 | −0.189 | 0.654 | +0.013 |
| South Sudan sorghum Main | 10 | −0.267 | 0.455 | +0.134 |

**Sudan maize Kharif 2024 is demonstrably inverted** (ρ = −0.717, p = 0.003). Read the product
against the irrigated share and the failure is plain:

| admin-1 | irrigated % | CPI | mean WRSI | S_water | yield t/ha |
|---|---|---|---|---|---|
| Khartoum | 100.0 | **10** | 43.7 | 78 | **0.23** |
| Red Sea | 100.0 | **10.5** | 49.6 | 76 | 0.21 |
| **Al Jazirah** (Gezira) | 99.5 | **37** | 65.2 | 55 | 0.68 |
| White Nile | 70.3 | 39 | 67.3 | 55 | 0.74 |
| Sennar | 58.4 | 77 | 98.2 | 0 | 1.52 |
| Al Qadarif | 24.0 | 34 | 77.1 | 47 | 0.75 |
| Blue Nile | 0.0 | 82 | 99.3 | 0 | 1.62 |
| Central Darfur | 0.0 | 87 | 99.5 | 0 | 1.71 |
| South Darfur | 0.0 | 83 | 97.6 | 2.1 | 1.66 |
| *(7 more, all 0 % irrigated)* | 0.0 | 53–72 | 80–94 | 17–43 | 1.07–1.47 |

The pipeline reports **Khartoum maize — grown entirely under Nile irrigation — at 0.23 t/ha**, and
the Gezira scheme at less than half the condition of rainfed Darfur. That is the balance correctly
reporting that Khartoum received no rain, and the product incorrectly labelling it crop failure.
Sennar (58 % irrigated, CPI 77) is the honest exception: it had rain as well.

**Somalia maize Deyr 2024** is the degenerate case — CPI 0 in all five riverine regions, so ρ on CPI
is undefined; WRSI declines monotonically with irrigated share (ρ = −1.000, n = 5, too few units to
be conclusive on its own but consistent in sign with Sudan).

**Sudan sorghum is the counter-example, and it matters.** Four states are 31–51 % irrigated, yet
ρ = −0.17 (p = 0.50). Sudan's sorghum is overwhelmingly rainfed mechanised farming in Al Qadarif —
3.3 M ha at 0.4 % irrigated, against 0.5 M ha in the Gezira. National exposure of 4.4 % is carried
by a few states holding a small minority of the area. **Exposure flags a product for inspection; it
does not by itself demonstrate corruption.**

## 4. What the pipeline already does about it

One product is handled explicitly. `crop_pipeline/run_all_crop.py:52`:

```python
IRRIGATED = {("Sudan", "Shitwi")}
```

Sudan's Shitwi wheat is scheme-irrigated winter wheat on the Nile and the Gezira, sown in November
in the dry season. Two consequences, both already implemented:

1. **Onset cannot be detected.** The CHIRPS 25/20 mm FEWS rule needs 25 mm in a dekad and Sudan gets
   essentially none in November, so the rainfall onset returned nothing — the first run produced an
   asset with 10,478 wheat-mask pixels and **zero valid ones**. Green-up onset fares no better: it is
   gated to a rainfall-driven climatological onset that does not exist here. The workaround takes the
   planting dekad as the **start of the calendar's indicative window** (`Nov-d1`), fixed, because
   planting on a scheme is scheduled rather than rain-driven. It is an assumption about timing and it
   is recorded on the asset (`method = "fixed-irr"`).
2. **The product is excluded from the apps and the Atlas** (`app_data.py:124`, `:246`). With the
   fixed onset the run completes and returns WRSI 0, S_water 100 % and CPI 0 across all 18
   localities including the Gezira — arithmetically correct and agronomically meaningless. The asset
   and CSV are retained, because the deficit *is* the irrigation requirement.

The Atlas stress layer refuses to write without `mean_deficit_mm` rather than falling back to
`S_water` %, for the same reason: a legend committed to 0–200 mm showing a percentage would be
readable and wrong.

## 5. Per-product exposure

`product_exposure.py` grades all 44 calendar rows. Full table:
`crop_pipeline/irrigation/product_irrigation_exposure.csv`.

| grade | rule | n | products |
|---|---|---|---|
| **INVALID as rainfed** | national ≥ 40 % | **2** | Sudan wheat Shitwi (98.4 %), Sudan maize Kharif (49.2 %) |
| **materially biased** | national ≥ 10 % or any admin-1 ≥ 50 % | **7** | Somalia maize Gu & Deyr, Somalia sorghum Gu & Deyr, Sudan sorghum Kharif, Ethiopia maize Meher & Belg |
| **locally biased** | national ≥ 2 % or any admin-1 ≥ 20 % | **2** | South Sudan sorghum Main & 2nd |
| **negligible** | below both | **33** | all Kenya, Uganda, Rwanda, Burundi, Eritrea, Tanzania products; Ethiopia sorghum/wheat/teff; South Sudan maize; Sudan millet |

**How to read each grade.** *Invalid*: do not report CPI or yield; the deficit is the irrigation
requirement. *Materially biased*: report at admin-1, name the irrigated units, and do not rank them
against rainfed units in the same table. *Locally biased*: national aggregates are sound, individual
units may not be. *Negligible*: report as rainfed without caveat.

The good news is the shape of that table: **75 % of products are unaffected**, and the exposure is
concentrated in two countries. Every teff, millet and Kenyan/Tanzanian wheat product — the whole of
the newest crop set except Sudan wheat — is rainfed to within 0.4 %.

## 6. Gaps

**G1 — No irrigation supply term (structural, affects 11 products).** `Wb = SW + P` has no place to
credit applied water. This is the root cause of everything above. Closing it needs a supply term,
and the honest obstacle is that there is no GHA-wide dekadal dataset of *applied* irrigation — only
of irrigated *extent*. Any supply term would be an assumption dressed as data.

**G2 — The crop mask does not separate irrigated from rainfed area.** `ctm_mask.crop_mask` returns
one fraction per pixel for total physical area of the crop, mixing both technologies. So a pixel in
Al Jazirah is 99.5 % irrigated maize and the pipeline treats all of it as rainfed. SPAM's `_I` and
`_R` layers exist at 10 km and would support splitting the mask into two — this is the most tractable
fix and is the one I would do first (see §7).

**G3 — Ym calibration absorbs the bias where it is fitted, and fails where it is total.** Ceilings
are fitted by least squares through the origin of reported yield on CPI. Where CPI is biased low by
irrigation but reported yield includes irrigated production, the fit compensates by **inflating Ym** —
the level comes out roughly right while the spatial pattern stays inverted. Sudan sorghum Kharif is
the visible symptom: fitted Ym 0.83 t/ha with **r = −0.33** (`sorghum_params.py:74`), a negative
correlation shipped as a calibration. Where CPI is 0 the fit is impossible: **Sudan wheat has no
entry in `crop_pipeline/params/wheat.py` YM_CAL** and never can under a rainfed balance. Sudan maize
carries an assumed 2.0 t/ha (`crop_type_mask/atlas/build_risk_crop.py:39`), not a HarvestStat fit.

**G4 — SPAM 2020 is a 2020 snapshot, and both directions of drift matter.** Ethiopia's irrigated
wheat programme expanded substantially after 2020; SPAM's 0.4 % for Ethiopia wheat is therefore
likely an **understatement**, and Ethiopia wheat Meher may belong a grade higher than *negligible*.
In the other direction, Sudan's schemes have been disrupted since 2023, so the Gezira may have been
**less** irrigated in the 2024 season than SPAM says. Neither is quantified here, and neither should
be guessed at — the grades in §5 are as-of-2020 exposure, which is the right prior and not a
measurement of 2024.

**G5 — The deficit overstates the net irrigation requirement.** Reinterpreting `deficit_mm` as the
irrigation requirement is right in kind but not calibrated in amount: it starts from a dry profile
(`init_soil_water_frac = 0.0`), and it credits no application efficiency, no capillary rise from
shallow Nile-valley water tables, and no scheme scheduling. Treat it as an upper bound on net
requirement, not a scheme water order.

**G6 — Teff has no SPAM class.** Its exposure is inferred from *other cereals*. Ethiopian teff is
close to entirely rainfed, so the conclusion is almost certainly safe, but it rests on a proxy.

**G7 — Onset for any future irrigated product needs the same manual entry.** `IRRIGATED` is a
hand-maintained set of one. Adding an irrigated product means knowing to add it, or getting a
zero-valid-pixel asset and having to diagnose why.

## 7. What would close it, in order of value per unit of work

1. **Split the mask by technology (closes G2, mitigates G1 and G3).** Derive `frac_<crop>_irr` and
   `frac_<crop>_rain` by apportioning the 100 m crop-type mask with the SPAM `_I`/`_R` ratio, then
   run two products per exposed country-season. The rainfed product becomes valid everywhere, and the
   irrigated one reports `deficit_mm` as requirement with no condition claim. Eleven products need
   this; two of them are currently unusable without it.
2. **Re-fit Ym on the rainfed split only (closes G3).** Once the rainfed area is separable, regress
   reported yield on rainfed CPI over rainfed area alone. The Sudan sorghum r = −0.33 is the test
   case: if the split is doing its job, that correlation should turn positive.
3. **Carry the exposure grade onto every asset and every app panel.** A single asset property
   (`irrigation_exposure`) and one line of app note costs almost nothing and stops a reader taking
   Khartoum's 0.23 t/ha at face value. Do this even before 1 and 2.
4. **Refresh the exposure layer (closes G4).** Re-run §2 against a post-2020 irrigated-extent source
   when one is available, and against any Sudan scheme-status assessment for 2024.
5. **Only then consider a supply term (G1).** A dekadal irrigation term is the theoretically correct
   fix and the least defensible in practice, because the applied-water data does not exist regionally.
   The split in step 1 gets most of the benefit without inventing a number.

---

### Reproducing this note

```bash
python crop_pipeline/irrigation/spam_irrigated_share.py     # → spam2020_irrigated_share.csv        (§2)
python crop_pipeline/irrigation/spam_irrigated_admin1.py    # → spam2020_irrigated_admin1.csv       (§2)
python crop_pipeline/irrigation/cpi_vs_irrigation.py        # → cpi_vs_irrigation.csv               (§3)
python crop_pipeline/irrigation/product_exposure.py         # → product_irrigation_exposure.csv     (§5)
```

Inputs: SPAM 2020 V2r2 physical-area GeoTIFFs (`/tmp/spam20/geotiff_physical/`), GADM 4.1
(`~/ICPAC-WORK/ADMIN-boundaries/`), and the pipeline's own `*_L1_skill_WKT.csv` admin-1 outputs.

**Related:** `sorghum_pipeline/docs/METHODOLOGY.md` (water balance and FAO-33 Ky),
`crop_pipeline/README.md` (wheat/teff/millet parameters), `config/crop_coefficients.yaml`
(`init_soil_water_frac`, `whc_assets`).
