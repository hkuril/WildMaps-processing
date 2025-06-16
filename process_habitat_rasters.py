# Import modules from the standard library.
import argparse
from datetime import datetime
import json
import logging
import os
import sys
from typing import List
import warnings

# Import third-party libraries.
import fiona
import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import CRS, Transformer
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize, shapes
from rasterio.io import MemoryFile
from rasterio.mask import mask as rasterio_mask
from rasterio.warp import calculate_default_transform, reproject
from rasterio.windows import from_bounds, transform
from shapely.geometry import (GeometryCollection, MultiPolygon, Polygon,
                              shape)
from shapely.ops import transform as sh_transform, unary_union

# Import local modules.
from custom_logging import LoggerWrapper

# Define constants.
# EPSG_MOLLWEIDE    The identifier string for the Mollweide projection.
EPSG_MOLLWEIDE = "ESRI:54009"

# --- Setting up. -------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="Process habitat raster files.")
    parser.add_argument('dir_data',
                        type=str,
                        help='File path to the directory containing the raster files.')

    args = parser.parse_args()

    return args

def initialise_logging(dir_output):

    global log
    path_log = os.path.join(dir_output, datetime.now().strftime("log_%Y-%m-%d_%H-%M-%S.txt"))
    log = LoggerWrapper(path_log)
    log.info('Writing logs to {:}'.format(path_log))

    return

def summarize_raster(src, data):

    # Basic metadata
    projection = src.crs
    dimensions = (src.height, src.width)
    bounds = src.bounds

    # Null (masked) analysis
    total_cells = data.size
    null_cells = np.ma.count_masked(data)
    null_fraction = null_cells / total_cells

    # Non-null stats
    non_null_data = data.compressed()  # Unmask data to get only valid values
    min_val = np.min(non_null_data)
    max_val = np.max(non_null_data)
    mean_val = np.mean(non_null_data)
    median_val = np.median(non_null_data)

    summary = {
        'projection': str(projection),
        'dimensions (rows, cols)': dimensions,
        'bounds': list(bounds),
        'fraction_null': null_fraction,
        'min': min_val,
        'max': max_val,
        'mean': mean_val,
        'median': median_val
    }
    
    log.info("Basic properties of the raster file:")
    for k, v in summary.items():
        log.info("{:30} : {:50}".format(k, str(v)), show_timestamp = False)
    log.info('', show_timestamp = False)

    return summary

def load_dataset_catalog(path_catalog):
    
    log.info('Loading catalog from {:}'.format(path_catalog))
    catalog = pd.read_csv(path_catalog)
    catalog.set_index('key', inplace = True)

    return catalog 

def load_results(path_results):

    if not os.path.exists(path_results):
        log.info("No existing results file found at {:}.".format(path_results))
        return {}
    
    log.info("Loading existing results file at {:}".format(path_results))
    with open(path_results, 'r', encoding='utf-8') as f:
        results = json.load(f)

    # Log the previous results. 
    log.info('Existing results:', to_console = False)
    log.info(json.dumps(results, indent=4, cls = custom_JSON_encoder),
                                to_console = False, show_timestamp = False)

    return results

def load_results_and_catalog_and_remove_results_no_longer_in_catalog(
        dir_output, dir_data):

    # The catalog tells us which files need to be processed.
    path_catalog = os.path.join(dir_data, 'dataset_catalog.csv')
    catalog = load_dataset_catalog(path_catalog)

    # Load any existing output, to avoid repeat calculations.
    path_results = os.path.join(dir_output, 'results.json')
    results = load_results(path_results)

    # Clear any rows from the results that are no longer found in the
    # catalog (i.e. they were deleted from the catalog file).
    results_updated = {}
    for k, v in results.items():

        if k in catalog.index:

            results_updated[k] = v

        else:

            log.info('The dataset {:} was found in the results file {:} but is not listed in the catalog file {:}, so it will be removed from the results file.'.format(k, path_results, path_catalog))

    results = results_updated

    return catalog, results, path_results

