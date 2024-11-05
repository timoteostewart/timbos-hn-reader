import base64
import concurrent.futures
import json
import logging
import os
import pickle
import re
import time
import traceback
import warnings
from urllib.parse import urlparse

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

import config
import social_media
import thnr_scrapers
import thumbs
import utils_aws
import utils_file
import utils_hash
import utils_http
import utils_mimetypes_magic
import utils_random
import utils_text
import utils_time
from PageOfStories import PageOfStories
from Story import Story
from thnr_exceptions import UnsupportedStoryType

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# quiet bs4since it's chatty
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


badge_codes = {
    "top": {"letter": "T", "sigil": "Ⓣ", "tooltip": "news"},
    "new": {"letter": "N", "sigil": "Ⓝ", "tooltip": "newest"},
    "best": {"letter": "B", "sigil": "Ⓑ", "tooltip": "best"},
    "active": {"letter": "A", "sigil": "Ⓐ", "tooltip": "active"},
    "classic": {"letter": "C", "sigil": "Ⓒ", "tooltip": "classic"},
}


skip_getting_content_type_via_head_request_for_domains = {
    "twitter.com",
    "bloomberg.com",
}

log_levels_to_funcs = {
    logging.INFO: logging.info,
    logging.WARNING: logging.warning,
    logging.ERROR: logging.error,
}


def generic_exception_handler(
    exc: Exception = None,
    include_tb: bool = False,
    log_detail: str = "",
    log_level: int = logging.INFO,
    log_prefix: str = "",
    postscript: str = "",
    raise_after: bool = False,
) -> None:
    log_prefix_local = log_prefix + "generic_exception_handler: "

    if log_detail:
        log_detail += ": "

    if postscript:
        postscript = " " + postscript

    log_func = log_levels_to_funcs[log_level]

    exc_module = exc.__class__.__module__
    exc_name = exc.__class__.__name__
    fq_exc_name = exc_module + "." + exc_name
    exc_msg = str(exc)
    exc_slug = fq_exc_name + ": " + exc_msg
    log_func(log_prefix_local + log_detail + exc_slug + postscript)

    if include_tb:
        tb_str = traceback.format_exc()
        log_func(log_prefix_local + tb_str)

    if raise_after:
        raise exc


def asdfft1(item_id=None, pos_on_page=None):
    log_prefix_id = f"id={item_id}: "
    log_prefix_local = log_prefix_id + "asdfft1: "

    # try:
    #     asdfft2(item_id, pos_on_page)
    # except Exception as exc:
    #     if isinstance(exc, UnsupportedStoryType):
    #         pass
    #     else:
    #         exc_name = exc.__class__.__name__
    #         exc_msg = str(exc)
    #         exc_slug = f"{exc_name}: {exc_msg}"
    #         logger.info(
    #             log_prefix_id + "asdfft2: " + "unexpected exception: " + exc_slug
    #         )
    #         tb_str = traceback.format_exc()
    #         logger.info(log_prefix_id + "asdfft2: " + tb_str)

    story_as_dict = None
    try:
        story_as_dict = query_firebaseio_for_story_data(item_id=item_id)
    except Exception as exc:
        exc_short_name = exc.__class__.__name__
        exc_name = exc.__class__.__module__ + "." + exc_short_name
        exc_msg = str(exc)
        exc_slug = exc_name + ": " + exc_msg
        logger.info(log_prefix_local + exc_slug)
        raise exc

    if not story_as_dict:
        logger.info(
            log_prefix_local + "failed to receive story details from firebaseio.com"
        )
        raise Exception(
            log_prefix_local + "failed to receive story details from firebaseio.com"
        )
    elif story_as_dict["type"] not in ["story", "job"]:
        # TODO: eventually handle poll, etc. other types
        logger.info(log_prefix_local + f"ignoring item of type {story_as_dict['type']}")
        raise UnsupportedStoryType(story_as_dict["type"])

    story_object = item_factory(story_as_dict)

    if not story_object:
        raise Exception(
            log_prefix_local + "item_factory: failed to create story object"
        )

    story_object.time_of_last_firebaseio_query = (
        utils_time.get_time_now_in_epoch_seconds_int()
    )

    if story_object.has_outbound_url:
        # get srct
        domain, domain_minus_www = utils_text.get_domains_from_url(story_object.url)
        if domain in skip_getting_content_type_via_head_request_for_domains:
            logger.info(log_prefix_local + f"skip HEAD request for {domain}")
        elif domain_minus_www in skip_getting_content_type_via_head_request_for_domains:
            logger.info(log_prefix_local + f"skip HEAD request for {domain_minus_www}")
        else:
            story_object.linked_url_reported_content_type = (
                utils_http.get_content_type_via_head_request(
                    url=story_object.url, log_prefix=log_prefix_local
                )
            )

        if (
            story_object.linked_url_reported_content_type
            and "," in story_object.linked_url_reported_content_type
        ):
            types = set(
                [
                    x.strip()
                    for x in story_object.linked_url_reported_content_type.split(",")
                ]
            )
            if len(types) == 1:
                story_object.linked_url_reported_content_type = types.pop()
            else:
                logger.info(
                    log_prefix_local
                    + "srct has multiple values: "
                    + story_object.linked_url_reported_content_type
                    + " ~Tim~"
                )
                if "text/html" in types:
                    story_object.linked_url_reported_content_type = "text/html"
                else:
                    story_object.linked_url_reported_content_type = None

        if (
            story_object.linked_url_reported_content_type == "text/html"
            or story_object.linked_url_reported_content_type == "application/xhtml+xml"
            or not story_object.linked_url_reported_content_type
        ):
            page_source = None
            soup = None

            page_source = utils_http.get_page_source(
                url=story_object.url,
                log_prefix=log_prefix_local,
            )

            if page_source:
                if (
                    story_object.linked_url_reported_content_type
                    == "application/xhtml+xml"
                ):
                    logger.info(log_prefix_local + "using 'lxml-xml' parser")
                    parser_to_use = "lxml-xml"
                else:
                    parser_to_use = "lxml"

                try:
                    soup = BeautifulSoup(page_source, parser_to_use)
                except Exception as exc:
                    generic_exception_handler(
                        exc=exc,
                        include_tb=True,
                        log_detail=f"unexpected problem making soup from {story_object.url}",
                        log_prefix=log_prefix_local,
                        postscript="~Tim~",
                    )

            if not page_source or not soup:
                return story_object

            # invariant now: we have page_source and soup

            # check for og:image
            og_image_url_result = soup.find("meta", {"property": "og:image"})
            if og_image_url_result:
                if og_image_url_result.has_attr("content"):
                    meta_og_image_content = og_image_url_result["content"]

                    if meta_og_image_content.startswith("data:"):
                        # content="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAeUAAACeEAIAAADTU..."

                        first_128 = meta_og_image_content[:128]
                        logger.info(
                            log_prefix_local
                            + f"found og:image inline data: '{first_128}...'"
                        )

                        match = re.match(
                            r"^data: *([a-z]+/[a-z\-\+]+) *; *", meta_og_image_content
                        )
                        if match:
                            story_object.og_image_inline_data_srct = match.group(1)
                            len_match = len(match.group())

                            meta_og_image_content = meta_og_image_content[len_match:]

                            if meta_og_image_content.startswith("base64"):
                                match = re.match(r"^base64 *[;,] *")
                                if match:
                                    len_match = len(match.group())
                                    meta_og_image_content = meta_og_image_content[
                                        len_match:
                                    ]

                                    # using base64, convert meta_og_image_content to binary data and save to a temp file
                                    local_file_with_og_image_inline_data_decoded = (
                                        config.settings["TEMP_DIR"]
                                        + f"og-image-via-inline-data-{story_object.id}"
                                    )
                                    binary_data = base64.b64decode(
                                        meta_og_image_content
                                    )

                                    with open(
                                        local_file_with_og_image_inline_data_decoded,
                                        "wb",
                                    ) as file:
                                        file.write(binary_data)

                                    story_object.og_image_is_inline_data = True
                                    story_object.has_thumb = True  # provisionally

                                    logger.info(
                                        log_prefix_local
                                        + f"saved og:image base64 inline data to {local_file_with_og_image_inline_data_decoded} url={story_object.url} ~Tim~"
                                    )

                                    story_object.og_image_inline_data_decoded_local_path = local_file_with_og_image_inline_data_decoded

                    else:
                        story_object.og_image_url = og_image_url_result["content"]
                        logger.info(
                            log_prefix_local
                            + f"found og:image url {story_object.og_image_url}"
                        )
            else:
                story_object.has_thumb = False
                # TODO: in the absence of an og:image, I could always fall back on a generic banner image for the linked article's website

            # get reading time
            try:
                reading_time = utils_text.get_reading_time(
                    page_source=page_source, log_prefix=log_prefix_id
                )
                if reading_time:
                    story_object.reading_time = reading_time
            except Exception as exc:
                short_exc_name = exc.__class__.__name__
                exc_name = exc.__class__.__module__ + "." + short_exc_name
                exc_msg = str(exc)
                exc_slug = f"{exc_name}: {exc_msg}"
                logger.error(
                    log_prefix_id
                    + "get_reading_time: unexpected exception: "
                    + exc_slug
                )
                tb_str = traceback.format_exc()
                logger.error(log_prefix_id + tb_str)

            ## create a slug for the linked URL's social-media website channel, if necessary.
            ## use details encoded in the url or the html page source
            ## https://hackernews-insight.vercel.app/domain-analysis
            try:
                social_media.check_for_social_media_details(
                    # driver=driver,
                    story_object=story_object,
                    page_source_soup=soup,
                )
            except Exception as exc:
                logger.error(
                    log_prefix_local + f"check_for_social_media_details: {exc}"
                )
                raise exc

        elif story_object.linked_url_reported_content_type.startswith("image/"):
            story_object.og_image_url = story_object.url

        elif story_object.linked_url_reported_content_type == "text/plain":
            # logger.info(
            #     log_prefix_local
            #     + f"creating minimal story card for story '{story_object.title}' at url {story_object.url} because its content-type is text/plain"
            # )

            # create story card with what we have
            populate_story_card_html_in_story_object(story_object)

            # pickle `story_object` as json to a file
            logger.info(log_prefix_local + "saving item to disk for the first time")
            save_story_object_to_disk(
                story_object=story_object, log_prefix=log_prefix_local
            )

            story_object.has_thumb = False

            return story_object

        # if story links to PDF, we'll use 1st page of PDF as thumb instead of og:image (if any)
        elif (
            story_object.linked_url_reported_content_type == "application/pdf"
            or story_object.linked_url_reported_content_type
            == "application/octet-stream"
        ):
            story_object.og_image_url = story_object.url

        else:
            logger.info(
                log_prefix_local
                + f"unexpected srct '{story_object.linked_url_reported_content_type}' for url {story_object.url}"
            )

        if story_object.og_image_url or story_object.og_image_is_inline_data:
            if story_object.og_image_url and thumbs.image_url_is_disqualified(
                url=story_object.og_image_url, log_prefix=log_prefix_local
            ):
                story_object.has_thumb = False
            else:
                d_og_image_res = thnr_scrapers.download_og_image1(story_object)
                if story_object.og_image_url and d_og_image_res:
                    story_object.has_thumb = True  # provisionally
                elif not d_og_image_res:
                    logger.info(log_prefix_local + "failed to download_og_image()")
                    story_object.has_thumb = False

                else:
                    logger.error(
                        log_prefix_local + "unexpected result from download_og_image()"
                    )
                    story_object.has_thumb = False

                if story_object.has_thumb:
                    if pos_on_page < 5:
                        img_loading_attr = "eager"
                    else:
                        img_loading_attr = "lazy"

                    thumbs.populate_image_slug_in_story_object(
                        story_object, img_loading=img_loading_attr
                    )
                    if story_object.has_thumb:
                        story_object.image_slug = thumbs.create_img_slug_html(
                            story_object, img_loading=img_loading_attr
                        )
                        if not story_object.image_slug:
                            story_object.has_thumb = False

        if story_object.has_thumb and story_object.image_slug:
            logger.info(log_prefix_local + "story card will have a thumbnail")

        if story_object.has_thumb and not story_object.image_slug:
            logger.error(
                log_prefix_local
                + "has_thumb is True, but there's no image_slug, so updating as_thumb to False ~Tim~"
            )
            story_object.has_thumb = False

    # apply "[pdf]" label after title if it's not there but is probably applicable
    if (
        story_object.downloaded_og_image_magic_result
        and story_object.downloaded_og_image_magic_result == "application/pdf"
    ):
        if "pdf" not in story_object.title[-12:].lower():
            story_object.story_content_type_slug = (
                ' <span class="story-content-type">[pdf]</span>'
            )
            logger.info(f"id={story_object.id}: added [pdf] label after title")

    return story_object


