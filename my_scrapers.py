import logging
import os
import sys
import time
import traceback

import dateutil.parser
import lxml
import magic

# import trafilatura  # never use; ← it has a dependency conflict with another package over the required version of `charset-normalizer`
import requests
from bs4 import BeautifulSoup
from dateutil.tz import tzutc
from goose3 import Goose
from goose3.crawler import Crawler
from goose3.extractors.publishdate import TIMEZONE_INFO

import aws_utils
import config
import retrieve_by_url
import text_utils
import time_utils
import url_utils
from my_exceptions import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# def monkeypatched_publish_date_to_utc(self):
#     try:
#         publish_datetime = dateutil.parser.parse(
#             self.article.publish_date, tzinfos=TIMEZONE_INFO
#         )
#         if publish_datetime.tzinfo:
#             return publish_datetime.astimezone(tzutc())
#         else:
#             return publish_datetime
#     except (ValueError, OverflowError):
#         logger.warning(
#             f"Publish date {self.article.publish_date} could not be resolved to UTC (monkeypatched_publish_date_to_utc)"
#         )
#         return None


# Crawler._publish_date_to_utc = monkeypatched_publish_date_to_utc


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

    if isinstance(exc, requests.exceptions.ReadTimeout):
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


def download_og_image(story_object, alt_url=None):
    log_prefix_id = f"id {story_object.id}: "
    log_prefix_local = log_prefix_id + f"d_og_i(): "

    # if no URL, no thumbnail
    if not story_object.linked_url_og_image_url_initial and not alt_url:
        logger.info(
            log_prefix_local + "no linked_url_og_image_url_initial or alt_url provided"
        )
        return False

    if alt_url:
        url_to_use = alt_url
    else:
        url_to_use = story_object.linked_url_og_image_url_initial

    get_response = None
    try:
        with requests.get(
            url=url_to_use,
            allow_redirects=True,
            verify=False,
            timeout=config.settings["SCRAPING"]["REQUESTS_GET_TIMEOUT_S"],
            headers={"User-Agent": config.settings["SCRAPING"]["UA_STR"]},
        ) as response:
            get_response = response
            story_object.linked_url_og_image_url_final = get_response.url

    # except requests.exceptions.ConnectTimeout as exc:
    #     handle_exception(exc=exc, log_prefix=log_prefix_local + "get(): ")
    #     return False

    # except requests.exceptions.HTTPError as exc:
    #     handle_exception(exc=exc, log_prefix=log_prefix_local + "get(): ")
    #     return False

    except requests.exceptions.MissingSchema as exc:
        exc_name = exc.__class__.__name__
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"

        if (
            story_object.linked_url_og_image_url_initial[0:2] == "//"
            and story_object.linked_url_og_image_url_initial[2:3] != "/"
        ):
            possibly_fixed_url = f"http://{story_object.hostname['minus_www']}/{story_object.linked_url_og_image_url_initial[2:]}"
            logger.info(
                log_prefix_local
                + "get(): "
                + f"attempting to heal and retry schemeless og:image URL {story_object.linked_url_og_image_url_initial} as {possibly_fixed_url}"
            )
            return download_og_image(story_object, alt_url=possibly_fixed_url)
        elif (
            story_object.linked_url_og_image_url_initial[0:1] == "/"
            and story_object.linked_url_og_image_url_initial[1:2] != "/"
        ):
            possibly_fixed_url = f"http://{story_object.hostname['minus_www']}/{story_object.linked_url_og_image_url_initial[1:]}"
            logger.info(
                log_prefix_local
                + "get(): "
                + f"attempting to heal and retry schemeless og:image URL {story_object.linked_url_og_image_url_initial} as {possibly_fixed_url}"
            )
            return download_og_image(story_object, alt_url=possibly_fixed_url)
        else:
            logger.info(log_prefix_local + "get(): " + "failed to get og:image")
            logger.info(log_prefix_local + "get(): " + exc_slug)
            tb_str = traceback.format_exc()
            logger.info(log_prefix_local + "get(): " + tb_str)
            story_object.linked_url_og_image_url_initial = ""
            story_object.linked_url_og_image_url_final = ""
            return False

    except Exception as exc:
        handle_exception(
            exc=exc,
            log_prefix=log_prefix_local + "get(): ",
            context={"url": url_to_use},
        )
        return False

    if not get_response or not story_object.linked_url_og_image_url_final:
        # I think we won't enter this block, because an exception would have occurred to cause this situation
        logger.error(
            log_prefix_local
            + "no get_response or linked_url_og_image_url_final (~Tim~)"
        )
        return False

    story_object.og_image_filename_details_from_url = (
        url_utils.get_filename_details_from_url(
            story_object.linked_url_og_image_url_final
        )
    )

    # get server-reported content type for og:image
    if story_object.linked_url_og_image_url_final:
        url_to_use = story_object.linked_url_og_image_url_final
    elif story_object.linked_url_og_image_url_initial:
        url_to_use = story_object.linked_url_og_image_url_initial
    story_object.og_image_content_type = get_content_type_via_head_request(
        url=url_to_use, log_prefix=log_prefix_local
    )
    if story_object.og_image_content_type:
        logger.info(
            log_prefix_id
            + f"content-type is {story_object.og_image_content_type}"
            + f" for og:image uri {story_object.linked_url_og_image_url_final}"
        )
    else:
        logger.info(
            log_prefix_id
            + f"content-type unavailable for og:image uri {story_object.linked_url_og_image_url_final}"
        )

    # download og:image
    story_object.normalized_og_image_filename = f"orig-{story_object.id}"
    story_object.downloaded_orig_thumb_full_path = os.path.join(
        config.settings["TEMP_DIR"],
        story_object.normalized_og_image_filename,
    )
    with open(story_object.downloaded_orig_thumb_full_path, "wb") as fout:
        fout.write(get_response.content)
    # logger.info(
    #     log_prefix
    #     + f"downloaded og:image {story_object.normalized_og_image_filename}"
    # )

    # determine magic type of downloaded og:image
    story_object.downloaded_og_image_magic_result = magic.from_file(
        story_object.downloaded_orig_thumb_full_path, mime=True
    )
    # logger.info(
    #     log_prefix
    #     + f"downloaded og:image file has magic type {story_object.downloaded_og_image_magic_result}"
    # )

    logger.info(
        log_prefix_id
        + f"magic type is {story_object.downloaded_og_image_magic_result}"
        + f" for downloaded og:image"
    )

    if alt_url:
        if (
            story_object.downloaded_og_image_magic_result.startswith("image/")
            or story_object.downloaded_og_image_magic_result == "application/pdf"
        ):
            logger.info(
                log_prefix_id
                + f"successfully healed og:image URL {story_object.linked_url_og_image_url_initial} to {alt_url}"
            )
            return True
        else:
            logger.info(
                log_prefix_id
                + f"og:image URL {story_object.linked_url_og_image_url_initial} seemed healed to {alt_url}, but downloaded og:image has magic type {story_object.downloaded_og_image_magic_result}"
            )
            story_object.reason_for_no_thumb = f"ignore og:image with content type {story_object.downloaded_og_image_magic_result}"
            return False

    return True


