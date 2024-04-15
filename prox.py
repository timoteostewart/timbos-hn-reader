import logging

import secrets_file
import utils_http

logger = logging.getLogger(__name__)


def main():
    ps = utils_http.get_page_source_via_proxy(
        url="https://www.icanhazip.com",
        proxy=secrets_file.PROXY_URL,
    )
    print(ps)


if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03dZ %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    main()