def asdfft2_preprocess_outbound_link(story_object, log_prefix: str) -> None:
    log_prefix_local = log_prefix + "asdfft2_preprocess_outbound_link: "

    parsed_url = urlparse(story_object.url)

    if (
        parsed_url.netloc.endswith("dropbox.com")
        and parsed_url.path.endswith(".pdf")
        and "dl=0" in parsed_url.query
    ):
        story_object.url = parsed_url._replace(query="dl=1").geturl()
        logger.info(
            log_prefix_local
            + f"changing url from {story_object.url} to {story_object.url}"
        )

    return


generic_binary_mimetypes = set(
    [
        "application/octet-stream",
        "application/data",
        "application/binary",
        "binary/octet",
    ]
)


def asdfft2(item_id=None, pos_on_page=None):
    # asdfft2=acquire story details for first time v2
    log_prefix_id = f"id={item_id}: "
    log_prefix_local = log_prefix_id + "asdfft2: "

    story_as_dict = None
    try:
        story_as_dict = query_firebaseio_for_story_data(item_id=item_id)
    except Exception as exc:
        generic_exception_handler(
            exc=exc,
            include_tb=True,
            log_detail="unexpected problem querying firebaseio",
            log_prefix=log_prefix_local,
            raise_after=True,
        )

    if not story_as_dict:
        logger.info(
            log_prefix_local + "failed to receive story details from firebaseio.com"
        )
        raise Exception("failed to receive story details from firebaseio.com")

    elif story_as_dict["type"] not in ["story", "job", "comment"]:
        # TODO: eventually handle poll, job, etc. other types
        logger.info(
            log_prefix_local
            + f"not processing item of item type {story_as_dict['type']}"
        )
        raise UnsupportedStoryType(story_as_dict["type"])

    story_object = item_factory(story_as_dict)

    if not story_object:
        # we have to give up
        err_msg = "item_factory: failed to create story object"
        logger.error(log_prefix_local + err_msg)
        raise Exception(log_prefix_local + err_msg)

    story_object.time_of_last_firebaseio_query = (
        utils_time.get_time_now_in_epoch_seconds_int()
    )

    if not story_object.has_outbound_url:
        # probably an Ask HN, etc.
        logger.info(log_prefix_local + "story has no outbound url")
        return story_object

    # invariant now: story_object.has_outbound_url == True

    # do some processing of the outbound link in some cases
    # TODO: extract this url processing logic to its own function
    parsed_url = urlparse(story_object.url)
    # dropbox.com
    if (
        parsed_url.netloc.endswith("dropbox.com")
        and parsed_url.path.endswith(".pdf")
        and "dl=0" in parsed_url.query
    ):
        new_url = parsed_url._replace(query="dl=1").geturl()
        logger.info(
            log_prefix_local + f"changing url from {story_object.url} to {new_url}"
        )
        story_object.url = new_url
        parsed_url = urlparse(story_object.url)

    response_objects = {}
    for each_gro_func in [
        utils_http.get_response_object_via_requests,
        utils_http.get_response_object_via_hrequests,
    ]:
        time.sleep(utils_random.random_real(0, 1))
        ro = each_gro_func(url=story_object.url, log_prefix=log_prefix_local)
        if ro:
            response_objects[each_gro_func.__name__] = ro

        else:
            logger.info(
                log_prefix_local
                + f"failed to get response object via {each_gro_func.__name__}"
            )

    if not response_objects:
        logger.info(
            log_prefix_local
            + f"failed to get any response objects for url {story_object.url} ~Tim~"
        )
        # create story card with what little we have
        story_object.has_thumb = False
        populate_story_card_html_in_story_object(story_object)
        logger.info(log_prefix_local + "saving item to disk for the first time")
        save_story_object_to_disk(
            story_object=story_object, log_prefix=log_prefix_local
        )
        return story_object

    # invariant now: we have at least one response object

    # let's download the content and determine its content type
    local_file_with_response_content_prefix = config.settings["TEMP_DIR"] + str(
        story_object.id
    )

    for k, v in response_objects.items():
        utils_file.save_response_content_to_disk(
            response=v,
            dest_local_file=local_file_with_response_content_prefix + "-" + k[4:],
            log_prefix=log_prefix_local,
        )

    # prefer the response object from requests, because the object from hrequests sometimes handles binary files as utf-8 strings
    if "get_response_object_via_requests" in response_objects:
        local_file_with_response_content = (
            local_file_with_response_content_prefix + "-response_object_via_requests"
        )
    else:
        # TODO: we REALLY REALLY don't want to use hrequest's ro, because it sometimes handles binary files as utf-8 strings
        # TODO: use curl or something as a fallback to get the content, in order to avoid using the hrequests ro
        # TODO: or maybe wait 30 seconds and try again to get the content via requests
        local_file_with_response_content = (
            local_file_with_response_content_prefix + "-response_object_via_hrequests"
        )

    textual_mimetype, page_source, is_wellformed_xml = (
        utils_mimetypes_magic.get_textual_mimetype(
            local_file=local_file_with_response_content,
            log_prefix=log_prefix_local,
            context={"url": story_object.url},
        )
    )

    if textual_mimetype:
        content_type_to_use = textual_mimetype
        story_object.is_wellformed_xml = is_wellformed_xml

    else:  # textual_mimetype is None
        # must be binary, so figure out what kind of binary

        # get magic type of the file
        mimetype_via_python_magic = utils_mimetypes_magic.get_mimetype_via_python_magic(
            local_file=local_file_with_response_content,
            log_prefix=log_prefix_local,
        )

        mimetype_via_file_command = utils_mimetypes_magic.get_mimetype_via_file_command(
            local_file=local_file_with_response_content,
            log_prefix=log_prefix_local,
        )

        mimetype_via_exiftool = utils_mimetypes_magic.get_mimetype_via_exiftool2(
            local_file=local_file_with_response_content,
            log_prefix=log_prefix_local,
        )

        content_types_guessed_from_uri_extension = (
            utils_mimetypes_magic.guess_mimetype_from_uri_extension(
                url=story_object.url,
                log_prefix=log_prefix_local,
                context={"url": story_object.url},
            )
        )

        possible_magic_types = []
        if mimetype_via_python_magic:
            possible_magic_types.append(mimetype_via_python_magic)
        if mimetype_via_file_command:
            possible_magic_types.append(mimetype_via_file_command)
        if mimetype_via_exiftool:
            if isinstance(type(mimetype_via_exiftool), str):
                possible_magic_types.append(mimetype_via_exiftool)
            else:
                logger.info(
                    log_prefix_local
                    + f"{mimetype_via_exiftool=}, type(mimetype_via_exiftool)={type(mimetype_via_exiftool)} ~Tim~"
                )

        srct = set(
            x
            for x in [
                get_content_type_from_response(
                    response=v,
                    log_prefix=log_prefix_local,
                    context={
                        "url": story_object.url,
                        "response_object_creator": k,
                    },
                )
                for (k, v) in response_objects.items()
            ]
            if x
        )

        if not srct:
            logger.info(
                log_prefix_local
                + f"failed to get any srct for url={story_object.url} ~Tim~"
            )
            srct = None
        elif len(srct) == 1:
            srct = srct.pop()
        elif len(srct) > 1:
            logger.info(
                log_prefix_local
                + f"multiple srct values: {srct} for url={story_object.url} ~Tim~"
            )
            srct = srct.pop()

        all_values = set()
        all_values.update(content_types_guessed_from_uri_extension)
        all_values.update(possible_magic_types)
        if textual_mimetype:
            all_values.add(textual_mimetype)

        trusted_values = set(
            [
                mimetype_via_python_magic,
                mimetype_via_file_command,
                mimetype_via_exiftool,
            ]
        )

        if srct:
            url_slug = f"for url {story_object.url}"

            all_values.add(srct)
            content_type_to_use = None

            # 1. If all_values has length 1 and this value matches srct, use that:
            if len(all_values) == 1 and srct in all_values:
                content_type_to_use = srct
                logger.info(
                    log_prefix_local
                    + f"{srct=} equals {all_values=} ; {content_type_to_use=} {url_slug}"
                )

            # 2. If srct is a generic binary mimetype and mimetype_via_python_magic, mimetype_via_file_command, mimetype_via_exiftool all agree, use that:
            elif srct in generic_binary_mimetypes:
                if len(trusted_values) == 1:
                    content_type_to_use = trusted_values.pop()
                    logger.info(
                        log_prefix_local
                        + f"generic {srct=}, but {trusted_values=} ; {content_type_to_use=} {url_slug} ~Tim~"
                    )

            # 3. If srct, mimetype_via_python_magic, mimetype_via_file_command, mimetype_via_exiftool all agree, use that:
            elif len(trusted_values) == 1 and srct in trusted_values:
                content_type_to_use = srct
                logger.info(
                    log_prefix_local
                    + f"{srct=} equals {trusted_values=} ; {content_type_to_use=} {url_slug} ~Tim~"
                )

            # 4. If srct matches any value in trusted_values, use that:
            elif srct in trusted_values:
                content_type_to_use = srct
                logger.info(
                    log_prefix_local
                    + f"{srct=} matches any of {trusted_values=} ; {content_type_to_use=} {url_slug} ~Tim~"
                )

            # 5. If srct matches any value in all_values, use that:
            elif srct in all_values:
                content_type_to_use = srct
                logger.info(
                    log_prefix_local
                    + f"{srct=} matches any of {all_values=} ; {content_type_to_use=} {url_slug} ~Tim~"
                )

            # 6. Just use srct
            else:
                content_type_to_use = srct
                logger.info(
                    log_prefix_local
                    + f"{srct=} instead of {all_values=} ; {content_type_to_use=} {url_slug} ~Tim~"
                )

        else:  # srct is None
            # 7. If mimetype_via_python_magic, mimetype_via_file_command, mimetype_via_exiftool all agree, use that:
            if len(trusted_values) == 1:
                content_type_to_use = trusted_values.pop()
                logger.info(
                    log_prefix_local
                    + f"srct=None, but {trusted_values=} ; {content_type_to_use=} {url_slug} ~Tim~"
                )

            # 8. Fall back on generic 'application/octet-stream'
            else:
                content_type_to_use = "application/octet-stream"
                logger.info(
                    log_prefix_local
                    + f"srct=None, and {all_values=} disagree ; {content_type_to_use=} {url_slug} ~Tim~"
                )

        # dismiss some very common mimetypes as not interesting
        uninteresting_mimetypes = [
            "application/pdf",
            "application/xhtml+xml",
            "text/html",
        ]
        copy_of_all_values = set(all_values)
        for each in uninteresting_mimetypes:
            copy_of_all_values.discard(each)

        is_interesting = True

        if not copy_of_all_values:
            is_interesting = False

        if is_interesting:
            copy_of_all_values = list(copy_of_all_values)
            copy_of_all_values.sort()

            logger.info(
                log_prefix_local
                + f"interesting mimetypes from all_values={copy_of_all_values} for url {story_object.url}"
            )

    # invariant now: content_type_to_use != None

    # try make soup from page_source
    if page_source and content_type_to_use in ["text/html", "application/xhtml+xml"]:
        if content_type_to_use.endswith("xml") and story_object.is_wellformed_xml:
            parser_to_use = "lxml-xml"
        else:
            parser_to_use = "lxml"

        try:
            soup = BeautifulSoup(page_source, parser_to_use)
        except Exception as exc:
            generic_exception_handler(
                exc=exc,
                include_tb=True,
                log_detail=f"unexpected problem making soup from {story_object.url}",
                log_prefix=log_prefix_local,
                postscript="~Tim~",
            )

        if not soup:
            return story_object

        # check for og:image
        og_image_url_result = soup.find("meta", {"property": "og:image"})
        if og_image_url_result:
            if og_image_url_result.has_attr("content"):
                meta_og_image_content = og_image_url_result["content"]

                if meta_og_image_content.startswith("data:"):
                    # Example:
                    # <meta property="og:image" content="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAeUAAACeEAIAAADTU...">

                    first_128 = meta_og_image_content[:128]
                    logger.info(
                        log_prefix_local
                        + f"found og:image inline data: '{first_128}...'"
                    )

                    match = re.match(
                        r"^data: *([a-z]+/[a-z\-\+]+) *; *", meta_og_image_content
                    )
                    if match:
                        story_object.og_image_inline_data_srct = match.group(1)
                        len_match = len(match.group())

                        meta_og_image_content = meta_og_image_content[len_match:]

                        if meta_og_image_content.startswith("base64"):
                            match = re.match(r"^base64 *[;,] *")
                            if match:
                                len_match = len(match.group())
                                meta_og_image_content = meta_og_image_content[
                                    len_match:
                                ]

                                # using base64, convert meta_og_image_content to binary data and save to a temp file
                                local_file_with_og_image_inline_data_decoded = (
                                    config.settings["TEMP_DIR"]
                                    + f"og-image-via-inline-data-{story_object.id}"
                                )
                                binary_data = base64.b64decode(meta_og_image_content)

                                with open(
                                    local_file_with_og_image_inline_data_decoded,
                                    "wb",
                                ) as file:
                                    file.write(binary_data)

                                story_object.og_image_is_inline_data = True
                                story_object.has_thumb = True  # provisionally

                                logger.info(
                                    log_prefix_local
                                    + f"saved og:image base64 inline data to {local_file_with_og_image_inline_data_decoded} url={story_object.url} ~Tim~"
                                )

                                story_object.og_image_inline_data_decoded_local_path = (
                                    local_file_with_og_image_inline_data_decoded
                                )

                else:
                    # Example:
                    # <meta property="og:image" content="https://www.esa.int/var/esa/storage/images/esa_multimedia/images/2024/03/webb_hubble_confirm_universe_s_expansion_rate/25971194-1-eng-GB/Webb_Hubble_confirm_Universe_s_expansion_rate_pillars.jpg">
                    story_object.og_image_url = og_image_url_result["content"]
                    logger.info(
                        log_prefix_local
                        + f"found og:image url {story_object.og_image_url}"
                    )
                    story_object.has_thumb = True  # provisionally
        else:
            story_object.has_thumb = False
            # TODO: in the absence of an og:image, I could always fall back on a generic screenshot of the linked article's website

        # get reading time via goose
        try:
            reading_time = utils_text.get_reading_time(
                page_source=page_source, log_prefix=log_prefix_id
            )
            if reading_time:
                story_object.reading_time = reading_time
        except Exception as exc:
            generic_exception_handler(
                exc=exc,
                include_tb=True,
                log_detail="unexpected problem getting reading time",
                log_prefix=log_prefix_local,
                postscript="~Tim~",
            )

        # if domain matches social media sites, check for those details
        try:
            social_media.check_for_social_media_details(
                # driver=driver,
                story_object=story_object,
                page_source_soup=soup,
            )
        except Exception as exc:
            generic_exception_handler(
                exc=exc,
                include_tb=True,
                log_detail="unexpected problem getting social media details",
                log_prefix=log_prefix_local,
                postscript="~Tim~",
                raise_after=True,
            )

    elif content_type_to_use == "application/pdf":
        # use the first page of the PDF as a thumbnail, with dog ear etc.
        story_object.og_image_url = story_object.url

        # apply "[pdf]" label after title if it's not there but is probably applicable
        if "pdf" not in story_object.title[-12:].lower():
            story_object.story_content_type_slug = (
                ' <span class="story-content-type">[pdf]</span>'
            )
            logger.info(log_prefix_local + "added [pdf] label after title")

    elif content_type_to_use.startswith("image/"):
        # use the image at the uri as the thumbnail
        story_object.og_image_url = story_object.url

    elif content_type_to_use.startswith("video/"):
        pass
        # TODO: extract a frame as a screenshot, OR, even better, extract 12 frames and arrange them in a 4x3 grid: 2024-02-13T15:15:56Z [new]     INFO     id 39358138: asdfft1(): unexpected linked url content-type video/mp4 for url https://www.goody2.ai/video/goody2-169.mp4

    if story_object.og_image_url or story_object.og_image_is_inline_data:
        if story_object.og_image_is_inline_data:
            # TODO: implement this
            story_object.has_thumb = False  # since this is a stub

            # if story_object.has_thumb:
            #     if pos_on_page < 5:
            #         img_loading_attr = "eager"
            #     else:
            #         img_loading_attr = "lazy"

            #     thumbs.populate_image_slug_in_story_object(
            #         story_object, img_loading=img_loading_attr
            #     )
            #     if story_object.has_thumb:
            #         story_object.image_slug = thumbs.create_img_slug_html(
            #             story_object, img_loading=img_loading_attr
            #         )
            #         if not story_object.image_slug:
            #             story_object.has_thumb = False

        elif story_object.og_image_url and thumbs.image_url_is_disqualified(
            url=story_object.og_image_url, log_prefix=log_prefix_local
        ):
            story_object.has_thumb = False

        # TODO: the logic around this area can be improved
        if story_object.og_image_url and story_object.has_thumb:
            d_og_image_res = thnr_scrapers.download_og_image1(story_object)
            if story_object.og_image_url and d_og_image_res:
                story_object.has_thumb = True  # provisionally
            elif not d_og_image_res:
                logger.info(log_prefix_local + "failed to download_og_image()")
                story_object.has_thumb = False

            else:
                logger.error(
                    log_prefix_local + "unexpected result from download_og_image()"
                )
                story_object.has_thumb = False

            if story_object.has_thumb:
                if pos_on_page < 5:
                    img_loading_attr = "eager"
                else:
                    img_loading_attr = "lazy"

                thumbs.populate_image_slug_in_story_object(
                    story_object, img_loading=img_loading_attr
                )
                if story_object.has_thumb:
                    story_object.image_slug = thumbs.create_img_slug_html(
                        story_object, img_loading=img_loading_attr
                    )
                    if not story_object.image_slug:
                        story_object.has_thumb = False

    if story_object.has_thumb and story_object.image_slug:
        logger.info(log_prefix_local + "story card will have a thumbnail")

    if story_object.has_thumb and not story_object.image_slug:
        logger.error(
            log_prefix_local
            + "has_thumb is True, but there's no image_slug, so updating as_thumb to False ~Tim~"
        )
        story_object.has_thumb = False

    if not story_object.has_thumb:
        logger.info(log_prefix_local + "story card will not have a thumbnail")

    # return story_object
    return story_object


