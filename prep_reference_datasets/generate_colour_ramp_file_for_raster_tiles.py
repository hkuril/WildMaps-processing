'''
Example:
python3 generate_colour_ramp_file_for_raster_tiles.py plasma 1000 1 254 ../data/colour_ramps/plasma_1_to_254__1000_stops_log.txt geomspace
'''
import numpy as np
import matplotlib.pyplot as plt
import sys

def generate_palette(colormap_name: str, num_stops: int, vmin: float, vmax: float, output_path: str, type_: str):
    """
    Generate a GDAL-compatible color-relief palette file using a matplotlib colormap.
    
    Parameters:
    - colormap_name (str): Name of the matplotlib colormap (e.g. 'viridis', 'plasma').
    - num_stops (int): Number of value-color stops in the palette.
    - vmin (float): Minimum data value.
    - vmax (float): Maximum data value.
    - output_path (str): Path to save the output palette file.
    """

    assert type_ in ['linspace', 'geomspace']

    cmap = plt.get_cmap(colormap_name)
    v_range = vmax - vmin
    if type_ == 'linspace':
        values = np.linspace(vmin, vmax, num_stops)
    else:
        values = np.geomspace(vmin, vmax, num_stops)

    pad = 1.0 / (num_stops - 1)
     
    with open(output_path, "w") as f:
        f.write("nv 0 0 0 0\n")  # NoData entry as transparent black
        for i, val in enumerate(values):
            val_norm = (val - vmin) / (vmax - vmin) 
            rgba = cmap(val_norm)
            r, g, b = [int(255 * c) for c in rgba[:3]]

            if (i == 0):
                val_i = val - pad
                f.write(f"{val_i:.6f} {r} {g} {b}\n")

            f.write(f"{val:.6f} {r} {g} {b}\n")

            if (i == num_stops - 1):
                val_i = val + pad
                f.write(f"{val_i:.6f} {r} {g} {b}\n")

    logging.info(f"Palette file written to {output_path}")

# Example usage from command line:
# python generate_palette.py viridis 10 0 300 palette.dat

if __name__ == "__main__":
    if len(sys.argv) != 7:
        logging.info("Usage: python generate_palette.py <colormap> <num_stops> <vmin> <vmax> <output_path> <type_> (linspace or geomspace)")
        sys.exit(1)

    colormap_name = sys.argv[1]
    num_stops = int(sys.argv[2])
    vmin = float(sys.argv[3])
    vmax = float(sys.argv[4])
    output_path = sys.argv[5]
    type_ = sys.argv[6]

    generate_palette(colormap_name, num_stops, vmin, vmax, output_path, type_)
