<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28" styleCategories="Symbology">
  <renderer-v2 type="graduatedSymbol" attr="mean_WRSI" graduatedMethod="GraduatedColor" symbollevels="0" forceraster="0" enableorderby="0">
    <ranges>
      <range lower="0.000" upper="50.000" label="Crop failure (&lt;50)" symbol="0" render="true"/>
      <range lower="50.000" upper="60.000" label="Poor (50–60)" symbol="1" render="true"/>
      <range lower="60.000" upper="80.000" label="Mediocre (60–80)" symbol="2" render="true"/>
      <range lower="80.000" upper="95.000" label="Good (80–95)" symbol="3" render="true"/>
      <range lower="95.000" upper="100.000" label="Optimal — no stress (≥95)" symbol="4" render="true"/>
    </ranges>
    <symbols>
      <symbol type="fill" name="0">
        <layer class="SimpleFill">
          <Option type="Map">
            <Option name="color" type="QString" value="165,0,38,255"/>
            <Option name="outline_color" type="QString" value="90,90,90,255"/>
            <Option name="outline_width" type="QString" value="0.12"/>
            <Option name="outline_style" type="QString" value="solid"/>
            <Option name="style" type="QString" value="solid"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="fill" name="1">
        <layer class="SimpleFill">
          <Option type="Map">
            <Option name="color" type="QString" value="244,109,67,255"/>
            <Option name="outline_color" type="QString" value="90,90,90,255"/>
            <Option name="outline_width" type="QString" value="0.12"/>
            <Option name="outline_style" type="QString" value="solid"/>
            <Option name="style" type="QString" value="solid"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="fill" name="2">
        <layer class="SimpleFill">
          <Option type="Map">
            <Option name="color" type="QString" value="253,174,97,255"/>
            <Option name="outline_color" type="QString" value="90,90,90,255"/>
            <Option name="outline_width" type="QString" value="0.12"/>
            <Option name="outline_style" type="QString" value="solid"/>
            <Option name="style" type="QString" value="solid"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="fill" name="3">
        <layer class="SimpleFill">
          <Option type="Map">
            <Option name="color" type="QString" value="166,217,106,255"/>
            <Option name="outline_color" type="QString" value="90,90,90,255"/>
            <Option name="outline_width" type="QString" value="0.12"/>
            <Option name="outline_style" type="QString" value="solid"/>
            <Option name="style" type="QString" value="solid"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="fill" name="4">
        <layer class="SimpleFill">
          <Option type="Map">
            <Option name="color" type="QString" value="26,152,80,255"/>
            <Option name="outline_color" type="QString" value="90,90,90,255"/>
            <Option name="outline_width" type="QString" value="0.12"/>
            <Option name="outline_style" type="QString" value="solid"/>
            <Option name="style" type="QString" value="solid"/>
          </Option>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
  <layerGeometryType>2</layerGeometryType>
</qgis>