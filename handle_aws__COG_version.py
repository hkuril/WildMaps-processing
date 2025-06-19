import hashlib
import os

import boto3

def get_s3_etag(bucket, key, session):
    """Return ETag of an object in S3, or None if it doesn't exist."""
    #s3 = boto3.client('s3')
    s3 = session.client('s3')
    try:
        response = s3.head_object(Bucket=bucket, Key=key)
        return response['ETag'].strip('"')
    except s3.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            return None
        else:
            raise

def compute_local_etag(filepath):
    """
    !!! Not used
    Compute a local MD5 hash (single-part ETag equivalent)."""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def get_s3_metadata(bucket, key, session):
    s3 = session.client('s3')
    try:
        response = s3.head_object(Bucket=bucket, Key=key)
        return {
            "ETag": response['ETag'].strip('"'),
            "Size": response['ContentLength'],
            "LastModified": response['LastModified']
        }
    except s3.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            return None
        else:
            raise

def upload_to_aws(local_path, bucket, key):
    """Upload to S3 only if content has changed."""
    print(f"Checking for changes in S3: s3://{bucket}/{key}")

    session = boto3.Session(profile_name = "habitat-maintainer")

    metadata = get_s3_metadata(bucket, key, session)
    local_size = os.path.getsize(local_path)

    if metadata and metadata["Size"] == local_size:
        print("S3 already has same-size file. Skipping upload.")
        return

    #local_etag = compute_local_etag(local_path)
    #s3_etag = get_s3_etag(bucket, key, session)

    #if s3_etag == local_etag:
    #    print("S3 already has identical file. Skipping upload.")
    #    return

    print(f"Uploading to s3://{bucket}/{key}")
    #s3 = boto3.client('s3')
    s3 = session.client("s3")
    s3.upload_file(local_path, bucket, key,
                       ExtraArgs={
                            "ContentType": "image/tiff",
                            "CacheControl": "public, max-age=86400"
                            }
                   )
    print(f"Uploaded to s3://{bucket}/{key}")
