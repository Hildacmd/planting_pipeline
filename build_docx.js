const fs=require('fs');
const {Document,Packer,Paragraph,TextRun,HeadingLevel,Table,TableRow,TableCell,WidthType,
  BorderStyle,ShadingType,ImageRun,AlignmentType,PageBreak,ExternalHyperlink}=require('docx');

const GREEN="2f7d4f", AMBER="b0702a", INK="1b241e", SOFT="4c574f", LINE="dde1d8", CODEBG="eef0e9";
const SANS="Calibri", SERIF="Georgia", MONO="Consolas";
const PWIDTH=9026; // usable DXA width (A4 minus 1" margins)

const img=(file,w,h)=>new Paragraph({alignment:AlignmentType.CENTER,spacing:{before:120,after:60},
  children:[new ImageRun({type:"png",data:fs.readFileSync(file),transformation:{width:w,height:h}})]});
const cap=(t)=>new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:180},
  children:[new TextRun({text:t,italics:true,size:16,color:SOFT,font:SANS})]});
const body=(runs,opts={})=>new Paragraph({spacing:{after:120,line:276},...opts,
  children:Array.isArray(runs)?runs:[new TextRun({text:runs,size:22,font:SANS,color:INK})]});
const t=(s,o={})=>new TextRun({text:s,size:22,font:SANS,color:INK,...o});
const bullet=(runs)=>new Paragraph({bullet:{level:0},spacing:{after:60},
  children:Array.isArray(runs)?runs:[t(runs)]});
const h2=(n,txt)=>new Paragraph({heading:HeadingLevel.HEADING_1,spacing:{before:320,after:120},
  children:[new TextRun({text:n+"  ",font:MONO,size:20,color:GREEN,bold:true}),
            new TextRun({text:txt,font:SERIF,size:30,bold:true,color:INK})]});
const h3=(txt,tag)=>new Paragraph({heading:HeadingLevel.HEADING_2,spacing:{before:220,after:80},
  children:[new TextRun({text:txt,font:SANS,size:24,bold:true,color:INK}),
    ...(tag?[new TextRun({text:"   "+tag,font:MONO,size:18,color:AMBER})]:[])]});
const code=(lines)=>new Paragraph({spacing:{before:120,after:120},shading:{type:ShadingType.CLEAR,fill:CODEBG},
  border:{left:{style:BorderStyle.SINGLE,size:18,color:AMBER,space:8}},
  children:lines.flatMap((l,i)=>[...(i?[new TextRun({break:1})]:[]),new TextRun({text:l,font:MONO,size:18,color:INK})])});

function cell(txt,w,{head=false,bold=false}={}){
  const runs=Array.isArray(txt)?txt:[new TextRun({text:txt,size:head?16:18,font:head?MONO:SANS,
    bold:head||bold,color:head?SOFT:INK})];
  return new TableCell({width:{size:w,type:WidthType.DXA},margins:{top:60,bottom:60,left:100,right:100},
    shading:head?{type:ShadingType.CLEAR,fill:CODEBG}:undefined,
    children:[new Paragraph({children:runs})]});
}
function table(cols,rows){
  const widths=cols.map(c=>c.w);
  const header=new TableRow({tableHeader:true,children:cols.map(c=>cell(c.t,c.w,{head:true}))});
  const trs=rows.map(r=>new TableRow({children:r.map((v,i)=>cell(v,widths[i]))}));
  return new Table({width:{size:PWIDTH,type:WidthType.DXA},columnWidths:widths,
    borders:{top:{style:BorderStyle.SINGLE,size:4,color:LINE},bottom:{style:BorderStyle.SINGLE,size:4,color:LINE},
      left:{style:BorderStyle.NONE},right:{style:BorderStyle.NONE},
      insideHorizontal:{style:BorderStyle.SINGLE,size:2,color:LINE},insideVertical:{style:BorderStyle.NONE}},
    rows:[header,...trs]});
}
const ref=(n,a,rest)=>new Paragraph({spacing:{after:80},indent:{left:400,hanging:400},
  children:[new TextRun({text:"["+n+"]  ",font:MONO,size:16,color:GREEN}),
            new TextRun({text:a+" ",size:18,bold:true,color:INK,font:SANS}),
            new TextRun({text:rest,size:18,color:SOFT,font:SANS})]});
const refhead=(x)=>new Paragraph({spacing:{before:160,after:60},
  children:[new TextRun({text:x,font:SANS,size:20,bold:true,color:GREEN})]});

