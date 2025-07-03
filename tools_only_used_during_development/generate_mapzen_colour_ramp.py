import argparse

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import matplotlib.cm as cm

def generate_color_ramp(below_water_stops, below_water_colormap, 
                       above_water_stops, above_water_colormap):
    """
    Generate a color ramp with normalized sampling across uneven intervals.
    
    Parameters:
    -----------
    below_water_stops : list
        List of elevation stops below water (should be negative values)
    below_water_colormap : str
        Name of matplotlib colormap for below water areas
    above_water_stops : list
        List of elevation stops above water (should be positive values, starting with 0)
    above_water_colormap : str
        Name of matplotlib colormap for above water areas
    
    Returns:
    --------
    str : Formatted color ramp text
    """
    
    def get_normalized_colors(stops, colormap_name, start = 0):
        """Get colors with normalized sampling between stops."""
        if len(stops) < 2:
            return []
            
        # Get the colormap
        cmap = cm.get_cmap(colormap_name)
        
        # Create normalized positions (0 to 1) for each stop
        # This ensures even color distribution regardless of data spacing
        normalized_positions = np.linspace(start, 1, len(stops))
        
        colors = []
        for i, (stop, norm_pos) in enumerate(zip(stops, normalized_positions)):
            # Sample the colormap at the normalized position
            print(norm_pos)
            rgba = cmap(norm_pos)
            # Convert to RGB values (0-255)
            rgb = tuple(int(c * 255) for c in rgba[:3])
            colors.append((stop, f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})"))
        
        return colors
    
    # Sort stops to ensure proper ordering
    below_water_stops = sorted(below_water_stops)
    above_water_stops = sorted(above_water_stops)
    
    # Generate colors for each section
    start_above = 0.0
    #start_above = 0.25
    below_water_colors = get_normalized_colors(below_water_stops, below_water_colormap)
    above_water_colors = get_normalized_colors(above_water_stops, above_water_colormap, start = start_above)
    
    # Combine all colors
    all_colors = below_water_colors + above_water_colors
    
    # Format output
    output_lines = []
    for stop, color in all_colors:
        # Format similar to the input example
        line = f"          {stop}, \"{color}\","
        output_lines.append(line)
    
    return "\n".join(output_lines), start_above

def preview_colormap(colormap_name, stops, title="", show = True, start = 0.0):
    """
    Preview a matplotlib colormap with stop values labeled.
    """
    try:
        cmap = cm.get_cmap(colormap_name)
        fig, ax = plt.subplots(figsize=(12, 2))
        
        # Create gradient
        gradient = np.linspace(0, 1, 256).reshape(1, -1)
        ax.imshow(gradient, aspect='auto', cmap=cmap, extent=[0, 1, 0, 1])
        
        # Add stop value labels
        if stops:
            # Calculate positions for each stop (normalized 0-1)
            normalized_positions = np.linspace(start, 1, len(stops))
            
            for i, (pos, stop) in enumerate(zip(normalized_positions, stops)):
                # Add vertical line at stop position
                ax.axvline(x=pos, color='black', linestyle='--', alpha=0.7, linewidth=1)
                
                # Add stop value label
                ax.text(pos, 1.1, str(stop), ha='center', va='bottom', 
                       fontsize=10, rotation=45 if len(str(stop)) > 4 else 0)
        
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_yticks([])
        ax.set_xticks([])
        ax.set_title(f"{title} - {colormap_name}")
        
        # Extend y-axis to accommodate labels
        ax.set_ylim(0, 1.3)
        
        plt.tight_layout()
        if show:
            plt.show()
    except Exception as e:
        print(f"Error previewing colormap '{colormap_name}': {e}")

# Example usage
if __name__ == "__main__":

    
    parser = argparse.ArgumentParser(description='Generate color ramp for bathymetry/topography data')
    parser.add_argument('output_path', help='Output file path to save the color ramp')
    parser.add_argument('--preview', action='store_true', help='Show colormap previews')
    
    args = parser.parse_args()
    
    # Define your stops
    below_water_stops = [-11000, -8000, -5000, -2000, -500, -1]
    above_water_stops = [0, 200, 500, 1000, 2000, 3000, 4000, 5000, 6000, 8000]
    
    # Choose colormaps
    #below_water_cmap = "Blues_r"  # Reversed blues (dark to light)
    below_water_cmap = "Greys_r"  # Reversed blues (dark to light)
    #above_water_cmap = "RdPu_r"   
    #above_water_cmap = "OrRd_r"   
    #above_water_cmap = "cubehelix"   
    above_water_cmap = "cividis"   
    
    # Generate the color ramp
    color_ramp, start_above = generate_color_ramp(
        below_water_stops, below_water_cmap,
        above_water_stops, above_water_cmap
    )
    
    # Save to file
    try:
        with open(args.output_path, 'w') as f:
            f.write(color_ramp)
        print(f"Color ramp saved to: {args.output_path}")
    except Exception as e:
        print(f"Error saving file: {e}")
        exit(1)
    
    # Optional: Preview the colormaps
    if args.preview:
        print("\nPreviewing colormaps...")
        preview_colormap(below_water_cmap, below_water_stops, "Below Water", show =False)
        preview_colormap(above_water_cmap, above_water_stops, "Above Water", start = start_above)
        
        # Show some popular colormap options
        print("\nPopular colormap options:")
        print("Below water: 'Blues_r', 'viridis_r', 'plasma_r', 'cool', 'winter'")
        print("Above water: 'terrain', 'gist_earth', 'copper', 'hot', 'autumn', 'Oranges'")
