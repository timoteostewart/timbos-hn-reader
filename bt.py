import logging
import sys
import time

import config
import utils_http
import utils_random

logger = logging.getLogger(__name__)

if __name__ == "__main__":

    logger.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    # formatter = MicrosecondFormatter("%(asctime)s %(levelname)-8s %(message)s")
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    log_prefix = "bt.py: "

    url = sys.argv[1]

    # TODO: try get_page_source_via_hrequests()
