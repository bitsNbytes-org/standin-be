from minio import Minio
from minio.error import S3Error
import logging
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MinIO client configuration
minio_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE,
)

BUCKET_NAME = settings.MINIO_BUCKET_NAME


def create_bucket_if_not_exists():
    """Create bucket if it doesn't exist"""
    try:
        if not minio_client.bucket_exists(BUCKET_NAME):
            minio_client.make_bucket(BUCKET_NAME)
            logger.info(f"Bucket '{BUCKET_NAME}' created successfully")
        else:
            logger.info(f"Bucket '{BUCKET_NAME}' already exists")
    except S3Error as e:
        logger.error(f"Error creating bucket: {e}")
        raise


def upload_file(file_path: str, object_name: str = None):
    """Upload a file to MinIO bucket"""
    if object_name is None:
        object_name = file_path.split("/")[-1]

    try:
        minio_client.fput_object(BUCKET_NAME, object_name, file_path)
        logger.info(f"File '{file_path}' uploaded as '{object_name}'")
        return True
    except S3Error as e:
        logger.error(f"Error uploading file: {e}")
        return False


def download_file(object_name: str, file_path: str):
    """Download a file from MinIO bucket"""
    try:
        minio_client.fget_object(BUCKET_NAME, object_name, file_path)
        logger.info(f"File '{object_name}' downloaded to '{file_path}'")
        return True
    except S3Error as e:
        logger.error(f"Error downloading file: {e}")
        return False


def delete_file(object_name: str):
    """Delete a file from MinIO bucket"""
    try:
        minio_client.remove_object(BUCKET_NAME, object_name)
        logger.info(f"File '{object_name}' deleted successfully")
        return True
    except S3Error as e:
        logger.error(f"Error deleting file: {e}")
        return False


def list_files():
    """List all files in the bucket"""
    try:
        objects = minio_client.list_objects(BUCKET_NAME)
        return [obj.object_name for obj in objects]
    except S3Error as e:
        logger.error(f"Error listing files: {e}")
        return []


# Initialize bucket on import
# try:
#     create_bucket_if_not_exists()
# except Exception as e:
#     logger.warning(f"Could not initialize MinIO bucket: {e}")
#     logger.warning("Make sure MinIO server is running")
