import logging

import numpy as np
from pyproj import CRS, Transformer
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import (reproject, transform_bounds)
from rasterio.windows import from_bounds
from shapely.geometry import Polygon
from shapely.ops import transform as sh_transform

from analyse_rasters.raster_utils import (
        generate_raster_profile_from_crs,
        get_non_null_region_of_raster_as_multipolygon,
        )

def get_suitable_regional_projection_for_raster(raster_data, raster_src):
    
    logging.info('Finding a Lambert azimuthal equal area projection centred on the raster')

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
    centroid = [lon_centroid, lat_centroid]
    logging.info('The geographical centre of the raster is {:+.3f} E {:+.3f} N'
          .format(lon_centroid, lat_centroid))

    # Define azimuthal equal-area CRS centered on raster.
    laea_crs = CRS.from_proj4(f"+proj=laea +lat_0={lat_centroid} +lon_0={lon_centroid} +units=m +datum=WGS84 +no_defs")
    logging.info('The proj4 string (defining the new map projection) is:')
    logging.info(laea_crs)

    return laea_crs, centroid

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

def reproject_raster_wrapper(raster_data, raster_src, profile):
    
    logging.info('\n' + 80 * '-')

    # Based on the geographical location of the raster, we 
    # define a suitable projected coordinate system.
    dst_crs, centroid = get_suitable_regional_projection_for_raster(
                    raster_data, raster_src)
    logging.info("Reprojecting raster to {:}".format(dst_crs))

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

    return dst_profile, dst_crs, dst_raster_data, centroid

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

def reproject_to_match(raster_src, path_second_raster, resampling=Resampling.nearest, buffer=0.01):
    """
    Reproject a second raster to match the extent, projection, and grid of a reference raster.
    Only processes the overlapping region for efficiency.

    Parameters:
    -----------
    raster_src : rasterio.DatasetReader
        Open rasterio dataset reader for the reference raster
    path_second_raster : str
        Path to the raster that needs to be reprojected
    resampling : rasterio.warp.Resampling, optional
        Resampling method to use (default: nearest)
    buffer : float, optional
        Buffer to add around bounds to avoid edge effects (default: 0.01)

    Returns:
    --------
    tuple : (reprojected_data, profile)
        reprojected_data : numpy.ndarray
            The reprojected raster data
        profile : dict
            Rasterio profile dict for the reprojected data
    """
    # Get reference properties
    ref_transform = raster_src.transform
    ref_crs = raster_src.crs
    ref_shape = (raster_src.height, raster_src.width)
    ref_bounds = raster_src.bounds

    # Create the output profile based on reference raster
    profile = raster_src.profile.copy()

    with rasterio.open(path_second_raster) as second_src:
        # Update profile with second raster's data type and nodata
        profile.update({
            'dtype': second_src.dtypes[0],
            'nodata': second_src.nodata,
            'count': 1  # assuming single band, adjust if needed
        })

        # Transform the reference bounds to the second raster's CRS
        second_crs_bounds = transform_bounds(ref_crs, second_src.crs, *ref_bounds)

        # Add buffer to ensure we don't miss edge pixels
        buffered_bounds = (
            second_crs_bounds[0] - buffer,
            second_crs_bounds[1] - buffer,
            second_crs_bounds[2] + buffer,
            second_crs_bounds[3] + buffer
        )

        try:
            # Get the window in the second raster that covers these bounds
            window = from_bounds(*buffered_bounds, second_src.transform)

            # Read only the relevant portion of the second raster
            clipped_data = second_src.read(1, window=window)
            clipped_transform = rasterio.windows.transform(window, second_src.transform)

            # Create array for reprojected data
            reprojected_data = np.empty(ref_shape, dtype=second_src.dtypes[0])

            # Reproject only the clipped portion
            reproject(
                source=clipped_data,
                destination=reprojected_data,
                src_transform=clipped_transform,
                src_crs=second_src.crs,
                dst_transform=ref_transform,
                dst_crs=ref_crs,
                resampling=resampling
            )

        except rasterio.errors.WindowError:
            logging.info("Warning: Bounds don't overlap with second raster")
            # Return array filled with nodata values
            fill_value = second_src.nodata if second_src.nodata is not None else 0
            reprojected_data = np.full(ref_shape, fill_value, dtype=second_src.dtypes[0])

    return reprojected_data, profile
