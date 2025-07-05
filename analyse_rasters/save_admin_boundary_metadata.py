import json
import logging
import os

import geopandas as gpd

from interact_with_aws.aws_tools import (
        upload_file_to_aws)

def get_unique_list_from_nested_attr(dict_, key):

    combined = []
    for val in dict_.values():

        # Safely get list or empty list, and extend full list with it.
        combined.extend(val.get(key, []))

    # Get sorted unique list.
    unique_sorted = sorted(set(combined))

    return unique_sorted

def generate_admin_boundary_json_wrapper(results, dir_output, path_adm0,
                                         path_adm1):

    # Get a list of all the admin-0 and and admin-1 zones covered by
    # all the rasters.
    all_adm0 = get_unique_list_from_nested_attr(results, 'adm0_list')
    all_adm1 = get_unique_list_from_nested_attr(results, 'adm1_list')
    logging.info('Admin-0 and admin-1 zones covered:')
    logging.info(all_adm0)
    logging.info(all_adm1)

    ## Load the old admin boundary information.
    path_admin_boundary_json = os.path.join(dir_output, 'adm_bdry_info.json')
    #if os.path.exists(path_admin_boundary_json):
    #    with open(path_admin_boundary_json, 'r', encoding='utf-8') as f:
    #        old_adm_dict = json.load(f)
    #else:
    #    old_adm_dict = None

    # Generate the new admin boundary information.
    adm_dict = generate_admin_boundary_json(path_adm0, path_adm1, all_adm0,
                                            all_adm1)

    #if (adm_dict == old_adm_dict):

    #    logging.info('The admin boundary information matches the previous file {:}, no need to update.'.format(path_admin_boundary_json))

    #else:

    #    logging.info('The admin boundary information has changed, updating file {:}.'.format(path_admin_boundary_json))
    logging.info('Writing admin boundary info to {:}'.format(
        path_admin_boundary_json))
    with open(path_admin_boundary_json, 'w', encoding='utf-8') as f:
        json.dump(adm_dict, f,
                  indent=4,
                  ensure_ascii=False,
                  #cls = custom_JSON_encoder,
                  )

    upload_file_to_aws(path_admin_boundary_json, overwrite = True)

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

        if (row['shapeType'] != 'ADM0'):
            is_disputed = 'yes'
        else:
            is_disputed = 'no'
        
        adm_dict['adm0'][iso3] = {
            'name': fix_mojibake_encoding(row['name']),
            'bbox': [bounds[0], bounds[1], bounds[2], bounds[3]],  # [lon_min, lat_min, lon_max, lat_max]
            'is_disputed' : is_disputed,
        }

    for adm1_code in adm1_list:
        row = gdf_adm1.loc[adm1_code]
        # Get bounding box from geometry
        bounds = row.geometry.bounds  # returns (minx, miny, maxx, maxy)
        
        adm_dict['adm1'][adm1_code] = {
            'name': fix_mojibake_encoding(row['name']),
            'adm0_iso3': row['adm0_iso3'],
            'bbox': [bounds[0], bounds[1], bounds[2], bounds[3]]  # [lon_min, lat_min, lon_max, lat_max]
        }

    return adm_dict

def fix_mojibake(text):
    """
    Fix mojibake in a single string

    Args:
        text (str): String with mojibake patterns

    Returns:
        str: Fixed string with proper UTF-8 characters
    """
    if not isinstance(text, str):
        return text

    # Method 1: Direct replacement (fastest for known patterns)
    replacements = {
        'Ã³': 'ó',  # RegiÃ³n → Región
        'Ã¡': 'á',  # TarapacÃ¡ → Tarapacá
        'Ã©': 'é',  # café → café
        'Ã±': 'ñ',  # España → España
        'Ãº': 'ú',  # Perú → Perú
        'Ã­': 'í',  # México → México
        'Ã ': 'à',  # là → là
        'Ã¨': 'è',  # très → très
        'Ã¬': 'ì',  # così → così
        'Ã²': 'ò',  # però → però
        'Ã¹': 'ù',  # più → più
        'Ã§': 'ç',  # français → français
        'Ã¼': 'ü',  # über → über
        'Ã¶': 'ö',  # schön → schön
        'Ã¤': 'ä',  # mädchen → mädchen
    }

    for mojibake, correct in replacements.items():
        text = text.replace(mojibake, correct)

    return text

def fix_mojibake_encoding(text):
    """
    Fix mojibake using encoding conversion

    Args:
        text (str): String with mojibake patterns

    Returns:
        str: Fixed string
    """
    try:
        # Try to encode as Latin-1 then decode as UTF-8
        return text.encode('latin-1').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        # If that fails, fall back to direct replacement
        return fix_mojibake(text)
