import builtins
import json
import logging
import mimetypes
import os
import re
import subprocess
import sys
import traceback
from collections import Counter, defaultdict
from typing import List
from urllib.parse import unquote, urlparse

import magic
from bs4 import BeautifulSoup
from intervaltree import IntervalTree

from Attribute import AttributeWithKey
from MarkupTag import MarkupTag
from Trie import Trie

logger = logging.getLogger(__name__)

html_tags = {}
svg_tags = {}
mathml_tags = {}

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

html_tags["github"] = set(
    [
        "action-menu",
        "anchored-position",
        "auto-check",
        "clipboard-copy",
        "cookie-consent",
        "cookie-consent-link",
        "custom-scopes",
        "details-dialog",
        "dialog-helper",
        "focus-group",
        "include-fragment",
        "modal-dialog",
        "qbsearch-input",
        "query-builder",
        "react-partial",
        "relative-time",
        "scrollable-region",
        "tool-tip",
        "turbo-frame",
    ]
)

html_tags["xml"] = set(
    [
        "!doctype",
        "?xml",
    ]
)

html_tags["php"] = set(
    [
        "?php",
    ]
)


all_html_tag_names = set()
all_html_tag_names.update(html_tags["current"])
all_html_tag_names.update(html_tags["obsolete_or_deprecated"])
all_html_tag_names.update(html_tags["html5"])
all_html_tag_names.update(html_tags["github"])
all_html_tag_names.update(html_tags["xml"])
all_html_tag_names.update(html_tags["php"])

svg_tags["current"] = set(
    [
        "a",
        "animate",
        "animatemotion",
        "animatetransform",
        "circle",
        "clippath",
        "defs",
        "desc",
        "ellipse",
        "feblend",
        "fecolormatrix",
        "fecomponenttransfer",
        "fecomposite",
        "feconvolvematrix",
        "fediffuselighting",
        "fedisplacementmap",
        "fedistantlight",
        "fedropshadow",
        "feflood",
        "fefunca",
        "fefuncb",
        "fefuncg",
        "fefuncr",
        "fegaussianblur",
        "feimage",
        "femerge",
        "femergenode",
        "femorphology",
        "feoffset",
        "fepointlight",
        "fespecularlighting",
        "fespotlight",
        "fetile",
        "feturbulence",
        "filter",
        "foreignobject",
        "g",
        "hatch",
        "hatchpath",
        "image",
        "line",
        "lineargradient",
        "marker",
        "mask",
        "metadata",
        "mpath",
        "path",
        "pattern",
        "polygon",
        "polyline",
        "radialgradient",
        "rect",
        "script",
        "set",
        "stop",
        "style",
        "svg",
        "switch",
        "symbol",
        "text",
        "textpath",
        "title",
        "tspan",
        "use",
        "view",
    ]
)

all_svg_tag_names = set()
all_svg_tag_names.update(svg_tags["current"])


mathml_tags["presentation"] = set(
    [
        "annotation",
        "annotation-xml",
        "maction",
        "math",
        "menclose",
        "merror",
        "mfenced",
        "mfrac",
        "mi",
        "mmultiscripts",
        "mn",
        "mo",
        "mover",
        "mpadded",
        "mphantom",
        "mprescripts",
        "mroot",
        "mrow",
        "ms",
        "mspace",
        "msqrt",
        "mstyle",
        "msub",
        "msubsup",
        "msup",
        "mtable",
        "mtd",
        "mtext",
        "mtr",
        "munder",
        "munderover",
        "semantics",
    ]
)

mathml_tags["content"] = set(
    [
        "abs",
        "and",
        "approx",
        "arccos",
        "arccosh",
        "arccot",
        "arccoth",
        "arccsc",
        "arccsch",
        "arcsec",
        "arcsech",
        "arcsin",
        "arcsinh",
        "arctan",
        "arctanh",
        "arg",
        "card",
        "cartesianproduct",
        "ceiling",
        "ci",
        "ci",
        "cn",
        "cn",
        "cn",
        "codomain",
        "complexes",
        "compose",
        "condition",
        "conjugate",
        "cos",
        "cosh",
        "cot",
        "coth",
        "csc",
        "csch",
        "csymbol",
        "csymbol",
        "curl",
        "degree",
        "determinant",
        "diff",
        "divergence",
        "divide",
        "domain",
        "domainofapplication",
        "emptyset",
        "eq",
        "equivalent",
        "eulergamma",
        "exists",
        "exp",
        "exponentiale",
        "factorial",
        "factorof",
        "false",
        "floor",
        "forall",
        "gcd",
        "geq",
        "grad",
        "gt",
        "ident",
        "image",
        "imaginary",
        "imaginaryi",
        "implies",
        "in",
        "infinity",
        "int",
        "integers",
        "intersect",
        "interval",
        "interval",
        "inverse",
        "lambda",
        "laplacian",
        "lcm",
        "leq",
        "limit",
        "list",
        "ln",
        "log",
        "logbase",
        "logbase",
        "lowlimit",
        "lt",
        "matrix",
        "matrixrow",
        "max",
        "mean",
        "median",
        "min",
        "minus",
        "mode",
        "moment",
        "momentabout",
        "momentabout",
        "naturalnumbers",
        "neq",
        "not",
        "notanumber",
        "notin",
        "notprsubset",
        "notsubset",
        "or",
        "otherwise",
        "outerproduct",
        "partialdiff",
        "pi",
        "piece",
        "piecewise",
        "plus",
        "power",
        "primes",
        "product",
        "prsubset",
        "quotient",
        "rationals",
        "real",
        "reals",
        "rem",
        "root",
        "scalarproduct",
        "sdev",
        "sec",
        "sech",
        "selector",
        "sep",
        "set",
        "setdiff",
        "sin",
        "sinh",
        "subset",
        "sum",
        "tan",
        "tanh",
        "tendsto",
        "times",
        "transpose",
        "true",
        "union",
        "uplimit",
        "variance",
        "vector",
        "vectorproduct",
        "xor",
    ]
)

