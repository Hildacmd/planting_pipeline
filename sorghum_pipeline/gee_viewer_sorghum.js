/**** Sorghum monitoring viewer — ICPAC / FSRP-AF, 2024 **********************************************
 *
 * Paste into the Earth Engine Code Editor (https://code.earthengine.google.com) and press Run.
 * Read-only: it only DISPLAYS assets written by planting_pipeline/sorghum_pipeline.
 *
 *   sorghumX_<Country>_<Season>_2024   CPI, yield, the three stresses, planting dekad, WRSI/WSI stages
 *   sorghumBX_<...>                    the same product on the GEOGLAM calendar (arm B), where it exists
 *   crop_type_mask/croptype_<ISO>_100m the sorghum mask and fraction the product is computed over
 *   whc_saxton_soilgrids_gha_150cm_250m  the 1.5 m root-zone water-holding capacity sorghum uses
 *
 * To publish this as a link colleagues can open without an Earth Engine account:
 *   Code Editor -> Apps -> NEW APP -> pick this script -> Publish.  The app URL is then shareable.
 *
 * Products whose asset does not exist are skipped and listed in the panel, so the script runs at
 * any stage. Click the map to inspect every value at a point.
 ****************************************************************************************************/

var PRODUCT = 'Sudan_Kharif';   // <-- change me; the full list is in PRODUCTS below

var EXPORTS = 'projects/ee-manzikye/assets';
var MASKS   = 'projects/indigo-proxy-484220-q8/assets/crop_type_mask';

// product -> ISO of the crop-type mask, map centre, fitted yield ceiling (null = uncalibrated),
// and the note that must travel with it.
var PRODUCTS = {
  'Sudan_Kharif':       {iso:'SD',   c:[31.5, 13.5], z:6, ym:0.80, r:-0.14,
                         note:'Largest sorghum area in the region, 6.32 Mha. Level only: CPI does not rank the localities.'},
  'Ethiopia_Meher':     {iso:'ET',   c:[39.5, 9.3],  z:6, ym:2.60, r:0.21,
                         note:'WRSI saturates near 100 and S_water is ~1 %, so the water balance carries almost no signal; CPI is driven by the vegetation term. Read as a level.'},
  'Ethiopia_Belg':      {iso:'ET',   c:[39.5, 8.0],  z:6, ym:null, r:null,
                         note:'Marginal for sorghum: HarvestStat holds 2 records from one unit.'},
  'Tanzania_Msimu':     {iso:'TZ',   c:[34.9, -6.4], z:6, ym:null, r:null,
                         note:'No sorghum yields in HarvestStat: UNCALIBRATED ceiling, do not quote the yield level.'},
  'Tanzania_Masika':    {iso:'TZ',   c:[36.5, -4.0], z:6, ym:null, r:null, note:'UNCALIBRATED.'},
  'South_Sudan_Main':   {iso:'SS',   c:[30.5, 7.5],  z:6, ym:null, r:null,
                         note:'2 HarvestStat units, too few to fit a ceiling. Mask uses the looser cropland rule.'},
  'South_Sudan_2nd':    {iso:'SS',   c:[30.5, 5.0],  z:6, ym:null, r:null, note:'Equatoria only. UNCALIBRATED.'},
  'Kenya_Longrains':    {iso:'KE',   c:[37.8, 0.3],  z:7, ym:1.41, r:0.54,
                         note:'The ONLY product with real rank skill (rho 0.59 against reported yields).'},
  'Kenya_Shortrains':   {iso:'KE',   c:[38.5, -0.5], z:7, ym:null, r:null, note:'UNCALIBRATED.'},
  'Uganda_1strains':    {iso:'UG',   c:[33.5, 2.0],  z:7, ym:1.31, r:-0.02,
                         note:'Ranks districts BACKWARDS (rho -0.20) against the 2009 statistics. Level only. Karamoja, the main sorghum zone, plants Apr-Aug, later than this national window.'},
  'Uganda_2ndrains':    {iso:'UG',   c:[33.5, 2.0],  z:7, ym:null, r:null, note:'UNCALIBRATED.'},
  'Somalia_Gu':         {iso:'SO20', c:[44.5, 3.5],  z:7, ym:0.41, r:0.36,
                         note:'Bay and Bakool rainfed sorghum. Level, weak pattern.'},
  'Somalia_Deyr':       {iso:'SO20', c:[44.5, 3.5],  z:7, ym:0.87, r:-0.04, note:'Level only.'},
  'Rwanda_SeasonA':     {iso:'RW20', c:[29.9, -1.95],z:9, ym:null, r:null, note:'UNCALIBRATED.'},
  'Rwanda_SeasonB':     {iso:'RW20', c:[29.9, -1.95],z:9, ym:null, r:null, note:'UNCALIBRATED.'},
  'Burundi_SeasonA':    {iso:'BI20', c:[29.9, -3.4], z:9, ym:null, r:null, note:'0.023 Mha total. UNCALIBRATED.'},
  'Burundi_SeasonB':    {iso:'BI20', c:[29.9, -3.4], z:9, ym:null, r:null, note:'UNCALIBRATED.'},
  'Eritrea_Kremti':     {iso:'ER',   c:[38.6, 15.2], z:7, ym:null, r:null,
                         note:'Eritrea is absent from HarvestStat entirely: never calibratable from it.'}
};
var P = PRODUCTS[PRODUCT];
if (!P) throw new Error('unknown PRODUCT: ' + PRODUCT);

