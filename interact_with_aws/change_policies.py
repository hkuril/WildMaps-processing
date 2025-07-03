import boto3
import json
import sys
from botocore.exceptions import ClientError, NoCredentialsError

from interact_with_aws.aws_tools import (AWS_PROFILE_NAME as PROFILE_NAME,
                                         AWS_BUCKET as BUCKET_NAME)

def update_bucket_policy(bucket_name, policy_file_path, profile_name):
    """Update S3 bucket policy"""
    with open(policy_file_path, 'r') as f:
        policy_json = f.read()
    
    # Validate JSON
    json.loads(policy_json)
    
    session = boto3.Session(profile_name=profile_name)
    s3 = session.client('s3')
    s3.put_bucket_policy(Bucket=bucket_name, Policy=policy_json)
    print(f"✅ Bucket policy updated for {bucket_name}")

def update_cors_policy(bucket_name, cors_file_path, profile_name):
    """Update S3 CORS configuration"""
    with open(cors_file_path, 'r') as f:
        cors_config = json.load(f)
    
    session = boto3.Session(profile_name=profile_name)
    s3 = session.client('s3')
    s3.put_bucket_cors(
        Bucket=bucket_name,
        CORSConfiguration=cors_config
    )
    print(f"✅ CORS configuration updated for {bucket_name}")

if __name__ == "__main__":
    # Check command line arguments
    if len(sys.argv) != 3:
        print("Usage: python script.py <bucket_policy|cors> <file-path>")
        print("Examples:")
        print("  python script.py bucket_policy policy.json")
        print("  python script.py cors cors.json")
        sys.exit(1)
    
    policy_type = sys.argv[1]
    file_path = sys.argv[2]
    
    try:
        if policy_type == "bucket_policy":
            print(f"Updating bucket policy from: {file_path}")
            update_bucket_policy(BUCKET_NAME, file_path, PROFILE_NAME)
        elif policy_type == "cors":
            print(f"Updating CORS configuration from: {file_path}")
            update_cors_policy(BUCKET_NAME, file_path, PROFILE_NAME)
        else:
            print(f"❌ Error: Invalid policy type '{policy_type}'")
            print("Valid options: bucket_policy, cors")
            sys.exit(1)
            
        print("Update completed successfully!")
        
    except FileNotFoundError:
        print(f"❌ Error: File not found: {file_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in file: {str(e)}")
        sys.exit(1)
    except NoCredentialsError:
        print(f"❌ Error: No credentials found for profile '{PROFILE_NAME}'")
        sys.exit(1)
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        print(f"❌ AWS Error ({error_code}): {error_message}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        sys.exit(1)


