import json
import os

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

def get_max_zoom_from_manifest(manifest_path):
    """
    Reads a tile manifest JSON file with keys like "z/x/y.png",
    and returns the highest zoom level (z) present.
    """
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)

    max_zoom = -1
    for key in manifest:
        try:
            z = int(key.split('/')[0])
            if z > max_zoom:
                max_zoom = z
        except (IndexError, ValueError):
            continue  # skip malformed keys

    return max_zoom
