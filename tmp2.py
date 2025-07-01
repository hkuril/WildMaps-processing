import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# Use the Viridis colormap
cmap = plt.get_cmap('viridis')

# Define the halfway points between the given stops
sample_points = [0.125, 0.375, 0.625, 0.875]

# Convert to hex
hex_colors = [mcolors.to_hex(cmap(p)) for p in sample_points]

# Print the hex color strings
for i, hex_color in enumerate(hex_colors):
    print(f"Point {sample_points[i]:.3f}: {hex_color}")

