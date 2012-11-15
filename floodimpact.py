#!/usr/bin/python
# coding=utf-8

import argparse
import datetime
import urllib
import subprocess
import glob
import os
import numpy

from functools import wraps

from safe.api import calculate_impact
from safe.storage.raster import Raster

from utils import *
from impact_functions import *
from process_microwave import *

FLOOD_KEYWORDS = """
category:hazard
subcategory:flood
source:modis
"""

REFERENCE_LAYER_NAME = None

if not '/usr/local/bin' in os.environ['PATH']:
    os.environ['PATH'] = os.environ['PATH'] + ':/usr/local/bin'

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

def _flood_severity(hazard_files, microwave_date = None):
    """
    Accumulate the hazard level
    """
    # Value above which people are regarded affected
    # For this dataset, 0 is no data, 1 is cloud, 2 is normal water level
    # and 3 is overflow.
    water_threshold = 3
    cloud_no_data_threshold = 1

    # This is a scalar but will end up being a matrix
    I_sum = None
    cloud_matrix_sum = None
    projection = None
    geotransform = None
    total_days = len(hazard_files)
    ignored = 0

    print 'Accumulating layers'

    I_sum_shape = None
    for hazard_filename in hazard_files:
        if os.path.exists(hazard_filename):
            print " - Processing %s" % hazard_filename
            layer = read_layer(hazard_filename)

            # Extract data as numeric arrays
            D = layer.get_data(nan=0.0) # Depth
            # Assign ones where it is affected
            I = numpy.where(D > threshold, 1, 0)

            # If this is the first file, use it to initialize the aggregated one and stop processing
            if I_sum is None:
                I_sum = I
                I_sum_shape = I_sum.shape
                projection=layer.get_projection()
                geotransform=layer.get_geotransform()
                continue

            # If it is not the first one, add it up if it has the right shape, otherwise, ignore it
            if  I_sum_shape == I.shape:
                I_sum = I_sum + I
            else:
                # Add them to a list of ignored files
                ignored = ignored + 1
                print 'Ignoring file %s because it is incomplete' % hazard_filename

    cloud_map = get_cloud_coverage(cloud_matrix_sum, total_days, projection, geotransform)
    
    # reverse the cloud map to get 0 where is cloudy with 1-cloud_map
    inverse_cloud_map = 1 - cloud_map 

    # TODO download microwave base on availability (use dates??)
    # if count cloud_map where 1 is 0, don't use microwave
    # if there is a one in the map then get available microwaves

    # multiply inverse_cloud_map * I_sum to get just not cloudy floods
    I_sum = I_sum * inverse_cloud_map

    if 1 in cloud_map and microwave_date is not None:
        microwave_file = download_microwave(microwave_date)
    
        if len(microwave_files) > 0:

            microwave_flood = detect_microwave_flood(REFERENCE_LAYER_NAME,microwave_file)

            # multiply the cloud_map and the microwave_flood to get microwave flood under clouds (under_cloud_flood)
            # scale the under_cloud_flood to get total_days + 1 (under_cloud_map = under_cloud_floods * (total_days + 1))
            under_cloud_flood = (microwave_flood * cloud_map) * (total_days + 1)

            # sum I_sum and under_cloud_map to get the mix of microwave and optical flooded areas
            I_sum += under_cloud_map

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

def get_cloud_coverage(cn_sum, num_files, projection, geotransform):
    """
    Verify where cloud coverage sum (cn_sum) is greater that the 70 percent of the number
    of the considered dates (num_files).
    Creates the cloud coverage source matrix and the corresponding tif file.
    Returns the numpy matrix. 
    """
    # Percentage of time where the pixel was covered by clouds
    days_threshold = 0.7 * len(num_files)

    # 0 where we use NASA data, 1 is where we use microwave data
    # this also means that 0 is no cloud covered and 1 is cloud covered
    cloud_exceed = numpy.where(cn_sum > days_threshold, 1,0)

    cc = Raster(cloud_exceed, projection=projection, geotransform=geotransform,name='Source map')
    cc.write_to_file('source_map.tif')

    return cloud_exceed

def start(west,north,east,south, since, until=None, data_dir=None, population=None):
    
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

    data_dir = os.path.abspath(data_dir)

    if not os.path.exists(data_dir):
        os.mkdir(data_dir)

    print 'Downloading layers per day'
    # Download the layers for the given viewport and timespan.
    download(the_viewports, the_timespan, data_dir)

    print 'Merging layers per day'
    merged_files = merge(the_timespan, data_dir)

    flood_filename = os.path.join(data_dir, 'flood_severity.tif')

    if not os.path.exists(flood_filename):
        if len(merged_files) > 0:
            # Add all the pixels with a value higher than 3.
            #accumulate(merged_files, flood_filename, threshold=3)
            flooded = _flood_severity(merged_files, microwave_date = until)
            flooded.write_to_file(flood_filename)

            subprocess.call(['gdal_merge.py',
                     '-co', 'compress=packbits',
                     '-o', 'flood_severity_compressed.tif',
                     '-ot', 'Byte',
                     flood_filename], stdout=open(os.devnull, 'w'))
            os.remove(flood_filename)
            os.rename('flood_severity_compressed.tif', flood_filename)
        else:
            raise Exception('No merged files found for %s' % the_timespan)
    
    population_file = os.path.join(data_dir, population)
    population_object = Raster(population_file)
    # get population bbox
    pop_bbox = population_object.get_bounding_box()

    # get resolutions and pick the best
    pop_resolution = population_object.get_resolution()[0]

    hazard_object = Raster(flood_filename)
    hazard_resolution = hazard_object.get_resolution()[0]
    hazard_bbox = hazard_object.get_bounding_box()

    if pop_bbox[0] > bbox[0] and pop_bbox[1] > bbox[1] and pop_bbox[2] < bbox[2] and pop_bbox[3] < bbox[3]:
        hazard_file = clip(flood_filename, pop_bbox, cellSize=pop_resolution)
        exposure_layer = population_file
    else:
        hazard_file = clip(flood_filename, hazard_bbox, cellSize=pop_resolution)
        exposure_layer = clip(population_file, hazard_bbox, cellSize=None)    

    basename, ext = os.path.splitext(hazard_file)
    keywords_file = basename + '.keywords'

    if not os.path.exists(keywords_file):
        with open(keywords_file, 'w') as f:
            f.write(FLOOD_KEYWORDS)

    impact = calculate(hazard_file, exposure_layer)

    impact.write_to_file('impact.tif')

    count = impact.keywords['count']
    pretty_date = until.strftime('%a %d, %b %Y')
    print pretty_date, "|", "People affected: %s / %s" % (count, impact.keywords['total'])


if __name__=="__main__":
    parser = argparse.ArgumentParser(description='Process flood imagery from modis.')

    parser.add_argument("west", type=int, help="west coordinate in lat long (e.g. 0)")
    parser.add_argument("south", type=int, help="south coordinate in lat long (e.g. 0)")
    parser.add_argument("east", type=int, help="east coordinate in lat long (e.g. 20)")
    parser.add_argument("north", type=int, help="north coordinate in lat long (e.g. 20")
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

    start(args.west, args.south, args.east, args.north, args.since, until=args.until, data_dir=args.data, population=args.population)
