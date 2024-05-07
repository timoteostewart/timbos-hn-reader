import os
import time

os.environ["TZ"] = "UTC"
time.tzset()

import atexit  # noqa: E402
import datetime  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import logging.config  # noqa: E402
import logging.handlers  # noqa: E402
import os.path  # noqa: E402
import queue  # noqa: E402
import sys  # noqa: E402
import traceback  # noqa: E402
import tracemalloc  # noqa: E402

import config  # noqa: E402
import hn  # noqa: E402
import utils_text  # noqa: E402

tracemalloc.start()

logger = None

## TODO:
# - create kafka_logger in main.py
# - in other files, import main, and then use kafka_logger.info() etc.


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
            except Exception as exc:
                logger.error(
                    f"Error: {exc}. Missing required dir {each_dir} and was unable to create it. Exiting."
                )
                exit(1)


def main():
    story_type = sys.argv[1]
    config.load_settings(sys.argv[2], sys.argv[3])

    ### Logging setup starts

    # Load configuration from a JSON file
    with open("logging_config.json", mode="r", encoding="utf-8") as file:
        logging_config = json.load(file)

    # configure root logger
    # compute name of today's log
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    cur_year = utc_now.year
    day_of_year = utc_now.date().timetuple().tm_yday
    cur_year_and_doy = f"{cur_year}-{day_of_year:03}"

    # Set filenames dynamically
    logging_config["handlers"]["file_handler_main"]["filename"] = os.path.join(
        config.settings["THNR_BASE_DIR"],
        "logs",
        f"{config.settings['cur_host']}-thnr-{cur_year_and_doy}.log",
    )
    logging_config["handlers"]["file_handler_alt"]["filename"] = os.path.join(
        config.settings["THNR_BASE_DIR"],
        "logs",
        f"{config.settings['cur_host']}-combined-{cur_year_and_doy}.log",
    )

    story_type_padded = f"[{story_type}]     "[:9]
    logging_config["formatters"]["unified"]["format"] = (
        f"%(asctime)s.%(msecs)03dZ {story_type_padded} %(levelname)-8s %(message)s"
    )

    my_queue = queue.Queue()
    logging_config["handlers"]["queue_handler"]["queue"] = my_queue

    # Apply logging configuration
    logging.config.dictConfig(logging_config)

    downstream_handlers_objects = []

    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if (
            isinstance(handler, logging.handlers.QueueHandler)
            and handler.queue is my_queue
        ):
            queue_handler = handler
            break

    if not queue_handler:
        raise ValueError("queue_handler not found")

    # unified_formatter = logging.Formatter(
    #     f"%(asctime)s.%(msecs)03dZ {story_type_padded} %(levelname)-8s %(message)s",
    #     datefmt="%Y-%m-%dT%H:%M:%S",
    # )
    main_log_filename = f"{config.settings['cur_host']}-thnr-{cur_year_and_doy}.log"
    alt_log_filename = f"{config.settings['cur_host']}-combined-{cur_year_and_doy}.log"
    handler_main = logging.FileHandler(
        os.path.join(config.settings["THNR_BASE_DIR"], "logs", main_log_filename),
        mode="a",
        encoding="utf-8",
    )
    handler_alt = logging.FileHandler(
        os.path.join(config.settings["THNR_BASE_DIR"], "logs", alt_log_filename),
        mode="a",
        encoding="utf-8",
    )
    # handler_main.setFormatter(unified_formatter)
    # handler_alt.setFormatter(unified_formatter)

    downstream_handlers_objects = [handler_main, handler_alt]

    queue_listener = logging.handlers.QueueListener(
        queue_handler.queue,
        *downstream_handlers_objects,
        respect_handler_level=True,
    )
    queue_listener.start()
    atexit.register(queue_listener.stop)
    for handler in logging.getLogger().handlers:
        if hasattr(handler, "stop"):
            atexit.register(handler.stop)

    logger = logging.getLogger(__name__)

    ### Logging setup ends

    log_prefix = "main: "

    for k, v in config.debug_flags.items():
        if v:
            logger.info(log_prefix + f"{k}={v}")

    if config.debug_flags["DEBUG_FLAG_FORCE_SINGLE_THREAD_EXECUTION"]:
        workers_slug = "1 thread"
    else:
        workers_slug = utils_text.add_singular_plural(
            config.max_workers, "thread", force_int=True
        )

    logger.info(
        log_prefix
        + f"started thnr with story type {story_type} on host {config.settings['cur_host']} with {workers_slug}"
    )

    # check_for_proxy()

    check_for_required_dirs()
    exit_code = None
    try:
        exit_code = hn.supervisor(cur_story_type=story_type)

    except Exception as exc:
        tb_str = traceback.format_exc()
        logger.error(log_prefix + f"{exc.__class__.__name__} {str(exc)}")
        logger.error(log_prefix + f"{tb_str}")
        exit_code = 1

    delay = 60
    logger.info(
        log_prefix
        + f"Pausing for {delay} seconds before exiting (to let Node/Playwright tidy up)."
    )
    time.sleep(delay)

    logger.info(log_prefix + f"Now exiting with exit code {exit_code}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
