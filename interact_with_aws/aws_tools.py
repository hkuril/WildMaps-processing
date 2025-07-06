import logging 
import mimetypes
import json
import os
from pathlib import Path
import tempfile

import boto3
from botocore.exceptions import ClientError
from tqdm import tqdm

AWS_PROFILE_NAME = "WildMapsMaintainer"
AWS_BUCKET = "wildcru-wildmaps"


def download_file_from_aws(local_path, bucket = None, key = None, overwrite=False):
    """
    Download a file from S3 to local path.
    
    Args:
        local_path (str): Local file path where to save the downloaded file
        bucket (str): S3 bucket name
        key (str): S3 object key
        overwrite (bool): Whether to overwrite existing local file
    """

    if bucket is None:
        bucket = AWS_BUCKET

    if key is None:
        key = local_path
    
    # Check if local file already exists
    if os.path.exists(local_path) and not overwrite:
        logging.warning(f"Local file already exists: {local_path}")
        logging.warning("Use --overwrite to force download and replace the existing file.")
        return False
    
    # Create local directory if it doesn't exist
    local_dir = os.path.dirname(local_path)
    if local_dir and not os.path.exists(local_dir):
        os.makedirs(local_dir, exist_ok=True)
        logging.info(f"Created directory: {local_dir}")
    
    # Initialize S3 client with profile
    session = boto3.Session(profile_name=AWS_PROFILE_NAME)
    s3 = session.client('s3')
    
    try:
        logging.info(f"Downloading s3://{bucket}/{key} to {local_path}")
        s3.download_file(Bucket=bucket, Key=key, Filename=local_path)
        logging.info("Download complete.")
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            logging.error(f"File not found in S3: s3://{bucket}/{key}")
        else:
            logging.error(f"Error downloading file: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return False

def get_default_headers_for_file(file_path):
    """
    Get default headers based on file extension.

    Args:
        file_path (str): Path to the file

    Returns:
        dict: Dictionary of default headers
    """
    headers = {}

    # Get file extension
    file_extension = Path(file_path).suffix.lower()

    # Guess MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        headers['Content-Type'] = mime_type

    # Extension-specific headers
    extension_headers = {
        # Web assets
        '.css': {
            'Content-Type': 'text/css',
            'Cache-Control': 'public, max-age=31536000'  # 1 year
        },
        '.js': {
            'Content-Type': 'application/javascript',
            'Cache-Control': 'public, max-age=31536000'  # 1 year
        },
        '.html': {
            'Content-Type': 'text/html; charset=utf-8',
            'Cache-Control': 'public, max-age=3600'  # 1 hour
        },
        '.htm': {
            'Content-Type': 'text/html; charset=utf-8',
            'Cache-Control': 'public, max-age=3600'  # 1 hour
        },

        # Images
        '.jpg': {
            'Content-Type': 'image/jpeg',
            'Cache-Control': 'public, max-age=31536000'  # 1 year
        },
        '.jpeg': {
            'Content-Type': 'image/jpeg',
            'Cache-Control': 'public, max-age=31536000'  # 1 year
        },
        '.png': {
            'Content-Type': 'image/png',
            'Cache-Control': 'public, max-age=31536000'  # 1 year
        },
        '.gif': {
            'Content-Type': 'image/gif',
            'Cache-Control': 'public, max-age=31536000'  # 1 year
        },
        '.svg': {
            'Content-Type': 'image/svg+xml',
            'Cache-Control': 'public, max-age=31536000'  # 1 year
        },
        '.webp': {
            'Content-Type': 'image/webp',
            'Cache-Control': 'public, max-age=31536000'  # 1 year
        },
        '.ico': {
            'Content-Type': 'image/x-icon',
            'Cache-Control': 'public, max-age=31536000'  # 1 year
        },

        # Fonts
        '.woff': {
            'Content-Type': 'font/woff',
            'Cache-Control': 'public, max-age=31536000'  # 1 year
        },
        '.woff2': {
            'Content-Type': 'font/woff2',
            'Cache-Control': 'public, max-age=31536000'  # 1 year
        },
        '.ttf': {
            'Content-Type': 'font/ttf',
            'Cache-Control': 'public, max-age=31536000'  # 1 year
        },
        '.otf': {
            'Content-Type': 'font/otf',
            'Cache-Control': 'public, max-age=31536000'  # 1 year
        },

        # Documents
        '.pdf': {
            'Content-Type': 'application/pdf',
            'Cache-Control': 'public, max-age=86400'  # 1 day
        },
        '.doc': {
            'Content-Type': 'application/msword',
            'Cache-Control': 'public, max-age=86400'  # 1 day
        },
        '.docx': {
            'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'Cache-Control': 'public, max-age=86400'  # 1 day
        },
        '.xls': {
            'Content-Type': 'application/vnd.ms-excel',
            'Cache-Control': 'public, max-age=86400'  # 1 day
        },
        '.xlsx': {
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'Cache-Control': 'public, max-age=86400'  # 1 day
        },

        # Data formats
        '.json': {
            'Content-Type': 'application/json',
            'Cache-Control': 'public, max-age=3600'  # 1 hour
        },
        '.xml': {
            'Content-Type': 'application/xml',
            'Cache-Control': 'public, max-age=3600'  # 1 hour
        },
        '.csv': {
            'Content-Type': 'text/csv',
            'Cache-Control': 'public, max-age=3600'  # 1 hour
        },
        '.txt': {
            'Content-Type': 'text/plain; charset=utf-8',
            'Cache-Control': 'public, max-age=3600'  # 1 hour
        },

        # Video
        '.mp4': {
            'Content-Type': 'video/mp4',
            'Cache-Control': 'public, max-age=31536000'  # 1 year
        },
        '.webm': {
            'Content-Type': 'video/webm',
            'Cache-Control': 'public, max-age=31536000'  # 1 year
        },

        # Audio
        '.mp3': {
            'Content-Type': 'audio/mpeg',
            'Cache-Control': 'public, max-age=31536000'  # 1 year
        },
        '.wav': {
            'Content-Type': 'audio/wav',
            'Cache-Control': 'public, max-age=31536000'  # 1 year
        },
        '.ogg': {
            'Content-Type': 'audio/ogg',
            'Cache-Control': 'public, max-age=31536000'  # 1 year
        },

        # Archives
        '.zip': {
            'Content-Type': 'application/zip',
            'Cache-Control': 'public, max-age=86400'  # 1 day
        },
        '.gz': {
            'Content-Type': 'application/gzip',
            'Cache-Control': 'public, max-age=86400'  # 1 day
        },
        '.tar': {
            'Content-Type': 'application/x-tar',
            'Cache-Control': 'public, max-age=86400'  # 1 day
        }
    }

    # Apply extension-specific headers
    if file_extension in extension_headers:
        headers.update(extension_headers[file_extension])

    return headers

def upload_file_to_aws(local_path, bucket=None, key=None, overwrite=False, headers=None, auto_headers=False):
    """
    Upload a file from local path to S3.

    Args:
        local_path (str): Local file path to upload
        bucket (str): S3 bucket name
        key (str): S3 object key (destination path in S3)
        overwrite (bool): Whether to overwrite existing S3 object
        headers (dict): Optional headers to set on the S3 object (e.g., {'Content-Type': 'text/css'})
        auto_headers (bool): Whether to automatically add headers based on file extension
    """
    if bucket is None:
        bucket = AWS_BUCKET
    if key is None:
        key = local_path

    # Check if local file exists
    if not os.path.exists(local_path):
        logging.error(f"**Local file does not exist: {local_path}**")
        return False

    # Initialize S3 client with profile
    session = boto3.Session(profile_name=AWS_PROFILE_NAME)
    s3 = session.client('s3')

    # Check if S3 object already exists (if overwrite is False)
    if not overwrite:
        try:
            s3.head_object(Bucket=bucket, Key=key)
            logging.warning(f"S3 object already exists: s3://{bucket}/{key}")
            logging.warning("Use --overwrite to force upload and replace the existing object.")
            return False
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                # Object doesn't exist, proceed with upload
                pass
            else:
                logging.error(f"Error checking S3 object: {e}")
                return False

    try:
        logging.info(f"Uploading {local_path} to s3://{bucket}/{key}")

        # Start with auto-detected headers if enabled
        final_headers = {}
        if auto_headers:
            final_headers = get_default_headers_for_file(local_path)
            logging.debug(f"Auto-detected headers: {final_headers}")

        # Merge with user-provided headers (user headers take precedence)
        if headers:
            final_headers.update(headers)
            logging.debug(f"Final headers after merge: {final_headers}")

        # Prepare extra arguments for upload
        extra_args = {}
        if final_headers:
            # Convert headers to the format expected by S3
            metadata = {}
            for key_name, value in final_headers.items():
                if key_name.lower() == 'content-type':
                    extra_args['ContentType'] = value
                elif key_name.lower() == 'cache-control':
                    extra_args['CacheControl'] = value
                elif key_name.lower() == 'content-encoding':
                    extra_args['ContentEncoding'] = value
                elif key_name.lower() == 'content-disposition':
                    extra_args['ContentDisposition'] = value
                elif key_name.lower() == 'content-language':
                    extra_args['ContentLanguage'] = value
                else:
                    # For custom metadata, prefix with 'x-amz-meta-'
                    metadata[key_name] = value

            if metadata:
                extra_args['Metadata'] = metadata

        # Upload with extra arguments if provided
        if extra_args:
            s3.upload_file(Filename=local_path, Bucket=bucket, Key=key, ExtraArgs=extra_args)
        else:
            s3.upload_file(Filename=local_path, Bucket=bucket, Key=key)

        logging.info("Upload complete.")
        return True
    except ClientError as e:
        logging.error(f"Error uploading file: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return False

def check_if_file_exists_on_aws(key, bucket=None):
    """
    Check if a file exists in S3.
    
    Args:
        key (str): S3 object key (required)
        bucket (str): S3 bucket name
        
    Returns:
        bool: True if file exists, False otherwise
    """

    if bucket is None:
        bucket = AWS_BUCKET
    
    # Initialize S3 client with profile
    session = boto3.Session(profile_name=AWS_PROFILE_NAME)
    s3 = session.client('s3')
    
    try:
        logging.info(f"Checking if file exists: s3://{bucket}/{key}")
        s3.head_object(Bucket=bucket, Key=key)
        logging.info("File exists.")
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            logging.info("File does not exist at specified AWS location.")
            return False
        else:
            logging.error(f"Error checking file existence: {e}")
            return False
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return False

def download_and_parse_aws(path, parse_func):

    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_path = tmp_file.name
    
    try:
        # Download the file
        download_file_from_aws(tmp_path, key = path,
                               overwrite = True)
        
        # Process the file
        result = parse_func(tmp_path)
        
        return result
        
    finally:
        # Clean up the temporary file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    
    return None

def upload_tiles_to_aws(dir_path_local, key, overwrite, bucket = None):
    # !!! Don’t need key.

    if bucket is None:

        bucket = AWS_BUCKET

    #session = boto3.Session(profile_name="habitat-maintainer")
    session = boto3.Session(profile_name=AWS_PROFILE_NAME)
    s3 = session.client('s3')

    #try:
    #    response = s3.list_buckets()
    #    logging.info("Available buckets:")
    #    for bucket in response['Buckets']:
    #        logging.info(f"  - {bucket['Name']}")
    #except Exception as e:
    #    logging.info(f"Can't list buckets: {e}")

    local_manifest_path = os.path.join(dir_path_local, '.tile_manifest.json')
    if not os.path.isfile(local_manifest_path):
        logging.info("Local manifest file not found:", local_manifest_path)
        return

    #partial_sync_mode = ('land_use' in key)
    partial_sync_mode = False

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
                logging.info("Manifest matches remote copy. Skipping upload.")
                skip_upload = True
        except ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchKey':
                raise
            logging.info("Remote manifest not found. Proceeding with upload.")

    if skip_upload:
        if partial_sync_mode:
            logging.info('Partial sync mode enabled, continuing despite presence of manifest.')
        else:
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

    logging.info(f"Uploading {len(file_paths)} files to s3://{bucket}/{key}/")
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
        
        if not partial_sync_mode:

            s3.upload_file(Filename=full_path, Bucket=bucket, Key=s3_key,
                           ExtraArgs = extra_args,
                           )
        else:

            try:
                s3.head_object(Bucket=bucket, Key=s3_key)
                #logging.info("File already exists!")
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    # File doesn't exist, safe to upload
                    s3.upload_file(Filename=full_path, Bucket=bucket, Key=s3_key, ExtraArgs=extra_args)

    logging.info("Upload complete.")
    return

def clear_s3_directory(bucket, prefix):
    """
    Delete all objects in S3 bucket with the given prefix
    """
    session = boto3.Session(profile_name=AWS_PROFILE_NAME)
    s3 = session.client('s3')

    try:
        # List all objects with the prefix
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)

        if 'Contents' in response:
            # Prepare list of objects to delete
            objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]

            print(f"Deleting {len(objects_to_delete)} existing files from s3://{bucket}/{prefix}")

            # Delete objects in batches (S3 allows up to 1000 objects per delete request)
            for i in range(0, len(objects_to_delete), 1000):
                batch = objects_to_delete[i:i+1000]
                s3.delete_objects(
                    Bucket=bucket,
                    Delete={'Objects': batch}
                )

            print("Existing files deleted successfully")
        else:
            print(f"No existing files found in s3://{bucket}/{prefix}")

    except Exception as e:
        print(f"Error clearing S3 directory: {e}")
        raise

def write_json_and_upload_to_s3(dict_, path_, encoder = None):

    # Save the results as a JSON file.
    logging.info("Saving to {:}".format(path_))
    #
    try:
        with open(path_, "w") as f:
            json.dump(dict_, f, indent=2, cls = encoder)
    except:
        logging.info(dict_)
        raise

    # Copy to S3.
    upload_file_to_aws(path_, overwrite = True)

    return