def define_dataset_paths(dir_data):

    # Define file path for (vector) country polygons
    # (also known as admin level 0 boundaries).
    dir_geoBoundaries = os.path.join(dir_data, 'vector', 'admin_boundaries',
                             'geoBoundaries')
    path_adm0 = os.path.join(dir_geoBoundaries, 'geoBoundariesCGAZ_ADM0.gpkg')
    path_adm1 = os.path.join(dir_geoBoundaries, 'geoBoundariesCGAZ_ADM1.gpkg')

    # Load the (vector) protected area polygons.
    path_PA_gpkg = os.path.join(
                            dir_data, 'vector', 'protected_areas', 'WDPA',
                            'WDPA_Jun2025_Public-polygons.gpkg')

    return path_adm0, path_adm1, path_PA_gpkg

class custom_JSON_encoder(json.JSONEncoder):
    '''
    This class helps withsaving certain datatypes to JSON (such as np arrays).
    '''
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        return super().default(obj)

# --- Determine polygon intersections with the raster -------------------------
def find_intersections_and_do_binning_for_one_raster(dir_data, path_adm0,
        path_adm1, path_PA_gpkg, raster_subfolder, raster_file_name,
        raster_band, scale_factor):

    results = dict()

    # Load the (raster) habitat suitability data.
    #name_raster = 'glm_pangosnewroads_seed333_1_1.tif'
    path_raster = os.path.join(dir_data, 'raster', 'SDM',
                               raster_subfolder, raster_file_name)

    # Summarize the raster and determine which country polygons
    # it intersects with.
    intersections_adm0, list_of_adm0, intersections_adm1, list_of_adm1,\
            raster_summary = \
            find_which_polygons_intersect_raster_wrapper(
                            path_adm0, path_adm1, path_raster, raster_band)
    
    # Bin the raster values into discrete ranges.
    bins = [0.0, 0.25, 0.50, 0.75, 1.0]
    dict_of_polygon_GDFs = {'whole'     : None,
                            'country'   : intersections_adm0,
                            'adm1-zone' : intersections_adm1}
    polygon_id_field_dict = {'whole'    : None,
                             'country'  : 'iso3',
                             'adm1-zone': 'adm1_code'}
    results = bin_raster_for_all_polygon_groups(
                                    path_raster,
                                    path_PA_gpkg,
                                    bins,
                                    dict_of_polygon_GDFs,
                                    list_of_adm0,
                                    polygon_id_field_dict,
                                    raster_band,
                                    scale_factor)

    results['adm0_list'] = list_of_adm0
    results['adm1_list'] = list_of_adm1
    results['raster_summary'] = raster_summary

    return results

def find_which_polygons_intersect_raster_wrapper(path_adm0, path_adm1, path_raster, raster_band):
    
    # Load the country outlines (admin-0 boundaries).
    log.info("Loading adm-0 file {:}".format(path_adm0))
    gdf_adm0 = gpd.read_file(path_adm0)

    # Load the raster, read the first band (with masking), and print summary.
    log.info("Loading raster file {:}".format(path_raster))
    raster_src = rasterio.open(path_raster)
    raster_data = raster_src.read(raster_band, masked=True)
    raster_summary = summarize_raster(raster_src, raster_data)

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
    log.info('', show_timestamp = False)

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

    log.info(80 * '-', show_timestamp = False)
    log.info("Finding which {:} intersect with the raster.".format(
        region_name_with_plural[1]))

    # Unpack raster information.
    transform = raster_src.transform
    raster_crs = raster_src.crs

    # Get the non-null part of the raster as a MultiPolygon.
    raster_geom = get_non_null_region_of_raster_as_multipolygon(
            raster_data, transform)

    # Reproject both the raster geometry and the polygons into the same
    # CRS (the default is a global equal-area CRS, the Mollweide projection).
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

