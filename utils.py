import datetime
import os
import urllib
import subprocess
import glob

def viewports(bbox):
    """
    Inputs:
        bbox: As a string in the following format: "0 20 20 0", multiples of
        10.
    Output:
        viewports: A list of boxes of 10 x 10 degrees.
    """
    STEP = 10
    west, north, east, south = bbox

    lon_steps = (east - west) / STEP
    lat_steps = (north - south) / STEP

    the_viewports = [
            '010E020N', # top right
            '000E010N', # bottom left
            '000E020N', # top left
            '010E010N', # bottom right
    ]

    return the_viewports


def timespan(since, until):
    """
    Inputs:
        since: A datetime.date object
        until: A datetime.date object
    Output:
        the_timespan: A list of time steps in the form "(year)(day of year)" (e.g. 2012214)
    """
    the_timespan = []
    d = since
    delta = datetime.timedelta(days=1)

    while d <= (until - delta):
        year = d.year
        yday = d.timetuple().tm_yday
        identifier = '%s%s' % (year, yday)
        the_timespan.append(identifier)
        d += delta

    return the_timespan


def download(the_viewports, the_timespan, data_dir):
    """
    Downloads layers from modis floodmap on the given viewport and timespan.

    Inputs:
        the_viewports: A list of 10 by 10 bounding boxes.
        the_timespan: A list of times in the form year and day of year
        data_dir: Output directory for the downloaded files. (Defaults to cwd)
    """

    site = "http://oas.gsfc.nasa.gov"
    filename_templates = ["/Products/%(viewport)s/MWP_%(time)s_%(viewport)s_2D2OT.tif",
                          "/Products/%(viewport)s/MWP_%(time)s_%(viewport)s_2D2ON.tif",
                          #"/Products/%(viewport)s/MSW_%(time)s_%(viewport)s_2D2OT_V.zip",
                          #"/Products/%(viewport)s/MSW_%(time)s_%(viewport)s_2D2ON_V.zip",
                          ]

    data_dir = os.path.abspath(data_dir)

    # Iterate over viewports and times to get the urls
    for time in the_timespan:
        for viewport in the_viewports:
            for template in filename_templates:
                path = template % {'viewport': viewport, 'time': time}
                url = site + path
                name = url.split('/')[-1]
                filename = os.path.join(data_dir, name)
                if not os.path.exists(filename):
                    if urllib.urlopen(url).code == 200:
                        print 'opened connection to %s' % url
                        urllib.urlretrieve(url, filename)


def merge(the_timespan, data_dir, prefix="MWP"):
    """
    Merge all the files from a given timestamp
    Inputs:
        the_timespan: List of times in the form "(year)(day of year)"
        data_dir: Location of files
    Output:
        out: List of files that were created during the merge
    """
    out = []
    for time in the_timespan:
        os.chdir(data_dir)
        output_name = "floods_%s.tif" % time
        output_file = os.path.join(data_dir, output_name)
        if os.path.exists(output_file):
            out.append(output_file)
        else:
            print ' - Merging %s' % output_file
            files = glob.glob('%s*%s*' % (prefix, time))
            input_files = [os.path.join(data_dir, file) for file in files]
            subprocess.call(['gdal_merge.py',
                             '-co', 'compress=packbits',
                             '-ot', 'Byte',
                             '-o', output_file]
                             + input_files,
                             stdout=open(os.devnull, 'w')
                             )
            out.append(output_file)
    return out

def clip(raster, bbox, cellSize=None):
    """
    Clip the population dataset to the bounding box
    """
    basename, ext = os.path.splitext(raster)
    clipped_raster = basename + "_clip" + ext

    if not os.path.exists(clipped_raster):
        if cellSize is None:
            command = "gdalwarp -q -t_srs EPSG:4326 -r near -cutline %s -crop_to_cutline %s %s" % (extentToKml(bbox),raster,clipped_raster)
            print command

            os.system(command)
        else:
            command = "gdalwarp -q -t_srs EPSG:4326 -r near -tr %s %s -cutline %s -crop_to_cutline %s %s" % (cellSize,cellSize,extentToKml(bbox),raster,clipped_raster)
            
            print command
           
            os.system(command)

    keywords_file = basename + '.keywords'

    if os.path.exists(keywords_file):
        basename, ext = os.path.splitext(clipped_raster)

        clipped_keywords_file = basename + '.keywords'

        if not os.path.exists(clipped_keywords_file):
            with open(keywords_file, 'r') as f:
                with open(clipped_keywords_file, 'w') as cf:
                    cf.write(f.read())

    return clipped_raster

def extentToKml(theExtent):
    """A helper to get a little kml doc for an extent so that
    we can use it with gdal warp for clipping."""

    myBottomLeftCorner = '%s,%s' % (theExtent[0], theExtent[1])
    myTopLeftCorner = '%s,%s' % (theExtent[0], theExtent[3])
    myTopRightCorner = '%s,%s' % (theExtent[2], theExtent[3])
    myBottomRightCorner = '%s,%s' % (theExtent[2], theExtent[1])
    myKml = ("""<?xml version="1.0" encoding="utf-8" ?>
                    <kml xmlns="http://www.opengis.net/kml/2.2">
                      <Document>
                        <Folder>
                          <Placemark>
                            <Polygon>
                              <outerBoundaryIs>
                                <LinearRing>
                                  <coordinates>
                                    %s %s %s %s %s
                                  </coordinates>
                                </LinearRing>
                              </outerBoundaryIs>
                            </Polygon>
                          </Placemark>
                        </Folder>
                      </Document>
                    </kml>""" %
        (myBottomLeftCorner,
         myTopLeftCorner,
         myTopRightCorner,
         myBottomRightCorner,
         myBottomLeftCorner))

    myFilename = 'extent.kml'
    myFile = open(myFilename, 'wt')
    myFile.write(myKml)
    myFile.close()
    return os.path.abspath(myFilename)
