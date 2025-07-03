import logging

import fiona
import geopandas as gpd

def load_gpkg_filtered_by_list_as_gdf(gpkg_path, filter_field,                  
                                      allowed_list, layer_name=None, additional_sql=None):                                               
    """                                                                             
    Load features from a GeoPackage filtered by ISO3 codes.                     
                                                                                
    Parameters:                                                                 
        gpkg_path (str): Path to the GeoPackage file.                           
        layer_name (str): Name of the layer within the GeoPackage.              
        filter_field (str): Field name to filter by.
        allowed_list (list): List of values to filter by.
        additional_sql (str, optional): Additional SQL WHERE clause to append.
                                                                                                         
    Returns:                                                                    
        geopandas.GeoDataFrame: Filtered GeoDataFrame.                          
    """                                                                         
                                                                                                                                              
    if layer_name is None:                                                          
        layers = fiona.listlayers(gpkg_path)                                            
        assert len(layers) == 1, "If you don't specify a layer name, the geopackage file must have only one layer"
        layer_name = layers[0]                                                   
                                                                                        
    list_str = ", ".join(f"'{val}'" for val in allowed_list)
    
    # Build the SQL query
    base_where = f"{filter_field} IN ({list_str})"
    
    if additional_sql:
        where_clause = f"({base_where}) AND ({additional_sql})"
    else:
        where_clause = base_where
        
    sql = f"SELECT * FROM {layer_name} WHERE {where_clause}"        
                                                                                    
    logging.info('Loading from {:}\nwith query {:}'.format(gpkg_path, sql))     
                                                                                    
    return gpd.read_file(gpkg_path, sql=sql)
