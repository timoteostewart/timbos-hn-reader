import inspect
import logging
import math
import re
import traceback
from urllib.parse import unquote, urlparse

import goose3
from dateutil.tz import tzutc
from goose3 import Goose
from goose3.crawler import Crawler
from goose3.extractors.publishdate import TIMEZONE_INFO
from goose3.text import get_encodings_from_content

import config
import utils_text
from multiple_tlds import is_multiple_tlds

# import trafilatura  # never use; ← it has a dependency conflict with another package over the required version of `charset-normalizer`


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CHARS_IN_DOMAINS_BREAK_BEFORE = "."
CHARS_IN_DOMAINS_BREAK_AFTER = "-"

# NONBREAKING_HYPHEN = config.settings["SYMBOLS"]["NONBREAKING_HYPHEN"]

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

EMPTY_STRING = ""

# def monkeypatched_publish_date_to_utc(self):
#     try:
#         publish_datetime = dateutil.parser.parse(
#             self.article.publish_date, tzinfos=TIMEZONE_INFO
#         )
#         if publish_datetime.tzinfo:
#             return publish_datetime.astimezone(tzutc())
#         else:
#             return publish_datetime
#     except (ValueError, OverflowError):
#         logger.warning(
#             f"Publish date {self.article.publish_date} could not be resolved to UTC (monkeypatched_publish_date_to_utc)"
#         )
#         return None


# Crawler._publish_date_to_utc = monkeypatched_publish_date_to_utc


def add_singular_plural(number, unit, force_int=False):
    if force_int:
        if number == 0 or number == 0.0:
            return f"zero {unit}s"
        elif number == 1 or number == 1.0:
            return f"1 {unit}"
        else:
            return f"{int(math.ceil(number))} {unit}s"

    if number == 0 or number == 0.0:
        return f"0 {unit}s"
    elif number == 1 or number == 1.0:
        return f"1 {unit}"
    else:
        x = ""
        if unit in ["hour"]:
            x = f"{get_frac(number, 'fourths')} {unit}s"
        elif unit in ["day", "week", "month", "year"]:
            x = f"{get_frac(number, 'halves')} {unit}s"
        else:
            x = f"{int(math.ceil(number))} {unit}s"
        if x[:2] == "1 ":
            return x[:-1]
        else:
            return x


def create_domains_slug(hostname_dict: str, log_prefix=""):
    if not hostname_dict["minus_www"]:
        return

    log_prefix_local = log_prefix + "create_domains_slug(): "

    # TODO: try using urlparse and netloc to extract domain, and see which is faster/more accurate. maybe log when results of both methods differ

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
            log_prefix_local
            + f"very long domain name constructed for search: {domains_for_hn_search} (~Tim~)"
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
                    log_prefix_local
                    + f"long domain component {orig} ({len(orig)} chars) in url {hostname_dict['full']}"
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


def get_frac(number, precision):

    fractions_halves = {
        0.0: "",
        0.5: "½",
    }

    fractions_fourths = {0.0: "", 0.25: "¼", 0.5: "½", 0.75: "¾"}

    fractions_to_use = None
    if precision == "halves":
        fractions_to_use = fractions_halves
    elif precision == "fourths":
        fractions_to_use = fractions_fourths
    else:
        fractions_to_use = fractions_halves

    whole_part = int(number)
    frac_part = number - whole_part
    min_diff = 1
    best_fraction = 0
    for each_fraction in fractions_to_use.keys():
        cur_diff = abs(frac_part - each_fraction)
        if cur_diff < min_diff:
            min_diff = cur_diff
            best_fraction = each_fraction

    return f"{whole_part}{fractions_to_use[best_fraction]}"


