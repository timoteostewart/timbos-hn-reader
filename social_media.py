import logging

import requests
import urllib3
from bs4 import BeautifulSoup
from sortedcontainers import SortedSet

import config
import secrets_file
import utils_http
import utils_text

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

# TODO: 2023-10-10 17:27:20 CDT [new]     WARNING  id 37838129: failed to understand format or structure of YouTube URL: https://www.youtube.com/shorts/8l32HDWMvPg
# TODO: see /srv/timbos-hn-reader/temp/warnings5.txt for more YouTube parsing fails and gaps


def check_for_social_media_details(
    driver=None, story_object=None, page_source_soup=None
):
    # TODO: add more sites based on # https://hackernews-insight.vercel.app/domain-analysis

    #
    # arstechnica.com
    #
    if story_object.hostname_dict["minus_www"] == "arstechnica.com":
        story_object.social_media["account_name_slug"] = get_arstechnica_account_slug(
            arstechnica_url=story_object.url,
            story_object=story_object,
            page_source_soup=page_source_soup,
        )

        if story_object.social_media["account_name_slug"]:
            story_object.hostname_dict["slug"] += story_object.social_media[
                "account_name_slug"
            ]

    #
    # bloomberg.com
    #
    elif story_object.hostname_dict["minus_www"] == "bloomberg.com":
        story_object.social_media["account_name_slug"] = get_bloomberg_account_slug(
            bloomberg_url=story_object.url,
            story_object=story_object,
            page_source_soup=page_source_soup,
        )

        if story_object.social_media["account_name_slug"]:
            story_object.hostname_dict["slug"] += story_object.social_media[
                "account_name_slug"
            ]

    #
    # github.com
    #
    elif story_object.hostname_dict["minus_www"] == "github.com":
        story_object.social_media["account_name_slug"] = get_github_account_slug(
            story_object.url, story_object=story_object
        )

        if story_object.social_media["account_name_slug"]:
            story_object.hostname_dict["slug"] = (
                f'<a class="domains-for-search{story_object.hostname_dict["for_display_addl_class"]}" href="https://news.ycombinator.com/from?site={story_object.social_media["hn_search_query"]}">({story_object.hostname_dict["for_display"]})</a>'
            )
            story_object.hostname_dict["slug"] += story_object.social_media[
                "account_name_slug"
            ]

        story_object.gh_repo_lang_stats = ""
        a_data_pjax_repo = page_source_soup.find(
            "a", {"data-pjax": "#repo-content-pjax-container"}
        )
        if a_data_pjax_repo and a_data_pjax_repo.has_attr("href"):
            repo_url_path = a_data_pjax_repo["href"]
            repo_url = f"https://github.com{repo_url_path}"
            gh_repo_lang_stats = get_github_repo_languages(
                driver=driver,
                repo_url=repo_url,
                story_id=story_object.id,
            )
            if gh_repo_lang_stats:
                story_object.gh_repo_lang_stats = gh_repo_lang_stats
                create_github_languages_slug(story_object)

    #
    # gist.github.com
    #
    elif story_object.hostname_dict["minus_www"] == "gist.github.com":
        story_object.social_media["account_name_slug"] = get_github_gist_account_slug(
            github_gist_url=story_object.url,
            story_object=story_object,
            page_source_soup=page_source_soup,
        )

        if story_object.social_media["account_name_slug"]:
            story_object.hostname_dict["slug"] += story_object.social_media[
                "account_name_slug"
            ]

    #
    # theguardian.com
    #
    # elif story_object.hostname_dict["minus_www"] == "theguardian.com":
    #     story_object.social_media[
    #         "account_name_slug"
    #     ] = get_theguardian_account_slug(
    #         theguardian_url=story_object.url,
    #         story_object=story_object,
    #         page_source_soup=page_source_soup,
    #     )

    #     if story_object.social_media["account_name_slug"]:
    #         story_object.hostname_dict["slug"] += story_object.social_media[
    #             "account_name_slug"
    #         ]

    #
    # linkedin.com
    #
    elif story_object.hostname_dict["minus_www"].endswith("linkedin.com"):  # TODO
        pass
    #
    # medium.com
    #
    elif story_object.hostname_dict["minus_www"].endswith("medium.com"):
        story_object.social_media["account_name_slug"] = get_medium_account_slug(
            story_object.url, story_object
        )

        if story_object.social_media["account_name_slug"]:
            story_object.hostname_dict["slug"] = (
                f'<a class="domains-for-search{story_object.hostname_dict["for_display_addl_class"]}" href="https://news.ycombinator.com/from?site={story_object.social_media["hn_search_query"]}">({story_object.hostname_dict["for_display"]})</a>'
            )
            story_object.hostname_dict["slug"] += story_object.social_media[
                "account_name_slug"
            ]

    #
    # nytimes.org
    #
    elif story_object.hostname_dict["minus_www"].endswith("nytimes.com"):
        story_object.social_media["account_name_slug"] = get_nytimes_article_slug(
            nytimes_url=story_object.url,
            story_object=story_object,
            page_source_soup=page_source_soup,
        )

        if story_object.social_media["account_name_slug"]:
            story_object.hostname_dict["slug"] += story_object.social_media[
                "account_name_slug"
            ]

    #
    # reddit.com
    #
    elif story_object.hostname_dict["minus_www"].endswith(
        "reddit.com"
    ):  # endswith, so we get `old.reddit.com` too
        story_object.social_media["account_name_slug"] = get_reddit_account_slug(
            story_object.url, story_object
        )

        if story_object.social_media["account_name_slug"]:
            story_object.hostname_dict["slug"] = (
                f'<a class="domains-for-search{story_object.hostname_dict["for_display_addl_class"]}" href="https://news.ycombinator.com/from?site={story_object.social_media["hn_search_query"]}">({story_object.hostname_dict["for_display"]})</a>'
            )
            story_object.hostname_dict["slug"] += story_object.social_media[
                "account_name_slug"
            ]
    #
    # substack.com
    #
    elif story_object.hostname_dict["minus_www"].endswith("substack.com"):
        if (
            story_object.hostname_dict["minus_www"].count(".") == 2
        ):  # i.e., no subdomain
            story_object.social_media["account_name_slug"] = get_substack_account_slug(
                story_object.url, story_object
            )

            if story_object.social_media["account_name_slug"]:
                story_object.hostname_dict["slug"] = (
                    f'<a class="domains-for-search{story_object.hostname_dict["for_display_addl_class"]}" href="https://news.ycombinator.com/from?site={story_object.social_media["hn_search_query"]}">({story_object.hostname_dict["for_display"]})</a>'
                )
                story_object.hostname_dict["slug"] += story_object.social_media[
                    "account_name_slug"
                ]

        meta_name_author = page_source_soup.find("head meta", {"name": "author"})
        if meta_name_author and meta_name_author.has_attr("content"):
            story_object.social_media["account_name_display"] = meta_name_author[
                "content"
            ]

    #
    # techcrunch.com
    #
    elif story_object.hostname_dict["minus_www"] == "techcrunch.com":
        story_object.social_media["account_name_slug"] = get_techcrunch_account_slug(
            techcrunch_url=story_object.url,
            story_object=story_object,
            page_source_soup=page_source_soup,
        )

        if story_object.social_media["account_name_slug"]:
            story_object.hostname_dict["slug"] += story_object.social_media[
                "account_name_slug"
            ]

    #
    # twitter.com
    #
    elif story_object.hostname_dict["minus_www"] == "twitter.com":
        story_object.social_media["account_name_slug"] = get_twitter_account_slug(
            story_object.url, story_object=story_object
        )

        if story_object.social_media["account_name_slug"]:
            story_object.hostname_dict["slug"] = (
                f'<a class="domains-for-search{story_object.hostname_dict["for_display_addl_class"]}" href="https://news.ycombinator.com/from?site={story_object.social_media["hn_search_query"]}">({story_object.hostname_dict["for_display"]})</a>'
            )
            story_object.hostname_dict["slug"] += story_object.social_media[
                "account_name_slug"
            ]

    #
    # wsj.com
    #
    elif story_object.hostname_dict["minus_www"] == "wsj.com":
        story_object.social_media["account_name_slug"] = ""

        # if story_object.social_media["account_name_slug"]:
        #     story_object.hostname_dict["slug"] = (
        #         f'<a class="domains-for-search{story_object.hostname_dict["for_display_addl_class"]}" href="https://news.ycombinator.com/from?site={story_object.social_media["hn_search_query"]}">({story_object.hostname_dict["for_display"]})</a>'
        #     )
        #     story_object.hostname_dict["slug"] += story_object.social_media[
        #         "account_name_slug"
        #     ]

    #
    # wikipedia.org
    #
    elif story_object.hostname_dict["minus_www"].endswith("wikipedia.org"):
        story_object.social_media["account_name_slug"] = get_wikipedia_article_slug(
            wikipedia_url=story_object.url,
            story_object=story_object,
            page_source_soup=page_source_soup,
        )

        if story_object.social_media["account_name_slug"]:
            # story_object.hostname_dict[
            #     "slug"
            # ] = f'<a class="domains-for-search{story_object.hostname_dict["for_display_addl_class"]}" href="https://news.ycombinator.com/from?site={story_object.social_media["hn_search_query"]}">({story_object.hostname_dict["for_display"]})</a>'

            story_object.hostname_dict["slug"] += story_object.social_media[
                "account_name_slug"
            ]

    #
    # youtube.com
    #
    elif story_object.hostname_dict["minus_www"] == "youtube.com":
        story_object.social_media["account_name_slug"] = get_youtube_channel_slug(
            story_object.url, story_object=story_object
        )

        # note: HN search stores youtube.com links without channel info, so no need to update domains_slug
        if story_object.social_media["account_name_slug"]:
            story_object.hostname_dict["slug"] += story_object.social_media[
                "account_name_slug"
            ]