def get_non_null_region_of_raster_as_multipolygon(raster_data, transform):

    # Create a mask for non-null pixels
    valid_mask = ~raster_data.mask

    # Extract polygons from valid raster area
    # valid_shapes  A list of pairs of (geometry_dict, masked).
    # valid_polys   A list of shapely polygons, the shapes of the valid
    #               regions of the raster.
    valid_shapes = shapes(valid_mask.astype(np.uint8),
                          mask=valid_mask,
                          transform=transform)
    # shapely.geometry.shape takes a geometry dictionary and returns
    # a shapely geometry, sucha as a polygon.
    valid_polys = [shape(geom) for geom, val in valid_shapes if val == 1]

    # Combine valid raster polygons into one geometry
    raster_geom = unary_union(valid_polys)

    return raster_geom

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

    log.info('The area covered by the raster (not including null pixels) is: {:,.1f} km2'.format(raster_total_area_km2))
    if len(intersections) == 1:
        region_str = region_name_with_plural[0]
    else:
        region_str = region_name_with_plural[1]
    log.info('The raster intersects with {:d} {:}:'.format(len(intersections), region_str))
    region_str = region_name_with_plural[0]
    row_fmt = '{:7} {:20} {:>20,.1f} {:>20,.1f} {:>15,.4f} {:>15,.4f} {:>7}'
    row_header_fmt = '{:7} {:20} {:>20} {:>20} {:>15} {:>15} {:>7}'
    log.info(row_header_fmt.format('iso3', region_str, 'intersection (km2)', '{:} area (km2)'.format(region_str), '% of {:}'.format(region_str), '% of raster', 'discard'), show_timestamp = False)
    for _, intersection in intersections.iterrows():
        
        if intersection['discard']:
            discard_str = 'yes'
        else:
            discard_str = 'no'
        log.info(row_fmt.format(intersection[id_field], intersection[name_field][:20],
                intersection['area_of_intersection_km2'],
                intersection['area_of_original_poly_km2'],
                intersection['frac_of_original_poly'] * 100.0,
                intersection['frac_of_raster'] * 100.0,
                discard_str,
                ),
                show_timestamp = False)

    return

def apply_thresholds_to_discard_intersection_areas(intersections):

    thresh_poly_frac = 0.01
    thresh_raster_frac = 0.01
    intersections['discard'] = (
            (intersections['frac_of_original_poly'] < thresh_poly_frac) &
            (intersections['frac_of_raster'] < thresh_poly_frac))

    return intersections

# --- Binning the raster values -----------------------------------------------
def bin_raster_for_all_polygon_groups(path_raster, path_PA_gpkg, bins,
    dict_of_polygon_GDFs, adm0_list, polygon_id_field_dict,
    raster_band, scale_factor):

    # Load the raster and re-project if necessary.
    with rasterio.open(path_raster) as raster_src:

        # Unpack raster information.
        profile = raster_src.profile
        crs = raster_src.crs
        raster_data = raster_src.read(raster_band, masked = True)

        # The raster must be in a projected coordinate system (coordinates
        # with units of length, such as metres, as opposed to a geographic
        # coordinate system with units of degrees), otherwise the grid cells
        # will have different sizes, and cell counts will not be 
        # proportional to area.
        # So, if the raster does not already have a projected coordinate
        # system, we must indentify a suitable one and re-project the
        # raster.
        if crs is None or crs.is_geographic:

            # Reproject.
            dst_profile, dst_crs, dst_raster_data = \
                    reproject_raster_wrapper(raster_data, raster_src, profile)

            # Overwrite values.
            profile = dst_profile
            crs = dst_crs
            raster_data = dst_raster_data

            # Replace raster_src with a new in-memory raster.
            raster_src = make_in_memory_raster(raster_data, profile)

    ## Calculate the pixel size and pixel counts.
    #(   pixel_width_metres, pixel_height_metres, pixel_area_km2,
    #    n_pxls_total, n_pxls_masked, n_pxls_unmasked,
    #    area_total_km2, area_masked_km2, area_unmasked_km2,
    #    frac_pxls_masked, frac_pxls_unmasked) = \
    #        calculate_pixel_size_and_counts(profile, raster_data)

    # Load the protected areas for the countries which intersect the
    # raster. The protected areas are dissolved into a single multipolygon
    # geometry, and projected to match the raster CRS.
    # !!! This could be made more efficient: Pre-process with a spatial
    # join to assign each protected area with adm1 zone(s). Then we only
    # need to load the PAs matching adm1.
    PA_mask = load_protected_areas_for_raster_clipping(path_PA_gpkg,
                        adm0_list, crs,
                        (raster_src.height, raster_src.width),
                        raster_src.transform)

    # Do the binning.
    #
    # Give a warning if the bins do not encompass the full range of
    # values in the raster.
    min_bin, max_bin = bins[0], bins[-1]
    if  ((raster_data.min() / scale_factor) < min_bin) or\
        ((raster_data.max() / scale_factor) > max_bin):
        warnings.warn("Some raster values fall outside the defined bins.")
    # Prepare output dictionary.
    results_for_all_polygon_groups__dict = dict()
    # Loop over lists of polygons.
    for polygons_name, polygons_GDF in dict_of_polygon_GDFs.items():

        # Reproject polygons.
        if polygons_GDF is not None:

           polygons_GDF = polygons_GDF.to_crs(dst_crs)

        # Do binning.
        results_for_all_polygon_groups__dict[polygons_name] =\
                bin_raster_for_one_polygon_group(
                            raster_src, raster_data,
                            scale_factor,
                            bins, PA_mask,
                            polygon_id_field_dict[polygons_name],
                            polygons_GDF = polygons_GDF,
                            polygons_name = polygons_name)

    ## Flatten the results dictionary (makes it easier to manipulate later).
    #results_flat = {}
    #for outer_key, inner_dict in results.items():
    #    for inner_key, values in inner_dict.items():
    #        flattened[inner_key] = {'zone': outer_key, **values}

    #return binned, profile
    return results_for_all_polygon_groups__dict

