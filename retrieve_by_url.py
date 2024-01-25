import logging
import os
import sys
import time

import hrequests
import requests

import config
import utils_random
from my_exceptions import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_page_source_hrequests(
    url=None,
    browser="chrome",
    inter_scrape_delay=1.1,
    log_prefix="",
    **kwargs,
):
    if not url:
        return None

    try:
        with hrequests.Session(
            browser=browser, os=os.getenv("CUR_OS", default="lin")
        ) as session:
            resp = session.get(url)
            with resp.render(headless=True, mock_human=True) as page:
                time.sleep(utils_random.random_real(0, 1))
                page.goto(url)
                time.sleep(utils_random.random_real(0, 1))
                page_source = page.html.find("html").html

        if not page_source:
            logger.error(log_prefix + "failed to get page source")
            raise RuntimeError("Failed to get page source.")
        elif page_source == "<html><head></head><body></body></html>":
            raise ServerReturnedEmptyDocumentError(
                "server returned empty document error"
            )
        else:
            logger.info(log_prefix + f"got page source for {url}")
            return page_source
    except:
        return None


def firebaseio_endpoint_query(query=None, log_prefix=""):
    url = "https://hacker-news.firebaseio.com" + query

    try:
        resp_as_json = endpoint_query_via_requests(url=url, log_prefix=log_prefix)
        return resp_as_json
    except requests.exceptions.ConnectionError as exc:
        logger.error(
            log_prefix + f"firebaseio.com actively refused query {query}: {exc}"
        )
        raise
    except requests.exceptions.RequestException as exc:
        logger.warning(
            log_prefix + f"GET request failed for firebaseio.com query {query}: {exc}"
        )
        time.sleep(
            int(config.settings["SCRAPING"]["FIREBASEIO_RETRY_DELAY"])
        )  # in case it's a transient error, such as a DNS issue, wait for some seconds
        raise
    except Exception as exc:
        logger.error(
            log_prefix + f"firebaseio.com somehow failed for query {query}: {exc}"
        )
        raise


def endpoint_query_via_requests(url=None, retries=3, delay=60, log_prefix=""):
    if retries == 0:
        logger.error(log_prefix + f"GET request {url} failed")
        raise FailedAfterRetrying()

    try:
        resp = requests.get(url)
        resp.raise_for_status()
        resp_as_json = resp.json()
        logger.info(log_prefix + f"successfully queried endpoint {url}")
        return resp_as_json
    except Exception as exc:
        logger.warning(
            log_prefix
            + f"{sys._getframe(  ).f_code.co_name}: problem querying {url}: {exc} ; will delay {delay} seconds and try again ; retries left {retries}"
        )
        time.sleep(delay)

        return endpoint_query_via_requests(
            url=url, retries=retries - 1, delay=delay * 2
        )


def get_page_source_noproxy(
    driver=None, url=None, tries_left=config.num_tries_for_page_retrieval, log_prefix=""
):
    return get_page_source_hrequests(url=url, log_prefix=log_prefix)

    try:
        return get_page_source_noproxy_helper(driver=driver, url=url)
    except ServerReturnedEmptyDocumentError as exc:
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
        page_source = driver.page_source
    except Exception as exc:
        logger.error(f"{sys._getframe(  ).f_code.co_name}: url {url}: {exc}")
        raise exc

    if page_source == "<html><head></head><body></body></html>":
        raise ServerReturnedEmptyDocumentError("server returned empty document error")

    return page_source
