import datetime
from dataclasses import dataclass
from typing import Dict, List

import text_utils
import time_utils
import url_utils


class Item:
    id: int  # item ID (required attribute)
    # 'story' or 'comment' ('job', 'poll', and 'pollopt' not yet implemented)
    type: str
    # title: str
    text: str  # in HTML format
    # url: str
    by: str  # username of item's author
    time: int  # in Unix time format
    publication_time_ISO_8601: str
    seconds_ago: int  # diff between time.time() and self.time
    time_ago_display: str  # display formatted with various time units
    # score: int

    # parent: int  # item ID
    kids: List[int]  # item IDs
    # descendants: int  # comment count for stories (and polls)

    deleted: bool
    dead: bool

    poll: int  # item ID; not implemented
    parts: List[int]  # for polls; not implemented

    def __init__(
        self, id: str, type: str, text: str, by: str, ztime: str, kids: List[str]
    ) -> None:
        self.id: int = int(id)
        self.type: str = type
        self.text: str = text
        self.by: str = by

        self.time = int(ztime)
        self.publication_time_ISO_8601: str = datetime.datetime.utcfromtimestamp(
            self.time
        ).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )  # note: in ISO 8601 in UTC

        time_now = time_utils.get_time_now_in_seconds_int()
        seconds_ago = time_now - ztime
        self.time_ago_display = time_utils.convert_seconds_ago_to_human_readable(
            seconds_ago
        )

        self.kids: List[int]
        if kids:
            self.kids = kids
        else:
            self.kids = []


@dataclass
class PageOfStories:
    story_type: str
    page_number: int
    story_ids: List[int]
    rosters: Dict
    is_first_page: bool
    is_last_page: bool


class Story(Item):
    def __init__(
        self,
        by: str,
        descendants: str,
        id: str,
        kids: List[str],
        score: str,
        time: str,
        title: str,
        text: str,
        url: str,
    ) -> None:

        if not url:
            self.is_ask_show_tell_launch_hn: bool = True
            self.url: str = f"https://news.ycombinator.com/item?id={id}"
            self.url_content_type: str = ""
        else:
            self.is_ask_show_tell_launch_hn: bool = False
            self.url: str = url
            self.url_content_type: str = ""

        self.title: str = title
        self.title_slug = text_utils.insert_possible_line_breaks(title)

        self.text: str = text

        self.url: str = url

        self.hostname = {}
        (
            self.hostname["full"],
            self.hostname["minus_www"],
        ) = url_utils.get_domains_from_url(url)
        self.hostname["for_hn_search"] = ""  # could include path after hostname
        self.hostname["for_display"] = ""
        self.hostname["for_display_addl_class"] = ""
        self.hostname["slug"] = ""
        url_utils.create_domains_slug(self.hostname)

        self.descendants: int = int(descendants)
        self.descendants_display = text_utils.add_singular_plural(
            self.descendants, "comment"
        )
        self.hn_comments_url: str = f"https://news.ycombinator.com/item?id={id}"

        self.score: int = int(score)
        self.score_display = text_utils.add_singular_plural(self.score, "point")

        self.time_of_last_firebaseio_query: int = (
            time_utils.get_time_now_in_seconds_int()
        )

        # by analyzing self.text:
        self.before_title_link_slug: str = ""

        self.linked_url_content_type: str = ""
        self.linked_url_og_image_url_initial: str = ""
        self.linked_url_github_langs_inner_html: str = ""

        self.gh_repo_lang_stats: str = ""
        self.github_languages_slug: str = ""

        self.reading_time: int = 0
        self.reading_time_slug: str = ""

        self.pdf_page_count: int = 0
        self.pdf_page_count_slug: str = ""

        self.story_content_type_slug: str = ""

        # while inside url_utils.get_data_via_requests()
        #   and promote_initial_og_image_url_to_final()
        self.linked_url_og_image_url_final: str = ""
        self.linked_url_og_image_url_content_type: str = ""
        self.downloaded_orig_thumb_filename: str = ""
        self.downloaded_orig_thumb_full_path: str = ""
        self.downloaded_orig_thumb_content_type: str = ""

        self.has_thumb: bool = True
        # We set `has_thumb` False in these cases:
        #     - the og:image filename is one we ignore
        #     - the thumbnail's magic number isn't an image file or PDF
        #     - the og:image couldn't be downloaded for some reason
        #     - we couldn't rasterize the first page of multipage PDF
        #     - the og:image was too small to thumbnail
        #     - the og:image's width or height was too small to work with
        #     - the og:image couldn't be bordered, cropped, or adjusted for some reason
        #     - the og:image URL was invalid for some reason
        #     - the og:image file seemed corrupt for some reason

        self.thumb_filename_details: dict() = {}
        self.thumb_aspect_hint: str = ""

        # while inside thumbs.check_for_thumb()
        self.image_slug: str = ""

        # social-media account details
        self.social_media = {}
        self.social_media["account_name_url"] = ""
        self.social_media["account_name_display"] = ""
        self.social_media["nowrap_class"] = ""
        self.social_media["account_url"] = ""
        self.social_media["account_name_slug"] = ""
        self.social_media["hn_search_query"] = ""

        # various things that will have to be computed anew periodically
        self.story_card_html: str = ""

        super().__init__(id, "story", text, by, time, kids)

    def __str__(self):
        s = ""
        d = vars(self)
        for ea_d in d:
            s += ea_d
            s += ": "
            s += str(d[ea_d])
            s += ", "
        return s
