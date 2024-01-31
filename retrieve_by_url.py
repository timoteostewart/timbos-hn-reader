import json
import logging
import os
import re
import sys
import time
import traceback
import warnings  # to quiet httpx deprecation warnings

import hrequests
import hrequests.exceptions
import httpx
import lxml.etree
import requests

import config
import utils_random
from my_exceptions import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# quiet httpx since it's chatty
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="httpx")


empty_page_source = "<html><head></head><body></body></html>"


def endpoint_query_via_requests(url=None, retries=3, delay=8, log_prefix=""):
    log_prefix_local = log_prefix + "endpoint_query_via_requests(): "
    if retries == 0:
        logger.info(log_prefix_local + f"failed to GET endpoint {url}")
        raise FailedAfterRetrying()

    try:
        resp = requests.get(url)
        resp.raise_for_status()
        resp_as_dict = resp.json()
        # logger.info(log_prefix + f"successfully queried endpoint {url}")
        return resp_as_dict

    except requests.exceptions.ConnectTimeout as exc:
        if url.startswith("http://ip-api.com/json/"):
            return None
        else:
            exc_name = exc.__class__.__name__
            exc_msg = str(exc)
            exc_slug = f"{exc_name}: {exc_msg}"
            logger.info(exc_slug + " (~Tim~)")

    except requests.exceptions.SSLError as exc:
        exc_name = exc.__class__.__name__
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        logger.info(exc_slug + " (~Tim~)")

    except Exception as exc:
        exc_name = exc.__class__.__name__
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"

        delay *= 2
        logger.info(
            log_prefix_local
            + f"problem querying url {url}: {exc_slug} ; will delay {delay} seconds and retry (retries left {retries})"
        )
        time.sleep(delay)

        return endpoint_query_via_requests(
            url=url, retries=retries - 1, delay=delay, log_prefix=log_prefix
        )


def get_page_source_via_response_object(response_object=None, log_prefix=""):

    log_prefix_local = log_prefix + "get_page_source_via_response_object(): "

    # get page source via GET
    page_source_via_get = response_object.text
    page_source_via_render = None

    # try to get page source via render()
    url = response_object.url
    try:
        with response_object.render(headless=True, mock_human=True) as page:
            time.sleep(utils_random.random_real(0, 1))
            page.goto(url)
            time.sleep(utils_random.random_real(0, 1))

            if page.html and page.html.find("html"):
                page_source_via_render = page.html.find("html").html
            else:
                page_source_via_render = ""

    except Exception as exc:
        logger.info(log_prefix_local + "got exception in render(): " + str(exc))
        handle_exception(exc=exc, log_prefix=log_prefix_local + "render(): ")

    if page_source_via_get:
        if page_source_via_get == empty_page_source:
            len_page_source_via_get = 0
        else:
            len_page_source_via_get = len(page_source_via_get)
    else:
        len_page_source_via_get = 0

    if page_source_via_render:
        if page_source_via_render == empty_page_source:
            len_page_source_via_render = 0
        else:
            len_page_source_via_render = len(page_source_via_render)
    else:
        len_page_source_via_render = 0

    if len_page_source_via_get + len_page_source_via_render == 0:
        logger.info(log_prefix_local + f"failed to get page source for {url}")
        return None
    else:
        if len_page_source_via_render >= len_page_source_via_get:
            page_source = page_source_via_render
            logger.info(log_prefix_local + f"got page_source (via render) for {url}")
        else:
            page_source = page_source_via_get
            logger.info(log_prefix_local + f"got page_source (via GET) for {url}")

        # logger.info(log_prefix_local + f"got page source for {url}")
        return page_source


def get_response_object_via_hrequests2(
    url=None,
    browser="chrome",
    log_prefix="",
):
    if not url:
        return None

    try:
        with hrequests.Session(
            browser=browser,
            os=os.getenv("CUR_OS", default="lin"),
            timeout=8,
        ) as session:
            response = session.get(
                url,
                timeout=8,
            )
            return response

    except Exception as exc:
        handle_exception(exc=exc, log_prefix=log_prefix + "gps_via_hr2(): get(): ")


def firebaseio_endpoint_query(query=None, log_prefix=""):
    url = "https://hacker-news.firebaseio.com" + query

    try:
        resp_as_dict = endpoint_query_via_requests(url=url, log_prefix=log_prefix)
        logger.info(log_prefix + f"successfully queried {url}")
        return resp_as_dict
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


def get_page_source(url=None, log_prefix=""):
    log_prefix_local = log_prefix + "get_page_source(): "

    if not url:
        logger.error(log_prefix_local + f"{url} required")
        return None

    res = None
    try:
        res = get_page_source_via_hrequests(url=url, log_prefix=log_prefix)
    except Exception as exc:
        exc_name = exc.__class__.__name__
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        logger.error(log_prefix_local + f"unexpected exception: " + exc_slug)

    if res:
        return res
    else:
        # logger.info(log_prefix_local + f"gps_via_hr() returned None for {url}")
        return None


