import datetime
import math
import time

import pytz

import text_utils

# various constants
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3_600
SECONDS_PER_DAY = 86_400
SECONDS_PER_WEEK = 604_800
SECONDS_PER_MONTH = 2_628_000
SECONDS_PER_YEAR = 31_557_600


def convert_epoch_seconds_to_utc(epoch_seconds):
    now_utc = datetime.datetime.fromtimestamp(epoch_seconds, pytz.utc)
    now_utc = str(now_utc)
    now_utc = now_utc[slice(now_utc.index("+"))]
    now_utc = now_utc.replace(" ", "T")
    now_utc += "Z"
    return now_utc


def convert_seconds_ago_to_human_readable(seconds_ago: int, force_int=False):
    if seconds_ago < SECONDS_PER_MINUTE:
        unit = "just now"
    elif seconds_ago < SECONDS_PER_HOUR:
        number = seconds_ago / SECONDS_PER_MINUTE
        unit = "minute"
    elif seconds_ago < SECONDS_PER_DAY:
        number = seconds_ago / SECONDS_PER_HOUR
        unit = "hour"
    elif seconds_ago < SECONDS_PER_WEEK:
        number = seconds_ago / SECONDS_PER_DAY
        unit = "day"
    elif seconds_ago < SECONDS_PER_MONTH:
        number = seconds_ago / SECONDS_PER_WEEK
        unit = "week"
    elif seconds_ago < SECONDS_PER_YEAR:
        number = seconds_ago / SECONDS_PER_MONTH
        unit = "month"
    else:
        number = seconds_ago / SECONDS_PER_YEAR
        unit = "year"

    if unit == "just now":
        time_ago_display = unit
    else:
        time_ago_display = (
            text_utils.add_singular_plural(number, unit, force_int=force_int) + " ago"
        )

    return time_ago_display


def convert_time_duration_to_human_readable_v1(new_page_ts):
    dt_str = str(datetime.datetime.now(tz=datetime.timezone.utc).isoformat())
    dt_str = dt_str[slice(0, dt_str.find("."))]
    dt_str += "Z"
    page_gen_elapsed = get_time_now_in_epoch_seconds_float() - new_page_ts
    if page_gen_elapsed < 1.0:
        page_gen_elapsed *= 1000
        page_gen_elapsed_str = f"{int(page_gen_elapsed)} milliseconds"
    elif page_gen_elapsed < 10.0:
        page_gen_elapsed_str = f"{round(page_gen_elapsed, 3)} seconds"
    elif page_gen_elapsed < 60.0:
        page_gen_elapsed_str = f"{int(page_gen_elapsed)} seconds"
    elif page_gen_elapsed < 600.0:
        m, s = divmod(int(page_gen_elapsed), 60)
        h, m = divmod(m, 60)
        # h = int(h)
        m = int(m)
        s = int(s)
        page_gen_elapsed_str = f"{m:01d}m:{s:02d}s"
    elif page_gen_elapsed < (3600.0):
        m, s = divmod(int(page_gen_elapsed), 60)
        h, m = divmod(m, 60)
        # h = int(h)
        m = int(m)
        s = int(s)
        page_gen_elapsed_str = f"{m:02d}m:{s:02d}s"
    elif page_gen_elapsed < (36000.0):
        m, s = divmod(int(page_gen_elapsed), 60)
        h, m = divmod(m, 60)
        h = int(h)
        m = int(m)
        s = int(s)
        page_gen_elapsed_str = f"{h:01d}h:{m:02d}m:{s:02d}s"
    else:  # page_gen_elapsed >= 36000.0
        m, s = divmod(int(page_gen_elapsed), 60)
        h, m = divmod(m, 60)
        h = int(h)
        m = int(m)
        s = int(s)
        page_gen_elapsed_str = f"{h:02d}h:{m:02d}m:{s:02d}s"

    return dt_str, page_gen_elapsed_str


def convert_time_duration_to_hms(duration_seconds):
    s_frac = duration_seconds - int(duration_seconds)
    s_frac = round(s_frac, 3)
    if s_frac == 0 or s_frac == 0.0:
        s_frac = ".000"
    else:
        s_frac = f"{str(s_frac)}000"
        s_frac = s_frac[1:5]
    m, s = divmod(int(duration_seconds), 60)
    h, m = divmod(m, 60)
    h = int(h)
    m = int(m)
    s = int(s)
    return h, m, s, s_frac


def convert_time_duration_to_human_readable(duration_sec):
    if duration_sec < 1.0:
        duration_sec *= 1000
        duration_str = f"{int(duration_sec)} milliseconds"
    elif duration_sec < 10.0:
        duration_str = f"{round(duration_sec, 3)} seconds"
    elif duration_sec < 60.0:
        duration_str = f"{int(duration_sec)} seconds"
    elif duration_sec < 600.0:
        m, s = divmod(int(duration_sec), 60)
        h, m = divmod(m, 60)
        m = int(m)
        s = int(s)
        duration_str = f"{m:01d}m:{s:02d}s"
    elif duration_sec < (3600.0):
        m, s = divmod(int(duration_sec), 60)
        h, m = divmod(m, 60)
        m = int(m)
        s = int(s)
        duration_str = f"{m:02d}m:{s:02d}s"
    elif duration_sec < (36000.0):
        m, s = divmod(int(duration_sec), 60)
        h, m = divmod(m, 60)
        h = int(h)
        m = int(m)
        s = int(s)
        duration_str = f"{h:01d}h:{m:02d}m:{s:02d}s"
    else:  # duration_sec >= 36000.0
        m, s = divmod(int(duration_sec), 60)
        h, m = divmod(m, 60)
        h = int(h)
        m = int(m)
        s = int(s)
        duration_str = f"{h:02d}h:{m:02d}m:{s:02d}s"

    return duration_str


def get_hms_for_page_gen(new_page_ts):
    this_page_elapsed_seconds = get_time_now_in_epoch_seconds_float() - new_page_ts
    m, s = divmod(this_page_elapsed_seconds, 60)
    h, m = divmod(m, 60)
    h = int(h)
    m = int(m)
    s = int(s)
    return h, m, s


def get_time_now_in_epoch_seconds_int():
    return int(time.time())


def get_time_now_in_epoch_seconds_float():
    return time.time()


def how_long_ago_human_readable(past_time_seconds):
    seconds_ago = get_time_now_in_epoch_seconds_int() - past_time_seconds
    return convert_seconds_ago_to_human_readable(seconds_ago)
