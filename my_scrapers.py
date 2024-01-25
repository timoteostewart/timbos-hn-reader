import logging
import os
import sys
import time

import magic

# import trafilatura  # never use; ← it has a dependency conflict with another package over the required version of `charset-normalizer`
import requests
from bs4 import BeautifulSoup
from goose3 import Goose

import aws_utils
import config
import retrieve_by_url
import text_utils
import time_utils
import url_utils
from my_exceptions import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def download_og_image(story_as_object, alt_url=None):
    # guard
    if not story_as_object.linked_url_og_image_url_initial:
        return False

    if alt_url:
        story_as_object.linked_url_og_image_url_initial = alt_url

    try:
        with requests.get(
            url=story_as_object.linked_url_og_image_url_initial,
            allow_redirects=True,
            verify=False,
            timeout=config.settings["SCRAPING"]["REQUESTS_GET_TIMEOUT_S"],
            headers={"User-Agent": config.settings["SCRAPING"]["UA_STR"]},
        ) as response:
            story_as_object.linked_url_og_image_url_final = response.url

            # if story_as_object.linked_url_og_image_url_final:
            #     while "//" in story_as_object.linked_url_og_image_url_final:
            #         story_as_object.linked_url_og_image_url_final = (
            #             story_as_object.linked_url_og_image_url_final.replace("//", "/")
            #         )

            story_as_object.og_image_filename_details_from_url = (
                url_utils.get_filename_details_from_url(
                    story_as_object.linked_url_og_image_url_final
                )
            )

            # get server-reported content type for og:image
            story_as_object.og_image_content_type = get_content_type_via_head_request(
                story_as_object.linked_url_og_image_url_final
            )
            if not story_as_object.og_image_content_type:
                logger.warning(
                    f"id {story_as_object.id}: no content-type header provided for {story_as_object.linked_url_og_image_url_final}"
                )

            # download og:image
            story_as_object.normalized_og_image_filename = f"orig-{story_as_object.id}"
            story_as_object.downloaded_orig_thumb_full_path = os.path.join(
                config.settings["TEMP_DIR"],
                story_as_object.normalized_og_image_filename,
            )
            with open(story_as_object.downloaded_orig_thumb_full_path, "wb") as fout:
                fout.write(response.content)
            # logger.info(
            #     f"id {story_as_object.id}: download_og_image(): downloaded og:image {story_as_object.normalized_og_image_filename}"
            # )

            # determine magic type of downloaded og:image
            story_as_object.downloaded_og_image_magic_result = magic.from_file(
                story_as_object.downloaded_orig_thumb_full_path, mime=True
            )
            logger.info(
                f"id {story_as_object.id}: downloaded og:image file has magic type {story_as_object.downloaded_og_image_magic_result}"
            )

            if story_as_object.downloaded_og_image_magic_result.startswith("image/"):
                if alt_url:
                    logger.info(
                        f"id {story_as_object.id}: healed og:image URL {story_as_object.linked_url_og_image_url_initial} to {story_as_object.linked_url_og_image_url_final}"
                    )
                return True
            elif story_as_object.downloaded_og_image_magic_result == "application/pdf":
                logger.info(
                    f"id {story_as_object.id}: healed og:image URL {story_as_object.linked_url_og_image_url_initial} to {story_as_object.linked_url_og_image_url_final}"
                )

                return True
            else:
                logger.info(
                    f"id {story_as_object.id}: failed to heal og:image URL {story_as_object.linked_url_og_image_url_initial}"
                )

                return False
    except requests.exceptions.MissingSchema as e:
        if (
            story_as_object.linked_url_og_image_url_initial[0:2] == "//"
            and story_as_object.linked_url_og_image_url_initial[2:3] != "/"
        ):
            possibly_fixed_url = f"http://{story_as_object.hostname['minus_www']}/{story_as_object.linked_url_og_image_url_initial[2:]}"
            logger.info(
                f"id {story_as_object.id}: attempting to heal and retry schemeless og:image URL {story_as_object.linked_url_og_image_url_initial} as {possibly_fixed_url}"
            )
            return download_og_image(story_as_object, alt_url=possibly_fixed_url)
        elif (
            story_as_object.linked_url_og_image_url_initial[0:1] == "/"
            and story_as_object.linked_url_og_image_url_initial[1:2] != "/"
        ):
            possibly_fixed_url = f"http://{story_as_object.hostname['minus_www']}/{story_as_object.linked_url_og_image_url_initial[1:]}"
            logger.info(
                f"id {story_as_object.id}: attempting to heal and retry schemeless og:image URL {story_as_object.linked_url_og_image_url_initial} as {possibly_fixed_url}"
            )
            return download_og_image(story_as_object, alt_url=possibly_fixed_url)
        else:
            logger.info(f"id {story_as_object.id}: failed to get og:image")
            story_as_object.linked_url_og_image_url_initial = ""
            story_as_object.linked_url_og_image_url_final = ""
            return False
    except Exception as e:
        if "No scheme supplied." in str(e):
            if (
                story_as_object.linked_url_og_image_url_initial[0:2] == "//"
                and story_as_object.linked_url_og_image_url_initial[2:3] != "/"
            ):
                possibly_fixed_url = f"http://{story_as_object.hostname['minus_www']}/{story_as_object.linked_url_og_image_url_initial[2:]}"
                logger.info(
                    f"id {story_as_object.id}: attempting to heal and retry schemeless og:image URL"
                )
                return download_og_image(story_as_object, alt_url=possibly_fixed_url)
            elif (
                story_as_object.linked_url_og_image_url_initial[0:1] == "/"
                and story_as_object.linked_url_og_image_url_initial[1:2] != "/"
            ):
                possibly_fixed_url = f"http://{story_as_object.hostname['minus_www']}/{story_as_object.linked_url_og_image_url_initial[1:]}"
                logger.info(
                    f"id {story_as_object.id}: attempting to heal and retry schemeless og:image URL"
                )
                return download_og_image(story_as_object, alt_url=possibly_fixed_url)
            else:
                logger.info(f"id {story_as_object.id}: failed to get og:image")
                story_as_object.linked_url_og_image_url_initial = ""
                story_as_object.linked_url_og_image_url_final = ""
                return False
        else:
            logger.info(f"id {story_as_object.id}: failed to get og:image")
            story_as_object.linked_url_og_image_url_initial = ""
            story_as_object.linked_url_og_image_url_final = ""
            return False


