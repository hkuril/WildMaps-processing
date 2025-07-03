import logging

import geopandas as gpd
import numpy as np
import rasterio
#from rasterio.features import shapes
from shapely.geometry import (GeometryCollection, MultiPolygon, Polygon)
#from shapely.ops import unary_union

from analyse_rasters.raster_utils import (
        get_non_null_region_of_raster_as_multipolygon,
        summarise_raster,
        )
from utilities.handle_vector_files import load_gpkg_filtered_by_list_as_gdf

def find_which_polygons_intersect_raster_wrapper(path_adm0, path_adm1, path_raster, raster_band):
    
    # Load the country outlines (admin-0 boundaries).
    logging.info("Loading adm-0 file {:}".format(path_adm0))
    gdf_adm0 = gpd.read_file(path_adm0)

    # Load the raster, read the first band (with masking), and print summary.
    logging.info("Loading raster file {:}".format(path_raster))
    raster_src = rasterio.open(path_raster)
    raster_data = raster_src.read(raster_band, masked=True)
    raster_summary = summarise_raster(raster_src, raster_data)

    # Determine which countries the raster intersects with.
    cols_to_keep = ['name', 'iso3']
    region_name_with_plural = ['country', 'countries']
    intersections_adm0 = find_which_polygons_intersect_raster(
                                            gdf_adm0,
                                            raster_data, raster_src,
                                            cols_to_keep,
                                            region_name_with_plural,
                                            id_field = 'iso3')

    # Get a list of the ISO codes of the countries intersected.
    list_of_adm0 = sorted(list(intersections_adm0['iso3'].unique()))

    # Load admin-1 boundaries, but only those that are for countries which
    # intersect the raster.
    filter_field = 'adm0_iso3'
    gdf_adm1 = load_gpkg_filtered_by_list_as_gdf(path_adm1,
                            filter_field, list_of_adm0)
    logging.info('')

    # Determine which admin-1 areas the raster intersects with.
    cols_to_keep = ['name', 'adm0_iso3', 'adm1_code']
    region_name_with_plural = ['adm1 zone', 'adm1 zones']
    intersections_adm1 = find_which_polygons_intersect_raster(
                                            gdf_adm1,
                                            raster_data, raster_src,
                                            cols_to_keep,
                                            region_name_with_plural,
                                            id_field = 'adm1_code')

    # Get a list of the codes of the admin-1 zones intersected.
    list_of_adm1 = sorted(list(intersections_adm1['adm1_code'].unique()))

    return  intersections_adm0, list_of_adm0,\
            intersections_adm1, list_of_adm1, \
            raster_summary

def find_which_polygons_intersect_raster(polygons, raster_data, raster_src,
                                         cols_to_keep, region_name_with_plural,
                                         id_field = 'iso3'):

    logging.info(80 * '-')
    logging.info("Finding which {:} intersect with the raster.".format(
        region_name_with_plural[1]))

    # Unpack raster information.
    transform = raster_src.transform
    raster_crs = raster_src.crs

    # Get the non-null part of the raster as a MultiPolygon.
    raster_geom = get_non_null_region_of_raster_as_multipolygon(
            raster_data, transform)

    # Reproject both the raster geometry and the polygons into the same
    # CRS (the default is a global equal-area CRS, the Mollweide projection).
    EPSG_MOLLWEIDE = "ESRI:54009"
    crs_for_intersections = EPSG_MOLLWEIDE
    raster_geom = gpd.GeoSeries([raster_geom], crs=raster_crs).to_crs(
                    crs_for_intersections).iloc[0]
    polygons = polygons.to_crs(crs_for_intersections)
    
    # Find the intersections between the raster outline and the
    # polygons.
    intersections = find_intersection_regions_between_polygons_and_raster(
                        polygons, raster_geom, cols_to_keep)

    # Calculate areas of intersection, as numbers and fractions.
    raster_total_area_km2, intersections = \
            get_intersection_area_summary_values(raster_geom, intersections)

    # Decide which rows to discard.
    intersections = apply_thresholds_to_discard_intersection_areas(
                        intersections)

    # Print summary.
    print_intersection_area_summary(raster_total_area_km2, intersections,
                                    region_name_with_plural,
                                    id_field = id_field)

    # Discard minor intersections.
    intersections = intersections[~intersections['discard']]
    intersections.drop(columns = ['discard'], inplace = True)
    
    return intersections

def find_intersection_regions_between_polygons_and_raster(polygons, raster_geom, cols_to_keep):

    # Find where the raster’s outline intersects the polygons.
    intersections = []
    # Loop through the polygons.
    for idx, polygon in polygons.iterrows():

        # For each polygon, find the part which intersects the
        # outline of the raster.
        data_to_store = \
            find_intersection_between_one_polygon_and_raster(
                    polygon, raster_geom, cols_to_keep)

        # Store in the list.
        if data_to_store is not None:

            intersections.append(data_to_store)

    # Convert the list to a GeoDataFrame.
    intersections = gpd.GeoDataFrame(intersections, crs = polygons.crs)

    return intersections

