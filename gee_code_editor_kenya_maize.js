/**** Kenya maize planting-window — GEE Code Editor demo ****/
// Paste into https://code.earthengine.google.com , press Run, watch the layers extract.

var YEAR = 2024;
var aoi = ee.FeatureCollection('FAO/GAUL_SIMPLIFIED_500m/2015/level0')
            .filter(ee.Filter.eq('ADM0_NAME','Kenya')).geometry();
Map.centerObject(aoi, 6);

var SOS_START = 9, SOS_END = 15;                 // Long-rains window: Mar-d3 .. May-d3
var dekadStart = function(y, dk){
  dk = ee.Number(dk);
  var m = dk.subtract(1).divide(3).floor().add(1);
  var day = ee.List([1,11,21]).get(dk.subtract(1).mod(3));
  return ee.Date.fromYMD(y, m, day);
};

// guarantee a Float single band even when a dekad has NO images (cloud gaps) -> avoids
// 0-band add errors and MaskOnly/Short type clashes in the collection reducers
var safeBand = function(col, bandName){
  col = col.select([bandName]).map(function(i){ return i.toFloat(); });
  return ee.Image(ee.Algorithms.If(col.size().gt(0),
    col.median(),
    ee.Image.constant(0).toFloat().rename(bandName).updateMask(ee.Image.constant(0)))).toFloat();
};

var s2col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(aoi).filterDate(YEAR+'-01-01',(YEAR+1)+'-01-05')
  .linkCollection(ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED'),['cs_cdf'])
  .map(function(img){
     img = img.updateMask(img.select('cs_cdf').gte(0.6)).divide(10000);
     return img.normalizedDifference(['B6','B5']).rename('NDRE').copyProperties(img,['system:time_start']);
  });

var s1col = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(aoi).filterDate(YEAR+'-01-01',(YEAR+1)+'-01-05')
  .filter(ee.Filter.eq('instrumentMode','IW')).filter(ee.Filter.eq('orbitProperties_pass','DESCENDING'))
  .map(function(img){
     var lin = ee.Image(10).pow(img.divide(10));
     var vv = lin.select('VV'), vh = lin.select('VH');
     return vh.multiply(4).divide(vv.add(vh)).rename('RVI').copyProperties(img,['system:time_start']);
  });

var fparCol = ee.ImageCollection('MODIS/061/MCD15A3H')
  .filterBounds(aoi).filterDate(YEAR+'-01-01',(YEAR+1)+'-01-05').select('Fpar');

var dekads = ee.List.sequence(SOS_START, SOS_END);
var gCol = ee.ImageCollection(dekads.map(function(dk){
  dk = ee.Number(dk);
  var s = dekadStart(YEAR, dk), e = s.advance(10,'day');
  var ndre = safeBand(s2col.filterDate(s,e), 'NDRE');
  var rvi  = safeBand(s1col.filterDate(s,e), 'RVI');
  var fpar = safeBand(fparCol.filterDate(s,e), 'Fpar').multiply(0.01);
  var optG = ndre.unitScale(0,0.7).clamp(0,1).add(fpar.unitScale(0,0.9).clamp(0,1)).divide(2);
  var sarG = rvi.unitScale(0.1,0.8).clamp(0,1);
  return optG.unmask(sarG).rename('G').toFloat().set({dekad: dk, 'system:time_start': s.millis()});
}));

var mask = ee.ImageCollection('ESA/WorldCereal/2021/MODELS/v100')
  .filter(ee.Filter.eq('product','maize')).mosaic().select('classification').eq(100).selfMask();

var gmin = gCol.select('G').min(), gmax = gCol.select('G').max();
var thresh = gmin.add(gmax.subtract(gmin).multiply(0.25));
var cand = gCol.map(function(img){
  var dk = ee.Number(img.get('dekad'));
  return img.select('G').gte(thresh).multiply(dk).selfMask().toInt16().rename('cand');
});
var sos = cand.min().rename('SOS_dekad').updateMask(mask);
var planting = sos.subtract(2).rename('planting_dekad');   // maize emergence offset = 2 dekads

var pal = ['2b83ba','abdda4','ffffbf','fdae61','d7191c'];
Map.addLayer(gmax.updateMask(mask), {min:0,max:1,palette:['white','darkgreen']}, 'peak fused greenness G');
Map.addLayer(sos,      {min:SOS_START,max:SOS_END,palette:pal}, 'SOS dekad');
Map.addLayer(planting, {min:8,max:14,palette:pal}, 'planting dekad');
print('Fused greenness collection:', gCol);

// extract to Drive (watch progress in the Tasks tab)
Export.image.toDrive({
  image: planting.toFloat(), description: 'demo_planting_Kenya_maize_'+YEAR,
  folder: 'planting_outputs', region: aoi, scale: 100, maxPixels: 1e13
});
