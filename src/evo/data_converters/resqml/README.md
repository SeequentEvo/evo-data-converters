# RESQML

RESQML is an XML based standard for geoscience data.

Refer here for more information: https://www.energistics.org/resqml-data-standards/

To work with RESQML files [the `resqpy` Python package](https://pypi.org/project/resqpy/) is used.

## Limitations

Processing a large amount of grid data can consume a lot of memory due to the `grid.corner_points` array getting very large.

To protect against this there is a `memory_threshold` setting in [conversion_options.py](importer/conversion_options.py). Grids will only be converted if the estimated size of `grid.corner_points` is less than the threshold. The default is 8 GiB but this can be increased if you have more memory available where the importer is running.