const children=[
  new Paragraph({spacing:{after:80},children:[new TextRun({text:"TOMORROWNOW / ICPAC · AGROMET PIPELINE · TECHNICAL WORKFLOW",font:MONO,size:16,color:GREEN})]}),
  new Paragraph({spacing:{after:120},children:[new TextRun({text:"Crop-Specific Dekadal Planting-Window Estimation",font:SERIF,size:48,bold:true,color:INK})]}),
  body([t("Per-pixel planting dekad for maize, teff and wheat across the Greater Horn of Africa — fusing Sentinel-2 red-edge phenology, Sentinel-1 SAR and FPAR, constrained by long-term climatology, cross-checked against a FEWS rainfall onset, and closed with a full FAO-56 water balance.",{color:SOFT})]),
  body([t("Engine: ",{bold:true}),t("Google Earth Engine + local Python    "),t("Reference run: ",{bold:true}),t("Kenya maize 2024    "),t("Time step: ",{bold:true}),t("dekad (10 days, 1–36/yr)")]),
  new Paragraph({border:{bottom:{style:BorderStyle.SINGLE,size:12,color:INK,space:8}},children:[]}),

  h2("01","Purpose"),
  body("Estimate the per-pixel planting dekad (1–36 in a year) for maize, teff and wheat inside crop-specific masks, by fusing Sentinel-2 red-edge phenology + FPAR + Sentinel-1 SAR, constraining the search with long-term-normal (LTN) climatology, cross-checking against a FEWS-style rainfall onset, running a full FAO-56/33 WRSI water balance, and aggregating to administrative units and agro-ecological zones (AEZ)."),
  body("A dekad is the atomic time step: d1 = days 1–10, d2 = 11–20, d3 = 21–end-of-month; 36 dekads per year. Dekad labels are shown as N · Mon-dN (e.g. 9 · Mar-d3)."),

  h2("02","High-level architecture"),
  img("wf_diagrams/fig1_arch.png",600,359), cap("Fig 1 — End-to-end data flow: inputs → fusion → LTN-gated SOS → planting → WRSI → aggregation."),

  h2("03","Data inputs"),
  table([{t:"Layer",w:1500},{t:"Dataset",w:3100},{t:"Res",w:900},{t:"Role",w:2826},{t:"Ref",w:700}],[
    ["Optical red-edge","COPERNICUS/S2_SR_HARMONIZED","10–20 m","NDRE onset signal","[2][4]"],
    ["Cloud mask","GOOGLE/CLOUD_SCORE_PLUS","10 m","clear-pixel gate","—"],
    ["SAR","COPERNICUS/S1_GRD","10 m","cloud-proof gap-fill","[3]"],
    ["FPAR","MODIS/061/MCD15A3H","500 m","greenness fusion","[12]"],
    ["Phenology LTN","MODIS/061/MCD12Q2","500 m","SOS prior (~24 yr)","—"],
    ["Rainfall","UCSB-CHG/CHIRPS/DAILY","~5.5 km","onset + WRSI","[8]"],
    ["Temperature","ECMWF/ERA5_LAND","~11 km","ET0 + thermal offset","[11]"],
    ["Soil water","OpenLandMap 33 kPa","250 m","WHC for WRSI","—"],
    ["Crop mask","ESA/WorldCereal/2021","10 m","crop-specific stratum","[1]"],
    ["Forecast (opt.)","Open-Meteo / NOAA GFS0P25","~1–28 km","4-day forecast rain","—"],
    ["AEZ","Jaetzold/Sombroek (local)","vector","maturity zonation","[17]"],
  ]),

  h2("04","Workflow stages"),
  h3("4.1 Optical & SAR preprocessing","s2_preprocess.py · s1_preprocess.py"),
  body("Per dekad, a cloud-masked median composite of red-edge indices — NDRE1 = (B6 − B5)/(B6 + B5), chlorophyll-sensitive and less soil-noisy than NDVI on sparse early canopy. Sentinel-1 gives RVI = 4·VH/(VV+VH) in terrain-flattened dB with a speckle filter. SAR is mandatory: rainy-season onset coincides with peak cloud, so S1 carries the signal."),
  h3("4.2 Fusion — gap-free greenness","fusion_phenometrics.py · estarfm.py"),
  code(["opt_G = mean( unitScale(NDRE), unitScale(FPAR) )","G     = opt_G  filled by SAR-derived greenness (RVI) where optical is missing"]),
  body("An enhanced path — ubESTARFM — blends fine/sparse Sentinel-2 with coarse/dense MODIS into a gap-free 10 m dekadal series:"),
  img("wf_diagrams/fig2_estarfm.png",600,86), cap("Fig 2 — ubESTARFM spatiotemporal fusion (compute-heavy; paid/tiled GEE)."),
  h3("4.3 Long-Term-Normal priors — rainfall-led, greenness-confirmed","ltn.py"),
  img("wf_diagrams/fig3_ltn.png",600,309), cap("Fig 3 — Rainfall onset up front (anchor), greenness confirms — one logic for both seasons."),
  body("The start of season is anchored by rainfall (the dense CHIRPS 25/20 mm onset normal, present every season) and confirmed by greenness (the MODIS greenup normal, averaged in only where present). The gate constrains SOS to ± ltn_pad dekads only where a prior exists — elsewhere it passes through to the calendar window, so a sparse second-cycle phenology can never mask a season out. The temperature LTN makes the emergence offset spatial."),
  body([t("Season behaviour (measured): ",{bold:true}),t("where both signals are strong (long rains) the prior adds +4.5 pts calendar hit-rate. Where the signal is weak (short rains: sparse Greenup_2, noisy onset) the rainfall-led prior keeps the season running (78% of pixels vs 0.02% under a naïve phenology gate) but does not sharpen it — the short rains are confirmation-limited, an honest data limitation.")]),
  h3("4.4 SOS detection & planting date","fusion_phenometrics.py · planting_date.py"),
  body([t("SOS",{bold:true}),t(" = the earliest dekad where G crosses baseline + 25%·amplitude and the dekad-to-dekad slope is positive (sustained green-up), within the calendar window intersected with the LTN prior. The crop mask is applied once, at the SOS output.")]),
  code(["planting_dekad = SOS_dekad − emergence_offset      # maize 2, wheat 1, teff 1 (dekads)"]),
  body("The offset is the planting → detectable green-up lag (satellite, ~2 dekads for maize), not the ~7-day physical emergence — a 10-day dekad cannot resolve 7 days."),
  h3("4.5 FEWS rainfall onset","wrsi_feedback.py"),
  img("wf_diagrams/fig4_onset.png",460,607), cap("Fig 4 — FEWS onset: 25/20 mm rule + P/PET≥0.5 gate, with optional 6-obs/4-forecast dekad."),
  body("The 25/20 mm rule (Senay & Verdin 2003) plus a new P/PET ≥ 0.5 agroclimatic gate that suppresses spurious onsets in high-evaporative-demand zones. The 6-obs + 4-forecast dekad (Open-Meteo, free) completes the running dekad for near-real-time timeliness; retrospective runs use full observed CHIRPS."),
  h3("4.6 WRSI water balance","wrsi_waterbalance.py · soil.py"),
  code(["ET0  = Hargreaves(ERA5-Land Tmin/Tmax, Ra(lat, DOY))","WR   = Kc(days-since-planting) · ET0","Wb   = SW + P ;  AET = min(Wb, WR) ;  SW = min(Wb − AET, WHC)","WRSI = 100 · sum(AET) / sum(WR)     # + deficit (mm) + FEWS class 1–5"]),
  body("Full FAO-56/33 dekadal balance, started at each pixel's detected planting dekad. Spatial WHC from OpenLandMap field capacity − wilting point over the crop root zone."),
  table([{t:"WRSI",w:1400},{t:"Class",w:1200},{t:"Interpretation for maize",w:6426}],[
    ["≥ 95","5","No/very-mild deficit — optimal"],
    ["80–95","4","Good — minimal yield reduction"],
    ["60–80","3","Mediocre"],["50–60","2","Poor"],["< 50","1","Crop failure"]]),
  body([t("\"Good enough\" for maize = WRSI ≥ 80",{bold:true}),t(" (≥ 95 = no stress; < 50 = failure). WRSI is a whole-cycle verdict; at the START of season, water adequacy is the onset rule (25/20 mm + P/PET ≥ 0.5), not WRSI. A QGIS style (wrsi_classes_*.qml) ships these class breaks.")]),
  body([t("AEZ × WRSI cross-validation: ",{bold:true}),t("water satisfaction rises with maturity class exactly as agronomy predicts — early (dry lowland) WRSI 90.0 / 4.2% failure, medium 93.8 / 0.8%, late (humid highland) 97.1 / 0% — independently confirming the AEZ → maturity logic through the water balance.")]),
  h3("4.7 Zonal aggregation & AEZ maturity","zonal_aggregate.py · aez_analysis.py"),
  img("wf_diagrams/fig5_aez.png",600,169), cap("Fig 5 — AEZ (LGP + thermal belt) → indicative maize maturity class."),
  body([t("Key finding (Kenya maize, Long rains 2024): ",{bold:true}),t("planting timing is nearly uniform across AEZ (~dekad 9, Mar-d3); the maturity class is what varies by zone. The planting-dekad map shows timing; the AEZ map shows maturity — largely decoupled. For a multi-country rollout the maturity class is derived from Length-of-Growing-Period (CHIRPS P/PET) + thermal belt (DEM/ERA5), a country-agnostic replacement for national AEZ codes.")]),

  h2("05","Enhancements added"),
  table([{t:"Enhancement",w:3200},{t:"Files",w:2800},{t:"Effect",w:3026}],[
    ["Bug fixes (2-band mask, band-type homogeneity)","run.py, fusion_phenometrics.py","pipeline runs to completion"],
    ["LTN prior — unified rainfall-led (phenology-confirmed) + temperature offset","ltn.py","+4.5 pts long-rains hit-rate; short rains kept running but confirmation-limited"],
    ["P/PET ≥ 0.5 onset gate","wrsi_feedback.py","agroclimatic onset; fewer false starts in dry zones"],
    ["6-obs + 4-forecast dekad","openmeteo_forecast.py, export_chirps6.py","near-real-time onset timeliness"],
    ["ubESTARFM fusion","estarfm.py","gap-free 10 m greenness"],
    ["Statistics + skill","skill_stats.py, skill_across_outputs.py","descriptive + validation + signal-strength + WRSI stats"],
    ["AEZ maturity + influence","aez_analysis.py, aez_influence.py","maize variety-class zonation"],
    ["WKT attribute tables","build_wkt_table.py, attributes_table.py","QGIS-ready CSVs with geometry + all attributes"],
    ["Local rendering + notebook + GEE demo","render_maps_pdf.py, *.ipynb, *.js","reproducible, observable runs"],
  ]),

  h2("06","Outputs"),
  bullet([t("Rasters (GeoTIFF): ",{bold:true}),t("planting dekad; WRSI + deficit + performance class.")]),
  bullet([t("Tables (CSV / CSV-with-WKT): ",{bold:true}),t("admin-1/2/3 planting distribution + skill; AEZ maturity; per-admin attribute table (NDRE / S1 / S2 / FPAR + LTN normals + SOS/planting). Raster CSV-with-WKT exported as pixel polygons for a clean QGIS load, plus admin/AEZ polygons.")]),
  bullet([t("Cartography (PDF/PNG): ",{bold:true}),t("planting-dekad maps, WRSI maps + GADM-1/2/3 choropleths, modal-dekad & hit-rate choropleths, skill graphs, AEZ-influence figure, agro-climatological calendar (precip/temp/greenness LTN + crop stages). Dekad labels as N-Mon (e.g. 9-Mar).")]),

  h2("07","Key design decisions"),
  bullet([t("Rainfall up front, greenness confirms",{bold:true}),t(" — the dense CHIRPS onset is the season-agnostic anchor; the satellite green-up confirms and sharpens it. One logic fits both long and short rains without masking.")]),
  bullet([t("SOS ≠ planting",{bold:true}),t(" — planting precedes detectable green-up by a crop-specific satellite lag.")]),
  bullet([t("Red-edge (NDRE) over NDVI",{bold:true}),t(" — chlorophyll-sensitive, less soil noise on sparse early canopy.")]),
  bullet([t("SAR is mandatory",{bold:true}),t(" — rainy-season onset = peak cloud; S1 carries the signal.")]),
  bullet([t("LTN prior gates the search",{bold:true}),t(" — rejects weeds / second-flush false starts.")]),
  bullet([t("WRSI runs entirely in GEE",{bold:true}),t(" — no GeoWRSI hand-off; planting dekad feeds the balance as SOS.")]),

  h2("08","Caveats"),
  bullet("Calendar windows in season_calendar.csv are indicative — calibrate against FEWS NET / FAO GIEWS / GEOGLAM."),
  bullet("Smallholder mixed pixels blur SOS; consider ubESTARFM or Planet 3 m in fragmented zones."),
  bullet("AEZ maturity mapping is a first-order Jaetzold convention — calibrate against Kenya Seed variety zonation. The Kenya AEZ codes do NOT transfer to other countries; for the 10-country rollout the maturity class is derived from LGP (CHIRPS P/PET) + thermal belt (DEM/ERA5), a country-agnostic engine."),
  bullet("Second/short rains are confirmation-limited: MODIS Greenup_2 is sparse and the onset is noisy, so the LTN prior keeps the season running (rainfall-led) but cannot sharpen it. Treat short-rains planting dates as indicative; lean on the rainfall onset."),
  bullet("Ward-level (admin-3) stats from downsampled mosaics are approximate; use native-resolution zonal stats for publication."),
  bullet("ubESTARFM and full LTN + WRSI at 10 m are compute-heavy — run on a paid/commercial GEE project; the CHIRPS-onset LTN defaults to a recent ~10-yr window."),

  h2("09","References"),
  refhead("SOS · SAR–optical fusion"),
  ref(1,"Van Tricht, K. et al. (2023).","WorldCereal. Earth Syst. Sci. Data 15, 5491–5515. doi:10.5194/essd-15-5491-2023"),
  ref(2,"Eisfelder, C. et al. (2024).","Cropland & Crop Type with S1/S2 in GEE, Ethiopia. Remote Sensing 16(5):866. doi:10.3390/rs16050866"),
  ref(3,"(2025).","S1 SAR annual rice area & long-term SOS dynamics. Sci. Reports. doi:10.1038/s41598-025-91655-z"),
  ref(4,"Vrieling, A. et al. (2019).","S1 & S2 time series for meadow phenology. Remote Sensing 11(5):542. doi:10.3390/rs11050542"),
  ref(5,"(2026).","PlanetScope + S2 fusion for maize phenometrics. GIScience & Remote Sensing. doi:10.1080/15481603.2026.2637207"),
  refhead("WRSI · water balance · onset"),
  ref(6,"Verdin, J. & Klaver, R. (2002).","Grid-cell crop water accounting for FEWS. Hydrol. Processes 16, 1617–1630. doi:10.1002/hyp.1025"),
  ref(7,"Senay, G.B. & Verdin, J. (2003).","GIS crop water balance, Ethiopia. Can. J. Remote Sensing 29(6), 687–692. doi:10.5589/m03-039"),
  ref(8,"Funk, C. et al. (2015).","CHIRPS. Scientific Data 2:150066. doi:10.1038/sdata.2015.66"),
  ref(9,"Allen, R.G. et al. (1998).","FAO-56 Crop evapotranspiration. FAO Irrigation & Drainage Paper 56."),
  ref(10,"Hargreaves, G.H. & Samani, Z.A. (1985).","Reference ET from temperature. Appl. Eng. Agric. 1(2), 96–99. doi:10.13031/2013.26773"),
  ref(11,"Muñoz-Sabater, J. et al. (2021).","ERA5-Land. Earth Syst. Sci. Data 13, 4349–4383. doi:10.5194/essd-13-4349-2021"),
  refhead("FPAR · phenology · monitoring · fusion"),
  ref(12,"Myneni, R. et al.","MODIS MCD15A3H FPAR/LAI C6.1. NASA LP DAAC. doi:10.5067/MODIS/MCD15A3H.061"),
  ref(13,"Becker-Reshef, I. et al. (2020).","GEOGLAM Crop Monitor for Early Warning. RSE 237:111553. doi:10.1016/j.rse.2019.111553"),
  ref(14,"Lee, D. et al. (2025).","HarvestStat Africa. Scientific Data. doi:10.1038/s41597-025-05001-z"),
  ref(15,"FEWS NET","crop calendars & data portal. fews.net/data"),
  ref(16,"FAO GIEWS","Country Briefs. fao.org/giews"),
  ref(17,"Jaetzold, R. & Schmidt, H.","Farm Management Handbook of Kenya (agro-ecological zones). Ministry of Agriculture, Kenya."),
  ref(18,"Zhu, X. et al. (2010).","ESTARFM — enhanced spatial and temporal adaptive reflectance fusion. RSE 114(11), 2610–2623. doi:10.1016/j.rse.2010.05.032"),
];

const doc=new Document({
  styles:{paragraphStyles:[
    {id:"Heading1",name:"Heading 1",basedOn:"Normal",next:"Normal",quickFormat:true,run:{size:30}},
    {id:"Heading2",name:"Heading 2",basedOn:"Normal",next:"Normal",quickFormat:true,run:{size:24}},
  ]},
  sections:[{properties:{page:{margin:{top:1440,bottom:1440,left:1440,right:1440}}},children}]
});
Packer.toBuffer(doc).then(b=>{fs.writeFileSync("Planting_Pipeline_Workflow.docx",b);
  console.log("wrote Planting_Pipeline_Workflow.docx",b.length,"bytes");});
