import logging

import numpy as np
import rasterio
from rasterio.enums import Resampling

from analyse_rasters.clipping_and_masking import (
        load_protected_areas_for_raster_clipping,
        prepare_PA_masked_raster_and_metadata)
from analyse_rasters.projection_tools import (
        reproject_raster_wrapper, reproject_to_match)
from analyse_rasters.raster_utils import (
        calculate_pixel_size_and_counts,
        make_in_memory_raster,
        )

def bin_raster_for_all_polygon_groups(path_raster, path_PA_gpkg,
    path_landuse, bins,
    dict_of_polygon_GDFs, adm0_list, polygon_id_field_dict,
    raster_band):

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
            dst_profile, dst_crs, dst_raster_data, centroid = \
                    reproject_raster_wrapper(raster_data, raster_src, profile)

            # Overwrite values.
            profile = dst_profile
            crs = dst_crs
            raster_data = dst_raster_data

            # Replace raster_src with a new in-memory raster.
            raster_src = make_in_memory_raster(raster_data, profile)

    # Clip, reproject and align the land use raster.
    # Use mode resampling for categorical data.
    # This assumes the landuse raster has a geographical projection.
    landuse_clip_buffer_degrees = 1.0
    logging.info('Clipping, reprojecting and aligning landuse raster.')
    landuse_data, landuse_profile = reproject_to_match(raster_src,
                path_landuse,
                resampling = Resampling.mode, 
                buffer = landuse_clip_buffer_degrees)
    landuse_src = make_in_memory_raster(landuse_data, landuse_profile)

    #from plot_categorical_data import display_categorical_data 
    #display_categorical_data(landuse_data, '../data/un_lcc_color_scheme.csv')

    #import sys
    #sys.exit()

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
    #min_bin, max_bin = bins[0], bins[-1]
    #if  ((raster_data.min() / scale_factor) < min_bin) or\
    #    ((raster_data.max() / scale_factor) > max_bin):
    #    warnings.warn("Some raster values fall outside the defined bins.")
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
                            bins, PA_mask,
                            landuse_src,
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

def bin_raster_for_one_polygon_group(raster_src, raster_data,
                bins, PA_mask, landuse_src, polygon_id_field,
                polygons_name = 'whole', polygons_GDF = None):
    
    logging.info('\n' + 80 * '-')
    logging.info('Binning raster for polygons list: {:}'.format(polygons_name))

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
                                    raster_src, PA_mask,
                                    landuse_src, bins,
                                    n_polys, polygon_id_field)

        # Store array for this polygon in dictionary.
        results_for_all_polygons_in_group__dict[polygon_id] =\
                results_for_one_polygon__dict

    return results_for_all_polygons_in_group__dict

def bin_raster_for_one_polygon(polygons_GDF, i, raster_data, raster_src,
                               PA_mask, landuse_src, bins,
                               n_polys, polygon_id_field):

    # Apply the protected areas mask and get polygon name and ID.
    raster_data, raster_data_PA, polygon_name, polygon_id, landuse_data =\
        prepare_PA_masked_raster_and_metadata(polygons_GDF, i, raster_data,
                                            raster_src, PA_mask, landuse_src,
                                            polygon_id_field)

    #from plot_categorical_data import display_categorical_data 
    #display_categorical_data(landuse_data, '../data/un_lcc_color_scheme.csv')

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
            raster_data, raster_data_PA, landuse_data, bins,
            pxl_info['pixel_area_km2'])

    # Print an update.
    print_bin_count_update(i, n_polys, polygon_name,
                           results_for_one_polygon__dict,
            pxl_info['area_unmasked_km2'],
            pxl_info_PA['area_unmasked_km2'],
            pxl_info['area_unmasked_km2'] - pxl_info_PA['area_unmasked_km2'])

    return polygon_id, results_for_one_polygon__dict

