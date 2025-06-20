import json
import sys
from pathlib import Path

TILE_DOMAIN = "tiles.openfreemap.org"
PLACEHOLDER = "__TILEJSON_DOMAIN__"

def replace_domain(value):
    """Recursively replace __TILEJSON_DOMAIN__ in all string values."""
    if isinstance(value, dict):
        return {k: replace_domain(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [replace_domain(v) for v in value]
    elif isinstance(value, str):
        return value.replace(PLACEHOLDER, TILE_DOMAIN)
    else:
        return value

def filter_layers(style_obj, keep_types):
    """Return a copy of the style with only specified layer types."""
    filtered = style_obj.copy()
    filtered["layers"] = [layer for layer in style_obj.get("layers", []) if layer.get("type") in keep_types]
    return filtered

def process_style_file(input_path):
    input_path = Path(input_path)
    with open(input_path, "r", encoding="utf-8") as f:
        style = json.load(f)

    # Recursively replace placeholders
    filled_style = replace_domain(style)

    # Save filled version
    filled_path = input_path.with_stem(f"{input_path.stem}_filled")
    with open(filled_path, "w", encoding="utf-8") as f:
        json.dump(filled_style, f, indent=2)
    print(f"Filled style saved to: {filled_path}")

    # Create overlay and underlay versions
    overlay_style = filter_layers(filled_style, keep_types={"symbol", "line"})
    underlay_style = filter_layers(filled_style, keep_types={"fill", "background", "raster"})

    overlay_path = input_path.with_stem(f"{input_path.stem}_overlay")
    underlay_path = input_path.with_stem(f"{input_path.stem}_underlay")

    with open(overlay_path, "w", encoding="utf-8") as f:
        json.dump(overlay_style, f, indent=2)
    print(f"Overlay style saved to: {overlay_path}")

    with open(underlay_path, "w", encoding="utf-8") as f:
        json.dump(underlay_style, f, indent=2)
    print(f"Underlay style saved to: {underlay_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python split_style.py <path/to/style.json>")
        sys.exit(1)

    process_style_file(sys.argv[1])