def get_domains_from_url_via_urllib(url: str, log_prefix=""):
    log_prefix_local = log_prefix + "get_domains_from_url_via_urllib(): "
    if not url:
        return None
    parsed_url = urlparse(url)

    hostname_full = parsed_url.netloc

    if hostname_full.endswith(":443"):
        hostname_full = hostname_full[:-4]
        logger.info(
            log_prefix_local + f"removed ':443' from end of hostname_full for url {url}"
        )

    match = re.search(r"^w{2,3}\d?\.", hostname_full)
    if match and len(match.group()) >= 3:
        hostname_minus_www = hostname_full.replace(match.group(), "", 1)
    else:
        hostname_minus_www = hostname_full

    return hostname_full, hostname_minus_www


def get_domains_from_url(url: str, log_prefix=""):
    if not url:
        return None, None

    log_prefix_local = log_prefix + "get_domains_from_url(): "

    original_url = url

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

    hostname_full_via_urllib, hostname_minus_www_via_urllib = (
        get_domains_from_url_via_urllib(url=original_url, log_prefix=log_prefix)
    )

    if hostname_full_via_urllib != hostname_full:
        logger.info(
            log_prefix_local + f"{hostname_full=}, {hostname_full_via_urllib=} (~Tim~)"
        )
    # else:
    #     logger.info(log_prefix_local + "hostname_full == hostname_full_via_urllib")

    if hostname_minus_www_via_urllib != hostname_minus_www:
        logger.info(
            log_prefix_local
            + f"{hostname_minus_www=}, {hostname_minus_www_via_urllib=} (~Tim~)"
        )
    # else:
    #     logger.info(
    #         log_prefix_local + "hostname_minus_www == hostname_minus_www_via_urllib"
    #     )

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


def get_reading_time_via_goose(page_source=None, log_prefix=""):
    log_prefix += "grt_via_g(): "

    try:
        if not page_source:
            logger.error(log_prefix + "page_source required")
            return None
        reading_time = None
        g = Goose()
        article = g.extract(raw_html=page_source)
        if article:
            reading_time = (
                utils_text.word_count(article.cleaned_text)
                // config.reading_speed_words_per_minute
            )
        if reading_time:
            reading_time = max(reading_time, 1)
            logger.info(
                log_prefix
                + f"{utils_text.add_singular_plural(reading_time, 'minute', force_int=True)}"
            )
            return reading_time
        else:
            logger.info(log_prefix + "could not determine reading time")
            return None
    except Exception as exc:
        short_exc_name = exc.__class__.__name__
        exc_name = exc.__class__.__module__ + "." + short_exc_name
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        logger.error(log_prefix + "unexpected exception: " + exc_slug)
        tb_str = traceback.format_exc()
        logger.error(log_prefix + tb_str)
        return None


get_reading_time = get_reading_time_via_goose


def get_text_between(
    left_pattern: str,
    right_pattern: str,
    text: str,
    okay_to_elide_right_pattern=False,
    force_lowercase=False,
):

    left_index = text.find(left_pattern)
    if left_index == -1:
        return None

    right_index = text.find(
        right_pattern, left_index + len(left_pattern)
    )  # note: lazy find
    if right_index == -1:
        if okay_to_elide_right_pattern:
            return text[slice(left_index + len(left_pattern), len(text))]
        else:
            return None

    # check for zero-length string between left_pattern and right_pattern
    if left_index + len(left_pattern) == right_index:
        return config.EMPTY_STRING

    result = text[slice(left_index + len(left_pattern), right_index)]

    if not result:
        return None

    if force_lowercase:
        return result.lower()
    else:
        return result