all_mathml_tag_names = set()
all_mathml_tag_names.update(mathml_tags["presentation"])
all_mathml_tag_names.update(mathml_tags["content"])

tag_based_markup_languages = [
    "application/atom+xml",
    "application/rss+xml",
    "application/mathml+xml",
    "application/xhtml+xml",
    "application/xml",
    "image/svg+xml",
    "text/html",
    "text/html5",
]


def check_for_valid_text_encodings(local_file: str, log_prefix="") -> List[str]:
    # requires iconv (i.e., libiconv) command

    log_prefix_local = log_prefix + "check_for_valid_text_encodings: "
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
            result = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True,
            )
            if result.returncode == 0:
                valid_encodings.append(each_encoding)
            else:
                continue

        except subprocess.CalledProcessError:
            # non-zero return code
            continue

        except Exception as exc:
            short_exc_name = exc.__class__.__name__
            exc_name = exc.__class__.__module__ + "." + short_exc_name
            exc_msg = str(exc)
            exc_slug = f"{exc_name}: {exc_msg}"
            logger.error(log_prefix_local + "unexpected exception: " + exc_slug)
            tb_str = traceback.format_exc()
            logger.error(log_prefix_local + tb_str)
            continue

    if "UTF-8" in valid_encodings:
        if not is_utf8_via_python(local_file):
            valid_encodings.remove("UTF-8")
            logger.info(
                log_prefix_local
                + f"`iconv -f UTF-8` succeeded, but `isutf8` failed for {local_file} ~Tim~"
            )

    return valid_encodings


def is_wellformed_xml_func(local_file: str, log_prefix="") -> bool:
    # requires Linux xmlwf command
    log_prefix_local = log_prefix + "is_wellformed_xml_func: "

    cmd = f"xmlwf -c {local_file}"

    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
        )
        if result.returncode == 0:
            return True

    except subprocess.CalledProcessError:
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
    # requires Linux isutf8 command
    log_prefix_local = log_prefix + "is_utf8: "

    cmd = f"isutf8 {local_file}"

    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
        )
        if result.returncode == 0:
            return True

    except Exception as exc:
        if isinstance(exc, subprocess.CalledProcessError):
            pass

        else:
            exc_name = exc.__class__.__name__
            exc_fq_name = exc.__class__.__module__ + "." + exc_name
            exc_msg = str(exc)
            exc_slug = f"{exc_fq_name}: {exc_msg}"
            logger.error(log_prefix_local + "unexpected exception: " + exc_slug)
            tb_str = traceback.format_exc()
            logger.error(log_prefix_local + tb_str)

    return False


def is_utf8_via_python(local_file: str, log_prefix="") -> bool:
    log_prefix_local = log_prefix + "is_utf8_via_python: "
    with open(local_file, "rb") as file:
        data = file.read()
        try:
            data.decode("UTF-8")
            return True
        except Exception as exc:
            if isinstance(exc, builtins.UnicodeDecodeError):
                pass
            else:
                exc_name = exc.__class__.__name__
                exc_fq_name = exc.__class__.__module__ + "." + exc_name
                exc_msg = str(exc)
                exc_slug = f"{exc_fq_name}: {exc_msg}"
                logger.error(log_prefix_local + "unexpected exception: " + exc_slug)
                tb_str = traceback.format_exc()
                logger.error(log_prefix_local + tb_str)

    return False


def is_valid_json(local_file: str, log_prefix="") -> bool:
    # requires Linux jq command
    log_prefix_local = log_prefix + "is_valid_json: "

    cmd = f"jq . {local_file}"

    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
        )
        if result.returncode == 0:
            return True

    except Exception as exc:
        if isinstance(exc, subprocess.CalledProcessError):
            pass
        else:
            exc_name = exc.__class__.__name__
            exc_fq_name = exc.__class__.__module__ + "." + exc_name
            exc_msg = str(exc)
            exc_slug = f"{exc_fq_name}: {exc_msg}"
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
        "inode/x-empty",
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
        "binary/octet-stream",
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
        "image/xvg+xml",
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


# def get_mimetype(
#     local_file: str, srct: str = None, url: str = None, story_object=None, log_prefix=""
# ) -> str:

#     log_prefix_local = log_prefix + "get_mimetype: "

#     if srct:
#         srcts = re.split("[;,]", srct)
#         srct = srcts[0].strip().lower()

#     # use trusted tools to check if file is probably binary
#     trusted_sources = Counter(
#         [
#             get_mimetype_via_python_magic(local_file=local_file, log_prefix=log_prefix),
#             get_mimetype_via_file_command(local_file=local_file, log_prefix=log_prefix),
#             get_mimetype_via_exiftool2(local_file=local_file, log_prefix=log_prefix),
#         ]
#     )

#     consensus_ct = None
#     if len(trusted_sources) == 1 and srct == trusted_sources.most_common(1)[0][0]:
#         # all 3 trusted sources agree with srct
#         consensus_ct = srct
#     elif len(trusted_sources) == 1:
#         # all 3 trusted sources agree; srct differs or is absent
#         consensus_ct = trusted_sources.most_common(1)[0][0]
#     elif len(trusted_sources) == 2 and srct == trusted_sources.most_common(1)[0][0]:
#         # 2 trusted sources agree with srct
#         consensus_ct = srct
#     elif len(trusted_sources) == 2:
#         # 2 trusted sources agree; srct differs or is absent
#         consensus_ct = trusted_sources.most_common(1)[0][0]
#     elif len(trusted_sources) >= 2 and srct in trusted_sources:
#         # 1 or 2 trusted sources agree with srct
#         consensus_ct = srct
#     else:
#         # no consensus
#         pass
#     # TODO: could fall back to guessing mimetype from URL

#     # if file is probably binary, invoke get_textual_mimetype just in case

#     # if file is probably not binary, invoke get_textual_mimetype


