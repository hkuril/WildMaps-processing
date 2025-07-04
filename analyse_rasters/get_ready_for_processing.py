import os
import json
import logging

import numpy as np
import pandas as pd

from interact_with_aws.aws_tools import (download_file_from_aws,
                                         download_and_parse_aws,
                                         upload_file_to_aws)
from utilities.handle_logging import set_up_logging

def get_ready_wrapper(dir_base):

    # Define file paths.
    dir_data = os.path.join(dir_base, 'data_inputs')
    dir_output = os.path.join(dir_base, 'data_outputs')
    path_catalog = os.path.join(dir_data, 'catalogs', 'dataset_catalog.csv')
    
    # Set up logging.
    set_up_logging(dir_output)

    # Load remote catalog.
    catalog_remote = load_remote_catalog(path_catalog)
    
    # Load local catalog.
    catalog_local = parse_catalog(path_catalog)

    # Sync catalogs.
    catalog = sync_catalogs(path_catalog, catalog_remote, catalog_local)

    # Define paths for admin polygons and protected areas.
    path_adm0, path_adm1, path_PA_gpkg, path_landuse =\
            define_dataset_paths(dir_data)

    # Define which catalog metadata keys will be transferred to the raster’s 
    # metadata.
    metadata_keys_to_use = ['folder', 'input_file_name',
                            'common_name', 'region', 'subregion',
                            'source_link', 'source_text', 'download_link',
                            'source_contact',
                            'band']

    return (dir_data, dir_output, catalog, 
            path_adm0, path_adm1, path_PA_gpkg, path_landuse,
            metadata_keys_to_use)

def load_remote_catalog(path_catalog):
    
    catalog = download_and_parse_aws(path_catalog, parse_catalog)

    return catalog

def load_results_and_catalog_and_remove_results_no_longer_in_catalog(
        dir_output, dir_data):

    ## The catalog tells us which files need to be processed.
    #path_catalog = os.path.join(dir_data, 'catalogs', 'dataset_catalog.csv')
    #catalog = load_dataset_catalog(path_catalog)

    ## Load any existing output, to avoid repeat calculations.
    #path_results = os.path.join(dir_output, 'results.json')
    #results = load_results(path_results)

    ## Clear any rows from the results that are no longer found in the
    ## catalog (i.e. they were deleted from the catalog file).
    #results_updated = {}
    #for k, v in results.items():

    #    if k in catalog.index:

    #        results_updated[k] = v

    #    else:

    #        logging.info('The dataset {:} was found in the results file {:} but is not listed in the catalog file {:}, so it will be removed from the results file.'.format(k, path_results, path_catalog))

    #results = results_updated

    #return catalog, results, path_results
    return None

def parse_catalog(path_catalog):
    
    logging.info('Loading catalog from {:}'.format(path_catalog))
    catalog = pd.read_csv(path_catalog)
    print(catalog)

    catalog['key'] = create_key(catalog, ['folder', 'subregion', 'common_name'])

    # Handle 'subregion' == 'none' cases
    none_mask = (catalog['subregion'] == 'none')
    if none_mask.any(): 
        catalog.loc[none_mask, 'key'] = create_key(
            catalog.loc[none_mask],
            ['folder', 'region', 'common_name']
        )

    catalog.set_index('key', inplace = True)
    
    #catalog = catalog[catalog['ignore'] == 'no']
    #catalog.drop(columns = 'ignore', inplace = True)
   
    return catalog 

def create_key(df, columns):
    """Create a key by joining specified columns with underscores and cleaning."""

    return (
        df[columns]
        .astype(str)
        .agg('_'.join, axis=1)
        .str.replace(r'[\W\s]+', '_', regex=True)
        .str.strip('_')
    )

def sync_catalogs(path_catalog, catalog_remote, catalog_local):

    # Get remote entries that don't have matching indices in local catalog
    remote_only = catalog_remote[~catalog_remote.index.isin(
                        catalog_local.index)]
    
    # Concatenate local catalog with non-duplicate remote entries
    synced_catalog = pd.concat([catalog_local, remote_only])

    # Overwrite local catalog.
    logging.info(f"Saving to {path_catalog}")
    synced_catalog.to_csv(path_catalog, index=False)

    # Overwrite remote catalog.
    upload_file_to_aws(path_catalog, overwrite=True)
    
    return synced_catalog

def load_results(path_results):

    #if not os.path.exists(path_results):
    #    logging.info("No existing results file found at {:}.".format(path_results))
    #    return {}
    #
    #logging.info("Loading existing results file at {:}".format(path_results))
    #with open(path_results, 'r', encoding='utf-8') as f:
    #    results = json.load(f)

    ## Log the previous results. 
    #logging.info('Existing results:')
    #logging.info(json.dumps(results, indent=4, cls = custom_JSON_encoder))

    return results

def define_dataset_paths(dir_data):

    # Define file path for (vector) country polygons
    # (also known as admin level 0 boundaries).
    dir_geoBoundaries = os.path.join(dir_data, 'vector', 'admin_boundaries',
                             'geoBoundaries')
    path_adm0 = os.path.join(dir_geoBoundaries, 'geoBoundariesCGAZ_ADM0_repaired_twice.gpkg')
    path_adm1 = os.path.join(dir_geoBoundaries, 'geoBoundariesCGAZ_ADM1_repaired_twice.gpkg')
    
    testing = False
    if testing:

        # Load the (vector) protected area polygons.
        path_PA_gpkg = os.path.join(
                                dir_data, 'vector', 'protected_areas', 'WDPA',
                                'WDPA_Jun2025_Public-polygons_brunei_only.gpkg')

        path_landuse = os.path.join(dir_data, 'raster', 'land_use',
                        'copernicus',
                        'copernicus_clms_land_cover_global_100m_epsg4326_small_version_for_testing.tif')

    else:

        # Load the (vector) protected area polygons.
        path_PA_gpkg = os.path.join(
                                dir_data, 'vector', 'protected_areas', 'WDPA',
                                'WDPA_Jun2025_Public-polygons.gpkg')

        path_landuse = os.path.join(dir_data, 'raster', 'land_use',
                        'copernicus',
                        'copernicus_clms_land_cover_global_100m_epsg4326.tif')

    return path_adm0, path_adm1, path_PA_gpkg, path_landuse

def define_results_path_for_dataset(dir_output, dataset_name):

    file_dataset_results = 'results_{:}.json'.format(dataset_name)
    path_dataset_results = os.path.join(dir_output, 'raster_analysis',
                                        file_dataset_results)

    return path_dataset_results

def load_all_results_from_aws(dir_output, catalog):
    
    read_json = lambda filename: json.load(open(filename, 'r'))

    results = dict()
    for dataset_name, dataset in catalog.iterrows():

        # Skip datasets that are set to ignore.
        if dataset['ignore'] == 'yes':
            continue

        path_dataset_results = define_results_path_for_dataset(
                dir_output, dataset_name)

        results[dataset_name] = download_and_parse_aws(
                path_dataset_results, read_json)

    return results

class custom_JSON_encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        return super().default(obj)
    
    def iterencode(self, obj, _one_shot=False):
        # Convert all keys before any encoding happens
        obj = self._convert_keys_recursive(obj)
        return super().iterencode(obj, _one_shot)
    
    def _convert_keys_recursive(self, obj):
        if isinstance(obj, dict):
            return {
                (k.item() if isinstance(k, (np.integer, np.floating)) else k): self._convert_keys_recursive(v)
                for k, v in obj.items()
            }
        elif isinstance(obj, (list, tuple)):
            return [self._convert_keys_recursive(item) for item in obj]
        else:
            return obj
