import logging
from pathlib import Path

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# TODO: rename file to utils_file.py


def delete_file(file_full_path):
    try:
        p = Path(file_full_path)
        p.unlink(missing_ok=True)
    except Exception as e:
        logger.error(f"file_utils.delete_file(): failed to delete {file_full_path}")
