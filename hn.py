import concurrent.futures
import json
import logging
import os
import pickle
import time
import traceback

import requests
from bs4 import BeautifulSoup

import aws_utils
import config
import hash_utils
import my_drivers
import my_scrapers
import retrieve_by_url
import social_media
import text_utils
import thumbs
import time_utils
import url_utils
from my_exceptions import *
from PageOfStories import PageOfStories
from Story import Story

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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


def acquire_story_details_for_first_time(driver=None, item_id=None, pos_on_page=None):
    try:
        story_as_dict = query_firebaseio_for_story_data(item_id=item_id)
    except Exception as exc:
        raise exc

    if not story_as_dict:
        logger.warning(
            f"id {item_id}: failed to receive story details from firebase.io"
        )
        raise Exception()
    elif story_as_dict["type"] not in ["story", "job", "comment"]:
        # TODO: eventually handle poll, job, etc. other types
        logger.info(
            f"id {item_id}: not processing item of item type {story_as_dict['type']}"
        )
        raise UnsupportedStoryType(story_as_dict["type"])

    story_as_object = item_factory(story_as_dict)

    if not story_as_object:
        raise Exception(f"id {item_id}: failed to get story details")

    if story_as_object.url:
        _, domains = url_utils.get_domains_from_url(story_as_object.url)
        if domains in skip_getting_content_type_via_head_request_for_domains:
            logger.info(f"id {story_as_object.id}: skip HEAD request for {domains}")
        else:
            story_as_object.linked_url_content_type = (
                my_scrapers.get_content_type_via_head_request(story_as_object.url)
            )
        if story_as_object.linked_url_content_type:
            logger.info(
                f"id {story_as_object.id}: content-type {story_as_object.linked_url_content_type} for url {story_as_object.url}"
            )
        else:
            logger.info(
                f"id {story_as_object.id}: content-type could not be determined for url {story_as_object.url}"
            )

        if (
            story_as_object.linked_url_content_type == "text/html"
            or not story_as_object.linked_url_content_type
        ):
            try:
                page_source = retrieve_by_url.get_page_source_noproxy(
                    driver=driver, url=story_as_object.url
                )
            except Exception as exc:
                logger.warning(
                    f"id {story_as_object.id}: problem getting page source from {story_as_object.url}: {exc}"
                )
                logger.info(
                    f"id {story_as_object.id}: creating minimal story card for story '{story_as_object.title}' at url {story_as_object.url}"
                )

                # create super minimal story card to have at least something to return
                create_story_card_html_from_story_object(story_as_object)

                # pickle `story_as_object` as json to a file
                logger.info(
                    f"id {story_as_object.id}: pickling item for the first time"
                )
                pickle.dump(
                    story_as_object,
                    open(
                        os.path.join(
                            config.settings["CACHED_STORIES_DIR"],
                            get_pickle_filename(story_as_object.id),
                        ),
                        "wb",
                    ),
                )

                return (
                    story_as_object.story_card_html,
                    time_utils.how_long_ago_human_readable(story_as_object.time),
                )

            try:
                soup = BeautifulSoup(page_source, "html.parser")
            except Exception as exc:
                logger.error(
                    f"id {story_as_object.id}: problem making soup from {story_as_object.url}: {exc}"
                )
                raise exc

            # og:image
            og_image_url_result = soup.find("meta", {"property": "og:image"})
            if og_image_url_result:
                if og_image_url_result.has_attr("content"):
                    og_image_url = og_image_url_result["content"]
                    story_as_object.linked_url_og_image_url_initial = og_image_url
                    logger.info(
                        f"id {story_as_object.id}: found og:image url {story_as_object.linked_url_og_image_url_initial}"
                    )
            else:
                logger.info(f"id {story_as_object.id}: did not find og:image url")

            try:
                reading_time = my_scrapers.get_reading_time(
                    story_as_object, page_source
                )
                if reading_time:
                    story_as_object.reading_time = reading_time
            except Exception as exc:
                logger.error(
                    f"id {story_as_object.id}: get_reading_time: {exc}; "
                    f"traceback:\n{traceback.format_exc(exc)}"
                )
                raise exc

            ## create a slug for the linked URL's social-media website channel, if necessary.
            ## use details encoded in the url or the html page source
            ## https://hackernews-insight.vercel.app/domain-analysis

            try:
                social_media.check_for_social_media_details(
                    driver=driver,
                    story_as_object=story_as_object,
                    page_source_soup=soup,
                )
            except Exception as exc:
                logger.error(
                    f"id {story_as_object.id}: check_for_social_media_details: {exc}"
                )
                raise exc

            if story_as_object.reading_time > 0:
                create_reading_time_slug(story_as_object)

        # if story links to PDF, we'll use 1st page of PDF as thumb instead of og:image (if any)
        elif (
            story_as_object.linked_url_content_type == "application/pdf"
            or story_as_object.linked_url_content_type == "application/octet-stream"
        ):
            story_as_object.linked_url_og_image_url_initial = story_as_object.url

        if my_scrapers.download_og_image(story_as_object):
            if pos_on_page < 5:
                img_loading_attr = "eager"
            else:
                img_loading_attr = "lazy"

            thumbs.get_image_slug(story_as_object, img_loading=img_loading_attr)

            if story_as_object.pdf_page_count > 0:
                story_as_object.pdf_page_count_slug = (
                    "<tr><td>"
                    '<div class="reading-time-bar">'
                    '<div class="estimated-reading-time">'
                    f"📄 {text_utils.add_singular_plural(story_as_object.pdf_page_count, 'page', force_int=True)}"
                    "</div>"
                    "</div>"
                    "</td></tr>"
                )

        else:
            story_as_object.image_slug = text_utils.EMPTY_STRING
            story_as_object.has_thumb = False

    else:
        logger.info(f"id {story_as_object.id} has no url (probably an Ask HN, etc.)")
        story_as_object.url = story_as_object.hn_comments_url
        story_as_object.image_slug = text_utils.EMPTY_STRING
        story_as_object.has_thumb = False

    ##
    ## add informative labels before and after the story card title, if possible
    ##

    if not story_as_object.image_slug or story_as_object.has_thumb == False:
        logger.info(f"id {story_as_object.id} will not have a thumbnail")
    else:
        logger.info(f"id {story_as_object.id} will have a thumbnail")

    # if we have no thumbnail, then make sure we don't include a `story_content_type_slug`
    if story_as_object.image_slug == text_utils.EMPTY_STRING:
        story_as_object.story_content_type_slug = text_utils.EMPTY_STRING
    else:
        # apply "[pdf]" label after title if it's not there but is probably applicable
        if (
            story_as_object.downloaded_og_image_magic_result
            and story_as_object.downloaded_og_image_magic_result == "application/pdf"
        ):
            if "pdf" not in story_as_object.title[-12:].lower():
                story_as_object.story_content_type_slug = (
                    ' <span class="story-content-type">[pdf]</span>'
                )
                logger.info(f"id {story_as_object.id}: added [pdf] label after title")

    ##
    ## build html for story card
    ##

    create_story_card_html_from_story_object(story_as_object)

    # pickle `story_as_object` as json to a file
    logger.info(f"id {story_as_object.id}: pickling item for the first time")
    pickle.dump(
        story_as_object,
        open(
            os.path.join(
                config.settings["CACHED_STORIES_DIR"],
                get_pickle_filename(story_as_object.id),
            ),
            "wb",
        ),
    )

    return story_as_object.story_card_html, time_utils.how_long_ago_human_readable(
        story_as_object.time
    )


