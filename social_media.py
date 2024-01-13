import logging
import sys
from collections import Counter

import requests
import urllib3
from bs4 import BeautifulSoup

import config
import my_drivers
import my_secrets
import retrieve_by_url
import text_utils

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


VIDEO_CAMERA_SYMBOL = "🎥"
MICROPHONE_SYMBOL = "🎙️"
MUSIC_SYMBOL = "🎵"
VIDEO_GAME_SYMBOL = "🎮"
STILL_CAMERA_SYMBOL = "📷"
PENCIL_SYMBOL = "✍"
KEYBOARD_SYMBOL = "⌨️"
# BIRD_SYMBOL = '🐦'
SILHOUETTE_SYMBOL = "👤"
ARTICLE_SYMBOL = "📄"


def check_for_social_media_details(
    driver=None, story_as_object=None, page_source_soup=None
):
    #
    # arstechnica.com
    #
    if story_as_object.hostname["minus_www"] == "arstechnica.com":
        story_as_object.social_media[
            "account_name_slug"
        ] = get_arstechnica_account_slug(
            arstechnica_url=story_as_object.url,
            story_as_object=story_as_object,
            page_source_soup=page_source_soup,
        )

        if story_as_object.social_media["account_name_slug"]:
            story_as_object.hostname["slug"] += story_as_object.social_media[
                "account_name_slug"
            ]

    #
    # bloomberg.com
    #
    elif story_as_object.hostname["minus_www"] == "bloomberg.com":
        story_as_object.social_media["account_name_slug"] = get_bloomberg_account_slug(
            bloomberg_url=story_as_object.url,
            story_as_object=story_as_object,
            page_source_soup=page_source_soup,
        )

        if story_as_object.social_media["account_name_slug"]:
            story_as_object.hostname["slug"] += story_as_object.social_media[
                "account_name_slug"
            ]

    #
    # github.com
    #
    elif story_as_object.hostname["minus_www"] == "github.com":
        story_as_object.social_media["account_name_slug"] = get_github_account_slug(
            story_as_object.url, story_as_object=story_as_object
        )

        if story_as_object.social_media["account_name_slug"]:
            story_as_object.hostname[
                "slug"
            ] = f'<a class="domains-for-search{story_as_object.hostname["for_display_addl_class"]}" href="https://news.ycombinator.com/from?site={story_as_object.social_media["hn_search_query"]}">({story_as_object.hostname["for_display"]})</a>'
            story_as_object.hostname["slug"] += story_as_object.social_media[
                "account_name_slug"
            ]

        story_as_object.gh_repo_lang_stats = text_utils.EMPTY_STRING
        a_data_pjax_repo = page_source_soup.find(
            "a", {"data-pjax": "#repo-content-pjax-container"}
        )
        if a_data_pjax_repo and a_data_pjax_repo.has_attr("href"):
            repo_url_path = a_data_pjax_repo["href"]
            repo_url = f"https://github.com{repo_url_path}"
            gh_repo_lang_stats = get_github_repo_languages(
                driver=driver, repo_url=repo_url
            )
            if gh_repo_lang_stats:
                story_as_object.gh_repo_lang_stats = gh_repo_lang_stats
                create_github_languages_slug(story_as_object)

    #
    # gist.github.com
    #
    elif story_as_object.hostname["minus_www"] == "gist.github.com":
        story_as_object.social_media[
            "account_name_slug"
        ] = get_github_gist_account_slug(
            github_gist_url=story_as_object.url,
            story_as_object=story_as_object,
            page_source_soup=page_source_soup,
        )

        if story_as_object.social_media["account_name_slug"]:
            story_as_object.hostname["slug"] += story_as_object.social_media[
                "account_name_slug"
            ]

    #
    # theguardian.com
    #
    # elif story_as_object.hostname["minus_www"] == "theguardian.com":
    #     story_as_object.social_media[
    #         "account_name_slug"
    #     ] = get_theguardian_account_slug(
    #         theguardian_url=story_as_object.url,
    #         story_as_object=story_as_object,
    #         page_source_soup=page_source_soup,
    #     )

    #     if story_as_object.social_media["account_name_slug"]:
    #         story_as_object.hostname["slug"] += story_as_object.social_media[
    #             "account_name_slug"
    #         ]

    #
    # linkedin.com
    #
    elif story_as_object.hostname["minus_www"].endswith("linkedin.com"):  # TODO
        pass
    #
    # medium.com
    #
    elif story_as_object.hostname["minus_www"].endswith("medium.com"):
        story_as_object.social_media["account_name_slug"] = get_medium_account_slug(
            story_as_object.url, story_as_object
        )

        if story_as_object.social_media["account_name_slug"]:
            story_as_object.hostname[
                "slug"
            ] = f'<a class="domains-for-search{story_as_object.hostname["for_display_addl_class"]}" href="https://news.ycombinator.com/from?site={story_as_object.social_media["hn_search_query"]}">({story_as_object.hostname["for_display"]})</a>'
            story_as_object.hostname["slug"] += story_as_object.social_media[
                "account_name_slug"
            ]

    #
    # nytimes.org
    #
    elif story_as_object.hostname["minus_www"].endswith("nytimes.com"):
        story_as_object.social_media["account_name_slug"] = get_nytimes_article_slug(
            nytimes_url=story_as_object.url,
            story_as_object=story_as_object,
            page_source_soup=page_source_soup,
        )

        if story_as_object.social_media["account_name_slug"]:
            story_as_object.hostname["slug"] += story_as_object.social_media[
                "account_name_slug"
            ]

    #
    # reddit.com
    #
    elif story_as_object.hostname["minus_www"].endswith(
        "reddit.com"
    ):  # endswith, so we get `old.reddit.com` too
        story_as_object.social_media["account_name_slug"] = get_reddit_account_slug(
            story_as_object.url, story_as_object
        )

        if story_as_object.social_media["account_name_slug"]:
            story_as_object.hostname[
                "slug"
            ] = f'<a class="domains-for-search{story_as_object.hostname["for_display_addl_class"]}" href="https://news.ycombinator.com/from?site={story_as_object.social_media["hn_search_query"]}">({story_as_object.hostname["for_display"]})</a>'
            story_as_object.hostname["slug"] += story_as_object.social_media[
                "account_name_slug"
            ]
    #
    # substack.com
    #
    elif story_as_object.hostname["minus_www"].endswith("substack.com"):
        if story_as_object.hostname["minus_www"].count(".") == 2:  # i.e., no subdomain
            story_as_object.social_media[
                "account_name_slug"
            ] = get_substack_account_slug(story_as_object.url, story_as_object)

            if story_as_object.social_media["account_name_slug"]:
                story_as_object.hostname[
                    "slug"
                ] = f'<a class="domains-for-search{story_as_object.hostname["for_display_addl_class"]}" href="https://news.ycombinator.com/from?site={story_as_object.social_media["hn_search_query"]}">({story_as_object.hostname["for_display"]})</a>'
                story_as_object.hostname["slug"] += story_as_object.social_media[
                    "account_name_slug"
                ]

        meta_name_author = page_source_soup.find("head meta", {"name": "author"})
        if meta_name_author and meta_name_author.has_attr("content"):
            story_as_object.social_media["account_name_display"] = meta_name_author[
                "content"
            ]

    #
    # techcrunch.com
    #
    elif story_as_object.hostname["minus_www"] == "techcrunch.com":
        story_as_object.social_media["account_name_slug"] = get_techcrunch_account_slug(
            techcrunch_url=story_as_object.url,
            story_as_object=story_as_object,
            page_source_soup=page_source_soup,
        )

        if story_as_object.social_media["account_name_slug"]:
            story_as_object.hostname["slug"] += story_as_object.social_media[
                "account_name_slug"
            ]

    #
    # twitter.com
    #
    elif story_as_object.hostname["minus_www"] == "twitter.com":
        story_as_object.social_media["account_name_slug"] = get_twitter_account_slug(
            story_as_object.url, story_as_object=story_as_object
        )

        if story_as_object.social_media["account_name_slug"]:
            story_as_object.hostname[
                "slug"
            ] = f'<a class="domains-for-search{story_as_object.hostname["for_display_addl_class"]}" href="https://news.ycombinator.com/from?site={story_as_object.social_media["hn_search_query"]}">({story_as_object.hostname["for_display"]})</a>'
            story_as_object.hostname["slug"] += story_as_object.social_media[
                "account_name_slug"
            ]

    #
    # wikipedia.org
    #
    elif story_as_object.hostname["minus_www"].endswith("wikipedia.org"):
        story_as_object.social_media["account_name_slug"] = get_wikipedia_article_slug(
            wikipedia_url=story_as_object.url,
            story_as_object=story_as_object,
            page_source_soup=page_source_soup,
        )

        if story_as_object.social_media["account_name_slug"]:
            # story_as_object.hostname[
            #     "slug"
            # ] = f'<a class="domains-for-search{story_as_object.hostname["for_display_addl_class"]}" href="https://news.ycombinator.com/from?site={story_as_object.social_media["hn_search_query"]}">({story_as_object.hostname["for_display"]})</a>'

            story_as_object.hostname["slug"] += story_as_object.social_media[
                "account_name_slug"
            ]

    #
    # youtube.com
    #
    elif story_as_object.hostname["minus_www"] == "youtube.com":
        story_as_object.social_media["account_name_slug"] = get_youtube_channel_slug(
            story_as_object.url, story_as_object=story_as_object
        )

        # note: HN search stores youtube.com links without channel info, so no need to update domains_slug
        if story_as_object.social_media["account_name_slug"]:
            story_as_object.hostname["slug"] += story_as_object.social_media[
                "account_name_slug"
            ]


