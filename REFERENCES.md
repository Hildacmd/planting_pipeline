# Supporting references (up to date)

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
