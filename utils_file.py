import logging
from pathlib import Path

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def delete_file(file_full_path, log_prefix=""):
    log_prefix_local = log_prefix + "delete_file(): "
    try:
        p = Path(file_full_path)
        p.unlink(missing_ok=True)
    except Exception as e:
        logger.error(log_prefix_local + f"failed to delete {file_full_path}")


def save_response_content_to_disk(response, dest_local_file, log_prefix=""):
    log_prefix_local = log_prefix + "save_response_content_to_disk(): "

    if isinstance(response.content, bytes):
        content_to_use = response.content
    elif isinstance(response.content, str):
        content_to_use = response.content.encode("utf-8")
    else:
        logger.error(
            log_prefix_local
            + f"unexpected type of response.content: {type(response.content)}"
        )
        return False

    try:
        with open(dest_local_file, "wb") as fout:
            fout.write(content_to_use)
        return True
    except Exception as exc:
        short_exc_name = exc.__class__.__name__
        exc_name = exc.__class__.__module__ + "." + short_exc_name
        exc_msg = str(exc)
        exc_slug = exc_name + ": " + exc_msg
        logger.error(log_prefix_local + exc_slug)
        return False
