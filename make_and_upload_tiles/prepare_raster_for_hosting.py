import json
import logging
import os
import tempfile

import numpy as np
import rasterio

from interact_with_aws.aws_tools import (
        check_if_file_exists_on_aws, upload_tiles_to_aws)
from utilities.use_command_line import run_cmd
from make_and_upload_tiles.prepare_tiles import (
        create_tile_manifest, compare_manifest)

def prepare_raster_tiles_wrapper(dir_data, dir_output, raster_subfolder,
                        raster_input_file_name,
                        raster_key, band_index, max_zoom, dataset_type,
                        name_color_ramp,
                        data_min = None, data_max = None,
                        percentile_min = None, percentile_max = None):

    overwrite = 'yes'

    # Define file paths.
    path_raster_in = os.path.join(dir_data, 'raster', 'SDM',
                               raster_subfolder, raster_input_file_name)
    path_color_ramp = os.path.join(dir_data, 'colour_ramps',
                                   '{:}.txt'.format(name_color_ramp))
    dir_tiles_out = define_raster_tileset_path(dir_output, raster_subfolder,
                                               raster_key, max_zoom)

    # Exit if tiles are already on the remote server.
    path_manifest = os.path.join(dir_tiles_out, '.tile_manifest.json') 
    exists_on_aws = check_if_file_exists_on_aws(path_manifest)
    if exists_on_aws:

        logging.info('Found tile manifest file {:} on AWS, skipping tile generation.'.format(path_manifest))
        return

    # Create local tiles (if they do not already exist).
    manifest_file = extract_band_and_generate_tiles(
        input_tiff = path_raster_in,
        band_index = band_index,
        max_zoom = max_zoom,
        output_dir = dir_tiles_out,
        color_ramp_file = path_color_ramp,
        dataset_type = dataset_type,
        overwrite = overwrite,
        data_min = data_min,
        data_max = data_max,
        percentile_min = percentile_min,
        percentile_max = percentile_max,
    )

    # Upload to AWS. (If the tiles are already there, no transfer will be
    # done.)
    #aws_key = '/'.join([subdir_raster_tiles, name_raster_tiles])
    # Double argument is deliberate!
    upload_tiles_to_aws(dir_tiles_out, dir_tiles_out, overwrite)

    ## Determine the maximum zoom level.
    #if max_zoom == 'auto':

    #    calculated_max_zoom = get_max_zoom_from_manifest(manifest_file)

    #return calculated_max_zoom
    return

def define_raster_tileset_path(dir_output, raster_subfolder, raster_key, max_zoom):

    if max_zoom == 'auto':
        name_raster_tiles = '{:}_zoom_auto'.format(raster_key)
    else:
        name_raster_tiles = '{:}_zoom_{:02d}'.format(raster_key, max_zoom)

    dir_raster_tiles = os.path.join(dir_output, 'raster_tiles',
                                    'SDM', raster_subfolder,
                                    name_raster_tiles)

    return dir_raster_tiles

