#!/usr/bin/python
# coding=utf-8

import argparse
import datetime
import urllib
import subprocess
import glob
import os
import numpy

from safe.api import read_layer, calculate_impact
from safe.impact_functions.core import FunctionProvider
from safe.impact_functions.core import get_hazard_layer, get_exposure_layers
from safe.storage.raster import Raster


class ModisFloodImpactFunction(FunctionProvider):
    """Risk plugin for flood impact

    :author Ariel Núñez
    :rating 1
    :param requires category=='hazard' and \
    subcategory=='flood' and \
    layertype=='raster' and \
    source=='modis'

    :param requires category=='exposure' and \
    subcategory=='population' and \
    layertype=='raster' and \
    datatype=='density'
    """

    plugin_name = 'flooded'

    @staticmethod
    def run(layers):
        """Risk plugin for earthquake fatalities

        Input
        layers: List of layers expected to contain
        H: Raster layer of flood depth
        P: Raster layer of population data on the same grid as H
        """

        # Value above which people are regarded affected
        # For this dataset, 0 is no data, 1 is cloud, 2 is normal water level
        # and 3 is overflow.
        threshold = 0

        # Identify hazard and exposure layers
        inundation = get_hazard_layer(layers)

        [population] = get_exposure_layers(layers)

        # Extract data as numeric arrays
        D = inundation.get_data(nan=0.0) # Depth

        # Scale the population layer
        P = population.get_data(nan=0.0, scaling=True)
        I = numpy.where(D > threshold, P, 0)

        # Assume an evenly distributed population for Gender
        G = 0.5
        pregnant_ratio = 0.024 # 2.4% of women are estimated to be pregnant

        # Calculate breakdown
        P_female = P * G
        P_male = P - P_female
        P_pregnant = P_female * pregnant_ratio

        I_female = I * G
        I_male = I - I_female
        I_pregnant = I_female * pregnant_ratio

        # Generate text with result for this study
        total = str(int(sum(P.flat) / 1000))
        count = str(int(sum(I.flat) / 1000))

        total_female = str(int(sum(P_female.flat) / 1000))
        total_male = str(int(sum(P_male.flat) / 1000))
        total_pregnant = str(int(sum(P_pregnant.flat) / 1000))

        affected_female = str(int(sum(I_female.flat) / 1000))
        affected_male = str(int(sum(I_male.flat) / 1000))
        affected_pregnant = str(int(sum(I_pregnant.flat) / 1000))

        # Create raster object and return
        R = Raster(I,
                   projection=inundation.get_projection(),
                   geotransform=inundation.get_geotransform(),
                   name='People affected',
                   keywords={'total': total, 'count': count,
                             'total_female': total_female, 'affected_female': affected_female,
                             'total_male': total_male, 'affected_male': affected_male,
                             'total_pregnant': total_pregnant, 'affected_pregnant': affected_pregnant,
                            })
        return R

class ModisFloodDaysFunction(FunctionProvider):
    """Risk plugin for severity of floods

    :author Ariel Núñez
    :rating 1
    :param requires category=='hazard' and \
    subcategory=='flood' and \
    layertype=='raster' and \
    source=='modis'

    """

    plugin_name = 'floodeddays'

    @staticmethod
    def run(layers):
        """Risk plugin for earthquake fatalities

        Input
        layers: List of layers expected to contain flood layers for different days
        """



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

    while d <= until:
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
        if not os.path.exists(output_file):
            files = glob.glob('%s*%s*' % (prefix, time))
            input_files = [os.path.join(data_dir, file) for file in files]
            subprocess.call(['gdal_merge.py',
                             '-co', 'compress=packbits',
                             '-o', output_file]
                             + input_files,
                             stdout=open(os.devnull, 'w'))
        if os.path.exists(output_file):
            out.append(output_file)

    return out


def resample(files, population):
    """
    Resample the input files to the resolution of the population dataset.
    """
    p = read_layer(population)
    res_x, res_y = p.get_resolution()
    out = []
    for input_file in files:
        basename, ext = os.path.splitext(input_file)
        sampled_output = basename + "_resampled" + ext
        if not os.path.exists(sampled_output):
            subprocess.call(['gdalwarp',
                             '-tr', str(res_x), str(res_y),
                             input_file, sampled_output],
                             stdout=open(os.devnull, 'w'))
        out.append(sampled_output)
    return out


def clip(population, bbox):
    """
    Clip the population dataset to the bounding box
    """
    basename, ext = os.path.splitext(population)
    clipped_population = basename + "_clip" + ext
    if not os.path.exists(clipped_population):
        subprocess.call(['gdal_translate',
                         '-projwin', str(bbox[0]), str(bbox[1]),
                                    str(bbox[2]), str(bbox[3]),
                         population, clipped_population],
                         stdout=open(os.devnull, 'w'))

    keywords_file = basename + '.keywords'

    if os.path.exists(keywords_file):
        basename, ext = os.path.splitext(clipped_population)

        clipped_keywords_file = basename + '.keywords'

        if not os.path.exists(clipped_keywords_file):
            with open(keywords_file, 'r') as f:
                with open(clipped_keywords_file, 'w') as cf:
                    cf.write(f.read())

    return clipped_population


FLOOD_KEYWORDS = """
category:hazard
subcategory:flood
source:modis
"""

def impact(hazard_files, exposure_file):
    """
    Calculate the impact of each of the hazards on the exposure
    """
    out = []
    for hazard_file in hazard_files:
        basename, ext = os.path.splitext(hazard_file)
        keywords_file = basename + '.keywords'

        if not os.path.exists(keywords_file):
            with open(keywords_file, 'w') as f:
                f.write(FLOOD_KEYWORDS)

        impact_file = basename + '_impact' + ext

        if not os.path.exists(impact_file):
            try:
                impact = calculate(hazard_file, exposure_file)
            except:
                continue
            else:
                impact.write_to_file(impact_file)

        out.append(impact_file)
    return out

