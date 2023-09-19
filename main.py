import datetime
import logging
import os
import os.path
import sys

import config
import hn
import update_chromedriver

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
    # typical invocation: `python main.py new thnr /srv/timbos-hn-reader/settings.yaml`
    story_type = sys.argv[1]  # e.g., `top`
    config.load_settings(sys.argv[2], sys.argv[3])

    # configure root logger
    # compute name of today's log
    cur_year = datetime.datetime.now().year
    day_of_year = datetime.date.today().timetuple().tm_yday
    log_filename = f"{config.settings['cur_host']}-thnr-{cur_year}-{day_of_year:03}.log"
    main.logger = logging.getLogger()
    main.logger.setLevel(logging.INFO)
    handler = logging.FileHandler(
        os.path.join(config.settings["THNR_BASE_DIR"], "logs", log_filename),
        "a",
        "utf-8",
    )
    story_type_padded = f"[{story_type}]     "[:9]
    handler.setFormatter(
        logging.Formatter(
            f"%(asctime)s {story_type_padded} %(levelname)-8s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S %Z",
        )
    )
    main.logger.addHandler(handler)

    main.logger.info(
        f"started thnr with story type {story_type} on host {config.settings['cur_host']}"
    )

    check_for_required_dirs()
    try:
        update_chromedriver.check_for_updated_chromedriver()
    except Exception as exc:
        main.logger.error(f"Error: {exc}. Exiting.")
        exit(1)

    return hn.supervisor(cur_story_type=story_type)


if __name__ == "__main__":
    sys.exit(main())
