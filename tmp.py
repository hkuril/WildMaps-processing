import os
import json
import geopandas as gpd

def update_admin_boundary_json_with_bbox(path_adm0, path_adm1, path_json):
    """
    Temporary script to add bounding boxes to existing admin boundary JSON
    """
    
    # Load existing JSON
    with open(path_json, 'r', encoding='utf-8') as f:
        adm_dict = json.load(f)
    
    # Extract unique adm0 and adm1 codes from existing JSON
    adm0_list = list(adm_dict.get('adm0', {}).keys())
    adm1_list = list(adm_dict.get('adm1', {}).keys())
    
    print(f"Found {len(adm0_list)} adm0 entries: {adm0_list}")
    print(f"Found {len(adm1_list)} adm1 entries: {adm1_list[:5]}...")  # Show first 5
    
    # Load the country outlines (admin-0 boundaries)
    print("Loading adm0 file...")
    gdf_adm0 = gpd.read_file(path_adm0)
    gdf_adm0.set_index('iso3', inplace=True)

    # Load the admin-1 boundaries
    print("Loading adm1 file...")
    gdf_adm1 = gpd.read_file(path_adm1)
    gdf_adm1.set_index('adm1_code', inplace=True)
    
    # Update adm0 entries with bounding boxes
    print("Adding bounding boxes to adm0 entries...")
    for iso3 in adm0_list:
        if iso3 in gdf_adm0.index:
            row = gdf_adm0.loc[iso3]
            bounds = row.geometry.bounds  # (minx, miny, maxx, maxy)
            adm_dict['adm0'][iso3]['bbox'] = [bounds[0], bounds[1], bounds[2], bounds[3]]
        else:
            print(f"Warning: {iso3} not found in adm0 shapefile")
    
    # Update adm1 entries with bounding boxes
    print("Adding bounding boxes to adm1 entries...")
    for adm1_code in adm1_list:
        if adm1_code in gdf_adm1.index:
            row = gdf_adm1.loc[adm1_code]
            bounds = row.geometry.bounds  # (minx, miny, maxx, maxy)
            adm_dict['adm1'][adm1_code]['bbox'] = [bounds[0], bounds[1], bounds[2], bounds[3]]
        else:
            print(f"Warning: {adm1_code} not found in adm1 shapefile")
    
    # Save updated JSON
    output_path = path_json.replace('.json', '_with_bbox.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(adm_dict, f, indent=4, ensure_ascii=False)
    
    print(f"Updated JSON saved to: {output_path}")
    return adm_dict

# Usage example:
if __name__ == "__main__":
    # Update these paths as needed
    dir_data = '/Users/hrmd/Documents/work/chrishen/data'
    dir_geoBoundaries = os.path.join(dir_data, 'vector', 'admin_boundaries',
                             'geoBoundaries')
    path_adm0 = os.path.join(dir_geoBoundaries, 'geoBoundariesCGAZ_ADM0_repaired_twice.gpkg')
    path_adm1 = os.path.join(dir_geoBoundaries, 'geoBoundariesCGAZ_ADM1_repaired_twice.gpkg')
    
    path_json = os.path.join(dir_data, 'code_output', "adm_bdry_info.json")
    
    updated_dict = update_admin_boundary_json_with_bbox(path_adm0, path_adm1, path_json)
