import os
import argparse

from interact_with_aws.aws_tools import download_file_from_aws
from utilities.handle_logging import set_up_logging

def main():

    set_up_logging('data_outputs')
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Download dataset catalog file from S3')
    parser.add_argument('--overwrite', action='store_true', 
                       help='Overwrite local file if it already exists')
    
    args = parser.parse_args()

    files_to_get = [
        'data_inputs/raster/land_use/copernicus/copernicus_clms_land_cover_global_100m_epsg4326.tif',
        'data_inputs/vector/protected_areas/WDPA/WDPA_Jun2025_Public-polygons.gpkg',
        'data_inputs/vector/admin_boundaries/geoBoundaries/geoBoundariesCGAZ_ADM0_repaired_twice.gpkg',
        'data_inputs/vector/admin_boundaries/geoBoundaries/geoBoundariesCGAZ_ADM1_repaired_twice.gpkg',
        ]
    
    for file_ in files_to_get:
        success = download_file_from_aws(file_,
                                         overwrite=args.overwrite)

if __name__ == "__main__":
    main()

