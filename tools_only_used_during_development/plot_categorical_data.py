import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

def display_categorical_data(data, color_palette_file):
    """
    Display a 2D array of categorical data using a color mapping
    from a CSV file with columns: code, r, g, b (RGB in 0–255).
    
    Parameters:
    - data: 2D numpy array of integers representing category codes.
    """
    # Load color mapping from CSV
    color_map_df = pd.read_csv(color_palette_file)

    # Normalize RGB values to [0, 1]
    color_map_df[['r', 'g', 'b']] = color_map_df[['r', 'g', 'b']] / 255.0

    # Build a dictionary mapping codes to RGB tuples
    code_to_rgb = dict(zip(color_map_df['code'], color_map_df[['r', 'g', 'b']].apply(tuple, axis=1)))

    # Initialize the RGB image
    rgb_image = np.zeros(data.shape + (3,), dtype=float)

    # Apply color mapping
    for code, rgb in code_to_rgb.items():
        rgb_image[data == code] = rgb

    # Display the image
    plt.imshow(rgb_image)
    plt.axis('off')
    plt.show()
