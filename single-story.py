import logging
import sys
import traceback

import config
import hn
from Story import Story

logger = logging.getLogger(__name__)


def main(id):
    log_prefix = "single-story: "
    logger.info(log_prefix + "in main")

    story_object = None
    try:
        story_object = hn.asdfft1(item_id=id, pos_on_page=1)

    except Exception as exc:
        exc_short_name = exc.__class__.__name__
        exc_name = f"{exc.__class__.__module__}.{exc_short_name}"
        exc_msg = str(exc)
        exc_slug = f"{exc_name}: {exc_msg}"
        logger.info(log_prefix + exc_slug)
        logger.info(log_prefix + f"failed to create story_object for {id=}")
        tb_str = traceback.format_exc()
        logger.info(log_prefix + tb_str)

    if not story_object:
        return 1

    hn.populate_story_card_html_in_story_object(story_object)

    if story_object.story_card_html:
        logger.info(log_prefix + "successfully created story_card_html")
    else:
        logger.info(log_prefix + "couldn't create story_card_html")

    hn.save_story_object_to_disk(story_object=story_object, log_prefix=log_prefix)


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

    log_prefix = ""

    config.load_settings("thnr", "/srv/timbos-hn-reader/settings.yaml")

    id = int(sys.argv[1])

    sys.exit(main(id=id))
