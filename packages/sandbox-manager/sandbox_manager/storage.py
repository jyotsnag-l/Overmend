import os
import logging
from typing import Optional, Tuple

logger = logging.getLogger("sandbox_manager.storage")

def get_s3_client():
    """
    Attempts to initialize a boto3 S3 client using environment variables.
    Returns None if not configured.
    """
    try:
        import boto3
    except ImportError:
        logger.warning("boto3 is not installed. S3/R2 storage will be bypassed.")
        return None

    bucket = os.getenv("S3_BUCKET_NAME") or os.getenv("R2_BUCKET_NAME")
    access_key = os.getenv("S3_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("S3_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY")
    endpoint_url = os.getenv("S3_ENDPOINT_URL")

    if not bucket:
        return None

    client_kwargs = {}
    if access_key and secret_key:
        client_kwargs["aws_access_key_id"] = access_key
        client_kwargs["aws_secret_access_key"] = secret_key
    if endpoint_url:
        client_kwargs["endpoint_url"] = endpoint_url
    
    region = os.getenv("S3_REGION_NAME") or os.getenv("AWS_DEFAULT_REGION")
    if region:
        client_kwargs["region_name"] = region

    try:
        return boto3.client("s3", **client_kwargs), bucket
    except Exception as e:
        logger.error(f"Failed to initialize S3 client: {e}", exc_info=True)
        return None


def upload_artifact(job_id: str, artifact_type: str, content: str) -> Optional[str]:
    """
    Uploads stdout or stderr content to S3/R2 if configured.
    Returns the key/URL if successful, otherwise None.
    """
    if not content:
        return None

    s3_info = get_s3_client()
    if not s3_info:
        logger.debug("S3 storage is not configured. Storing artifact metadata only.")
        return None

    s3_client, bucket = s3_info
    key = f"sandbox_runs/{job_id}/{artifact_type}.log"
    
    try:
        logger.info(f"Uploading {artifact_type} to S3/R2: s3://{bucket}/{key}")
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content.encode("utf-8"),
            ContentType="text/plain"
        )
        
        # If there is a custom endpoint (like R2/LocalStack), we might return a custom URL,
        # otherwise we return the standard S3 virtual host URL or just the bucket/key.
        endpoint = os.getenv("S3_ENDPOINT_URL")
        if endpoint:
            # Strip trailing slash
            endpoint = endpoint.rstrip("/")
            return f"{endpoint}/{bucket}/{key}"
        else:
            return f"https://{bucket}.s3.amazonaws.com/{key}"
    except Exception as e:
        logger.error(f"Failed to upload artifact {key} to S3: {e}", exc_info=True)
        return None