def reproject_raster_wrapper(raster_data, raster_src, profile):
    
    log.info('\n' + 80 * '-', show_timestamp = False)

    # Based on the geographical location of the raster, we 
    # define a suitable projected coordinate system.
    dst_crs = get_suitable_regional_projection_for_raster(
                    raster_data, raster_src)
    log.info("Reprojecting raster to {:}".format(dst_crs))

    # Find the updated raster profile (which contains transform
    # information) based on the new CRS.
    transform, width, height, dst_profile = \
        generate_raster_profile_from_crs(dst_crs, raster_src, profile)

    # Reproject the raster.
    dst_raster_data = reproject_raster(raster_data, height,
                                width, raster_src, transform, dst_crs)

    #path_raster_out_tmp = '/Users/hrmd/Desktop/tmp.tif'
    #save_raster(path_raster_out_tmp, raster_data, dst_profile,
    #            dtype=raster_data.dtype)

    return dst_profile, dst_crs, dst_raster_data

def make_in_memory_raster(data, profile):
    memfile = MemoryFile()
    with memfile.open(**profile) as dataset:
        dataset.write(data, 1)
    return memfile.open()

def get_suitable_regional_projection_for_raster(raster_data, raster_src):
    
    log.info('Finding a Lambert azimuthal equal area projection centred on the raster')

    # Unpack raster information.
    transform = raster_src.transform
    raster_crs = raster_src.crs

    # Get the non-null part of the raster as a MultiPolygon.
    raster_geom = get_non_null_region_of_raster_as_multipolygon(
            raster_data, transform)

    # Calculate the geographic centroid of the raster.
    lon_centroid, lat_centroid = geographic_true_centroid(
                                    raster_geom, raster_crs,
                                    tolerance = 1e-3,
                                    max_iterations = 10)
    log.info('The geographical centre of the raster is {:+.3f} E {:+.3f} N'
          .format(lon_centroid, lat_centroid))

    # Define azimuthal equal-area CRS centered on raster.
    laea_crs = CRS.from_proj4(f"+proj=laea +lat_0={lat_centroid} +lon_0={lon_centroid} +units=m +datum=WGS84 +no_defs")
    log.info('The proj4 string (defining the new map projection) is:')
    log.info(laea_crs)

    return laea_crs