def get_list_of_hrequests_exceptions(text: str = ""):
    pattern = r"(hrequests.exceptions.Browser\w+):"
    exc_names = []
    exc_msgs = []

    for match in re.finditer(pattern, text):
        exc_names.append(match.group(1))
        start_pos = match.end()
        end_pos = text.find("\n", start_pos)
        if end_pos == -1:
            end_pos = len(text)
        exc_msgs.append(text[start_pos:end_pos].strip())

    return (exc_names, exc_msgs)


def handle_exception(exc: Exception = None, log_prefix=""):
    exc_name = f"{exc.__class__.__module__}.{exc.__class__.__name__}"
    exc_msg = str(exc)
    exc_slug = f"{exc_name}: {exc_msg}"

    if isinstance(exc, hrequests.exceptions.BrowserTimeoutException):
        pattern = r"Timeout (\d+)ms exceeded."
        match = re.search(pattern, exc_msg)
        if match:
            pass
        else:
            tb_str = traceback.format_exc()
            logger.error(log_prefix + "unexpected exception: " + exc_slug)
            logger.error(log_prefix + tb_str)

    elif isinstance(exc, hrequests.exceptions.BrowserException):
        tb_str = traceback.format_exc()
        excs_tuple = get_list_of_hrequests_exceptions(tb_str)
        if len(excs_tuple[0]) > 1:
            if (
                excs_tuple[0][0] == "hrequests.exceptions.BrowserTimeoutException"
                and excs_tuple[0][1] == "hrequests.exceptions.BrowserException"
            ):
                pass
            else:
                zip_object = zip(excs_tuple[0], excs_tuple[1])
                excs_list = [f"{x[0]}: {x[1]}" for x in zip_object]
                excs_str = "; ".join(excs_list)
                logger.info(log_prefix + "stacked exceptions: " + excs_str)

        if exc_msg.startswith("Browser was closed. Attribute call failed: close"):
            pass
        elif exc_msg.startswith(
            "Unable to retrieve content because the page is navigating and changing the content."
        ):
            pass
        elif exc_msg.startswith("cookies"):
            pattern = r"cookies\[(\d+)\]\.value: expected string, got undefined"
            match = re.search(pattern, exc_msg)
            if match:
                pass
            else:
                logger.error(log_prefix + "unexpected exception: " + exc_slug)
                tb_str = traceback.format_exc()
                logger.error(log_prefix + tb_str)
        else:
            tb_str = traceback.format_exc()
            logger.error(log_prefix + "unexpected exception: " + exc_slug)
            logger.error(log_prefix + tb_str)

    elif isinstance(exc, hrequests.exceptions.ClientException):
        if "x509: certificate signed by unknown authority" in exc_msg:
            pass
        elif exc_msg.startswith("Connection error"):
            tb_str = traceback.format_exc()

            pattern = r"^hrequests.exceptions.ClientException:(.*)$"
            match = re.search(pattern, tb_str)
            if match:
                detailed_msg = match.group(1)
                logger.error(log_prefix + f"from traceback: {detailed_msg}")
        else:
            logger.error(log_prefix + "unexpected exception: " + exc_slug)
            logger.error(log_prefix + tb_str)

    elif isinstance(exc, lxml.etree.ParserError):
        if "Document is empty" in exc_msg:
            pass
        else:
            tb_str = traceback.format_exc()
            logger.error(log_prefix + "unexpected exception: " + exc_slug)
            logger.error(log_prefix + tb_str)

    elif isinstance(exc, Exception):
        tb_str = traceback.format_exc()
        logger.error(log_prefix + "unexpected exception: " + exc_slug)
        logger.error(log_prefix + tb_str)

    else:
        logger.error(
            log_prefix
            + "fell through all exceptions! (this shouldn't happen) "
            + exc_slug
            + " (~Tim~)"
        )


