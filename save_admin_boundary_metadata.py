import json
import os

import geopandas as gpd

import logger_store

def generate_admin_boundary_json_wrapper(dir_output, path_adm0, path_adm1,
                                         adm0_list, adm1_list):

    # Load the old admin boundary information.
    path_admin_boundary_json = os.path.join(dir_output, 'adm_bdry_info.json')
    if os.path.exists(path_admin_boundary_json):
        with open(path_admin_boundary_json, 'r', encoding='utf-8') as f:
            old_adm_dict = json.load(f)
    else:
        old_adm_dict = None

    # Generate the new admin boundary information.
    adm_dict = generate_admin_boundary_json(path_adm0, path_adm1, adm0_list,
                                            adm1_list)

    if (adm_dict == old_adm_dict):

        logger_store.log.info('The admin boundary information matches the previous file {:}, no need to update.'.format(path_admin_boundary_json))

    else:

        logger_store.log.info('The admin boundary information has changed, updating file {:}.'.format(path_admin_boundary_json))
        with open('adm_bdry_info.json', 'w', encoding='utf-8') as f:
            json.dump(adm_dict, f,
                      indent=4,
                      ensure_ascii=False,
                      #cls = custom_JSON_encoder,
                      )

    return adm_dict

def generate_admin_boundary_json(path_adm0, path_adm1, adm0_list, adm1_list):

    # Load the country outlines (admin-0 boundaries).
    gdf_adm0 = gpd.read_file(path_adm0)
    gdf_adm0.set_index('iso3', inplace = True)

    # Load the admin-1 boundaries.
    gdf_adm1 = gpd.read_file(path_adm1)
    gdf_adm1.set_index('adm1_code', inplace = True)
    
    # Store information in dictionary.
    adm_dict= {}
    adm_dict['adm0'] = {}
    adm_dict['adm1'] = {}
    
    for iso3 in adm0_list:
        row = gdf_adm0.loc[iso3]
        # Get bounding box from geometry
        bounds = row.geometry.bounds  # returns (minx, miny, maxx, maxy)
        
        adm_dict['adm0'][iso3] = {
            'name': row['name'],
            'bbox': [bounds[0], bounds[1], bounds[2], bounds[3]]  # [lon_min, lat_min, lon_max, lat_max]
        }

    for adm1_code in adm1_list:
        row = gdf_adm1.loc[adm1_code]
        # Get bounding box from geometry
        bounds = row.geometry.bounds  # returns (minx, miny, maxx, maxy)
        
        adm_dict['adm1'][adm1_code] = {
            'name': row['name'],
            'adm0_iso3': row['adm0_iso3'],
            'bbox': [bounds[0], bounds[1], bounds[2], bounds[3]]  # [lon_min, lat_min, lon_max, lat_max]
        }

    return adm_dict