def geographic_true_centroid(polygon: Polygon, polygon_crs: CRS, tolerance: float = 1e-10, max_iterations: int = 10):
    """
    Computes the true geographic centroid of a polygon on the ellipsoid
    using iterative projection to an Azimuthal Equidistant projection.

    Args:
        polygon (shapely.geometry.Polygon): The input polygon.
        polygon_crs (pyproj.CRS): The CRS of the input polygon (e.g., pyproj.CRS("EPSG:4326")).
        tolerance (float): Convergence threshold in degrees.
        max_iterations (int): Maximum number of iterations.

    Returns:
        (float, float): The true geographic centroid in geographic coordinates (lon, lat).
    """
    assert polygon.is_valid and not polygon.is_empty, "Invalid or empty polygon."

    # Start with the centroid in the polygon's native CRS
    initial_centroid = polygon.centroid

    # Define a transformer to geographic coordinates
    to_geo = Transformer.from_crs(polygon_crs, CRS("EPSG:4326"), always_xy=True)
    lon, lat = to_geo.transform(initial_centroid.x, initial_centroid.y)

    for _ in range(max_iterations):
        # Define AEQD CRS centered on current (lon, lat)
        laea_crs = CRS.from_proj4(f"+proj=laea +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs")
        from_crs_to_laea = Transformer.from_crs(polygon_crs, laea_crs, always_xy=True).transform
        from_laea_to_geo = Transformer.from_crs(laea_crs, CRS("EPSG:4326"), always_xy=True).transform

        # Reproject the polygon
        projected_polygon = sh_transform(from_crs_to_laea, polygon)

        # Compute projected centroid
        projected_centroid = projected_polygon.centroid

        # Transform back to geographic coordinates
        new_lon, new_lat = sh_transform(from_laea_to_geo, projected_centroid).coords[0]

        # Check for convergence
        if abs(new_lon - lon) < tolerance and abs(new_lat - lat) < tolerance:
            return new_lon, new_lat

        lon, lat = new_lon, new_lat

    return lon, lat

def generate_raster_profile_from_crs(dst_crs, raster_src, raster_profile):

    transform, width, height = calculate_default_transform(
        raster_src.crs, dst_crs, raster_src.width, raster_src.height,
        *raster_src.bounds
    )

    dst_profile = raster_profile.copy()
    dst_profile.update({
        'crs': dst_crs,
        'transform': transform,
        'width': width,
        'height': height
    })

    return transform, width, height, dst_profile

def reproject_raster(raster_data, height, width, raster_src, transform, dst_crs):

    reprojected = np.empty((height, width), dtype=raster_data.dtype)

    # Reproject doesn’t handle masked arrays, so fill in the nodata values.
    src_nodata = raster_data.fill_value
    raster_data_filled = raster_data.filled(src_nodata)

    # Reproject. We have to use nearest neighbour interpolation, because
    # we have nodata values which will otherwise cause interpolation
    # artifacts.
    reproject(
        #source=raster_data,
        source=raster_data_filled,
        destination=reprojected,
        src_transform=raster_src.transform,
        src_crs=raster_src.crs,
        dst_transform=transform,
        dst_crs=dst_crs,
        resampling=Resampling.nearest,
        src_nodata=src_nodata,
        dst_nodata=src_nodata  # Same nodata value for output.
    )
    #raster_data = np.ma.masked_invalid(reprojected)

    # Re-apply the mask.
    raster_data = np.ma.masked_equal(reprojected, src_nodata)

    return raster_data

def load_protected_areas_for_raster_clipping(path_PA_gpkg,
                        adm0_list, raster_crs,
                        raster_shape, raster_transform):
    
    log.info('\n' + 80 * '-', show_timestamp = False)
    log.info('Preparing protected areas mask, to use in clipping')
    # Load the protected areas (only for the countries that the raster
    # intersects).
    filter_field = 'iso3'
    gdf_PAs = load_gpkg_filtered_by_list_as_gdf(path_PA_gpkg,
                            filter_field, adm0_list)
    
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

