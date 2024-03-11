from typing import Dict, List

import utils_text
from Item import Item

# TODO: make this a dataclass? what are the benefits?


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
        self.story_object_version: int = 1

        self.hn_comments_url: str = f"https://news.ycombinator.com/item?id={id}"

        log_prefix = f"id {id}: "

        if url:
            self.url: str = url
            self.has_outbound_link: bool = True
            self.has_thumb: bool = None
            self.url_content_type: str = ""
            self.title_hyperlink = url

        else:
            self.url: str = self.hn_comments_url
            self.has_outbound_link: bool = False
            self.has_thumb: bool = False
            self.url_content_type: str = ""
            self.title_hyperlink = self.hn_comments_url

        self.hostname_dict: dict = {}
        (
            self.hostname_dict["full"],
            self.hostname_dict["minus_www"],
        ) = utils_text.get_domains_from_url(url, log_prefix=log_prefix)

        self.hostname_dict["for_hn_search"] = ""  # may include path after hostname
        self.hostname_dict["for_display"] = ""
        self.hostname_dict["for_display_addl_class"] = ""
        self.hostname_dict["slug"] = ""
        utils_text.create_domains_slug(self.hostname_dict, log_prefix=log_prefix)

        self.title: str = title
        self.text: str = text
        self.descendants: int = descendants
        self.score: int = score

        self.time_of_last_firebaseio_query: int

        self.linked_url_reported_content_type: str = ""
        self.linked_url_confirmed_content_type: str = ""

        # og:image info
        self.og_image_url: str = None
        self.og_image_url_possibly_redirected: str = None
        self.og_image_content_type: str = None
        self.normalized_og_image_filename: str = None
        self.downloaded_orig_thumb_full_path: str = None
        self.downloaded_og_image_magic_result: str = None
        self.og_image_filename_details_from_url: Dict = {}
        self.thumb_aspect_hint: str = None

        self.og_image_is_inline_data: bool = False
        self.og_image_inline_data_srct: str = None
        self.og_image_inline_data_decoded_local_path: str = None

        # for download_og_image2()
        self.og_image_dict: Dict[str, str] = {}
        self.og_image_dict["og_image_url"] = None
        self.og_image_dict["og_image_url_possibly_redirected"] = None
        self.og_image_dict["og_image_content_type"] = None
        self.og_image_dict["normalized_og_image_filename"] = None
        self.og_image_dict["downloaded_orig_thumb_full_path"] = None
        self.og_image_dict["downloaded_og_image_magic_result"] = None
        self.og_image_dict["og_image_filename_details_from_url"] = None
        self.og_image_dict["thumb_aspect_hint"] = None

        # outbound link info
        self.story_content_type_slug: str = ""

        # outbound links to GitHub repos
        self.linked_url_github_langs_inner_html: str = ""
        self.gh_repo_lang_stats: str = ""
        self.github_languages_slug: str = ""

        # social-media account details
        self.social_media = {}
        self.social_media["account_name_url"] = ""
        self.social_media["account_name_display"] = ""
        self.social_media["nowrap_class"] = ""
        self.social_media["account_url"] = ""
        self.social_media["account_name_slug"] = ""
        self.social_media["hn_search_query"] = ""

        # html story card caches
        self.image_slug: str = ""
        self.badges_slug: str = ""
        self.story_card_html: str = ""

        # what kind of content is at outbound link
        self.outbound_link_to_binary: bool = False
        self.outbound_link_to_html: bool = False

        # outbound link to PDF
        self.pdf_page_count: int = 0

        # info about textual content at outbound link
        self.reading_time: int = None
        self.is_wellformed_xml: bool = False
        self.declared_root_element: str = None

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