def get_content_type_via_head_request(url: str = None, log_prefix=""):
    if not url:
        raise Exception("no URL provided")

    headers = None
    try:
        headers = url_utils.head_request(url, log_prefix=log_prefix)
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


def get_reading_time_via_goose(page_source=None, log_prefix=""):
    log_prefix += "grt_via_g(): "

    try:
        if not page_source:
            logger.error(log_prefix + "page_source required")
            return None
        reading_time = None
        g = Goose()
        article = g.extract(raw_html=page_source).cleaned_text
        if article:
            reading_time = int(
                text_utils.word_count(article) / config.reading_speed_words_per_minute
            )
        if reading_time:
            reading_time = max(reading_time, 1)
            logger.info(
                log_prefix
                + f"{text_utils.add_singular_plural(reading_time, 'minute', force_int=True)}"
            )
            return reading_time
        else:
            logger.info(log_prefix + "could not determine reading time")
            return None
    except Exception as exc:
        logger.error(
            log_prefix + f"could not determine reading time due to error: {str(exc)}"
        )
        # logger.error(log_prefix + f"{traceback.format_exc()}")
        return None


get_reading_time = get_reading_time_via_goose


def get_roster_for(roster_story_type: str = None, log_prefix=""):
    if roster_story_type in ["active", "classic"]:
        roster = get_roster_via_screen_scraping(
            roster_story_type=roster_story_type, log_prefix=log_prefix
        )
    elif roster_story_type in ["best", "new", "top"]:
        try:
            roster = get_roster_via_endpoint(roster_story_type, log_prefix=log_prefix)
        except Exception as exc:
            raise exc
    else:
        raise Exception(
            log_prefix
            + f"Error: cannot get a roster for unrecognized story type {roster_story_type}"
        )
    return roster