def calculate_pixel_size_and_counts(profile, raster_data, verbose = True):

    pixel_width_metres = abs(profile['transform'].a) 
    pixel_height_metres = abs(profile['transform'].e)
    pixel_area_km2 = (pixel_width_metres * pixel_height_metres) / 1.0E6
    #
    n_pxls_total = raster_data.size
    n_pxls_masked = np.ma.count_masked(raster_data)
    n_pxls_unmasked = np.ma.count(raster_data)
    #
    area_total_km2 = pixel_area_km2 * n_pxls_total
    area_masked_km2 = pixel_area_km2 * n_pxls_masked
    area_unmasked_km2 = pixel_area_km2 * n_pxls_unmasked
    #
    frac_pxls_masked = n_pxls_masked / n_pxls_total
    frac_pxls_unmasked = n_pxls_unmasked / n_pxls_total

    # Store in a dictionary.
    raster_info_dict = {
        "pixel_width_metres": pixel_width_metres,
        "pixel_height_metres": pixel_height_metres,
        "pixel_area_km2": pixel_area_km2,
        "n_pxls_total": n_pxls_total,
        "n_pxls_masked": n_pxls_masked,
        "n_pxls_unmasked": n_pxls_unmasked,
        "area_total_km2": area_total_km2,
        "area_masked_km2": area_masked_km2,
        "area_unmasked_km2": area_unmasked_km2,
        "frac_pxls_masked": frac_pxls_masked,
        "frac_pxls_unmasked": frac_pxls_unmasked,
    }
    
    if verbose:

        log.info('Pixel width × height = {:,.1f} metres × {:,.1f} metres = {:,.1f} m2'.format(
            pixel_width_metres, pixel_height_metres, pixel_area_km2 * 1.0E6), show_timestamp = False)
        log.info("Total pxls:    {:12,d}           = {:15,.1f} km2".format(n_pxls_total, area_total_km2), show_timestamp = False)
        log.info("Masked pxls:   {:12,d} ({:>5.1f} %) = {:15,.1f} km2".format(n_pxls_masked, frac_pxls_masked * 100.0, area_masked_km2), show_timestamp = False)
        log.info("Unmasked pxls: {:12,d} ({:>5.1f} %) = {:15,.1f} km2".format(n_pxls_unmasked, frac_pxls_unmasked * 100.0, area_unmasked_km2), show_timestamp = False)
    
    return raster_info_dict

def bin_raster_for_one_polygon_group(raster_src, raster_data, scale_factor,
                bins, PA_mask, polygon_id_field, polygons_name = 'whole', polygons_GDF = None):
    
    log.info('\n' + 80 * '-', show_timestamp = False)
    log.info('Binning raster for polygons list: {:}'.format(polygons_name))

    # Determine the length of the loop.
    if polygons_GDF is None:
        n_polys = 1
    else:
        n_polys = len(polygons_GDF)
    
    # Loop over each polygon to do binning.
    results_for_all_polygons_in_group__dict = dict()
    for i in range(n_polys):

        # Do binning for one polygon.
        polygon_id, results_for_one_polygon__dict = \
                bin_raster_for_one_polygon(polygons_GDF, i, raster_data,
                                   raster_src, scale_factor, PA_mask, bins,
                                   n_polys, polygon_id_field)

        # Store array for this polygon in dictionary.
        results_for_all_polygons_in_group__dict[polygon_id] =\
                results_for_one_polygon__dict

    return results_for_all_polygons_in_group__dict

def bin_raster_for_one_polygon(polygons_GDF, i, raster_data, raster_src,
                               scale_factor, PA_mask, bins, n_polys,
                               polygon_id_field):

    # Apply the protected areas mask and get polygon name and ID.
    raster_data, raster_data_PA, polygon_name, polygon_id =\
        prepare_PA_masked_raster_and_metadata(polygons_GDF, i, raster_data,
                                            raster_src, PA_mask,
                                            polygon_id_field)
        
    # Get pixel size and counts for the current raster (after clipping).
    pxl_info = calculate_pixel_size_and_counts(raster_src.profile,
                                            raster_data,
                                            verbose = False)

    # Get pixel size and counts for the current raster (after clipping
    # and masking by protected areas).
    pxl_info_PA = calculate_pixel_size_and_counts(raster_src.profile,
                                            raster_data_PA,
                                            verbose = False)

    ## Summarise amount of protected area.
    #area_unmasked_and_unprotected_km2_i = \
    #        area_unmasked_km2_i - area_unmasked_and_protected_km2_i
    #frac_protected_i = \
    #        area_unmasked_and_protected_km2_i / area_unmasked_km2_i
    #frac_unprotected_i = 1.0 - frac_protected_i

    # Do binning and get bin counts for the data with and without the
    # protected areas mask.
    results_for_one_polygon__dict = get_bin_counts_wrapper(
            raster_data, raster_data_PA, bins, pxl_info['pixel_area_km2'],
            scale_factor)

    # Print an update.
    print_bin_count_update(i, n_polys, polygon_name,
                           results_for_one_polygon__dict,
            pxl_info['area_unmasked_km2'],
            pxl_info_PA['area_unmasked_km2'],
            pxl_info['area_unmasked_km2'] - pxl_info_PA['area_unmasked_km2'])

    return polygon_id, results_for_one_polygon__dict

