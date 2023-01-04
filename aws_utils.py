import io
import json
import logging
import os
import sys
import time

import boto3
import boto3.session
import botocore
from botocore.errorfactory import ClientError

import config
import my_secrets
from my_exceptions import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

boto3_session = boto3.Session(profile_name=my_secrets.AWS_PROFILE_NAME)
s3_resource = boto3_session.resource("s3")
my_bucket = s3_resource.Bucket(my_secrets.S3_BUCKET_NAME)


def does_object_exist(full_s3_key):
    try:
        object = s3_resource.Object(my_secrets.S3_BUCKET_NAME, full_s3_key)
        l = object.content_length
        return l >= 0
    except ClientError as e:
        return False


def does_story_exist(story_filename):
    try:
        object = s3_resource.Object(
            my_secrets.S3_BUCKET_NAME, f"{config.s3_stories_path}{story_filename}"
        )
        l = object.content_length
        return l >= 0
    except ClientError as e:
        return False


def does_thumb_exist(thumb_filename):
    try:
        object = s3_resource.Object(
            my_secrets.S3_BUCKET_NAME, f"{config.s3_thumbs_path}{thumb_filename}"
        )
        l = object.content_length
        return l >= 0
    except ClientError as e:
        return False


def get_json_from_s3_as_dict(full_s3_key):
    try:
        obj = s3_resource.Object(bucket_name=my_secrets.S3_BUCKET_NAME, key=full_s3_key)
        obj_body = obj.get()["Body"].read().decode("utf-8")
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchKey":
            raise CouldNotGetObjectFromS3Error(f"Error: {exc}")
        else:
            raise

    json_as_dict = json.loads(obj_body)
    return json_as_dict


def get_object_from_s3_as_bytes(full_s3_key):
    try:
        obj = s3_resource.Object(bucket_name=my_secrets.S3_BUCKET_NAME, key=full_s3_key)
    except Exception as e:
        logger.error(f"failed to retrieve s3 object {full_s3_key}")
        raise CouldNotGetObjectFromS3Error(
            f"failed to retrieve s3 object {full_s3_key}"
        )

    return obj.read()


def upload_dict_to_s3_as_json(d, full_s3_key):
    j = json.dumps(d, indent=2)
    upload_string_to_s3(str(j), full_s3_key, "application/json")

    if does_object_exist(full_s3_key):
        return True
    else:
        return False


def upload_file_to_s3(
    full_s3_key=None, full_local_filename=None, extra_args={}, retries_left=3
):
    try:
        my_bucket.upload_file(
            Filename=full_local_filename,
            Key=full_s3_key,
            ExtraArgs=extra_args,
        )
    except botocore.exceptions.EndpointConnectionError as exc:
        if retries_left > 0:
            time.sleep(1)
            logger.warning(
                f"{sys._getframe(  ).f_code.co_name}: EndpointConnectionError uploading {full_s3_key}; will retry"
            )
            upload_file_to_s3(
                full_s3_key=full_s3_key,
                full_local_filename=full_local_filename,
                extra_args=extra_args,
                retries_left=retries_left - 1,
            )
        else:
            raise exc

    if does_object_exist(full_s3_key):
        return True
    else:
        return False


def upload_page_of_stories(page_filename):
    extra_args = {"ContentLanguage": "en", "ContentType": "text/html"}

    try:
        upload_file_to_s3(
            full_s3_key=f"{config.s3_stories_path}{page_filename}",
            full_local_filename=os.path.join(
                config.settings["COMPLETED_PAGES_DIR"], page_filename
            ),
            extra_args=extra_args,
        )
    except Exception as exc:
        return False
    else:
        return True


def upload_string_to_s3(string, full_s3_key, content_type):
    buffer = io.BytesIO(string.encode())

    extra_args = {"ContentType": content_type}

    my_bucket.upload_fileobj(
        Fileobj=buffer,
        Key=full_s3_key,
        ExtraArgs=extra_args,
    )

    if does_object_exist(full_s3_key):
        return True
    else:
        return False


def upload_thumb(thumb_filename):
    extra_args = {"ContentType": "image/webp"}

    try:
        upload_file_to_s3(
            full_s3_key=f"{config.s3_thumbs_path}{thumb_filename}",
            full_local_filename=os.path.join(
                config.settings["TEMP_DIR"], thumb_filename
            ),
            extra_args=extra_args,
        )
    except Exception as exc:
        raise exc
