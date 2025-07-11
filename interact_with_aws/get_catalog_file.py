import os
import argparse

from interact_with_aws.aws_tools import download_file_from_aws
from utilities.handle_logging import set_up_logging

def main():

    set_up_logging('data_outputs')
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Download dataset catalog file from S3')
    parser.add_argument('--overwrite', action='store_true', 
                       help='Overwrite local file if it already exists')
    
    args = parser.parse_args()
    
    # Default parameters
    local_path = "data_inputs/catalogs/dataset_catalog.csv"
    
    # Call the download function
    success = download_file_from_aws(local_path,
                                     overwrite=args.overwrite)
    
    if not success:
        exit(1)

if __name__ == "__main__":
    main()
