/**** Visualize the maize pipeline outputs in the GEE Code Editor ***************************
 * Paste into https://code.earthengine.google.com  (project: ee-manzikye).
 *
 * The pipeline exports GeoTIFFs to Drive; the Code Editor can only draw EE ASSETS, so first
 * ingest each product as an Image asset (see README note) and put its asset id below.
 * The WHC layer is already an asset and works as-is.
 *
 * Bands are renamed positionally on load, so it does not matter what band names the ingest
 * assigned (b1..bN or original) — only the export ORDER matters, which is fixed here.
 *******************************************************************************************/

// ---- 1. ASSET IDS — fill these in after ingesting the Drive GeoTIFFs -------------------
var P = 'projects/ee-manzikye/assets/';          // your asset folder
var ASSETS = {
  cpi_ke_long : P + 'cpi_Kenya_Longrains_2024',          // 11 bands (see CPI_MAIN)
  cpi_et_meher: P + 'cpi_Ethiopia_Meher_2024',           // 11 bands
  cpi_ke_short: P + 'cpi_Kenya_maize_Shortrains_2024',   //  5 bands (see CPI_SHORT)
  stage_short : P + 'stagemonitor_Kenya_maize_Shortrains_2024', // 6 bands (STAGE)
  whc         : P + 'whc_saxton_soilgrids_gha_250m',     //  1 band  — ALREADY an asset
  // excess / waterlogging diagnostics (onset false-start + aeration waterlogging + SPI-3 wet)
  oe_ke_long  : P + 'onsetexcess_Kenya_Longrains_2024',  //  4 bands (OE_MAIN)
  oe_et_meher : P + 'onsetexcess_Ethiopia_Meher_2024',   //  4 bands (OE_MAIN)
  oe_ke_short : P + 'onsetexcess_Kenya_Shortrains_2024', //  2 bands (OE_SHORT)
  // fused canopy condition (FCCI) — 1 band 0-100, peak fused greenness
  fcci_ke_long : P + 'fcci_Kenya_Longrains_2024',
  fcci_et_meher: P + 'fcci_Ethiopia_Meher_2024',
  fcci_ke_short: P + 'fcci_Kenya_Shortrains_2024'
};

// ---- 2. Band order as EXPORTED (do not reorder) ---------------------------------------
var CPI_MAIN  = ['wrsi_veg','wrsi_flo','wrsi_grf','wsi_veg','wsi_flo','wsi_grf',
                 'CPI','yield_tha_x100','S_water','S_heat','S_veg'];
var CPI_SHORT = ['CPI','yield_tha_x100','S_water','S_heat','S_veg'];
var STAGE     = ['wrsi_veg','wrsi_flo','wrsi_grf','wsi_veg','wsi_flo','wsi_grf'];
var OE_MAIN   = ['false_start','waterlog_idx','spi3_wet','onset_acc_mm'];
var OE_SHORT  = ['waterlog_idx','spi3_wet'];

// ---- 3. Palettes ----------------------------------------------------------------------
var RdYlGn = ['a50026','d73027','f46d43','fdae61','fee08b','ffffbf',
              'd9ef8b','a6d96a','66bd63','1a9850','006837'];     // low->high good
var STRESS = ['ffffff','fee5d9','fcae91','fb6a4a','de2d26','a50f15']; // 0->1 worse
var YIELD  = ['ffffcc','c2e699','78c679','31a354','006837'];     // t/ha
var WHCPAL = ['fff7fb','ece7f2','d0d1e6','a6bddb','74a9cf','3690c0','0570b0','045a8d','023858'];
var SPIPAL = ['8c510a','bf812d','dfc27d','f6e8c3','f5f5f5','c7eae5','80cdc1','35978f','01665e'];
var DEKAD  = ['440154','3b528b','21908d','5dc863','fde725'];     // planting dekad (viridis)

var VIS = {
  wrsi : {min:0,   max:100, palette:RdYlGn},   // WRSI 0-100 (<50 failure)
  cpi  : {min:0,   max:100, palette:RdYlGn},   // CPI  0-100
  yield: {min:0,   max:6,   palette:YIELD},    // t/ha
  wsi  : {min:0,   max:100, palette:STRESS},   // dekadal water stress (%)
  str  : {min:0,   max:60,  palette:STRESS},   // S_water/heat/veg (%, capped ~60)
  whc  : {min:25,  max:180, palette:WHCPAL},   // mm
  spi  : {min:-2,  max:2,   palette:SPIPAL},   // SPI-3
  dekad: {min:1,   max:36,  palette:DEKAD},
  wlog : {min:0,   max:40,  palette:WHCPAL},   // aeration waterlogging index (modelled, uncal.)
  wet  : {min:0,   max:1,   palette:WHCPAL},   // SPI-3 wet mask (0/1)
  fstart:{min:0,   max:1,   palette:STRESS},   // false-start 0/1
  fcci : {min:0,   max:100, palette:RdYlGn}    // fused canopy condition 0-100
};

// ---- 4. Loader: load asset, rename to schema, mask to the valid (maize) footprint ------
function load(id, names, primary) {
  var img = ee.Image(id).rename(names);
  var mask = img.select(primary).gt(0);        // primary band > 0 = valid maize pixel
  return img.updateMask(mask);
}

// ---- 5. Build the layer list ----------------------------------------------------------
// Each entry: [displayImage, visKey, 'label', shownByDefault]
var layers = [];
function push(im, vkey, label, shown){ layers.push({im:im, v:VIS[vkey], name:label, on:!!shown}); }

