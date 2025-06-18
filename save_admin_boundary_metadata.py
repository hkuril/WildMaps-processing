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
        with open(path_admin_boundary_json, "w") as f:

            json.dump(adm_dict, f,
                      indent=4,
                      #cls = custom_JSON_encoder,
                      )

    return adm_dict

def generate_admin_boundary_json(path_adm0, path_adm1, adm0_list, adm1_list):

    # Load the country outlines (admin-0 boundaries).
    #logger_store.log.info("Loading adm-0 file {:}".format(path_adm0))
    gdf_adm0 = gpd.read_file(path_adm0)
    gdf_adm0.set_index('iso3', inplace = True)

    # Load the admin-1 boundaries.
    #logger_store.log.info("Loading adm-1 file {:}".format(path_adm1))
    gdf_adm1 = gpd.read_file(path_adm1)
    gdf_adm1.set_index('adm1_code', inplace = True)
    
    # Store information in dictionary.
    adm_dict= {}
    adm_dict['adm0'] = {}
    adm_dict['adm1'] = {}
    #
    for iso3 in adm0_list:

        row = gdf_adm0.loc[iso3]
        adm_dict['adm0'][iso3] = {
                'name' : gdf_adm0.loc[iso3]['name'] 
                }

    for adm1_code in adm1_list:
        
        row = gdf_adm1.loc[adm1_code]
        adm_dict['adm1'][adm1_code] = {
                'name' : row['name'],
                'adm0_iso3' : row['adm0_iso3'],
                }

    #logger_store.log.info(json.dumps(adm_dict, indent = 4))

    return adm_dict
