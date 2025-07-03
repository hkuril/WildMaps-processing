import logging

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.mask import mask as rasterio_mask
from rasterio.windows import from_bounds

from utilities.handle_vector_files import (
        load_gpkg_filtered_by_list_as_gdf)

def clip_raster_to_polygon_and_apply_PA_mask(
        polygon, raster_src, PA_mask):

    # Clip the raster by the polgyon.
    data_clipped, transform_clipped = clip_raster_to_polygon(polygon,
                                                             raster_src)
    if PA_mask is not None:
        # Apply the PA mask.
        data_clipped_and_masked = \
                apply_full_size_mask_to_clipped_raster(raster_src,
                                                       data_clipped,
                                               transform_clipped, PA_mask)
    else:
        data_clipped_and_masked = None

    return data_clipped, data_clipped_and_masked

def clip_raster_to_polygon(polygon, raster_src):
    
    # Get a geoJSON-like representation of the polygon geometry.
    polygon_geom_json = [polygon.__geo_interface__]
    
    # Clip the raster with the polygon.
    raster_data_clipped_to_poly, \
    raster_transform_clipped_to_poly = rasterio_mask(raster_src,
                                            polygon_geom_json,
                                            crop = True,
                                            filled = True)

    # Drop band axis,  if single-band.
    raster_data_clipped_to_poly = raster_data_clipped_to_poly[0]
    
    # Re-apply the nodata mask.
    nodata = raster_src.nodata
    raster_data_clipped_to_poly = np.ma.masked_equal(
                                    raster_data_clipped_to_poly, nodata)
    
    return raster_data_clipped_to_poly, raster_transform_clipped_to_poly

def apply_full_size_mask_to_clipped_raster(raster_src_unclipped,
                                           data_clipped, transform_clipped,
                                           mask):

    # Get bounds of clipped raster
    clipped_bounds = rasterio.transform.array_bounds(
        data_clipped.shape[0], data_clipped.shape[1], transform_clipped)
    
    # Get the window of the original raster that corresponds to
    # the clipped bounds.
    clipping_window = from_bounds(*clipped_bounds,
                              transform = raster_src_unclipped.transform)
    
    # Read the relevant portion of the full mask using the clipping window.
    i0 = int(round(clipping_window.row_off))
    i1 = int(round(clipping_window.row_off + clipping_window.height))
    j0 = int(round(clipping_window.col_off))
    j1 = int(round(clipping_window.col_off + clipping_window.width))
    #
    clipped_mask = mask[i0 : i1, j0 : j1]

    # Apply the clipped mask to the clipped raster (taking into account
    # any mask that the clipped raster already has).
    data_masked = update_mask(data_clipped, clipped_mask == 0, np.logical_or)

    return data_masked

def load_protected_areas_for_raster_clipping(path_PA_gpkg,
                        adm0_list, raster_crs,
                        raster_shape, raster_transform):
    
    logging.info('\n' + 80 * '-')
    logging.info('Preparing protected areas mask, to use in clipping')
    # Load the protected areas (only for the countries that the raster
    # intersects).
    filter_field = 'iso3'
    gdf_PAs = load_gpkg_filtered_by_list_as_gdf(path_PA_gpkg,
                            filter_field, adm0_list,
                            additional_sql="MARINE IN (0, 1)", # Remove marine PAs.
                            )
    
    # Dissolve the protected areas into a single multipolygon.
    # This discards information about the protected areas, but should
    # make intersection calculations a bit faster.
    PAs_dissolved_geom = gdf_PAs.union_all()

    # Reproject the protected areas to match the raster projection.
    gdf_PAs = gpd.GeoDataFrame(geometry = [PAs_dissolved_geom],
                               crs = gdf_PAs.crs)
    gdf_PAs = gdf_PAs.to_crs(raster_crs)
    PAs_MultiPolygon = gdf_PAs.iloc[0].geometry

    # Rasterize the protected areas to create a mask.
    inside_value  = 1
    outside_value = 0
    mask_PAs = rasterize(
                    [(PAs_MultiPolygon, inside_value)],
                    out_shape = raster_shape,
                    transform = raster_transform,
                    fill = outside_value,
                    dtype = 'uint8'
                )

    return mask_PAs

def prepare_PA_masked_raster_and_metadata(polygons_GDF, i, raster_data,
                raster_src, PA_mask, landuse_src, polygon_id_field):

    # Case 1: A list of polygons has been provided.
    if polygons_GDF is not None:
        
        # Unpack the name, geometry, and ISO code.
        polygon = polygons_GDF.iloc[i]
        #
        polygon_name = polygon['name']
        polygon_id = polygon[polygon_id_field]
        polygon_geom = polygon['geometry']
        #

        # Use the polygon to clip the raster. Also, get a version
        # that has secondary clipping by the protected areas.
        raster_data, raster_data_masked =\
                clip_raster_to_polygon_and_apply_PA_mask(
                            polygon_geom, raster_src, PA_mask)

        # Use the polygon to clip the landuse raster.
        landuse_data, _ =\
                clip_raster_to_polygon_and_apply_PA_mask(
                            polygon_geom, landuse_src, PA_mask)



    # Case 2: No list of polygons has been provided (do binning 
    # for the whole raster, with no polygon clipping).
    else:

        #raster_data_i = raster_data
        raster_data_masked = update_mask(raster_data, PA_mask == 0,
                                           np.logical_or)
        polygon_name = 'whole'
        polygon_id = 'whole'

        landuse_data = landuse_src.read(1)

    return (raster_data, raster_data_masked, polygon_name, polygon_id,
            landuse_data)

def update_mask(array, new_mask, operator):

    new_mask = operator(array.mask, new_mask)
    array_mask_updated= np.ma.masked_array(array.data,
                                     mask = new_mask)

    return array_mask_updated
