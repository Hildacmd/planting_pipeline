# Planting-Date Validation — Kenya 2024 (MAM & OND)

Validates the pipeline's estimated planting dekad against **farmer-reported planting dates**, per county,
for the 2024 Long rains (MAM) and Short rains (OND). Dekad = 10-day period of the year (1–36); ±1 dekad ≈ 10 days.

## 1. Data
- **MAM (Long rains):** county-median farmer planting date, 2024, from the FarmerList survey
  (**~4.8 million farmers**, native county+ward fields). Source: `Planting_Dates_by_County_2023-2025.xlsx`.
- **OND (Short rains):** farmer-level planting survey, taken **2024-09-30**. Source: `OND Planting validation Report 2024.xlsx`.
- **Estimate:** the pipeline's modal (and mean) planting dekad per county — Long rains from cue-fusion
  green-up (`planting_Kenya_maize_Longrains_2024`), Short rains from rainfall onset
  (`planting_Kenya_maize_Shortrains_2024_rainfed`).

## 2. MAM (Long rains) — the method picks planting well ✅

![MAM validation](planting_validation_MAM_2024.png)

Against the ~4.8 M-farmer county medians (**42 / 44 counties matched**):

| Metric (estimated − observed) | Modal dekad | Mean dekad |
|---|---|---|
| **Bias** | **−0.31 dekad (≈ −3 days)** | −0.12 |
| **MAE** | **1.02 dekad (≈ 9 days)** | 0.89 |
| **RMSE** | 1.41 | 1.23 |
| **Within ±1 dekad** | 66.7 % | 64.3 % |
| **Within ±2 dekads** | **92.9 %** | 92.9 % |

**Read:** essentially **unbiased**, accurate to **~1 dekad**, with **93 % of counties within ±2 dekads**.
The low county-to-county correlation (r = 0.16) is **not a weakness** — MAM planting is highly
*synchronous* (almost every county plants late-March/early-April), so there is little spatial spread to
rank; the *absolute timing* is what matters and it is accurate. The few larger misses are **arid/marginal
counties** (Marsabit +3, Garissa +3, Tana River −3) where green-up is sparse and farmer samples are small.

### 2b. MAM at **ward level** — the accuracy holds at fine scale ✅
Against the ward-median farmer dates (**855 wards matched**):

| | Modal dekad | Mean dekad |
|---|---|---|
| Bias | **−0.44 dekad** | −0.20 |
| MAE | **1.10 dekad** | 0.90 |
| Within ±1 / ±2 dekads | 72 % / **96 %** | — / 94 % |

So the method is accurate not just at county level but down to **individual wards** (96 % within ±2 dekads
across 855 wards). Worst wards are again in arid counties (Garissa, Tana River).

## 3. OND / Short rains — three sources chased; still not cleanly validated ⚠️

**(a) OND validation survey 2024** — taken **2024-09-30, at the *start* of OND**, so **84 % of records are
pre-OND planting** (Aug–Sep). On the 16 % who planted Oct–Dec (9 counties ≥ 5 farmers), several match
exactly (Kakamega, Kisii, Kwale, Siaya = 0; Narok +1) but others run ~+4 dekads — too small/biased to conclude.

**(b) KIAMIS counties validation** — this survey is dated **2022-10-28 → OND 2022, not 2024**; out of scope.

**(c) Kakamega & Bungoma (409,306 maize farmers, GPS + ward)** — a rich 2024 dataset, but it reveals a
**seasonal-regime difference, not a timing error**: those western-Kenya farmers planted their maize in
**Aug–Sep (observed ward-median dekad 24–25)**, i.e. the **western bimodal *second season***, ~1 month
**earlier** than the **OND (Oct–Dec)** window the short-rains method targets. Our OND estimate for the same
wards is ~dekad 28 (Oct), a **+3-dekad gap** that reflects the two seasons being genuinely different. It
means the short-rains method is **OND-calibrated (Oct-onset)** and would need a **separate, earlier search
window** to capture the western Aug–Sep second season.

**Recommendation:** for a clean OND validation, use a **post-OND survey (Dec–Jan)**; and treat the
**western Aug–Sep second season as its own product** (earlier onset window) rather than folding it into OND.

## 4. In the app
The Explorer (`pw_app.html`) now carries two validation layers for the Long rains:
- **Observed planting — farmers (MAM)** — the ground-truth median dekad (county at L1/L2, ward at L3).
- **Planting error (estimated − observed)** — diverging map + the ranked-bar/histogram stats, so the
  county/ward-level agreement is visible directly (median 0 dekad, ±3 range, worst = Garissa).

## 5. Bottom line
- **Long rains (MAM): validated at county AND ward level** — unbiased, ~1-dekad accuracy, 93–96 % within
  ±2 dekads vs ~4.8 M farmers. The method picks MAM planting well.
- **Short rains (OND): not yet validated** — the 2024 OND survey predates OND planting; KIAMIS is 2022;
  the Kakamega/Bungoma data is the *western Aug–Sep season*, a different regime. A correctly-timed OND
  survey (Dec–Jan) is the missing piece, and the western second season should be handled separately.

*Tables: `planting_validation_MAM_2024.csv` (county), `/tmp/ward_mam.csv` (ward). Dekad: `N·Mon-dX`, e.g. dekad 9 = Mar-d3.*