def choose_best_page_source(
    page_source_via_get, page_source_via_render, url, log_prefix=""
):
    log_prefix_local = log_prefix + "choose_best_page_source: "
    empty_page_source = "<html><head></head><body></body></html>"
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


def create_badges_slug(story_id, story_type, rosters):
    if story_type not in badge_codes:
        raise Exception(
            f"cannot create badge for unrecognized story_type {story_type} for story_id={story_id}"
        )
    own_badge = badge_codes[story_type]["letter"]

    badges = ""  # reset badge string
    if story_id in rosters["top"] and own_badge != "T":
        badges += "T"
    if story_id in rosters["new"] and own_badge != "N":
        badges += "N"
    if story_id in rosters["best"] and own_badge != "B":
        badges += "B"
    if story_id in rosters["active"] and own_badge != "A":
        badges += "A"
    if story_id in rosters["classic"] and own_badge != "C":
        badges += "C"

    if badges:
        # Ⓣ Ⓝ Ⓑ Ⓐ Ⓒ
        list_of_badges = []
        for each_story_type in ["top", "new", "best", "active", "classic"]:
            if badge_codes[each_story_type]["letter"] in badges:
                list_of_badges.append(
                    f'<div class="{each_story_type}-badge" title="This story is currently on /{badge_codes[each_story_type]["tooltip"]}.">{badge_codes[each_story_type]["sigil"]}</div>'
                )
        list_of_badges[-1] = list_of_badges[-1].replace(
            'class="', 'class="final-badge '
        )
        return '<div class="badges-tray">' + "".join(list_of_badges) + "</div>"
    else:
        return ""


