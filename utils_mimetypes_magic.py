import json
import logging
import mimetypes
import os
import re
import subprocess
import sys
import traceback
from collections import Counter, defaultdict
from enum import Enum, auto
from typing import Dict, List
from urllib.parse import unquote, urlparse

import exiftool
import magic
from bs4 import BeautifulSoup

from MarkupTag import MarkupTag
from Trie import Trie

logger = logging.getLogger(__name__)

html_tags = {}
svg_tags = {}

html_tags["current"] = set(
    [
        "a",
        "abbr",
        "address",
        "area",
        "article",
        "aside",
        "audio",
        "b",
        "base",
        "bdi",
        "bdo",
        "blockquote",
        "body",
        "br",
        "button",
        "canvas",
        "caption",
        "cite",
        "code",
        "col",
        "colgroup",
        "data",
        "datalist",
        "dd",
        "del",
        "details",
        "dfn",
        "dialog",
        "div",
        "dl",
        "dt",
        "em",
        "embed",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "head",
        "header",
        "hgroup",
        "hr",
        "html",
        "i",
        "iframe",
        "img",
        "input",
        "ins",
        "kbd",
        "label",
        "legend",
        "li",
        "link",
        "main",
        "map",
        "mark",
        "math",
        "menu",
        "meta",
        "meter",
        "nav",
        "noscript",
        "object",
        "ol",
        "optgroup",
        "option",
        "output",
        "p",
        "picture",
        "portal",
        "pre",
        "progress",
        "q",
        "rp",
        "rt",
        "ruby",
        "s",
        "samp",
        "script",
        "search",
        "section",
        "select",
        "slot",
        "small",
        "source",
        "span",
        "strong",
        "style",
        "sub",
        "summary",
        "sup",
        "svg",
        "table",
        "tbody",
        "td",
        "template",
        "textarea",
        "tfoot",
        "th",
        "thead",
        "time",
        "title",
        "tr",
        "track",
        "u",
        "ul",
        "var",
        "video",
        "wbr",
    ]
)

html_tags["obsolete_or_deprecated"] = set(
    [
        "acronym",
        "big",
        "center",
        "content",
        "dir",
        "font",
        "frame",
        "frameset",
        "image",
        "marquee",
        "menuitem",
        "nobr",
        "noembed",
        "noframes",
        "param",
        "plaintext",
        "rb",
        "rtc",
        "shadow",
        "strike",
        "tt",
        "xmp",
    ]
)

html_tags["html5"] = set(
    [
        "article",
        "aside",
        "audio",
        "bdi",
        "canvas",
        "data",
        "datalist",
        "details",
        "dialog",
        "embed",
        "figcaption",
        "figure",
        "footer",
        "header",
        "hgroup",
        "keygen",
        "main",
        "mark",
        "meter",
        "nav",
        "output",
        "picture",
        "progress",
        "rp",
        "rt",
        "ruby",
        "section",
        "source",
        "summary",
        "svg",
        "template",
        "time",
        "track",
        "video",
        "wbr",
    ]
)


svg_tags["current"] = set(
    [
        "a",
        "animate",
        "animateMotion",
        "animateTransform",
        "circle",
        "clipPath",
        "defs",
        "desc",
        "ellipse",
        "feBlend",
        "feColorMatrix",
        "feComponentTransfer",
        "feComposite",
        "feConvolveMatrix",
        "feDiffuseLighting",
        "feDisplacementMap",
        "feDistantLight",
        "feDropShadow",
        "feFlood",
        "feFuncA",
        "feFuncB",
        "feFuncG",
        "feFuncR",
        "feGaussianBlur",
        "feImage",
        "feMerge",
        "feMergeNode",
        "feMorphology",
        "feOffset",
        "fePointLight",
        "feSpecularLighting",
        "feSpotLight",
        "feTile",
        "feTurbulence",
        "filter",
        "foreignObject",
        "g",
        "hatch",
        "hatchpath",
        "image",
        "line",
        "linearGradient",
        "marker",
        "mask",
        "metadata",
        "mpath",
        "path",
        "pattern",
        "polygon",
        "polyline",
        "radialGradient",
        "rect",
        "script",
        "set",
        "stop",
        "style",
        "svg",
        "switch",
        "symbol",
        "text",
        "textPath",
        "title",
        "tspan",
        "use",
        "view",
    ]
)

tag_based_markup_languages = [
    "application/atom+xml",
    "application/rss+xml",
    "application/xhtml+xml",
    "application/xml",
    "image/svg+xml",
    "text/html",
    "text/html5",
]


def check_for_valid_text_encodings(local_file: str, log_prefix="") -> List[str]:
    # requires iconv (i.e., libiconv) command

    log_prefix_local = log_prefix + "check_for_valid_text_encodings(): "
    valid_encodings = []

    text_encodings = [
        "ASCII",
        "ISO-8859-1",
        "UTF-8",
        "WINDOWS-1251",
    ]

    # text_encodings.extend(
    #     [
    #         "ISO-8859-2",
    #         "UTF-16",
    #         "UTF-32",
    #         "UTF-7",
    #         "WINDOWS-1252",
    #     ]
    # )

    for each_encoding in text_encodings:
        cmd = f"iconv -f {each_encoding} -t {each_encoding} {local_file} -o /dev/null"

        try:
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True,
            )

            valid_encodings.append(each_encoding)

        except subprocess.CalledProcessError as exc:
            # non-zero return code
            pass

        except Exception as exc:
            short_exc_name = exc.__class__.__name__
            exc_name = exc.__class__.__module__ + "." + short_exc_name
            exc_msg = str(exc)
            exc_slug = f"{exc_name}: {exc_msg}"
            logger.error(log_prefix_local + "unexpected exception: " + exc_slug)
            tb_str = traceback.format_exc()
            logger.error(log_prefix_local + tb_str)

    if "UTF-8" in valid_encodings:
        if is_utf8_2(local_file):
            logger.info(
                log_prefix_local
                + f"`iconv -f UTF-8` succeeded and `isutf8` agreed for {local_file} (~Tim~)"
            )

        else:
            valid_encodings.remove("UTF-8")
            logger.info(
                log_prefix_local
                + f"`iconv -f UTF-8` succeeded, but `isutf8` failed for {local_file} (~Tim~)"
            )

    return valid_encodings