# def get_mimetype_via_exiftool(local_file: str, log_prefix="") -> str:
#     log_prefix_local = log_prefix + "get_mimetype_via_exiftool: "
#     mimetype = None
#     try:
#         with exiftool.ExifToolHelper(executable="/usr/local/bin/exiftool") as et:
#             metadata = et.get_metadata(local_file)[0]
#             # file_type = metadata.get("File:FileType")
#             # file_type_extension = metadata.get("File:FileTypeExtension")
#             mimetype = metadata.get("File:MIMEType")
#         # logger.info(log_prefix_local + f"exiftool succeeded for {local_file}")
#         return mimetype

#     except Exception as exc:
#         if isinstance(exc, exiftool.exceptions.ExifToolExecuteError):
#             logger.error(log_prefix_local + exc_slug)
#             tb_str = traceback.format_exc()
#             logger.error(log_prefix_local + tb_str)

#         elif isinstance(exc, exiftool.exceptions.ExifToolVersionError):
#             logger.error(log_prefix_local + exc_slug)
#             tb_str = traceback.format_exc()
#             logger.error(log_prefix_local + tb_str)

#         else:
#             short_exc_name = exc.__class__.__name__
#             exc_name = exc.__class__.__module__ + "." + short_exc_name
#             exc_msg = str(exc)
#             exc_slug = f"{exc_name}: {exc_msg}"
#             logger.error(log_prefix_local + "unexpected exception: " + exc_slug)
#             tb_str = traceback.format_exc()
#             logger.error(log_prefix_local + tb_str)

#         logger.info(log_prefix_local + f"exiftool failed for {local_file} ~Tim~")

#         return None


def get_mimetype_via_exiftool2(local_file: str, log_prefix="") -> str:
    log_prefix_local = log_prefix + "get_mimetype_via_exiftool2: "
    mimetype = None

    cmd = f'/usr/local/bin/exiftool -File:MIMEType "{local_file}"'

    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
        )

        if result.stdout:
            match = re.search(r"MIME Type[\ ]*:\ ", result.stdout)
            if match:
                mimetype = result.stdout.split(":")[-1].strip()
                return mimetype
            else:
                return None
        else:
            return None

    except Exception as exc:
        exc_name = exc.__class__.__name__
        fq_exc_name = exc.__class__.__module__ + "." + exc_name
        exc_msg = str(exc)
        exc_slug = f"{fq_exc_name}: {exc_msg}"

        if isinstance(exc, subprocess.CalledProcessError):
            logger.info(log_prefix_local + exc_slug)

        else:
            logger.error(log_prefix_local + "unexpected exception: " + exc_slug)
            tb_str = traceback.format_exc()
            logger.error(log_prefix_local + result.stderr)
            logger.error(log_prefix_local + tb_str)

        with open(local_file, mode="rb") as file:
            bytes = file.read(512)
            logger.error(log_prefix_local + f"{bytes=} ~Tim~")

        return None


def get_mimetype_via_file_command(local_file, log_prefix="") -> str:
    log_prefix_local = log_prefix + "get_mimetype_via_file_command: "

    cmd = f"/srv/timbos-hn-reader/getmt local {local_file}"

    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
        )
        if result.returncode == 0:
            result_stdout = result.stdout
        else:
            return None

    except Exception as exc:
        short_exc_name = exc.__class__.__name__
        exc_fq_name = exc.__class__.__module__ + "." + short_exc_name
        exc_msg = str(exc)
        exc_slug = f"{exc_fq_name}: {exc_msg}"
        tb_str = traceback.format_exc()

        if isinstance(exc, subprocess.CalledProcessError):
            logger.error(log_prefix_local + exc_slug)
            logger.error(log_prefix_local + tb_str)

        else:
            logger.error(log_prefix_local + "unexpected exception: " + exc_slug)
            logger.error(log_prefix_local + tb_str)

        return None

    # result_stdout is json, so decode it into a python dictionary
    result_json = json.loads(result_stdout)
    return result_json["mimetype"]


def get_mimetype_via_python_magic(local_file, log_prefix="") -> str:
    log_prefix_local = log_prefix + "get_mimetype_via_python_magic: "
    try:
        magic_type_as_mimetype = magic.from_file(local_file, mime=True)
        return magic_type_as_mimetype
    except Exception as exc:
        short_exc_name = exc.__class__.__name__
        exc_name = exc.__class__.__module__ + "." + short_exc_name
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        tb_str = traceback.format_exc()
        logger.error(log_prefix_local + "unexpected exception: " + exc_slug)
        logger.error(log_prefix_local + tb_str)

    return None