def check_if_nowrap_needed(account_name: str):
    if len(account_name) <= 22:
        return " nowrap"
    else:
        return text_utils.EMPTY_STRING


def get_arstechnica_account_slug(
    arstechnica_url=None, story_as_object=None, page_source_soup=None
):
    author_display_name = None
    author_link = None

    a_els = page_source_soup.select("a")
    for each_a in a_els:
        if each_a.has_attr("rel"):
            if each_a["rel"] == "author":
                span_els = each_a.select("span")
                for each_span in span_els:
                    if each_span.has_attr("itemprop"):
                        if each_span["itemprop"] == "name":
                            author_display_name = each_span.text
                            if each_a.has_attr("href"):
                                author_link = each_a["href"]
                            break

    if not author_display_name:
        logger.warning(
            f"id {story_as_object.id}: could not find arstechnica author name"
        )
        return text_utils.EMPTY_STRING

    logger.info(f"id {story_as_object.id}: arstechnica author is {author_display_name}")

    if author_link:
        author_slug = f'<a href="{author_link}">{author_display_name}</a>'
    else:
        author_slug = f"{author_display_name}"

    nowrap_class = check_if_nowrap_needed(author_display_name)

    account_name_slug = (
        "<br/>"
        f'<span class="social-media-account-name{nowrap_class}">'
        f'<span class="social-media-account-emoji">{SILHOUETTE_SYMBOL}</span>'
        f"{author_slug}"
        "</span>"
    )

    if story_as_object:
        story_as_object.social_media["account_name_url"] = author_link
        story_as_object.social_media["account_name_display"] = author_display_name
        story_as_object.social_media["nowrap_class"] = nowrap_class
        story_as_object.social_media["account_url"] = author_link
        story_as_object.social_media["account_name_slug"] = account_name_slug

    return account_name_slug


