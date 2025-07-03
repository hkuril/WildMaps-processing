#!/usr/bin/env python3

import sys
import argparse
import numpy as np

def main():
    parser = argparse.ArgumentParser(description='Interpolate RGB values from colormap data')
    parser.add_argument('input_file', help='Path to input text file')
    args = parser.parse_args()
    
    # Read and parse the input file
    try:
        with open(args.input_file, 'r') as f:
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
    stop_values = [0, 30, 100, 300, 1000, 3000]
    
    # Scale stop values from 0-3000 to 1-254
    scaled_stops = 1 + (np.array(stop_values) / 3000) * (254 - 1)
    
    # Interpolate RGB values using numpy
    r_interp = np.interp(scaled_stops, vals, r_vals)
    g_interp = np.interp(scaled_stops, vals, g_vals)
    b_interp = np.interp(scaled_stops, vals, b_vals)
    
    # Round and convert to integers, then print results
    for i, stop_val in enumerate(stop_values):
        r = int(round(r_interp[i]))
        g = int(round(g_interp[i]))
        b = int(round(b_interp[i]))
        print(f"{stop_val} {r} {g} {b}")

if __name__ == "__main__":
    main()