def freshen_up(story_object=None, page_package=None):
    log_prefix_local = f"id={story_object.id}: "

    # by freshen up, we mean: update title, score, comment count

    try:
        updated_story_data_as_dict = query_firebaseio_for_story_data(
            item_id=story_object.id
        )
    except Exception as exc:
        logger.info(
            log_prefix_local
            + f"freshen_up: query to hacker-news.firebaseio.com failed for story id={story_object.id} ; so re-using old story details"
        )
        raise Exception("failed to freshen story: " + exc)

    if not updated_story_data_as_dict:
        logger.info(
            log_prefix_local
            + f"freshen_up: query to hacker-news.firebaseio.com failed for story id={story_object.id} ; so re-using old story details"
        )
        raise Exception("failed to freshen story")

    story_object.time_of_last_firebaseio_query = (
        utils_time.get_time_now_in_epoch_seconds_int()
    )

    # update title if needed
    if "title" in updated_story_data_as_dict:
        old_title = story_object.title
        new_title = updated_story_data_as_dict["title"]

        if old_title != new_title:
            story_object.title = new_title
            logger.info(
                log_prefix_local + f"updated title from '{old_title}' to '{new_title}'"
            )

            if (
                story_object.downloaded_og_image_magic_result == "application/pdf"
                and "pdf" in story_object.title[-12:].lower()
                and story_object.story_content_type_slug
                == ' <span class="story-content-type">[pdf]</span>'
            ):
                story_object.story_content_type_slug = ""
                logger.info(
                    f"id={story_object.id}: removed [pdf] label after title ~Tim~"
                )

    else:
        logger.info(
            log_prefix_local
            + "no key for 'title' in updated_story_data_as_dict (story is probably dead)"
        )

    # update URL if necessary
    if "url" in updated_story_data_as_dict:
        old_url = story_object.url
        new_url = updated_story_data_as_dict["url"]
        if old_url != new_url:
            story_object.url = new_url
            story_object.title_hyperlink = story_object.url
            logger.info(log_prefix_local + f"updated url from {old_url} to {new_url}")

    # update score if needed
    if "score" in updated_story_data_as_dict:
        old_score = story_object.score
        new_score = updated_story_data_as_dict["score"]
        if old_score != new_score:
            story_object.score = new_score
            logger.info(
                log_prefix_local + f"updated score from {old_score} to {new_score}"
            )
    else:
        logger.info(
            log_prefix_local + "no key for 'score' in updated_story_data_as_dict"
        )

    # update comment count (i.e., "descendants") if needed
    if "descendants" in updated_story_data_as_dict:
        old_descendants = story_object.descendants
        new_descendants = updated_story_data_as_dict["descendants"]
        if old_descendants != new_descendants:
            story_object.descendants = new_descendants
            logger.info(
                log_prefix_local
                + f"updated comment count from {old_descendants} to {new_descendants}"
            )
    else:
        if (
            "type" in updated_story_data_as_dict
            and updated_story_data_as_dict["type"] == "job"
        ):
            pass
        else:
            logger.info(
                log_prefix_local
                + "no key for 'descendants' in non-job-story updated_story_data_as_dict"
            )