def check_for_wellformed_xml(local_file: str, log_prefix="") -> bool:
    # requires Linux xmlwf command
    log_prefix_local = log_prefix + "is_wellformed_xml(): "

    cmd = f"xmlwf -c {local_file}"

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
        )
        return True

    except subprocess.CalledProcessError as exc:
        pass

    except Exception as exc:
        short_exc_name = exc.__class__.__name__
        exc_name = exc.__class__.__module__ + "." + short_exc_name
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        logger.error(log_prefix_local + "unexpected exception: " + exc_slug)
        tb_str = traceback.format_exc()
        logger.error(log_prefix_local + tb_str)

    return False


def is_utf8(local_file: str, log_prefix="") -> bool:
    # requires Linux xmlwf command
    log_prefix_local = log_prefix + "is_utf8(): "

    cmd = f"isutf8 {local_file}"

    try:
        res = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
        )
        if res.returncode == 0:
            return True

    except subprocess.CalledProcessError as exc:
        pass

    except Exception as exc:
        short_exc_name = exc.__class__.__name__
        exc_name = exc.__class__.__module__ + "." + short_exc_name
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        logger.error(log_prefix_local + "unexpected exception: " + exc_slug)
        tb_str = traceback.format_exc()
        logger.error(log_prefix_local + tb_str)

    return False


def is_utf8_2(local_file: str, log_prefix="") -> bool:
    with open(local_file, "rb") as file:
        data = file.read()
        try:
            data.decode("UTF-8")
        except UnicodeDecodeError:
            return False
        else:
            return True


def is_valid_json(local_file: str, log_prefix="") -> bool:
    # requires Linux jq command
    log_prefix_local = log_prefix + "get_mimetype_via_file_command(): "

    cmd = f"jq . {local_file}"

    try:
        res = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
        )
        if res.returncode == 0:
            return True

    except subprocess.CalledProcessError as exc:
        pass

    except Exception as exc:
        short_exc_name = exc.__class__.__name__
        exc_name = exc.__class__.__module__ + "." + short_exc_name
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        logger.error(log_prefix_local + "unexpected exception: " + exc_slug)
        tb_str = traceback.format_exc()
        logger.error(log_prefix_local + tb_str)

    return False


nonspecific_cts = set(
    [
        "application/binary",  # nonstandard
        "application/octet-stream",
        "message/rfc822",
        "multipart/alternative",
        "multipart/form-data",
        "multipart/mixed",
    ]
)

binary_cts = set(
    [
        "application/eps",
        "application/gzip",
        "application/ogg",
        "application/opengraph-image",
        "application/vnd.android.package-archive",
        "application/vnd.lotus-organizer",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.rar",
        "application/x-bzip2",
        "application/x-dosexec",
        "application/x-gzip",
        "application/x-tar",
        "application/zip",
        "audio/mp4",
        "audio/mpeg",
        "audio/mpeg3",
        "audio/prs.sid",
        "font/ttf",
        "image/avif",
        "image/bmp",
        "image/gif",
        "image/jp2",
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/svg+xml",
        "image/tiff",
        "image/vnd.microsoft.icon",
        "image/webp",
        "image/x-eps",
        "image/x-icon",
        "model/opengraph-image",  # nonstandard
        "video/mp4",
        "video/webm",
        "video/x-ms-wmv",
    ]
)

binary_mimetypes_prefixes = [
    "image/",
    "audio/",
    "video/",
    "model/",
    "font/",
]

binary_mimetypes_prefixes_trie = Trie(prefix_search=True)
for _ in binary_mimetypes_prefixes:
    binary_mimetypes_prefixes_trie.add_member(_)

textual_cts = set(
    [
        "application/activity+json",
        "application/atom+xml",
        "application/json",
        "application/pdf",
        "application/postscript",
        "application/rls-services+xml",
        "application/rss+xml",
        "application/svg+xml",
        "application/typescript",  # nonstandard
        "application/xhtml+xml",
        "application/xml",
        "text/calendar",
        "text/css",
        "text/csv",
        "text/html",
        "text/html5",  # nonstandard
        "text/hypertext",  # nonstandard
        "text/javascript",
        "text/markdown",
        "text/pdf",  # nonstandard
        "text/pgp",  # nonstandard
        "text/plain",
        "text/vnd.trolltech.linguist",
        "text/x-c",
        "text/x-c++",
        "text/x-c++src",
        "text/x-component",
        "text/x-csrc",
        "text/x-diff",
        "text/x-java",
        "text/x-lilypond",
        "text/x-perl",
        "text/x-php",
        "text/x-ruby",
        "text/x-script.python",
        "text/x-server-parsed-html",
        "text/x-sh",
        "text/x-shellscript",
        "text/x-tex",
        "text/x-web-markdown",
        "text/xml",
        "text/xsl",
    ]
)

textual_mimetypes_suffixes = [
    "+json",
    "+xml",
]

