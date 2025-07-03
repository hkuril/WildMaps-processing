import pandas as pd
import geopandas as gpd
import sys
from pathlib import Path

def extract_unique_biome_attributes(gpkg_path, output_path, layer_name=None):
    """
    Load geopackage attributes table and extract unique biome information.
    
    Parameters:
    -----------
    gpkg_path : str or Path
        Path to the geopackage file
    output_path : str or Path
        Path where to save the output CSV file
    layer_name : str, optional
        Name of the layer to read. If None, reads the first layer
    """
    
    try:
        # Load geopackage (only attributes, drop geometry)
        print(f"Loading geopackage from: {gpkg_path}")
        
        if layer_name:
            gdf = gpd.read_file(gpkg_path, layer=layer_name)
        else:
            gdf = gpd.read_file(gpkg_path)
        
        # Drop geometry column to work with attributes only
        df = pd.DataFrame(gdf.drop(columns='geometry'))
        
        print(f"Loaded {len(df)} records")
        print(f"Available columns: {list(df.columns)}")
        
        # Check if required columns exist
        #unique_col = 'ECO_BIOME_'
        #unique_col = 'BIOME_NAME'
        unique_col = 'COLOR_BIO'
        #required_columns = [unique_col, 'BIOME_NAME', 'COLOR', 'COLOR_BIO', 'COLOR_NNH']
        #required_columns = [unique_col, 'BIOME_NAME', 'COLOR_BIO',]
        #required_columns = [unique_col, 'COLOR_BIO',]
        required_columns = [unique_col, 'BIOME_NAME',]
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"Warning: Missing columns: {missing_columns}")
            available_columns = [col for col in required_columns if col in df.columns]
            if not available_columns:
                raise ValueError("None of the required columns found in the dataset")
            required_columns = available_columns
        
        # Get unique combinations based on ECO_BIOME_
        print(f"\nExtracting unique values for columns: {required_columns}")
        
        # Group by ECO_BIOME_ and get first occurrence of each group
        # This assumes that ECO_BIOME_ uniquely identifies the other attributes
        other_columns = [col for col in required_columns if col != unique_col]
        unique_biomes = df.groupby(unique_col)[other_columns].first().reset_index()
        
        # Verify uniqueness assumption
        eco_biome_count = len(df[unique_col].unique())
        unique_combinations = len(df[required_columns].drop_duplicates())
        
        print(f"Unique ECO_BIOME_ values: {eco_biome_count}")
        print(f"Unique combinations of all columns: {unique_combinations}")
        
        if eco_biome_count != unique_combinations:
            print("Warning: ECO_BIOME_ values don't have unique combinations of other attributes")
            print("Using drop_duplicates() on all columns instead...")
            unique_biomes = df[required_columns].drop_duplicates().sort_values(unique_col)
        
        print(f"\nFinal unique records: {len(unique_biomes)}")
        
        # Save to specified path
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        unique_biomes.to_csv(output_path, index=False)
        print(f"Saved unique biome attributes to: {output_path}")
        
        # Display preview
        print(f"\nPreview of saved data:")
        print(unique_biomes.head())
        
        return unique_biomes
        
    except Exception as e:
        print(f"Error processing geopackage: {e}")
        sys.exit(1)

def main():
    """
    Main function with example usage.
    Modify the paths below for your specific use case.
    """
    
    # Example paths - modify these for your use case
    gpkg_path = 'data_inputs/vector/ecoregions/Ecoregions2017/Ecoregions2017.gpkg'
    output_path = 'data_inputs/colour_ramps/ecoregions_colours.csv'
    layer_name = None  # or specify layer name if needed
    
    # Check if geopackage exists
    if not Path(gpkg_path).exists():
        print(f"Error: Geopackage file not found at {gpkg_path}")
        print("Please update the gpkg_path variable with the correct path to your geopackage file.")
        return
    
    # Extract unique biome attributes
    unique_data = extract_unique_biome_attributes(gpkg_path, output_path, layer_name)
    
    # Optional: Print summary statistics
    print(f"\nSummary:")
    print(f"Total unique ECO_BIOME_ values: {len(unique_data)}")
    if 'BIOME_NAME' in unique_data.columns:
        print(f"Unique BIOME_NAME values: {unique_data['BIOME_NAME'].nunique()}")

if __name__ == "__main__":
    main()
