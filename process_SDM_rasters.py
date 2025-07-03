# Standard-library imports.
import json
import logging
import os

import numpy as np

# Imports from within this package.
from analyse_rasters.do_binning import bin_raster_for_all_polygon_groups
from analyse_rasters.find_polygon_intersections_with_raster import (
        find_which_polygons_intersect_raster_wrapper,
        )
from analyse_rasters.get_ready_for_processing import (
        custom_JSON_encoder,
        define_dataset_paths,
        define_results_path_for_dataset,
        get_ready_wrapper,
        load_all_results_from_aws,
        )
from make_and_upload_tiles.prepare_raster_for_hosting import (
        define_raster_tileset_path,
        get_raster_percentile,
        prepare_raster_tiles_wrapper)
from make_and_upload_tiles.prepare_tiles import (
        get_max_zoom_from_manifest)
from analyse_rasters.save_admin_boundary_metadata import (
        generate_admin_boundary_json_wrapper)
from interact_with_aws.aws_tools import (
        check_if_file_exists_on_aws,
        download_and_parse_aws,
        upload_file_to_aws)

def old_imports():
    ## Import modules from the standard library.
    #import argparse
    #from datetime import datetime
    #import json
    #import logging
    #import os
    #import sys
    #from typing import List
    #import warnings
    #
    ## Import third-party libraries.
    #import fiona
    #import geopandas as gpd
    #import numpy as np
    #import pandas as pd
    #from pyproj import CRS, Transformer
    #import rasterio
    #from rasterio.enums import Resampling
    #from rasterio.features import rasterize, shapes
    #from rasterio.io import MemoryFile
    #from rasterio.mask import mask as rasterio_mask
    #from rasterio.warp import (calculate_default_transform, reproject,
    #                            transform_bounds)
    #from rasterio.windows import from_bounds, transform
    #from shapely.geometry import (GeometryCollection, MultiPolygon, Polygon,
    #                              shape)
    #from shapely.ops import transform as sh_transform, unary_union
    #
    ## Import local modules.
    ##from custom_logging import LoggerWrapper
    #import logger_store
    #from custom_logging import initialise_logging
    #from handle_aws import aws_bucket
    ##from prepare_raster_for_hosting import prepare_cog_wrapper
    #from prepare_raster_for_hosting import prepare_raster_tiles_wrapper 
    #from save_admin_boundary_metadata import generate_admin_boundary_json_wrapper
    #
    #from utilities.handle_logging import set_up_logging
    #
    ## Define constants.
    ## EPSG_MOLLWEIDE    The identifier string for the Mollweide projection.
    #EPSG_MOLLWEIDE = "ESRI:54009"
    return

def find_intersections_and_do_binning_for_all_rasters(
        dir_data, dir_output, path_adm0, path_adm1, path_PA_gpkg,
        path_landuse, catalog, metadata_keys_to_use):

    # Loop through all the datasets in the catalog.
    for dataset_name, dataset in catalog.iterrows():
        
        # Skip datasets that are set to ignore.
        if dataset['ignore'] == 'yes':
            continue

        # Log.
        logging.info(80 * '=')
        logging.info('Processing dataset: {:}'.format(dataset_name))
        logging.info('')

        # Skip datasets that already have remote results.
        path_dataset_results = define_results_path_for_dataset(
                dir_output, dataset_name)
        exists_on_aws = check_if_file_exists_on_aws(path_dataset_results)
        if exists_on_aws:
            logging.info('Results file {:} found on AWS, skipping analysis for this dataset.'.format(path_dataset_results))
            continue
        
        # If dataset already has local results, upload to AWS.
        if os.path.exists(path_dataset_results):
            logging.info('No results file found on AWS, but found a local results file, will upload to AWS now...')

            upload_file_to_aws(path_dataset_results)

        # Do all the processing steps for this raster.
        results = find_intersections_and_do_binning_for_one_raster(
                        dir_data, path_adm0, path_adm1, path_PA_gpkg,
                        path_landuse,
                        dataset['folder'], dataset['input_file_name'],
                        dataset['band'])

        # Transfer (or update) metadata from the catalog to the results.
        for metadata_key in metadata_keys_to_use:
            
            results[metadata_key] = dataset[metadata_key]

        write_json_and_upload_to_s3(results, path_dataset_results)

    return

def write_json_and_upload_to_s3(dict_, path_):

    # Save the results as a JSON file.
    logging.info("Saving to {:}".format(path_))
    #
    try:
        with open(path_, "w") as f:
            json.dump(dict_, f, indent=2, cls = custom_JSON_encoder)
    except:
        logging.info(dict_)
        raise

    # Copy to S3.
    upload_file_to_aws(path_, overwrite = True)

    return