def prepare_PA_masked_raster_and_metadata(polygons_GDF, i, raster_data,
                                          raster_src, PA_mask, polygon_id_field):

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

    # Case 2: No list of polygons has been provided (do binning 
    # for the whole raster, with no polygon clipping).
    else:

        #raster_data_i = raster_data
        raster_data_masked = update_mask(raster_data, PA_mask == 0,
                                           np.logical_or)
        polygon_name = 'whole'
        polygon_id = 'whole'

    return raster_data, raster_data_masked, polygon_name, polygon_id

def load_gpkg_filtered_by_list_as_gdf(gpkg_path, filter_field,
                                      allowed_list, layer_name = None):
    """
    Load features from a GeoPackage filtered by ISO3 codes.

    Parameters:
        gpkg_path (str): Path to the GeoPackage file.
        layer_name (str): Name of the layer within the GeoPackage.
        iso3_list (list of str): List of ISO3 country codes to filter by.

    Returns:
        geopandas.GeoDataFrame: Filtered GeoDataFrame.
    """

    if layer_name is None:

        layers = fiona.listlayers(gpkg_path)
        assert len(layers) == 1, 'If you don’t specify a layer name, the geopackage file must have only one layer'
        layer_name = layers[0]

    list_str = ", ".join(f"'{val}'" for val in allowed_list)
    sql = f"SELECT * FROM {layer_name} WHERE {filter_field} IN ({list_str})"

    log.info('Loading from {:}\nwith query {:}'.format(gpkg_path, sql))

    return gpd.read_file(gpkg_path, sql=sql)

def clip_raster_to_polygon_and_apply_PA_mask(
        polygon, raster_src, PA_mask):

    # Clip the raster by the polgyon.
    data_clipped, transform_clipped = clip_raster_to_polygon(polygon,
                                                             raster_src)

    # Apply the PA mask.
    data_clipped_and_masked = \
            apply_full_size_mask_to_clipped_raster(raster_src, data_clipped,
                                           transform_clipped, PA_mask)

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

def update_mask(array, new_mask, operator):

    new_mask = operator(array.mask, new_mask)
    array_mask_updated= np.ma.masked_array(array.data,
                                     mask = new_mask)

    return array_mask_updated

def get_bin_counts_wrapper(data, data_PA, bins, pixel_area_km2, scale_factor):

    # Get bin counts.
    counts_by_bin = get_bin_counts(data, bins, scale_factor)
    counts_by_bin_in_PA = get_bin_counts(data_PA, bins, scale_factor)
    counts_by_bin_not_in_PA = counts_by_bin - counts_by_bin_in_PA

    # Get bin areas.
    areas_km2_by_bin = counts_by_bin * pixel_area_km2
    areas_km2_by_bin_in_PA = counts_by_bin_in_PA * pixel_area_km2
    areas_km2_by_bin_not_in_PA = counts_by_bin_not_in_PA * pixel_area_km2

    # Store the information for this group of polygons.
    #areas_km2_by_bin_array = np.stack([
    #    areas_km2_by_bin, areas_km2_by_bin_in_PA,
    #    areas_km2_by_bin_not_in_PA], axis = 1)
    results_for_one_polygon__dict = {
        'area_km2_by_bin' : areas_km2_by_bin,
        'area_km2_by_bin_in_PA' : areas_km2_by_bin_in_PA,
        'area_km2_by_bin_not_in_PA' : areas_km2_by_bin_not_in_PA,
        }

    #return areas_km2_by_bin_array
    return results_for_one_polygon__dict

def get_bin_counts(data_with_mask, bins, scale_factor):

    # Apply the scale factor (some rasters use a range not between
    # 0 and 1, for example to allow smaller file sizes by saving as
    # Int16 format).
    data_with_mask = data_with_mask / scale_factor

    # Bin the data and re-apply the mask.
    binned = np.digitize(data_with_mask, bins, right = False)
    binned = np.ma.masked_array(binned, mask = data_with_mask.mask)

    # Get counts for each bin, ignoring masked values.
    n_bins = len(bins) - 1
    counts_by_bin = np.zeros(n_bins, dtype = int)
    for i in range(1, len(bins)):
        
        counts_by_bin[i - 1] = np.sum((binned == i) & ~binned.mask)

    return counts_by_bin

