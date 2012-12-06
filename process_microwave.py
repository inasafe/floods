import numpy, os

from utils import read_layer, clip

def download_reference_layer():
    """
    Downloads and merge all the tiles of the needed reference layer from modis.
    """
    return 'nigeria_water_mask.tif'

def download_microwave(date):
    """
    If microwave is available on the website download the all the available images 
    in the dates range (python datetime).
    """

    # veify the available number of files
    return 'test_microwave.tif'

def detect_microwave_flood(microwave_date, bbox, resolution, data_dir):
    """
    Verify the microwave format to check whether it contains information on normal
     water (reference water levels). Detect water
    """
    
    microwave_filename = os.path.join(data_dir, download_microwave(microwave_date))

    reference_filename = os.path.join(data_dir, download_reference_layer())

    water_normal_level = 1

    print 'Clipping reference layer to %s and bbox %s' % (resolution, bbox)

    reference_layer = clip(reference_filename, bbox, resolution)
    
    reference_layer = read_layer(reference_layer)
    
    D = reference_layer.get_data(nan=0.0)
    # 0 is normal water, 1 is no normal water

    print 'Getting reference levels'
    I = numpy.where(D == water_normal_level , 0, 1)

    # Resample and clip the microwave to the hazard resolution
    # we know that microwave bbox is always > hazard bbox
    clipped_microwave = clip(microwave_filename, bbox, cellSize=resolution)

    microwave_layer = read_layer(clipped_microwave)
    M = microwave_layer.get_data(nan=0.0)
    # 0 is normal water, 1 is not equal to normal water 
    # TODO: check in the nasa files have the same normal water in all the dates

    microwave_water_level = define_microwave_water_level(M, I)

    MW = numpy.where(M >= microwave_water_level, 1, 0)

    print 'Creating the microwave flood matrix'
    # 0 is not flood water, 1 is flood water
    MW_flood = MW * I

    return MW_flood

def define_microwave_water_level(microwave_matrix, reference_matrix):
    """
    Calculate the microwave water level based on modis flood data.
    Input data is the flood_severity matrix.
    """

    microwave_subset = microwave_matrix.compress((reference_matrix == 1).flat)


    avg = numpy.average(microwave_subset)
    std = numpy.std(microwave_subset)

    print len(microwave_subset), avg, std
    return avg + (0.5 * std)