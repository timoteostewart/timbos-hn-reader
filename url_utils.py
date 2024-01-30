import inspect
import logging
import sys

import requests
import urllib3

import config
import retrieve_by_url
import text_utils
from multiple_tlds import is_multiple_tlds

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CHARS_IN_DOMAINS_BREAK_BEFORE = "."
CHARS_IN_DOMAINS_BREAK_AFTER = "-"

# NONBREAKING_HYPHEN = config.settings["SYMBOLS"]["NONBREAKING_HYPHEN"]


def create_domains_slug(hostname_dict: str):
    if not hostname_dict["minus_www"]:
        return

    domains_lowercase = hostname_dict["minus_www"].lower()
    domains_all_as_list = domains_lowercase.split(".")

    if len(domains_all_as_list) < 2:
        return

    domains_for_hn_search = f"{domains_all_as_list[-2]}.{domains_all_as_list[-1]}"

    index = -2
    while (len(domains_all_as_list) + index > 0) and is_multiple_tlds(
        domains_for_hn_search
    ):
        index -= 1
        domains_for_hn_search = domains_all_as_list[index] + "." + domains_for_hn_search

    if index <= -4:
        logger.info(
            f"very long domain name constructed for search: {domains_for_hn_search}"
        )

    domains_for_search_as_list = domains_for_hn_search.split(".")

    longest_domain_component = len(max(domains_for_search_as_list, key=len))

    # entire hostname is short enough to stay on one line
    for_display_addl_class = ""
    CHAR_LENGTH_FOR_LINEWRAPPING_DOMAINS = config.settings["SLUGS"][
        "CHAR_LENGTH_FOR_LINEWRAPPING_DOMAINS"
    ]
    if len(domains_for_hn_search) < CHAR_LENGTH_FOR_LINEWRAPPING_DOMAINS:
        domains_for_display = domains_for_hn_search
        for_display_addl_class = " nowrap"

    # hostname is composed of 3 domains, so group the secondary domain with the shorter of the other components
    elif domains_for_hn_search.count(".") == 2 and longest_domain_component <= (
        CHAR_LENGTH_FOR_LINEWRAPPING_DOMAINS - 4
    ):
        if domains_for_search_as_list[0] < domains_for_search_as_list[2]:
            domains_for_display = f"{domains_for_search_as_list[0]}.{domains_for_search_as_list[1]}&ZeroWidthSpace;.{domains_for_search_as_list[2]}"
        else:
            domains_for_display = f"{domains_for_search_as_list[0]}&ZeroWidthSpace;.{domains_for_search_as_list[1]}.{domains_for_search_as_list[2]}"

    # insert ZeroWidthSpaces in long domains of hostname to aid in line breaking
    else:
        domains_for_search_as_list = split_domain_on_chars(domains_for_hn_search)
        for i in range(len(domains_for_search_as_list)):
            # skip over periods and hyphens in the list
            if "&ZeroWidthSpace;" in domains_for_search_as_list[i]:
                continue

            # if this component is too long...
            if (
                len(domains_for_search_as_list[i])
                >= CHAR_LENGTH_FOR_LINEWRAPPING_DOMAINS
            ):
                orig = domains_for_search_as_list[i]
                logger.info(
                    f"{inspect.currentframe().f_code.co_name}() saw long domain component: {orig} ({len(orig)} chars)"
                )
                parts = []
                while len(orig) >= CHAR_LENGTH_FOR_LINEWRAPPING_DOMAINS:
                    if len(orig) < int(CHAR_LENGTH_FOR_LINEWRAPPING_DOMAINS * 1.5):
                        index_after_split = len(orig) // 2
                        parts.append(f"{orig[:index_after_split]}&ZeroWidthSpace;")
                        parts.append(orig[index_after_split:])
                        orig = ""
                    else:
                        DOUBLE_OBLIQUE_HYPHEN = config.settings["SYMBOLS"][
                            "DOUBLE_OBLIQUE_HYPHEN"
                        ]
                        parts.append(
                            f"{orig[:CHAR_LENGTH_FOR_LINEWRAPPING_DOMAINS]}{DOUBLE_OBLIQUE_HYPHEN}&ZeroWidthSpace;"
                        )
                        orig = orig[CHAR_LENGTH_FOR_LINEWRAPPING_DOMAINS:]
                if orig:
                    parts.append(orig)

                domains_for_search_as_list[i] = "".join(parts)

        domains_for_display = "".join(domains_for_search_as_list)

    hostname_slug = f"<a class='domains-for-search{for_display_addl_class}' href='https://news.ycombinator.com/from?site={domains_for_hn_search}'>({domains_for_display})</a>"

    hostname_dict["for_hn_search"] = domains_for_hn_search
    hostname_dict["for_display"] = domains_for_display
    hostname_dict["for_display_addl_class"] = for_display_addl_class
    hostname_dict["slug"] = hostname_slug