def get_bloomberg_account_slug(
    bloomberg_url=None, story_as_object=None, page_source_soup=None
):
    author_display_name = None
    author_link = None

    a_els = page_source_soup.select("a")
    for each_a in a_els:
        if each_a.has_attr("rel"):
            if each_a["rel"] == "author":
                author_display_name = each_a.text
                if each_a.has_attr("href"):
                    author_link = each_a["href"]
                break

    if not author_display_name:
        logger.warning(f"id {story_as_object.id}: could not find bloomberg author name")
        return text_utils.EMPTY_STRING

    logger.info(f"id {story_as_object.id}: bloomberg author is {author_display_name}")

    if author_link:
        author_slug = f'<a href="{author_link}">{author_display_name}</a>'
    else:
        author_slug = f"{author_display_name}"

    nowrap_class = check_if_nowrap_needed(author_display_name)

    account_name_slug = (
        "<br/>"
        f'<span class="social-media-account-name{nowrap_class}">'
        f'<span class="social-media-account-emoji">{SILHOUETTE_SYMBOL}</span>'
        f"{author_slug}"
        "</span>"
    )

    if story_as_object:
        story_as_object.social_media["account_name_url"] = author_link
        story_as_object.social_media["account_name_display"] = author_display_name
        story_as_object.social_media["nowrap_class"] = nowrap_class
        story_as_object.social_media["account_url"] = author_link
        story_as_object.social_media["account_name_slug"] = account_name_slug

    return account_name_slug


