import logging

import numpy as np
from rasterio.features import shapes
from rasterio.io import MemoryFile
from rasterio.warp import calculate_default_transform
from shapely.geometry import shape
from shapely.ops import unary_union

def make_in_memory_raster(data, profile):
    memfile = MemoryFile()
    with memfile.open(**profile) as dataset:
        dataset.write(data, 1)
    return memfile.open()

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

        logging.info('Pixel width × height = {:,.1f} metres × {:,.1f} metres = {:,.1f} m2'.format(
            pixel_width_metres, pixel_height_metres, pixel_area_km2 * 1.0E6))
        logging.info("Total pxls:    {:12,d}           = {:15,.1f} km2".format(n_pxls_total, area_total_km2))
        logging.info("Masked pxls:   {:12,d} ({:>5.1f} %) = {:15,.1f} km2".format(n_pxls_masked, frac_pxls_masked * 100.0, area_masked_km2))
        logging.info("Unmasked pxls: {:12,d} ({:>5.1f} %) = {:15,.1f} km2".format(n_pxls_unmasked, frac_pxls_unmasked * 100.0, area_unmasked_km2))
    
    return raster_info_dict

def summarise_raster(src, data):

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

    if null_fraction < 0.1:
        warnings.warn("Raster has less than 10% null values, check they were read correctly.")

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
    
    logging.info("Basic properties of the raster file:")
    for k, v in summary.items():
        logging.info("{:30} : {:50}".format(k, str(v)))
    logging.info('')

    return summary

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
