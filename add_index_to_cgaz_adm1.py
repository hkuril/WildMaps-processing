import argparse

import fiona
import geopandas as gpd

def parse_args():
    parser = argparse.ArgumentParser(description = 
                "The adm-1 files downloaded from CGAZ are good but they "
                "don’t have any convenient ID code. This script takes the "
                "geopackage and generates a unique ID string for each "
                "zone, using on country ISO3 followed by position in an "
                "alphabetical list in English for that country, such as "
                "'USA_001' for Alabama."
                )
    parser.add_argument('path_gpkg',
                        type=str,
                        help='Path to the geopackage file containing the CGAZ adm1 boundaries. Note that the field "shapeName" should be changed to "name", and "shapeGroup" should be changed to "adm_iso3".')


    args = parser.parse_args()

    return args

def main():

    # Get the path to the geopackage from the command line.
    args = parse_args()
    path_adm1 = args.path_gpkg

    # Load the GeoPackage (assumes there is only one layer).
    #layer_name = gpd.io.file.fiona.listlayers(path_adm1)[0]
    layer_name = fiona.listlayers(path_adm1)[0]
    gdf = gpd.read_file(path_adm1, layer=layer_name)

    # Group by 'adm0_iso' and sort by 'name' within each group
    groups = gdf.groupby('adm0_iso3', sort=False)
    
    # Create a list to track the new adm1_code values
    adm1_codes = []
    
    # Process each group
    for adm0_iso3, group in groups:
        sorted_group = group.sort_values('name')
        print(f"{adm0_iso3}: {len(sorted_group)} items")
        # Generate padded index for each item in group
        for i in range(len(sorted_group)):
            code = f"{adm0_iso3}_{str(i+1).zfill(3)}"
            adm1_codes.append(code)
    
    # Assign new column in the correct order
    # Since the groupby breaks the original order, we must reprocess carefully
    gdf_sorted = (
        gdf.groupby('adm0_iso3', group_keys=False)
           .apply(lambda x: x.sort_values('name'))
           .reset_index(drop=True)
    )
    gdf_sorted['adm1_code'] = [
        f"{adm0_iso3}_{str(i+1).zfill(3)}"
        for adm0_iso3, group in gdf_sorted.groupby('adm0_iso3')
        for i in range(len(group))
    ]
    
    # Overwrite the original file
    print('Re-writing {:}'.format(path_adm1))
    gdf_sorted.to_file(path_adm1, layer=layer_name, driver='GPKG')

    return

if __name__ == '__main__':

    main()