def insert_possible_line_breaks(orig_title):

    words_by_spaces = orig_title.split(" ")

    # we will break each "word" down further, if possible or necessary
    break_after_these = "/-"
    break_before_these = "\\"

    LINE_BREAK_HYPHEN = "⸗"

    for i in range(len(words_by_spaces)):

        intraword_tokens = []

        cur_word = ""
        for char in words_by_spaces[i]:

            if char in break_after_these:
                intraword_tokens.append(cur_word)
                cur_word = char
                cur_word += "&ZeroWidthSpace;"
                intraword_tokens.append(cur_word)
                cur_word = ""
            elif char in break_before_these:
                intraword_tokens.append(cur_word)
                cur_word = "&ZeroWidthSpace;"
                cur_word += char
                intraword_tokens.append(cur_word)
                cur_word = ""
            else:
                cur_word += char
        if cur_word:
            intraword_tokens.append(cur_word)

        for j in range(len(intraword_tokens)):
            if "&ZeroWidthSpace;" in intraword_tokens[j]:
                continue
            # check if hyphenation is needed

            MAX_ALLOWED_WORD_LENGTH = config.settings["SLUGS"]["MAX_SUBSTRING_LENGTH"]

            if len(intraword_tokens[j]) > MAX_ALLOWED_WORD_LENGTH:
                t = intraword_tokens[j]
                t_conv = []
                while len(t) >= MAX_ALLOWED_WORD_LENGTH:
                    if len(t) <= 1.5 * MAX_ALLOWED_WORD_LENGTH:
                        len_to_use = len(t) // 2
                        t_conv.append(t[slice(len_to_use)])
                        t_conv.append(f"{LINE_BREAK_HYPHEN}&ZeroWidthSpace;")
                        t_conv.append(t[slice(len_to_use, len(t))])
                        # t_conv.append("-&ZeroWidthSpace;")
                        t = ""
                    elif len(t) <= 2 * MAX_ALLOWED_WORD_LENGTH:
                        len_to_use = len(t) // 3
                        twice_len_to_use = int(2 * len_to_use)
                        t_conv.append(t[slice(len_to_use)])
                        t_conv.append(f"{LINE_BREAK_HYPHEN}&ZeroWidthSpace;")
                        t_conv.append(t[slice(len_to_use, twice_len_to_use)])
                        t_conv.append(f"{LINE_BREAK_HYPHEN}&ZeroWidthSpace;")
                        t_conv.append(t[slice(twice_len_to_use, len(t))])
                        # t_conv.append("-&ZeroWidthSpace;")
                        t = ""
                    else:
                        t_conv.append(t[:MAX_ALLOWED_WORD_LENGTH])
                        t_conv.append(f"{LINE_BREAK_HYPHEN}&ZeroWidthSpace;")
                        t = t[24:]
                intraword_tokens[j] = "".join(t_conv)
        words_by_spaces[i] = "".join(intraword_tokens)

    return " ".join(words_by_spaces)


def parse_content_type_from_raw_header(content_type_header: str, log_prefix=""):
    log_prefix_local = log_prefix + "parse_content_type_from_raw_header(): "
    if not content_type_header:
        return None

    ct_set = set()

    if isinstance(content_type_header, list):
        for each in content_type_header:
            ct_set.update(re.split("[;,]", each))
    elif isinstance(content_type_header, str):
        ct_set.update(re.split("[;,]", content_type_header))
    else:
        logger.info(
            log_prefix_local
            + f"unexpected type {str(type(content_type_header))} for content_type_header {str(content_type_header)} (~Tim~)"
        )

    ct_set = {x.strip() for x in ct_set if x.strip()}

    for each in ct_set.copy():
        if "/" in each:
            pass
        elif each.startswith("charset"):
            ct_set.remove(each)
        else:
            ct_set.remove(each)

    if len(ct_set) == 1:
        return ct_set.pop().lower()
    elif not ct_set:
        logger.info(log_prefix_local + f"no content-type found in http header (~Tim~)")
        return None
    else:
        logger.info(
            log_prefix_local
            + f"multiple content-types found in http header {ct_set=} (~Tim~)"
        )
        return ct_set.pop().lower()

    return content_type.lower() if content_type else None


def sanitize(s: str):
    s = s.lower()
    allowed_chars = "abcdefghijklmnopqrstuvwxyz 0123456789"
    sanitized = ""
    for char in s:
        if char in allowed_chars:
            sanitized += char
    sanitized = re.sub(" {2,}", " ", sanitized)
    return sanitized.strip()


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


