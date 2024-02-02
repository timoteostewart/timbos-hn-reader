import json
import logging
import os
import re
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
import utils_random
from thnr_exceptions import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# quiet httpx since it's chatty
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="httpx")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

    except requests.exceptions.HTTPError as exc:
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
    if not url:
        raise Exception("no URL provided")

    headers = None
    try:
        headers = head_request(url, log_prefix=log_prefix)
    except Exception as exc:
        exc_name = f"{exc.__class__.__module__}.{exc.__class__.__name__}"
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        logger.info(log_prefix + f"{exc_slug}")

    if not headers:
        # suppress logging if we're coming from download_og_image() since we log there
        if log_prefix.endswith("d_og_i(): "):
            pass
        else:
            logger.info(log_prefix + f"failed to get HTTP headers for {url}")
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
    else:
        logger.info(
            log_prefix + f"content-type is absent from HTTP headers for url {url}"
        )
        return None

    if content_type:
        return content_type
    else:
        logger.info(
            log_prefix
            + f"content-type could not be determined from HTTP headers for url {url}"
        )
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


def get_rendered_page_source_via_response_object(response_object, log_prefix=""):
    log_prefix_local = log_prefix + "get_rendered_page_source_via_response_object(): "
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


def handle_exception(exc: Exception = None, log_prefix="", context=None):
    exc_name = f"{exc.__class__.__module__}.{exc.__class__.__name__}"
    exc_msg = str(exc)
    exc_slug = f"{exc_name}: {exc_msg}"

    if isinstance(exc, requests.exceptions.ConnectTimeout):
        if "Max retries exceeded with url" in exc_msg:
            url = context["url"] if (context and "url" in context) else ""
            if url:
                url_slug = f" for url {url}"
            else:
                url_slug = ""
            logger.info(log_prefix + exc_name + url_slug)
        else:
            tb_str = traceback.format_exc()
            logger.error(log_prefix + "unexpected exception: " + exc_slug)
            logger.error(log_prefix + tb_str)

    elif isinstance(exc, requests.exceptions.ReadTimeout):
        if "Read timed out." in exc_msg:
            url = context["url"] if (context and "url" in context) else ""
            if url:
                url_slug = f" for url {url}"
            else:
                url_slug = ""
            logger.info(log_prefix + exc_name + url_slug)
        else:
            tb_str = traceback.format_exc()
            logger.error(log_prefix + "unexpected exception: " + exc_slug)
            logger.error(log_prefix + tb_str)

    elif isinstance(exc, requests.exceptions.HTTPError):
        if "502 Server Error: Bad Gateway for url" in exc_msg:
            url = context["url"] if (context and "url" in context) else ""
            if url:
                url_slug = f" for url {url}"
            else:
                url_slug = ""
            logger.info(log_prefix + exc_name + url_slug)
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
            log_prefix + "fell through all exceptions! should never happen. (~Tim~)"
        )


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


def head_request(url=None, log_prefix=""):
    log_prefix += "head_request(): "
    if not url:
        # logger.error(log_prefix + "no URL provided")
        raise Exception("no URL provided")

    try:
        resp = requests.head(
            url,
            verify=False,
            timeout=config.settings["SCRAPING"]["REQUESTS_GET_TIMEOUT_S"],
            headers={"User-Agent": config.settings["SCRAPING"]["UA_STR"]},
        )
        return resp.headers

    except requests.exceptions.ConnectTimeout as exc:
        exc_name = f"{exc.__class__.__module__}.{exc.__class__.__name__}"
        # exc_msg = str(exc)
        # exc_slug = f"{exc_name}: {exc_msg}"
        logger.info(log_prefix + f"{exc_name} for url {url}")
        # tb_str = traceback.format_exc()
        # logger.error(log_prefix + tb_str)
        return None

    except requests.exceptions.ConnectionError as exc:
        exc_name = f"{exc.__class__.__module__}.{exc.__class__.__name__}"
        # exc_msg = str(exc)
        # exc_slug = f"{exc_name}: {exc_msg}"
        logger.info(log_prefix + f"{exc_name} for url {url}")
        # tb_str = traceback.format_exc()
        # logger.error(log_prefix + tb_str)
        return None

    except requests.exceptions.ReadTimeout as exc:
        exc_name = f"{exc.__class__.__module__}.{exc.__class__.__name__}"
        # exc_msg = str(exc)
        # exc_slug = f"{exc_name}: {exc_msg}"
        logger.info(log_prefix + f"{exc_name} for url {url}")
        # tb_str = traceback.format_exc()
        # logger.error(log_prefix + tb_str)
        return None

    except requests.exceptions.SSLError as exc:
        exc_name = f"{exc.__class__.__module__}.{exc.__class__.__name__}"
        # exc_msg = str(exc)
        # exc_slug = f"{exc_name}: {exc_msg}"
        logger.info(log_prefix + f"{exc_name} for url {url}")
        # tb_str = traceback.format_exc()
        # logger.error(log_prefix + tb_str)
        return None

    except Exception as exc:
        exc_name = f"{exc.__class__.__module__}.{exc.__class__.__name__}"
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        logger.error(log_prefix + f"unexpected exception: {exc_slug} for url {url}")
        tb_str = traceback.format_exc()
        logger.error(log_prefix + tb_str + " (~Tim~)")
        return None


# monkey patch a few hrequests dependencies to prevent them from crashing on me
fingerprints_bablosoft_com_responses = {
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

for k, v in fingerprints_bablosoft_com_responses.items():
    fingerprints_bablosoft_com_responses[k] = json.loads(v)

for browser_name in [
    "chrome",
    "chromium",
    "edge",
    "firefox",
    "safari",
]:
    try:
        res = endpoint_query_via_requests(
            url=f"http://fingerprints.bablosoft.com/preview?rand=0.1&tags={browser_name},Desktop,Linux"
        )
        fingerprints_bablosoft_com_responses[browser_name] = res
        logger.info(
            f"updated fingerprints_bablosoft_com_responses[{browser_name}] using fingerprints.bablosoft.com"
        )
    except Exception as exc:
        logger.info(
            f"using cached fingerprints_bablosoft_com_responses[{browser_name}] value"
        )


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
    my_wan_ip = my_wan_ip.get("ip")
    if not my_wan_ip:
        error_msg = "failed to get my_wan_ip via ipify.org"
        logger.info(error_msg)
        raise Exception(error_msg)
    logger.info("got my_wan_ip via ipify.org")
except Exception as exc:
    url = "https://icanhazip.com/"
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            my_wan_ip = resp.text
            logger.info("got my_wan_ip via icanhazip.com")
        else:
            my_wan_ip = None
            logger.info("failed to get my_wan_ip via icanhazip.com")
    except Exception as exc:
        short_exc_name = exc.__class__.__name__
        exc_name = f"{exc.__class__.__module__}.{short_exc_name}"
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"

        my_wan_ip = None
        logger.info(exc_name + f": failed to get my_wan_ip via {url}")
if not my_wan_ip:
    my_wan_ip = "70.123.4.4"
    logger.info(f"got my_wan_ip from hardcoded value: {my_wan_ip}")


async def monkeypatched_check_proxy(self) -> None:
    data = None
    try:
        data = endpoint_query_via_requests(
            url=f"http://ip-api.com/json/{my_wan_ip}",
            retries=3,
            delay=2,
            log_prefix="monkeypatched_check_proxy(): ",
        )
    except Exception as exc:
        pass

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