def get_content_type_from_response(response, log_prefix="", context=None):
    if response and "Content-Type" in response.headers:
        if context:
            context.update({"url": response.url})
        else:
            context = {"url": response.url}
        return utils_text.parse_content_type_from_raw_header(
            response.headers["Content-Type"],
            log_prefix=log_prefix,
            context=context,
        )

    return None


def get_html_page_filename(story_type: str, page_number: int, light_mode: bool):
    if light_mode:
        return f"{story_type}_stories_page_{page_number}_lm.html"
    else:
        return f"{story_type}_stories_page_{page_number}_dm.html"


def get_pickle_filename(id):
    return f"id-{id}.pickle"


def get_story_page_url(story_type, page_num, light_mode=True, from_other_mode=False):
    url = None
    if config.settings["cur_host"] in ["tsio", "thnr-home-arpa", "thnr", "owl"]:
        url = f"./{get_html_page_filename(story_type, page_num, light_mode=light_mode)}"
    else:
        raise Exception(f"host name {config.settings['cur_host']} is not supported")

    return url


def item_factory(story_as_dict):
    if "type" not in story_as_dict:
        story_as_dict["type"] = "story"

    if story_as_dict["type"] == "story":
        # check for incomplete metadata and assign default values
        if "by" not in story_as_dict:
            story_as_dict["by"] = "(no author)"
        if "descendants" not in story_as_dict:
            story_as_dict["descendants"] = 0
        if "id" not in story_as_dict:
            story_as_dict["id"] = -1
        if "kids" not in story_as_dict:
            story_as_dict["kids"] = []
        if "score" not in story_as_dict:
            story_as_dict["score"] = 0
        if "time" not in story_as_dict:
            story_as_dict["time"] = 0
        if "title" not in story_as_dict:
            story_as_dict["title"] = "(no title)"
        if "text" not in story_as_dict:
            story_as_dict["text"] = ""
        if "url" not in story_as_dict:
            story_as_dict["url"] = ""

        return Story(
            story_as_dict["by"],
            story_as_dict["descendants"],
            story_as_dict["id"],
            story_as_dict["kids"],
            story_as_dict["score"],
            story_as_dict["time"],
            story_as_dict["title"],
            story_as_dict["text"],
            story_as_dict["type"],
            story_as_dict["url"],
        )

    elif story_as_dict["type"] == "job":
        # check for incomplete metadata and assign default values
        if "by" not in story_as_dict:
            story_as_dict["by"] = "(no author)"
        if "descendants" not in story_as_dict:
            story_as_dict["descendants"] = 0
        if "id" not in story_as_dict:
            story_as_dict["id"] = -1
        if "kids" not in story_as_dict:
            story_as_dict["kids"] = []
        if "score" not in story_as_dict:
            story_as_dict["score"] = 0
        if "time" not in story_as_dict:
            story_as_dict["time"] = 0
        if "title" not in story_as_dict:
            story_as_dict["title"] = "(no title)"
        if "text" not in story_as_dict:
            story_as_dict["text"] = ""
        if "url" not in story_as_dict:
            story_as_dict["url"] = ""

        return Story(
            story_as_dict["by"],
            story_as_dict["descendants"],
            story_as_dict["id"],
            story_as_dict["kids"],
            story_as_dict["score"],
            story_as_dict["time"],
            story_as_dict["title"],
            story_as_dict["text"],
            story_as_dict["type"],
            story_as_dict["url"],
        )

    else:
        return None


