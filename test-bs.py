import logging
import sys

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


tag_names_of_possible_root_elements = [
    "feed",
    "html",
    "math",
    "rss",
    "svg",
]

other_tags_to_delete = [
    "iframe",
    "link",
    "meta",
    "noscript",
    "script",
    "style",
]


def delete_specified_tag_elements(
    content: str, tags_to_delete, parser_to_use="lxml"
) -> str:
    soup = BeautifulSoup(content, parser_to_use)
    for tag_name in tags_to_delete:
        for tag in soup.find_all(tag_name):
            tag.decompose()
    return soup.prettify()


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

    local_file = sys.argv[1]
    # local_file = "/srv/timbos-hn-reader/temp/test1.xml"

    log_prefix = ""

    with open(local_file, mode="r", encoding="utf-8") as f:
        content = f.read()

    content = delete_specified_tag_elements(content=content, tags_to_delete="html")

    print(content)