def get_github_account_slug(github_url: str, story_as_object=None):
    account_name_url = text_utils.get_text_between(
        "github.com/",
        "/",
        github_url,
        okay_to_elide_right_pattern=True,
        force_lowercase=True,
    )

    if not account_name_url:
        return text_utils.EMPTY_STRING

    account_url = f"https://www.github.com/{account_name_url}"
    nowrap_class = check_if_nowrap_needed(account_name_url)
    hn_search_query = f"github.com/{account_name_url}"

    account_name_slug = f"<br/><span class='social-media-account-name{nowrap_class}'><a href='{account_url}'><span class='social-media-account-emoji'>{SILHOUETTE_SYMBOL}</span>{account_name_url}</a></span>"

    if story_as_object:
        story_as_object.social_media["account_name_url"] = account_name_url
        story_as_object.social_media["account_name_display"] = account_name_url
        story_as_object.social_media["nowrap_class"] = nowrap_class
        story_as_object.social_media["account_url"] = account_url
        story_as_object.social_media["account_name_slug"] = account_name_slug
        story_as_object.social_media["hn_search_query"] = hn_search_query

    return account_name_slug


def get_github_gist_account_slug(
    github_gist_url=None, story_as_object=None, page_source_soup=None
):
    author_handle = None
    author_link = None

    a_els = page_source_soup.select("a")
    for each_a in a_els:
        if each_a.has_attr("data-hovercard-type"):
            data_hovercard_type_val = each_a["data-hovercard-type"]
            if data_hovercard_type_val == "user":
                author_handle = each_a.text
                author_link = f'https://gist.github.com/{each_a["href"]}'

    if not author_handle:
        logger.warning(
            f"id {story_as_object.id}: could not find github gist author name"
        )
        return text_utils.EMPTY_STRING

    nowrap_class = check_if_nowrap_needed(author_handle)

    account_name_slug = (
        "<br/>"
        f'<span class="social-media-account-name{nowrap_class}">'
        f'<span class="social-media-account-emoji">{SILHOUETTE_SYMBOL}</span>'
        f'<a href="{author_link}">'
        f"{author_handle}"
        f"</a>"
        "</span>"
    )

    if story_as_object:
        story_as_object.social_media["account_name_url"] = author_link
        story_as_object.social_media["account_name_display"] = author_handle
        story_as_object.social_media["nowrap_class"] = nowrap_class
        story_as_object.social_media["account_url"] = author_link
        story_as_object.social_media["account_name_slug"] = account_name_slug

    return account_name_slug


def create_github_languages_slug(story_as_object):
    if not story_as_object.gh_repo_lang_stats:
        return text_utils.EMPTY_STRING

    languages_list = []
    for ld in story_as_object.gh_repo_lang_stats:
        this_lang = f'<div class="each-lang"><div class="lang-dot" style="color: {ld[2]}">⬤</div><div class="lang-name-and-percentage"><div class="lang-name">&nbsp;{ld[0]}</div><div class="lang-percentage">&nbsp;{ld[1]}</div></div></div>'
        languages_list.append(this_lang)

    languages_list[-1] = languages_list[-1].replace("class=", 'id="#final-lang" class=')
    story_as_object.github_languages_slug = (
        f'<tr><td><div class="languages-bar">{"".join(languages_list)}</div></td></tr>'
    )


