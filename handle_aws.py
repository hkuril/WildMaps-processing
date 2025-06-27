import os
import json

import boto3
from botocore.exceptions import ClientError
from tqdm import tqdm

aws_bucket = "habitat-web-map"

def upload_to_aws(dir_path_local, bucket, key, overwrite):
    session = boto3.Session(profile_name="habitat-maintainer")
    s3 = session.client('s3')

    local_manifest_path = os.path.join(dir_path_local, '.tile_manifest.json')
    if not os.path.isfile(local_manifest_path):
        print("Local manifest file not found:", local_manifest_path)
        return

    # Check if remote manifest exists
    remote_manifest_key = f"{key}/.tile_manifest.json"
    skip_upload = False

    if overwrite != 'yes':
        try:
            remote_manifest_obj = s3.get_object(Bucket=bucket, Key=remote_manifest_key)
            remote_manifest = remote_manifest_obj['Body'].read().decode('utf-8')
            with open(local_manifest_path, 'r') as f:
                local_manifest = f.read()
            if remote_manifest.strip() == local_manifest.strip():
                print("Manifest matches remote copy. Skipping upload.")
                skip_upload = True
        except ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchKey':
                raise
            print("Remote manifest not found. Proceeding with upload.")

    if skip_upload:
        return

    # Walk through all files in dir_path_local
    file_paths = []
    for root, _, files in os.walk(dir_path_local):
        for file in files:
            full_path = os.path.join(root, file)
            relative_path = os.path.relpath(full_path, dir_path_local)
            if not (full_path.endswith('.png') or
                    full_path.endswith('.json') or
                    full_path.endswith('.pbf')
                    ):
                continue
            s3_key = f"{key}/{relative_path.replace(os.sep, '/')}"
            file_paths.append((full_path, s3_key))

    print(f"Uploading {len(file_paths)} files to s3://{bucket}/{key}/")
    for full_path, s3_key in tqdm(file_paths, desc="Uploading tiles", unit="file"):
        
        # Set the content type.
        if full_path.endswith('.json'):
            content_type = 'application/json'
        elif full_path.endswith('.png'):
            content_type = 'image/png'
        elif full_path.endswith('.pbf'):
            content_type = 'application/x-protobuf'
        else: 
            content_type = None

        if content_type is not None:
            extra_args  = {'ContentType': content_type}
            if content_type == 'application/x-protobuf':
                extra_args['ContentEncoding'] = 'gzip'
        else:
            extra_args = None

        s3.upload_file(Filename=full_path, Bucket=bucket, Key=s3_key,
                       ExtraArgs = extra_args,
                       )

    print("Upload complete.")