def calculate(hazard_filename, exposure_filename):
    """
    Use SAFE to calculate the impact
    Inputs:
        hazard_filename: Absolute path to hazard file
        exposure_filename: Absolute path to exposure file
    """

    H = read_layer(hazard_filename)
    E = read_layer(exposure_filename)
    IF = ModisFloodImpactFunction

    impact_layer = calculate_impact(layers=[H, E],impact_fcn=IF)
    impact_filename = impact_layer.get_filename()

    calculated_raster = read_layer(impact_filename)
    return calculated_raster


def flood_severity(hazard_files):
    """
    Accumulate the hazard level
    """
    # Value above which people are regarded affected
    # For this dataset, 0 is no data, 1 is cloud, 2 is normal water level
    # and 3 is overflow.
    threshold = 2.9

    # This is a scalar but will end up being a matrix
    I_sum = None
    projection = None
    geotransform = None
    total_days = len(hazard_files)
    ignored = 0
    for hazard_filename in hazard_files:
        print "Processing %s" % hazard_filename
        layer = read_layer(hazard_filename)

        # Extract data as numeric arrays
        D = layer.get_data(nan=0.0) # Depth
        # Assign ones where it is affected
        I = numpy.where(D > threshold, 1, 0)

        # If this is the first file, use it to initialize the aggregated one and stop processing
        if I_sum is None:
            I_sum = I
            projection=layer.get_projection()
            geotransform=layer.get_geotransform()
            continue

        # If it is not the first one, add it up if it has the right shape, otherwise, ignore it
        if  I_sum.shape == I.shape:
            I_sum = I_sum + I
        else:
            # Add them to a list of ignored files
            ignored = ignored + 1
            print 'Ignoring file %s because it is incomplete' % hazard_filename

    # Create raster object and return
    R = Raster(I_sum,
               projection=projection,
               geotransform=geotransform,
               name='People affected',
               keywords={'category':'hazard', 'subcategory': 'flood',
                         'units': 'days', 'total_days': total_days,
                         'ignored': ignored,
                         })
    return R

def start(west,north,east,south, since, data_dir=None, until =None):
    
    bbox = (west, north, east, south)

    year, month, day = [int(x) for x in since.split('-')]
    since = datetime.date(year, month, day)

    if not isinstance(until, datetime.date):
        year, month, day = [int(x) for x in until.split('-')]
        until = datetime.date(year, month, day)
    else:
        until = until

    # Make sure the inputs are divisible by 10.
    for item in bbox:
        msg = "%d is not divisible by 10." % item
        assert int(item) % 10 == 0, msg    

    the_viewports = viewports(bbox)
    the_timespan = timespan(since, until)

    print 'viewports generated'
    data_dir = os.path.abspath(data_dir)

    if not os.path.exists(data_dir):
        os.mkdir(data_dir)

    # Download the layers for the given viewport and timespan.
    download(the_viewports, the_timespan, data_dir)

    merged_files = merge(the_timespan, data_dir)

    population_file = os.path.join(data_dir, args.population)

    #resampled_files = resample(merged_files, population_file)

    temp = os.path.join(data_dir, 'flood_severity.tif')

    if not os.path.exists(temp):
    	flood_severity = flood_severity(merged_files)
    	flood_severity.write_to_file(temp)

    	subprocess.call(['gdal_merge.py',
                     '-co', 'compress=packbits',
                     '-o', 'flood_severity_compressed.tif',
                     temp], stdout=open(os.devnull, 'w'))
    	os.remove(temp)
    	os.rename('flood_severity_compressed.tif', temp)
    else:
	flood_severity = read_layer(temp)
    exposure_layer = clip(population_file, bbox)


    [hazard_file] = resample([temp], exposure_layer)

    basename, ext = os.path.splitext(hazard_file)
    keywords_file = basename + '.keywords'

    if not os.path.exists(keywords_file):
        with open(keywords_file, 'w') as f:
            f.write(FLOOD_KEYWORDS)

    impact = calculate(hazard_file, exposure_layer)

    impact.write_to_file('impact.tif')

    count = impact.keywords['count']
    pretty_date = until.strftime('%a %d, %b %Y')
#    print pretty_date, "|", "People affected: %s / %s" % (count, impact.keywords['total'])

if __name__=="__main__":
    parser = argparse.ArgumentParser(description='Process flood imagery from modis.')

    parser.add_argument("west", type=int, help="west coordinate in lat long (e.g. 0)")
    parser.add_argument("north", type=int, help="north coordinate in lat long (e.g. 20")
    parser.add_argument("east", type=int, help="east coordinate in lat long (e.g. 20)")
    parser.add_argument("south", type=int, help="south coordinate in lat long (e.g. 0)")
    parser.add_argument("since", type=str,
                        help="Day in the form of YYYY-MM-DD (e.g. 2012-01-23)")

    parser.add_argument("-u", "--until", dest="until", type=str,
                help="Day in the form of YYYY-MM-DD. (defaults to today)",
                default=datetime.date.today())

    parser.add_argument("-d", "--dest", dest="data", type=str,
                help="Destination directory. (defaults to current directory)",
                default=os.path.join(os.getcwd(), 'data'))

    parser.add_argument("-p", "--population", dest="population", type=str,
                help="Population filename. (defaults to population.tif)",
                default='population.tif')

    args = parser.parse_args()

    start(args.west,args.north,args.east,args.south, args.since, until=args.until, data_dir=args.data)