textual_mimetypes_suffixes_trie = Trie(suffix_search=True)
for _ in textual_mimetypes_suffixes:
    textual_mimetypes_suffixes_trie.add_member(_)


def is_a_binary_mimetype(mimetype: str) -> bool:
    if mimetype in binary_cts:
        return True
    elif mimetype in textual_cts:
        return False
    elif mimetype.startswith("text/"):
        return False
    elif binary_mimetypes_prefixes_trie.search(mimetype) is not None:
        return True
    elif textual_mimetypes_suffixes_trie.search(mimetype) is not None:
        return False
    else:
        return True


def get_mimetype(
    local_file: str, srct: str = None, url: str = None, log_prefix=""
) -> str:

    log_prefix_local = log_prefix + "get_mimetype(): "

    if srct:
        if ";" in srct:
            srct = srct.split(";")[0].strip()
        srct = srct.lower()

    # use trusted tools to check if file is probably binary
    trusted_sources = Counter(
        [
            get_mimetype_via_python_magic(local_file=local_file, log_prefix=log_prefix),
            get_mimetype_via_file_command(local_file=local_file, log_prefix=log_prefix),
            get_mimetype_via_exiftool(local_file=local_file, log_prefix=log_prefix),
        ]
    )

    consensus_ct = None
    if len(trusted_sources) == 1 and srct == trusted_sources.most_common(1)[0][0]:
        # all 3 trusted sources agree with srct
        consensus_ct = srct
    elif len(trusted_sources) == 1:
        # all 3 trusted sources agree; srct differs or is absent
        consensus_ct = trusted_sources.most_common(1)[0][0]
    elif len(trusted_sources) == 2 and srct == trusted_sources.most_common(1)[0][0]:
        # 2 trusted sources agree with srct
        consensus_ct = srct
    elif len(trusted_sources) == 2:
        # 2 trusted sources agree; srct differs or is absent
        consensus_ct = trusted_sources.most_common(1)[0][0]
    elif len(trusted_sources) >= 2 and srct in trusted_sources:
        # 1 or 2 trusted sources agree with srct
        consensus_ct = srct
    else:
        # no consensus
        pass
    # TODO: could fall back to guessing mimetype from URL

    # if file is probably binary, invoke get_textual_mimetype just in case

    # if file is probably not binary, invoke get_textual_mimetype


def get_mimetype_via_exiftool(local_file: str, log_prefix="") -> str:
    log_prefix_local = log_prefix + "get_mimetype_via_exiftool(): "
    mimetype = None
    try:
        with exiftool.ExifToolHelper(executable="/usr/local/bin/exiftool") as et:
            metadata = et.get_metadata(local_file)[0]
            # file_type = metadata.get("File:FileType")
            # file_type_extension = metadata.get("File:FileTypeExtension")
            mimetype = metadata.get("File:MIMEType")
        # logger.info(log_prefix_local + f"exiftool succeeded for {local_file}")
        return mimetype

    except Exception as exc:
        if isinstance(exc, exiftool.exceptions.ExifToolExecuteError):
            logger.error(log_prefix_local + exc_slug)
            tb_str = traceback.format_exc()
            logger.error(log_prefix_local + tb_str)

        elif isinstance(exc, exiftool.exceptions.ExifToolVersionError):
            logger.error(log_prefix_local + exc_slug)
            tb_str = traceback.format_exc()
            logger.error(log_prefix_local + tb_str)

        else:
            short_exc_name = exc.__class__.__name__
            exc_name = exc.__class__.__module__ + "." + short_exc_name
            exc_msg = str(exc)
            exc_slug = f"{exc_name}: {exc_msg}"
            logger.error(log_prefix_local + "unexpected exception: " + exc_slug)
            tb_str = traceback.format_exc()
            logger.error(log_prefix_local + tb_str)

        logger.info(log_prefix_local + f"exiftool failed for {local_file} (~Tim~)")

        return None


def get_mimetype_via_exiftool2(local_file: str, log_prefix="") -> str:
    log_prefix_local = log_prefix + "get_mimetype_via_exiftool2(): "
    mimetype = None

    cmd = f'/usr/local/bin/exiftool -File:MIMEType "{local_file}"'

    try:
        res = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
        ).stdout

    except Exception as exc:
        exc_name = exc.__class__.__name__
        fq_exc_name = exc.__class__.__module__ + "." + exc_name
        exc_msg = str(exc)
        exc_slug = f"{fq_exc_name}: {exc_msg}"

        if isinstance(exc, subprocess.CalledProcessError):
            logger.error(log_prefix_local + exc_slug)

        else:
            logger.error(log_prefix_local + "unexpected exception: " + exc_slug)
            tb_str = traceback.format_exc()
            logger.error(log_prefix_local + tb_str)

        with open(local_file, mode="rb") as file:
            bytes = file.read(512)
            logger.error(log_prefix_local + f"{bytes=} (~Tim~)")

        return None

    if res:
        match = re.search(r"MIME Type[\ ]*:\ ", res)
        if match:
            mimetype = res.split(":")[-1].strip()
            return mimetype
        else:
            return None
    else:
        return None


