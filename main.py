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
import utils_text

logger = None

# TODO: 2024-01-30T07:41:55Z [new]     ERROR    id 39187286: asdfft(): has_thumb is True, but there's no image_slug, so updating as_thumb to False ~Tim~
# TODO: 2024-01-30T07:59:10Z [new]     INFO     id 39187463: d_og_i(): get(): MissingSchema: Invalid URL '../../uploads/farewell_djangosites.jpg': No scheme supplied. Perhaps you meant https://../../uploads/farewell_djangosites.jpg?
# TODO: endpoint_query_via_requests(): problem querying url https://api.ipify.org?format=json: SSLError: HTTPSConnectionPool(host='api.ipify.org', port=443): Max retries exceeded with url: /?format=json (Caused by SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1007)'))) ; will delay 4 seconds and retry (retries left 10)
# TODO: 2024-01-31T06:13:33Z [active]  INFO     id 39196532: asdfft(): found og:image url //stsci-opo.org/STScI-01HM9KB3F5RCZ5KPA4P9V3B987.png
# TODO: 2024-01-31T06:13:57Z [active]  INFO     id 39196532: d_og_i(): get(): attempting to heal and retry schemeless og:image URL //stsci-opo.org/STScI-01HM9KB3F5RCZ5KPA4P9V3B987.png as http://webbtelescope.org/stsci-opo.org/STScI-01HM9KB3F5RCZ5KPA4P9V3B987.png


def check_for_required_dirs():
    required_directories = [
        config.settings["CACHED_STORIES_DIR"],
        config.settings["COMPLETED_PAGES_DIR"],
        config.settings["PREPARED_THUMBS_SERVICE_DIR"],
        config.settings["TEMPLATES_SERVICE_DIR"],
        config.settings["SCRATCH_DIR"],
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

    log_prefix = "main: "

    story_type = sys.argv[1]
    config.load_settings(sys.argv[2], sys.argv[3])

    # configure root logger
    # compute name of today's log
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    cur_year = utc_now.year
    day_of_year = utc_now.date().timetuple().tm_yday
    cur_year_and_doy = f"{cur_year}-{day_of_year:03}"
    main_log_filename = f"{config.settings['cur_host']}-thnr-{cur_year_and_doy}.log"
    main.logger = logging.getLogger()
    main.logger.setLevel(logging.INFO)

    handler_main = logging.FileHandler(
        os.path.join(config.settings["THNR_BASE_DIR"], "logs", main_log_filename),
        mode="a",
        encoding="utf-8",
    )
    story_type_padded = f"[{story_type}]     "[:9]

    formatter = logging.Formatter(
        f"%(asctime)s.%(msecs)03dZ {story_type_padded} %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    handler_main.setFormatter(formatter)
    main.logger.addHandler(handler_main)

    alt_log_filename = f"{config.settings['cur_host']}-combined-{cur_year_and_doy}.log"
    handler_alt = logging.FileHandler(
        os.path.join(config.settings["THNR_BASE_DIR"], "logs", alt_log_filename),
        mode="a",
        encoding="utf-8",
    )
    story_type_padded = f"[{story_type}]     "[:9]
    handler_alt.setFormatter(
        logging.Formatter(
            f"%(asctime)s.%(msecs)03dZ {story_type_padded} %(levelname)-8s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    main.logger.addHandler(handler_alt)

    for k, v in config.debug_flags.items():
        if v:
            main.logger.info(log_prefix + f"{k}={v}")

    if config.debug_flags["DEBUG_FLAG_FORCE_SINGLE_THREAD_EXECUTION"]:
        workers_slug = "1 thread"
    else:
        workers_slug = utils_text.add_singular_plural(
            config.max_workers, "thread", force_int=True
        )

    main.logger.info(
        log_prefix
        + f"started thnr with story type {story_type} on host {config.settings['cur_host']} with {workers_slug}"
    )

    check_for_required_dirs()
    exit_code = None
    try:
        exit_code = hn.supervisor(cur_story_type=story_type)

    except Exception as exc:
        tb_str = traceback.format_exc()
        main.logger.error(log_prefix + f"{exc.__class__.__name__} {str(exc)}")
        main.logger.error(log_prefix + f"{tb_str}")
        exit_code = 1

    delay = 60
    main.logger.info(
        log_prefix
        + f"Pausing for {delay} seconds before exiting (to let Node/Playwright tidy up)."
    )
    time.sleep(delay)

    main.logger.info(log_prefix + f"Now exiting with exit code {exit_code}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
