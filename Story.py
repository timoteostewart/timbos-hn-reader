from typing import List

import utils_text
import utils_time
from Item import Item


class Story(Item):
    def __init__(
        self,
        by: str,
        descendants: int,
        id: str,
        kids: List[int],
        score: int,
        time: int,
        title: str,
        text: str,
        url: str,
    ) -> None:

        self.hn_comments_url: str = f"https://news.ycombinator.com/item?id={id}"

        if url:
            self.url: str = url
            self.has_outbound_link: bool = True
            self.url_content_type: str = ""
            self.title_hyperlink = url

        else:
            self.url: str = self.hn_comments_url
            self.has_outbound_link: bool = False
            self.url_content_type: str = ""
            self.title_hyperlink = self.hn_comments_url

        self.hostname = {}
        (
            self.hostname["full"],
            self.hostname["minus_www"],
        ) = utils_text.get_domains_from_url(url)

        self.hostname["for_hn_search"] = ""  # could include path after hostname
        self.hostname["for_display"] = ""
        self.hostname["for_display_addl_class"] = ""
        self.hostname["slug"] = ""
        utils_text.create_domains_slug(self.hostname)

        self.title: str = title

        self.text: str = text

        self.descendants: int = descendants

        self.score: int = score

        self.time_of_last_firebaseio_query: int

        self.linked_url_reported_content_type: str = ""
        self.linked_url_confirmed_content_type: str = ""
        self.linked_url_og_image_url_initial: str = ""
        self.linked_url_github_langs_inner_html: str = ""

        self.gh_repo_lang_stats: str = ""
        self.github_languages_slug: str = ""

        self.reading_time = None

        self.pdf_page_count: int = 0

        self.story_content_type_slug: str = ""

        # while inside url_utils.get_data_via_requests()
        #   and promote_initial_og_image_url_to_final()
        self.linked_url_og_image_url_final: str = (
            ""  # rename to: linked_url_og_image_url_possibly_redirected
        )
        self.og_image_content_type: str = ""
        self.normalized_og_image_filename: str = ""
        self.downloaded_orig_thumb_full_path: str = ""
        self.downloaded_og_image_magic_result: str = ""

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
        self.reason_for_no_thumb: str = ""

        self.og_image_filename_details_from_url: dict() = {}
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

        self.story_card_html: str = ""

        self.badges_slug = ""

        self.story_object_version = "0.0.1"

        super().__init__(id, "story", text, by, time, kids)

    def __str__(self):
        res = ""
        all_vars = vars(self)
        for each in all_vars:
            res += each
            res += ": "
            res += str(all_vars[each])
            res += ", "
        return res

    def to_dict(self):
        return {key: value for key, value in self.__dict__.items()}
