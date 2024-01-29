import os
import time

os.environ["TZ"] = "UTC"
time.tzset()

import datetime
import logging
import os.path
import re
import sys
import traceback

import config
import hn
import text_utils

logger = None


def check_for_required_dirs():
    required_directories = [
        config.settings["CACHED_STORIES_DIR"],
        config.settings["COMPLETED_PAGES_DIR"],
        config.settings["PREPARED_THUMBS_SERVICE_DIR"],
        config.settings["TEMPLATES_SERVICE_DIR"],
    ]

    for each_dir in required_directories:
        if not os.path.isdir(each_dir):
            try:
                os.makedirs(each_dir)
            except Exception as e:
                main.logger.error(
                    f"Error: {e}. Missing required dir {each_dir} and was unable to create it. Exiting."
                )
                exit(1)


def main():
    log_prefix = "main(): "

    story_type = sys.argv[1]
    config.load_settings(sys.argv[2], sys.argv[3])

    # configure root logger
    # compute name of today's log
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    cur_year = utc_now.year
    day_of_year = utc_now.date().timetuple().tm_yday
    cur_year_and_doy=f"{cur_year}-{day_of_year:03}"
    main_log_filename = (
        f"{config.settings['cur_host']}-thnr-{cur_year_and_doy}.log"
    )
    main.logger = logging.getLogger()
    main.logger.setLevel(logging.INFO)

    handler_main = logging.FileHandler(
        os.path.join(config.settings["THNR_BASE_DIR"], "logs", main_log_filename),
        mode="a",
        encoding="utf-8",
    )
    story_type_padded = f"[{story_type}]     "[:9]
    handler_main.setFormatter(
        logging.Formatter(
            f"%(asctime)s {story_type_padded} %(levelname)-8s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
    )
    main.logger.addHandler(handler_main)

    alt_log_filename = (
        f"{config.settings['cur_host']}-combined-{cur_year_and_doy}.log"
    )
    handler_alt = logging.FileHandler(
        os.path.join(config.settings["THNR_BASE_DIR"], "logs", alt_log_filename),
        mode="a",
        encoding="utf-8",
    )
    story_type_padded = f"[{story_type}]     "[:9]
    handler_alt.setFormatter(
        logging.Formatter(
            f"%(asctime)s {story_type_padded} %(levelname)-8s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
    )
    main.logger.addHandler(handler_alt)

    if config.DEBUG_FLAG_DISABLE_CONCURRENT_PAGE_PROCESSING:
        workers_slug = "1 thread"
    else:
        workers_slug = text_utils.add_singular_plural(
            config.max_workers, "thread", force_int=True
        )

    main.logger.info(
        log_prefix
        + f"started thnr with story type {story_type} on host {config.settings['cur_host']} with {workers_slug}"
    )

    check_for_required_dirs()
    exit_code = None
    try:
        # update_chromedriver.check_for_updated_chromedriver()
        exit_code = hn.supervisor(cur_story_type=story_type)

    except Exception as exc:
        tb_str = traceback.format_exc()
        main.logger.error(log_prefix + f"{exc.__class__.__name__} {str(exc)}")
        main.logger.error(log_prefix + f"{tb_str}")
        exit_code = 1

    delay = 30
    main.logger.info(
        log_prefix
        + f"Pausing for {delay} seconds before exiting (to let Node/Playwright tidy up)."
    )
    time.sleep(delay)

    main.logger.info(log_prefix + f"Now exiting with exit code {exit_code}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