def get_github_repo_languages(driver=None, repo_url=None):
    page_source = retrieve_by_url.get_page_source_noproxy(driver=driver, url=repo_url)

    soup = BeautifulSoup(page_source, "html.parser")
    h2_languages = soup.find("h2", text="Languages")

    if h2_languages:
        ul_languages = h2_languages.find_next_sibling("ul")
        if not ul_languages:
            logger.info(
                f"{sys._getframe(  ).f_code.co_name}: couldn't get GH repo lang stats from {repo_url}"
            )
            return None
        gh_repo_lang_stats = []
        li_els = ul_languages.find_all("li")
        for each_li in li_els:
            """
            (lang_name, percent, color)
            """
            lang_name = ""
            lang_percent = ""
            lang_color = ""
            for each_span in each_li.find_all("span"):
                if (
                    each_span.has_attr("class")
                    and "color-fg-default" in each_span["class"]
                ):
                    lang_name = each_span.text
                if each_span.text.endswith("%"):
                    lang_percent = each_span.text
            lang_color = each_li.find("svg")["style"][6:-1].upper()
            gh_repo_lang_stats.append((lang_name, lang_percent, lang_color))
        logger.info(
            f"{sys._getframe(  ).f_code.co_name}: got GH repo lang stats from {repo_url}"
        )
        return gh_repo_lang_stats
    else:
        logger.warning(f"couldn't find h2_languages on url {repo_url}")


def get_theguardian_account_slug(
    theguardian_url=None, story_as_object=None, page_source_soup=None
):
    author_display_name = None
    author_link = None

    # TODO: not currently working correctly.

    a_els = page_source_soup.select("a")
    # logger.info(f"guardian a_els: {a_els}")
    for each_a in a_els:
        # logger.info(f"guardian each_a: {each_a}")
        if each_a.has_attr("rel"):
            if each_a["rel"] == "author":
                logger.info(f"guardian each_a.text: {each_a.text}")
                author_display_name = each_a.text
                if each_a.has_attr("href"):
                    author_link = each_a["href"]
                    logger.info(f'guardian each_a.href: {each_a["href"]}')
                break

    if not author_display_name:
        logger.warning(
            f"id {story_as_object.id}: could not find theguardian author name"
        )
        return text_utils.EMPTY_STRING

    logger.info(f"id {story_as_object.id}: theguardian author is {author_display_name}")

    if author_link:
        author_slug = f'<a href="{author_link}">{author_display_name}</a>'
    else:
        author_slug = f"{author_display_name}"

    nowrap_class = check_if_nowrap_needed(author_display_name)

    account_name_slug = (
        "<br/>"
        f'<span class="social-media-account-name{nowrap_class}">'
        f'<span class="social-media-account-emoji">{SILHOUETTE_SYMBOL}</span>'
        f"{author_slug}"
        "</span>"
    )

    if story_as_object:
        story_as_object.social_media["account_name_url"] = author_link
        story_as_object.social_media["account_name_display"] = author_display_name
        story_as_object.social_media["nowrap_class"] = nowrap_class
        story_as_object.social_media["account_url"] = author_link
        story_as_object.social_media["account_name_slug"] = account_name_slug

    return account_name_slug


def get_medium_account_slug(medium_url, story_as_object):
    if story_as_object.hostname["minus_www"].count(".") >= 2:
        domains_as_list = story_as_object.hostname["minus_www"].split(".")
        account_name_url = domains_as_list[-3]
        account_url = f"https://{domains_as_list[-3]}.medium.com"
        at_sign_slug = ""
        hn_search_query = f"{domains_as_list[-3]}.medium.com"
    elif "medium.com/@" in medium_url:
        account_name_url = text_utils.get_text_between(
            "medium.com/@",
            "/",
            medium_url,
            okay_to_elide_right_pattern=True,
            force_lowercase=True,
        )
        account_url = f"https://www.medium.com/@{account_name_url}"
        at_sign_slug = "@"
        hn_search_query = f"medium.com/{account_name_url}"
    else:
        account_name_url = text_utils.get_text_between(
            "medium.com/", "/", medium_url, okay_to_elide_right_pattern=True
        )
        account_url = f"https://www.medium.com/{account_name_url}"
        at_sign_slug = ""
        hn_search_query = f"medium.com/{account_name_url}".lower()

    if not account_name_url:
        return text_utils.EMPTY_STRING

    nowrap_class = check_if_nowrap_needed(account_name_url)

    if at_sign_slug:
        at_sign_slug = "<span class='social-media-account-atsign'>@</span>"

    account_name_slug = f"<br/><span class='social-media-account-name{nowrap_class}'><a href='{account_url}'><span class='social-media-account-emoji'>{SILHOUETTE_SYMBOL}</span>{at_sign_slug}{account_name_url}</a></span>"

    if story_as_object:
        story_as_object.social_media["account_name_url"] = account_name_url
        story_as_object.social_media[
            "account_name_display"
        ] = account_name_url  # TODO: find a display name?
        story_as_object.social_media["nowrap_class"] = nowrap_class
        story_as_object.social_media["account_url"] = account_url
        story_as_object.social_media["account_name_slug"] = account_name_slug
        story_as_object.social_media["hn_search_query"] = hn_search_query

    return account_name_slug