// ---- palettes -------------------------------------------------------------------------------
// Planting dekad: ONE hue, dark (early) to light (late). A planting date is an ordered quantity
// with no meaningful midpoint, so a multi-hue or diverging ramp would invite reading the colours
// as categories rather than as earlier and later.
var BLUES  = ['08306b','08519c','2171b5','4292c6','6baed6','9ecae1','c6dbef'];
var RYG    = ['a50026','f46d43','fee08b','a6d96a','1a9850'];
var STRESS = ['ffffcc','fd8d3c','800026'];
var YLD    = ['f7fcb9','78c679','005a32'];

var missing = [];
function asset(id) {
  try { ee.data.getAsset(id); return true; } catch (e) { missing.push(id.split('/').pop()); return false; }
}

// ---- the product ----------------------------------------------------------------------------
var id = EXPORTS + '/sorghumX_' + PRODUCT + '_2024';
var img = asset(id) ? ee.Image(id) : null;
var maskImg = ee.Image(MASKS + '/croptype_' + P.iso + '_100m');
var sorghumMask = maskImg.select('mask_sorghum').selfMask();
var sorghumFrac = maskImg.select('frac_sorghum');

Map.setCenter(P.c[0], P.c[1], P.z);
Map.setOptions('HYBRID');

// the mask the product is computed over — always drawn, so an empty product is never mistaken
// for an empty season
Map.addLayer(sorghumFrac.selfMask(), {min: 0, max: 40, palette: ['f3f2ee', '1baf7a']},
             'Sorghum fraction, % of cell', false);
Map.addLayer(sorghumMask, {palette: ['1baf7a']}, 'Sorghum mask (frac >= 10 %)', false);

if (img) {
  // planting dekad, stretched to this product's own window rather than 1..36
  var pd = img.select('planting_dekad');
  var lo = ee.Number(pd.reduceRegion({reducer: ee.Reducer.percentile([2]),
            geometry: img.geometry(), scale: 2000, maxPixels: 1e10, bestEffort: true})
            .values().get(0));
  var hi = ee.Number(pd.reduceRegion({reducer: ee.Reducer.percentile([98]),
            geometry: img.geometry(), scale: 2000, maxPixels: 1e10, bestEffort: true})
            .values().get(0));
  lo.evaluate(function (a) { hi.evaluate(function (b) {
    Map.addLayer(pd, {min: a, max: b, palette: BLUES}, 'Planting dekad (' + a + ' to ' + b + ')');
  });});

  Map.addLayer(img.select('CPI'), {min: 0, max: 100, palette: RYG}, 'CPI');
  Map.addLayer(img.select('yield_tha_x100').divide(100),
               {min: 0, max: (P.ym || 3), palette: YLD},
               'Yield t/ha' + (P.ym ? '' : '  [UNCALIBRATED]'), false);
  Map.addLayer(img.select('wrsi_flo'), {min: 40, max: 100, palette: RYG}, 'WRSI at flowering', false);
  Map.addLayer(img.select('wrsi_grf'), {min: 40, max: 100, palette: RYG}, 'WRSI whole cycle', false);
  Map.addLayer(img.select('S_water'), {min: 0, max: 100, palette: STRESS}, 'Water stress S_water %', false);
  Map.addLayer(img.select('S_heat'),  {min: 0, max: 100, palette: STRESS}, 'Heat stress S_heat %', false);
  Map.addLayer(img.select('S_veg'),   {min: 0, max: 100, palette: STRESS}, 'Vegetation stress S_veg %', false);
  Map.addLayer(img.select('wrsi_flo').lt(50).selfMask(), {palette: ['a50026']},
               'Crop failure at flowering (WRSI < 50)', false);
}

