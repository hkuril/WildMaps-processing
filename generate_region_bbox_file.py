#!/usr/bin/env python3
"""
GeoPackage Bounding Box Calculator with Dateline Crossing Support

This script processes a GeoPackage file and computes bounding boxes for each region,
handling dateline crossings properly for use with MapLibre GL JS.
"""

import argparse
import csv
import os
import sys
from pathlib import Path

try:
    import geopandas as gpd
    import pandas as pd
    from shapely.geometry import box, Polygon
    from shapely.ops import unary_union
except ImportError as e:
    print(f"Error: Required package not found: {e}")
    print("Please install required packages:")
    print("pip install geopandas pandas shapely")
    sys.exit(1)


def crosses_dateline(geometry):
    """Check if geometry crosses the international dateline (180/-180 longitude)"""
    bounds = geometry.bounds
    return bounds[2] - bounds[0] > 180  # max_lon - min_lon > 180


def compute_smart_bbox(geometry):
    """
    Compute bounding box handling dateline crossings.
    Returns (lon_min, lat_min, lon_max, lat_max) suitable for MapLibre GL JS.
    """
    if geometry.is_empty:
        return None, None, None, None
    
    # Get all coordinates from the geometry
    if hasattr(geometry, 'geoms'):  # MultiPolygon or GeometryCollection
        coords = []
        for geom in geometry.geoms:
            if hasattr(geom, 'exterior'):  # Polygon
                coords.extend(list(geom.exterior.coords))
                for interior in geom.interiors:
                    coords.extend(list(interior.coords))
            elif hasattr(geom, 'coords'):  # LineString or Point
                coords.extend(list(geom.coords))
    elif hasattr(geometry, 'exterior'):  # Single Polygon
        coords = list(geometry.exterior.coords)
        for interior in geometry.interiors:
            coords.extend(list(interior.coords))
    elif hasattr(geometry, 'coords'):  # LineString or Point
        coords = list(geometry.coords)
    else:
        # Fallback to bounds
        bounds = geometry.bounds
        return bounds[0], bounds[1], bounds[2], bounds[3]
    
    if not coords:
        return None, None, None, None
    
    lons = [coord[0] for coord in coords]
    lats = [coord[1] for coord in coords]
    
    lat_min, lat_max = min(lats), max(lats)
    
    # Smart dateline crossing detection and handling
    lon_min, lon_max = min(lons), max(lons)
    
    # If naive span > 180°, we might have a dateline crossing
    if lon_max - lon_min > 180:
        # Test if the geometry actually crosses the dateline or if it's just spread wide
        # Method: compute the "wrap-around" bounding box and see which makes more sense
        
        # Sort longitudes to analyze distribution
        sorted_lons = sorted(lons)
        
        # Find the largest gap between consecutive longitudes
        max_gap = 0
        gap_start_idx = 0
        
        for i in range(len(sorted_lons) - 1):
            gap = sorted_lons[i + 1] - sorted_lons[i]
            if gap > max_gap:
                max_gap = gap
                gap_start_idx = i
        
        # Also check the wrap-around gap (from largest to smallest + 360)
        wrap_gap = (sorted_lons[0] + 360) - sorted_lons[-1]
        
        # If the largest interior gap is > 180°, or if the wrap-around gap is smaller
        # than the current span, then we likely have a dateline crossing
        current_span = lon_max - lon_min
        
        if max_gap > 180 or wrap_gap < current_span:
            # This looks like a dateline crossing case
            # Use the complement of the largest gap
            if max_gap > wrap_gap:
                # Split at the largest interior gap
                lon_min = sorted_lons[gap_start_idx + 1]
                lon_max = sorted_lons[gap_start_idx]
                # Handle the wraparound case
                if lon_max < lon_min:
                    # This means we're spanning across the dateline
                    # Keep the original bounds but be aware this crosses dateline
                    print(f"    Warning: Geometry appears to cross dateline, bbox may be wide")
                    lon_min, lon_max = min(lons), max(lons)
            else:
                # The wrap-around gap is largest, so use normal bounds
                lon_min, lon_max = min(lons), max(lons)
        
        # Additional heuristic: if we have points on both sides of ±150°, 
        # it's likely a Pacific region crossing the dateline
        far_west = [lon for lon in lons if lon > 150]  # Western Pacific
        far_east = [lon for lon in lons if lon < -150]  # Eastern Pacific
        
        if far_west and far_east:
            # Definitely crosses dateline in Pacific
            # For MapLibre GL JS, we need to decide how to represent this
            # Option 1: Use the side with more points
            # Option 2: Use the side that makes geographic sense
            
            west_count = len(far_west)
            east_count = len(far_east)
            
            # Count points in middle regions too
            middle_west = [lon for lon in lons if 0 <= lon <= 150]
            middle_east = [lon for lon in lons if -150 <= lon < 0]
            
            total_west = len(far_west) + len(middle_west)
            total_east = len(far_east) + len(middle_east)
            
            if total_west > total_east:
                # More points on western side (positive longitudes)
                western_lons = [lon for lon in lons if lon >= 0]
                if western_lons:
                    lon_min, lon_max = min(western_lons), max(western_lons)
            else:
                # More points on eastern side (negative longitudes)  
                eastern_lons = [lon for lon in lons if lon < 0]
                if eastern_lons:
                    lon_min, lon_max = min(eastern_lons), max(eastern_lons)
    
    # Ensure longitude bounds are within valid range
    lon_min = max(-180, min(180, lon_min))
    lon_max = max(-180, min(180, lon_max))
    lat_min = max(-90, min(90, lat_min))
    lat_max = max(-90, min(90, lat_max))
    
    return lon_min, lat_min, lon_max, lat_max