def get_nytimes_article_slug(
    nytimes_url=None, story_as_object=None, page_source_soup=None
):
    author_accumulator = []
    a_els = page_source_soup.select("a")
    for each_a in a_els:
        if each_a.has_attr("href"):
            if "nytimes.com/by/" in each_a["href"] and each_a.text:
                if not "More about" in each_a.text:
                    author_accumulator.append(
                        (each_a.text.replace(" ", "&nbsp;"), each_a["href"])
                    )
    if not author_accumulator:
        logger.info(
            f"id {story_as_object.id}: could not determine nytimes article authors"
        )
        return text_utils.EMPTY_STRING

    author_slug = ", ".join(
        [
            f'<a href="{each_author[1]}">{each_author[0]}</a>'
            for each_author in author_accumulator
        ]
    )

    # nowrap_class = check_if_nowrap_needed(article_author)

    account_name_slug = (
        "<br/>"
        f'<span class="social-media-account-name">'
        f'<span class="social-media-account-emoji">{SILHOUETTE_SYMBOL}</span>'
        f"{author_slug}"
        "</span>"
    )

    if story_as_object:
        story_as_object.social_media["account_name_url"] = text_utils.EMPTY_STRING
        # story_as_object.social_media["account_name_display"] = article_author
        # story_as_object.social_media["nowrap_class"] = nowrap_class
        story_as_object.social_media["account_url"] = text_utils.EMPTY_STRING
        story_as_object.social_media["account_name_slug"] = account_name_slug

    return account_name_slug


def get_reddit_account_slug(reddit_url, story_as_object):
    if "reddit.com/r/" not in reddit_url:
        return text_utils.EMPTY_STRING

    subreddit_name_url = text_utils.get_text_between(
        "reddit.com/r/", "/", reddit_url, okay_to_elide_right_pattern=True
    )

    if not subreddit_name_url:
        return text_utils.EMPTY_STRING

    subreddit_url = f"https://old.reddit.com/r/{subreddit_name_url}"
    nowrap_class = check_if_nowrap_needed(subreddit_name_url)
    hn_search_query = "reddit.com"

    account_name_slug = f"<br/><span class='social-media-account-name{nowrap_class}'><a href='{subreddit_url}'>r/{subreddit_name_url}</a></span>"

    if story_as_object:
        story_as_object.social_media["account_name_url"] = subreddit_name_url
        story_as_object.social_media["account_name_display"] = subreddit_name_url
        story_as_object.social_media["nowrap_class"] = nowrap_class
        story_as_object.social_media["account_url"] = subreddit_url
        story_as_object.social_media["account_name_slug"] = account_name_slug
        story_as_object.social_media["hn_search_query"] = hn_search_query

    return account_name_slug


def get_substack_account_slug(substack_url, story_as_object):
    account_name_url = story_as_object.hostname["minus_www"].split(".")[0]

    if not account_name_url:
        return text_utils.EMPTY_STRING

    nowrap_class = check_if_nowrap_needed(account_name_url)
    account_url = f"https://{story_as_object.hostname['minus_www']}"
    hn_search_query = story_as_object.hostname["minus_www"]

    account_name_slug = f"<br/><span class='social-media-account-name{nowrap_class}'><a href='{account_url}'><span class='social-media-account-emoji'>{SILHOUETTE_SYMBOL}</span>{account_name_url}</a></span>"

    if story_as_object:
        story_as_object.social_media["account_name_url"] = account_name_url
        story_as_object.social_media["nowrap_class"] = nowrap_class
        story_as_object.social_media["account_url"] = account_name_url
        story_as_object.social_media["account_name_slug"] = account_name_slug
        story_as_object.social_media["hn_search_query"] = hn_search_query

    return account_name_slug