def get_roster_via_endpoint(story_type: str, log_prefix=""):
    query = f"/v0/{story_type}stories.json"
    return retrieve_by_url.firebaseio_endpoint_query(query=query, log_prefix=log_prefix)

    url = "https://hacker-news.firebaseio.com" + query

    try:
        resp_as_json = retrieve_by_url.endpoint_query_via_requests(url)
    except requests.exceptions.ConnectionError as exc:
        logger.error(f"firebaseio.com actively refused query {query}: {exc}")
        raise
    except requests.exceptions.RequestException as exc:
        logger.warning(f"GET request failed for firebaseio.com query {query}: {exc}")
        time.sleep(
            int(config.settings["SCRAPING"]["FIREBASEIO_RETRY_DELAY"])
        )  # in case it's a transient error, such as a DNS issue, wait for some seconds
        raise
    except Exception as exc:
        logger.error(f"firebaseio.com somehow failed for query {query}: {exc}")
        raise

    return resp_as_json


def get_roster_via_screen_scraping(roster_story_type: str = None, log_prefix=""):
    log_prefix += "get_roster_via_screen_scraping(): "
    if roster_story_type not in ["active", "classic"]:
        raise Exception(
            log_prefix
            + f"cannot create a roster for unrecognized story type '{roster_story_type}'"
        )

    prev_roster_as_dict = None
    try:
        prev_roster_as_dict = aws_utils.get_json_from_s3_as_dict(
            f"rosters/{roster_story_type}_roster.json"
        )
        if prev_roster_as_dict:
            prev_time = prev_roster_as_dict["time_retrieved"]
            cur_time = time_utils.get_time_now_in_epoch_seconds_int()
            roster_age_seconds = cur_time - prev_time
            if 0 < roster_age_seconds < 2 * time_utils.SECONDS_PER_HOUR:
                if prev_roster_as_dict["story_ids"]:
                    logger.info(
                        log_prefix
                        + f"reusing old '{roster_story_type}' roster with length {len(prev_roster_as_dict['story_ids'])} since it's still recent"
                    )
                    return prev_roster_as_dict["story_ids"]
            else:
                logger.info(
                    log_prefix + f"previous '{roster_story_type}' roster is too old"
                )
        else:
            logger.info(
                log_prefix
                + f"previous '{roster_story_type}' roster doesn't seem to exist"
            )

    except CouldNotGetObjectFromS3Error as exc:
        logger.warning(log_prefix + f"{str(exc)}")
        raise

    # invariant now: prev_roster_as_dict is None, or else prev_roster_as_dict["story_ids"] data is more than 2 hours old

    cur_page = 1
    tries_left = 3
    cur_roster = []

    try:
        while True:
            url = f"https://news.ycombinator.com/{roster_story_type}?p={str(cur_page)}"

            try:
                page_source = retrieve_by_url.get_page_source(url=url, log_prefix="")
            except FailedAfterRetrying as exc:
                break

            if page_source:
                soup = BeautifulSoup(page_source, "lxml")

                tr_els = soup.find_all(name="tr", class_="athing")

                if not tr_els:
                    tries_left -= 1
                    if tries_left == 0:
                        break
                    else:
                        continue

                for row in tr_els:
                    cur_roster.append(int(row["id"]))

                cur_page += 1

            else:
                tries_left -= 1
                if tries_left == 0:
                    break
                else:
                    time.sleep(4)  # courtesy pause between scrape attempts
                    continue

    except Exception as exc:
        logger.error(f"Error during while loop: {str(exc)}")
        logger.error(traceback.format_exc())

    if not cur_roster:
        if prev_roster_as_dict:
            logger.info(
                log_prefix
                + f"reusing previous '{roster_story_type}' roster since new roster couldn't be scraped"
            )
            return prev_roster_as_dict["story_ids"]
        else:
            logger.info(
                log_prefix
                + f"no previous '{roster_story_type}' roster, and no current roster either"
            )
            return []

    new_roster = {}
    new_roster["story_type"] = roster_story_type
    new_roster["time_retrieved"] = time_utils.get_time_now_in_epoch_seconds_int()
    new_roster["story_ids"] = cur_roster
    aws_utils.upload_roster_to_s3(
        roster_dict=new_roster,
        roster_dest_fullpath=f"rosters/{roster_story_type}_roster.json",
    )

    logger.info(
        log_prefix
        + f"populated a fresh '{roster_story_type}' roster with length {len(cur_roster)}"
    )
    return cur_roster