def page_package_processor(page_package: PageOfStories, context: dict = None):
    ppp_unique_id = utils_hash.get_sha1_of_current_time(
        salt=utils_random.random_real(0, 1)
    )

    log_prefix_local = f"ppp={ppp_unique_id} page={page_package.page_number}: "

    sup_slug = f"sup={context['supervisor_id']} "

    logger.info(
        sup_slug
        + log_prefix_local
        + f"len(story_ids)={len(page_package.story_ids)} story_ids={page_package.story_ids}"
    )

    page_processor_start_ts = utils_time.get_time_now_in_epoch_seconds_float()

    # customize links and labels
    # light mode
    other_stories_links_lm = ""
    other_stories_links_dm = ""
    for each_story_type in page_package.rosters.keys():
        if each_story_type == page_package.story_type:
            continue
        other_stories_links_lm += f'<a class="other-story-type" href="{get_story_page_url(each_story_type, 1, light_mode=True)}">{each_story_type}</a>\n'
        other_stories_links_dm += f'<a class="other-story-type" href="{get_story_page_url(each_story_type, 1, light_mode=False)}">{each_story_type}</a>\n'
    other_stories_links_lm = (
        f'<div class="next-page-link-tray">{other_stories_links_lm}</div>'
    )
    other_stories_links_dm = (
        f'<div class="next-page-link-tray">{other_stories_links_dm}</div>'
    )

    page_html = ""

    num_stories_on_page = None

    for rank, cur_id in enumerate(page_package.story_ids):
        log_prefix_id = f"id={cur_id}: "
        log_prefix_rank_cur_id_loop = log_prefix_id + f"ppp={ppp_unique_id}: "

        # logger.info(id_log_prefix + f"page:rank={page_package.page_number}:{rank}")

        story_object = None
        we_have_to_save_story_object = True

        # check for locally cached story
        cached_filename = os.path.join(
            config.settings["CACHED_STORIES_DIR"], get_pickle_filename(cur_id)
        )
        if not os.path.exists(cached_filename):
            logger.info(log_prefix_rank_cur_id_loop + "no cached story found")

        else:
            with open(cached_filename, mode="rb") as file:
                story_object = pickle.load(file)

            required_minimum_version = 1
            if story_object.story_object_version < required_minimum_version:
                logger.info(
                    log_prefix_rank_cur_id_loop
                    + f"cached story found, but its story_object_version {story_object.story_object_version} is below the minimum of {required_minimum_version}"
                )
                story_object = None  # reset so we know to invoke asdfft1()

            else:
                minutes_ago_since_last_firebaseio_update = (
                    utils_time.get_time_now_in_epoch_seconds_int()
                    - story_object.time_of_last_firebaseio_query
                ) // 60

                time_ago_since_last_firebaseio_update_display_for_log = (
                    utils_text.add_singular_plural(
                        minutes_ago_since_last_firebaseio_update,
                        "minute",
                        force_int=True,
                    )
                    + " ago"
                )

                logger.info(
                    log_prefix_rank_cur_id_loop
                    + f"cached story found (last updated from firebaseio.com {time_ago_since_last_firebaseio_update_display_for_log})"
                )

                if (
                    minutes_ago_since_last_firebaseio_update
                    < config.settings["MINUTES_BEFORE_REFRESHING_STORY_METADATA"]
                ):
                    # too soon to refreshen
                    logger.info(
                        log_prefix_rank_cur_id_loop
                        + f"re-using cached story (last updated from firebaseio.com {time_ago_since_last_firebaseio_update_display_for_log})"
                    )
                    we_have_to_save_story_object = False

                else:
                    logger.info(
                        log_prefix_rank_cur_id_loop + "try to freshen cached story"
                    )

                    try:
                        freshen_up(story_object=story_object, page_package=page_package)
                        logger.info(
                            log_prefix_rank_cur_id_loop + "successfully freshened story"
                        )

                    except Exception as exc:
                        short_exc_name = exc.__class__.__name__
                        exc_name = exc.__class__.__module__ + "." + short_exc_name
                        exc_msg = str(exc)

                        if exc_msg == "failed to freshen story":
                            logger.info(
                                log_prefix_rank_cur_id_loop
                                + "failed to freshen story; will re-use cached story"
                            )
                            we_have_to_save_story_object = False

                        else:
                            exc_slug = f"{exc_name}: {exc_msg}"
                            logger.error(
                                log_prefix_id
                                + "freshen_up: "
                                + "unexpected exception: "
                                + exc_slug
                            )
                            tb_str = traceback.format_exc()
                            logger.error(log_prefix_id + "freshen_up: " + tb_str)

        if not story_object:
            try:
                story_object = asdfft2(item_id=cur_id, pos_on_page=rank)

            except UnsupportedStoryType as exc:
                exc_short_name = exc.__class__.__name__
                exc_name = f"{exc.__class__.__module__}.{exc_short_name}"
                exc_msg = str(exc)
                exc_slug = f"{exc_name}: {exc_msg}"
                logger.info(log_prefix_rank_cur_id_loop + exc_slug)
                logger.info(log_prefix_rank_cur_id_loop + "discarding this story")
                continue  # to next cur_id

            except Exception as exc:
                exc_short_name = exc.__class__.__name__
                exc_name = f"{exc.__class__.__module__}.{exc_short_name}"
                exc_msg = str(exc)
                exc_slug = f"{exc_name}: {exc_msg}"
                logger.error(
                    log_prefix_rank_cur_id_loop
                    + "asdfft: unexpected exception: "
                    + exc_slug
                )
                tb_str = traceback.format_exc()
                logger.error(log_prefix_rank_cur_id_loop + tb_str)
                logger.info(log_prefix_rank_cur_id_loop + "discarding this story")
                continue  # to next cur_id

        if not story_object:
            logger.info(log_prefix_rank_cur_id_loop + "couldn't get story details")
            logger.info(log_prefix_rank_cur_id_loop + "discarding this story")
            continue  # to next cur_id

        # if not story_object.has_thumb:
        #     logger.info(log_prefix_local + "story card will not have a thumbnail")

        # update badge
        story_object.badges_slug = create_badges_slug(
            story_object.id, page_package.story_type, page_package.rosters
        )

        populate_story_card_html_in_story_object(story_object)

        if not story_object.story_card_html:
            logger.info(
                log_prefix_local
                + log_prefix_rank_cur_id_loop
                + "couldn't create story_card_html"
            )
            logger.info(
                log_prefix_local + log_prefix_rank_cur_id_loop + "discarding this story"
            )
            continue  # to next cur_id
        else:
            logger.info(
                log_prefix_rank_cur_id_loop + "successfully created story_card_html"
            )

        if we_have_to_save_story_object:
            save_story_object_to_disk(
                story_object=story_object, log_prefix=log_prefix_id
            )

        page_html += story_object.story_card_html
        page_html += "\n"  # so html source looks pretty

    label_next_page = f"page {page_package.page_number + 1}"
    if page_package.is_first_page:
        more_button_lm = (
            '<hr class="before-more-buttons"/>'
            '<div class="more-buttons">'
            '<div class="next-page-link-tray">'
            f'<a href="{get_story_page_url(page_package.story_type, 2, light_mode=True)}">{label_next_page}</a>'
            "</div>"  # next-page-link-tray
            f'<div class="other-stories-tray">{other_stories_links_lm}</div>'
            "</div>\n"  # more-buttons
        )
        more_button_dm = (
            '<hr class="before-more-buttons"/>'
            '<div class="more-buttons">'
            '<div class="next-page-link-tray">'
            f'<a href="{get_story_page_url(page_package.story_type, 2, light_mode=False)}">{label_next_page}</a>'
            "</div>"  # next-page-link-tray
            f'<div class="other-stories-tray">{other_stories_links_dm}</div>'
            "</div>\n"  # more-buttons
        )
    elif page_package.is_last_page:
        more_button_lm = (
            '<hr class="before-more-buttons"/>'
            '<div class="more-buttons">'
            '<div class="next-page-link-tray">'
            f"no more pages of {page_package.story_type}. "
            f'<a href="{get_story_page_url(page_package.story_type, 1, light_mode=True)}">'
            f"page 1 of {page_package.story_type}"
            "</a>"
            "</div>"  # next-page-link-tray
            f'<div class="other-stories-tray">{other_stories_links_lm}</div>'
            "</div>"  # more-buttons
        )
        more_button_dm = (
            '<hr class="before-more-buttons"/>'
            '<div class="more-buttons">'
            '<div class="next-page-link-tray">'
            f"no more pages of {page_package.story_type}. "
            f'<a href="{get_story_page_url(page_package.story_type, 1, light_mode=False)}">'
            f"page 1 of {page_package.story_type}"
            "</a>"
            "</div>"  # next-page-link-tray
            f'<div class="other-stories-tray">{other_stories_links_dm}</div>'
            "</div>"  # more-buttons
        )
    else:  # not first page, not last page
        more_button_lm = (
            '<hr class="before-more-buttons"/>'
            '<div class="more-buttons">'
            '<div class="next-page-link-tray">'
            '<a href="'
            f"{get_story_page_url(page_package.story_type, page_package.page_number + 1, light_mode=True)}"
            '">'
            f"{label_next_page}"
            "</a>"
            "</div>"  # next-page-link-tray
            f'<div class="other-stories-tray">{other_stories_links_lm}</div>'
            "</div>\n"  # more-buttons
        )
        more_button_dm = (
            '<hr class="before-more-buttons"/>'
            '<div class="more-buttons">'
            '<div class="next-page-link-tray">'
            '<a href="'
            f"{get_story_page_url(page_package.story_type, page_package.page_number + 1, light_mode=False)}"
            '">'
            f"{label_next_page}"
            "</a>"
            "</div>"  # next-page-link-tray
            f'<div class="other-stories-tray">{other_stories_links_dm}</div>'
            "</div>\n"  # more-buttons
        )

    stories_channel_contents_top_section = (
        f'<div class="stories-section" data-page-num="{page_package.page_number}">\n\n'
        '<div class="page-header-and-switch-bar">\n'
        '<div class="page-header-tray">\n'
        f'<div class="page-header-label">page {page_package.page_number} of {page_package.story_type}</div>\n'
        "</div>\n"
        "</div>\n\n"
        '<div class="which-mode"><a href="{{ which_mode_url }}">{{ which_mode_label }}</a></div>\n'
        "<table>\n"
    )

    stories_channel_contents_bottom_section = "</table>\n</div>\n"

    html_generation_end_ts = utils_time.get_time_now_in_epoch_seconds_float()
    now_in_epoch_seconds = int(html_generation_end_ts)
    now_in_utc_readable = utils_time.convert_epoch_seconds_to_utc(now_in_epoch_seconds)

    how_long_to_generate_page_html = utils_time.convert_time_duration_to_human_readable(
        html_generation_end_ts - page_processor_start_ts
    )
    html_generation_time_slug = f'<div id="html-generation-time" class="html-generation-time" data-html-generation-time-in-epoch-seconds="{now_in_epoch_seconds}">This page was generated in {how_long_to_generate_page_html} at {now_in_utc_readable}<span id="how-long-ago"></span>.</div>\n'

    # prepare light mode page
    stories_channel_contents_top_plus_page_html_plus_bottom = (
        stories_channel_contents_top_section
        + page_html
        + stories_channel_contents_bottom_section
    )

    stories_channel_contents_lm = (
        stories_channel_contents_top_plus_page_html_plus_bottom
        + more_button_lm
        + html_generation_time_slug
    )

    with open(
        os.path.join(config.settings["TEMPLATES_SERVICE_DIR"], "stories.html"),
        "r",
        encoding="utf-8",
    ) as f:
        stories_html_page_template_lm = f.read()

    stories_html_page_template_lm = stories_html_page_template_lm.replace(
        "{{ canonical_url }}", config.settings["CANONICAL_URL"]["LM"]
    )
    stories_html_page_template_lm = stories_html_page_template_lm.replace(
        "{{ header_hyperlink }}", config.settings["HEADER_HYPERLINK"]["LM"]
    )
    stories_html_page_template_lm = stories_html_page_template_lm.replace(
        "{{ short_url_display }}", config.settings["SHORT_URL_DISPLAY"]
    )
    stories_html_page_template_lm = stories_html_page_template_lm.replace(
        "{{ static_css_url }}", f"{config.settings['CSS_URL']}styles.css"
    )
    stories_html_page_template_lm = stories_html_page_template_lm.replace(
        "{{ stories }}", stories_channel_contents_lm
    )
    stories_html_page_template_lm = stories_html_page_template_lm.replace(
        "{{ about_url }}", config.settings["ABOUT_HTML_URL"]["LM"]
    )
    stories_html_page_template_lm = stories_html_page_template_lm.replace(
        "{{ which_mode_url }}",
        get_story_page_url(
            page_package.story_type,
            page_package.page_number,
            light_mode=False,
            from_other_mode=True,
        ),
    )
    stories_html_page_template_lm = stories_html_page_template_lm.replace(
        "{{ which_mode_label }}", "dark mode"
    )

    filename_lm = get_html_page_filename(
        page_package.story_type, page_package.page_number, light_mode=True
    )
    full_path_lm = os.path.join(config.settings["COMPLETED_PAGES_DIR"], filename_lm)

    upload_attempts_remaining = 3
    delay_between_upload_attempts = 8
    while True:
        if upload_attempts_remaining == 0:
            logger.error(
                log_prefix_local
                + f"failed to upload page {page_package.page_number} of {page_package.story_type} ~Tim~"
            )
            return None

        try:
            with open(full_path_lm, mode="w", encoding="utf-8") as f:
                f.write(stories_html_page_template_lm)
                f.close()

            utils_aws.upload_page_of_stories(
                page_filename=filename_lm, log_prefix=sup_slug + log_prefix_local
            )
            break
        except Exception as exc:
            upload_attempts_remaining -= 1
            exc_name = exc.__class__.__name__
            exc_msg = str(exc)
            exc_slug = f"{exc_name}: {exc_msg}"
            logger.error(
                log_prefix_local + exc_slug + f" {upload_attempts_remaining=} ~Tim~"
            )
            time.sleep(delay_between_upload_attempts)
            delay_between_upload_attempts *= 2

    num_stories_on_page = stories_html_page_template_lm.count("data-story-id")

    # prepare dark mode page
    stories_channel_contents_dm = (
        stories_channel_contents_top_plus_page_html_plus_bottom
        + more_button_dm
        + html_generation_time_slug
    )

    with open(
        os.path.join(config.settings["TEMPLATES_SERVICE_DIR"], "stories.html"),
        mode="r",
        encoding="utf-8",
    ) as f:
        stories_html_page_template_dm = f.read()

    stories_html_page_template_dm = stories_html_page_template_dm.replace(
        "{{ canonical_url }}",
        config.settings["CANONICAL_URL"]["DM"],
    )
    stories_html_page_template_dm = stories_html_page_template_dm.replace(
        "{{ header_hyperlink }}",
        config.settings["HEADER_HYPERLINK"]["DM"],
    )
    stories_html_page_template_dm = stories_html_page_template_dm.replace(
        "{{ short_url_display }}",
        config.settings["SHORT_URL_DISPLAY"],
    )
    stories_html_page_template_dm = stories_html_page_template_dm.replace(
        "{{ static_css_url }}",
        f"{config.settings['CSS_URL']}styles-dm.css",
    )
    stories_html_page_template_dm = stories_html_page_template_dm.replace(
        "{{ about_url }}", config.settings["ABOUT_HTML_URL"]["DM"]
    )
    stories_html_page_template_dm = stories_html_page_template_dm.replace(
        "{{ stories }}", stories_channel_contents_dm
    )
    stories_html_page_template_dm = stories_html_page_template_dm.replace(
        "{{ about_url }}", config.settings["ABOUT_HTML_URL"]["DM"]
    )
    stories_html_page_template_dm = stories_html_page_template_dm.replace(
        "{{ which_mode_url }}",
        get_story_page_url(
            page_package.story_type,
            page_package.page_number,
            light_mode=True,
            from_other_mode=True,
        ),
    )
    stories_html_page_template_dm = stories_html_page_template_dm.replace(
        "{{ which_mode_label }}", "light mode"
    )

    filename_dm = get_html_page_filename(
        page_package.story_type, page_package.page_number, light_mode=False
    )
    full_path_dm = os.path.join(config.settings["COMPLETED_PAGES_DIR"], filename_dm)

    try:
        with open(full_path_dm, mode="w", encoding="utf-8") as f:
            f.write(stories_html_page_template_dm)

        utils_aws.upload_page_of_stories(
            page_filename=filename_dm, log_prefix=sup_slug + log_prefix_local
        )
    except Exception as exc:
        exc_name = exc.__class__.__name__
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        logger.error(log_prefix_local + exc_slug + " ~Tim~")
        return None

    # compute how long it took to ship this page

    page_processor_end_ts = utils_time.get_time_now_in_epoch_seconds_float()

    h, m, s, s_frac = utils_time.convert_time_duration_to_hms(
        page_processor_end_ts - page_processor_start_ts
    )

    logger.info(
        sup_slug
        + f"ppp={ppp_unique_id} page={page_package.page_number}: shipped {num_stories_on_page} stories in {h:02d}:{m:02d}:{s:02d}"
    )

    return page_package.page_number