def guess_mimetype_from_uri_extension(url, log_prefix="", debug=False, context=None):
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Common_types
    # https://www.digipres.org/formats/mime-types/#application/illustrator%0A
    # https://www.digipres.org/formats/sources/fdd/formats/#fdd000018

    log_prefix_local = log_prefix + "guess_mimetype_from_uri_extension: "

    # raw.githubusercontent.com

    if context and "url" in context:
        url_slug = f" for url=({context['url']}) "
    else:
        url_slug = ""

    guesses = defaultdict(list)

    # get tld for url
    parsed_url = urlparse(url)
    tld = parsed_url.netloc.split(".")[-1]

    path = unquote(parsed_url.path)
    paths_extension = os.path.splitext(path)[1]
    if debug:
        logger.info(
            log_prefix_local
            + f"{parsed_url.netloc=} {tld=} {paths_extension=} {path=} {parsed_url.query=} {url_slug}"
        )

    if f".{tld}" == paths_extension:
        logger.info(
            log_prefix_local + f".tld=.{tld} equals {paths_extension=} {url_slug}~Tim~"
        )

    # guess using mimetypes and the file extension as extracted from the URL by os.path.splitext()
    guess_by_mimetypes_using_filename = None
    if paths_extension:
        guess_by_mimetypes_using_filename, _ = mimetypes.guess_type(
            f"foo.{paths_extension}", strict=False
        )
        if guess_by_mimetypes_using_filename:
            guesses[guess_by_mimetypes_using_filename.lower()].append(
                "guess_by_mimetypes_using_filename"
            )

    # guess using mimetypes and the entire URL
    # (anecdotally, it's sloppier than the preceding method)
    guess_by_mimetypes = None
    guess_by_mimetypes, _ = mimetypes.guess_type(url, strict=False)
    if guess_by_mimetypes:
        guesses[guess_by_mimetypes.lower()].append("guess_by_mimetypes")

    guesses_set = set(guesses.keys())

    if len(guesses_set) > 1:
        logger.info(
            log_prefix_local + f"multiple guesses {guesses_set} {url_slug}~Tim~"
        )

    incorrect_associations_tld_to_mimetype = [
        ("ai", "application/postscript"),
        ("ai", "application/vnd.adobe.illustrator"),
        ("cc", "text/x-c++src"),
        ("com", "application/x-msdos-program"),
        ("info", "application/x-info"),
        ("org", "application/vnd.lotus-organizer"),
        ("pl", "text/x-perl"),
        ("sh", "text/x-sh"),
        ("xyz", "chemical/x-xyz"),
        ("zip", "application/x-zip"),
        ("zip", "application/x-zip-compressed"),
        ("zip", "application/zip"),
    ]

    for each in incorrect_associations_tld_to_mimetype:
        if tld == each[0] and each[1] in guesses_set and paths_extension != f".{tld}":
            old_guess = each[1]
            guessers_slug = ", ".join(guesses[old_guess])
            logger.info(
                log_prefix_local
                + f"discarding '{old_guess}' by {guessers_slug} {url_slug}~Tim~"
            )
            guesses_set.remove(old_guess)

    incorrect_associations_paths_extension_to_mimetype = [
        (".aspx", "application/x-wine-extension-ini", "text/html"),
        (".csp", "application/vnd.commonspace", "text/html"),
        (".rs", "application/rls-services+xml", "text/rust"),  # nonstandard mimetype
    ]

    for each in incorrect_associations_paths_extension_to_mimetype:
        if each[0] == paths_extension and each[1] in guesses_set:
            old_guess = each[1]
            new_guess = each[2]
            guessers_slug = ", ".join(guesses[old_guess])
            logger.info(
                log_prefix_local
                + f"changing '{old_guess}' to '{new_guess}' by {guessers_slug} {url_slug}~Tim~"
            )
            guesses_set.remove(old_guess)
            guesses_set.add(new_guess)

    # my domain-based overrides
    if parsed_url.netloc == "github.com":
        # example URLs:
        # https://github.com/rkaehn/cr_task.h
        # https://github.com/rkaehn/cr_task.h/blob/main/cr_task.h
        new_guess = "text/html"
        logger.info(
            log_prefix_local + f"overriding {guesses_set=} to '{new_guess}' {url_slug}"
        )
        guesses_set.clear()
        guesses_set.add(new_guess)
    # elif parsed_url.netloc == "raw.githubusercontent.com":
    #     # example URLs:
    #     # https://raw.githubusercontent.com/rkaehn/cr_task.h/main/cr_task.h
    #     pass

    return list(x for x in guesses_set if x)


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

        elif char == "'":  # Toggle the in_quote flag when we hit a quote
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

    substrings = [x.strip() for x in substrings]
    substrings = [x for x in substrings if x]

    return substrings


white_space_chars = set(
    [
        " ",
        "\f",
        "\n",
        "\v",
        "\r",
        "\t",
    ]
)


def delete_specified_tag_elements(
    content: str, tags_to_delete, parser_to_use="lxml"
) -> str:
    soup = BeautifulSoup(content, parser_to_use)
    for tag_name in tags_to_delete:
        for tag in soup.find_all(tag_name):
            tag.decompose()
    return soup.prettify()


