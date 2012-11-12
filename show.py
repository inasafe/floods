
    x, y = flood_severity.get_data().shape
    m = mapnik.Map(x, y)
    m.background = mapnik.Color(255,255,255,0)

    layer = mapnik.Layer('world')

    rs = mapnik.RasterSymbolizer()
    rs.colorizer = mapnik.RasterColorizer()
    rs.colorizer.epsilon = 1

    total_days = flood_severity.keywords['total_days']

    rs.colorizer.add_stop(0, mapnik.COLORIZER_LINEAR, mapnik.Color(255,255,255,0) )

    rs.colorizer.add_stop(2,mapnik.Color(241, 238, 246))
    rs.colorizer.add_stop(5,mapnik.Color(189, 201, 225))
    rs.colorizer.add_stop(10,mapnik.Color(116, 169, 207))
    rs.colorizer.add_stop(30,mapnik.Color(43, 140, 190))
    rs.colorizer.add_stop(60, mapnik.Color(4, 90, 141))

    # 0 not flooded, one color
    #1,2,3 # another color
    #4- 6, # another color
    #7 - 8 # another color

    raster = mapnik.Gdal(file=temp, band=1)
    layer = mapnik.Layer('GDAL Layer from TIFF file')
    layer.datasource = raster

    s = mapnik.Style() # style object to hold rules
    r = mapnik.Rule() # rule object to hold symbolizers
    r.symbols.append(rs)
    s.rules.append(r)

    m.append_style('flood_style',s)

    layer.styles.append('flood_style')

    m.layers.append(layer)
    m.zoom_all()

    earth = mapnik.Gdal(file='earth.tif')
    earth_layer = mapnik.Layer('Earth')
    earth_layer.datasource = earth

    m.layers.append(earth_layer)

    # Write the data to a png image called world.png the current directory
    mapnik.render_to_file(m,'flood.png', 'png')