def get_mimetype_via_file_command(local_file, log_prefix="") -> str:
    log_prefix_local = log_prefix + "get_mimetype_via_file_command(): "

    cmd = f"/srv/timbos-hn-reader/getmt local {local_file}"

    try:
        res = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        short_exc_name = exc.__class__.__name__
        exc_name = exc.__class__.__module__ + "." + short_exc_name
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        tb_str = traceback.format_exc()
        logger.error(log_prefix_local + exc_slug)
        logger.error(log_prefix_local + tb_str)
        return None
    except Exception as exc:
        short_exc_name = exc.__class__.__name__
        exc_name = exc.__class__.__module__ + "." + short_exc_name
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        tb_str = traceback.format_exc()
        logger.error(log_prefix_local + "unexpected exception: " + exc_slug)
        logger.error(log_prefix_local + tb_str)
        return None

    # res is json, so decode it into a python dictionary
    res = json.loads(res)
    return res["mimetype"]


def get_mimetype_via_python_magic(local_file, log_prefix="") -> str:
    log_prefix_local = log_prefix + "get_mimetype_via_libmagic(): "
    try:
        magic_type_as_mimetype = magic.from_file(local_file, mime=True)
    except Exception as exc:
        short_exc_name = exc.__class__.__name__
        exc_name = exc.__class__.__module__ + "." + short_exc_name
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        tb_str = traceback.format_exc()
        logger.error(log_prefix_local + "unexpected exception: " + exc_slug)
        logger.error(log_prefix_local + tb_str)
        return None

    return magic_type_as_mimetype


def guess_mimetype_from_uri_extension(url, log_prefix=""):
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Common_types
    # https://www.digipres.org/formats/mime-types/#application/illustrator%0A
    # https://www.digipres.org/formats/sources/fdd/formats/#fdd000018

    log_prefix_local = log_prefix + "guess_mimetype_from_uri_extension(): "

    res = []

    # get tld for url
    parsed_url = urlparse(url)
    tld = parsed_url.netloc.split(".")[-1]

    path = unquote(parsed_url.path)
    paths_extension = os.path.splitext(path)[1]
    logger.info(
        log_prefix_local
        + f"{parsed_url.netloc=} {tld=} {paths_extension=} {path=} {parsed_url.query=} {url=}"
    )
    if f".{tld}" == paths_extension:
        logger.info(
            log_prefix_local
            + f".tld .{tld} == paths_extension {paths_extension} for url {url} (~Tim~)"
        )

    # my overrides
    if (
        parsed_url.netloc == "github.com"
        and paths_extension == ".md"
        and "/blob/" in path
        or "/tree/" in path
    ):
        # https://github.com/Doubiiu/DynamiCrafter/blob/main/README.md
        # https://github.com/facebook/hermes/blob/main/API%2Fhermes_sandbox%2FREADME.md
        res.append("text/html")

    else:
        # guess using urlparse
        guess_by_urlparse = None
        if paths_extension:
            guess_by_urlparse, _ = mimetypes.guess_type(
                f"file.{paths_extension}", strict=False
            )
            if guess_by_urlparse:
                guess_by_urlparse = guess_by_urlparse.lower()
                res.append(guess_by_urlparse)

        # guess using mimetypes (anecdotally, it's sloppier than urlparse)
        guess_by_mimetypes = None
        guess_by_mimetypes, _ = mimetypes.guess_type(url, strict=False)
        if guess_by_mimetypes:
            guess_by_mimetypes = guess_by_mimetypes.lower()

            if (
                tld == "ai"
                and paths_extension != "ai"
                and (
                    guess_by_mimetypes == "application/vnd.adobe.illustrator"
                    or guess_by_mimetypes == "application/postscript"
                )
            ):
                guess_by_mimetypes = None

            elif (
                tld == "com"
                and (paths_extension != "com" or path == "/")
                and guess_by_mimetypes == "application/x-msdos-program"
            ):
                guess_by_mimetypes = None

            elif (
                tld == "info"
                and paths_extension != "info"
                and guess_by_mimetypes == "application/x-info"
            ):
                guess_by_mimetypes = None

            elif (
                tld == "org"
                and paths_extension != "org"
                and guess_by_mimetypes == "application/vnd.lotus-organizer"
            ):
                guess_by_mimetypes = None

            elif (
                tld == "xyz"
                and paths_extension != "xyz"
                and guess_by_mimetypes == "chemical/x-xyz"
            ):
                guess_by_mimetypes = None

            elif (
                tld == "zip"
                and paths_extension != "zip"
                and guess_by_mimetypes
                in [
                    "application/x-zip",
                    "application/x-zip-compressed",
                    "application/zip",
                ]
            ):
                logger.info(log_prefix_local + f"{guess_by_mimetypes=} {tld=} (~Tim~)")

            if guess_by_mimetypes:
                res.append(guess_by_mimetypes)

    return res


def collect_empty_attributes(s: str):
    if not s:
        return []

    in_quote = False  # Flag to track whether we're inside quotes
    current_substr = ""  # Current substring being collected
    substrings = []  # List to hold the final substrings

    for char in s:
        if char == '"':  # Toggle the in_quote flag when we hit a quote
            if in_quote:  # If we're ending a quoted string, add it to the list
                current_substr += char  # Include the closing quote
                substrings.append(current_substr[1:-1])
                current_substr = ""
            else:  # If we're starting a quoted string, save any current substring
                if current_substr:
                    substrings.append(current_substr)
                    current_substr = ""
                current_substr = char  # Include the opening quote
            in_quote = not in_quote
        elif char == "\n" or char == "\t" or char == "\f" or char == " ":
            if in_quote:
                current_substr += char
            else:
                if current_substr:
                    substrings.append(current_substr)
                    current_substr = ""
            # if we're not in quotes, interpret the whitespace as meaning we've ended the attribute

        elif (
            not in_quote and char == " "
        ):  # If we're not in quotes and hit a space, end the current substring
            if current_substr:
                substrings.append(current_substr)
                current_substr = ""
        else:
            current_substr += char  # Add character to the current substring

    # Add the last substring if there's anything left
    if current_substr:
        substrings.append(current_substr)

    return [x.strip() for x in substrings if x.strip() != ""]