def find_intersections_and_do_binning_for_one_raster(dir_data, path_adm0,
        path_adm1, path_PA_gpkg, path_landuse, raster_subfolder,
        raster_file_name,
        raster_band):

    results = dict()

    # Load the (raster) habitat suitability data.
    #name_raster = 'glm_pangosnewroads_seed333_1_1.tif'
    path_raster = os.path.join(dir_data, 'raster', 'SDM',
                               raster_subfolder, raster_file_name)
    
    # Summarize the raster and determine which country polygons
    # it intersects with.
    intersections_adm0, list_of_adm0, intersections_adm1, list_of_adm1,\
            raster_summary = \
            find_which_polygons_intersect_raster_wrapper(
                            path_adm0, path_adm1, path_raster, raster_band)

    percentile_max = 99.0
    raster_summary['99pc'] = get_raster_percentile(path_raster,
                                percentile_max, raster_band)
    print('Percentile: {:.2f}, value: {:.2f}'.format(percentile_max, 
                                                     raster_summary['99pc']))

    # Bin the raster values into discrete ranges.
    bin_dtype = raster_summary['max'].dtype
    bins = list(
            np.array([0.0, 0.25, 0.50, 0.75, 1.0]) * raster_summary['99pc'])
    bins = [x.astype(bin_dtype) for x in bins]
    bins[-1] = raster_summary['max']
    logging.info('bins: {:}'.format(str(bins)))
    dict_of_polygon_GDFs = {'whole'     : None,
                            'country'   : intersections_adm0,
                            'adm1-zone' : intersections_adm1,
                            }
    polygon_id_field_dict = {'whole'    : None,
                             'country'  : 'iso3',
                             'adm1-zone': 'adm1_code',
                             }
    results = bin_raster_for_all_polygon_groups(
                                    path_raster,
                                    path_PA_gpkg,
                                    path_landuse,
                                    bins,
                                    dict_of_polygon_GDFs,
                                    list_of_adm0,
                                    polygon_id_field_dict,
                                    raster_band
                                    )

    results['adm0_list'] = list_of_adm0
    results['adm1_list'] = list_of_adm1
    results['raster_summary'] = raster_summary

    return results

def make_tiles_for_all_rasters(dir_data, dir_output, catalog, results):

    # Define tile settings.
    #max_zoom = 6
    max_zoom = 'auto'
    color_ramp_name = 'viridis_1_to_254__1000_stops'
    dataset_type = 'continuous'

    ## Loop over the datasets and create tiles for each one.
    #for dataset, raster_info in results.items():
    # Loop through all the datasets in the catalog.
    for dataset_name, dataset in catalog.iterrows():

        # Skip datasets that are set to ignore.
        if dataset['ignore'] == 'yes':
            continue

        # Log.
        logging.info(80 * '=')
        logging.info('Making tiles for dataset: {:}'.format(dataset_name))
        logging.info('')

        # Determine the bounds used for the colour stretch.
        raster_min = 0.0
        #raster_max = results[dataset_name]['raster_summary']['max']
        raster_99pc = results[dataset_name]['raster_summary']['99pc']

        # Create the tiles for this dataset.
        # (Tile creation will be skipped if already found.)
        #results[dataset]['max_zoom'] = prepare_raster_tiles_wrapper(
        prepare_raster_tiles_wrapper(
                dir_data = dir_data,
                dir_output = dir_output, 
                raster_subfolder = dataset['folder'],
                raster_input_file_name = dataset['input_file_name'],
                raster_key = dataset_name,
                band_index = dataset['band'],
                max_zoom = max_zoom,
                dataset_type = dataset_type,
                data_min = raster_min,
                data_max = raster_99pc,
                #percentile_max = 98.0,
                name_color_ramp = color_ramp_name,
                )

    return

def write_dataset_summary_file(dir_output, results):

    #def load_manifest_and_get_max_zoom(path_):

    #    manifest = json.load(open(path_, 'r'))
    #    return get_max_zoom_from_manifest(manifest)

    results_summary = dict()
    for dataset_name in results:

        results_summary[dataset_name] = dict()
        for key in results[dataset_name].keys():
            
            # Copy across the metadata, but not the bulky admin data.
            if key not in ['whole', 'country', 'adm1-zone']:

                results_summary[dataset_name][key] = \
                        results[dataset_name][key]

        # Retrieve the manifest file.
        max_zoom = 'auto'
        dir_tiles = define_raster_tileset_path(dir_output,
                        results[dataset_name]['folder'],
                        dataset_name, max_zoom)
        path_manifest = os.path.join(dir_tiles, '.tile_manifest.json')
        max_zoom = download_and_parse_aws(path_manifest,
                                          get_max_zoom_from_manifest)

        results_summary[dataset_name]['max_zoom'] = max_zoom

    # Save the results as a JSON file.
    path_summary = os.path.join(dir_output, 'raster_analysis',
                                        'results_summary.json')
    write_json_and_upload_to_s3(results_summary, path_summary)

    return

def main():
    
    # Get the project directory. 
    #dir_base = os.path.dirname(os.path.abspath(__file__))
    dir_base = ''

    # Get the catalog as well as file paths and metadata keys. 
    (dir_data, dir_output, catalog,
        path_adm0, path_adm1, path_PA_gpkg, path_landuse,
        metadata_keys_to_use) = get_ready_wrapper(dir_base)
    
    # Loop over the datasets and do the analysis.
    find_intersections_and_do_binning_for_all_rasters(
        dir_data, dir_output, path_adm0, path_adm1, path_PA_gpkg,
        path_landuse, catalog, metadata_keys_to_use)
        
    # Get all the results (not just local files).
    results = load_all_results_from_aws(dir_output, catalog)

    # Update the dictionary of admin regions.
    adm_dict = generate_admin_boundary_json_wrapper(
            results, dir_output, path_adm0, path_adm1)
    
    # Make the tiles.
    make_tiles_for_all_rasters(dir_data, dir_output, catalog, results)

    # Create and save a summary file.
    write_dataset_summary_file(dir_output, results)

    return

if __name__ == '__main__':

    main()
