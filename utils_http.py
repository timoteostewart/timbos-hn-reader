import builtins
import importlib
import json
import logging
import os
import re
import ssl
import time
import traceback
import warnings  # to quiet httpx deprecation warnings

import hrequests
import hrequests.exceptions
import httpx
import lxml.etree
import requests
import urllib3

import config
import secrets_file
import utils_random
from thnr_exceptions import *
from Trie import Trie

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# quiet httpx since it's chatty
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="httpx")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

empty_page_source = "<html><head></head><body></body></html>"
# user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"


def endpoint_query_via_requests(url=None, retries=3, delay=8, log_prefix=""):
    log_prefix_local = log_prefix + "endpoint_query_via_requests: "
    if retries == 0:
        logger.info(log_prefix_local + f"failed to GET endpoint {url}")
        raise FailedAfterRetrying()

    try:
        response = requests.get(
            url,
            headers={"User-Agent": config.settings["SCRAPING"]["UA_STR"]},
            timeout=config.settings["SCRAPING"]["REQUESTS_GET_TIMEOUT_S"],
            verify=False,
        )
        response.raise_for_status()
        resp_as_dict = response.json()
        # logger.info(log_prefix + f"successfully queried endpoint {url}")
        return resp_as_dict

    except Exception as exc:
        pass
        handle_exception(exc=exc, log_prefix=log_prefix_local, context={"url": url})

        delay *= 2
        logger.info(
            log_prefix_local
            + f"problem querying url {url} ; will delay {delay} seconds and retry (retries left {retries})"
        )
        time.sleep(delay)

        return endpoint_query_via_requests(
            url=url, retries=retries - 1, delay=delay, log_prefix=log_prefix
        )


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


def get_content_type_via_head_request(url: str = None, log_prefix=""):
    log_prefix_local = log_prefix + "get_content_type_via_head_request: "
    if not url:
        raise Exception("no URL provided")

    headers = None
    try:
        headers = head_request(url, log_prefix=log_prefix)
    except Exception as exc:
        exc_name = f"{exc.__class__.__module__}.{exc.__class__.__name__}"
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        logger.info(log_prefix_local + f"{exc_slug}")

    if not headers:
        # suppress logging if we're coming from download_og_image() since we log there
        if log_prefix.endswith("d_og_i: "):
            pass
        else:
            logger.info(log_prefix_local + f"failed to get HTTP headers for {url}")
        return None

    # extract content-type from headers
    content_type = None
    if "content-type" in headers:
        for each_ct_val in headers["content-type"].split(";"):
            if "charset" in each_ct_val:
                continue
            if "/" in each_ct_val:
                content_type = each_ct_val
                break

        if content_type == "*/*":
            logger.info(log_prefix_local + f"{content_type=} for {url} ~Tim~")
            content_type = None

        if content_type and "," in content_type:
            comma_delimited_content_types = [x.strip() for x in content_type.split(",")]
            if len(set(comma_delimited_content_types)) == 1:
                content_type = comma_delimited_content_types[0]
            else:
                logger.info(
                    log_prefix_local
                    + f"multiple content-types {comma_delimited_content_types} found in HTTP headers for url {url} ~Tim~"
                )
                content_type = None

    else:
        logger.info(
            log_prefix_local + f"content-type is absent from HTTP headers for url {url}"
        )
        content_type = None

    if content_type:
        return content_type
    else:
        logger.info(
            log_prefix_local
            + f"content-type could not be determined from HTTP headers for url {url}"
        )
        return None


def get_list_of_hrequests_exceptions(traceback: str = ""):

    excs = [
        (
            match.group(1).strip(),
            match.group(2).strip(),
        )
        for match in re.finditer(r"(hrequests\.exceptions\.[A-Za-z]+): (.*)", traceback)
    ]

    # for match in re.finditer(r"(hrequests\.exceptions\.[A-Za-z]+): (.*)", traceback):
    #     excs.append(
    #         (
    #             match.group(1).strip(),
    #             match.group(2).strip(),
    #         )
    #     )
    return excs


def get_page_source(url=None, log_prefix=""):
    log_prefix_local = log_prefix + "get_page_source: "

    if not url:
        logger.error(log_prefix_local + f"{url} required")
        return None

    content_encoding_hint = None

    while True:

        response = None
        try:
            response = get_page_source_via_hrequests(
                url=url,
                log_prefix=log_prefix,
                content_encoding_hint=content_encoding_hint,
            )

        except builtins.LookupError as exc:
            exc_module = exc.__class__.__module__
            exc_short_name = exc.__class__.__name__
            exc_name = exc_module + "." + exc_short_name
            exc_msg = str(exc)
            exc_slug = exc_name + ": " + exc_msg
            tb_str = traceback.format_exc()

            logger.info(log_prefix_local + exc_slug)

            if "unknown encoding" in exc_msg:
                content_encoding_hint = "utf_8"
                logger.info(
                    log_prefix_local
                    + f"retrying with content_encoding_hint set to {content_encoding_hint}"
                )
                continue

        except Exception as exc:
            exc_module = exc.__class__.__module__
            exc_short_name = exc.__class__.__name__
            exc_name = exc_module + "." + exc_short_name
            exc_msg = str(exc)
            exc_slug = exc_name + ": " + exc_msg
            tb_str = traceback.format_exc()

            logger.info(log_prefix + f"{exc_module=} ~Tim~")
            logger.info(log_prefix + f"{exc_short_name=} ~Tim~")

            logger.error(log_prefix_local + f"unexpected exception: " + exc_slug)

        if response:
            return response
        else:
            # logger.info(log_prefix_local + f"gps_via_hr() returned None for {url}")
            return None


def get_page_source_via_hrequests(
    url=None, browser="chrome", log_prefix="", content_encoding_hint=None
):
    if not url:
        return None

    page_source_via_get = None
    page_source_via_render = None

    response = get_response_object_via_hrequests(url, browser, log_prefix)

    # get page source via GET
    if response:
        try:
            if content_encoding_hint:
                logger.info(
                    log_prefix
                    + f"using content_encoding_hint: {content_encoding_hint} ~Tim~"
                )
                response.encoding = content_encoding_hint
            page_source_via_get = response.text
        except Exception as exc:
            handle_exception(
                exc=exc,
                log_prefix=log_prefix + "gps_via_hr(): get: ",
                context={"url": url},
            )

        # try to get page source via render()
        try:
            with response.render(headless=True, mock_human=True) as page:
                time.sleep(utils_random.random_real(0, 1))
                page.goto(url)
                time.sleep(utils_random.random_real(6, 10))

                page_source_via_render = (
                    page.html.find("html").html
                    if (page.html and page.html.find("html"))
                    else ""
                )

        except Exception as exc:
            handle_exception(
                exc=exc,
                log_prefix=log_prefix + "gps_via_hr(): render: ",
                context={"url": url},
            )

    if page_source_via_get:
        if page_source_via_get == empty_page_source:
            logger.info(
                log_prefix + f"matched empty_page_source on response for {url} ~Tim~"
            )
            len_page_source_via_get = 0
        else:
            len_page_source_via_get = len(page_source_via_get)
    else:
        len_page_source_via_get = 0

    if page_source_via_render:
        if page_source_via_render == empty_page_source:
            logger.info(
                log_prefix + f"matched empty_page_source on response for {url} ~Tim~"
            )
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


# def gps_via_hro(response_object=None, log_prefix=""):

#     log_prefix_local = log_prefix + "gps_via_hro: "

#     # get page source via GET
#     page_source_via_get = response_object.text
#     page_source_via_render = None

#     # try to get page source via render()
#     url = response_object.url
#     try:
#         with response_object.render(headless=True, mock_human=True) as page:
#             time.sleep(utils_random.random_real(0, 1))
#             page.goto(url)
#             time.sleep(utils_random.random_real(0, 1))

