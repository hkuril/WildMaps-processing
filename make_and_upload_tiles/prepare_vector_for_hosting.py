import logging
import os
from pathlib import Path
import tempfile

import fiona

from interact_with_aws.aws_tools import upload_tiles_to_aws
from prepare_raster_for_hosting import (run_cmd, create_tile_manifest,
                                        compare_manifest)

def prepare_vector_tiles_wrapper(path_vector_input, dir_vector_tile_out,
                                 subdir_tiles, name_tiles, max_zoom,
                                 attributes_to_keep, overwrite):
    
    manifest_file = generate_vector_tiles(path_vector_input,
                                          dir_vector_tile_out, max_zoom,
                                          attributes_to_keep, overwrite)

    # Upload to AWS. (If the tiles are already there, no transfer will be
    # done.)
    aws_key = '/'.join([subdir_tiles, name_tiles])
    upload_tiles_to_aws(dir_vector_tile_out, aws_key, overwrite)

    return

def generate_vector_tiles(vector_file_path, output_dir, max_zoom, attributes, overwrite):
    """
    Generate vector tiles from a vector file (GeoPackage or GeoJSON).
    
    Args:
        vector_file_path (str): Path to the input vector file
        output_dir (str): Directory where output tiles will be stored
        max_zoom (int): Maximum zoom level for tiles
        attributes (list): List of attribute names to include in tiles
        
    Raises:
        NotImplementedError: If file format is not supported
        ValueError: If GeoPackage has multiple layers
    """

    # Check if the manifest file exists, and if it matches, skip the
    # tile generation unless overwrite is requested.
    manifest_file = os.path.join(output_dir, ".tile_manifest.json")
    if (os.path.exists(output_dir) and
        compare_manifest(output_dir, manifest_file) and overwrite == 'no'):
        logging.info("Tiles match manifest file {:}. Skipping generation.".format(
            manifest_file))
        return

    # Determine file type from extension
    file_path = Path(vector_file_path)
    file_extension = file_path.suffix.lower()
    
    if file_extension not in ['.gpkg', '.geojson']:
        raise NotImplementedError(f"File format {file_extension} is not supported. Only .gpkg and .geojson are supported.")
    
    # Get base filename without extension for naming
    base_name = file_path.stem
    output_layer_name = '_'.join(Path(output_dir).stem.split('_')[:-1])
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    if file_extension == '.gpkg':
        # Handle GeoPackage - convert to FlatGeobuf
        fgb_path = _process_geopackage(vector_file_path, base_name)
    else:
        # Handle GeoJSON - use directly with tippecanoe
        fgb_path = vector_file_path
    
    # Generate tiles directly to PBF directory using tippecanoe
    _generate_tiles_direct(fgb_path, max_zoom, attributes, output_dir,
                           output_layer_name)
    
    # Clean up temporary FlatGeobuf if we created one
    if file_extension == '.gpkg' and fgb_path != vector_file_path:
        os.unlink(fgb_path)

    # Create the tile manifest.
    logging.info("Tile generation complete. Saving manifest to {:}".format(
        manifest_file))
    create_tile_manifest(output_dir, manifest_file)

    return

def _process_geopackage(gpkg_path, base_name):
    """
    Process GeoPackage file and convert to FlatGeobuf.
    
    Args:
        gpkg_path (str): Path to GeoPackage file
        base_name (str): Base name for output files
        
    Returns:
        str: Path to generated FlatGeobuf file
        
    Raises:
        ValueError: If GeoPackage has multiple layers
    """
    # Get layer names from GeoPackage using fiona
    layers = fiona.listlayers(gpkg_path)
    
    if len(layers) > 1:
        raise ValueError(f"GeoPackage contains {len(layers)} layers. Only single-layer GeoPackages are supported.")
    
    if len(layers) == 0:
        raise ValueError("GeoPackage contains no layers.")
    
    layer_name = layers[0]
    
    # Create temporary FlatGeobuf file
    temp_fd, temp_fgb_path = tempfile.mkstemp(suffix='.fgb')
    os.close(temp_fd)  # Close file descriptor, we just need the path
    os.unlink(temp_fgb_path)  # Remove the file so ogr2ogr can create it
    
    # Convert GeoPackage to FlatGeobuf with progress bar
    run_cmd([
        'ogr2ogr',
        '-f', 'FlatGeobuf',
        '-progress',  # Show progress bar
        temp_fgb_path,
        gpkg_path,
        layer_name
    ])
    
    return temp_fgb_path

def _generate_tiles_direct(input_path, max_zoom, attributes, output_dir,
                           output_layer_name):
    """
    Generate vector tiles directly to PBF directory using tippecanoe.
    
    Args:
        input_path (str): Path to input file (FlatGeobuf or GeoJSON)
        base_name (str): Base name for output files
        max_zoom (int): Maximum zoom level
        attributes (list): List of attributes to include
        output_dir (str): Output directory
    """
    # Create tiles directory
    #tiles_dir = os.path.join(output_dir, f'{base_name}_tiles')
    
    # Build tippecanoe command
    tippecanoe_cmd = [
        'tippecanoe',
        '--output-to-directory', output_dir,
        f'--layer={output_layer_name}',
        #'--drop-densest-as-needed',
        '--drop-smallest-as-needed',
        #'--coalesce-smallest-as-needed', # too slow
        #'--coalesce', # not good
        '--generate-ids',
        '--force',
        '-Z', '0',
        '-z', str(max_zoom)
    ]
    
    # Add include attributes
    for attr in attributes:
        tippecanoe_cmd.extend(['--include', attr])
    
    # Add input file
    tippecanoe_cmd.append(input_path)
    
    # Run tippecanoe (outputs compressed PBF tiles directly)
    run_cmd(tippecanoe_cmd)
