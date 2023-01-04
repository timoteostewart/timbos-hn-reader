import logging
import traceback

import undetected_chromedriver as uc

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_chromedriver_noproxy(user_agent=""):
    chrome_options = uc.ChromeOptions()
    chrome_options.add_argument("--disable-gpu")  # note: required for dockerized Chrome
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--incognito")  # optional
    chrome_options.add_argument("--no-sandbox")

    if user_agent:
        chrome_options.add_argument(f"--user-agent={user_agent}")

    try:  # `undetected-chrome` helps to access websites sitting behind a CDN
        driver = uc.Chrome(
            options=chrome_options,
            use_subprocess=True,
        )  # `use_subprocess=True` is required by `uc.Chrome()` but must be removed for `webservice.Chrome()`
    except Exception as exc:
        logger.error(f"get_chromedriver_noproxy(): {exc}")
        traceback.print_exc()
        raise exc

    return driver
