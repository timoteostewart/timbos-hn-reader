import logging
import os
import time
import traceback

import magic
import requests
from bs4 import BeautifulSoup

import config
import utils_aws
import utils_http
import utils_text
import utils_time
from thnr_exceptions import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def download_og_image2(story_object, first_time=True, url_queue=None):
    log_prefix_id = f"id {story_object.id}: "
    log_prefix_local = log_prefix_id + f"d_og_i2(): "

    if first_time:
        url_queue = []
        if story_object.linked_url_og_image_url_initial:
            url_queue.append(story_object.linked_url_og_image_url_initial)

    if not url_queue:
        logger.info(log_prefix_local + "failed to download og:image")
        return False

    cur_url = url_queue.pop(0)

    ## attempt to heal a few common URL problems

    # TODO: eventually move these validations and healings to a separate function

    # problems where the URLs start with two slashes
    if cur_url[0:2] == "//" and cur_url[2:3] != "/":
        pass

        # URL starts with two slashes and then the host
        # //example.com/images/foo.jpg
        # //example.com

        # URL starts with two slashes and then the path
        # //images/foo.jpg
        # //images

    # problems where the URLs start with one slash
    elif cur_url[0:1] == "/" and cur_url[1:2] != "/":
        pass

        # URL starts with one slash and then the host (the slash is a malformed scheme separator)
        # /example.com/images/foo.jpg

        # URL starts with one slash and then the path
        # /images/foo.jpg

    elif not cur_url.startswith("http://") and not cur_url.startswith("https://"):
        pass

        # URL starts with the host
        # example.com/images/foo.jpg

        # URL starts with the path but without the initial path separator (i.e., the root slash)
        # images/foo.jpg

        # idea: try adding "http://" and "https://" and trying to reach them to see if it works

    # URL is any of various localhost development URLs
    elif cur_url[:15] in [
        "http://localhos",
        "https://localho",
        "http://192.168.",
        "https://192.168",
        "http://127.0.0.",
        "https://127.0.0",
    ]:
        localhost_url = cur_url
        healed_url = utils_text.heal_localhost_url(
            localhost_url=localhost_url,
            real_hostname=story_object.hostname["full"],
        )

        story_object.linked_url_og_image_url_initial = healed_url
        cur_url = healed_url
        logger.info(
            log_prefix_local
            + f"healed localhost og:image URL {localhost_url} to {healed_url} (~Tim~)"
        )

    # by now, we have somewhat validated and possibly healed the URL

    get_response = None
    try:
        with requests.get(
            url=cur_url,
            allow_redirects=True,
            verify=False,
            timeout=config.settings["SCRAPING"]["REQUESTS_GET_TIMEOUT_S"],
            headers={"User-Agent": config.settings["SCRAPING"]["UA_STR"]},
        ) as response:
            get_response = response
            possibly_redirected_url = get_response.url

    except requests.exceptions.MissingSchema as exc:
        short_exc_name = exc.__class__.__name__
        exc_name = exc.__class__.__module__ + "." + short_exc_name
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        tb_str = traceback.format_exc()
        logger.error(
            log_prefix_local
            + "unexpected exception "
            + exc_slug
            + f" for url {cur_url}"
        )
        logger.error(log_prefix_local + tb_str)
        return False

    except Exception as exc:
        handle_exception(
            exc=exc,
            log_prefix=log_prefix_local + "get(): ",
            context={"url": cur_url},
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
        utils_text.get_filename_details_from_url(
            story_object.linked_url_og_image_url_final
        )
    )

    story_object.og_image_content_type = utils_http.get_content_type_via_head_request(
        url=possibly_redirected_url, log_prefix=log_prefix_local
    )
    if story_object.og_image_content_type:
        logger.info(
            log_prefix_id
            + f"content-type is {story_object.og_image_content_type}"
            + f" for og:image uri {possibly_redirected_url}"
        )
    else:
        logger.info(
            log_prefix_id
            + f"content-type unavailable for og:image uri {possibly_redirected_url}"
        )

    # download og:image
    story_object.normalized_og_image_filename = f"orig-{story_object.id}"
    story_object.downloaded_orig_thumb_full_path = os.path.join(
        config.settings["TEMP_DIR"],
        story_object.normalized_og_image_filename,
    )
    with open(story_object.downloaded_orig_thumb_full_path, "wb") as fout:
        fout.write(get_response.content)

    # determine magic type of downloaded og:image
    story_object.downloaded_og_image_magic_result = magic.from_file(
        story_object.downloaded_orig_thumb_full_path, mime=True
    )

    logger.info(
        log_prefix_id
        + f"magic type is {story_object.downloaded_og_image_magic_result}"
        + f" for downloaded og:image"
    )

    return True