// ---- arm B: the same product on the GEOGLAM calendar, where it was run -----------------------
var idB = EXPORTS + '/sorghumBX_' + PRODUCT + '_2024';
if (asset(idB)) {
  var imgB = ee.Image(idB);
  Map.addLayer(imgB.select('CPI'), {min: 0, max: 100, palette: RYG},
               'CPI — GEOGLAM calendar (arm B)', false);
  Map.addLayer(imgB.select('CPI').subtract(img.select('CPI')),
               {min: -20, max: 20, palette: ['2166ac', 'f7f7f7', 'b2182b']},
               'CPI difference, arm B minus arm A', false);
}

// ---- the soil input -------------------------------------------------------------------------
var whc = EXPORTS + '/whc_saxton_soilgrids_gha_150cm_250m';
if (asset(whc)) {
  Map.addLayer(ee.Image(whc), {min: 40, max: 250, palette: ['ffffd4', '78c679', '006837']},
               'Water-holding capacity, 1.5 m root zone (mm)', false);
}

// ---- panel ----------------------------------------------------------------------------------
var panel = ui.Panel({style: {width: '380px', padding: '8px'}});
panel.add(ui.Label('Sorghum 2024 — ' + PRODUCT.replace(/_/g, ' '),
                   {fontWeight: 'bold', fontSize: '16px'}));
panel.add(ui.Label('Crop-type mask: croptype_' + P.iso + '_100m, band mask_sorghum. NOT WorldCereal, ' +
                   'which has no sorghum class.', {fontSize: '11px', color: '#555'}));
panel.add(ui.Label(P.ym ? ('Yield ceiling Ym = ' + P.ym + ' t/ha, fitted to HarvestStat (r = ' + P.r + ')')
                        : 'Yield ceiling UNCALIBRATED — report CPI, not yield.',
                   {fontSize: '12px', fontWeight: 'bold',
                    color: P.ym ? '#1a6b2f' : '#a50026'}));
panel.add(ui.Label(P.note, {fontSize: '11px', color: '#333'}));
panel.add(ui.Label('FAO-33 sorghum Ky: veg 0.2, flowering 0.55, grain fill 0.45 — against maize ' +
                   '0.4 / 1.5 / 0.5. A flowering deficit costs maize about three times what it ' +
                   'costs sorghum, so a sorghum crop scored with maize factors would read as failed ' +
                   'in seasons it survives.', {fontSize: '11px', color: '#555'}));
panel.add(ui.Label('Area = sum(frac_sorghum / 100 x pixel area). NEVER count mask pixels: the mask ' +
                   'turns a whole cell on at 10 % crop, so it covers about 2.4x the ground the crop ' +
                   'occupies.', {fontSize: '11px', color: '#555'}));
if (missing.length) {
  panel.add(ui.Label('Not found (skipped): ' + missing.join(', '),
                     {fontSize: '11px', color: '#a50026'}));
}

// click to inspect
var out = ui.Panel();
panel.add(ui.Label('Click the map to inspect:', {fontWeight: 'bold', fontSize: '12px'}));
panel.add(out);
Map.onClick(function (coords) {
  out.clear();
  out.add(ui.Label('loading...'));
  var pt = ee.Geometry.Point([coords.lon, coords.lat]);
  var stack = img ? img.addBands(sorghumFrac) : sorghumFrac;
  stack.reduceRegion({reducer: ee.Reducer.first(), geometry: pt, scale: 250})
       .evaluate(function (v) {
         out.clear();
         Object.keys(v || {}).sort().forEach(function (k) {
           if (v[k] !== null) out.add(ui.Label(k + ': ' + v[k], {fontSize: '11px', margin: '1px 8px'}));
         });
         if (!v || Object.keys(v).length === 0) out.add(ui.Label('no data here', {fontSize: '11px'}));
       });
});
ui.root.insert(0, panel);
print('Sorghum viewer —', PRODUCT, '| product asset:', img ? 'found' : 'MISSING',
      '| missing:', missing);