def get_content_type_via_head_request(url: str):
    try:
        headers = url_utils.get_response_headers(url)
    except Exception as exc:
        logger.error(f"{sys._getframe(  ).f_code.co_name}: {url}: {exc}")
        return ""

    try:
        ct = headers["content-type"]
        ct_vals = ct.split(";")
        for each_val in ct_vals:
            if "charset" in each_val:
                continue
            if "/" in each_val:
                return each_val
        return ""
    except Exception as exc:
        logger.error(f"{sys._getframe(  ).f_code.co_name}: {url}: {exc}")
        return ""


# def get_reading_time(story_as_object, page_source):
#     rt_g = get_reading_time_via_goose(story_as_object, page_source)
#     return rt_g


def get_reading_time_via_goose(story_as_object, page_source):
    reading_time = None
    g = Goose()
    article = g.extract(raw_html=page_source)
    article2 = article.cleaned_text
    if article2:
        wc = text_utils.word_count(article2)
        reading_time = int(wc / config.reading_speed_words_per_minute)
    if reading_time:
        reading_time = max(reading_time, 1)
        logger.info(
            f"id {story_as_object.id}: goose reported reading time of {reading_time} minutes"
        )
        return reading_time
    else:
        logger.info(f"id {story_as_object.id}: goose could not determine reading time")
        return None


get_reading_time = get_reading_time_via_goose


def get_roster_for(roster_story_type: str = None):
    if roster_story_type in ["active", "classic"]:
        roster = get_roster_via_screen_scraping(
            roster_story_type=roster_story_type,
        )
    elif roster_story_type in ["best", "new", "top"]:
        try:
            roster = get_roster_via_endpoint(roster_story_type)
        except Exception as exc:
            raise exc
    else:
        raise Exception(
            f"Error: cannot get a roster for unrecognized story type {roster_story_type}"
        )
    return roster


def get_roster_via_endpoint(story_type: str):
    query = f"/v0/{story_type}stories.json"
    return retrieve_by_url.firebaseio_endpoint_query(query=query)

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


def get_roster_via_screen_scraping(driver=None, roster_story_type: str = None):
    if roster_story_type not in ["active", "classic"]:
        raise Exception(
            f"{sys._getframe(  ).f_code.co_name}: cannot create a roster for unrecognized story type '{roster_story_type}'"
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
                        f"{sys._getframe(  ).f_code.co_name}: reusing old '{roster_story_type}' roster with length {len(prev_roster_as_dict['story_ids'])} since it's still recent"
                    )
                    return prev_roster_as_dict["story_ids"]
            else:
                logger.info(
                    f"{sys._getframe(  ).f_code.co_name}: previous '{roster_story_type}' roster is too old"
                )
        else:
            logger.info(
                f"{sys._getframe(  ).f_code.co_name}: previous '{roster_story_type}' roster doesn't seem to exist"
            )

    except CouldNotGetObjectFromS3Error as exc:
        pass

    # invariant now: prev_roster_as_dict is None, or else prev_roster_as_dict["story_ids"] data is more than 2 hours old

    cur_page = 1
    tries_left = 3
    cur_roster = []

    while True:
        url = f"https://news.ycombinator.com/{roster_story_type}?p={str(cur_page)}"

        try:
            page_source = retrieve_by_url.get_page_source_noproxy(
                # driver=driver,
                url=url,
                log_prefix="",
            )
        except FailedAfterRetrying as exc:
            break

        soup = BeautifulSoup(page_source, "html.parser")

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
        time.sleep(3)  # courtesy pause between scrape attempts

    if not cur_roster:
        if prev_roster_as_dict:
            logger.info(
                f"{sys._getframe(  ).f_code.co_name}: reusing previous '{roster_story_type}' roster since new roster couldn't be scraped"
            )
            return prev_roster_as_dict["story_ids"]
        else:
            logger.info(
                f"{sys._getframe(  ).f_code.co_name}: no previous '{roster_story_type}' roster, and no current roster either"
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
        f"{sys._getframe(  ).f_code.co_name}: populated a fresh '{roster_story_type}' roster with length {len(cur_roster)}"
    )
    return cur_roster