def get_textual_mimetype(local_file, log_prefix="", debug=False, context=None) -> str:
    """Discriminate between HTML, HTML5, JSON, plain text, XHTML, XHTML5, and XML"""

    """

    todo:

    - add check for UTF 7, UTF 8, 16LE, 16BE, 32LE, 32BE BOMs at start of file: https://unicodebook.readthedocs.io/unicode_encodings.html#utf-7

    - figure out checks for markdown

    - document the prerequisites of installing xmlwf, jq, iconv, libiconv, exiftool, isutf8 etc. to stand up THNR server (not to mention ghostscript, imagemagic 6, imagemagick 7, etc.)

    - elsewhere, create way of invoking specific version of imagemagick, so we can fall back to version 6 in case of the pamcmyk32 error

    - add check for atom+xml format. https://www.ibm.com/docs/en/baw/22.x?topic=formats-atom-feed-format
    https://validator.w3.org/feed/docs/atom.html
    https://validator.w3.org/feed/docs/rfc4287.html



    """

    # 2024-02-10T21:09:43Z [active]  INFO     id 39324847: asdfft2(): srct: text/html, guesses: ['text/html', 'text/html'], mts: ['text/html', 'text/html', 'text/html'], textual_mimetype='image/svg+xml' for url https://kmaasrud.com/blog/opml-is-underrated.html
    # 2024-02-11T06:56:32Z [new]     INFO     id 39327596: asdfft2(): srct: text/plain, guesses: ['text/html'], mts: ['application/json', 'application/json', 'application/json'], textual_mimetype='application/json' for url https://github.com/denkspuren/BitboardC4/blob/master/BitboardDesign.md
    # 2024-02-11T17:54:16Z [new]     INFO     id 39336677: asdfft2(): timbos_textfile_format_identifier(): clues_toward=[('text/plain', 0), ('text/html', 0), ('application/xml', 0), ('application/json', 0), ('text/markdown', 0), ('application/postscript', 0), ('image/x-eps', 0), ('application/pdf', 0), ('text/x-shellscript', 0), ('application/xhtml+xml', -inf), ('image/svg+xml', -inf)] (~Tim~)

    # TODO: compare "tags seen" with textfile_format_identifier result, particular the tag soup when the result is text/plain or None
    # for text/html, what are the top 5 tags seen? for xhtml+xml? for text/html5?
    # compare "tags seen" with textfile_format_identifier result, particular the tag soup when the result is text/plain or None

    log_prefix_local = log_prefix + "get_textual_mimetype(): "

    CHARS_TO_READ = None  # 'None' means read all chars

    local_file = os.path.abspath(local_file)

    text_encodings = check_for_valid_text_encodings(local_file, log_prefix)

    if not text_encodings:
        if context and "url" in context:
            logger.info(
                log_prefix_local
                + f"file {local_file} is probably binary (url: {context['url']})"
            )
            return None
        else:
            logger.info(log_prefix_local + f"file {local_file} is probably binary")
            return None

    encoding_to_use = None
    if "UTF-8" in text_encodings:
        encoding_to_use = "utf-8"
    else:
        if (
            "ISO-8859-1" in text_encodings
            # and "ISO-8859-2" in text_encodings
            and len(text_encodings) == 1
        ):
            content = None
            with open(local_file, mode="r", encoding="ISO-8859-1") as file:
                if CHARS_TO_READ:
                    content = file.read(CHARS_TO_READ)
                else:
                    content = file.read()
            for char in content:
                if ord(char) < 32:
                    if context and "url" in context:
                        logger.info(
                            log_prefix_local
                            + f"file {local_file} is probably binary (url: {context['url']})"
                        )
                        return None
                    else:
                        logger.info(
                            log_prefix_local + f"file {local_file} is probably binary"
                        )
                        return None
                elif 127 <= ord(char) <= 159:
                    if context and "url" in context:
                        logger.info(
                            log_prefix_local
                            + f"file {local_file} is probably binary (url: {context['url']})"
                        )
                        return None
                    else:
                        logger.info(
                            log_prefix_local + f"file {local_file} is probably binary"
                        )
                        return None

        if "ISO-8859-1" in text_encodings:
            encoding_to_use = "iso-8859-1"
        elif "WINDOWS-1252" in text_encodings:
            encoding_to_use = "windows-1252"
        elif "ASCII" in text_encodings:
            encoding_to_use = "ascii"
        # elif "WINDOWS-1251" in text_encodings:
        #     encoding_to_use = "windows-1251"
        # elif "UTF-16" in text_encodings:
        #     encoding_to_use = "utf_16"
        # elif "UTF-7" in text_encodings:
        #     encoding_to_use = "utf_7"
        # elif "UTF-32" in text_encodings:
        #     encoding_to_use = "utf_32"
        # elif "ISO-8859-2" in text_encodings:
        #     encoding_to_use = "iso-8859-2"

    clues_toward = {
        "text/plain": 0,
        "text/markdown": 0,
        "text/html": 0,
        "text/html5": 0,
        "application/xml": 0,
        "application/atom+xml": 0,
        "application/rss+xml": 0,
        "application/xhtml+xml": 0,
        "image/svg+xml": 0,
        "application/json": 0,
        "application/postscript": 0,
        "image/x-eps": 0,
        "application/pdf": 0,
        "text/x-shellscript": 0,
    }

    content = None
    with open(local_file, mode="r", encoding=encoding_to_use) as file:
        if CHARS_TO_READ:
            content = file.read(CHARS_TO_READ)
        else:
            content = file.read()

    if not content:
        logger.info(log_prefix_local + f"file {local_file} is empty")
        return None

    while content[0] in [
        " ",
        "\f",
        "\n",
        "\v",
        "\r",
        "\t",
    ]:
        content = content[1:]

    logger.info(log_prefix_local + f"{encoding_to_use=} out of {text_encodings=}")
    first_64 = content[:64].replace("\n", " ")
    logger.info(log_prefix_local + f"content[:64]={first_64}")

    if is_valid_json(local_file):
        clues_toward["application/json"] += 1
    else:
        clues_toward["application/json"] = -float("inf")

    is_wellformed_xml = check_for_wellformed_xml(local_file)

    # check for PDF
    if content.startswith("%PDF-"):
        clues_toward["application/pdf"] += 1

        if content.startswith("%PDF-1."):
            clues_toward["application/pdf"] += 1
    else:
        clues_toward["application/pdf"] = -float("inf")

    # check for shebang
    if content.startswith("#!"):
        clues_toward["text/x-shellscript"] += 1
    else:
        clues_toward["text/x-shellscript"] = -float("inf")

    # check for application/postscript or image/x-eps
    if content.startswith("%!"):
        clues_toward["application/postscript"] += 1
        clues_toward["image/x-eps"] += 1

        if content.startswith("%!PS"):
            clues_toward["application/postscript"] += 1
            clues_toward["image/x-eps"] += 1
        if "EPSF-3.0" in content[:30]:
            clues_toward["image/x-eps"] += 1
        if not "EPS" in content[:30]:
            clues_toward["image/x-eps"] -= 1

        # if not "%%BoundingBox:" in content:
        #     clues_toward["image/x-eps"] = 0
    else:
        clues_toward["application/postscript"] = -float("inf")
        clues_toward["image/x-eps"] = -float("inf")

    document = defaultdict(list)

    # xml_attribute_name_re = r"[A-Za-z_:][A-Za-z_:0-9-.]*"
    xml_attribute_name_re = r"""[^\t\n\f \/>"'=]+"""  # per https://html.spec.whatwg.org/multipage/syntax.html#attributes-2
    xml_attribute_name_re = (
        "[^\\t\\n\\f \\/>'\"=]+"  # rewritten to avoid escaping backslashes
    )

    xml_attribute_unquoted_value_re = r"""[^\t\n\f "'/<=>\`]+"""
    xml_attribute_unquoted_value_re = (
        "[^\\t\\n\\f \"'/<=>\\`]+"  # rewritten to avoid escaping backslashes
    )

    for xml_case in [
        "xml",
        "XML",
    ]:
        cur_re = r"<\?" + xml_case + r"\b(.*?)\?>"
        match = re.search(cur_re, content, re.DOTALL)
        if match:
            the_tag = MarkupTag(
                tag_name=xml_case,
                tag_as_string=match.group(),
                start_index=match.start(),
            )
            document[the_tag.tag_name.lower()].append(the_tag)

            attrib_material = match.group(1).strip()

            # collect attributes with quoted values
            matches = re.finditer(
                f" ?({xml_attribute_name_re})=['\"](.*?)['\"]",
                attrib_material,
            )
            for match in matches:
                the_tag.attribs[match.group(1).lower()] = match.group(2)

            # collect attributes with unquoted values
            matches = re.finditer(
                f" ?({xml_attribute_name_re})=({xml_attribute_unquoted_value_re})",
                attrib_material,
            )
            for match in matches:
                the_tag.attribs[match.group(1).lower()] = match.group(2)

            # collect empty attributes (no value; or implicitly the empty string)
            copy_of_attrib_material = attrib_material

            for k, v in the_tag.attribs.items():
                target_replacement_strs = [
                    f'{k}="{v}"',
                    f"{k}='{v}'",
                ]

                for each in target_replacement_strs:
                    while each in copy_of_attrib_material:
                        copy_of_attrib_material = copy_of_attrib_material.replace(
                            each, " "
                        )

                # for values without spaces, we can also try to remove unquoted attribute values
                if not " " in v:
                    target_replacement_str = f"{k}={v}"
                    while target_replacement_str in copy_of_attrib_material:
                        copy_of_attrib_material = copy_of_attrib_material.replace(
                            target_replacement_str, " "
                        )

            the_tag.empty_attribs.extend(
                collect_empty_attributes(copy_of_attrib_material)
            )

    tags_to_check_upper = [
        "!DOCTYPE",
        "BODY",
        "HEAD",
        "HTML",
        "META",
        "SVG",
        "TITLE",
        "RSS",
        "FEED",
    ]

    for each_tag in [
        item for elem in tags_to_check_upper for item in (elem, elem.lower())
    ]:
        cur_re = r"<" + each_tag + r"\b(.*?)/?>"

        matches = re.finditer(cur_re, content, re.DOTALL)
        for match in matches:
            the_tag = MarkupTag(
                tag_name=each_tag,
                tag_as_string=match.group(),
                start_index=match.start(),
            )
            document[the_tag.tag_name.lower()].append(the_tag)

            attrib_material = match.group(1).strip()
            # print(f"{the_tag.tag_name.lower()}: {attrib_material=}")

            # collect attributes with quoted values
            matches = re.finditer(
                f" ?({xml_attribute_name_re})=['\"](.*?)['\"]",
                attrib_material,
            )
            for match in matches:
                the_tag.attribs[match.group(1).lower()] = match.group(2)

            # collect attributes with unquoted values
            matches = re.finditer(
                f" ?({xml_attribute_name_re})=({xml_attribute_unquoted_value_re})",
                attrib_material,
            )
            for match in matches:
                the_tag.attribs[match.group(1).lower()] = match.group(2)

            # collect empty attributes (no value; or implicitly the empty string)
            copy_of_attrib_material = attrib_material

            for k, v in the_tag.attribs.items():
                target_replacement_strs = [
                    f'{k}="{v}"',
                    f"{k}='{v}'",
                ]

                for each in target_replacement_strs:
                    while each in copy_of_attrib_material:
                        copy_of_attrib_material = copy_of_attrib_material.replace(
                            each, " "
                        )

                # for values without spaces, we can also try to remove unquoted attribute values
                if not " " in v:
                    target_replacement_str = f"{k}={v}"
                    while target_replacement_str in copy_of_attrib_material:
                        copy_of_attrib_material = copy_of_attrib_material.replace(
                            target_replacement_str, " "
                        )

            the_tag.empty_attribs.extend(
                collect_empty_attributes(copy_of_attrib_material)
            )

    # check all sorts of tags to apply any statistical heuristics
    number_of_tags = 0
    cur_re = r"<([A-Za-z0-9]+)(.*?)/?>"
    tags_seen = Counter()
    matches = re.finditer(cur_re, content, re.DOTALL)
    for match in matches:
        if not match.group().endswith("/>"):
            tags_seen[match.group(1).lower()] += 1
            number_of_tags += 1

    logger.info(log_prefix_local + f"{number_of_tags=}")
    logger.info(
        log_prefix_local
        + f"tags_seen={sorted(tags_seen.items(), key=lambda x: x[1], reverse=True)}"
    )
    logger.info(log_prefix_local + f"{len(content)=}")

    has_html_tags = {k: False for k, v in html_tags.items()}

    for html_tag_sets_k, html_tag_sets_v in html_tags.items():
        for k, v in tags_seen.items():
            if k in html_tag_sets_v:
                has_html_tags[html_tag_sets_k] = True

    # analyze !doctype
    has_dtd = False
    if "!doctype" in document:
        for empty_attrib in document["!doctype"][0].empty_attribs:

            # check for public identifier
            if empty_attrib.startswith("-//"):
                has_dtd = True
                match = re.search(r"-//(.*?)//DTD (.*?)//", empty_attrib)
                if match:
                    if match.group(2).startswith("XHTML"):
                        clues_toward["application/xhtml+xml"] += 1
                    elif match.group(2).startswith("SVG"):
                        clues_toward["image/svg+xml"] += 1
                    elif match.group(2).startswith("HTML"):
                        clues_toward["text/html"] += 1
                    else:
                        logger.info(
                            log_prefix_local
                            + f"unexpected DTD {match.group(2)} in {local_file}"
                        )
                continue

            # check for system identifier
            if (
                empty_attrib.startswith("http://www.w3.org/")
                or empty_attrib.startswith("DTD")
                or empty_attrib.startswith("/DTD")
                or empty_attrib.endswith(".dtd")
            ):
                has_dtd = True
                match = re.search(r"(.*?)/(.*?)\.dtd", empty_attrib)
                if "svg" in match.group(2):
                    clues_toward["image/svg+xml"] += 1
                elif "xhtml" in match.group(2):
                    clues_toward["application/xhtml+xml"] += 1
                elif "html" in match.group(2):
                    clues_toward["text/html"] += 1
                else:
                    logger.info(
                        log_prefix_local
                        + f"unexpected DTD {match.group(2)} in {local_file}"
                    )
                continue

            each_lower = empty_attrib.lower()
            if each_lower == "html":
                clues_toward["text/html"] += 2
                clues_toward["application/xhtml+xml"] += 2
                continue

            if each_lower == "svg":
                clues_toward["application/svg+xml"] += 2
                continue

            if each_lower in ["public", "system"]:
                continue

            logger.info(
                log_prefix_local
                + f"unexpected !doctype empty attrib {empty_attrib} found in "
                + local_file
            )

    if not "!doctype" in document:
        clues_toward["application/xhtml+xml"] = -float("inf")

    # check for html5
    # 3-4 points is a strong indicator
    if "!doctype" in document:
        # check for <!DOCTYPE html>
        doctype_elem = document["!doctype"][0]
        if (
            not doctype_elem.attribs
            and len(doctype_elem.empty_attribs) == 1
            and "html" in doctype_elem.empty_attribs
        ):
            clues_toward["text/html5"] += 1
    if "html" in document:
        # check for <html lang="en">
        html_elem = document["html"][0]
        if "lang" in html_elem.attribs:
            clues_toward["text/html5"] += 1
    if "meta" in document:
        # check for meta charset and content-type
        for each_meta_tag in document["meta"]:
            if (
                "charset" in each_meta_tag.attribs
                and each_meta_tag.attribs["charset"].lower() == "utf-8"
            ):
                clues_toward["text/html5"] += 1
            if "http-equiv" in each_meta_tag.attribs:
                if each_meta_tag.attribs["http-equiv"] == "content-type":
                    if "content" in each_meta_tag.attribs:
                        vals = each_meta_tag.attribs["content"].split(";")
                        for each_val in vals:
                            if "/" in each_val and each_val not in [
                                "application/xhtml+xml",
                                "text/html",
                            ]:
                                logger.info(
                                    log_prefix_local
                                    + f"unexpected meta http-equiv content-type '{each_val}'"
                                )

    if has_html_tags["html5"]:
        clues_toward["text/html5"] += 1

    # check for html element
    if "html" in document:
        clues_toward["text/html"] += 1
        clues_toward["application/xhtml+xml"] += 1
    else:
        clues_toward["application/xhtml+xml"] = -float("inf")

    # award text/html a bonus of 1 point if it has 3 or more text/html5 markers
    clues_toward["text/html"] += clues_toward["text/html5"] // 3

    # check for Atom element and namespace
    if "feed" in document:
        clues_toward["application/atom+xml"] += 1

        found_xmlns = False
        for k, v in document["feed"][0].attribs.items():
            k_lower = k.lower()
            v_lower = v.lower()
            if k_lower.startswith("xmlns") and v_lower.endswith("atom"):
                # http://www.w3.org/2005/Atom
                found_xmlns = True
                clues_toward["application/atom+xml"] += 1
        if not found_xmlns:
            clues_toward["application/atom+xml"] = -float("inf")

    # check for html element and xhtml namespace
    if "html" in document:
        found_xmlns = False
        for k, v in document["html"][0].attribs.items():
            k_lower = k.lower()
            v_lower = v.lower()
            if k_lower.startswith("xmlns") and v_lower.endswith("xhtml"):
                found_xmlns = True
                clues_toward["application/xhtml+xml"] += 1
        if not found_xmlns:
            clues_toward["application/xhtml+xml"] = -float("inf")

    # check for rss element and namespace
    if "rss" in document:
        clues_toward["application/rss+xml"] += 1
        for k, v in document["rss"][0].attribs.items():
            k_lower = k.lower()
            v_lower = v.lower()
            if k_lower == "version" and v_lower == "2.0":
                clues_toward["application/rss+xml"] += 1

    # check for svg element and namespace
    if "svg" in document:
        clues_toward["image/svg+xml"] += 1

        found_xmlns = False
        for k, v in document["svg"][0].attribs.items():
            k_lower = k.lower()
            v_lower = v.lower()
            if k_lower.startswith("xmlns") and v_lower.endswith("svg"):
                # http://www.w3.org/2000/svg
                found_xmlns = True
                clues_toward["image/svg+xml"] += 1
        if not found_xmlns:
            clues_toward["image/svg+xml"] = -float("inf")

    if has_dtd:
        clues_toward["application/xml"] += 1

    if is_wellformed_xml:
        clues_toward["application/xml"] += 1

    if "xml" in document:
        clues_toward["application/xml"] += 1
    else:
        clues_toward["application/xhtml+xml"] = -float("inf")

    if "xml" in document and "html" in document:
        clues_toward["application/xhtml+xml"] += 1

    if not has_dtd:
        clues_toward["application/xhtml+xml"] = -float("inf")

    if "head" in document and "body" in document:
        clues_toward["text/html"] += 1

    # clues_toward.sort(key=lambda x: x[1], reverse=True)
    if debug:
        # dump contents of document object
        for k, v in document.items():
            print(k)
            for each in v:
                each.dump()

    log_first_1k_chars = False

    if tags_seen:
        # 2024-02-23T13:46:37Z [new]     INFO     id 39480233: asdfft2(): timbos_textfile_format_identifier(): tags_seen=[('a', 18), ('meta', 1), ('pre', 1), ('b', 1), ('small', 1)]
        num_html_tags_seen = 0
        num_svg_tags_seen = 0
        for k in tags_seen.keys():
            if k in html_tags["current"] or k in html_tags["html5"]:
                num_html_tags_seen += 1
            if k in html_tags["obsolete_or_deprecated"]:
                num_html_tags_seen += 1
            if k in svg_tags["current"]:
                num_svg_tags_seen += 1

        if num_html_tags_seen > 0:
            clues_toward["text/html"] += 1
        if num_svg_tags_seen > 0:
            clues_toward["image/svg+xml"] += 1

        if debug:
            print(f"{tags_seen=}")
            print(f"{num_html_tags_seen=}")

    else:
        for _ in tag_based_markup_languages:
            clues_toward[_] = -float("inf")

    res = "text/plain"

    if clues_toward:
        list_sorted = sorted(clues_toward.items(), key=lambda x: x[1], reverse=True)
        list_sorted = [x for x in list_sorted if x[1] > 0]

        if debug:
            print(f"{clues_toward=}")
            print(f"{list_sorted=}")

        logger.info(log_prefix_local + f"clues_toward={list_sorted}")

        high_score = -1
        for k, v in clues_toward.items():
            if v > high_score:
                high_score = v
                res = k

        if res == "text/html5":
            res = "text/html"

        if res == "application/xml":
            # try to make more specific
            top_xml_score = 0
            for k, v in clues_toward.items():
                if k.endswith("+xml") and v > top_xml_score:
                    res = k
                    top_xml_score = v

    if res not in [
        "application/pdf",
        "application/xhtml+xml",
        "text/html",
    ]:
        log_first_1k_chars = True

    if log_first_1k_chars:
        logger.info(
            log_prefix_local
            + "first 1024 characters of content starts on next line: (~Tim~)\n"
            + content[:1024]
        )

    return res


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Usage: python utils_mimetypes_magic.py <local_file>")
        sys.exit(1)

    local_file = sys.argv[1]
    # local_file = "/srv/timbos-hn-reader/temp/test1.xml"

    log_prefix = ""

    try:
        res = get_textual_mimetype(local_file=local_file, log_prefix="", debug=True)
        print(res)
    except Exception as exc:
        short_exc_name = exc.__class__.__name__
        exc_name = exc.__class__.__module__ + "." + short_exc_name
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        logger.error(log_prefix + exc_slug)
        tb_str = traceback.format_exc()
        logger.error(log_prefix + tb_str)