#             if page.html and page.html.find("html"):
#                 page_source_via_render = page.html.find("html").html
#             else:
#                 page_source_via_render = ""

#     except Exception as exc:
#         logger.info(log_prefix_local + "got exception in render: " + str(exc))
#         handle_exception(
#             exc=exc, log_prefix=log_prefix_local + "render: ", context={"url": url}
#         )

#     if page_source_via_get:
#         if page_source_via_get == empty_page_source:
#             len_page_source_via_get = 0
#         else:
#             len_page_source_via_get = len(page_source_via_get)
#     else:
#         len_page_source_via_get = 0

#     if page_source_via_render:
#         if page_source_via_render == empty_page_source:
#             len_page_source_via_render = 0
#         else:
#             len_page_source_via_render = len(page_source_via_render)
#     else:
#         len_page_source_via_render = 0

#     if len_page_source_via_get + len_page_source_via_render == 0:
#         logger.info(log_prefix_local + f"failed to get page source for {url}")
#         return None
#     else:
#         if len_page_source_via_render >= len_page_source_via_get:
#             page_source = page_source_via_render
#             logger.info(log_prefix_local + f"got page_source (via render) for {url}")
#         else:
#             page_source = page_source_via_get
#             logger.info(log_prefix_local + f"got page_source (via GET) for {url}")

#         # logger.info(log_prefix_local + f"got page source for {url}")
#         return page_source


def get_rendered_page_source_via_response_object(response_object, log_prefix=""):
    log_prefix_local = log_prefix + "get_rendered_page_source_via_response_object: "
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
        logger.info(log_prefix_local + "got exception in render: " + str(exc))
        handle_exception(
            exc=exc, log_prefix=log_prefix_local + "render: ", context={"url": url}
        )


