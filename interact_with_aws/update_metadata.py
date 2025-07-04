import json
import logging

from analyse_rasters.get_ready_for_processing import (
        custom_JSON_encoder,
        define_results_path_for_dataset,
        get_ready_wrapper,
        load_all_results_from_aws,)
from interact_with_aws.aws_tools import (
        write_json_and_upload_to_s3)
from process_SDM_rasters import (
        write_dataset_summary_file,
        write_json_and_upload_to_s3,
        )

def main():

    # Get the project directory. 
    #dir_base = os.path.dirname(os.path.abspath(__file__))
    dir_base = ''

    # Sets up logging too!
    # Get the catalog as well as file paths and metadata keys. 
    (dir_data, dir_output, catalog,
        _, _, _, _, _) = get_ready_wrapper(dir_base)

    # Get all the results (not just local files).
    results = load_all_results_from_aws(dir_output, catalog)

    logging.info('Before update:')
    logging.info(json.dumps(results, indent=2, cls = custom_JSON_encoder))

    metadata_columns_to_update = ['source_link', 'source_contact',
                                  'source_text', 'download_link']
    # Loop through all the datasets in the catalog.
    for dataset_name, dataset in catalog.iterrows():
        
        # Skip datasets that are set to ignore.
        if dataset['ignore'] == 'yes':
            continue

        for metadata_col in metadata_columns_to_update:

            results[dataset_name][metadata_col] =\
                dataset[metadata_col]
    
    logging.info('After update:')
    logging.info(json.dumps(results, indent=2, cls = custom_JSON_encoder))

    for dataset_name, results_ in results.items():

        path_dataset_results = define_results_path_for_dataset(
                dir_output, dataset_name)
        write_json_and_upload_to_s3(results_, path_dataset_results,
                                    encoder = custom_JSON_encoder)

    write_dataset_summary_file(dir_output, results)

    return

if __name__ == '__main__':

    main()
