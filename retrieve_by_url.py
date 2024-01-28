import json
import logging
import os
import re
import sys
import time
import traceback

import hrequests
import hrequests.exceptions
import httpx
import requests

import config
import utils_random
from my_exceptions import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# declutter logs since httpx is very chatty
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)

empty_page_source = "<html><head></head><body></body></html>"


def endpoint_query_via_requests(url=None, retries=3, delay=8, log_prefix=""):
    if retries == 0:
        logger.error(log_prefix + f"GET request {url} failed")
        raise FailedAfterRetrying()

    try:
        resp = requests.get(url)
        resp.raise_for_status()
        resp_as_json = resp.json()
        # logger.info(log_prefix + f"successfully queried endpoint {url}")
        return resp_as_json
    except Exception as exc:
        delay *= 2
        logger.warning(
            log_prefix
            + f"problem querying {url}: {exc} ; will delay {delay} seconds and retry (retries left {retries})"
        )
        time.sleep(delay)

        return endpoint_query_via_requests(
            url=url, retries=retries - 1, delay=delay, log_prefix=log_prefix
        )


def firebaseio_endpoint_query(query=None, log_prefix=""):
    url = "https://hacker-news.firebaseio.com" + query

    try:
        resp_as_json = endpoint_query_via_requests(url=url, log_prefix=log_prefix)
        logger.info(log_prefix + f"successfully queried {url}")
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


def get_page_source(url=None, log_prefix=""):
    gps_log_prefix = log_prefix + "get_page_source(): "

    if not url:
        logger.error(gps_log_prefix + f"{url} required")
        return None
    try:
        res = get_page_source_hrequests(url=url, log_prefix=log_prefix)
    except hrequests.exceptions.BrowserTimeoutException as exc:
        logger.error(
            gps_log_prefix + f"get_page_source_hrequests() timed out for {url}"
        )
        return None
    except Exception as exc:
        logger.error(
            gps_log_prefix + f"get_page_source_hrequests() failed for {url}: {exc}"
        )
        logger.error(gps_log_prefix + traceback.format_exc())
        raise

    if res:
        return res
    else:
        logger.error(
            gps_log_prefix + f"get_page_source_hrequests() returned None for {url}"
        )
        return None


def get_list_of_hrequests_exceptions(text: str = ""):
    pattern = r"hrequests.exceptions.Browser\w+"
    exceptions = []
    comments = []

    for match in re.finditer(pattern, text):
        exceptions.append(match.group())
        start_pos = match.end()
        end_pos = text.find("\n", start_pos)
        if end_pos == -1:
            end_pos = len(text)
        comments.append(text[start_pos:end_pos].strip())

    return exceptions, comments


def get_page_source_hrequests(
    url=None,
    browser="chrome",
    log_prefix="",
):
    if not url:
        return None

    log_prefix += "get_page_source_hrequests(): "

    logger.info(log_prefix + f"getting {url}")

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
            page_source1 = resp.text
            # TODO: try to save page source from the resp object;
            # that way, in case the resp.render doesn't work, we might come
            # away with at least something.
            # see https://daijro.gitbook.io/hrequests/simple-usage/attributes

            try:
                with resp.render(headless=True, mock_human=True) as page:
                    time.sleep(utils_random.random_real(0, 1))
                    page.goto(url)
                    time.sleep(utils_random.random_real(0, 1))

                    page_source2 = (
                        page.html.find("html").html
                        if (page.html and page.html.find("html"))
                        else ""
                    )
            except hrequests.exceptions.BrowserTimeoutException as exc:
                logger.error(
                    log_prefix
                    + f"in hrequests.Session().get().render(): {exc.__class__.__name__} {str(exc)} (expected hrequests.exceptions.BrowserTimeoutException)"
                )
                raise
            except hrequests.exceptions.BrowserException as exc:
                tb_str = traceback.format_exc()
                exceptions, comments = get_list_of_hrequests_exceptions(tb_str)
                if exceptions == [
                    "hrequests.exceptions.BrowserTimeoutException",
                    "hrequests.exceptions.BrowserException",
                ]:
                    logger.error(
                        log_prefix
                        + f"in hrequests.Session().get().render(): BrowserTimeoutException ({comments[0]}) followed by BrowserException ({comments[0]})"
                    )
                raise
            except Exception as exc:
                logger.error(
                    log_prefix
                    + f"in hrequests.Session().get().render(): {exc.__class__.__name__} {str(exc)} (expected unspecified Exception)"
                )
                raise

    except hrequests.exceptions.BrowserTimeoutException as exc:
        # TODO: save the traceback to a string and check which exceptions were raised upstream (e.g., timeout)
        logger.error(
            log_prefix
            + f"timeout exception during hrequests.Session(): {str(exc)} (expected hrequests.exceptions.BrowserTimeoutException)"
        )
        tb_str = traceback.format_exc()
        logger.error(log_prefix + tb_str)
        return None

    # TODO: also catch hrequests.exceptions.BrowserException: Browser was closed

    except hrequests.exceptions.BrowserException as exc:
        logger.error(
            log_prefix
            + f"{exc.__class__.__name__} during hrequests.Session(): {str(exc)} (expected hrequests.exceptions.BrowserException)"
        )
        tb_str = traceback.format_exc()

        if "Browser was closed. Attribute call failed: close" in tb_str:
            return None
        else:
            logger.error(log_prefix + tb_str)
        return None

    except hrequests.exceptions.ClientException as exc:
        logger.error(
            log_prefix
            + f"{exc.__class__.__name__} during hrequests.Session(): {str(exc)} (expected hrequests.exceptions.ClientException)"
        )
        tb_str = traceback.format_exc()
        logger.error(log_prefix + tb_str)
        return None

    except Exception as exc:
        logger.error(
            log_prefix
            + f"{exc.__class__.__name__} during hrequests.Session(): {str(exc)} (expected unspecified Exception)"
        )
        tb_str = traceback.format_exc()
        logger.error(log_prefix + tb_str)
        return None

    if page_source2 and page_source2 != empty_page_source:
        page_source = page_source2
    else:
        if page_source1:
            page_source = page_source1
        else:
            page_source = ""

    if not page_source:
        logger.info(log_prefix + f"failed to get page source for {url}")
        return None

    if page_source == empty_page_source:
        logger.info(log_prefix + f"web server returned empty document error for {url}")
        return None

    logger.info(log_prefix + f"got page source for {url}")
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

my_wan_ip = endpoint_query_via_requests(
    url="https://api.ipify.org?format=json", retries=10, delay=2, log_prefix=""
)

# ip_api_com_json_response = endpoint_query_via_requests(
#     url=f"http://ip-api.com/json/{my_wan_ip}", retries=10, delay=2, log_prefix=""
# )


async def monkeypatched_check_proxy(self) -> None:
    data = endpoint_query_via_requests(
        url=f"http://ip-api.com/json/{my_wan_ip}", retries=10, delay=2, log_prefix=""
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