def process_gpkg_to_csv(gpkg_path, csv_path):
    """Process GeoPackage and generate CSV with bounding boxes"""
    try:
        # Read the GeoPackage
        print(f"Reading GeoPackage: {gpkg_path}")
        gdf = gpd.read_file(gpkg_path)
        
        if gdf.empty:
            raise ValueError("GeoPackage contains no data")
        
        # Check if SUBREGION column exists
        if 'SUBREGION' not in gdf.columns:
            raise ValueError("Column 'SUBREGION' not found in GeoPackage")
        
        print(f"Found {len(gdf)} features with {len(gdf['SUBREGION'].unique())} unique subregions")
        
        # Ensure we're working in WGS84 (EPSG:4326) for lat/lon coordinates
        if gdf.crs != 'EPSG:4326':
            print(f"Reprojecting from {gdf.crs} to EPSG:4326")
            gdf = gdf.to_crs('EPSG:4326')
        
        results = []
        
        # Group by SUBREGION and compute bounding boxes
        for subregion in gdf['SUBREGION'].unique():
            if pd.isna(subregion):
                continue
                
            region_geom = gdf[gdf['SUBREGION'] == subregion].geometry
            
            # Union all geometries for this subregion
            union_geom = unary_union(region_geom.values)
            
            # Compute smart bounding box
            lon_min, lat_min, lon_max, lat_max = compute_smart_bbox(union_geom)
            
            if lon_min is not None:  # Valid bbox computed
                results.append({
                    'name': str(subregion),
                    'lon_min': lon_min,
                    'lon_max': lon_max,
                    'lat_min': lat_min,
                    'lat_max': lat_max
                })
                print(f"  {subregion}: [{lon_min:.6f}, {lat_min:.6f}, {lon_max:.6f}, {lat_max:.6f}]")
            else:
                print(f"  Warning: Could not compute bbox for {subregion}")
        
        # Write results to CSV
        if results:
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['name', 'lon_min', 'lon_max', 'lat_min', 'lat_max'])
                writer.writeheader()
                writer.writerows(results)
            
            print(f"\nBounding boxes written to: {csv_path}")
            print(f"Processed {len(results)} regions")
        else:
            raise ValueError("No valid bounding boxes could be computed")
            
    except Exception as e:
        print(f"Error processing GeoPackage: {e}")
        sys.exit(1)


def generate_preview_gpkg(csv_path):
    """Generate preview GeoPackage from CSV bounding boxes"""
    try:
        # Read the CSV
        df = pd.read_csv(csv_path)
        
        if df.empty:
            raise ValueError("CSV file is empty")
        
        # Check required columns
        required_cols = ['name', 'lon_min', 'lon_max', 'lat_min', 'lat_max']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
        
        # Create geometries from bounding boxes
        geometries = []
        for _, row in df.iterrows():
            try:
                # Create rectangle from bounding box
                bbox_geom = box(row['lon_min'], row['lat_min'], row['lon_max'], row['lat_max'])
                geometries.append(bbox_geom)
            except Exception as e:
                print(f"Warning: Could not create geometry for {row['name']}: {e}")
                geometries.append(None)
        
        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame(df, geometry=geometries, crs='EPSG:4326')
        
        # Remove rows with invalid geometries
        gdf = gdf[gdf.geometry.notna()]
        
        if gdf.empty:
            raise ValueError("No valid geometries created from CSV")
        
        # Generate output path
        csv_path_obj = Path(csv_path)
        preview_path = csv_path_obj.parent / f"{csv_path_obj.stem}_preview.gpkg"
        
        # Write preview GeoPackage
        gdf.to_file(preview_path, driver='GPKG')
        
        print(f"Preview GeoPackage generated: {preview_path}")
        print(f"Contains {len(gdf)} bounding box rectangles")
        
    except Exception as e:
        print(f"Error generating preview: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Compute bounding boxes for regions in a GeoPackage with dateline crossing support"
    )
    parser.add_argument('path_gpkg', help='Path to input GeoPackage file')
    parser.add_argument('path_csv_out', help='Path to output CSV file')
    parser.add_argument('--generate_preview', action='store_true',
                       help='Generate preview GeoPackage from existing CSV instead of processing GPKG')
    
    args = parser.parse_args()
    
    # Validate input paths
    if not args.generate_preview:
        if not os.path.exists(args.path_gpkg):
            print(f"Error: GeoPackage file not found: {args.path_gpkg}")
            sys.exit(1)
        
        if not args.path_gpkg.lower().endswith('.gpkg'):
            print("Warning: Input file doesn't have .gpkg extension")
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(os.path.abspath(args.path_csv_out))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    if args.generate_preview:
        # Generate preview from existing CSV
        if not os.path.exists(args.path_csv_out):
            print(f"Error: CSV file not found: {args.path_csv_out}")
            sys.exit(1)
        
        generate_preview_gpkg(args.path_csv_out)
    else:
        # Process GeoPackage to CSV
        process_gpkg_to_csv(args.path_gpkg, args.path_csv_out)


if __name__ == '__main__':
    main()