def create_badges_slug(story_id, story_type, rosters):
    if story_type not in badge_codes:
        raise Exception(
            f"cannot create badge for unrecognized story_type {story_type} for story_id {story_id}"
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
        data_separator_slug = f'<div class="data-separator">{config.settings["SYMBOLS"]["DATA_SEPARATOR"]}</div>'
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
        badges_slug = f'<div class="badges-tray">{"".join(list_of_badges)}</div>{data_separator_slug}'
    else:
        badges_slug = f""

    return badges_slug


def create_reading_time_slug(story_as_object):
    story_as_object.reading_time_slug = (
        "<tr><td>"
        '<div class="reading-time-bar">'
        '<div class="estimated-reading-time">'
        f"⏱️ {text_utils.add_singular_plural(story_as_object.reading_time, 'minute', force_int=True)}"
        "</div>"
        "</div>"
        "</td></tr>"
    )


def create_story_card_html_from_story_object(story_as_object):
    title_slug_string = (
        f'<a href="{story_as_object.url}">{story_as_object.title_slug}</a>'
    )
    story_as_object.title_slug_string = title_slug_string
    score_slug_string = (
        f'<div class="story-score">{story_as_object.score_display}</div>'
    )
    story_as_object.score_slug_string = score_slug_string
    descendants_slug_string = f'<div class="story-descendants"><a href="{story_as_object.hn_comments_url}">{story_as_object.descendants_display}</a></div>'
    story_as_object.descendants_slug_string = descendants_slug_string

    data_separator_slug = f'<div class="data-separator">{config.settings["SYMBOLS"]["DATA_SEPARATOR"]}</div>'
    story_as_object.story_card_html = (
        f'<tr data-story-id="{story_as_object.id}"><td>'
        '<table class="story-details"><tbody class="story-details">'
        "<tr><td>"
        "<hr>"
        f"{story_as_object.image_slug}"
        "</td></tr>"
        f"{story_as_object.github_languages_slug}"
        "<tr><td>"
        '<div class="title-and-domain-bar">'
        f'<div class="title-part">{story_as_object.before_title_link_slug}'
        f"{title_slug_string}"
        f"{story_as_object.story_content_type_slug}</div>"
        f'<div class="domain-part">{story_as_object.hostname["slug"]}</div>'
        "</div>"
        "</td></tr>"
        "<tr><td>"
        '<div class="badges-points-comments-time-author-bar">'
        "<!-- badges_slug goes here -->"
        f"{score_slug_string}"
        f"{data_separator_slug}"
        f"{descendants_slug_string}"
        f"{data_separator_slug}"
        f'<div class="story-time-ago" title="{story_as_object.publication_time_ISO_8601}">'
        "<!-- pub_time_ago_display goes here -->&nbsp;</div>"
        f'<div class="story-byline">by <a href="https://news.ycombinator.com/user?id={story_as_object.by}">{story_as_object.by}</a></div>'
        "</div>"
        "</td></tr>"
        f"{story_as_object.reading_time_slug}"
        f"{story_as_object.pdf_page_count_slug}"
        "</tbody></table>"
        "</td></tr>"
    )


def freshen_up(story_as_object=None):
    # try to update title, score, comment count

    try:
        updated_story_data_as_dict = query_firebaseio_for_story_data(
            item_id=story_as_object.id
        )
    except Exception as exc:
        logger.warning(
            f"freshen_up(): query to hacker-news.firebaseio.com failed for story id {story_as_object.id} ; so re-using old story details"
        )
        raise exc

    if not updated_story_data_as_dict:
        logger.warning(
            f"freshen_up(): query to hacker-news.firebaseio.com failed for story id {story_as_object.id} ; so re-using old story details"
        )
        raise exc

    story_as_object.time_of_last_firebaseio_query = (
        time_utils.get_time_now_in_epoch_seconds_int()
    )

    # update title if needed
    if "title" in updated_story_data_as_dict:
        old_title = story_as_object.title
        new_title = updated_story_data_as_dict["title"]

        if old_title != new_title:
            if "url" in updated_story_data_as_dict:
                # old_url = story_as_object.url
                new_url = updated_story_data_as_dict["url"]
            else:
                # old_url = story_as_object.url
                new_url = f'https://news.ycombinator.com/item?id={updated_story_data_as_dict["id"]}'

            old_title_slug_string = story_as_object.title_slug_string
            new_title_slug_string = f'<a href="{new_url}">{text_utils.insert_possible_line_breaks(new_title)}</a>'

            pre = story_as_object.story_card_html
            story_as_object.story_card_html = story_as_object.story_card_html.replace(
                old_title_slug_string, new_title_slug_string, 1
            )
            post = story_as_object.story_card_html
            if pre == post:
                logger.error(
                    f"id {story_as_object.id}: failed to update title. old title slug string: {old_title_slug_string} ; new title slug string: {new_title_slug_string} ; old title: {old_title} ; new title: {new_title}"
                )
                logger.error(
                    f"id {story_as_object.id}: story_card_html: {story_as_object.story_card_html}"
                )

            else:
                story_as_object.title_slug_string = new_title_slug_string
                story_as_object.title = new_title
                logger.info(
                    f"id {story_as_object.id}: updated title from '{old_title}' to '{new_title}'"
                )

    else:
        logger.warning(
            f"id {story_as_object.id}: no key for 'title' in updated_story_data_as_dict; story is probably dead"
        )

    # update score if needed
    if "score" in updated_story_data_as_dict:
        old_score = story_as_object.score
        new_score = int(updated_story_data_as_dict["score"])
        if old_score != new_score:
            # old_score_slug_string = (
            #     f'<div class="story-score">{story_as_object.score_display}</div>'
            # )
            old_score_slug_string = story_as_object.score_slug_string
            new_score_display = text_utils.add_singular_plural(new_score, "point")
            new_score_slug_string = (
                f'<div class="story-score">{new_score_display}</div>'
            )
            story_as_object.story_card_html = story_as_object.story_card_html.replace(
                old_score_slug_string, new_score_slug_string, 1
            )

            story_as_object.score_slug_string = new_score_slug_string
            story_as_object.score = new_score
            logger.info(
                f"id {story_as_object.id}: updated score from {old_score} to {new_score}"
            )

    else:
        logger.warning(
            f"id {story_as_object.id}: no key for 'score' in updated_story_data_as_dict"
        )

    # update comment count (i.e., "descendants") if needed
    if "descendants" in updated_story_data_as_dict:
        old_descendants = story_as_object.descendants
        new_descendants = int(updated_story_data_as_dict["descendants"])
        if old_descendants != new_descendants:
            # old_descendants_slug_string = f'<div class="story-descendants"><a href="{story_as_object.hn_comments_url}">{story_as_object.descendants_display}</a></div>'
            old_descendants_slug_string = story_as_object.descendants_slug_string

            new_descendants_display = text_utils.add_singular_plural(
                new_descendants, "comment"
            )
            new_descendants_slug_string = f'<div class="story-descendants"><a href="{story_as_object.hn_comments_url}">{new_descendants_display}</a></div>'

            story_as_object.story_card_html = story_as_object.story_card_html.replace(
                old_descendants_slug_string, new_descendants_slug_string, 1
            )

            story_as_object.descendants_slug_string = new_descendants_slug_string
            story_as_object.descendants = new_descendants
            logger.info(
                f"id {story_as_object.id}: updated comment count from {old_descendants} to {new_descendants}"
            )


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
    item_type = story_as_dict["type"]

    if item_type == "story":
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
            story_as_dict["url"],
        )

    elif item_type == "job":
        # check for incomplete metadata and assign default values
        if "by" not in story_as_dict:
            story_as_dict["by"] = "(no author)"
        if "descendants" not in story_as_dict:
            story_as_dict["descendants"] = 0
        if "id" not in story_as_dict:
            story_as_dict["id"] = -1
        if "kids" not in story_as_dict:
            story_as_dict["kids"] = list()
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
            story_as_dict["url"],
        )

    else:  # item_type == 'comment':
        return None


