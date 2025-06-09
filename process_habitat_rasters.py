import argparse
import os

import numpy as np
import rasterio

def parse_args():
    parser = argparse.ArgumentParser(description="Process habitat raster files.")
    parser.add_argument('dir_data',
                        type=str,
                        help='File path to the directory containing the raster files.')

    args = parser.parse_args()

    return args

def make_output_dir(dir_data):
    dir_out = os.path.join(dir_data, 'code_output')
    os.makedirs(dir_out, exist_ok=True)
    return dir_out

def summarize_raster(src, data):

    # Basic metadata
    projection = src.crs
    dimensions = (src.height, src.width)
    bounds = src.bounds

    # Null (masked) analysis
    total_cells = data.size
    null_cells = np.ma.count_masked(data)
    null_fraction = null_cells / total_cells

    # Non-null stats
    non_null_data = data.compressed()  # Unmask data to get only valid values
    min_val = np.min(non_null_data)
    max_val = np.max(non_null_data)
    mean_val = np.mean(non_null_data)
    median_val = np.median(non_null_data)

    summary = {
        'projection': str(projection),
        'dimensions (rows, cols)': dimensions,
        'bounds': bounds,
        'fraction_null': null_fraction,
        'min': min_val,
        'max': max_val,
        'mean': mean_val,
        'median': median_val
    }

    for k, v in summary.items():
        print(f"{k}: {v}")

    return summary

def main():

    args = parse_args()
    dir_data = args.dir_data

    dir_out = make_output_dir(dir_data)

    name_raster = 'glm_pangosnewroads_seed333_1_1.tif'
    path_raster = os.path.join(dir_data, 'raster', 'habitat_suitability', name_raster)

    path_protected_areas = os.path.join(dir_data, 'vector', 'protected_areas', 
                                        'MYS', 'MY-12',
                                        'Management_Units_(PAs-FRs).shp')

    with rasterio.open(path_raster) as raster_src:

        raster_data = raster_src.read(1, masked=True)  # Read first band with masking
        #profile = src.profile

        summarize_raster(raster_src, raster_data)

    return

if __name__ == '__main__':

    main()
