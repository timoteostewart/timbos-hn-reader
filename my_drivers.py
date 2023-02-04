import logging
import sys
import traceback

import undetected_chromedriver as uc
from selenium.webdriver.chrome.service import Service

import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_chromedriver_noproxy(user_agent="", requestor=""):
    chrome_options = uc.ChromeOptions()
    # chrome_options.add_argument("--disable-gpu")  # note: no longer required for dockerized Chrome
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--headless")  # note: required
    chrome_options.add_argument("--incognito")  # optional
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--verbose")

    chrome_options.add_argument("--allow-insecure-localhost")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument(
        "--disable-browser-side-navigation"
    )  # https://stackoverflow.com/a/49123152/1689770
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument(
        "--disable-gpu"
    )  # https://stackoverflow.com/questions/51959986/how-to-solve-selenium-chromedriver-timed-out-receiving-message-from-renderer-exc
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-setuid-sandbox")
    chrome_options.add_argument(
        "--enable-automation"
    )  # https://stackoverflow.com/a/43840128/1689770
    chrome_options.add_argument("--force-device-scale-factor=2.0")
    chrome_options.add_argument("--high-dpi-support=2.0")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--mute-audio")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument(
        "start-maximized"
    )  # https://stackoverflow.com/a/26283818/1689770
    chrome_options.add_argument("window-size=1920x1200")

    chrome_options.add_argument("--bwsi")
    chrome_options.add_argument("--noerrdialogs")
    chrome_options.add_argument("--start-maximized")

    # https://stackoverflow.com/questions/62889739/selenium-gives-timed-out-receiving-message-from-renderer-for-all-websites-afte
    chrome_options.add_experimental_option(
        "prefs",
        {
            "intl.accept_languages": "en,en_US",
            "download.prompt_for_download": False,
            "download.default_directory": "/dev/null",
            "automatic_downloads": 2,
            "download_restrictions": 3,
            "notifications": 2,
            "media_stream": 2,
            "media_stream_mic": 2,
            "media_stream_camera": 2,
            "durable_storage": 2,
        },
    )

    chrome_options.headless = True

    # chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])  # doesn't work

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
        logger.error(
            f"{sys._getframe(  ).f_code.co_name}: {requestor} failed to get a driver: {exc}"
        )
        traceback.print_exc()
        raise exc

    driver.set_page_load_timeout(180)
    driver.implicitly_wait(180)

    logger.info(f"{sys._getframe(  ).f_code.co_name}: {requestor} got a driver")
    return driver
