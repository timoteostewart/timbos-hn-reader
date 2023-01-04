import logging
import sys
import time

import requests

import config
from my_exceptions import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def endpoint_query_via_requests(url=None):
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        resp_as_json = resp.json()
    except Exception as exc:
        raise exc

    return resp_as_json


def get_page_source_noproxy(
    driver=None, url=None, tries_left=config.num_tries_for_page_retrieval
):
    try:
        return get_page_source_noproxy_helper(driver=driver, url=url)
    except (ServerReturnedEmptyDocumentError) as exc:
        logger.error(f"{sys._getframe(  ).f_code.co_name}: url {url}: {exc}")
        tries_left -= 1
        if tries_left == 0:
            err = f"failed to retrieve {url} after {tries_left} tries"
            logger.error(err)
            raise FailedAfterRetrying(err)
        else:
            return get_page_source_noproxy(
                driver=driver,
                url=url,
                tries_left=tries_left,
            )
    except Exception as exc:
        logger.error(f"{sys._getframe(  ).f_code.co_name}: url {url}: {exc}")
        raise exc


def get_page_source_noproxy_helper(driver=None, url=None):
    try:
        driver.get(url)
        time.sleep(
            config.delay_for_page_to_load_seconds
        )  # extra time for CDN (if any) to resolve and page to load

        page_source = driver.page_source
    except Exception as exc:
        logger.error(f"{sys._getframe(  ).f_code.co_name}: url {url}: {exc}")
        raise exc

    if page_source == "<html><head></head><body></body></html>":
        raise ServerReturnedEmptyDocumentError("server returned empty document error")

    return page_source