def get_techcrunch_account_slug(
    techcrunch_url=None, story_as_object=None, page_source_soup=None
):
    author_display_name = None
    author_link = None

    # get author display name
    meta_els = page_source_soup.select("meta")
    for each_meta in meta_els:
        if each_meta.has_attr("name"):
            if each_meta["name"] == "author":
                author_display_name = each_meta["content"]
                break

    if not author_display_name:
        logger.warning(
            f"id {story_as_object.id}: could not find techcrunch author name"
        )
        return text_utils.EMPTY_STRING

    a_els = page_source_soup.select("a")
    for each_a in a_els:
        if each_a.has_attr("href"):
            if each_a["href"].startswith("/author/"):
                if each_a.text == author_display_name:
                    author_link = f'https://techcrunch.com{each_a["href"]}/'

    nowrap_class = check_if_nowrap_needed(author_display_name)

    account_name_slug = (
        "<br/>"
        f'<span class="social-media-account-name{nowrap_class}">'
        f'<span class="social-media-account-emoji">{SILHOUETTE_SYMBOL}</span>'
        f'<a href="{author_link}">'
        f"{author_display_name}"
        f"</a>"
        "</span>"
    )

    if story_as_object:
        story_as_object.social_media["account_name_url"] = author_link
        story_as_object.social_media["account_name_display"] = author_display_name
        story_as_object.social_media["nowrap_class"] = nowrap_class
        story_as_object.social_media["account_url"] = author_link
        story_as_object.social_media["account_name_slug"] = account_name_slug

    return account_name_slug


def get_twitter_account_slug(twitter_url: str, story_as_object=None):
    if "/events/" in twitter_url:
        return text_utils.EMPTY_STRING

    if "/spaces/" in twitter_url:
        return text_utils.EMPTY_STRING

    account_name_url = text_utils.get_text_between(
        "twitter.com/", "/status/", twitter_url, okay_to_elide_right_pattern=True
    )

    if not account_name_url:
        return text_utils.EMPTY_STRING

    account_url = f"https://www.twitter.com/{account_name_url}"
    nowrap_class = check_if_nowrap_needed(account_name_url)
    hn_search_query = f"twitter.com/{account_name_url}"

    account_name_slug = f"<br/><span class='social-media-account-name{nowrap_class}'><a href='{account_url}'><span class='social-media-account-atsign'>@</span>{account_name_url}</a></span>"

    if story_as_object:
        story_as_object.social_media["account_name_url"] = account_name_url
        story_as_object.social_media["account_name_display"] = account_name_url
        story_as_object.social_media["nowrap_class"] = nowrap_class
        story_as_object.social_media["account_url"] = account_url
        story_as_object.social_media["account_name_slug"] = account_name_slug
        story_as_object.social_media["hn_search_query"] = hn_search_query

    return account_name_slug


def get_wikipedia_article_slug(
    wikipedia_url=None, story_as_object=None, page_source_soup=None
):
    article_title = None

    article_title_el = page_source_soup.select("span.mw-page-title-main")
    if article_title_el:
        logger.info(f"id {story_as_object.id}: found wikipedia article title")
        article_title = article_title_el[0].text
    else:
        logger.warning(
            f"id {story_as_object.id}: could not find wikipedia article title"
        )
        return text_utils.EMPTY_STRING

    nowrap_class = check_if_nowrap_needed(article_title)

    account_name_slug = (
        "<br/>"
        f'<span class="social-media-account-name{nowrap_class}">'
        f'<span class="social-media-account-emoji">{ARTICLE_SYMBOL}</span>'
        f"“{article_title}”"
        "</span>"
    )

    if story_as_object:
        story_as_object.social_media["account_name_url"] = text_utils.EMPTY_STRING
        story_as_object.social_media["account_name_display"] = article_title
        story_as_object.social_media["nowrap_class"] = nowrap_class
        story_as_object.social_media["account_url"] = text_utils.EMPTY_STRING
        story_as_object.social_media["account_name_slug"] = account_name_slug

    return account_name_slug