def word_count(text):
    return len(text.split(" "))


def heal_localhost_url(localhost_url: str, real_hostname: str):

    if not localhost_url:
        return None

    parsed_url = urlparse(localhost_url)

    if parsed_url.scheme:
        scheme_part = unquote(parsed_url.scheme)
        if scheme_part:
            scheme_part = scheme_part + "://"
        else:
            scheme_part = ""
    else:
        scheme_part = ""

    if parsed_url.hostname:
        hostname_part = unquote(parsed_url.hostname)
        if not hostname_part:
            hostname_part = ""
    else:
        hostname_part = ""

    port_number = parsed_url.port
    if port_number:
        port_number = ":" + str(port_number)
    else:
        port_number = ""

    if parsed_url.path:
        path_part = unquote(parsed_url.path)
        if not path_part:
            path_part = "/"
    else:
        path_part = "/"

    if parsed_url.params:
        params_part = unquote(parsed_url.params)
        if params_part:
            params_part = ";" + params_part
        else:
            params_part = ""
    else:
        params_part = ""

    if parsed_url.query:
        query_part = unquote(parsed_url.query)
        if query_part:
            query_part = "?" + query_part
        else:
            query_part = ""
    else:
        query_part = ""

    if parsed_url.fragment:
        fragment_part = unquote(parsed_url.fragment)
        if fragment_part:
            fragment_part = "#" + fragment_part
        else:
            fragment_part = ""
    else:
        fragment_part = ""

    https_scheme_string = "https://"

    possibly_healed_url = (
        https_scheme_string
        + real_hostname
        + path_part
        + params_part
        + query_part
        + fragment_part
    )

    return possibly_healed_url


# eliminate some goose3 errors I occasionally get


def monkeypatched_extract_3_1_19(self):
    return {
        "description": self.get_meta_description(),
        "keywords": self.get_meta_keywords(),
        "lang": self.get_meta_lang(),
        "favicon": self.get_favicon(),
        "canonical": "www.example.com",
        "domain": "example.com",
        "encoding": self.get_meta_encoding(),
    }


# def get_meta_encoding(self):
#     """Parse the meta encoding"""
#     encoding = get_encodings_from_content(self.article.raw_html)
#     return encoding[0] if encoding else None


def monkeypatched_get_meta_encoding_3_1_19(self):
    """Parse the meta encoding"""
    encoding = get_encodings_from_content(self.article.raw_html)

    # replace every occurrence of "null" with "utf-8" in 'encoding'
    disallowed_encodings = ["", "none", "null"]
    encoding = [x if x not in disallowed_encodings else "utf-8" for x in encoding]

    if encoding:
        res = encoding[0]
    else:
        res = None

    for each in [
        "",
        "none",
        "null",
    ]:
        if res == each:
            logger.info(
                f"monkeypatched_get_meta_encoding_3_1_19(): defaulting to 'utf-8' for {self.article.final_url} since original was '{each}' (~Tim~)"
            )
            res = "utf-8"

    return res


metas_extractor = goose3.extractors.metas.MetasExtractor
metas_extractor.extract = monkeypatched_extract_3_1_19
metas_extractor.get_meta_encoding = monkeypatched_get_meta_encoding_3_1_19


if __name__ == "__main__":
    try:
        res = heal_localhost_url(
            localhost_url="http://xxxxxx:3000/aardvark/bear.jpeg;sorrowful?a=apple&b=banana#carrot",
            real_hostname="shotune.com",
        )
        print(res)
    except Exception as exc:
        exc_module = exc.__class__.__module__
        exc_short_name = exc.__class__.__name__
        exc_name = exc_module + "." + exc_short_name
        exc_msg = str(exc)
        exc_slug = exc_name + ": " + exc_msg
        logger.error("unexpected exception: " + exc_slug)
        tb_str = traceback.format_exc()
        logger.error(tb_str)