def get_textual_mimetype(local_file, log_prefix="", debug=False, context=None) -> str:
    """Discriminate between HTML, HTML5, JSON, plain text, XHTML, XHTML5, and XML"""

    """

    todo:


    - figure out checks for markdown

    - document the prerequisites of installing xmlwf, jq, iconv, libiconv, exiftool, isutf8 etc. to stand up THNR server (not to mention ghostscript, imagemagic 6, imagemagick 7, etc.)



    - add check for atom+xml format. https://www.ibm.com/docs/en/baw/22.x?topic=formats-atom-feed-format
    https://validator.w3.org/feed/docs/atom.html
    https://validator.w3.org/feed/docs/rfc4287.html



    """

    # TODO: compare "tags seen" with textfile_format_identifier result, particular the tag soup when the result is text/plain or None
    # for text/html, what are the top 5 tags seen? for xhtml+xml? for text/html5?
    # compare "tags seen" with textfile_format_identifier result, particular the tag soup when the result is text/plain or None

    log_prefix_local = log_prefix + "get_textual_mimetype: "

    none_tuple = (None, None, None)

    if context and "url" in context:
        file_url_slug = f"{local_file=} url={context['url']} "
    else:
        file_url_slug = f"{local_file=}"

    local_file = os.path.abspath(local_file)

    text_encodings = check_for_valid_text_encodings(local_file, log_prefix)

    if not text_encodings:
        logger.info(log_prefix_local + f"probably binary file {file_url_slug}")
        return none_tuple

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
                content = file.read()
            for char in content:
                if ord(char) < 32:
                    if context and "url" in context:
                        logger.info(
                            log_prefix_local + f"probably binary file {file_url_slug}"
                        )
                        return none_tuple
                    else:
                        logger.info(
                            log_prefix_local + f"probably binary file {file_url_slug}"
                        )
                        return none_tuple
                elif 127 <= ord(char) <= 159:
                    if context and "url" in context:
                        logger.info(
                            log_prefix_local + f"probably binary file {file_url_slug}"
                        )
                        return none_tuple
                    else:
                        logger.info(
                            log_prefix_local + f"probably binary file {file_url_slug}"
                        )
                        return none_tuple

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
        "application/xml": 0,  # sometimes seen as 'text/xml'
        "application/atom+xml": 0,
        "application/rss+xml": 0,
        "application/xhtml+xml": 0,
        "application/mathml+xml": 0,
        "image/svg+xml": 0,
        "application/json": 0,
        "application/postscript": 0,
        "image/x-eps": 0,
        "application/pdf": 0,
        "text/x-shellscript": 0,
    }

    content = None
    with open(local_file, mode="r", encoding=encoding_to_use) as file:
        content = file.read()

    if not content:
        logger.info(log_prefix_local + f"empty file {local_file=}")
        return none_tuple

    while content[0] in white_space_chars:
        content = content[1:]

    logger.info(log_prefix_local + f"{len(content)=}")

    logger.info(log_prefix_local + f"{encoding_to_use=} out of {text_encodings=}")

    content = re.sub(r"\s+", " ", content)

    first_128 = content[:128].replace("\n", " ")
    logger.info(log_prefix_local + f"content[:128]={first_128}")

    if is_valid_json(local_file):
        clues_toward["application/json"] += 1
    else:
        clues_toward["application/json"] = -float("inf")

    is_wellformed_xml = is_wellformed_xml_func(local_file)

    # check for PDF
    if content.startswith("%PDF-"):
        clues_toward["application/pdf"] += 1

        if content.startswith("%PDF-1."):
            clues_toward["application/pdf"] += 1
    else:
        clues_toward["application/pdf"] = -float("inf")

    # check for shell script
    if content.startswith("#!"):
        clues_toward["text/x-shellscript"] += 1
    else:
        clues_toward["text/x-shellscript"] = -float("inf")

    # check for application/postscript or image/x-eps
    if content.startswith("%!PS"):
        clues_toward["application/postscript"] += 1
        clues_toward["image/x-eps"] += 1

        if "EPS" in content[:30]:
            clues_toward["image/x-eps"] += 1
            if "EPSF-3.0" in content[:30]:
                clues_toward["image/x-eps"] += 1
    else:
        clues_toward["application/postscript"] = -float("inf")
        clues_toward["image/x-eps"] = -float("inf")

    document = defaultdict(list)
    document_data = {}

    # xml_attribute_name_re = r"""[^\t\n\f \/>'"=]+"""  # per https://html.spec.whatwg.org/multipage/syntax.html#attributes-2
    xml_attribute_name_re = "[^\\t\\n\\f \\/>'\"=]+"  # rewritten to avoid raw string

    # xml_attribute_unquoted_value_re = r"""[^\t\n\f "'/<=>\`]+"""
    xml_attribute_unquoted_value_re = (
        "[^\\t\\n\\f \"'/<=>\\`]+"  # rewritten to avoid raw string
    )

    # TODO: I'll need to start saving a literal copy of the attribute K-V pair, because not all K-V pairs
    # will omit spaces around the equals sign, as the code around the empty attributes collection assumes.
    # this will probably entail an update to the MarkupTag class.

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

            # collect attributes with single-quoted values
            matches = re.finditer(
                f" ?({xml_attribute_name_re}) *= *('.+?')",
                attrib_material,
            )
            for match in matches:
                # the_tag.attribs[match.group(1).lower()] = match.group(2)[1:-1]
                new_attrib = AttributeWithKey(
                    attribute_literal=match.group().strip(" "),
                    key_literal=match.group(1),
                    value_literal=match.group(2),
                )
                the_tag.attribs[new_attrib.key] = new_attrib

            # collect attributes with double-quoted values
            matches = re.finditer(
                f' ?({xml_attribute_name_re}) *= *(".+?")',
                attrib_material,
            )
            for match in matches:
                # the_tag.attribs[match.group(1).lower()] = match.group(2)[1:-1]
                new_attrib = AttributeWithKey(
                    attribute_literal=match.group().strip(" "),
                    key_literal=match.group(1),
                    value_literal=match.group(2),
                )
                the_tag.attribs[new_attrib.key] = new_attrib

            # collect attributes with unquoted values
            matches = re.finditer(
                f" ?({xml_attribute_name_re}) *= *({xml_attribute_unquoted_value_re})",
                attrib_material,
            )
            for match in matches:
                # the_tag.attribs[match.group(1).lower()] = match.group(2)
                new_attrib = AttributeWithKey(
                    attribute_literal=match.group().strip(" "),
                    key_literal=match.group(1),
                    value_literal=match.group(2),
                )
                the_tag.attribs[new_attrib.key] = new_attrib

            # collect empty attributes (no value; or implicitly the empty string)
            copy_of_attrib_material = attrib_material
            for each_attr in the_tag.attribs.values():
                copy_of_attrib_material = copy_of_attrib_material.replace(
                    each_attr.attribute_literal, " "
                )

            the_tag.empty_attribs.extend(
                collect_empty_attributes(copy_of_attrib_material)
            )

    tag_names_of_possible_root_elements = [
        "feed",
        "html",
        "math",
        "rss",
        "svg",
    ]

    tags_to_check = [
        # !doctype
        "!doctype",
        # root elements
        *tag_names_of_possible_root_elements,
        # other significant elements
        "head",
        "title",
        "meta",
        "body",
    ]

    for each_tag in [item for elem in tags_to_check for item in (elem, elem.upper())]:
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

            tree = IntervalTree()

            matches_kv_attribs = []

            # collect non-empty attributes with single-quoted values
            matches = re.finditer(
                f" ?({xml_attribute_name_re}) *= *'([^']+?)'",
                attrib_material,
            )
            matches_kv_attribs.extend(matches)

            # collect non-empty attributes with double-quoted values
            matches = re.finditer(
                f' ?({xml_attribute_name_re}) *= *"([^"]+?)"',
                attrib_material,
            )
            matches_kv_attribs.extend(matches)

            # collect non-empty attributes with unquoted values
            matches = re.finditer(
                f" ?({xml_attribute_name_re}) *= *({xml_attribute_unquoted_value_re})",
                attrib_material,
            )
            matches_kv_attribs.extend(matches)

            for match in matches_kv_attribs:
                if tree[match.start()]:
                    continue
                # the_tag.attribs[match.group(1).lower()] = match.group(2)
                tree[match.start() : match.end()] = True

                new_attrib = AttributeWithKey(
                    attribute_literal=match.group().strip(" "),
                    key_literal=match.group(1),
                    value_literal=match.group(2),
                )
                the_tag.attribs[new_attrib.key] = new_attrib

            copy_of_attrib_material = attrib_material
            for each_attr in the_tag.attribs.values():
                copy_of_attrib_material = copy_of_attrib_material.replace(
                    each_attr.attribute_literal, " "
                )

            the_tag.empty_attribs.extend(
                collect_empty_attributes(copy_of_attrib_material)
            )

    # check in !doctype for declared root element
    declared_root_element = None
    root_element_xmlns = None
    if "!doctype" in document and document["!doctype"][0].empty_attribs:
        declared_root_element = document["!doctype"][0].empty_attribs[0]

        if declared_root_element.lower() in tag_names_of_possible_root_elements:
            if declared_root_element in document:
                if "xmlns" in document[declared_root_element][0].attribs:
                    root_element_xmlns = document[declared_root_element][0].attribs[
                        "xmlns"
                    ]
                    logger.info(
                        log_prefix_local
                        + f"{declared_root_element=}, xmlns={root_element_xmlns}, {is_wellformed_xml=} {file_url_slug}"
                    )

        else:
            logger.info(
                log_prefix_local
                + f"unexpected {declared_root_element=} {file_url_slug}"
            )
            declared_root_element = None

    if declared_root_element:
        if declared_root_element.lower() == "html":
            clues_toward["text/html"] += 1  # and text/html5

    if root_element_xmlns:
        clues_toward["application/xhtml+xml"] += 1
    else:
        clues_toward["application/xhtml+xml"] = -float("inf")

    # check in !doctype for FPI and system identifier
    has_formal_public_identifier = False
    has_system_identifier = False
    if "!doctype" in document:
        for empty_attrib in document["!doctype"][0].empty_attribs:
            # check for formal public identifier (FPI)
            if empty_attrib.startswith("-//"):
                has_formal_public_identifier = True  # noqa: F841
                match = re.search(r"-//(.*?)//DTD (.*?)//", empty_attrib)
                if match:
                    document_data["FPI"] = empty_attrib
                    if match.group(2).startswith("HTML"):
                        clues_toward["text/html"] += 1
                    elif match.group(2).startswith("MathML"):
                        clues_toward["application/mathml+xml"] += 1
                    elif match.group(2).startswith("SVG"):
                        clues_toward["image/svg+xml"] += 1
                    elif match.group(2).startswith("XHTML"):
                        clues_toward["application/xhtml+xml"] += 1
                    else:
                        logger.info(
                            log_prefix_local
                            + f"unexpected FPI '{match.group(2)}' {file_url_slug}"
                        )
                continue

            # check for system identifier
            if (
                empty_attrib.startswith("http://www.w3.org/")
                or empty_attrib.startswith("https://www.w3.org/")
                or empty_attrib.startswith("DTD")
                or empty_attrib.startswith("/DTD")
                or empty_attrib.endswith(".dtd")
            ):
                has_system_identifier = True  # noqa: F841
                document_data["SI"] = empty_attrib
                # http://www.w3.org/1999/html
                # http://www.w3.org/1999/xhtml
                # http://www.w3.org/TR/html4/loose.dtd
                # http://www.w3.org/TR/html4/strict.dtd
                # http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd
                # http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd
                # https://www.w3.org/1999/xhtml
                match = re.search(r"(.*/)([^/]*)$", empty_attrib)
                if match.group(2).startswith("xhtml"):
                    clues_toward["application/xhtml+xml"] += 1
                elif match.group(1).endswith("/TR/html4/"):
                    clues_toward["text/html"] += 1
                elif match.group(2).startswith("svg1"):
                    clues_toward["image/svg+xml"] += 1
                elif match.group(2).startswith("mathml"):
                    clues_toward["application/mathml+xml"] += 1
                else:
                    logger.info(
                        log_prefix_local
                        + f"unexpected system_identifier='{empty_attrib}' {file_url_slug}"
                    )
                continue

            each_lower = empty_attrib.lower()
            if each_lower in ["public", "system"]:
                continue
            if declared_root_element and each_lower == declared_root_element.lower():
                continue

            logger.info(
                log_prefix_local
                + f"unexpected !doctype empty_attrib='{empty_attrib}' {file_url_slug}"
            )

    fpi_si_slug = ""
    if "FPI" in document_data:
        fpi_si_slug += f"FPI='{document_data['FPI']}'"
    if "SI" in document_data:
        if fpi_si_slug:
            fpi_si_slug += " "
        fpi_si_slug += f"SI='{document_data['SI']}'"
    if fpi_si_slug:
        logger.info(log_prefix_local + f"{fpi_si_slug} {file_url_slug}")

    # quickly check if we're likely dealing with an html file, so we can delete superfluous root element tags
    #    to get a more accurate identification
    if not declared_root_element:
        if "head" in document and "title" in document and "body" in document:
            declared_root_element = (
                "html"  # putatively declare the root element to be html
            )

    if declared_root_element:
        # delete other root element tags used as inline or embedded elements in the document
        copy_of_tag_names_of_possible_root_elements = list(
            tag_names_of_possible_root_elements
        )
        copy_of_tag_names_of_possible_root_elements.remove(
            declared_root_element.lower()
        )
        tags_to_delete = copy_of_tag_names_of_possible_root_elements
        tags_to_delete.extend(["iframe", "link", "noscript", "script", "style"])
        if root_element_xmlns:
            parser_to_use = "lxml-xml"
        else:
            parser_to_use = "lxml"
        content = delete_specified_tag_elements(
            content=content, tags_to_delete=tags_to_delete, parser_to_use=parser_to_use
        )
        for each in tags_to_delete:
            _ = document.pop(each, None)

    if "!doctype" not in document:
        clues_toward["application/xhtml+xml"] = -float("inf")

    # check for various clues for html, html5, xhtml
    if "html" in document:
        clues_toward["application/xhtml+xml"] += 1
        clues_toward["text/html"] += 1  # and html5

        html_elem = document["html"][0]
        has_common_html5_html_tag_attributes = False
        for each in [
            "dir",
            "lang",
            "manifest",
        ]:
            if each in html_elem.attribs:
                has_common_html5_html_tag_attributes = True

        if has_common_html5_html_tag_attributes:
            clues_toward["text/html5"] += 1

        # if "lang" in html_elem.attribs:
        #     clues_toward["text/html"] += 1  # and html5

        if "xml:lang" in html_elem.attribs:
            clues_toward["application/xhtml+xml"] += 1

    if "html" not in document:
        clues_toward["application/xhtml+xml"] = -float("inf")
        clues_toward["text/html5"] = -float("inf")

    if "head" in document and "body" in document:
        clues_toward["application/xhtml+xml"] += 1
        clues_toward["text/html"] += 1  # and html5
    else:
        clues_toward["application/xhtml+xml"] = -float("inf")
        clues_toward["text/html5"] = -float("inf")

    if "head" in document and "title" in document:
        clues_toward["text/html"] += 1  # and html5
        clues_toward["application/xhtml+xml"] += 1

    if (
        "html" in document
        and "!doctype" in document
        and declared_root_element
        and declared_root_element.lower() == "html"
    ):
        clues_toward["application/xhtml+xml"] += 1
        clues_toward["text/html5"] += 1

    if "xml" in document:
        clues_toward["application/xml"] += 1
        if "html" in document:
            clues_toward["application/xhtml+xml"] += 1
    # else:
    #     clues_toward["application/xhtml+xml"] = -float("inf")

    found_meta_charset = False
    found_meta_http_equiv = False
    found_meta_viewport = False
    if "meta" in document:
        # check for clues in meta tags
        for each_meta_tag in document["meta"]:
            # <meta charset="utf-8">
            if (
                "charset" in each_meta_tag.attribs
                and each_meta_tag.attribs["charset"].value.lower() == "utf-8"
            ):
                found_meta_charset = True

            # <meta http-equiv="content-type" content="text/html; charset=UTF-8">
            if "http-equiv" in each_meta_tag.attribs:
                if each_meta_tag.attribs["http-equiv"].value.lower() == "content-type":
                    if "content" in each_meta_tag.attribs:
                        for each_val in re.split(
                            "[;,]", each_meta_tag.attribs["content"].value
                        ):
                            if "/" in each_val and each_val not in [
                                "application/xhtml+xml",
                                "text/html",
                            ]:
                                logger.info(
                                    log_prefix_local
                                    + f"unexpected meta http-equiv content-type '{each_val}'"
                                )
                            elif each_val == "text/html":
                                clues_toward["text/html5"] += 1
                                found_meta_http_equiv = True
                            elif each_val == "application/xhtml+xml":
                                clues_toward["application/xhtml+xml"] += 1
                                found_meta_http_equiv = True
                            elif each_val.startswith("charset"):
                                try:
                                    if each_val.split("=")[1].lower() == "utf-8":
                                        found_meta_charset = True
                                except IndexError:
                                    logger.info(
                                        log_prefix_local
                                        + f"unexpected meta http-equiv content-type charset '{each_val}'"
                                    )

            # <meta name="viewport" content="width=device-width, initial-scale=1">
            # <meta name="viewport" content="initial-scale=1.0, maximum-scale=1.0, minimum-scale=1.0 user-scalable=no, width=device-width">

            if "name" in each_meta_tag.attribs:
                if each_meta_tag.attribs["name"].value.lower() == "viewport":
                    if "content" in each_meta_tag.attribs:
                        found_meta_viewport = True
                        for each in re.split(
                            "[;, ]+", each_meta_tag.attribs["content"].value.lower()
                        ):
                            if not each:
                                continue
                            try:
                                k, v = each.split("=")
                            except (IndexError, ValueError):
                                if each in ["minimal-ui"]:
                                    continue

                                logger.info(
                                    log_prefix_local
                                    + f"unexpected meta viewport content value '{each}'"
                                )
                                continue

                            if k == "width" and v.lower() == "device-width":
                                clues_toward["text/html5"] += 1
                            elif k == "initial-scale":
                                clues_toward["text/html5"] += 1

            if found_meta_charset and found_meta_http_equiv and found_meta_viewport:
                break

    if found_meta_charset:
        clues_toward["text/html5"] += 1

    # check all sorts of tags to apply any statistical heuristics
    tag_counts = Counter()
    # pattern = r"<([A-Za-z0-9\-]+)(.*?)/?>"
    # matches = re.finditer(pattern, content, re.DOTALL)
    pattern1 = r"<([^\ />]+?)/?>"  # for tags with no attributes
    pattern2 = r"<([^\ />]+?) +(.*?)/?>"  # for tags with attributes
    matches = []
    matches.extend(re.finditer(pattern1, content, re.DOTALL))
    matches.extend(re.finditer(pattern2, content, re.DOTALL))
    for match in matches:
        if match.group().startswith("<!--"):
            continue
        elif match.group().endswith("-->"):
            continue
        else:
            tag_counts[match.group(1).lower()] += 1
    if tag_counts:
        logger.info(
            log_prefix_local
            + f"tag_counts={sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)}"
        )

    # has_html_tags = {k: False for k in html_tags.keys()}
    # for html_tag_sets_k, html_tag_sets_v in html_tags.items():
    #     for tag_counts_k in tag_counts.keys():
    #         if tag_counts_k in html_tag_sets_v:
    #             has_html_tags[html_tag_sets_k] = True
    # if has_html_tags["html5"]:
    #     clues_toward["text/html5"] += 1

    # award text/html all of text/html5's points
    if clues_toward["text/html5"] > 0:
        clues_toward["text/html"] += clues_toward["text/html5"]

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
    # if "html" in document:
    #     found_xmlns = False
    #     for k, v in document["html"][0].attribs.items():
    #         k_lower = k.lower()
    #         v_lower = v.lower()
    #         if k_lower.startswith("xmlns") and v_lower.endswith("xhtml"):
    #             found_xmlns = True
    #             clues_toward["application/xhtml+xml"] += 1
    #     if not found_xmlns:
    #         clues_toward["application/xhtml+xml"] = -float("inf")

    # check for rss element and namespace
    if "rss" in document:
        clues_toward["application/rss+xml"] += 1
        for k, v in document["rss"][0].attribs.items():
            k_lower = k.lower()
            v_lower = v.lower()
            if k_lower == "version" and v_lower == "2.0":
                clues_toward["application/rss+xml"] += 1
    else:
        clues_toward["application/rss+xml"] = -float("inf")

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
    else:
        clues_toward["image/svg+xml"] = -float("inf")

    # check for math element and namespace
    if "math" in document:
        clues_toward["application/mathml+xml"] += 1
        found_xmlns = False
        for k, v in document["math"][0].attribs.items():
            k_lower = k.lower()
            v_lower = v.lower()
            if k_lower.startswith("xmlns") and v_lower.endswith("MathML"):
                # http://www.w3.org/1998/Math/MathML
                found_xmlns = True
                clues_toward["application/mathml+xml"] += 1
        if not found_xmlns:
            clues_toward["application/mathml+xml"] = -float("inf")
    else:
        clues_toward["application/mathml+xml"] = -float("inf")

    # if has_dtd:
    #     clues_toward["application/xhtml+xml"] += 1
    #     clues_toward["application/xml"] += 1

    if is_wellformed_xml:
        clues_toward["application/atom+xml"] += 1
        clues_toward["application/mathml+xml"] += 1
        clues_toward["application/rss+xml"] += 1
        clues_toward["application/xhtml+xml"] += 1
        clues_toward["application/xml"] += 1
        clues_toward["image/svg+xml"] += 1

    # if not has_formal_public_identifier:
    #     clues_toward["application/xhtml+xml"] = -float("inf")

    # clues_toward.sort(key=lambda x: x[1], reverse=True)
    if debug:
        # dump contents of document object
        for k, v in document.items():
            print(k)
            for each_tag_to_delete in v:
                each_tag_to_delete.dump()

    log_first_1k_chars = False

    num_nonstandard_tag_names_seen = 0

    if tag_counts:
        num_html_tag_names_seen = 0
        num_svg_tag_names_seen = 0
        num_mathml_tag_names_seen = 0
        nonstandard_tags_population = 0

        nonstd_tag_names = []

        for k, v in tag_counts.items():
            k_lower = k.lower()
            if k_lower in all_html_tag_names:
                num_html_tag_names_seen += 1
            elif k_lower in all_svg_tag_names:
                num_svg_tag_names_seen += 1
            elif k_lower in all_mathml_tag_names:
                num_mathml_tag_names_seen += 1
            else:
                num_nonstandard_tag_names_seen += 1
                nonstandard_tags_population += v
                nonstd_tag_names.append(k_lower)

        if nonstd_tag_names:
            nonstd_tag_names.sort()
            logger.info(log_prefix_local + f"{nonstd_tag_names=}")

        if num_html_tag_names_seen > 0:
            clues_toward["text/html"] += 1
            clues_toward["application/xhtml+xml"] += 1
        if num_svg_tag_names_seen > 0:
            clues_toward["image/svg+xml"] += 1
        if num_mathml_tag_names_seen > 0:
            clues_toward["application/mathml+xml"] += 1

        if num_nonstandard_tag_names_seen > 0:
            nonstd_as_pct_of_names = (
                num_nonstandard_tag_names_seen * 100 / len(tag_counts.keys())
            )
            nonstd_as_pct_of_tags = (
                nonstandard_tags_population * 100 / sum(tag_counts.values())
            )

        # if debug:
        #     logger.debug(f"{tag_counts=}")
        #     logger.debug(f"{num_html_tag_names_seen=}")

    else:
        for _ in tag_based_markup_languages:
            clues_toward[_] = -float("inf")

    res = "text/plain"

    if clues_toward["image/svg+xml"] <= 1:
        clues_toward["image/svg+xml"] = 0

    if clues_toward:
        list_sorted = sorted(clues_toward.items(), key=lambda x: x[1], reverse=True)
        list_sorted_pruned = [x for x in list_sorted if x[1] > 0]

        high_score = -1
        for k, v in list_sorted_pruned:
            if v >= high_score:
                high_score = v
                res = k

        if num_nonstandard_tag_names_seen > 0:
            # this indicates a possibly unreliable conclusion
            logger.info(
                log_prefix_local + f"clues_toward={list_sorted_pruned}, "
                f"nonstd_as_pct_of_names={nonstd_as_pct_of_names:.1f}%, "
                f"nonstd_as_pct_of_tags={nonstd_as_pct_of_tags:.1f}% {file_url_slug}"
            )
        else:
            logger.info(log_prefix_local + f"clues_toward={list_sorted_pruned}")

        logger.debug(log_prefix_local + f"list_sorted={list_sorted}")

        if res == "text/html5":
            res = "text/html"

        if res == "application/xml":
            # try to make more specific
            top_xml_score = 0
            for k, v in clues_toward.items():
                if k.endswith("+xml") and v > top_xml_score:
                    logger.info(
                        log_prefix_local
                        + f"increased precision of textual_mimetype={res} to {k} {file_url_slug} ~Tim~"
                    )
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
            + f"first 1024 characters of content starts on next line. {file_url_slug} ~Tim~\n"
            + content[:1024]
        )

    logger.info(log_prefix_local + f"{res=}")

    return (res, content, is_wellformed_xml)


if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    # formatter = MicrosecondFormatter("%(asctime)s %(levelname)-8s %(message)s")
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if len(sys.argv) < 2:
        print("Usage: python utils_mimetypes_magic.py <local_file>")
        sys.exit(1)

    log_prefix = ""

    if sys.argv[1] == "--guess-from-url":
        url = sys.argv[2]
        guess_mimetype_from_uri_extension(url, log_prefix, debug=True)

    else:
        local_file = sys.argv[1]

        try:
            res = get_textual_mimetype(local_file=local_file, log_prefix="", debug=True)
            print(f"\n{res[0]}\n")
        except Exception as exc:
            short_exc_name = exc.__class__.__name__
            exc_name = exc.__class__.__module__ + "." + short_exc_name
            exc_msg = str(exc)
            exc_slug = f"{exc_name}: {exc_msg}"
            logger.error(log_prefix + exc_slug)
            tb_str = traceback.format_exc()
            logger.error(log_prefix + tb_str)
