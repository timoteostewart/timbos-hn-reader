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

from MarkupTag import MarkupTag

logger = logging.getLogger(__name__)

html_tags = {}

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


def check_for_valid_text_encodings(local_file: str, log_prefix="") -> List[str]:
    # requires iconv (i.e., libiconv) command

    log_prefix_local = log_prefix + "check_for_valid_text_encodings(): "
    valid_encodings = []

    text_encodings = [
        "ASCII",
        "ISO-8859-1",
        "UTF-8",
        "WINDOWS-1251",
        # "ISO-8859-2",
        # "UTF-16",
        # "UTF-32",
        # "UTF-7",
        # "WINDOWS-1252",
    ]

    for each_encoding in text_encodings:
        cmd = f"iconv -f {each_encoding} -t {each_encoding} {local_file} -o /dev/null"

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
                valid_encodings.append(each_encoding)

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

    return valid_encodings


def check_for_wellformed_xml(local_file: str, log_prefix="") -> bool:
    # requires Linux xmlwf command
    log_prefix_local = log_prefix + "is_wellformed_xml(): "

    cmd = f"xmlwf -c {local_file}"

    try:
        res = subprocess.run(
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


def get_mimetype_via_exiftool(local_file: str, log_prefix="") -> str:
    log_prefix_local = log_prefix + "get_mimetype_via_exiftool(): "
    mimetype = None
    try:
        with exiftool.ExifToolHelper(executable="/usr/local/bin/exiftool") as et:
            metadata = et.get_metadata(local_file)[0]
            # file_type = metadata.get("File:FileType")
            # file_type_extension = metadata.get("File:FileTypeExtension")
            mimetype = metadata.get("File:MIMEType")
        logger.info(log_prefix_local + f"exiftool succeeded for {local_file}")
        return mimetype
    except Exception as exc:

        if isinstance(exc, exiftool.exceptions.ExifToolExecuteError):
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
                and paths_extension != "com"
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


def collect_empty_attributes(doctype_str: str):
    in_quote = False  # Flag to track whether we're inside quotes
    current_substr = ""  # Current substring being collected
    substrings = []  # List to hold the final substrings

    for char in doctype_str:
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
    - determine return types: { raise Exception for probably not textual, raise Exception for empty file, return string for textual mimetype }

    - add check for UTF 7, UTF 8, 16LE, 16BE, 32LE, 32BE BOMs at start of file: https://unicodebook.readthedocs.io/unicode_encodings.html#utf-7

    - fill out checks for SVG

    - figure out checks for markdown

    - document need for installing xmlwf, jq, iconv, libiconv, exiftool, etc. to stand up THNR server (not to mention ghostscript, imagemagic 6, imagemagick 7, etc.)

    - elsewhere, create way of invoking specific version of imagemagick, so we can fall back to version 6 in case of the pamcmyk32 error

    - add check for atom+xml format. https://www.ibm.com/docs/en/baw/22.x?topic=formats-atom-feed-format
    https://validator.w3.org/feed/docs/atom.html
    https://validator.w3.org/feed/docs/rfc4287.html

    - add shell subprocess call to `isutf8` ?

    - fyi, how to invoke the perl binary/text heuristic check:
        - find . -type f -print0 | perl -0nE 'say if -f and -s _ and -T _'
        - find . -type f -print0 | perl -0nE 'say if -f and -s _ and -B _'

    """

    # 2024-02-10T21:09:43Z [active]  INFO     id 39324847: asdfft2(): srct: text/html, guesses: ['text/html', 'text/html'], mts: ['text/html', 'text/html', 'text/html'], textual_mimetype='image/svg+xml' for url https://kmaasrud.com/blog/opml-is-underrated.html
    # 2024-02-11T06:56:32Z [new]     INFO     id 39327596: asdfft2(): srct: text/plain, guesses: ['text/html'], mts: ['application/json', 'application/json', 'application/json'], textual_mimetype='application/json' for url https://github.com/denkspuren/BitboardC4/blob/master/BitboardDesign.md
    # 2024-02-11T17:54:16Z [new]     INFO     id 39336677: asdfft2(): timbos_textfile_format_identifier(): clues_toward=[('text/plain', 0), ('text/html', 0), ('application/xml', 0), ('application/json', 0), ('text/markdown', 0), ('application/postscript', 0), ('image/x-eps', 0), ('application/pdf', 0), ('text/x-shellscript', 0), ('application/xhtml+xml', -inf), ('image/svg+xml', -inf)] (~Tim~)

    # defaults

    log_prefix_local = log_prefix + "timbos_textfile_format_identifier(): "

    CHARS_TO_READ = None  # 4096

    local_file = os.path.abspath(local_file)

    clues_toward = {
        "text/plain": 0,
        "text/html": 0,
        "text/html5": 0,
        "application/xml": 0,
        "application/xhtml+xml": 0,
        "image/svg+xml": 0,
        "application/json": 0,
        "text/markdown": 0,
        "application/postscript": 0,
        "image/x-eps": 0,
        "application/pdf": 0,
        "text/x-shellscript": 0,
    }

    text_encodings = check_for_valid_text_encodings(local_file, log_prefix)
    # print(text_encodings)

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
        encoding_to_use = "utf_8"
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

    # if encoding_to_use:
    #     clues_toward["text/plain"] += 1

    if is_valid_json(local_file):
        clues_toward["application/json"] += 1

    is_wellformed_xml = check_for_wellformed_xml(local_file)

    content = None
    with open(local_file, mode="r", encoding=encoding_to_use) as file:
        if CHARS_TO_READ:
            content = file.read(CHARS_TO_READ)
        else:
            content = file.read()
    if not content:
        logger.info(log_prefix_local + f"file {local_file} is empty")
        return None

    # check for PDF
    if content.startswith("%PDF-"):
        clues_toward["application/pdf"] += 1

        if content.startswith("%PDF-1."):
            clues_toward["application/pdf"] += 1

    # check for shebang
    if content.startswith("#!"):
        clues_toward["x-shellscript"] += 1

    # check for application/postscript or image/x-eps
    if content.startswith("%!"):
        clues_toward["image/x-eps"] += 1
        clues_toward["application/postscript"] += 1

        if content.startswith("%!PS"):
            clues_toward["image/x-eps"] += 1
            clues_toward["application/postscript"] += 1

        if "EPSF-3.0" in content[:30]:
            clues_toward["image/x-eps"] += 1
        if not "EPS" in content[:30]:
            clues_toward["image/x-eps"] -= 1

        # if not "%%BoundingBox:" in content:
        #     clues_toward["image/x-eps"] = 0

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
        match = re.search(r"<\?" + xml_case + r"\b(.*?)\?>", content, re.DOTALL)
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
                f" ({xml_attribute_name_re})=['\"](.*?)['\"]",
                attrib_material,
            )
            for match in matches:
                the_tag.attribs[match.group(1).lower()] = match.group(2)

            # collect attributes with unquoted values
            matches = re.finditer(
                " ("
                + xml_attribute_name_re
                + ")=("
                + xml_attribute_unquoted_value_re
                + ")",
                attrib_material,
            )
            for match in matches:
                the_tag.attribs[match.group(1).lower()] = match.group(2)

            # collect empty attributes (no value; or implicitly the empty string)
            copy_of_attrib_material = attrib_material

            for k, v in the_tag.attribs.items():
                target_re = f"{k}=['\"]{v}['\"]"
                copy_of_attrib_material = re.sub(
                    target_re, " ", copy_of_attrib_material, 1
                )
                # for values without spaces, we can also try to remove unquoted attribute values
                if not " " in v:
                    target_re = f"{k}={v}"
                    copy_of_attrib_material = re.sub(
                        target_re, " ", copy_of_attrib_material, 1
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
                f"({xml_attribute_name_re})=['\"](.*?)['\"]",
                attrib_material,
            )
            for match in matches:
                the_tag.attribs[match.group(1).lower()] = match.group(2)

            # collect attributes with unquoted values
            matches = re.finditer(
                f" ({xml_attribute_name_re})=({xml_attribute_unquoted_value_re})",
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
                            if "/" in each_val and each_val != "text/html":
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

    # check for xmlns attribute in specific tags
    has_xmlns_attr = False
    for each_tag in [
        "html",
        "svg",
        "xml",
    ]:
        if each_tag in document:
            for each_time in document[each_tag]:
                for k, v in each_time.attribs.items():
                    if k.lower() == "xmlns" and v.lower().endswith("xhtml"):
                        has_xmlns_attr = True

    if "html" in document and has_xmlns_attr:
        clues_toward["application/xhtml+xml"] += 1

    if "html" in document and not has_xmlns_attr:
        clues_toward["application/xhtml+xml"] = -float("inf")

    # check for svg element and namespace
    if "svg" in document:
        clues_toward["image/svg+xml"] += 1

        for k, v in document["svg"][0].attribs.items():
            k_lower = k.lower()
            v_lower = v.lower()
            if k_lower == "xmlns" and v_lower.endswith("svg"):
                has_xmlns_attr = True
                clues_toward["image/svg+xml"] += 1
    else:
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

    if not has_dtd or not has_xmlns_attr:
        clues_toward["application/xhtml+xml"] = -float("inf")

    if "body" in document and "head" in document:
        clues_toward["text/html"] += 1

    # clues_toward.sort(key=lambda x: x[1], reverse=True)
    if debug:
        # dump contents of document object
        for k, v in document.items():
            print(k)
            for each in v:
                each.dump()

    list_sorted = sorted(clues_toward.items(), key=lambda x: x[1], reverse=True)
    list_sorted = [x for x in list_sorted if x[1] > 0]

    if debug:
        print(list_sorted)

    res = "text/plain"
    high_score = -1
    for k, v in clues_toward.items():
        if v > high_score:
            high_score = v
            res = k

    if res == "text/html5":
        logger.info(log_prefix_local + f"text/html5 (~Tim~)")
        res = "text/html"

    logger.info(log_prefix_local + f"clues_toward={list_sorted}")

    if res not in ["text/html", "application/xhtml+xml"]:
        logger.info(log_prefix_local + "(~Tim~)\n" + content[:1024])

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

