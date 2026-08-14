<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28" styleCategories="Symbology">
  <!-- WRSI (Water Requirement Satisfaction Index) — FEWS/GeoWRSI crop-performance classes.
       Apply to the WRSI GeoTIFF, band 1 (WRSI 0–100). Discrete classes: value <= item bound. -->
  <pipe>
    <rasterrenderer type="singlebandpseudocolor" band="1" opacity="1"
                    classificationMin="0" classificationMax="100" alphaBand="-1" nodataColor="">
      <rastershader>
        <colorrampshader colorRampType="DISCRETE" classificationMode="1" clip="0"
                         minimumValue="0" maximumValue="100" labelPrecision="0">
          <item value="50"  color="#a50026" alpha="255" label="Crop failure (&lt; 50)"/>
          <item value="60"  color="#f46d43" alpha="255" label="Poor (50–60)"/>
          <item value="80"  color="#fdae61" alpha="255" label="Mediocre (60–80)"/>
          <item value="95"  color="#a6d96a" alpha="255" label="Good (80–95)"/>
          <item value="100" color="#1a9850" alpha="255" label="Optimal — no stress (≥ 95)"/>
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
    <brightnesscontrast brightness="0" contrast="0" gamma="1"/>
    <huesaturation grayscaleMode="0" saturation="0" colorizeStrength="100" colorizeOn="0"/>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
