floodimpact
===========

Flood impact using InaSafe


installation
============

virtualenv floods
source floods/bin/activate
pip install -e git+https://github.com/AIFDR/inasafe.git#egg=python-safe


Usage
=====

```
python floodimpact.py west south east north since_date [-u until_date] [-d data_folder] [-p population_file_path]

west: the west geographic coordinate of the bounding box (0 for Nigeria)
south: the south geographic coordinate of the bounding box (0 for Nigeria)
east: the east geographic coordinate of the bounding box (20 for Nigeria)
north: the north geographic coordinate of the bounding box (20 for Nigeria)

since_date: the starting date to analyze in the form 'YYYY-MM-DD'
untile_date: the end date to analyze in the form 'YYYY-MM-DD'

data_folder: the path to the data folder

population_file: the path to the population file tu use in the analysis

In order to run the tool make sure to have a population file downloaded in your most convenient folder
```
