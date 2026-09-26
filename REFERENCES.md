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
- Shojaeezadeh, S.A., Elnashar, A. & Weber, T.K.D. (2025). *A novel fusion of Sentinel-1 and
  Sentinel-2 with climate data for crop phenology estimation using machine learning.* Science of
  Remote Sensing 11:100227. https://doi.org/10.1016/j.srs.2025.100227
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
- Nakalembe, C., Becker-Reshef, I., Bonifacio, R. et al. (2021). *A review of satellite-based
  global agricultural monitoring systems available for Africa.* Global Food Security 29:100543.
  https://doi.org/10.1016/j.gfs.2021.100543
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

**Verification status (checked 26 September 2026, `verify_dois.py`).** All **42 DOIs in this file
resolve, and each resolved record's title matches the citation here** — checked by DOI content
negotiation against Crossref/DataCite, not by eye. Re-run with `python verify_dois.py`; results in
`doi_verification.csv`.

Two entries that were previously anonymous placeholders ("(2025) *A novel fusion…*", "(2021)
*A review…*") have been completed with their authors and DOIs, and DOIs were added for Running et
al. (2004) and Ritchie & NeSmith (1991).

**What is still unverified**, and it is not the DOIs: 11 entries are books, monographs, agency
reports and one 2005 journal article with no DOI to check — Stone (1974), Efron & Tibshirani (1993),
FAO (1978), Jones & Kiniry (1986), Kiniry & Bonhomme (1991), Jaetzold et al. (2006–2012), Hassan
(1998), De Groote et al. (2005) and similar. These were confirmed against a Crossref search where a
record exists; De Groote et al. (2005, eJADE) returned only a different 2023 paper by the same
author, so **check that one against a library before citing it**. Live URLs resolve except three
that return 403 to automated requests (ScienceDirect, mapspam.info) and two agency APIs — all
reachable in a browser.

## Productivity / biomass-based yield (DMP, added 2026-09)
- Monteith, J.L. (1972). *Solar radiation and productivity in tropical ecosystems.* Journal of
  Applied Ecology 9(3), 747–766. https://doi.org/10.2307/2401901  — light-use-efficiency basis of DMP.
- Running, S.W., Nemani, R.R., Heinsch, F.A. et al. (2004). *A continuous satellite-derived measure
  of global terrestrial primary production.* BioScience 54(6), 547–560.
  https://doi.org/10.1641/0006-3568(2004)054[0547:ACSMOG]2.0.CO;2 — MOD17 GPP/NPP algorithm (the
  MODIS stand-in for CGLS DMP).
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
- Ritchie, J.T. & NeSmith, D.S. (1991). *Temperature and crop development.* In: Modeling Plant and
  Soil Systems, Agronomy Monograph 31, ASA-CSSA-SSSA, 5–29.
  https://doi.org/10.2134/agronmonogr31.c2
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
