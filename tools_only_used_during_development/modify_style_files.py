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

def convert_to_english_only(text_field_value):
    """Convert text-field expressions to English-only labels."""
    # Simple English-only expression that tries multiple English field variants
    return [
        "coalesce",
        ["get", "name:en"],      # Standard English name
        ["get", "name_en"],      # Alternative English name format
        ["get", "name:latin"],   # Latin script fallback
        ["get", "name"]          # Final fallback to default name
    ]

def modify_labels_to_english(style_obj):
    """Modify all text-field properties in layers to show English-only labels."""
    modified_style = json.loads(json.dumps(style_obj))  # Deep copy
    
    def process_layer(layer):
        """Process a single layer, modifying text-field if present."""
        if "layout" in layer and "text-field" in layer["layout"]:
            layer["layout"]["text-field"] = convert_to_english_only(layer["layout"]["text-field"])
        
        # Also check paint properties (some styles put text-field there)
        if "paint" in layer and "text-field" in layer["paint"]:
            layer["paint"]["text-field"] = convert_to_english_only(layer["paint"]["text-field"])
    
    # Process all layers
    for layer in modified_style.get("layers", []):
        process_layer(layer)
    
    return modified_style

def filter_layers(style_obj, keep_types, layer_prefix=""):
    """Return a copy of the style with only specified layer types."""
    filtered = style_obj.copy()
    filtered_layers = []
    
    for layer in style_obj.get("layers", []):
        if layer.get("type") in keep_types:
            # Create a copy of the layer
            new_layer = json.loads(json.dumps(layer))
            
            # Always add prefix to layer ID to ensure uniqueness between overlay/underlay
            if layer_prefix:
                new_layer["id"] = f"{layer_prefix}{layer['id']}"
            
            filtered_layers.append(new_layer)
    
    filtered["layers"] = filtered_layers
    return filtered

def process_style_file(input_path):
    input_path = Path(input_path)
    with open(input_path, "r", encoding="utf-8") as f:
        style = json.load(f)

    # Step 1: Convert labels to English-only
    print("Converting labels to English-only...")
    english_style = modify_labels_to_english(style)

    # Step 2: Recursively replace placeholders
    filled_style = replace_domain(english_style)

    # Save filled version
    filled_path = input_path.with_stem(f"{input_path.stem}_english_filled")
    with open(filled_path, "w", encoding="utf-8") as f:
        json.dump(filled_style, f, indent=2)
    print(f"English-only filled style saved to: {filled_path}")

    # Create overlay and underlay versions with unique prefixes
    overlay_style = filter_layers(filled_style, keep_types={"symbol", "line"}, layer_prefix="ol-")
    underlay_style = filter_layers(filled_style, keep_types={"fill", "background", "raster"}, layer_prefix="ul-")

    overlay_path = input_path.with_stem(f"{input_path.stem}_english_overlay")
    underlay_path = input_path.with_stem(f"{input_path.stem}_english_underlay")

    with open(overlay_path, "w", encoding="utf-8") as f:
        json.dump(overlay_style, f, indent=2)
    print(f"English-only overlay style saved to: {overlay_path}")

    with open(underlay_path, "w", encoding="utf-8") as f:
        json.dump(underlay_style, f, indent=2)
    print(f"English-only underlay style saved to: {underlay_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python modify_style_files.py <path/to/style.json>")
        sys.exit(1)

    process_style_file(sys.argv[1])
