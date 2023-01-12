import logging
import traceback

import undetected_chromedriver as uc
from selenium.webdriver.chrome.service import Service

import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_chromedriver_noproxy(user_agent=""):
    chrome_options = uc.ChromeOptions()
    # chrome_options.add_argument("--disable-gpu")  # note: required for dockerized Chrome
    chrome_options.add_argument("--headless")  # note: required
    chrome_options.add_argument("--incognito")  # optional
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    if user_agent:
        chrome_options.add_argument(f"--user-agent={user_agent}")

    chrome_service = Service(
        executable_path=config.settings["SCRAPING"]["PATH_TO_CHROMEDRIVER"]
    )

    try:
        driver = uc.Chrome(
            browser_executable_path=config.settings["SCRAPING"][
                "PATH_TO_CHROME_BROWSER"
            ],
            options=chrome_options,
            service=chrome_service,
            use_subprocess=False,
        )
    except Exception as exc:
        logger.error(f"get_chromedriver_noproxy(): {exc}")
        traceback.print_exc()
        raise exc

    return driver