def print_bin_count_update(i, n_polys, polygon_name, results_for_one_polygon__dict, total_area, total_area_protected, total_area_unprotected):

    # Print update.
    log.info("\nPolygon {:>5d} of {:>5d}: {:}".format(i + 1, n_polys, polygon_name))
    log.info("Raster areas (km2) within polygon:", show_timestamp = False)
    log.info("{:15} {:>15} {:>15} {:>15}".format('Bin', 'total', 'protected', 'unprotected'), show_timestamp = False)
    log.info("{:15} {:15,.1f} {:15,.1f} {:15,.1f}".format(
            'All bins',
            total_area,
            total_area_protected,
            total_area_unprotected), show_timestamp = False)

    n_bins = results_for_one_polygon__dict['area_km2_by_bin'].shape[0]
    for i in range(n_bins):
        log.info("{:15d} {:15,.1f} {:15,.1f} {:15,.1f}".format(
                i + 1,
                results_for_one_polygon__dict['area_km2_by_bin'][i],
                results_for_one_polygon__dict['area_km2_by_bin_in_PA'][i],
                results_for_one_polygon__dict['area_km2_by_bin_not_in_PA'][i],
                ), show_timestamp = False)

    return

def get_unique_list_from_nested_attr(dict_, key):

    combined = []
    for val in dict_.values():

        # Safely get list or empty list, and extend full list with it.
        combined.extend(val.get(key, []))

    # Get sorted unique list.
    unique_sorted = sorted(set(combined))

    return unique_sorted

# --- Main sentinel. -------------------------------
def main():

    # Parse the command-line arguments.
    args = parse_args()
    dir_data = args.dir_data
    dir_output = os.path.join(dir_data, 'code_output')
    #print('')

    # Set up logging (overrides the 'print' function).
    initialise_logging(dir_output)
    
    # Load results and catalog, and clear out any old results.
    catalog, results, path_results = \
        load_results_and_catalog_and_remove_results_no_longer_in_catalog(
                dir_output, dir_data)

    # Define paths for admin polygons and protected areas.
    path_adm0, path_adm1, path_PA_gpkg = define_dataset_paths(dir_data)

    # Loop through all the datasets in the catalog.
    for key, dataset in catalog.iterrows():
        
        #key = dataset['key']
        log.info(80 * '=', show_timestamp = False)
        log.info('Processing dataset: {:}'.format(key))
        log.info('')
        if (key in results.keys()) and (dataset['overwrite'] == 'no'):
            
            log.info('Skipping processing for {:}, as the results file already has data for this dataset.'.format(key))
            continue

        # Do all the processing steps for this raster.
        results[key] = find_intersections_and_do_binning_for_one_raster(
                        dir_data, path_adm0, path_adm1, path_PA_gpkg,
                        dataset['folder'], dataset['input_file_name'],
                        dataset['band'],
                        dataset['scale_factor'])

    # Transfer (or update) metadata from the catalog to the results.
    metadata_keys_to_use = ['folder', 'input_file_name', 'species', 'study_area',
                            'source_link', 'source_text']
    for dataset in results:

        for metadata_key in metadata_keys_to_use:

            results[dataset][metadata_key] = catalog.loc[dataset][metadata_key]

    # Log the results.
    log.info("Final results:", to_console = False)
    log.info(json.dumps(results, indent=4, cls = custom_JSON_encoder),
                                to_console = False)
    
    # Get a list of all the admin-0 and and admin-1 zones covered by
    # all the rasters.
    all_adm0 = get_unique_list_from_nested_attr(results, 'adm0_list')
    all_adm1 = get_unique_list_from_nested_attr(results, 'adm1_list')
    log.info('Admin-0 and admin-1 zones covered:')
    log.info(all_adm0)
    log.info(all_adm1)

    # Save the results as a JSON file.
    log.info('', show_timestamp = False)
    log.info("Saving to {:}".format(path_results))
    with open(path_results, "w") as f:
        json.dump(results, f, indent=4, cls = custom_JSON_encoder)
    
    return

if __name__ == '__main__':

    main()