def download_og_image(story_object, alt_url=None, use_url_queue=False, url_queue=None):
    log_prefix_id = f"id {story_object.id}: "
    log_prefix_local = log_prefix_id + f"d_og_i(): "

    # TODO: 2024-02-02T05:44:23Z [new]     INFO     id 39219609: asdfft1(): found og:image url http://localhost:3000/opengraph-image.jpeg?6a9141518aeca0a0

    if not use_url_queue:
        url_queue = []
        if story_object.linked_url_og_image_url_initial:
            url_queue.append(story_object.linked_url_og_image_url_initial)

    if not url_queue:
        logger.info(log_prefix_local + "failed to download og:image")
        return False

    cur_url = url_queue.pop(0)

    ## attempt to heal a few common URL problems

    # URL is missing a scheme
    # example.com/images/foo.jpg

    # URL is missing a scheme and starts with two slashes
    # //example.com/images/foo.jpg
    # if cur_url[0:2] == "//":
    #     schemeless_url = cur_url
    #     healed_url = utils_text.heal_schemeless_url(
    #         schemeless_url=schemeless_url,
    #         real_scheme="https",
    #     )

    #     story_object.linked_url_og_image_url_initial = healed_url
    #     cur_url = healed_url
    #     logger.info(
    #         log_prefix_local
    #         + f"healed schemeless og:image URL {schemeless_url} to {healed_url} (~Tim~)"
    #     )

    # URL is missing a scheme and hostname and starts with one slash
    # /images/foo.jpg

    # URL is a dev URL using localhost
    if cur_url[:16] in [
        "http://localhost",
        "https://localhos",
    ]:
        localhost_url = cur_url
        possibly_healed_url = utils_text.heal_localhost_url(
            localhost_url=localhost_url,
            real_hostname=story_object.hostname["full"],
        )

        story_object.linked_url_og_image_url_initial = possibly_healed_url
        cur_url = possibly_healed_url
        logger.info(
            log_prefix_local
            + f"healed localhost og:image URL {localhost_url} to {possibly_healed_url} (~Tim~)"
        )

    if alt_url:
        url_to_use = alt_url
    else:
        url_to_use = cur_url

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

    except requests.exceptions.MissingSchema as exc:
        short_exc_name = exc.__class__.__name__
        exc_name = f"{exc.__class__.__module__}.{short_exc_name}"
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"

        if cur_url[0:2] == "//" and cur_url[2:3] != "/":
            possibly_healed_url = (
                f"http://{story_object.hostname['minus_www']}/{cur_url[2:]}"
            )
            logger.info(
                log_prefix_local
                + "get(): "
                + f"attempting to heal and retry schemeless og:image URL {cur_url} as {possibly_healed_url}"
            )
            return download_og_image(story_object, alt_url=possibly_healed_url)

        elif cur_url[0:1] == "/" and cur_url[1:2] != "/":
            possibly_healed_url = (
                f"http://{story_object.hostname['minus_www']}/{cur_url[1:]}"
            )
            logger.info(
                log_prefix_local
                + "get(): "
                + f"attempting to heal and retry schemeless og:image URL {cur_url} as {possibly_healed_url}"
            )
            return download_og_image(story_object, alt_url=possibly_healed_url)

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
        utils_text.get_filename_details_from_url(
            story_object.linked_url_og_image_url_final
        )
    )

    # get server-reported content type for og:image
    if story_object.linked_url_og_image_url_final:
        url_to_use = story_object.linked_url_og_image_url_final
    elif story_object.linked_url_og_image_url_initial:
        url_to_use = story_object.linked_url_og_image_url_initial
    story_object.og_image_content_type = utils_http.get_content_type_via_head_request(
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


def get_roster_for_story_type(roster_story_type: str = None, log_prefix=""):
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
    return utils_http.firebaseio_endpoint_query(query=query, log_prefix=log_prefix)


def get_roster_via_screen_scraping(roster_story_type: str = None, log_prefix=""):
    log_prefix += "get_roster_via_screen_scraping(): "
    if roster_story_type not in ["active", "classic"]:
        raise Exception(
            log_prefix
            + f"cannot create a roster for unrecognized story type '{roster_story_type}'"
        )

    prev_roster_as_dict = None
    try:
        prev_roster_as_dict = utils_aws.get_json_from_s3_as_dict(
            f"rosters/{roster_story_type}_roster.json"
        )
        if prev_roster_as_dict:
            prev_time = prev_roster_as_dict["time_retrieved"]
            cur_time = utils_time.get_time_now_in_epoch_seconds_int()
            roster_age_seconds = cur_time - prev_time
            if 0 < roster_age_seconds < 2 * utils_time.SECONDS_PER_HOUR:
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
                page_source = utils_http.get_page_source(url=url, log_prefix="")
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
    new_roster["time_retrieved"] = utils_time.get_time_now_in_epoch_seconds_int()
    new_roster["story_ids"] = cur_roster
    utils_aws.upload_roster_to_s3(
        roster_dict=new_roster,
        roster_dest_fullpath=f"rosters/{roster_story_type}_roster.json",
    )

    logger.info(
        log_prefix
        + f"populated a fresh '{roster_story_type}' roster with length {len(cur_roster)}"
    )
    return cur_roster


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
