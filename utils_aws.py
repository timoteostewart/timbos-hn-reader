import io
import json
import logging
import os
import sys
import time
from collections import ChainMap
from typing import Dict, List, Set

import boto3
import boto3.session
import botocore
from botocore.errorfactory import ClientError

import config
import my_secrets
from thnr_exceptions import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

boto3_session = boto3.Session(profile_name=my_secrets.AWS_PROFILE_NAME)
s3_config = botocore.config.Config(max_pool_connections=max(25, config.max_workers))
s3_resource = boto3_session.resource("s3", config=s3_config)
# my_bucket = s3_resource.Bucket(my_secrets.S3_BUCKET_NAME)

bucket_cdn = s3_resource.Bucket(my_secrets.S3_BUCKET_NAME_CDN)
bucket_html = s3_resource.Bucket(my_secrets.S3_BUCKET_NAME_HTML)


# def does_object_exist(full_s3_key):
#     try:
#         object = s3_resource.Object(my_secrets.S3_BUCKET_NAME, full_s3_key)
#         l = object.content_length
#         return l >= 0
#     except ClientError as e:
#         return False


# def does_story_exist(story_filename):
#     try:
#         object = s3_resource.Object(
#             my_secrets.S3_BUCKET_NAME_CDN, f"{config.s3_stories_path}{story_filename}"
#         )
#         l = object.content_length
#         return l >= 0
#     except ClientError as e:
#         return False


# def does_thumb_exist(thumb_filename):
#     try:
#         object = s3_resource.Object(
#             my_secrets.S3_BUCKET_NAME_CDN, f"{config.s3_thumbs_path}{thumb_filename}"
#         )
#         l = object.content_length
#         return l >= 0
#     except ClientError as e:
#         return False


def get_json_from_s3_as_dict(full_s3_key):
    try:
        obj = s3_resource.Object(
            bucket_name=my_secrets.S3_BUCKET_NAME_CDN, key=full_s3_key
        )
        obj_body = obj.get()["Body"].read().decode("utf-8")
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchKey":
            raise CouldNotGetObjectFromS3Error(f"Error: {exc}")
        else:
            raise

    json_as_dict = json.loads(obj_body)
    return json_as_dict


# def get_object_from_s3_as_bytes(full_s3_key):
#     try:
#         obj = s3_resource.Object(bucket_name=my_secrets.S3_BUCKET_NAME_CDN, key=full_s3_key)
#     except Exception as e:
#         logger.error(f"failed to retrieve s3 object {full_s3_key}")
#         raise CouldNotGetObjectFromS3Error(
#             f"failed to retrieve s3 object {full_s3_key}"
#         )
#     return obj.read()


def upload_dict_to_s3_as_json(d, full_s3_key, extra_args=None):
    j = json.dumps(d, indent=2)

    if not extra_args:
        extra_args = {
            "Tagging": "Activity=UploadDictionary",
        }

    upload_string_to_s3(string=str(j), full_s3_key=full_s3_key, extra_args=extra_args)

    return True


def upload_file_to_s3(
    full_s3_key=None,
    full_local_filename=None,
    extra_args=None,
    retries_left=3,
    bucket=None,
):
    if not extra_args:
        extra_args = {
            "Tagging": "Activity=UploadFile",
        }

    try:
        bucket.upload_file(
            Key=full_s3_key,
            Filename=full_local_filename,
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
                bucket=bucket,
            )
        else:
            raise exc

    return True


def upload_page_of_stories(page_filename=None, log_prefix=""):
    extra_args = {
        "ContentLanguage": "en",
        "ContentType": "text/html",
        "Tagging": "Activity=UploadPageOfStories",
    }

    # config.DEBUG_TIMES_IN_UPLOAD_PAGE_OF_STORIES_TO_S3 += 1
    # logger.info(f"{config.DEBUG_TIMES_IN_UPLOAD_PAGE_OF_STORIES_TO_S3=}")

    try:
        upload_file_to_s3(
            full_s3_key=f"{config.s3_stories_path}{page_filename}",
            full_local_filename=os.path.join(
                config.settings["COMPLETED_PAGES_DIR"], page_filename
            ),
            extra_args=extra_args,
            bucket=bucket_html,
        )
        logger.info(log_prefix + f"uploaded {page_filename} to S3")
    except Exception as exc:
        logger.error(log_prefix + f"failed to upload {page_filename} to S3")
        raise exc


def upload_roster_to_s3(roster_dict=None, roster_dest_fullpath=None):
    extra_args = {"ContentType": "application/json", "Tagging": "Activity=UploadRoster"}

    upload_dict_to_s3_as_json(
        d=roster_dict, full_s3_key=roster_dest_fullpath, extra_args=extra_args
    )


def upload_string_to_s3(string: str, full_s3_key, extra_args=None, bucket=bucket_cdn):
    buffer = io.BytesIO(string.encode())

    if not extra_args:
        extra_args = {
            "Tagging": "Activity=UploadString",
        }

    bucket.upload_fileobj(
        Fileobj=buffer,
        Key=full_s3_key,
        ExtraArgs=extra_args,
    )

    return True
    # if does_object_exist(full_s3_key):
    #     return True
    # else:
    #     return False


def upload_thumb(thumb_filename: str):
    extra_args = {"ContentType": "image/webp", "Tagging": "Activity=UploadThumb"}

    try:
        upload_file_to_s3(
            full_s3_key=f"{config.s3_thumbs_path}{thumb_filename}",
            full_local_filename=os.path.join(
                config.settings["TEMP_DIR"], thumb_filename
            ),
            extra_args=extra_args,
            bucket=bucket_cdn,
        )
    except Exception as exc:
        raise exc
