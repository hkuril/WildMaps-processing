'''
Example:
python3 generate_colour_ramp_file_for_raster_tiles.py viridis 256 0 255 ../data/colour_ramps/viridis_0_to_255__256_stops.txt
'''
import numpy as np
import matplotlib.pyplot as plt
import sys

def generate_palette(colormap_name: str, num_stops: int, vmin: float, vmax: float, output_path: str):
    """
    Generate a GDAL-compatible color-relief palette file using a matplotlib colormap.
    
    Parameters:
    - colormap_name (str): Name of the matplotlib colormap (e.g. 'viridis', 'plasma').
    - num_stops (int): Number of value-color stops in the palette.
    - vmin (float): Minimum data value.
    - vmax (float): Maximum data value.
    - output_path (str): Path to save the output palette file.
    """

    cmap = plt.get_cmap(colormap_name)
    values = np.linspace(vmin, vmax, num_stops)
    
    with open(output_path, "w") as f:
        f.write("nv 0 0 0 0\n")  # NoData entry as transparent black
        for val in values:
            rgba = cmap((val - vmin) / (vmax - vmin))  # Normalize to 0–1
            r, g, b = [int(255 * c) for c in rgba[:3]]
            f.write(f"{val:.6f} {r} {g} {b}\n")
    
    print(f"Palette file written to {output_path}")

# Example usage from command line:
# python generate_palette.py viridis 10 0 300 palette.dat

if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Usage: python generate_palette.py <colormap> <num_stops> <vmin> <vmax> <output_path>")
        sys.exit(1)

    colormap_name = sys.argv[1]
    num_stops = int(sys.argv[2])
    vmin = float(sys.argv[3])
    vmax = float(sys.argv[4])
    output_path = sys.argv[5]

    generate_palette(colormap_name, num_stops, vmin, vmax, output_path)