// -- main seasons (11-band CPI composites) --
[['cpi_ke_long','Kenya Long rains'], ['cpi_et_meher','Ethiopia Meher']].forEach(function(s){
  var id = ASSETS[s[0]]; if(!id) return;
  var im = load(id, CPI_MAIN, 'CPI');
  push(im.select('CPI'),                    'cpi',  s[1]+' · CPI',            s[0]==='cpi_ke_long');
  push(im.select('yield_tha_x100').divide(100),'yield',s[1]+' · Yield t/ha', false);
  push(im.select('wrsi_flo'),               'wrsi', s[1]+' · WRSI @flowering', false);
  push(im.select('wrsi_grf'),               'wrsi', s[1]+' · WRSI @maturity',  false);
  push(im.select('S_water'),                'str',  s[1]+' · S_water %',        false);
  push(im.select('S_heat'),                 'str',  s[1]+' · S_heat %',         false);
  push(im.select('S_veg'),                  'str',  s[1]+' · S_veg %',          false);
});

// -- short rains CPI (5-band) --
if (ASSETS.cpi_ke_short){
  var sh = load(ASSETS.cpi_ke_short, CPI_SHORT, 'CPI');
  push(sh.select('CPI'),                     'cpi',  'Kenya Short rains · CPI',       false);
  push(sh.select('yield_tha_x100').divide(100),'yield','Kenya Short rains · Yield t/ha',false);
  push(sh.select('S_water'),                 'str',  'Kenya Short rains · S_water %',  false);
}

// -- short rains stage monitor (6-band) --
if (ASSETS.stage_short){
  var stg = load(ASSETS.stage_short, STAGE, 'wrsi_veg');
  push(stg.select('wrsi_veg'), 'wrsi', 'Short rains · WRSI @vegetative', false);
  push(stg.select('wrsi_flo'), 'wrsi', 'Short rains · WRSI @flowering',  false);
  push(stg.select('wrsi_grf'), 'wrsi', 'Short rains · WRSI @grain-fill', false);
  push(stg.select('wsi_flo'),  'wsi',  'Short rains · WSI @flowering',   false);
}

// -- excess / waterlogging diagnostics (onset false-start + aeration + SPI-3 wet) --
[['oe_ke_long','Kenya Long rains',OE_MAIN], ['oe_et_meher','Ethiopia Meher',OE_MAIN],
 ['oe_ke_short','Kenya Short rains',OE_SHORT]].forEach(function(s){
  var id = ASSETS[s[0]]; if(!id) return;
  var im = ee.Image(id).rename(s[2]), foot = im.select('waterlog_idx').gte(0);   // any valid pixel
  push(im.select('waterlog_idx').updateMask(foot), 'wlog', s[1]+' · Soil waterlogging (modelled)', false);
  push(im.select('spi3_wet').updateMask(foot),     'wet',  s[1]+' · SPI-3 wet (0/1)',              false);
  if (s[2].indexOf('false_start')>=0)
    push(im.select('false_start').updateMask(foot),'fstart',s[1]+' · False-start (5+7)',           false);
});

// -- fused canopy condition (uncomment the fcci_* asset ids above once run_fcci.py TO_ASSET=1 has run) --
[['fcci_ke_long','Kenya Long rains'], ['fcci_et_meher','Ethiopia Meher'], ['fcci_ke_short','Kenya Short rains']]
 .forEach(function(s){ var id=ASSETS[s[0]]; if(!id) return;
   push(ee.Image(id).rename('FCCI').selfMask(), 'fcci', s[1]+' · Canopy condition (fused 10-20 m)', false); });

// -- static soil WHC (already an asset) --
if (ASSETS.whc){
  push(ee.Image(ASSETS.whc).rename('WHC_mm').updateMask(ee.Image(ASSETS.whc).gt(0)),
       'whc', 'Soil WHC (mm) · SoilGrids/Saxton', false);
}

// -- optional extras (uncomment the asset ids above to enable) --
if (ASSETS.spi3_ke_short) push(ee.Image(ASSETS.spi3_ke_short).rename('SPI3'), 'spi',
                               'Kenya Short rains · SPI-3', false);
if (ASSETS.planting_ke_long) push(ee.Image(ASSETS.planting_ke_long).rename('dekad').selfMask(),
                               'dekad', 'Kenya Long rains · planting dekad', false);

// ---- 6. Add to map --------------------------------------------------------------------
Map.setOptions('HYBRID');
Map.setCenter(38.0, 3.0, 5);                    // Greater Horn of Africa
layers.forEach(function(L){ Map.addLayer(L.im, L.v, L.name, L.on); });

// ---- 7. Legend panel ------------------------------------------------------------------
function legend(title, vis){
  var pan = ui.Panel({style:{padding:'6px', position:'bottom-left'}});
  pan.add(ui.Label(title, {fontWeight:'bold', fontSize:'12px', margin:'0 0 4px 0'}));
  var g = ui.Panel({layout: ui.Panel.Layout.flow('horizontal')});
  var bar = ee.Image.pixelLonLat().select(0)
              .multiply((vis.max-vis.min)/100).add(vis.min)
              .visualize({min:vis.min, max:vis.max, palette:vis.palette});
  var thumb = ui.Thumbnail({image:bar, params:{bbox:[0,0,100,8], dimensions:'120x10'},
                            style:{margin:'0 4px'}});
  g.add(ui.Label(''+vis.min)); g.add(thumb); g.add(ui.Label(''+vis.max));
  pan.add(g); return pan;
}
Map.add(legend('CPI / WRSI  (red→green = worse→better, <50 = failure)', VIS.cpi));
Map.add(legend('Stress / WSI  (white→red = worse)', VIS.wsi));

print('Layers loaded. Toggle them in the Layers menu (top-right of the map).');
print('Tip: use the Inspector tab, then click a pixel to read every band value.');
