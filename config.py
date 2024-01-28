import os
import traceback

import yaml

settings = {}


def load_settings(cur_host, settings_file):
    try:
        with open(settings_file, "r", encoding="utf-8") as f:
            settings_yaml = yaml.safe_load(f)

            settings.update(settings_yaml)

            settings["cur_host"] = cur_host

            settings["TEMP_DIR"] = settings_yaml["TEMP_DIR"][settings["cur_host"]]

            settings["THNR_BASE_DIR"] = settings_yaml["THNR_BASE_DIR"][
                settings["cur_host"]
            ]
            settings["CACHED_STORIES_DIR"] = os.path.join(
                settings["THNR_BASE_DIR"], "cached_stories"
            )
            settings["COMPLETED_PAGES_DIR"] = os.path.join(
                settings["THNR_BASE_DIR"], "completed_pages"
            )
            settings["PREPARED_THUMBS_SERVICE_DIR"] = os.path.join(
                settings["THNR_BASE_DIR"], "prepared_thumbs"
            )
            settings["TEMPLATES_SERVICE_DIR"] = os.path.join(
                settings["THNR_BASE_DIR"], "templates"
            )

            settings["STATIC_URL"] = settings_yaml["STATIC_URL"][settings["cur_host"]]
            settings["STORIES_URL"] = settings_yaml["STORIES_URL"][settings["cur_host"]]
            settings["THUMBS_URL"] = settings_yaml["THUMBS_URL"][settings["cur_host"]]
            settings["CSS_URL"] = settings_yaml["STATIC_URL"][settings["cur_host"]]

            settings["SHORT_URL_DISPLAY"] = settings_yaml["SHORT_URL_DISPLAY"][
                settings["cur_host"]
            ]

            settings["CANONICAL_URL"]["LM"] = settings_yaml["CANONICAL_URL"]["LM"][
                settings["cur_host"]
            ]
            settings["CANONICAL_URL"]["DM"] = settings_yaml["CANONICAL_URL"]["DM"][
                settings["cur_host"]
            ]
            settings["HEADER_HYPERLINK"]["LM"] = settings_yaml["HEADER_HYPERLINK"][
                "LM"
            ][settings["cur_host"]]
            settings["HEADER_HYPERLINK"]["DM"] = settings_yaml["HEADER_HYPERLINK"][
                "DM"
            ][settings["cur_host"]]
            settings["ABOUT_HTML_URL"]["LM"] = settings_yaml["ABOUT_HTML_URL"]["LM"][
                settings["cur_host"]
            ]
            settings["ABOUT_HTML_URL"]["DM"] = settings_yaml["ABOUT_HTML_URL"]["DM"][
                settings["cur_host"]
            ]

    except Exception as e:
        traceback.print_exc()
        print(f"Error: {e}")
        print(f"Cannot load settings file {settings_file}. Exiting.")
        exit(1)


# AWS settings: paths in S3 bucket
# (name of actual bucket goes in `my_secrets.py`)
s3_thumbs_path = "thumbs/"
s3_stories_path = ""

# number of threads
max_workers = 14

# connections settings
delay_for_page_to_load_seconds = 4
num_tries_for_page_retrieval = 3

# other settings
reading_speed_words_per_minute = (
    250  # this is used to divide word count of article to get reading time
)

# environment details
my_wan_ip = ""

# debug flags
DEBUG_FLAG_DISABLE_CONCURRENT_PAGE_PROCESSING = False
DEBUG_TIMES_IN_UPLOAD_PAGE_OF_STORIES_TO_S3 = 0