def populate_story_card_html_in_story_object(story_object):
    # slugs must begin and end with <div> tags

    data_separator_slug = f'<div class="data-separator">{config.settings["SYMBOLS"]["DATA_SEPARATOR"]}</div>'

    story_card_html = ""

    story_card_html += (
        f'<tr data-story-id="{story_object.id}"><td>'
        + '<table class="story-details">'
        + "<tr><td>"
        + "<hr>"
    )

    if story_object.image_slug:
        story_card_html += story_object.image_slug

    story_card_html += "</td></tr>"

    if story_object.github_languages_slug:
        story_card_html += (
            "<tr><td>" + story_object.github_languages_slug + "</td></tr>"
        )

    story_card_html += '<tr><td><div class="title-and-domain-bar">'
    story_card_html += '<div class="title-part">'

    story_card_html += (
        f'<a href="{story_object.title_hyperlink}">'
        + utils_text.insert_possible_line_breaks(story_object.title)
        + "</a>"
    )

    if story_object.story_content_type_slug:
        story_card_html += story_object.story_content_type_slug

    story_card_html += "</div>"

    if story_object.has_outbound_url:
        story_card_html += (
            '<div class="domain-part">' + story_object.hostname_dict["slug"] + "</div>"
        )

    story_card_html += "</div></td></tr>"

    story_card_html += '<tr><td><div class="badges-points-comments-time-author-bar">'

    if story_object.badges_slug:
        story_card_html += story_object.badges_slug + data_separator_slug

    story_card_html += (
        '<div class="story-score">'
        + utils_text.add_singular_plural(story_object.score, "point")
        + "</div>"
        + data_separator_slug
    )

    story_card_html += (
        '<div class="story-descendants">'
        + f'<a href="{story_object.hn_comments_url}">'
        + utils_text.add_singular_plural(story_object.descendants, "comment")
        + "</a></div>"
        + data_separator_slug
    )

    story_card_html += (
        f'<div class="story-time-ago" title="{story_object.publication_time_ISO_8601}">'
        + utils_time.how_long_ago_human_readable(story_object.time)
        + "&nbsp;</div>"
    )

    story_card_html += (
        f'<div class="story-byline">by <a href="https://news.ycombinator.com/user?id={story_object.by}">'
        + story_object.by
        + "</a></div>"
    )

    story_card_html += "</div></td></tr>"

    if story_object.reading_time:
        story_card_html += (
            "<tr><td>"
            + '<div class="reading-time-bar"><div class="estimated-reading-time">⏱️&nbsp;'
            + utils_text.add_singular_plural(
                story_object.reading_time, "minute", force_int=True
            )
            + "</div></div></tr></td>"
        )

    if story_object.pdf_page_count:
        story_card_html += (
            '<tr><td><div class="reading-time-bar">'
            + '<div class="estimated-reading-time">📄&nbsp;'
            + utils_text.add_singular_plural(
                story_object.pdf_page_count, "page", force_int=True
            )
            + "</div></div></td></tr>"
        )

    story_card_html += "</table></td></tr>"

    story_object.story_card_html = story_card_html