def check_if_nowrap_needed(account_name: str):
    if len(account_name) <= 22:
        return " nowrap"
    else:
        return ""


def get_arstechnica_account_slug(
    arstechnica_url=None, story_object=None, page_source_soup=None
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
        logger.info(f"id={story_object.id}: failed to find arstechnica author name")
        return ""

    logger.info(f"id={story_object.id}: arstechnica author is {author_display_name}")

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

    if story_object:
        story_object.social_media["account_name_url"] = author_link
        story_object.social_media["account_name_display"] = author_display_name
        story_object.social_media["nowrap_class"] = nowrap_class
        story_object.social_media["account_url"] = author_link
        story_object.social_media["account_name_slug"] = account_name_slug

    return account_name_slug


def get_bloomberg_account_slug(
    bloomberg_url=None, story_object=None, page_source_soup=None
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
        logger.info(f"id={story_object.id}: failed to find bloomberg author name")
        return ""

    logger.info(f"id={story_object.id}: bloomberg author is {author_display_name}")

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

    if story_object:
        story_object.social_media["account_name_url"] = author_link
        story_object.social_media["account_name_display"] = author_display_name
        story_object.social_media["nowrap_class"] = nowrap_class
        story_object.social_media["account_url"] = author_link
        story_object.social_media["account_name_slug"] = account_name_slug

    return account_name_slug


def get_github_account_slug(github_url: str, story_object=None):
    account_name_url = utils_text.get_text_between(
        "github.com/",
        "/",
        github_url,
        okay_to_elide_right_pattern=True,
        force_lowercase=True,
    )

    if not account_name_url:
        return ""

    account_url = f"https://www.github.com/{account_name_url}"
    nowrap_class = check_if_nowrap_needed(account_name_url)
    hn_search_query = f"github.com/{account_name_url}"

    account_name_slug = f"<br/><span class='social-media-account-name{nowrap_class}'><a href='{account_url}'><span class='social-media-account-emoji'>{SILHOUETTE_SYMBOL}</span>{account_name_url}</a></span>"

    if story_object:
        story_object.social_media["account_name_url"] = account_name_url
        story_object.social_media["account_name_display"] = account_name_url
        story_object.social_media["nowrap_class"] = nowrap_class
        story_object.social_media["account_url"] = account_url
        story_object.social_media["account_name_slug"] = account_name_slug
        story_object.social_media["hn_search_query"] = hn_search_query

    return account_name_slug


def get_github_gist_account_slug(
    github_gist_url=None, story_object=None, page_source_soup=None
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
        logger.info(f"id={story_object.id}: failed to find github gist author name")
        return ""

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

    if story_object:
        story_object.social_media["account_name_url"] = author_link
        story_object.social_media["account_name_display"] = author_handle
        story_object.social_media["nowrap_class"] = nowrap_class
        story_object.social_media["account_url"] = author_link
        story_object.social_media["account_name_slug"] = account_name_slug

    return account_name_slug


def create_github_languages_slug(story_object):
    if not story_object.gh_repo_lang_stats:
        return ""

    languages_list = []
    for ld in story_object.gh_repo_lang_stats:
        this_lang = f'<div class="each-lang"><div class="lang-dot" style="color: {ld[2]}">⬤</div><div class="lang-name-and-percentage"><div class="lang-name">&nbsp;{ld[0]}</div><div class="lang-percentage">&nbsp;{ld[1]}</div></div></div>'
        languages_list.append(this_lang)

    languages_list[-1] = languages_list[-1].replace("class=", 'id="#final-lang" class=')
    story_object.github_languages_slug = (
        f'<div class="languages-bar">{"".join(languages_list)}</div>'
    )


def get_github_repo_languages(driver=None, repo_url=None, story_id=None):
    log_prefix = f"id={story_id}: " if story_id else "n/a"

    page_source = utils_http.get_page_source(
        # driver=driver,
        url=repo_url,
        log_prefix=log_prefix,
    )

    if page_source:
        soup = BeautifulSoup(page_source, "html.parser")
        h2_languages = soup.find("h2", string="Languages")

        if h2_languages:
            ul_languages = h2_languages.find_next_sibling("ul")
            if not ul_languages:
                logger.info(
                    log_prefix + f"failed to get GH repo lang stats from {repo_url}"
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
            logger.info(log_prefix + f"got GH repo lang stats from {repo_url}")
            return gh_repo_lang_stats
        else:
            logger.info(log_prefix + f"failed to find h2_languages on url {repo_url}")
    else:
        logger.info(log_prefix + f"failed to read GH repo page  {repo_url}")


def get_theguardian_account_slug(
    theguardian_url=None, story_object=None, page_source_soup=None
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
        logger.info(f"id={story_object.id}: failed to find theguardian author name")
        return ""

    logger.info(f"id={story_object.id}: theguardian author is {author_display_name}")

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

    if story_object:
        story_object.social_media["account_name_url"] = author_link
        story_object.social_media["account_name_display"] = author_display_name
        story_object.social_media["nowrap_class"] = nowrap_class
        story_object.social_media["account_url"] = author_link
        story_object.social_media["account_name_slug"] = account_name_slug

    return account_name_slug


def get_medium_account_slug(medium_url, story_object):
    if story_object.hostname_dict["minus_www"].count(".") >= 2:
        domains_as_list = story_object.hostname_dict["minus_www"].split(".")
        account_name_url = domains_as_list[-3]
        account_url = f"https://{domains_as_list[-3]}.medium.com"
        at_sign_slug = ""
        hn_search_query = f"{domains_as_list[-3]}.medium.com"
    elif "medium.com/@" in medium_url:
        account_name_url = utils_text.get_text_between(
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
        account_name_url = utils_text.get_text_between(
            "medium.com/", "/", medium_url, okay_to_elide_right_pattern=True
        )
        account_url = f"https://www.medium.com/{account_name_url}"
        at_sign_slug = ""
        hn_search_query = f"medium.com/{account_name_url}".lower()

    if not account_name_url:
        return ""

    nowrap_class = check_if_nowrap_needed(account_name_url)

    if at_sign_slug:
        at_sign_slug = "<span class='social-media-account-atsign'>@</span>"

    account_name_slug = f"<br/><span class='social-media-account-name{nowrap_class}'><a href='{account_url}'><span class='social-media-account-emoji'>{SILHOUETTE_SYMBOL}</span>{at_sign_slug}{account_name_url}</a></span>"

    if story_object:
        story_object.social_media["account_name_url"] = account_name_url
        story_object.social_media["account_name_display"] = (
            account_name_url  # TODO: find a display name?
        )
        story_object.social_media["nowrap_class"] = nowrap_class
        story_object.social_media["account_url"] = account_url
        story_object.social_media["account_name_slug"] = account_name_slug
        story_object.social_media["hn_search_query"] = hn_search_query

    return account_name_slug


def get_nytimes_article_slug(
    nytimes_url=None, story_object=None, page_source_soup=None
):
    author_accumulator = []
    a_els = page_source_soup.select("a")
    authors_seen = set()
    for each_a in a_els:
        if each_a.has_attr("href"):
            if "nytimes.com/by/" in each_a["href"] and each_a.text:
                if not "More about" in each_a.text:
                    each_a_text = each_a.text.strip()
                    if each_a_text not in authors_seen:
                        authors_seen.add(each_a_text)
                        author_accumulator.append(
                            (each_a_text.replace(" ", "&nbsp;"), each_a["href"])
                        )
    if not author_accumulator:
        logger.info(f"id={story_object.id}: failed to determine nytimes article author")
        return ""

    logger.info(f"id={story_object.id}: {author_accumulator=}")

    author_accumulator = list(SortedSet(author_accumulator))

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

    if story_object:
        story_object.social_media["account_name_url"] = ""
        # story_object.social_media["account_name_display"] = article_author
        # story_object.social_media["nowrap_class"] = nowrap_class
        story_object.social_media["account_url"] = ""
        story_object.social_media["account_name_slug"] = account_name_slug

    return account_name_slug


def get_reddit_account_slug(reddit_url, story_object):
    if "reddit.com/r/" not in reddit_url:
        return ""

    subreddit_name_url = utils_text.get_text_between(
        "reddit.com/r/", "/", reddit_url, okay_to_elide_right_pattern=True
    )

    if not subreddit_name_url:
        return ""

    subreddit_url = f"https://old.reddit.com/r/{subreddit_name_url}"
    nowrap_class = check_if_nowrap_needed(subreddit_name_url)
    hn_search_query = "reddit.com"

    account_name_slug = f"<br/><span class='social-media-account-name{nowrap_class}'><a href='{subreddit_url}'>r/{subreddit_name_url}</a></span>"

    if story_object:
        story_object.social_media["account_name_url"] = subreddit_name_url
        story_object.social_media["account_name_display"] = subreddit_name_url
        story_object.social_media["nowrap_class"] = nowrap_class
        story_object.social_media["account_url"] = subreddit_url
        story_object.social_media["account_name_slug"] = account_name_slug
        story_object.social_media["hn_search_query"] = hn_search_query

    return account_name_slug


def get_substack_account_slug(substack_url, story_object):
    account_name_url = story_object.hostname_dict["minus_www"].split(".")[0]

    if not account_name_url:
        return ""

    nowrap_class = check_if_nowrap_needed(account_name_url)
    account_url = f"https://{story_object.hostname_dict['minus_www']}"
    hn_search_query = story_object.hostname_dict["minus_www"]

    account_name_slug = f"<br/><span class='social-media-account-name{nowrap_class}'><a href='{account_url}'><span class='social-media-account-emoji'>{SILHOUETTE_SYMBOL}</span>{account_name_url}</a></span>"

    if story_object:
        story_object.social_media["account_name_url"] = account_name_url
        story_object.social_media["nowrap_class"] = nowrap_class
        story_object.social_media["account_url"] = account_name_url
        story_object.social_media["account_name_slug"] = account_name_slug
        story_object.social_media["hn_search_query"] = hn_search_query

    return account_name_slug


def get_techcrunch_account_slug(
    techcrunch_url=None, story_object=None, page_source_soup=None
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
        logger.info(f"id={story_object.id}: failed to find techcrunch author name")
        return ""

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

    if story_object:
        story_object.social_media["account_name_url"] = author_link
        story_object.social_media["account_name_display"] = author_display_name
        story_object.social_media["nowrap_class"] = nowrap_class
        story_object.social_media["account_url"] = author_link
        story_object.social_media["account_name_slug"] = account_name_slug

    return account_name_slug


def get_twitter_account_slug(twitter_url: str, story_object=None):
    if "/events/" in twitter_url:
        return ""

    if "/spaces/" in twitter_url:
        return ""

    account_name_url = utils_text.get_text_between(
        "twitter.com/", "/status/", twitter_url, okay_to_elide_right_pattern=True
    )

    if not account_name_url:
        return ""

    account_url = f"https://www.twitter.com/{account_name_url}"
    nowrap_class = check_if_nowrap_needed(account_name_url)
    hn_search_query = f"twitter.com/{account_name_url}"

    account_name_slug = f"<br/><span class='social-media-account-name{nowrap_class}'><a href='{account_url}'><span class='social-media-account-atsign'>@</span>{account_name_url}</a></span>"

    if story_object:
        story_object.social_media["account_name_url"] = account_name_url
        story_object.social_media["account_name_display"] = account_name_url
        story_object.social_media["nowrap_class"] = nowrap_class
        story_object.social_media["account_url"] = account_url
        story_object.social_media["account_name_slug"] = account_name_slug
        story_object.social_media["hn_search_query"] = hn_search_query

    return account_name_slug


def get_wsj_account_slug(story_object=None, page_source_soup=None):
    author_display_name = None

    # <a href="https://www.wsj.com/news/author/rory-jones" aria-label="Author page for Rory Jones" class="css-tuctgt-AuthorLink e10pnb9y0">Rory Jones</a>

    el = page_source_soup.select_one('a[aria-label^="Author page for"]')
    if el:
        author_display_name = el.get_text()
        author_url = el.get("href") if "href" in el.attrs else ""
    else:
        logger.info(f"id={story_object.id}: failed to find wsj author name")
        return ""

    author_href_slug = (
        f'<a href="{author_url}">{author_display_name}</a>'
        if author_url
        else author_display_name
    )

    nowrap_class = check_if_nowrap_needed(author_display_name)

    account_name_slug = (
        "<br/>"
        f'<span class="social-media-account-name{nowrap_class}">'
        f'<span class="social-media-account-emoji">{SILHOUETTE_SYMBOL}</span>'
        f"{author_href_slug}"
        "</span>"
    )

    if story_object:
        story_object.social_media["account_name_url"] = author_url
        story_object.social_media["account_name_display"] = author_display_name
        story_object.social_media["nowrap_class"] = nowrap_class
        story_object.social_media["account_name_slug"] = account_name_slug

    return account_name_slug


def get_wikipedia_article_slug(
    wikipedia_url=None, story_object=None, page_source_soup=None
):
    article_title = None

    article_title_el = page_source_soup.select("span.mw-page-title-main")
    if article_title_el:
        logger.info(f"id={story_object.id}: found wikipedia article title")
        article_title = article_title_el[0].text
    else:
        logger.info(f"id={story_object.id}: failed to find wikipedia article title")
        return ""

    nowrap_class = check_if_nowrap_needed(article_title)

    account_name_slug = (
        "<br/>"
        f'<span class="social-media-account-name{nowrap_class}">'
        f'<span class="social-media-account-emoji">{ARTICLE_SYMBOL}</span>'
        f"“{article_title}”"
        "</span>"
    )

    if story_object:
        story_object.social_media["account_name_url"] = ""
        story_object.social_media["account_name_display"] = article_title
        story_object.social_media["nowrap_class"] = nowrap_class
        story_object.social_media["account_url"] = ""
        story_object.social_media["account_name_slug"] = account_name_slug

    return account_name_slug


def get_youtube_channel_slug(youtube_url: str, story_object=None):
    if "youtube.com/watch?v=" in youtube_url:
        video_id = utils_text.get_text_between(
            "v=", "&", youtube_url, okay_to_elide_right_pattern=True
        )

        # TODO: convert this to use my existing endpoint_query_via_requests() function
        api_query_url = f"https://youtube.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={secrets_file.google_api_key}"
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
        except Exception as exc:
            if story_object:
                logger.warning(
                    f"id={story_object.id}: failed to get video details for YouTube URL {youtube_url}: {exc}"
                )
            else:
                logger.warning(
                    f"failed to get video details for YouTube URL {youtube_url}: {exc}"
                )

            return ""

    elif "youtube.com/channel/" in youtube_url:
        channel_id = utils_text.get_text_between(
            "youtube.com/channel/",
            "?",
            youtube_url,
            okay_to_elide_right_pattern=True,
        )

        # TODO: convert this to use my existing endpoint_query_via_requests() function
        api_query_url = f"https://youtube.googleapis.com/youtube/v3/channels?part=snippet&id={channel_id}&key={secrets_file.google_api_key}"
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
        except Exception as exc:
            if story_object:
                logger.warning(
                    f"id={story_object.id}: failed to get channel details for YouTube URL {youtube_url}: {exc}"
                )
            else:
                logger.warning(
                    f"failed to get channel details for YouTube URL {youtube_url}: {exc}"
                )

            return ""

    elif "youtube.com/playlist" in youtube_url:
        playlist_id = utils_text.get_text_between(
            "list=", "&", youtube_url, okay_to_elide_right_pattern=True
        )

        # TODO: convert this to use my existing endpoint_query_via_requests() function
        url = f"https://youtube.googleapis.com/youtube/v3/playlists?part=snippet&id={playlist_id}&key={secrets_file.google_api_key}"
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
        except Exception as exc:
            if story_object:
                logger.info(
                    f"id={story_object.id}: failed to get playlist details for YouTube URL {youtube_url}: {exc}"
                )
            else:
                logger.info(
                    f"failed to get playlist details for YouTube URL {youtube_url}: {exc}"
                )
            return ""
    else:
        if story_object:
            logger.info(
                f"id={story_object.id}: failed to understand format or structure of YouTube URL: {youtube_url}"
            )
        else:
            logger.info(
                f"failed to understand format or structure of YouTube URL: {youtube_url}"
            )

        return ""

    if not account_name and not account_url:
        return ""

    nowrap_class = check_if_nowrap_needed(account_name)

    account_name_slug = f"<br/><span class='social-media-account-name{nowrap_class}'><a href='{account_url}'><span class='social-media-account-emoji'>{SILHOUETTE_SYMBOL}</span>{account_name}</a></span>"

    if story_object:
        story_object.social_media["account_name_url"] = channel_id
        story_object.social_media["account_name_display"] = account_name
        story_object.social_media["nowrap_class"] = nowrap_class
        story_object.social_media["account_url"] = account_url
        story_object.social_media["account_name_slug"] = account_name_slug

    return account_name_slug