def get_response_object_via_hrequests(
    url=None,
    browser="chrome",
    log_prefix="",
):
    if not url:
        return None

    log_prefix_local = log_prefix + "gro_via_hr: "

    with hrequests.Session(
        browser=browser,
        os=os.getenv("CUR_OS", default="lin"),
        temp=True,
        verify=False,
    ) as session:
        user_agent = (
            config.settings["SCRAPING"]["UA_STR"]
            if "SCRAPING" in config.settings
            else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        session.headers.update({"User-Agent": user_agent})

        try:
            timeout = (
                config.settings["SCRAPING"]["REQUESTS_GET_TIMEOUT_S"]
                if "SCRAPING" in config.settings
                else 30
            )
            response = session.get(
                allow_redirects=True,
                headers={"Accept": "text/html,*/*"},
                timeout=timeout,
                url=url,
            )
            if response and response.status_code == 200:
                return response
            else:
                logger.info(
                    log_prefix_local
                    + f"Failed to get response object. {response.status_code=}. {url=}"
                )
                return None

        except Exception as exc:
            handle_exception(
                exc=exc,
                log_prefix=log_prefix_local,
                context={"url": url},
            )

    return None


def get_response_object_via_requests(
    url=None,
    log_prefix="",
):
    if not url:
        return None

    log_prefix_local = log_prefix + "gro_via_r:  "

    with requests.Session() as session:
        user_agent = (
            config.settings["SCRAPING"]["UA_STR"]
            if "SCRAPING" in config.settings
            else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        session.headers.update({"User-Agent": user_agent})
        try:
            timeout = (
                config.settings["SCRAPING"]["REQUESTS_GET_TIMEOUT_S"]
                if "SCRAPING" in config.settings
                else 30
            )
            with session.get(
                allow_redirects=True,
                headers={"Accept": "text/html,*/*"},
                stream=False,
                timeout=timeout,
                url=url,
                verify=False,
            ) as response:
                if response and response.status_code == 200:
                    return response
                else:
                    logger.info(
                        log_prefix_local
                        + f"Failed to get response object. {response.status_code=}. {url=}"
                    )
                    return None

        except Exception as exc:
            handle_exception(
                exc=exc,
                log_prefix=log_prefix_local,
                context={"url": url},
            )

    return None


browser_exception_msg_prefixes = [
    "Browser was closed. Attribute call failed: close",
    "Cookie should have a valid expires, only -1 or a positive number for the unix timestamp in seconds is allowed",
    "Navigation failed because page crashed!",
    "Navigation failed because page was closed!",
    "Protocol error (Storage.setCookies): Invalid cookie fields",
    "Target crashed",
    "Target page, context or browser has been closed",
    "Timeout 30000ms exceeded.",
    "net::ERR_ABORTED",
    "net::ERR_CERT_COMMON_NAME_INVALID",
    "net::ERR_HTTP_RESPONSE_CODE_FAILURE",
    "net::ERR_NAME_NOT_RESOLVED",
    "net::ERR_NETWORK_CHANGED",
    "net::ERR_SOCKET_NOT_CONNECTED",
]

browser_exception_msg_prefixes_trie = Trie(prefix_search=True)
for _ in browser_exception_msg_prefixes:
    browser_exception_msg_prefixes_trie.add_member(_)


hrequests_exceptions_suffixes = [
    " EOF",
    "EOF (Client.Timeout exceeded while awaiting headers)",
    "context deadline exceeded (Client.Timeout exceeded while awaiting headers)",
    "http2: unsupported scheme",
    "i/o timeout (Client.Timeout exceeded while awaiting headers)",
    "i/o timeout",
    "no such host",
    "remote error: tls: unexpected message",
    "remote error: tls: user canceled",
    "stream error: stream ID 1; INTERNAL_ERROR",
    "unexpected EOF",
    "x509: certificate signed by unknown authority",
]

hrequests_exceptions_suffixes_trie = Trie(suffix_search=True)
for _ in hrequests_exceptions_suffixes:
    hrequests_exceptions_suffixes_trie.add_member(_)


def handle_exception(exc: Exception = None, log_prefix="", context=None):
    # handle exceptions for:
    # - get_page_source_via_hrequests
    # - get_page_source_via_response_object
    # - get_rendered_page_source_via_response_object
    # - get_response_object_via_hrequests2
    # - head_request

    # TODO: in future, for many of these exceptions, we could check archive.is, WBM, google cache, etc. for the url

    log_prefix_local = log_prefix + "handle_exception: "

    exc_module = exc.__class__.__module__
    exc_name = exc.__class__.__name__
    fq_exc_name = exc_module + "." + exc_name
    exc_msg = str(exc)
    exc_slug = fq_exc_name + ": " + exc_msg

    url = context["url"] if (context and "url" in context) else ""
    if url:
        url_slug = f" for url {url}"
    else:
        url_slug = ""

    tb_str = traceback.format_exc()

    if fq_exc_name == "requests.exceptions.SSLError":
        logger.info(
            log_prefix_local
            + f"fq_exc_name==requests.exceptions.SSLError succeeded, {exc_module=}, {exc_msg=} ~Tim~"
        )

    if exc_name == "SSLError":
        logger.info(log_prefix_local + f"exc_name==SSLError succeeded, {exc_module=}, {exc_msg=} ~Tim~")

    # for hrequests.exceptions only, check for stacked exceptions
    expected_stacked_exceptions = None
    if exc_module == "hrequests.exceptions":
        excs = get_list_of_hrequests_exceptions(tb_str)

        # log the stacked exception, then promote the initial exception (`excs[0][0]`) to be handled by code that follows
        len_excs = len(excs)
        if len_excs > 1:
            expected_stacked_exceptions = False

            if excs[len_excs - 1][1] == "Browser was closed.":
                expected_stacked_exceptions = True

            elif (
                excs[len_excs - 1][1]
                == "Browser was closed. Attribute call failed: close"
            ):
                expected_stacked_exceptions = True

            elif excs[len_excs - 1][1] == "Connection error":
                expected_stacked_exceptions = True

            if expected_stacked_exceptions:
                logger.info(
                    log_prefix_local
                    + "stacked exceptions: "
                    + str(excs)
                    + " "
                    + url_slug
                )
            else:
                logger.info(
                    log_prefix_local
                    + "unexpected stacked exceptions: "
                    + str(excs)
                    + " "
                    + url_slug
                )
                logger.info(log_prefix_local + tb_str)

                for i in range(len(excs)):
                    for j in range(len(excs[0])):
                        logger.info(log_prefix_local + f"excs[{i}][{j}]: {excs[i][j]}")

            # assign intial exception to variable `exc`
            module_path, _, exc_class_name = excs[0][0].rpartition(".")
            module = importlib.import_module(module_path)
            exc_class = getattr(module, exc_class_name)
            exc = exc_class(excs[0][1])

            exc_module = exc.__class__.__module__
            exc_name = exc.__class__.__name__
            fq_exc_name = exc_module + "." + exc_name
            exc_msg = str(exc)
            exc_slug = fq_exc_name + ": " + exc_msg

    expected_exception = False

    if exc_module == "hrequests.exceptions":
        if isinstance(exc, hrequests.exceptions.BrowserException):
            if exc_msg == "Browser closed.":
                expected_exception = True

            elif (
                exc_msg
                == "Unable to retrieve content because the page is navigating and changing the content."
            ):
                expected_exception = True

            elif browser_exception_msg_prefixes_trie.search(exc_msg) is not None:
                expected_exception = True

            elif exc_msg.startswith("net::ERR_CERT_DATE_INVALID"):
                expected_exception = True

            elif "cookies" in exc_msg:
                pattern = r"cookies\[\d+\]\.value: expected string, got undefined"
                match = re.search(pattern, exc_msg)
                if match:
                    expected_exception = True

        elif isinstance(exc, hrequests.exceptions.BrowserTimeoutException):
            match = re.search(r"Timeout \d+ms exceeded\.", exc_msg)
            if match:
                expected_exception = True

        elif isinstance(exc, hrequests.exceptions.ClientException):
            if hrequests_exceptions_suffixes_trie.search(exc_msg) is not None:
                expected_exception = True

            elif "net/http: request canceled" in exc_msg:
                expected_exception = True

            elif (
                ": net/http: HTTP/1.x transport connection broken: malformed HTTP response"
                in exc_msg
            ):
                expected_exception = True

    elif exc_module == "requests.exceptions":
        logger.info(
            log_prefix_local
            + f"{type(exc)=}, {fq_exc_name=}, {exc_msg=}, {url_slug=}, module s.b. requests.exceptions)"
        )

        if isinstance(exc, requests.exceptions.ConnectTimeout):
            if "Max retries exceeded with url" in exc_msg:
                expected_exception = True

        elif isinstance(exc, requests.exceptions.ConnectionError):
            if exc_msg.endswith('Temporary failure in name resolution)"))'):
                expected_exception = True

            elif "No address associated with hostname" in exc_msg:
                expected_exception = True

            elif "Connection refused" in exc_msg:
                expected_exception = True

            elif "Name or service not known" in exc_msg:
                expected_exception = True

            elif "Remote end closed connection without response" in exc_msg:
                expected_exception = True

            elif "Read timed out." in exc_msg:
                expected_exception = True

        elif isinstance(exc, requests.exceptions.HTTPError):
            if "502 Server Error: Bad Gateway for url" in exc_msg:
                expected_exception = True

        elif isinstance(exc, requests.exceptions.InvalidSchema):
            if "No connection adapters were found" in exc_msg:
                expected_exception = True

        elif isinstance(exc, requests.exceptions.InvalidURL):
            expected_exception = True

        elif isinstance(exc, requests.exceptions.ReadTimeout):
            if "Read timed out." in exc_msg:
                expected_exception = True

        elif isinstance(exc, requests.exceptions.SSLError):
            if "EOF occurred in violation of protocol" in exc_msg:
                expected_exception = True

            elif "SSL: SSLV3_ALERT_HANDSHAKE_FAILURE" in exc_msg:
                expected_exception = True

            elif "SSL: TLSV1_UNRECOGNIZED_NAME" in exc_msg:
                expected_exception = True

            elif "SSL: UNEXPECTED_EOF_WHILE_READING" in exc_msg:
                expected_exception = True

            elif "SSL: UNSAFE_LEGACY_RENEGOTIATION_DISABLED" in exc_msg:
                expected_exception = True

        elif isinstance(exc, requests.exceptions.TooManyRedirects):
            expected_exception = True

    elif exc_module == "lxml.etree":
        if isinstance(exc, lxml.etree.ParserError):
            if "Document is empty" in exc_msg:
                expected_exception = True

    elif exc_module == "builtins":
        if isinstance(exc, builtins.LookupError):
            if "unknown encoding" in exc_msg:
                raise

    if expected_exception:
        logger.info(log_prefix_local + exc_slug + url_slug)
    else:
        logger.error(log_prefix_local + "unexpected exception: " + exc_slug + url_slug)
        logger.error(
            log_prefix_local
            + f"unexpected exception name breakdown: {exc_module=} {exc_name=}"
        )
        if not tb_str:
            tb_str = traceback.format_exc()
        logger.error(log_prefix_local + tb_str)


def head_request(url=None, log_prefix=""):
    log_prefix += "head_request: "
    if not url:
        # logger.error(log_prefix + "no URL provided")
        raise Exception("no URL provided")

    try:
        response = requests.head(
            url,
            headers={"User-Agent": config.settings["SCRAPING"]["UA_STR"]},
            timeout=config.settings["SCRAPING"]["REQUESTS_GET_TIMEOUT_S"],
            verify=False,
        )
        return response.headers

    except Exception as exc:
        handle_exception(
            exc=exc,
            log_prefix=log_prefix,
            context={"url": url},
        )
        return None


def download_file_via_requests(url, dest_local_file, log_prefix="") -> bool:
    log_prefix_local = log_prefix + "download_file_via_requests: "
    try:
        with requests.get(
            allow_redirects=True,
            headers={"User-Agent": config.settings["SCRAPING"]["UA_STR"]},
            stream=True,
            timeout=config.settings["SCRAPING"]["REQUESTS_GET_TIMEOUT_S"],
            url=url,
            verify=False,
        ) as response:
            if response and response.status_code == 200:
                with open(dest_local_file, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
            else:
                logger.info(
                    log_prefix_local
                    + f"Error: status code {response.status_code} for url {url}"
                )
                return False
    except Exception as exc:
        handle_exception(
            exc=exc,
            log_prefix=log_prefix,
            context={"url": url},
        )
        return False


def download_file_via_hrequests(url, dest_local_file, log_prefix="") -> bool:
    log_prefix_local = log_prefix + "download_file_via_hrequests: "

    # get hrequests response object
    response = get_response_object_via_hrequests(
        url=url,
        log_prefix=log_prefix_local,
    )

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


# monkey patch a few hrequests dependencies to prevent them from crashing on me
fingerprints_bablosoft_com_responses_cached = {
    "chrome": (
        """{"found":true,"ua":"Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/118.0","headers":["Host","X-Real-Ip","X-Forwarded-For","Connection","Content-Length","User-Agent","Accept","Accept-Language","Accept-Encoding","Referer","Content-Type","Upgrade-Insecure-Requests","Accept-Datetime","Authorization","Cache-Control","If-Match","If-Modified-Since","If-None-Match","If-Range","If-Unmodified-Since","Max-Forwards","Pragma","Range","X-Requested-With","X-Http-Method-Override","X-Csrf-Token","X-Request-Id","Origin","Sec-Fetch-Dest","Sec-Fetch-Mode","Sec-Fetch-Site"],"hasSessionStorage":true,"hasLocalStorage":true,"hasIndexedDB":true,"hasWebSql":false,"width":1850,"height":968,"availWidth":1920,"availHeight":1080,"vendor":"AMD","renderer":"Radeon R9 200 Series","plugins":{"count":5,"first":"PDF Viewer"},"canvas":"125,126,129,124,131,124,123,125,127,124,124,130,128,130,123,125,129,125,124,129,130,130,125,128,129,131,126,127,126,127,131,126,128,125,130,131,124,129,124,126,130,124,130,127,131,130,130,123,127,128,126","audio":"113,129,114,140,115,118,131,108,127,127,123,127,120,115,121,123,144,114,124,138,139,133,135,116,110,123,116,131,113,122,128,142,137,128,145,133,133,130,113,131,138,111,109,130,145,144,139,109,136,122,125,120,138,109,132,109,128,131,132,133,118,126,108,111,147,130,133,140,117,139,117,115,127,120,107,109,135,136,114,147,130,130,127,135,131,131,127,146,139,113,134,107,107,113,142,141,145,136,111,143","audio_properties":{"BaseAudioContextSampleRate":44100,"AudioContextBaseLatency":0,"AudioContextOutputLatency":0,"AudioDestinationNodeMaxChannelCount":2,"AnalyzerNodeFftSize":2048,"AnalyzerNodeFrequencyBinCount":1024,"AnalyzerNodeMinDecibels":-100,"AnalyzerNodeMaxDecibels":-30,"AnalyzerNodeSmoothingTimeConstant":0.8,"BiquadFilterNodeFrequencyDefaultValue":350,"BiquadFilterNodeFrequencyMaxValue":22050,"BiquadFilterNodeFrequencyMinValue":-22050,"BiquadFilterNodeDetuneDefaultValue":0,"BiquadFilterNodeDetuneMaxValue":3.4028234663852886e+38,"BiquadFilterNodeDetuneMinValue":-3.4028234663852886e+38,"BiquadFilterNodeQDefaultValue":1,"BiquadFilterNodeQMaxValue":3.4028234663852886e+38,"BiquadFilterNodeQMinValue":-3.4028234663852886e+38,"BiquadFilterNodeGainDefaultValue":0,"BiquadFilterNodeGainMaxValue":3.4028234663852886e+38,"BiquadFilterNodeGainMinValue":-3.4028234663852886e+38,"BiquadFilterNodeType":"lowpass","AudioBufferSourceNodeDetuneDefaultValue":0,"AudioBufferSourceNodeDetuneMaxValue":3.4028234663852886e+38,"AudioBufferSourceNodeDetuneMinValue":-3.4028234663852886e+38,"AudioBufferSourceNodePlaybackRateDefaultValue":1,"AudioBufferSourceNodePlaybackRateMaxValue":3.4028234663852886e+38,"AudioBufferSourceNodePlaybackRateMinValue":-3.4028234663852886e+38,"ConstantSourceNodeOffsetDefaultValue":1,"ConstantSourceNodeOffsetMaxValue":3.4028234663852886e+38,"ConstantSourceNodeOffsetMinValue":-3.4028234663852886e+38,"DelayNodeDelayTimeDefaultValue":0,"DelayNodeDelayTimeMaxValue":1,"DelayNodeDelayTimeMinValue":0,"DynamicsCompressorNodeThresholdDefaultValue":-24,"DynamicsCompressorNodeThresholdMaxValue":0,"DynamicsCompressorNodeThresholdMinValue":-100,"DynamicsCompressorNodeKneeDefaultValue":30,"DynamicsCompressorNodeKneeMaxValue":40,"DynamicsCompressorNodeKneeMinValue":0,"DynamicsCompressorNodeRatioDefaultValue":12,"DynamicsCompressorNodeRatioMaxValue":20,"DynamicsCompressorNodeRatioMinValue":1,"DynamicsCompressorNodeReduction":0,"DynamicsCompressorNodeAttackDefaultValue":0.003000000026077032,"DynamicsCompressorNodeAttackMaxValue":1,"DynamicsCompressorNodeAttackMinValue":0,"DynamicsCompressorNodeReleaseDefaultValue":0.25,"DynamicsCompressorNodeReleaseMaxValue":1,"DynamicsCompressorNodeReleaseMinValue":0,"GainNodeGainDefaultValue":1,"GainNodeGainMaxValue":3.4028234663852886e+38,"GainNodeGainMinValue":-3.4028234663852886e+38,"OscillatorNodeFrequencyDefaultValue":440,"OscillatorNodeFrequencyMaxValue":22050,"OscillatorNodeFrequencyMinValue":-22050,"OscillatorNodeDetuneDefaultValue":0,"OscillatorNodeDetuneMaxValue":3.4028234663852886e+38,"OscillatorNodeDetuneMinValue":-3.4028234663852886e+38,"OscillatorNodeType":"sine","StereoPannerNodePanDefaultValue":0,"StereoPannerNodePanMaxValue":1,"StereoPannerNodePanMinValue":-1,"PannerNodePositionXDefaultValue":0,"PannerNodePositionXMaxValue":3.4028234663852886e+38,"PannerNodePositionXMinValue":-3.4028234663852886e+38,"PannerNodePositionYDefaultValue":0,"PannerNodePositionYMaxValue":3.4028234663852886e+38,"PannerNodePositionYMinValue":-3.4028234663852886e+38,"PannerNodePositionZDefaultValue":0,"PannerNodePositionZMaxValue":3.4028234663852886e+38,"PannerNodePositionZMinValue":-3.4028234663852886e+38,"PannerNodeOrientationXDefaultValue":1,"PannerNodeOrientationXMaxValue":3.4028234663852886e+38,"PannerNodeOrientationXMinValue":-3.4028234663852886e+38,"PannerNodeOrientationYDefaultValue":0,"PannerNodeOrientationYMaxValue":3.4028234663852886e+38,"PannerNodeOrientationYMinValue":-3.4028234663852886e+38,"PannerNodeOrientationZDefaultValue":0,"PannerNodeOrientationZMaxValue":3.4028234663852886e+38,"PannerNodeOrientationZMinValue":-3.4028234663852886e+38},"mimeTypes":{"count":2,"first":"application/pdf"},"fonts":{"count":313,"first":"Andale Mono"}}"""
    ),
    "chromium": (
        """{"found":true,"ua":"Mozilla/5.0 (X11; Linux x86_64; rv:91.0) Gecko/20100101 Firefox/91.0","headers":["Host","X-Real-Ip","X-Forwarded-For","Connection","Content-Length","User-Agent","Accept","Accept-Language","Accept-Encoding","Referer","Content-Type","Upgrade-Insecure-Requests","Accept-Datetime","Authorization","Cache-Control","If-Match","If-Modified-Since","If-None-Match","If-Range","If-Unmodified-Since","Max-Forwards","Pragma","Range","X-Requested-With","X-Http-Method-Override","X-Csrf-Token","X-Request-Id","Origin","Sec-Fetch-Dest","Sec-Fetch-Mode","Sec-Fetch-Site"],"hasSessionStorage":true,"hasLocalStorage":true,"hasIndexedDB":true,"hasWebSql":false,"width":1856,"height":902,"availWidth":1856,"availHeight":1016,"vendor":"X.Org","renderer":"Generic Renderer","plugins":{"count":0},"canvas":"123,125,123,131,123,129,124,127,126,123,125,125,124,129,127,130,126,130,125,130,128,124,128,131,123,125,123,131,129,127,129,130,130,123,129,128,126,131,124,125,123,129,126,128,127,130,126,128,130,123,128","audio":"124,108,143,147,139,146,117,142,122,125,138,138,136,126,146,118,128,121,146,136,135,135,117,121,137,124,134,112,127,113,129,143,124,142,131,114,124,140,133,130,117,132,137,112,114,116,109,136,144,114,135,137,117,112,124,126,107,114,122,109,132,145,140,138,122,130,135,127,125,111,115,132,122,137,131,120,115,112,143,146,129,131,122,115,138,137,142,126,107,134,112,118,136,125,121,142,112,113,115,137","audio_properties":{"BaseAudioContextSampleRate":48000,"AudioContextBaseLatency":0,"AudioContextOutputLatency":0,"AudioDestinationNodeMaxChannelCount":2,"AnalyzerNodeFftSize":2048,"AnalyzerNodeFrequencyBinCount":1024,"AnalyzerNodeMinDecibels":-100,"AnalyzerNodeMaxDecibels":-30,"AnalyzerNodeSmoothingTimeConstant":0.8,"BiquadFilterNodeFrequencyDefaultValue":350,"BiquadFilterNodeFrequencyMaxValue":24000,"BiquadFilterNodeFrequencyMinValue":-24000,"BiquadFilterNodeDetuneDefaultValue":0,"BiquadFilterNodeDetuneMaxValue":3.4028234663852886e+38,"BiquadFilterNodeDetuneMinValue":-3.4028234663852886e+38,"BiquadFilterNodeQDefaultValue":1,"BiquadFilterNodeQMaxValue":3.4028234663852886e+38,"BiquadFilterNodeQMinValue":-3.4028234663852886e+38,"BiquadFilterNodeGainDefaultValue":0,"BiquadFilterNodeGainMaxValue":3.4028234663852886e+38,"BiquadFilterNodeGainMinValue":-3.4028234663852886e+38,"BiquadFilterNodeType":"lowpass","AudioBufferSourceNodeDetuneDefaultValue":0,"AudioBufferSourceNodeDetuneMaxValue":3.4028234663852886e+38,"AudioBufferSourceNodeDetuneMinValue":-3.4028234663852886e+38,"AudioBufferSourceNodePlaybackRateDefaultValue":1,"AudioBufferSourceNodePlaybackRateMaxValue":3.4028234663852886e+38,"AudioBufferSourceNodePlaybackRateMinValue":-3.4028234663852886e+38,"ConstantSourceNodeOffsetDefaultValue":1,"ConstantSourceNodeOffsetMaxValue":3.4028234663852886e+38,"ConstantSourceNodeOffsetMinValue":-3.4028234663852886e+38,"DelayNodeDelayTimeDefaultValue":0,"DelayNodeDelayTimeMaxValue":1,"DelayNodeDelayTimeMinValue":0,"DynamicsCompressorNodeThresholdDefaultValue":-24,"DynamicsCompressorNodeThresholdMaxValue":0,"DynamicsCompressorNodeThresholdMinValue":-100,"DynamicsCompressorNodeKneeDefaultValue":30,"DynamicsCompressorNodeKneeMaxValue":40,"DynamicsCompressorNodeKneeMinValue":0,"DynamicsCompressorNodeRatioDefaultValue":12,"DynamicsCompressorNodeRatioMaxValue":20,"DynamicsCompressorNodeRatioMinValue":1,"DynamicsCompressorNodeReduction":0,"DynamicsCompressorNodeAttackDefaultValue":0.003000000026077032,"DynamicsCompressorNodeAttackMaxValue":1,"DynamicsCompressorNodeAttackMinValue":0,"DynamicsCompressorNodeReleaseDefaultValue":0.25,"DynamicsCompressorNodeReleaseMaxValue":1,"DynamicsCompressorNodeReleaseMinValue":0,"GainNodeGainDefaultValue":1,"GainNodeGainMaxValue":3.4028234663852886e+38,"GainNodeGainMinValue":-3.4028234663852886e+38,"OscillatorNodeFrequencyDefaultValue":440,"OscillatorNodeFrequencyMaxValue":24000,"OscillatorNodeFrequencyMinValue":-24000,"OscillatorNodeDetuneDefaultValue":0,"OscillatorNodeDetuneMaxValue":3.4028234663852886e+38,"OscillatorNodeDetuneMinValue":-3.4028234663852886e+38,"OscillatorNodeType":"sine","StereoPannerNodePanDefaultValue":0,"StereoPannerNodePanMaxValue":1,"StereoPannerNodePanMinValue":-1,"PannerNodePositionXDefaultValue":0,"PannerNodePositionXMaxValue":3.4028234663852886e+38,"PannerNodePositionXMinValue":-3.4028234663852886e+38,"PannerNodePositionYDefaultValue":0,"PannerNodePositionYMaxValue":3.4028234663852886e+38,"PannerNodePositionYMinValue":-3.4028234663852886e+38,"PannerNodePositionZDefaultValue":0,"PannerNodePositionZMaxValue":3.4028234663852886e+38,"PannerNodePositionZMinValue":-3.4028234663852886e+38,"PannerNodeOrientationXDefaultValue":1,"PannerNodeOrientationXMaxValue":3.4028234663852886e+38,"PannerNodeOrientationXMinValue":-3.4028234663852886e+38,"PannerNodeOrientationYDefaultValue":0,"PannerNodeOrientationYMaxValue":3.4028234663852886e+38,"PannerNodeOrientationYMinValue":-3.4028234663852886e+38,"PannerNodeOrientationZDefaultValue":0,"PannerNodeOrientationZMaxValue":3.4028234663852886e+38,"PannerNodeOrientationZMinValue":-3.4028234663852886e+38},"mimeTypes":{"count":0},"fonts":{"count":232,"first":"Liberation Serif"}}"""
    ),
    "edge": (
        """{"found":true,"ua":"Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0","headers":["Host","X-Real-Ip","X-Forwarded-For","Connection","Content-Length","User-Agent","Accept","Accept-Language","Accept-Encoding","Referer","Content-Type","Upgrade-Insecure-Requests","Accept-Datetime","Authorization","Cache-Control","If-Match","If-Modified-Since","If-None-Match","If-Range","If-Unmodified-Since","Max-Forwards","Pragma","Range","X-Requested-With","X-Http-Method-Override","X-Csrf-Token","X-Request-Id","Origin","Sec-Fetch-Dest","Sec-Fetch-Mode","Sec-Fetch-Site"],"hasSessionStorage":true,"hasLocalStorage":true,"hasIndexedDB":true,"hasWebSql":false,"width":1680,"height":918,"availWidth":1680,"availHeight":1050,"vendor":"NVIDIA Corporation","renderer":"GeForce GTX 980/PCIe/SSE2","plugins":{"count":5,"first":"PDF Viewer"},"canvas":"124,130,128,127,126,131,130,123,127,127,129,126,131,130,123,128,130,128,127,128,130,128,126,130,129,128,127,124,130,128,131,129,126,125,131,124,125,123,128,123,129,125,129,125,123,125,124,123,125,128,130","audio":"121,118,118,135,120,127,123,137,112,110,115,111,137,113,119,127,114,116,144,136,135,117,109,129,136,138,140,127,123,134,143,125,132,112,142,113,109,124,128,123,127,142,115,146,124,118,138,128,135,143,127,112,139,112,133,136,132,109,145,113,146,109,132,113,119,115,125,141,145,113,111,107,111,123,112,121,132,112,115,112,144,113,110,114,146,146,138,108,123,123,110,117,131,120,129,133,138,137,124,114","audio_properties":{"BaseAudioContextSampleRate":48000,"AudioContextBaseLatency":0,"AudioContextOutputLatency":0,"AudioDestinationNodeMaxChannelCount":2,"AnalyzerNodeFftSize":2048,"AnalyzerNodeFrequencyBinCount":1024,"AnalyzerNodeMinDecibels":-100,"AnalyzerNodeMaxDecibels":-30,"AnalyzerNodeSmoothingTimeConstant":0.8,"BiquadFilterNodeFrequencyDefaultValue":350,"BiquadFilterNodeFrequencyMaxValue":24000,"BiquadFilterNodeFrequencyMinValue":-24000,"BiquadFilterNodeDetuneDefaultValue":0,"BiquadFilterNodeDetuneMaxValue":3.4028234663852886e+38,"BiquadFilterNodeDetuneMinValue":-3.4028234663852886e+38,"BiquadFilterNodeQDefaultValue":1,"BiquadFilterNodeQMaxValue":3.4028234663852886e+38,"BiquadFilterNodeQMinValue":-3.4028234663852886e+38,"BiquadFilterNodeGainDefaultValue":0,"BiquadFilterNodeGainMaxValue":3.4028234663852886e+38,"BiquadFilterNodeGainMinValue":-3.4028234663852886e+38,"BiquadFilterNodeType":"lowpass","AudioBufferSourceNodeDetuneDefaultValue":0,"AudioBufferSourceNodeDetuneMaxValue":3.4028234663852886e+38,"AudioBufferSourceNodeDetuneMinValue":-3.4028234663852886e+38,"AudioBufferSourceNodePlaybackRateDefaultValue":1,"AudioBufferSourceNodePlaybackRateMaxValue":3.4028234663852886e+38,"AudioBufferSourceNodePlaybackRateMinValue":-3.4028234663852886e+38,"ConstantSourceNodeOffsetDefaultValue":1,"ConstantSourceNodeOffsetMaxValue":3.4028234663852886e+38,"ConstantSourceNodeOffsetMinValue":-3.4028234663852886e+38,"DelayNodeDelayTimeDefaultValue":0,"DelayNodeDelayTimeMaxValue":1,"DelayNodeDelayTimeMinValue":0,"DynamicsCompressorNodeThresholdDefaultValue":-24,"DynamicsCompressorNodeThresholdMaxValue":0,"DynamicsCompressorNodeThresholdMinValue":-100,"DynamicsCompressorNodeKneeDefaultValue":30,"DynamicsCompressorNodeKneeMaxValue":40,"DynamicsCompressorNodeKneeMinValue":0,"DynamicsCompressorNodeRatioDefaultValue":12,"DynamicsCompressorNodeRatioMaxValue":20,"DynamicsCompressorNodeRatioMinValue":1,"DynamicsCompressorNodeReduction":0,"DynamicsCompressorNodeAttackDefaultValue":0.003000000026077032,"DynamicsCompressorNodeAttackMaxValue":1,"DynamicsCompressorNodeAttackMinValue":0,"DynamicsCompressorNodeReleaseDefaultValue":0.25,"DynamicsCompressorNodeReleaseMaxValue":1,"DynamicsCompressorNodeReleaseMinValue":0,"GainNodeGainDefaultValue":1,"GainNodeGainMaxValue":3.4028234663852886e+38,"GainNodeGainMinValue":-3.4028234663852886e+38,"OscillatorNodeFrequencyDefaultValue":440,"OscillatorNodeFrequencyMaxValue":24000,"OscillatorNodeFrequencyMinValue":-24000,"OscillatorNodeDetuneDefaultValue":0,"OscillatorNodeDetuneMaxValue":3.4028234663852886e+38,"OscillatorNodeDetuneMinValue":-3.4028234663852886e+38,"OscillatorNodeType":"sine","StereoPannerNodePanDefaultValue":0,"StereoPannerNodePanMaxValue":1,"StereoPannerNodePanMinValue":-1,"PannerNodePositionXDefaultValue":0,"PannerNodePositionXMaxValue":3.4028234663852886e+38,"PannerNodePositionXMinValue":-3.4028234663852886e+38,"PannerNodePositionYDefaultValue":0,"PannerNodePositionYMaxValue":3.4028234663852886e+38,"PannerNodePositionYMinValue":-3.4028234663852886e+38,"PannerNodePositionZDefaultValue":0,"PannerNodePositionZMaxValue":3.4028234663852886e+38,"PannerNodePositionZMinValue":-3.4028234663852886e+38,"PannerNodeOrientationXDefaultValue":1,"PannerNodeOrientationXMaxValue":3.4028234663852886e+38,"PannerNodeOrientationXMinValue":-3.4028234663852886e+38,"PannerNodeOrientationYDefaultValue":0,"PannerNodeOrientationYMaxValue":3.4028234663852886e+38,"PannerNodeOrientationYMinValue":-3.4028234663852886e+38,"PannerNodeOrientationZDefaultValue":0,"PannerNodeOrientationZMaxValue":3.4028234663852886e+38,"PannerNodeOrientationZMinValue":-3.4028234663852886e+38},"mimeTypes":{"count":2,"first":"application/pdf"},"fonts":{"count":193,"first":"FreeMono"}}"""
    ),
    "firefox": (
        """{"found":true,"ua":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36","headers":["Host","X-Real-Ip","X-Forwarded-For","Connection","Content-Length","Cache-Control","Sec-Ch-Ua","Accept-Datetime","Dnt","X-Csrf-Token","If-Unmodified-Since","Authorization","X-Requested-With","If-Modified-Since","Max-Forwards","X-Http-Method-Override","X-Request-Id","Sec-Ch-Ua-Platform","Pragma","Upgrade-Insecure-Requests","Sec-Ch-Ua-Mobile","User-Agent","Content-Type","If-None-Match","If-Match","If-Range","Range","Accept","Origin","Sec-Fetch-Site","Sec-Fetch-Mode","Sec-Fetch-Dest","Referer","Accept-Encoding","Accept-Language"],"hasSessionStorage":true,"hasLocalStorage":true,"hasIndexedDB":true,"hasWebSql":false,"width":1920,"height":929,"availWidth":1920,"availHeight":1050,"vendor":"Google Inc. (NVIDIA)","renderer":"ANGLE (NVIDIA, Vulkan 1.3.224 (NVIDIA NVIDIA GeForce GTX 1650 (0x00001F82)), NVIDIA)","plugins":{"count":5,"first":"PDF Viewer"},"canvas":"124,124,131,123,130,131,130,127,127,127,128,125,125,126,126,130,125,128,128,130,130,124,124,130,127,131,123,123,126,129,128,129,130,131,130,125,123,128,126,124,123,130,130,131,127,126,131,129,129,128,130","audio":"117,131,107,109,121,124,115,122,120,123,135,145,110,128,114,120,137,119,108,114,110,121,124,126,128,138,135,132,147,140,123,110,115,122,140,120,110,135,114,138,137,128,118,121,121,118,139,117,136,137,131,127,134,113,109,146,108,125,137,134,147,110,118,128,108,134,116,113,124,109,139,110,122,120,113,118,111,138,135,113,109,130,145,142,140,121,122,117,116,141,138,121,137,113,131,121,122,113,108,141","audio_properties":{"BaseAudioContextSampleRate":44100,"AudioContextBaseLatency":0.011609977324263039,"AudioContextOutputLatency":0,"AudioDestinationNodeMaxChannelCount":2,"AnalyzerNodeFftSize":2048,"AnalyzerNodeFrequencyBinCount":1024,"AnalyzerNodeMinDecibels":-100,"AnalyzerNodeMaxDecibels":-30,"AnalyzerNodeSmoothingTimeConstant":0.8,"BiquadFilterNodeFrequencyDefaultValue":350,"BiquadFilterNodeFrequencyMaxValue":22050,"BiquadFilterNodeFrequencyMinValue":0,"BiquadFilterNodeDetuneDefaultValue":0,"BiquadFilterNodeDetuneMaxValue":153600,"BiquadFilterNodeDetuneMinValue":-153600,"BiquadFilterNodeQDefaultValue":1,"BiquadFilterNodeQMaxValue":3.4028234663852886e+38,"BiquadFilterNodeQMinValue":-3.4028234663852886e+38,"BiquadFilterNodeGainDefaultValue":0,"BiquadFilterNodeGainMaxValue":1541.273681640625,"BiquadFilterNodeGainMinValue":-3.4028234663852886e+38,"BiquadFilterNodeType":"lowpass","AudioBufferSourceNodeDetuneDefaultValue":0,"AudioBufferSourceNodeDetuneMaxValue":3.4028234663852886e+38,"AudioBufferSourceNodeDetuneMinValue":-3.4028234663852886e+38,"AudioBufferSourceNodePlaybackRateDefaultValue":1,"AudioBufferSourceNodePlaybackRateMaxValue":3.4028234663852886e+38,"AudioBufferSourceNodePlaybackRateMinValue":-3.4028234663852886e+38,"ConstantSourceNodeOffsetDefaultValue":1,"ConstantSourceNodeOffsetMaxValue":3.4028234663852886e+38,"ConstantSourceNodeOffsetMinValue":-3.4028234663852886e+38,"DelayNodeDelayTimeDefaultValue":0,"DelayNodeDelayTimeMaxValue":1,"DelayNodeDelayTimeMinValue":0,"DynamicsCompressorNodeThresholdDefaultValue":-24,"DynamicsCompressorNodeThresholdMaxValue":0,"DynamicsCompressorNodeThresholdMinValue":-100,"DynamicsCompressorNodeKneeDefaultValue":30,"DynamicsCompressorNodeKneeMaxValue":40,"DynamicsCompressorNodeKneeMinValue":0,"DynamicsCompressorNodeRatioDefaultValue":12,"DynamicsCompressorNodeRatioMaxValue":20,"DynamicsCompressorNodeRatioMinValue":1,"DynamicsCompressorNodeReduction":0,"DynamicsCompressorNodeAttackDefaultValue":0.003000000026077032,"DynamicsCompressorNodeAttackMaxValue":1,"DynamicsCompressorNodeAttackMinValue":0,"DynamicsCompressorNodeReleaseDefaultValue":0.25,"DynamicsCompressorNodeReleaseMaxValue":1,"DynamicsCompressorNodeReleaseMinValue":0,"GainNodeGainDefaultValue":1,"GainNodeGainMaxValue":3.4028234663852886e+38,"GainNodeGainMinValue":-3.4028234663852886e+38,"OscillatorNodeFrequencyDefaultValue":440,"OscillatorNodeFrequencyMaxValue":22050,"OscillatorNodeFrequencyMinValue":-22050,"OscillatorNodeDetuneDefaultValue":0,"OscillatorNodeDetuneMaxValue":153600,"OscillatorNodeDetuneMinValue":-153600,"OscillatorNodeType":"sine","StereoPannerNodePanDefaultValue":0,"StereoPannerNodePanMaxValue":1,"StereoPannerNodePanMinValue":-1,"AudioListenerPositionXDefaultValue":0,"AudioListenerPositionXMaxValue":3.4028234663852886e+38,"AudioListenerPositionXMinValue":-3.4028234663852886e+38,"AudioListenerPositionYDefaultValue":0,"AudioListenerPositionYMaxValue":3.4028234663852886e+38,"AudioListenerPositionYMinValue":-3.4028234663852886e+38,"AudioListenerPositionZDefaultValue":0,"AudioListenerPositionZMaxValue":3.4028234663852886e+38,"AudioListenerPositionZMinValue":-3.4028234663852886e+38,"AudioListenerForwardXDefaultValue":0,"AudioListenerForwardXMaxValue":3.4028234663852886e+38,"AudioListenerForwardXMinValue":-3.4028234663852886e+38,"AudioListenerForwardYDefaultValue":0,"AudioListenerForwardYMaxValue":3.4028234663852886e+38,"AudioListenerForwardYMinValue":-3.4028234663852886e+38,"AudioListenerForwardZDefaultValue":-1,"AudioListenerForwardZMaxValue":3.4028234663852886e+38,"AudioListenerForwardZMinValue":-3.4028234663852886e+38,"AudioListenerUpXDefaultValue":0,"AudioListenerUpXMaxValue":3.4028234663852886e+38,"AudioListenerUpXMinValue":-3.4028234663852886e+38,"AudioListenerUpYDefaultValue":1,"AudioListenerUpYMaxValue":3.4028234663852886e+38,"AudioListenerUpYMinValue":-3.4028234663852886e+38,"AudioListenerUpZDefaultValue":0,"AudioListenerUpZMaxValue":3.4028234663852886e+38,"AudioListenerUpZMinValue":-3.4028234663852886e+38,"PannerNodePositionXDefaultValue":0,"PannerNodePositionXMaxValue":3.4028234663852886e+38,"PannerNodePositionXMinValue":-3.4028234663852886e+38,"PannerNodePositionYDefaultValue":0,"PannerNodePositionYMaxValue":3.4028234663852886e+38,"PannerNodePositionYMinValue":-3.4028234663852886e+38,"PannerNodePositionZDefaultValue":0,"PannerNodePositionZMaxValue":3.4028234663852886e+38,"PannerNodePositionZMinValue":-3.4028234663852886e+38,"PannerNodeOrientationXDefaultValue":1,"PannerNodeOrientationXMaxValue":3.4028234663852886e+38,"PannerNodeOrientationXMinValue":-3.4028234663852886e+38,"PannerNodeOrientationYDefaultValue":0,"PannerNodeOrientationYMaxValue":3.4028234663852886e+38,"PannerNodeOrientationYMinValue":-3.4028234663852886e+38,"PannerNodeOrientationZDefaultValue":0,"PannerNodeOrientationZMaxValue":3.4028234663852886e+38,"PannerNodeOrientationZMinValue":-3.4028234663852886e+38},"mimeTypes":{"count":2,"first":"application/pdf"},"fonts":{"count":222,"first":"Andale Mono"}}"""
    ),
    "safari": (
        """{"found":true,"ua":"Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0","headers":["Host","X-Real-Ip","X-Forwarded-For","Connection","Content-Length","User-Agent","Accept","Accept-Language","Accept-Encoding","Referer","Content-Type","Upgrade-Insecure-Requests","Accept-Datetime","Authorization","Cache-Control","If-Match","If-Modified-Since","If-None-Match","If-Range","If-Unmodified-Since","Max-Forwards","Pragma","Range","X-Requested-With","X-Http-Method-Override","X-Csrf-Token","X-Request-Id","Origin","Dnt","Sec-Fetch-Dest","Sec-Fetch-Mode","Sec-Fetch-Site"],"hasSessionStorage":true,"hasLocalStorage":true,"hasIndexedDB":true,"hasWebSql":false,"width":1680,"height":904,"availWidth":1680,"availHeight":1013,"vendor":"Intel","renderer":"Intel(R) HD Graphics 400","plugins":{"count":5,"first":"PDF Viewer"},"canvas":"125,131,126,131,131,124,123,127,128,124,123,124,124,126,130,127,127,129,126,128,126,127,123,129,124,124,127,129,123,130,127,123,129,130,123,123,129,126,131,125,125,124,131,127,124,124,125,127,127,128,123","audio":"114,123,145,146,141,125,136,113,136,119,112,135,116,140,126,113,138,113,108,145,122,147,122,134,126,141,113,109,126,124,146,145,123,110,117,117,137,130,129,130,115,110,122,134,118,109,127,138,147,139,147,133,111,136,131,119,142,114,131,144,136,120,129,125,128,128,120,133,142,121,139,108,124,136,126,143,131,127,141,115,143,107,133,123,114,126,143,123,114,120,144,107,112,125,126,140,115,118,113,115","audio_properties":{"BaseAudioContextSampleRate":48000,"AudioContextBaseLatency":0,"AudioContextOutputLatency":0,"AudioDestinationNodeMaxChannelCount":2,"AnalyzerNodeFftSize":2048,"AnalyzerNodeFrequencyBinCount":1024,"AnalyzerNodeMinDecibels":-100,"AnalyzerNodeMaxDecibels":-30,"AnalyzerNodeSmoothingTimeConstant":0.8,"BiquadFilterNodeFrequencyDefaultValue":350,"BiquadFilterNodeFrequencyMaxValue":24000,"BiquadFilterNodeFrequencyMinValue":-24000,"BiquadFilterNodeDetuneDefaultValue":0,"BiquadFilterNodeDetuneMaxValue":3.4028234663852886e+38,"BiquadFilterNodeDetuneMinValue":-3.4028234663852886e+38,"BiquadFilterNodeQDefaultValue":1,"BiquadFilterNodeQMaxValue":3.4028234663852886e+38,"BiquadFilterNodeQMinValue":-3.4028234663852886e+38,"BiquadFilterNodeGainDefaultValue":0,"BiquadFilterNodeGainMaxValue":3.4028234663852886e+38,"BiquadFilterNodeGainMinValue":-3.4028234663852886e+38,"BiquadFilterNodeType":"lowpass","AudioBufferSourceNodeDetuneDefaultValue":0,"AudioBufferSourceNodeDetuneMaxValue":3.4028234663852886e+38,"AudioBufferSourceNodeDetuneMinValue":-3.4028234663852886e+38,"AudioBufferSourceNodePlaybackRateDefaultValue":1,"AudioBufferSourceNodePlaybackRateMaxValue":3.4028234663852886e+38,"AudioBufferSourceNodePlaybackRateMinValue":-3.4028234663852886e+38,"ConstantSourceNodeOffsetDefaultValue":1,"ConstantSourceNodeOffsetMaxValue":3.4028234663852886e+38,"ConstantSourceNodeOffsetMinValue":-3.4028234663852886e+38,"DelayNodeDelayTimeDefaultValue":0,"DelayNodeDelayTimeMaxValue":1,"DelayNodeDelayTimeMinValue":0,"DynamicsCompressorNodeThresholdDefaultValue":-24,"DynamicsCompressorNodeThresholdMaxValue":0,"DynamicsCompressorNodeThresholdMinValue":-100,"DynamicsCompressorNodeKneeDefaultValue":30,"DynamicsCompressorNodeKneeMaxValue":40,"DynamicsCompressorNodeKneeMinValue":0,"DynamicsCompressorNodeRatioDefaultValue":12,"DynamicsCompressorNodeRatioMaxValue":20,"DynamicsCompressorNodeRatioMinValue":1,"DynamicsCompressorNodeReduction":0,"DynamicsCompressorNodeAttackDefaultValue":0.003000000026077032,"DynamicsCompressorNodeAttackMaxValue":1,"DynamicsCompressorNodeAttackMinValue":0,"DynamicsCompressorNodeReleaseDefaultValue":0.25,"DynamicsCompressorNodeReleaseMaxValue":1,"DynamicsCompressorNodeReleaseMinValue":0,"GainNodeGainDefaultValue":1,"GainNodeGainMaxValue":3.4028234663852886e+38,"GainNodeGainMinValue":-3.4028234663852886e+38,"OscillatorNodeFrequencyDefaultValue":440,"OscillatorNodeFrequencyMaxValue":24000,"OscillatorNodeFrequencyMinValue":-24000,"OscillatorNodeDetuneDefaultValue":0,"OscillatorNodeDetuneMaxValue":3.4028234663852886e+38,"OscillatorNodeDetuneMinValue":-3.4028234663852886e+38,"OscillatorNodeType":"sine","StereoPannerNodePanDefaultValue":0,"StereoPannerNodePanMaxValue":1,"StereoPannerNodePanMinValue":-1,"PannerNodePositionXDefaultValue":0,"PannerNodePositionXMaxValue":3.4028234663852886e+38,"PannerNodePositionXMinValue":-3.4028234663852886e+38,"PannerNodePositionYDefaultValue":0,"PannerNodePositionYMaxValue":3.4028234663852886e+38,"PannerNodePositionYMinValue":-3.4028234663852886e+38,"PannerNodePositionZDefaultValue":0,"PannerNodePositionZMaxValue":3.4028234663852886e+38,"PannerNodePositionZMinValue":-3.4028234663852886e+38,"PannerNodeOrientationXDefaultValue":1,"PannerNodeOrientationXMaxValue":3.4028234663852886e+38,"PannerNodeOrientationXMinValue":-3.4028234663852886e+38,"PannerNodeOrientationYDefaultValue":0,"PannerNodeOrientationYMaxValue":3.4028234663852886e+38,"PannerNodeOrientationYMinValue":-3.4028234663852886e+38,"PannerNodeOrientationZDefaultValue":0,"PannerNodeOrientationZMaxValue":3.4028234663852886e+38,"PannerNodeOrientationZMinValue":-3.4028234663852886e+38},"mimeTypes":{"count":2,"first":"application/pdf"},"fonts":{"count":252,"first":"Haettenschweiler"}}"""
    ),
}

fingerprints_bablosoft_com_responses = {}
for k, v in fingerprints_bablosoft_com_responses_cached.items():
    fingerprints_bablosoft_com_responses[k] = json.loads(v)


async def monkeypatched_computer_0_7_1(self, proxy, browser_name) -> None:
    # hrequests-0.7.1
    data = fingerprints_bablosoft_com_responses[browser_name]

    # self.useragent = data.get("ua")
    self.vendor = data.get("vendor")
    self.renderer = data.get("renderer")
    self.width = data.get("width", 0)
    self.height = data.get("height", 0)
    self.avail_width = data.get("availWidth", 0)
    self.avail_height = data.get("availHeight", 0)
    # If the Window is too small for the captcha
    if (
        self.width
        and self.height > 810
        and self.avail_height > 810
        and self.avail_width > 810
    ):
        return


faker = hrequests.playwright_mock.Faker
faker.computer = monkeypatched_computer_0_7_1


re_ip_address = r"^(\d{1,3}\.){3}\d{1,3}$"


def is_ip_address(ip_address):
    if not re.match(re_ip_address, ip_address):
        return False

    octets = ip_address.split(".")
    for octet in octets:
        if not 0 <= int(octet) <= 255:
            return False

    return True


async def monkeypatched_check_proxy_0_7_1(self) -> None:
    # hrequests-0.7.1
    self.country = "United States"
    self.country_code = "US"
    self.region = "TX"
    self.city = "Austin"
    self.zip = "78723"
    self.latitude = 30.3023
    self.longitude = -97.6914
    self.timezone = "America/Chicago"


async def monkeypatched_check_proxy_0_8_1(
    self, httpx_client: httpx.AsyncClient
) -> None:
    # hrequests-0.8.1
    self.country = "United States"
    self.country_code = "US"
    self.region = "TX"
    self.city = "Austin"
    self.zip = "78723"
    self.latitude = 30.3023
    self.longitude = -97.6914
    self.timezone = "America/Chicago"


proxy_manager = hrequests.playwright_mock.ProxyManager
proxy_manager.check_proxy = monkeypatched_check_proxy_0_7_1


async def monkeypatched_goto_0_7_1(self, url):
    # hrequests-0.7.1
    resp = await self.page.goto(url)
    if resp:
        self.status_code = resp.status
    else:
        logger.error(f"monkeypatched_goto_0_7_1(): resp is None. ~Tim~")
    return resp


async def monkeypatched_goto_0_8_1(self, url):
    # hrequests-0.8.1
    resp = await self.page.goto(url)
    if resp:
        self.status_code = resp.status
    else:
        logger.error(f"monkeypatched_goto_0_8_1(): resp is None. ~Tim~")
    return resp


hrequests.BrowserSession._goto = monkeypatched_goto_0_7_1
