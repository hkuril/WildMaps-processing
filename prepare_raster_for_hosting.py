import os
import subprocess
import tempfile

import rasterio
from rasterio.warp import calculate_default_transform
from tqdm import tqdm

from handle_aws import upload_to_aws

def run_command(cmd):
    """Print and run a shell command."""
    print("Running command:", " ".join(cmd))
    subprocess.run(cmd, check=True)

def old():
    def is_cog(path):
        """Check if the file is a COG using gdalinfo."""
        cmd = ["gdalinfo", "-json", path]
        print("Running command:", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return '"COG": "YES"' in result.stdout
    
    def convert_to_regular_geotiff(cog_path, tmp_dir, band_index):
        """Convert a COG to a regular single-band GeoTIFF."""
        out_path = os.path.join(tmp_dir, "regular_band.tif")
        extract_single_band(cog_path, out_path, band_index)
        return out_path

def extract_single_band(src_path, dst_path, band_index):
    """Extract a single band from a TIFF using gdal_translate."""
    cmd = ["gdal_translate", "-b", str(band_index), src_path, dst_path]
    run_command(cmd)

def get_target_resolution_for_zoom(zoom_level):
    """Approximate resolution (in meters per pixel) for a given Web Mercator zoom level."""
    initial_res = 156543.03  # meters/pixel at zoom level 0
    return initial_res / (2 ** zoom_level)

def get_native_resolution(geotiff_path):
    """Get native resolution in meters, reprojecting if input is in degrees."""
    with rasterio.open(geotiff_path) as src:
        if src.crs.is_geographic:
            dst_crs = "EPSG:3857"
            transform, width, height = calculate_default_transform(
                src.crs, dst_crs, src.width, src.height, *src.bounds)
            res_x = transform.a
            res_y = -transform.e
            return max(res_x, res_y)
        else:
            return max(src.res)

def build_overviews(geotiff_path, zoom_level):
    """Build overviews for the GeoTIFF based on web zoom level."""
    native_res = get_native_resolution(geotiff_path)
    target_res = get_target_resolution_for_zoom(zoom_level)

    factor = 2
    overviews = []
    while native_res * factor < target_res:
        overviews.append(factor)
        factor *= 2

    if overviews:
        cmd = ["gdaladdo", "-r", "average", geotiff_path] + list(map(str, overviews))
        run_command(cmd)

def create_cog(input_tif, output_cog):
    """Create a COG using gdal_translate."""
    cmd = [
        "gdal_translate", input_tif, output_cog,
        "-of", "COG",
        "-co", "COMPRESS=LZW",
        "-co", "TILING_SCHEME=GoogleMapsCompatible"
    ]
    run_command(cmd)

def prepare_cog(input_path, zoom_level, output_cog_path, band_index=1):

    with tempfile.TemporaryDirectory() as tmp_dir:
        #print("Checking input file...")
        #if is_cog(input_path):
        #    print("Input is COG — converting to regular single-band GeoTIFF...")
        #    regular_path = convert_to_regular_geotiff(input_path, tmp_dir, band_index)
        #else:
        #    print("Input is not COG — extracting single band...")
        #    regular_path = os.path.join(tmp_dir, "regular_band.tif")
        #    extract_single_band(input_path, regular_path, band_index)

        # Extract the required band.
        print("Extracting band {:}".format(band_index))
        regular_path = os.path.join(tmp_dir, "regular_band.tif")
        extract_single_band(input_path, regular_path, band_index)

        print(f"Generating overviews for zoom level {zoom_level}...")
        build_overviews(regular_path, zoom_level)

        print("Creating COG with appropriate tiling...")
        create_cog(regular_path, output_cog_path)

        print(f"Done. COG ready at: {output_cog_path}")

def prepare_cog_wrapper(dir_data, raster_subfolder, raster_input_file_name,
                        raster_key, band_index, max_zoom, overwrite,
                        aws_bucket):

    # Define file paths.
    path_raster = os.path.join(dir_data, 'raster', 'SDM',
                               raster_subfolder, raster_input_file_name)
    subdir_cloud_raster = '/'.join(['code_output', 'cloud_raster',
                                   'SDM', raster_subfolder])
    dir_cloud_raster = os.path.join(dir_data, subdir_cloud_raster)
    name_cloud_raster = '{:}_zoom_{:02d}.tif'.format(raster_key, max_zoom)
    path_cloud_raster = os.path.join(dir_cloud_raster, name_cloud_raster)

    # Check if the output file already exists.
    if (os.path.exists(path_cloud_raster)) and (overwrite == 'no'):

        print("The cloud-optimised geoTIFF file {:} already exists, "
              "skipping file creation...".format(path_cloud_raster))

    else:

        # Make the output directory if it doesn’t already exist..
        print("Making directory {:} (if it doesn’t already exist).".format(
            dir_cloud_raster))
        os.makedirs(dir_cloud_raster, exist_ok = True)

        # Create a COG from the existing GeoTIFF.
        prepare_cog(
            input_path = path_raster,
            zoom_level = max_zoom,
            output_cog_path = path_cloud_raster,
            band_index = band_index,
            )
    
    # Upload to AWS. (If the file is already there, no transfer will be
    # done.)
    aws_key = '/'.join([subdir_cloud_raster , name_cloud_raster])
    print(aws_bucket, aws_key)

    upload_to_aws(path_cloud_raster, aws_bucket, aws_key)

    return

def test():

    prepare_cog(
        input_path="../data/raster/SDM/burns_2025/sumatra_sambar_sdm_2021.tif",
        zoom_level=10,
        output_cog_path="../data/code_output/cloud_raster/SDM/burns_2025/sumatra_sambar_sdm_2021.tif",
        band_index = 1,
        )

    return

if __name__ == '__main__':

    test()
