#!/usr/bin/env python3

import sys
import argparse
import numpy as np

def main():

    input_file = 'data_inputs/colour_ramps/viridis_1_to_254__1000_stops.txt'
    
    # Read and parse the input file
    try:
        with open(input_file, 'r') as f:
            lines = f.readlines()
        
        # Skip first two rows and final row
        data_lines = lines[2:-1]
        
        # Parse data into arrays
        vals = []
        r_vals = []
        g_vals = []
        b_vals = []
        
        for line in data_lines:
            parts = line.strip().split()
            if len(parts) >= 4:
                vals.append(float(parts[0]))
                r_vals.append(int(parts[1]))
                g_vals.append(int(parts[2]))
                b_vals.append(int(parts[3]))
        
        # Convert to numpy arrays
        vals = np.array(vals)
        r_vals = np.array(r_vals)
        g_vals = np.array(g_vals)
        b_vals = np.array(b_vals)
        
        # Sort by vals to ensure proper interpolation
        sort_indices = np.argsort(vals)
        vals = vals[sort_indices]
        r_vals = r_vals[sort_indices]
        g_vals = g_vals[sort_indices]
        b_vals = b_vals[sort_indices]
        
    except FileNotFoundError:
        print(f"Error: File '{args.input_file}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)
    
    # Define stop values
    stop_values = np.linspace(1.0, 254.0, num = 254)
    
    # Interpolate RGB values using numpy
    r_interp = np.interp(stop_values, vals, r_vals)
    g_interp = np.interp(stop_values, vals, g_vals)
    b_interp = np.interp(stop_values, vals, b_vals)
    
    # Round and convert to integers, then print results
    for i, stop_val in enumerate(stop_values):
        if (i % 10 == 0) or (i == (len(stop_values) - 1)):
            r = int(round(r_interp[i]))
            g = int(round(g_interp[i]))
            b = int(round(b_interp[i]))
            print(f"{stop_val} {r} {g} {b}")

if __name__ == "__main__":
    main()
