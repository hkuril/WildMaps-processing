#!/usr/bin/env python3
import logging
import os
import shutil
import re
from pathlib import Path

from interact_with_aws.aws_tools import (clear_s3_directory,
                                         upload_file_to_aws)
from utilities.use_command_line import run_cmd
from utilities.handle_logging import set_up_logging

def deploy_website(aws_base_url="https://your-bucket.s3.amazonaws.com"):
    """
    Build and deploy website to AWS with updated asset URLs
    """
    # Store the starting directory
    start_dir = os.getcwd()
    
    try:
        # Step 1: Build the website
        print("Building website...")
        website_dir = '../WildMaps-website/'
        os.chdir(website_dir)
        run_cmd(['npm', 'run', 'build'])
        
        # Step 2: Go back to starting directory
        print("Returning to starting directory...")
        os.chdir(start_dir)
        
        # Step 3: Copy dist files to website_dist
        print("Copying dist files...")
        dist_source = '../WildMaps-website/dist/'
        dist_dest = 'website_dist/'
        
        ## Remove existing website_dist if it exists
        #if os.path.exists(dist_dest):
        #    for item in os.listdir(dist_dest):
        #        if item != '.gitkeep':
        #            item_path = os.path.join(dist_dest, item)
        #            if os.path.isdir(item_path):
        #                shutil.rmtree(item_path)
        #            else:
        #                os.remove(item_path)

        # Remove existing website_dist if it exists
        if os.path.exists(dist_dest):
            shutil.rmtree(dist_dest)
        
        # Copy the entire dist directory
        shutil.copytree(dist_source, dist_dest)

        gitkeep_path = Path(dist_dest) / ".gitkeep"
        gitkeep_path.touch()

        # Step 3.5: Clear existing files on S3
        print("Clearing existing files on S3...")
        clear_s3_directory('wildcru-wildmaps', 'website_dist/')
        
        # Step 4: Upload files to AWS
        print("Uploading files to AWS...")
        
        # Upload CSS file with appropriate headers
        css_files = list(Path(dist_dest).glob('assets/*.css'))
        for css_file in css_files:
            upload_file_to_aws(str(css_file), headers={'Content-Type': 'text/css'}, overwrite = True)
        
        # Upload JS files with appropriate headers
        js_files = list(Path(dist_dest).glob('assets/*.js'))
        for js_file in js_files:
            upload_file_to_aws(str(js_file), headers={'Content-Type': 'application/javascript'}, overwrite = True)
        
        # Upload HTML file with appropriate headers
        html_file = os.path.join(dist_dest, 'index.html')
        upload_file_to_aws(html_file, headers={'Content-Type': 'text/html'},
                           overwrite = True)
        
        # Step 5: Modify index.html to point to AWS URLs
        print("Updating asset URLs in index.html...")
        update_html_asset_urls(html_file, aws_base_url)
        
        # Re-upload the modified HTML file
        upload_file_to_aws(html_file, headers={'Content-Type': 'text/html'},
                           overwrite = True)
        
        print("Deployment completed successfully!")
        
    except Exception as e:
        print(f"Error during deployment: {e}")
        # Make sure we return to starting directory even if there's an error
        os.chdir(start_dir)
        raise

def update_html_asset_urls(html_file_path, aws_base_url="https://your-bucket.s3.amazonaws.com"):
    """
    Update the HTML file to point asset URLs to AWS
    
    Args:
        html_file_path: Path to the HTML file
        aws_base_url: Base URL for your AWS S3 bucket (update this with your actual bucket URL)
    """
    with open(html_file_path, 'r', encoding='utf-8') as file:
        html_content = file.read()
    
    # Pattern to match /assets/, ./assets/, or assets/ references
    # This will match href="/assets/..." and src="/assets/..." 
    asset_pattern = r'(href|src)="(\.?/?assets/[^"]+)"'
    
    def replace_asset_url(match):
        attribute = match.group(1)  # 'href' or 'src'
        old_path = match.group(2)   # the full path like "/assets/index-CGV6iwgK.js"
        # Extract just the filename part after "assets/"
        filename = old_path.split('assets/')[-1]
        #new_url = f'{attribute}="{aws_base_url}/assets/{filename}"'
        new_url = f'{attribute}="{aws_base_url}/website_dist/assets/{filename}"'
        print(f"Replacing: {match.group(0)} -> {new_url}")
        return new_url
    
    # Apply the replacement
    updated_content = re.sub(asset_pattern, replace_asset_url, html_content)
    
    # Write the updated content back to the file
    with open(html_file_path, 'w', encoding='utf-8') as file:
        file.write(updated_content)
    
    print(f"Updated asset URLs in {html_file_path}")

def get_asset_filenames(dist_dir):
    """
    Helper function to get the actual asset filenames for reference
    """
    assets_dir = os.path.join(dist_dir, 'assets')
    if not os.path.exists(assets_dir):
        return [], []
    
    css_files = [f for f in os.listdir(assets_dir) if f.endswith('.css')]
    js_files = [f for f in os.listdir(assets_dir) if f.endswith('.js')]
    
    return css_files, js_files

if __name__ == "__main__":
    
    set_up_logging("data_outputs")
    aws_base_url = "https://wildcru-wildmaps.s3.amazonaws.com"
    deploy_website(aws_base_url)