def query_firebaseio_for_story_data(item_id=None):
    query = f"/v0/item/{item_id}.json"
    return utils_http.firebaseio_endpoint_query(
        query=query, log_prefix=f"id={item_id}: "
    )


def save_story_object_to_disk(story_object=None, log_prefix=""):
    log_prefix += "save_story_object_to_disk: "
    try:
        with open(
            os.path.join(
                config.settings["CACHED_STORIES_DIR"],
                get_pickle_filename(story_object.id),
            ),
            mode="wb",
        ) as file:
            pickle.dump(story_object, file)
    except Exception as exc:
        exc_name = f"{exc.__class__.__module__}.{exc.__class__.__name__}"
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        logger.info(log_prefix + exc_slug)

    try:
        with open(
            os.path.join(
                config.settings["CACHED_STORIES_DIR"],
                f"id-{story_object.id}.json",
            ),
            mode="w",
            encoding="utf-8",
        ) as f:
            f.write(json.dumps(story_object.to_dict(), indent=4, sort_keys=True))
    except Exception as exc:
        exc_name = f"{exc.__class__.__module__}.{exc.__class__.__name__}"
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        logger.info(log_prefix + exc_slug)


def supervisor(cur_story_type):
    unique_id = utils_hash.get_sha1_of_current_time(salt=utils_random.random_real(0, 1))
    log_prefix = f"sup={unique_id}: "

    supervisor_start_ts = utils_time.get_time_now_in_epoch_seconds_float()

    logger.info(
        log_prefix
        + f"started at {utils_time.convert_epoch_seconds_to_utc(int(supervisor_start_ts))}"
    )

    rosters = {}
    for roster_story_type in config.settings["SCRAPING"]["STORY_ROSTERS"]:
        try:
            rosters[roster_story_type] = thnr_scrapers.get_roster_for_story_type(
                roster_story_type=roster_story_type, log_prefix=log_prefix
            )
            if rosters[roster_story_type]:
                logger.info(
                    log_prefix
                    + f"ingested roster for {roster_story_type} stories; length: {len(rosters[roster_story_type])}"
                )
            else:
                logger.info(
                    log_prefix
                    + f"failed to ingest roster for {roster_story_type} stories ~Tim~"
                )
        except Exception as exc:
            logger.info(
                log_prefix
                + f"failed to ingest roster for {roster_story_type} stories: {exc} ~Tim~"
            )

    if len(rosters[cur_story_type]) == 0:
        logger.info(
            log_prefix
            + f"failed to ingest roster '{cur_story_type}' after {config.settings['SCRAPING']['NUM_RETRIES_FOR_HN_FEEDS']} tries. will proceed with empty roster. ~Tim~"
        )
        rosters[roster_story_type] = []

    page_packages = []
    cur_page_number = 1
    cur_story_ids = []
    cur_roster = list(rosters[cur_story_type])
    is_first_page = True
    is_last_page = False

    pages_in_progress = set()

    while cur_roster:
        while (
            cur_roster
            and len(cur_story_ids) < config.settings["PAGES"]["NUM_STORIES_PER_PAGE"]
        ):
            cur_story_ids.append(cur_roster.pop(0))

            if len(cur_roster) == 0:
                is_last_page = True

        cur_page_package = PageOfStories(
            cur_story_type,
            cur_page_number,
            list(cur_story_ids),
            dict(rosters),
            is_first_page,
            is_last_page,
        )

        pages_in_progress.add(cur_page_number)

        page_packages.append(cur_page_package)
        cur_page_number += 1
        cur_story_ids.clear()
        is_first_page = False

    if config.debug_flags["DEBUG_FLAG_FORCE_SINGLE_THREAD_EXECUTION"]:
        for each_page in page_packages:
            res = page_package_processor(
                page_package=each_page,
                context={"supervisor_id": unique_id},
            )
            if res:
                pages_in_progress.remove(res)
    else:
        page_processing_job_futures = []

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=config.max_workers
        ) as executor:
            for each_page_package in page_packages:
                page_processing_job_futures.append(
                    executor.submit(
                        page_package_processor,
                        page_package=each_page_package,
                        context={"supervisor_id": unique_id},
                    )
                )

        concurrent.futures.wait(page_processing_job_futures)

        for future in page_processing_job_futures:
            future_result = future.result()
            if future_result:
                pages_in_progress.remove(int(future_result))

    if pages_in_progress:
        logger.warning(
            log_prefix + f"shipped some pages: missing {pages_in_progress} ~Tim~"
        )
    else:
        logger.info(log_prefix + "shipped all pages")

    supervisor_end_ts = utils_time.get_time_now_in_epoch_seconds_float()

    h, m, s, s_frac = utils_time.convert_time_duration_to_hms(
        supervisor_end_ts - supervisor_start_ts
    )
    logger.info(
        log_prefix
        + f"completed in {h:02d}:{m:02d}:{s:02d}{s_frac} at {utils_time.convert_epoch_seconds_to_utc(int(supervisor_end_ts))}"
    )
    return 0
