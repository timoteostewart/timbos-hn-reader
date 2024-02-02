import json
import logging
import mimetypes
import os
import subprocess
import traceback
from urllib.parse import unquote, urlparse

import exiftool
import magic

logger = logging.getLogger(__name__)


def get_mimetype_via_exiftool(local_file: str, log_prefix="") -> str:
    log_prefix_local = log_prefix + "get_mimetype_via_exiftool(): "
    mimetype = None
    try:
        with exiftool.ExifToolHelper() as et:
            metadata = et.get_metadata(local_file)[0]
            file_type = metadata.get("File:FileType")
            file_type_extension = metadata.get("File:FileTypeExtension")
            mimetype = metadata.get("File:MIMEType")
        return mimetype
    except Exception as exc:
        short_exc_name = exc.__class__.__name__
        exc_name = exc.__class__.__module__ + "." + short_exc_name
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        tb_str = traceback.format_exc()
        logger.error(log_prefix_local + "unexpected exception: " + exc_slug)
        logger.error(log_prefix_local + tb_str)
        return None


def get_mimetype_via_file_command(local_file, log_prefix="") -> str:
    log_prefix_local = log_prefix + "get_mimetype_via_file_command(): "

    cmd = f"/srv/timbos-hn-reader/getmt local {local_file}"

    try:
        res = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        short_exc_name = exc.__class__.__name__
        exc_name = exc.__class__.__module__ + "." + short_exc_name
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        tb_str = traceback.format_exc()
        logger.error(log_prefix_local + exc_slug)
        logger.error(log_prefix_local + tb_str)
        return None
    except Exception as exc:
        short_exc_name = exc.__class__.__name__
        exc_name = exc.__class__.__module__ + "." + short_exc_name
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        tb_str = traceback.format_exc()
        logger.error(log_prefix_local + "unexpected exception: " + exc_slug)
        logger.error(log_prefix_local + tb_str)
        return None

    # res is json, so decode it into a python dictionary
    res = json.loads(res)
    return res["mimetype"]


def get_mimetype_via_libmagic(local_file, log_prefix="") -> str:
    log_prefix_local = log_prefix + "get_mimetype_via_libmagic(): "
    try:
        magic_type_as_mimetype = magic.from_file(local_file, mime=True)
    except Exception as exc:
        short_exc_name = exc.__class__.__name__
        exc_name = exc.__class__.__module__ + "." + short_exc_name
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        tb_str = traceback.format_exc()
        logger.error(log_prefix_local + "unexpected exception: " + exc_slug)
        logger.error(log_prefix_local + tb_str)
        return None

    if magic_type_as_mimetype == "application/x-wine-extension-ini":
        pass

    return magic_type_as_mimetype


def guess_mimetype_from_uri_extension(url):
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Common_types
    # https://www.digipres.org/formats/mime-types/#application/illustrator%0A
    # https://www.digipres.org/formats/sources/fdd/formats/#fdd000018

    # get tld for url
    parsed_url = urlparse(url)
    tld = parsed_url.netloc.split(".")[-1]

    # guess using urlparse
    guess_by_urlparse = None
    path = unquote(parsed_url.path)
    paths_extension = os.path.splitext(path)[1]
    logger.info(f"{parsed_url.netloc=} {tld=} {paths_extension=} {path=} {url=}")
    if f".{tld}" == paths_extension:
        logger.info(f".tld .{tld} == paths_extension {paths_extension} for url {url}")
    if paths_extension:
        guess_by_urlparse, _ = mimetypes.guess_type(
            f"file.{paths_extension}", strict=False
        )
        if guess_by_urlparse:
            guess_by_urlparse = guess_by_urlparse.lower()

    # guess using mimetypes (anecdotally more slopppy than urlparse)
    guess_by_mimetypes = None
    guess_by_mimetypes, _ = mimetypes.guess_type(url, strict=False)

    if guess_by_mimetypes == "application/x-msdos-program" and tld == "com":
        guess_by_mimetypes = None
    elif guess_by_mimetypes == "application/x-info" and tld == "info":
        guess_by_mimetypes = None
    elif guess_by_mimetypes == "application/vnd.adobe.illustrator" and tld == "ai":
        guess_by_mimetypes = None
    elif (
        tld == "ai"
        and guess_by_mimetypes == "application/postscript"
        and paths_extension != "ai"
    ):
        guess_by_mimetypes = None
    elif tld == "zip" and guess_by_mimetypes in [
        "application/x-zip-compressed",
        "application/zip",
        "application/x-zip",
    ]:
        logger.info(f"guess_by_mimetypes(): {guess_by_mimetypes=} {tld=}")

    res = []
    res.append(guess_by_urlparse)
    res.append(guess_by_mimetypes)
    return res
