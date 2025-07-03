import argparse
import os

import pandas as pd

#from handle_aws import aws_bucket, upload_to_aws
from interact_with_aws.aws_tools import (
        AWS_BUCKET as aws_bucket, upload_tiles_to_aws)
from prepare_raster_for_hosting import extract_band_and_generate_tiles
from prepare_vector_for_hosting import prepare_vector_tiles_wrapper
from utilities.handle_logging import set_up_logging

def parse_args():

    parser = argparse.ArgumentParser(description="Process habitat raster files.")
    parser.add_argument('dir_data',
                        type=str,
                        help='File path to the directory containing the raster files.')

    args = parser.parse_args()

    return args

def load_basemap_catalog():

    # The catalog tells us which files need to be processed.
    #path_catalog = os.path.join(dir_data, 'catalogs', 'basemap_catalog.csv')
    path_catalog = os.path.join('data_inputs', 'catalogs', 'basemap_catalog.csv')

    catalog = pd.read_csv(path_catalog)
    catalog.set_index('key', inplace = True)
    
    # Do some data validation.
    yes_no_cols = ['needs_ocean_clip', 'overwrite']
    for col in yes_no_cols:
        assert catalog[col].isin(['yes', 'no']).all()
    assert catalog['type'].isin(['raster', 'vector']).all()

    return catalog 

def prepare_raster_basemap_layer(basemap_key, layer, max_zoom):
    
    if layer['needs_ocean_clip'] == 'yes':

        raise NotImplementedError('Ocean clipping not implemented')
    
    # Define input and output paths.
    path_raster_in = os.path.join('data_inputs',
            'raster', layer['folder'], layer['input_file_name'])
    # 
    if max_zoom == 'auto':
        name_tiles_out = '{:}_auto'.format(basemap_key)
    else:
        name_tiles_out = '{:}_{:02d}'.format(basemap_key, max_zoom)


    dir_tiles = os.path.join('data_outputs', 'raster_tiles', layer['folder'],
                             name_tiles_out)
    #
    path_colour_ramp = os.path.join('data_inputs', 'colour_ramps',
                                    layer['file_colour_ramp'])
    
    extract_band_and_generate_tiles(
            path_raster_in,
            layer['band'],
            max_zoom,
            dir_tiles,
            path_colour_ramp,
            layer['dataset_type'],
            layer['overwrite'],
            data_min = layer['val_min'],
            data_max = layer['val_max'])

    # Upload to AWS. (If the tiles are already there, no transfer will be
    # done.)
    # Duplicate argument is deliberate.
    upload_tiles_to_aws(dir_tiles, dir_tiles, layer['overwrite'])

    return

def prepare_vector_basemap_layer(aws_bucket, dir_data, key, layer, max_zoom):

    if layer['needs_ocean_clip'] == 'yes':

        raise NotImplementedError('Ocean clipping not implemented')
    
    # Define input and output paths.
    path_vector_in = os.path.join(dir_data, 'vector',
                                  layer['folder'], layer['input_file_name'])
    # 
    name_tiles_out = '{:}_{:02d}'.format(key, max_zoom)
    subdir_tiles = '/'.join(['data_outputs', 'vector_tiles', layer['folder']])
    dir_tiles_out = os.path.join('',  subdir_tiles, name_tiles_out)

    attribs_to_keep = layer['attribs_to_keep'].split(';')

    prepare_vector_tiles_wrapper(
            path_vector_in, dir_tiles_out, subdir_tiles, name_tiles_out,
            max_zoom, attribs_to_keep, layer['overwrite'])

    #extract_band_and_generate_tiles(path_vector_in, layer['band'], max_zoom,
    #        dir_tiles_out, layer['val_min'], layer['val_max'],
    #        path_colour_ramp, layer['resample_method'], layer['overwrite'])

    ## Upload to AWS. (If the tiles are already there, no transfer will be
    ## done.)
    #aws_key = '/'.join([subdir_tiles, name_tiles_out])
    #upload_to_aws(dir_tiles_out, aws_bucket, aws_key, layer['overwrite'])

    return

def main():
    # !!! Currently doesn’t check if it appears on server.

    # Set up logging
    set_up_logging('data_outputs')

    catalog = load_basemap_catalog()
    #catalog = catalog.loc[['wdpa']]
    catalog = catalog.loc[['worldpop']]

    # 
    for basemap_key, layer in catalog.iterrows():
        
        if layer['type'] == 'raster':

            #max_zoom = 'auto'
            max_zoom = 8 
            prepare_raster_basemap_layer(basemap_key, layer, max_zoom)

        else:

            max_zoom = 10
            prepare_vector_basemap_layer(aws_bucket, dir_data, basemap_key,
                                         layer, max_zoom)

    return

if __name__ == '__main__':

    main()
