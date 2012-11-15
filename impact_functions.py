# coding=utf-8

import numpy

from safe.storage.raster import Raster
from safe.impact_functions.core import FunctionProvider
from safe.impact_functions.core import get_hazard_layer, get_exposure_layers

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