def extract_band_and_generate_tiles(input_tiff, band_index, max_zoom,
            output_dir, color_ramp_file, dataset_type,
            overwrite,
            data_min = None, data_max = None,
            percentile_min = None, percentile_max = None):

    # Check if the manifest file exists, and if it matches, skip the
    # tile generation unless overwrite is requested.
    manifest_file = os.path.join(output_dir, ".tile_manifest.json")
    if (os.path.exists(output_dir) and
        compare_manifest(output_dir, manifest_file) and overwrite == 'no'):
        logging.info("Tiles match manifest file {:}. Skipping generation.".format(
            manifest_file))
        return manifest_file
    
    assert dataset_type in ['continuous', 'categorical']
    if dataset_type == 'continuous':

        assert not ((data_min is None) and (percentile_min is None)) 
        assert not ((data_max is None) and (percentile_max is None)) 

        #if percentile_min is not None:
        #    data_min = get_raster_percentile(input_tiff, percentile_min,
        #                                     band_index)
        #if percentile_max is not None:
        #    data_max = get_raster_percentile(input_tiff, percentile_max,
        #                                     band_index)
        
        resample_method = 'bilinear'

        # Define temporary file paths for intermediate TIFF files.
        tmp_tif = dict()
        tmp_tif_list = ['scaled', 'scaled_with_alpha', 'alpha', 'color',
                        'color_with_alpha']
        for name in tmp_tif_list:
            tmp_tif[name] = tempfile.NamedTemporaryFile(suffix='.tif', delete=False)
            tmp_tif[name].close()

        # Scale to 8-bit (required to generate image tiles), i.e. integer from
        # 0 to 255. (Use 1 - 254 instead of 0 - 255 because of issues
        # with applying colour ramp.)
        scale_cmd = [
            "gdal_translate",
            "-b", str(band_index),
            "-ot", "Byte",
            "-scale", str(data_min), str(data_max), "1", "254",
            input_tiff,
            tmp_tif['scaled'].name
        ]
        run_cmd(scale_cmd)

        # Add alpha, based on null pixels, as a second channel.
        warp_cmd = [
            "gdalwarp",
            "-dstalpha",
            tmp_tif['scaled'].name,
            tmp_tif['scaled_with_alpha'].name
        ]
        run_cmd(warp_cmd)

        # Get alpha channel as a separate tif.
        cmd = ["gdal_translate", "-b", "2",
                tmp_tif['scaled_with_alpha'].name,
                tmp_tif['alpha'].name]
        run_cmd(cmd)

        # Apply color ramp to the 8-bit tiff.
        assert os.path.exists(color_ramp_file)
        logging.info(f"Applying color ramp from {color_ramp_file}...")
        color_cmd = [
        "gdaldem", "color-relief",
        tmp_tif['scaled'].name,
        color_ramp_file,
        tmp_tif['color'].name,
        ]
        run_cmd(color_cmd)

        # Apply alpha to colored tiff and as a fourth channel.
        cmd = [
            "gdal_merge.py", "-separate", "-o",
            tmp_tif['color_with_alpha'].name,
            tmp_tif['color'].name,
            tmp_tif['alpha'].name
            ]
        run_cmd(cmd)

        # Modify metadata to ensure that fourth channel is treated as alpha.
        cmd = [
                "gdal_edit.py", "-colorinterp_4", "alpha",
                tmp_tif['color_with_alpha'].name
                ]
        run_cmd(cmd)

        # Generate the tiles from the four-channel TIFF.
        # Need to use to --xyz tile order convention for compatibility with 
        # MapLibre GL.
        # bilinear interpolation is suitable for continuous data.
        logging.info(f"Generating tiles up to zoom level {max_zoom} in {output_dir}...")
        if max_zoom == 'auto':
            zoom_args = []
        else:
            zoom_args = ["-z", f"0-{max_zoom}"]

        gdal2tiles_cmd = [
            "gdal2tiles.py",
            "--xyz",
            *zoom_args,
            "-r", resample_method,
            "--processes", "4",
            tmp_tif['color_with_alpha'].name,
            output_dir
        ]
        run_cmd(gdal2tiles_cmd)

        # Boost the zoom level by 1.
        if max_zoom == 'auto':
            auto_max_zoom = get_max_zoom_level(output_dir)
            gdal2tiles_cmd = [
                "gdal2tiles.py",
                "--xyz",
                "-r", resample_method,
                "--processes", "4",
                "--resume",
                "-z", f"{auto_max_zoom + 1}-{auto_max_zoom + 1}",
                tmp_tif['color_with_alpha'].name,
                output_dir
            ]
            run_cmd(gdal2tiles_cmd)

        # Cleanup (remove temporary files).
        for name in tmp_tif_list:
            os.unlink(tmp_tif[name].name)

    elif dataset_type == 'categorical':

        resample_method = 'mode'
        tmp_file_list = dict()
        tmp_file_list['vrt'] = tempfile.NamedTemporaryFile(suffix='.vrt',
                                                           delete=False)

        for key in tmp_file_list.keys():
            tmp_file_list[key].close()

        vrt_cmd = [
            "gdal_translate", "-of", "vrt", "-expand", "rgba",
            input_tiff, tmp_file_list['vrt'].name]
        run_cmd(vrt_cmd)

        # Generate the tiles.
        # Need to use to --xyz tile order convention for compatibility with 
        # MapLibre GL.
        # bilinear interpolation is suitable for continuous data.
        logging.info(f"Generating tiles up to zoom level {max_zoom} in {output_dir}...")
        if max_zoom == 'auto':
            zoom_args = []
        else:
            zoom_args = ["-z", f"0-{max_zoom}"]

        gdal2tiles_cmd = [
            "gdal2tiles.py",
            "--xyz",
            *zoom_args,
            "-r", resample_method,
            "--processes", "4",
            tmp_file_list['vrt'].name,
            output_dir
        ]
        run_cmd(gdal2tiles_cmd)

        for key in tmp_file_list.keys():
            os.unlink(tmp_file_list[key].name)

    # Create the tile manifest.
    logging.info("Tile generation complete. Saving manifest to {:}".format(
        manifest_file))
    create_tile_manifest(output_dir, manifest_file)

    ## Save the min and max values.
    #path_raster_min_max = os.path.join(output_dir, "min_max_info.json")
    #raster_min_max = {'min' : str(data_min), 'max' : str(data_max)}
    #print("Saving min-max info to {:}".format(path_raster_min_max))
    #with open(path_raster_min_max, "w") as f:
    #    json.dump(raster_min_max, f)

    return manifest_file

def get_raster_percentile(input_tiff, percentile, band_index=1):
    """
    Calculate percentile using rasterio's built-in masking functionality.
    
    Parameters:
    -----------
    input_tiff : str
        Path to the input TIFF file
    percentile : float
        Desired percentile (0-100)
    band_index : int, optional
        Band index (1-based, default is 1)
    
    Returns:
    --------
    float
        The percentile value
    """
    
    with rasterio.open(input_tiff) as src:
        # Validate band index
        if band_index < 1 or band_index > src.count:
            raise IndexError(f"Band index {band_index} is out of range. Dataset has {src.count} bands.")
        
        # Read as masked array (automatically handles nodata)
        masked_array = src.read(band_index, masked=True)
        
        # Get only the valid (non-masked) data
        valid_data = masked_array.compressed()
        
        # Check if we have any valid data
        if len(valid_data) == 0:
            raise ValueError("No valid data found after masking")
        
        # Calculate and return percentile
        result = np.percentile(valid_data, percentile)
        
        return float(result)

# Infer the max zoom level from generated tiles
def get_max_zoom_level(dir_tiles):
    max_zoom = 0
    for item in os.listdir(dir_tiles):
        if item.isdigit():
            max_zoom = max(max_zoom, int(item))
    return max_zoom