def get_youtube_channel_slug(youtube_url: str, story_as_object=None):
    if "youtube.com/watch?v=" in youtube_url:
        video_id = text_utils.get_text_between(
            "v=", "&", youtube_url, okay_to_elide_right_pattern=True
        )

        api_query_url = f"https://youtube.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={my_secrets.GOOGLE_API_KEY}"
        try:
            with requests.get(
                api_query_url,
                allow_redirects=True,
                verify=False,
                timeout=config.settings["SCRAPING"]["REQUESTS_GET_TIMEOUT_S"],
            ) as response:
                json = response.json()
                account_name = json["items"][0]["snippet"]["channelTitle"]
                channel_id = json["items"][0]["snippet"]["channelId"]
                account_url = f"https://www.youtube.com/channel/{channel_id}"
        except Exception as e:
            if story_as_object:
                logger.warning(
                    f"id {story_as_object.id}: error getting video details for YouTube URL {youtube_url}: {e}"
                )
            else:
                logger.warning(
                    f"error getting video details for YouTube URL {youtube_url}: {e}"
                )

            return text_utils.EMPTY_STRING

    elif "youtube.com/channel/" in youtube_url:
        channel_id = text_utils.get_text_between(
            "youtube.com/channel/",
            "?",
            youtube_url,
            okay_to_elide_right_pattern=True,
        )

        api_query_url = f"https://youtube.googleapis.com/youtube/v3/channels?part=snippet&id={channel_id}&key={my_secrets.GOOGLE_API_KEY}"
        try:
            with requests.get(
                api_query_url,
                allow_redirects=True,
                verify=False,
                timeout=config.settings["SCRAPING"]["REQUESTS_GET_TIMEOUT_S"],
            ) as response:
                json = response.json()
                account_name = json["items"][0]["snippet"]["title"]
                channel_id = json["items"][0]["snippet"]["channelId"]
                account_url = f"https://www.youtube.com/channel/{channel_id}"
        except Exception as e:
            if story_as_object:
                logger.warning(
                    f"id {story_as_object.id}: error getting channel details for YouTube URL {youtube_url}: {e}"
                )
            else:
                logger.warning(
                    f"error getting channel details for YouTube URL {youtube_url}: {e}"
                )

            return text_utils.EMPTY_STRING

    elif "youtube.com/playlist" in youtube_url:
        playlist_id = text_utils.get_text_between(
            "list=", "&", youtube_url, okay_to_elide_right_pattern=True
        )

        url = f"https://youtube.googleapis.com/youtube/v3/playlists?part=snippet&id={playlist_id}&key={my_secrets.GOOGLE_API_KEY}"
        try:
            with requests.get(
                url,
                allow_redirects=True,
                verify=False,
                timeout=config.settings["SCRAPING"]["REQUESTS_GET_TIMEOUT_S"],
            ) as response:
                json = response.json()
                account_name = json["items"][0]["snippet"]["title"]
                channel_id = json["items"][0]["snippet"]["channelId"]
                account_url = f"https://www.youtube.com/channel/{channel_id}"
        except Exception as e:
            if story_as_object:
                logger.warning(
                    f"id {story_as_object.id}: error getting playlist details for YouTube URL {youtube_url}: {e}"
                )
            else:
                logger.warning(
                    f"error getting playlist details for YouTube URL {youtube_url}: {e}"
                )
            return text_utils.EMPTY_STRING
    else:
        if story_as_object:
            logger.warning(
                f"id {story_as_object.id}: failed to understand format or structure of YouTube URL: {youtube_url}"
            )
        else:
            logger.warning(
                f"failed to understand format or structure of YouTube URL: {youtube_url}"
            )

        return text_utils.EMPTY_STRING

    if not account_name and not account_url:
        return text_utils.EMPTY_STRING

    nowrap_class = check_if_nowrap_needed(account_name)

    account_name_slug = f"<br/><span class='social-media-account-name{nowrap_class}'><a href='{account_url}'><span class='social-media-account-emoji'>{SILHOUETTE_SYMBOL}</span>{account_name}</a></span>"

    if story_as_object:
        story_as_object.social_media["account_name_url"] = channel_id
        story_as_object.social_media["account_name_display"] = account_name
        story_as_object.social_media["nowrap_class"] = nowrap_class
        story_as_object.social_media["account_url"] = account_url
        story_as_object.social_media["account_name_slug"] = account_name_slug

    return account_name_slug