def get_bin_counts_wrapper(data, data_PA, landuse_data, bins,
                           pixel_area_km2):

    # Get bin counts.
    counts_by_bin, data_binned = get_bin_counts(data, bins)
    counts_by_bin_in_PA, _ = get_bin_counts(data_PA, bins)
    counts_by_bin_not_in_PA = counts_by_bin - counts_by_bin_in_PA

    # Get bin areas.
    areas_km2_by_bin = counts_by_bin * pixel_area_km2
    areas_km2_by_bin_in_PA = counts_by_bin_in_PA * pixel_area_km2
    areas_km2_by_bin_not_in_PA = counts_by_bin_not_in_PA * pixel_area_km2

    # Calculate bin areas, double-binned by land use category.
    areas_km2_by_category_and_bin = count_binned_by_category(data_binned,
                                        landuse_data, pixel_area_km2)
    
    #logging.info(areas_km2_by_category_and_bin)
    #logging.info('\n')
    for landuse_category, val in areas_km2_by_category_and_bin.items():
        logging.info('{:>4d} {:10.1f} {:10.1f} {:10.1f} {:10.1f} km2'.format(
            landuse_category, *val))

    # Store the information for this group of polygons.
    #areas_km2_by_bin_array = np.stack([
    #    areas_km2_by_bin, areas_km2_by_bin_in_PA,
    #    areas_km2_by_bin_not_in_PA], axis = 1)
    results_for_one_polygon__dict = {
        'area_km2_by_bin' : areas_km2_by_bin,
        'area_km2_by_bin_in_PA' : areas_km2_by_bin_in_PA,
        'area_km2_by_bin_not_in_PA' : areas_km2_by_bin_not_in_PA,
        'area_km2_by_landuse_and_bin' : areas_km2_by_category_and_bin,
        }

    #return areas_km2_by_bin_array
    return results_for_one_polygon__dict

def get_bin_counts(data_with_mask, bins):

    ## Apply the scale factor (some rasters use a range not between
    ## 0 and 1, for example to allow smaller file sizes by saving as
    ## Int16 format).
    #data_with_mask = data_with_mask / scale_factor
    logging.info('Doing binning with bins {:}'.format(str(bins)))

    # Bin the data and re-apply the mask.
    binned = np.digitize(data_with_mask, bins, right = False)
    binned = np.ma.masked_array(binned, mask = data_with_mask.mask)

    # Get counts for each bin, ignoring masked values.
    n_bins = len(bins) - 1
    counts_by_bin = np.zeros(n_bins, dtype = int)
    for i in range(1, len(bins)):
        
        #counts_by_bin[i - 1] = np.sum((binned == i) & ~binned.mask)
        masked_equals_i = np.ma.masked_not_equal(binned, i)
        counts_by_bin[i - 1] = np.ma.count(masked_equals_i)

    return counts_by_bin, binned

def print_bin_count_update(i, n_polys, polygon_name, results_for_one_polygon__dict, total_area, total_area_protected, total_area_unprotected):

    # Print update.
    logging.info("\nPolygon {:>5d} of {:>5d}: {:}".format(i + 1, n_polys, polygon_name))
    logging.info("Raster areas (km2) within polygon:")
    logging.info("{:15} {:>15} {:>15} {:>15}".format('Bin', 'total', 'protected', 'unprotected'))
    logging.info("{:15} {:15,.1f} {:15,.1f} {:15,.1f}".format(
            'All bins',
            total_area,
            total_area_protected,
            total_area_unprotected))

    n_bins = results_for_one_polygon__dict['area_km2_by_bin'].shape[0]
    for i in range(n_bins):
        logging.info("{:15d} {:15,.1f} {:15,.1f} {:15,.1f}".format(
                i + 1,
                results_for_one_polygon__dict['area_km2_by_bin'][i],
                results_for_one_polygon__dict['area_km2_by_bin_in_PA'][i],
                results_for_one_polygon__dict['area_km2_by_bin_not_in_PA'][i],
                ))

    return

def count_binned_by_category(binned, category, multiplier):
    result = {}

    # Masked elements: ignore any location where either is masked
    combined_mask = np.ma.getmaskarray(binned) | np.ma.getmaskarray(category)

    # Get valid data
    valid_binned = binned[~combined_mask]
    valid_category = category[~combined_mask]

    # Loop through unique category values
    for cat_val in np.unique(valid_category):
        counts = [0, 0, 0, 0]  # Assuming binned values are 0,1,2,3
        # Filter binned values corresponding to current category
        binned_for_cat = valid_binned[valid_category == cat_val]
        for i in range(4):
            counts[i] = np.sum(binned_for_cat == i + 1)
        result[cat_val] = [c * multiplier for c in counts]

    return result