def page_package_processor(page_package):
    logger.info(
        f"entering page_package_processor with {page_package.story_type} page {page_package.page_number}"
    )

    start_processing_page_ts = time_utils.get_time_now_in_epoch_seconds_float()

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

    for rank, each_id in enumerate(page_package.story_ids):
        if os.path.exists(
            os.path.join(
                config.settings["CACHED_STORIES_DIR"], get_pickle_filename(each_id)
            )
        ):
            logger.info(f"id {each_id}: cached story found")
            story_as_object = pickle.load(
                open(
                    os.path.join(
                        config.settings["CACHED_STORIES_DIR"],
                        get_pickle_filename(each_id),
                    ),
                    "rb",
                )
            )

            minutes_ago_since_last_firebaseio_update = int(
                (
                    time_utils.get_time_now_in_epoch_seconds_int()
                    - story_as_object.time_of_last_firebaseio_query
                )
                / 60
            )

            time_ago_since_last_firebaseio_update_display = (
                text_utils.add_singular_plural(
                    minutes_ago_since_last_firebaseio_update, "minute", force_int=True
                )
                + " ago"
            )

            if (
                minutes_ago_since_last_firebaseio_update
                > config.settings["MINUTES_BEFORE_REFRESHING_STORY_METADATA"]
            ):
                logger.info(
                    f"id {story_as_object.id}: try to freshen cached story (last update from firebaseio {time_ago_since_last_firebaseio_update_display})"
                )

                # attempt to update title, score, comment count
                try:
                    freshen_up(story_as_object=story_as_object)
                except Exception as exc:
                    repickling_log_detail = f"failed to freshen story: {exc}"
                else:
                    repickling_log_detail = "re-pickling freshened story"

            else:
                logger.info(
                    f"id {each_id}: re-using cached story (last updated from firebaseio {time_ago_since_last_firebaseio_update_display})"
                )
                # even if we re-use the cached story, we'll still update the
                # publication time ago and badges, since we have this info on hand
                repickling_log_detail = "re-pickling re-used cached story"

            # whether freshened or not, update pub_time_ago_display
            pub_time_ago_display = time_utils.how_long_ago_human_readable(
                story_as_object.time
            )

            logger.info(f"id {story_as_object.id}: {repickling_log_detail}")

            if repickling_log_detail.startswith("re-pickling"):
                pickle.dump(
                    story_as_object,
                    open(
                        os.path.join(
                            config.settings["CACHED_STORIES_DIR"],
                            get_pickle_filename(story_as_object.id),
                        ),
                        "wb",
                    ),
                )

                with open(
                    os.path.join(
                        config.settings["CACHED_STORIES_DIR"],
                        f"id-{story_as_object.id}.json",
                    ),
                    mode="w",
                    encoding="utf-8",
                ) as f:
                    f.write(
                        json.dumps(story_as_object.to_dict(), indent=4, sort_keys=True)
                    )

            cur_story_card_html = story_as_object.story_card_html

        else:
            logger.info(
                f"page {page_package.page_number}, id {each_id}: no cached story found"
            )

            try:
                driver = my_drivers.get_chromedriver(
                    requestor=f"id {each_id}, page_package_processor({page_package.story_type}), page {page_package.page_number}"
                )
                (
                    cur_story_card_html,
                    pub_time_ago_display,
                ) = acquire_story_details_for_first_time(
                    driver=driver, item_id=each_id, pos_on_page=rank
                )
                driver.close()
                driver.quit()
            except UnsupportedStoryType as exc:
                logger.info(f"id {each_id}: {exc}")
                continue  # to next each_id
            except Exception as exc:
                logger.error(
                    f"id {each_id}: acquire_story_details_for_first_time: {exc}; "
                    f"traceback:\n{traceback.format_exc(exc)}"
                )
                continue  # to next each_id

        if not cur_story_card_html:
            logger.error(f"id {each_id}: couldn't get story details for some reason")
            continue  # to next each_id

        # populate pub_time_ago_display
        cur_story_card_html = cur_story_card_html.replace(
            "<!-- pub_time_ago_display goes here -->", pub_time_ago_display, 1
        )

        # populate badges_slug placeholder
        new_badges_slug = create_badges_slug(
            each_id, page_package.story_type, page_package.rosters
        )
        cur_story_card_html = cur_story_card_html.replace(
            "<!-- badges_slug goes here -->", new_badges_slug, 1
        )

        page_html += cur_story_card_html
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
            f'<div class="stories-section" data-page-num="{page_package.page_number}">\n'
            ""
            '<div class="page-header-and-switch-bar">'
            '<div class="page-header-tray">'
            f'<div class="page-header-label">page {page_package.page_number} of {page_package.story_type}</div>'
            "</div>"
            "</div>"
            ""
            '<div class="which-mode"><a href="{{ which_mode_url }}">{{ which_mode_label }}</a></div>'
            ""
            "<table>"
        )

        stories_channel_contents_bottom_section = "</table>\n</div>\n"

        now_in_epoch_seconds = time_utils.get_time_now_in_epoch_seconds_int()
        now_in_utc_readable = time_utils.convert_epoch_seconds_to_utc(
            now_in_epoch_seconds
        )

        how_long_to_generate_page_html = (
            time_utils.convert_time_duration_to_human_readable(
                time_utils.get_time_now_in_epoch_seconds_float()
                - start_processing_page_ts
            )
        )
        html_generation_time_slug = f'<div class="html-generation-time" data-html-generation-time-in-epoch-seconds="{now_in_epoch_seconds}">This page was generated in {how_long_to_generate_page_html} at {now_in_utc_readable}.</div>\n'

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
        try:
            with open(full_path_lm, "w", encoding="utf-8") as f:
                f.write(stories_html_page_template_lm)
                f.close()
        except Exception as e:
            logger.error(f"{e}")
        aws_utils.upload_page_of_stories(filename_lm)

        # prepare dark mode page
        stories_channel_contents_dm = (
            stories_channel_contents_top_plus_page_html_plus_bottom
            + more_button_dm
            + html_generation_time_slug
        )

        with open(
            os.path.join(config.settings["TEMPLATES_SERVICE_DIR"], "stories.html"),
            "r",
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

        with open(full_path_dm, "w", encoding="utf-8") as f:
            f.write(stories_html_page_template_dm)
        aws_utils.upload_page_of_stories(filename_dm)

    num_stories_on_page = stories_html_page_template_lm.count("data-story-id")

    # compute how long it took to process this page
    h, m, s, s_frac = time_utils.convert_time_duration_to_hms(
        time_utils.get_time_now_in_epoch_seconds_float() - start_processing_page_ts
    )
    logger.info(
        f"update_stories() shipped page {page_package.page_number} of {page_package.story_type} containing {num_stories_on_page} actual stories in {h:02d}:{m:02d}:{s:02d}"
    )


def query_firebaseio_for_story_data(driver=None, item_id=None):
    query = f"/v0/item/{item_id}.json"
    return retrieve_by_url.firebaseio_endpoint_query(
        query=query, log_prefix=f"id {item_id}: "
    )

    url = "https://hacker-news.firebaseio.com" + query

    try:
        resp_as_json = retrieve_by_url.endpoint_query_via_requests(url)
    except requests.exceptions.ConnectionError as exc:
        logger.error(
            f"id {item_id}: firebaseio.com actively refused query {query}: {exc}"
        )
        raise
    except requests.exceptions.RequestException as exc:
        logger.warning(
            f"id {item_id}: GET request failed for firebaseio.com query {query}: {exc}"
        )
        time.sleep(
            int(config.settings["SCRAPING"]["FIREBASEIO_RETRY_DELAY"])
        )  # in case it's a transient error, such as a DNS issue, wait for some seconds
        raise
    except Exception as exc:
        logger.error(
            f"id {item_id}: query to firebaseio.com failed for query {query}: {exc}"
        )
        raise

    return resp_as_json


def supervisor(cur_story_type):
    supervisor_start_ts = time_utils.get_time_now_in_epoch_seconds_float()
    uniq = hash_utils.get_sha1_of_current_time()
    logger.info(
        f"supervisor({cur_story_type}) with unique id {uniq} started at {time_utils.convert_epoch_seconds_to_utc(time_utils.get_time_now_in_epoch_seconds_int())}"
    )

    rosters = {}
    driver = my_drivers.get_chromedriver(requestor=f"supervisor({cur_story_type})")
    for roster_story_type in config.settings["SCRAPING"]["STORY_ROSTERS"]:
        try:
            rosters[roster_story_type] = my_scrapers.get_roster_for(
                driver, roster_story_type
            )
            if rosters[roster_story_type]:
                logger.info(
                    f"ingested roster for {roster_story_type} stories; length: {len(rosters[roster_story_type])}"
                )
            else:
                logger.error(f"failed to ingest roster for {roster_story_type} stories")
        except Exception as exc:
            logger.error(
                f"supervisor({cur_story_type}) with unique id {uniq} failed to ingest roster for {roster_story_type} stories: {exc}"
            )
            raise exc

    driver.close()
    driver.quit()

    if len(rosters[cur_story_type]) == 0:
        logger.error(
            f"supervisor({cur_story_type}) with unique id {uniq} failed to ingest roster '{cur_story_type}' after {config.settings['SCRAPING']['NUM_RETRIES_FOR_HN_FEEDS']} tries. See errors"
        )
        return 1

    page_packages = []
    cur_page_number = 1
    cur_story_ids = []
    cur_roster = list(rosters[cur_story_type])
    is_first_page = True
    is_last_page = False

    while cur_roster:
        while (
            cur_roster
            and len(cur_story_ids) < config.settings["PAGES"]["NUM_STORIES_PER_PAGE"]
        ):
            cur_story_ids.append(cur_roster.pop(0))

            if len(cur_roster) == 0:
                is_last_page = True

        cur_page = PageOfStories(
            cur_story_type,
            int(cur_page_number),
            list(cur_story_ids),
            dict(rosters),
            is_first_page,
            is_last_page,
        )
        page_packages.append(cur_page)
        cur_page_number += 1
        cur_story_ids.clear()
        is_first_page = False

    # for each_page in page_packages:
    #     page_package_processor(each_page)

    page_processing_job_futures = []
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=config.max_workers
    ) as executor:
        for each_page_package in page_packages:
            page_processing_job_futures.append(
                executor.submit(page_package_processor, each_page_package)
            )
        # futures_dict = {
        #     executor.submit(page_package_processor, each_page): each_page
        #     for each_page in page_packages
        # }
        # for future in concurrent.futures.as_completed(futures_dict):
        #     pp = futures_dict[future]
        #     res = future.result()
    concurrent.futures.wait(page_processing_job_futures)

    h, m, s, s_frac = time_utils.convert_time_duration_to_hms(
        time_utils.get_time_now_in_epoch_seconds_float() - supervisor_start_ts
    )
    logger.info(
        f"supervisor({cur_story_type}) with unique id {uniq} completed in {h:02d}:{m:02d}:{s:02d}{s_frac} at {time_utils.convert_epoch_seconds_to_utc(time_utils.get_time_now_in_epoch_seconds_int())}"
    )
    return 0
