import os

from interact_with_aws.aws_tools import upload_file_to_aws
from utilities.handle_logging import set_up_logging

def main():

    set_up_logging('data_outputs')

    dir_data_inputs = 'data_inputs'
    dir_dictionaries = os.path.join(dir_data_inputs, 'dictionaries')
    dir_styles = os.path.join(dir_data_inputs, 'styles')
    dir_colour_ramps = os.path.join(dir_data_inputs, 'colour_ramps')

    dicts_to_send = ['region', 'subregion', 'superspecies', 'species']
    paths = []
    for dict_ in dicts_to_send:

        path_dict_to_send = os.path.join(dir_dictionaries,
                                     '{:}_dictionary.csv'.format(dict_))
        paths.append(path_dict_to_send)

    styles_to_send = [
        'positron_english_underlay',                               
        'positron_english_overlay',                               
        'esri_world_imagery',                                      
        'mapzen_elevation_and_hillshade',                          
        'worldpop',                                                
        'landcover',                                               
        'ecoregions',                                              
        'wdpa',                                              
        ]
    for style in styles_to_send:
        path_ = os.path.join(dir_styles, '{:}.json'.format(style))
        paths.append(path_)

    paths.append(os.path.join(dir_colour_ramps, 'un_lcc_color_scheme.csv'))
    paths.append(os.path.join(dir_data_inputs, 'website_assets', 'splash_page_animation.mp4'))
    paths.append(os.path.join(dir_data_inputs, 'website_assets', 'wildmaps_logo.png'))
    
    for path_ in paths:
        
        upload_file_to_aws(path_, overwrite = True,
                           auto_headers = True)

    return

if __name__ == "__main__":

    main()
