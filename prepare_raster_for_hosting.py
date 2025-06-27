import json
import os
import shlex
import subprocess
import tempfile

from handle_aws import upload_to_aws

def run_cmd(cmd):
    if isinstance(cmd, list):
        printable = ' '.join(shlex.quote(str(c)) for c in cmd)
    else:
        printable = cmd
    print(f"\n>>> Running: {printable}\n")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("Command failed with error:")
        print(result.stderr)
        raise subprocess.CalledProcessError(result.returncode, cmd)
    if result.stdout:
        print(result.stdout)

def create_tile_manifest(directory, output_path):
    manifest = {}
    for root, _, files in os.walk(directory):
        for f in files:
            if not f.endswith(".png"):
                continue
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, directory)
            size = os.path.getsize(full_path)
            manifest[rel_path] = size
    with open(output_path, "w") as f:
        json.dump(manifest, f)

def compare_manifest(directory, manifest_path):
    if not os.path.exists(manifest_path):
        return False
    with open(manifest_path) as f:
        saved = json.load(f)
    current = {}
    for root, _, files in os.walk(directory):
        for f in files:
            if not f.endswith(".png"):
                continue
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, directory)
            size = os.path.getsize(full_path)
            current[rel_path] = size
    return saved == current

def extract_band_and_generate_tiles(input_tiff, band_index, max_zoom,
            output_dir, data_min, data_max, color_ramp_file, resample_method,
            overwrite):

    # Check if the manifest file exists, and if it matches, skip the
    # tile generation unless overwrite is requested.
    manifest_file = os.path.join(output_dir, ".tile_manifest.json")
    if (os.path.exists(output_dir) and
        compare_manifest(output_dir, manifest_file) and overwrite == 'no'):
        print("Tiles match manifest file {:}. Skipping generation.".format(
            manifest_file))
        return

    # Define temporary file paths for intermediate TIFF files.
    tmp_tif = dict()
    tmp_tif_list = ['scaled', 'scaled_with_alpha', 'alpha', 'color',
                    'color_with_alpha']
    for name in tmp_tif_list:
        tmp_tif[name] = tempfile.NamedTemporaryFile(suffix='.tif', delete=False)
        tmp_tif[name].close()

    # Scale to 8-bit (required to generate image tiles), i.e. integer from
    # 0 to 255. (Use 1 - 254 instead of 0 - 255 because of issues with applying
    # colour ramp.)
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
    print(f"Applying color ramp from {color_ramp_file}...")
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
    print(f"Generating tiles up to zoom level {max_zoom} in {output_dir}...")
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

    # Create the tile manifest.
    print("Tile generation complete. Saving manifest to {:}".format(
        manifest_file))
    create_tile_manifest(output_dir, manifest_file)

    # Cleanup (remove temporary files).
    for name in tmp_tif_list:
        os.unlink(tmp_tif[name].name)

    return

def prepare_raster_tiles_wrapper(dir_data, raster_subfolder,
                        raster_input_file_name,
                        raster_key, band_index, max_zoom, overwrite,
                        aws_bucket, raster_min, raster_max, name_color_ramp):

    # Define file paths.
    path_raster = os.path.join(dir_data, 'raster', 'SDM',
                               raster_subfolder, raster_input_file_name)
    subdir_raster_tiles = '/'.join(['code_output', 'raster_tiles',
                                   'SDM', raster_subfolder])
    dir_raster_tiles = os.path.join(dir_data, subdir_raster_tiles)
    if max_zoom == 'auto':
        name_raster_tiles = '{:}_zoom_auto'.format(raster_key)
    else:
        name_raster_tiles = '{:}_zoom_{:02d}'.format(raster_key, max_zoom)

    dir_raster_tiles = os.path.join(dir_raster_tiles, name_raster_tiles)
    path_color_ramp = os.path.join(dir_data, 'colour_ramps',
                                   '{:}.txt'.format(name_color_ramp))

    # Create tiles (if they do not already exist).
    manifest_file = extract_band_and_generate_tiles(
        input_tiff = path_raster,
        band_index = band_index,
        max_zoom = max_zoom,
        output_dir = dir_raster_tiles,
        data_min = raster_min,
        data_max = raster_max,
        color_ramp_file = path_color_ramp,
        overwrite = overwrite,
    )

    # Upload to AWS. (If the tiles are already there, no transfer will be
    # done.)
    aws_key = '/'.join([subdir_raster_tiles, name_raster_tiles])
    upload_to_aws(dir_raster_tiles, aws_bucket, aws_key, overwrite)

    return

# Example usage
#if __name__ == "__main__":
#    extract_band_and_generate_tiles(
#        input_tiff="path/to/input.tif",
#        band_index=1,
#        max_zoom=10,
#        output_dir="output_tiles",
#        data_min=0,       # replace with real min
#        data_max=100,     # replace with real max
#        color_ramp_file="ramp.txt"
#    )
