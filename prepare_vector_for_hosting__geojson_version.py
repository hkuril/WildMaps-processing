import os
from pathlib import Path
import tempfile

import fiona

from handle_aws import upload_to_aws
from prepare_raster_for_hosting import (run_cmd, create_tile_manifest,
                                        compare_manifest)

def prepare_vector_tiles_wrapper(path_vector_input, dir_vector_tile_out,
                                 max_zoom, attributes_to_keep):
    
    manifest_file = generate_vector_tiles(path_vector_input,
                                          dir_vector_tile_out, max_zoom,
                                          attributes_to_keep)

    ## Upload to AWS. (If the tiles are already there, no transfer will be
    ## done.)
    #aws_key = '/'.join([subdir_vector_tiles, name_vector_tiles])
    #upload_to_aws(dir_vector_tiles, aws_bucket, aws_key, overwrite)

    return

def generate_vector_tiles(vector_file_path, output_dir, max_zoom, attributes):
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
    # Determine file type from extension
    file_path = Path(vector_file_path)
    file_extension = file_path.suffix.lower()

    if file_extension not in ['.gpkg', '.geojson']:
        raise NotImplementedError(f"File format {file_extension} is not supported. Only .gpkg and .geojson are supported.")

    # Get base filename without extension for naming
    base_name = file_path.stem

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    if file_extension == '.gpkg':
        # Handle GeoPackage
        geojson_path = _process_geopackage(vector_file_path, base_name)
    else:
        # Handle GeoJSON - use directly
        geojson_path = vector_file_path

    # Generate tiles using tippecanoe
    _generate_tiles_with_tippecanoe(geojson_path, base_name, max_zoom, attributes, output_dir)

    # Clean up temporary GeoJSON if we created one
    if file_extension == '.gpkg' and geojson_path != vector_file_path:
        os.unlink(geojson_path)


def _process_geopackage(gpkg_path, base_name):
    """
    Process GeoPackage file and convert to GeoJSON.

    Args:
        gpkg_path (str): Path to GeoPackage file
        base_name (str): Base name for output files

    Returns:
        str: Path to generated GeoJSON file

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

    # Create temporary GeoJSON file
    temp_fd, temp_geojson_path = tempfile.mkstemp(suffix='.geojson')
    os.close(temp_fd)  # Close file descriptor, we just need the path
    os.unlink(temp_geojson_path)  # Remove the file so ogr2ogr can create it

    # Convert GeoPackage to GeoJSON
    run_cmd([
        'ogr2ogr',
        '-f', 'GeoJSON',
        temp_geojson_path,
        gpkg_path,
        layer_name
    ])

    return temp_geojson_path


def _generate_tiles_with_tippecanoe(geojson_path, base_name, max_zoom, attributes, output_dir):
    """
    Generate vector tiles using tippecanoe and convert to PBF format.

    Args:
        geojson_path (str): Path to GeoJSON file
        base_name (str): Base name for output files
        max_zoom (int): Maximum zoom level
        attributes (list): List of attributes to include
        output_dir (str): Output directory
    """
    # Create temporary mbtiles file
    temp_fd, temp_mbtiles_path = tempfile.mkstemp(suffix='.mbtiles')
    os.close(temp_fd)
    os.unlink(temp_mbtiles_path)  # Remove the file so tippecanoe can create it

    try:
        # Build tippecanoe command
        tippecanoe_cmd = [
            'tippecanoe',
            '-o', temp_mbtiles_path,
            f'--layer={base_name}',
            '--drop-densest-as-needed',
            '--generate-ids',
            '-Z', '0',
            '-z', str(max_zoom)
        ]

        # Add include attributes
        for attr in attributes:
            tippecanoe_cmd.extend(['--include', attr])

        # Add input file
        tippecanoe_cmd.append(geojson_path)

        # Run tippecanoe
        run_cmd(tippecanoe_cmd)

        # Convert mbtiles to PBF tiles using mb-util
        tiles_dir = os.path.join(output_dir, f'{base_name}_tiles')
        run_cmd([
            'mb-util',
            temp_mbtiles_path,
            tiles_dir,
            '--image_format=pbf'
        ])

        # Gzip all PBF tiles
        run_cmd([
            'find', tiles_dir, '-name', '*.pbf',
            '|', 'parallel', '-j', '+1', '--bar',
            'gzip -n -9 {} && mv {}.gz {}'
        ])

    finally:
        # Clean up temporary mbtiles file
        if os.path.exists(temp_mbtiles_path):
            os.unlink(temp_mbtiles_path)