def get_domains_from_url(url: str):
    if not url:
        return text_utils.EMPTY_STRING, text_utils.EMPTY_STRING

    # remove scheme
    if url.startswith("http"):
        iodfs = url.index("//")
        url = url[(iodfs + 2) :]

    try:  # remove path symbol (i.e., forward slash) and remainder of string
        iofs = url.index("/")
        url = url[:iofs]
    except:
        pass

    try:  # remove percent-encoded path symbol (i.e., forward slash) and remainder of string
        iofs = url.index("%2F")
        url = url[:iofs]
    except:
        pass

    try:  # remove query marker (i.e., question mark) and remainder of string
        ioqm = url.index("?")
        url = url[:ioqm]
    except:
        pass

    try:  # remove percent-encoded query marker (i.e., question mark) and remainder of string
        ioqm = url.index("%3F")
        url = url[:ioqm]
    except:
        pass

    try:  # remove port number symbol and remainder of string
        ioc = url.index(":")
        url = url[:ioc]
    except:
        pass

    try:  # remove URI fragment and remainder of string
        # more info: https://en.wikipedia.org/wiki/URI_fragment
        iohm = url.index("#")
        url = url[:iohm]
    except:
        pass

    hostname_full = url

    # remove any www, www1, www2, www3 subdomains
    if url.startswith("www."):
        hostname_minus_www = hostname_full[4:]
    elif url.startswith("www") and url[3:4].isnumeric() and url[4:5] == ".":
        hostname_minus_www = url[5:]
    else:
        hostname_minus_www = hostname_full

    return hostname_full, hostname_minus_www


def get_filename_details_from_url(full_url):
    if not full_url:
        return None

    # delete rightmost question mark and everything after it
    end_index = full_url.rfind("?")
    if end_index != -1:
        full_url = full_url[0:end_index]

    # delete rightmost percent-encoded question mark and everything after it
    end_index = full_url.rfind("%3F")
    if end_index != -1:
        full_url = full_url[0:end_index]

    # # delete rightmost open square bracket and everything after it
    # end_index = full_url.rfind("[")
    # if end_index != -1:
    #     full_url = full_url[0:end_index]

    # # delete rightmost percent-encoded open square bracket and everything after it
    # end_index = full_url.rfind("%5B")
    # if end_index != -1:
    #     full_url = full_url[0:end_index]

    # delete leftmost forward slash and everything before it
    start_index = full_url.rfind("/")
    if start_index != -1:
        full_url = full_url[(start_index + 1) :]

    # delete leftmost percent-encoded forward slash and everything before it
    start_index = full_url.rfind("%2F")
    if start_index != -1:
        full_url = full_url[(start_index + 1) :]

    # filename is whatever is left of the original URL after the preceding deletions
    filename = full_url

    # try to determine file extension
    last_dot_index = filename.rfind(".")
    if last_dot_index == -1:
        basename = filename
        extension = ""
    else:
        basename = filename[:last_dot_index]
        extension = filename[(last_dot_index + 1) :]

    # bundle up our results
    filename_details = {
        "filename": filename,
        "base_name": basename,
        "file_extension": extension,
    }

    return filename_details


def head_request(url=None, log_prefix=""):
    log_prefix += "head_request(): "
    if not url:
        # logger.error(log_prefix + "no URL provided")
        raise Exception("no URL provided")

    try:
        resp = requests.head(
            url,
            verify=False,
            timeout=config.settings["SCRAPING"]["REQUESTS_GET_TIMEOUT_S"],
            headers={"User-Agent": config.settings["SCRAPING"]["UA_STR"]},
        )
        return resp.headers

    except Exception as exc:
        exc_name = str(exc.__class__.__name__)
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        logger.error(log_prefix + f"{exc_slug} for url {url}")
        return None


def split_domain_on_chars(domain_string: str):
    result = []
    cur_part = ""
    for char in domain_string:
        if char in CHARS_IN_DOMAINS_BREAK_BEFORE:
            result.append(cur_part)
            result.append(f"&ZeroWidthSpace;{char}")
            cur_part = ""
        elif char in CHARS_IN_DOMAINS_BREAK_AFTER:
            result.append(cur_part)
            result.append(f"{char}&ZeroWidthSpace;")
            cur_part = ""
        else:
            cur_part += char
    if cur_part:
        result.append(cur_part)
    return result