def find_intersection_between_one_polygon_and_raster(polygon, raster_geom, cols_to_keep):

    # Calculate intersection.
    intersection = polygon.geometry.intersection(raster_geom)

    # Store the intersection (if there is any).
    if not intersection.is_empty:

        # Tidy up the geometry (there can be some Line features
        # which have no area).
        if isinstance(intersection, GeometryCollection):
            
            intersection = geometryCollection_to_multipolygon(
                    intersection)

        else:

            assert  isinstance(intersection, MultiPolygon) or \
                    isinstance(intersection, Polygon), \
                    'Expected a Polygon or MultiPolygon shapely geometry, '\
                    'but instead got {:}'.format(type(intersection))

        # Store the intersection in a list.
        data_to_store = {
            'original_poly_geometry' : polygon.geometry,
            'geometry' : intersection,
            }
        for col in cols_to_keep:
            data_to_store[col] = polygon[col]

    else:

        data_to_store = None

    return data_to_store

def geometryCollection_to_multipolygon(geom_collection: GeometryCollection) -> MultiPolygon:
    """
    Extract all polygons and multipolygons from a GeometryCollection,
    filtering out points and linestrings, and return as a single MultiPolygon.

    Args:
        geom_collection: A Shapely GeometryCollection

    Returns:
        MultiPolygon containing all polygon geometries from the collection

    Raises:
        ValueError: If input is not a GeometryCollection
        ValueError: If no polygons are found in the collection
    """
    if not isinstance(geom_collection, GeometryCollection):
        raise ValueError("Input must be a GeometryCollection")

    polygons: List[Polygon] = []

    for geom in geom_collection.geoms:
        if isinstance(geom, Polygon):
            polygons.append(geom)
        elif isinstance(geom, MultiPolygon):
            # Extract individual polygons from MultiPolygon
            polygons.extend(list(geom.geoms))
        # Skip Points, LineStrings, and other geometry types

    if not polygons:
        raise ValueError("No polygons found in the GeometryCollection")

    return MultiPolygon(polygons)

def get_intersection_area_summary_values(raster_geom, intersections):

    raster_total_area_km2 = raster_geom.area / 1.0E6

    intersections['area_of_intersection_km2'] = intersections['geometry'].area / 1.0E6
    intersections['area_of_original_poly_km2'] = \
        intersections['original_poly_geometry'].apply(
                lambda geom: geom.area / 1.0E6)

    # Calculate fractions.
    intersections['frac_of_raster'] = (
        intersections['area_of_intersection_km2'] / raster_total_area_km2)
    #
    intersections['frac_of_original_poly'] = (
        intersections['area_of_intersection_km2'] / 
        intersections['area_of_original_poly_km2'])

    # Sort by area of intersection.
    intersections.sort_values(by = 'area_of_intersection_km2', inplace = True,
                              ascending = False)

    return raster_total_area_km2, intersections

def print_intersection_area_summary(raster_total_area_km2, intersections,
                                    region_name_with_plural, id_field = 'iso3',
                                    name_field = 'name'):

    logging.info('The area covered by the raster (not including null pixels) is: {:,.1f} km2'.format(raster_total_area_km2))
    if len(intersections) == 1:
        region_str = region_name_with_plural[0]
    else:
        region_str = region_name_with_plural[1]
    logging.info('The raster intersects with {:d} {:}:'.format(len(intersections), region_str))
    region_str = region_name_with_plural[0]
    row_fmt = '{:7} {:20} {:>20,.1f} {:>20,.1f} {:>15,.4f} {:>15,.4f} {:>7}'
    row_header_fmt = '{:7} {:20} {:>20} {:>20} {:>15} {:>15} {:>7}'
    logging.info(row_header_fmt.format('iso3', region_str, 'intersection (km2)', '{:} area (km2)'.format(region_str), '% of {:}'.format(region_str), '% of raster', 'discard'))
    for _, intersection in intersections.iterrows():
        
        if intersection['discard']:
            discard_str = 'yes'
        else:
            discard_str = 'no'
        logging.info(row_fmt.format(
                        intersection[id_field],
                        intersection[name_field][:20],
                        intersection['area_of_intersection_km2'],
                        intersection['area_of_original_poly_km2'],
                        intersection['frac_of_original_poly'] * 100.0,
                        intersection['frac_of_raster'] * 100.0,
                        discard_str,
                    ),
                )

    return

def apply_thresholds_to_discard_intersection_areas(intersections):

    thresh_poly_frac = 0.01
    thresh_raster_frac = 0.01
    intersections['discard'] = (
            (intersections['frac_of_original_poly'] < thresh_poly_frac) &
            (intersections['frac_of_raster'] < thresh_poly_frac))

    return intersections
