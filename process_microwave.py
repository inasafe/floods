import numpy

from utils import read_layer, clip

def download_microwave(dates):
    """
    If microwave is available on the website download the all the available images 
    in the dates range (python datetime).
    """

    # veify the available number of files
    pass

def detect_microwave_flood(hazard_filename, microwave_filename):
    """
    Verify the microwave format to check whether it contains information on normal
     water (reference water levels). Detect water
    """
    water_normal_level = 2

    hazard_layer = read_layer(hazard_filename)
    D = hazard_layer.get_data(nan=0.0)
    # 0 is normal water, 1 is no normal water
    I = numpy.where(D = water_normal_level , 0, 1)

    hazard_resolution = D.get_resolution()[0]

    # Resample and clip the microwave to the hazard resolution
    # we know that microwave bbox is always > hazard bbox
    clipped_microwave = clip(microwave_filename, D.get_bounding_box(), cellSize=hazard_resolution)

    microwave_layer = read_layer(clipped_microwave)
    M = microwave_layer.get_data(nan=0.0)
    # 0 is normal water, 1 is not equal to normal water 
    # TODO: check in the nasa files have the same normal water in all the dates

    microwave_water_level = define_microwave_water_level(D)
    MW = numpy.where(M <= microwave_water_level, 1, 0)

    # 0 is not flood water, 1 is flood water
    MW_flood = MW * I

    return MW_flood

def define_microwave_water_level(modis_flood_matrix):
    """
    Calculate the microwave water level based on modis flood data.
    Input data is the flood_severity matrix.
    """
    avg = numpy.average(modis_flood_matrix)
    std = numpy.std(modis_flood_matrix)

    return avg + (2 * std)