def get_page_source_via_hrequests(
    url=None,
    browser="chrome",
    log_prefix="",
):
    if not url:
        return None

    # logger.info(log_prefix + f"getting {url}")

    page_source_via_get = None
    page_source_via_render = None

    try:
        with hrequests.Session(
            browser=browser,
            os=os.getenv("CUR_OS", default="lin"),
            timeout=8,
        ) as session:
            resp = session.get(
                url,
                timeout=8,
            )
            # get page source via GET
            page_source_via_get = resp.text

            # try to get page source via render()
            try:
                with resp.render(headless=True, mock_human=True) as page:
                    time.sleep(utils_random.random_real(0, 1))
                    page.goto(url)
                    time.sleep(utils_random.random_real(0, 1))

                    page_source_via_render = (
                        page.html.find("html").html
                        if (page.html and page.html.find("html"))
                        else ""
                    )

            except Exception as exc:
                handle_exception(
                    exc=exc, log_prefix=log_prefix + "gps_via_hr(): render(): "
                )

    except Exception as exc:
        handle_exception(exc=exc, log_prefix=log_prefix + "gps_via_hr(): get(): ")

    if page_source_via_get:
        if page_source_via_get == empty_page_source:
            len_page_source_via_get = 0
        else:
            len_page_source_via_get = len(page_source_via_get)
    else:
        len_page_source_via_get = 0

    if page_source_via_render:
        if page_source_via_render == empty_page_source:
            len_page_source_via_render = 0
        else:
            len_page_source_via_render = len(page_source_via_render)
    else:
        len_page_source_via_render = 0

    if len_page_source_via_get + len_page_source_via_render == 0:
        logger.info(log_prefix + f"failed to get page source for {url}")
        return None
    else:
        if len_page_source_via_render >= len_page_source_via_get:
            page_source = page_source_via_render
            logger.info(log_prefix + f"got page_source (via render) for {url}")
        else:
            page_source = page_source_via_get
            logger.info(log_prefix + f"got page_source (via GET) for {url}")

        # logger.info(log_prefix + f"got page source for {url}")
        return page_source


# monkey patch a few hrequests dependencies to prevent them from crashing on me
fingerprints_bablosoft_com_responses = {
    browser_name: endpoint_query_via_requests(
        url=f"http://fingerprints.bablosoft.com/preview?rand=0.1&tags={browser_name},Desktop,Linux"
    )
    for browser_name in ["chrome", "chromium", "edge", "firefox", "safari"]
}


async def monkeypatched_computer(self, proxy, browser_name) -> None:
    data = fingerprints_bablosoft_com_responses[browser_name]
    # self.useragent = data.get("ua")
    self.vendor: str = data.get("vendor")
    self.renderer: str = data.get("renderer")
    self.width: int = data.get("width", 0)
    self.height: int = data.get("height", 0)
    self.avail_width: int = data.get("availWidth", 0)
    self.avail_height: int = data.get("availHeight", 0)
    # If the Window is too small for the captcha
    if (
        self.width
        and self.height > 810
        and self.avail_height > 810
        and self.avail_width > 810
    ):
        return


faker = hrequests.playwright_mock.Faker
faker.computer = monkeypatched_computer


my_wan_ip = None
try:
    my_wan_ip = endpoint_query_via_requests(
        url="https://api.ipify.org?format=json",
        retries=3,
        delay=2,
        log_prefix="get my_wan_ip",
    )
    my_wan_ip = my_wan_ip.get("ip")  # {"ip":"70.123.4.4"}
    if not my_wan_ip:
        error_msg = "failed to get my_wan_ip via ipify.org"
        logger.info(error_msg)
        raise Exception(error_msg)
    logger.info("got my_wan_ip via ipify.org")
except Exception as exc:
    url = "https://icanhazip.com/"
    resp = requests.get(url)
    if resp.status_code == 200:
        my_wan_ip = resp.text
        logger.info("got my_wan_ip via icanhazip.com")
    else:
        my_wan_ip = None
        logger.info("failed to get my_wan_ip via icanhazip.com")
if not my_wan_ip:
    my_wan_ip = "70.123.4.4"
    logger.info(f"got my_wan_ip from hardcoded value {my_wan_ip}")


async def monkeypatched_check_proxy(self) -> None:
    data = endpoint_query_via_requests(
        url=f"http://ip-api.com/json/{my_wan_ip}",
        retries=3,
        delay=2,
        log_prefix="monkeypatched_check_proxy(): ",
    )

    if not data or data["status"] == "fail":
        cached_data = f"""{{"status":"success","country":"United States","countryCode":"US","region":"TX","regionName":"Texas","city":"Austin","zip":"78723","lat":30.3023,"lon":-97.6914,"timezone":"America/Chicago","isp":"Charter Communications","org":"Spectrum","as":"AS11427 Charter Communications Inc","query":"{my_wan_ip}"}}"""
        data = json.loads(cached_data)

    self.country = data.get("country")
    self.country_code = data.get("countryCode")
    self.region = data.get("regionName")
    self.city = data.get("city")
    self.zip = data.get("zip")
    self.latitude = data.get("lat")
    self.longitude = data.get("lon")
    self.timezone = data.get("timezone")
    # logger.info(f"monkeypatched_check_proxy(): {data}")


proxy_manager = hrequests.playwright_mock.ProxyManager
proxy_manager.check_proxy = monkeypatched_check_proxy
