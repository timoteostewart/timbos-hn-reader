import re
import statistics
from dataclasses import dataclass
from typing import Dict, List

import numpy as np

log_path = "/mnt/synology/logs/thnr2.home.arpa/"


@dataclass
class StoryProcessingEvent:
    id: int = -1
    start_time: int = -1
    end_time: int = -1
    processing_duration: int = -1
    uncached_story: bool = False
    cached_story: bool = False
    freshened_story: bool = False
    reused_story: bool = False
    has_thumbnail: bool = False


@dataclass
class StoryTypeSession:
    id: str
    start_time: int = -1
    end_time: int = -1
    duration: int = -1
    num_stories: int = 0
    stories_per_second: float = 0.0
    story_type: str = None


events = {}
sessions = {}
id_to_uid = {}


def create_incrementer(starting_number):
    def inner():
        nonlocal starting_number
        while True:
            yield starting_number
            starting_number += 1

    return inner()


uid_generator = create_incrementer(1)
cur_session_id = None

for year in ["2024"]:

    for day in range(1, 366):

        log_file = f"thnr-thnr-{year}-{day:0>3}.log"

        print(f"{log_file=}")

        # first check if the file exists
        try:
            with open(log_path + log_file, mode="r", encoding="utf-8") as file:
                pass
        except FileNotFoundError:
            continue

        with open(log_path + log_file, mode="r", encoding="utf-8") as file:
            lines = file.readlines()

        for line in lines:

            # print(line.strip())

            # check for an id in line
            pattern = r"id (\d{8})"
            match = re.search(pattern, line)
            if match:
                id = match.group(1)
            else:
                continue

            try:
                event_time = (
                    int(line[11:13]) * 3600 + int(line[14:16]) * 60 + int(line[17:19])
                )
            except Exception as exc:
                print(f"{exc}: {line}")
                continue

            # 2023, 2024
            if "no cached story found" in line:
                uid = next(uid_generator)
                events[uid] = StoryProcessingEvent(
                    id=id, start_time=event_time, uncached_story=True
                )
                id_to_uid[id] = uid
                if cur_session_id:
                    sessions[cur_session_id].num_stories += 1

            # 2023, 2024
            elif "cached story found" in line:
                uid = next(uid_generator)
                events[uid] = StoryProcessingEvent(
                    id=id, start_time=event_time, cached_story=True
                )
                id_to_uid[id] = uid
                if cur_session_id:
                    sessions[cur_session_id].num_stories += 1

            # 2023
            elif "og:image file has magic type" in line:
                uid = id_to_uid[id]
                if uid in events:
                    events[uid].has_thumbnail = True

            # 2024
            elif "will have a thumbnail" in line:
                uid = id_to_uid[id]
                if uid in events:
                    events[uid].has_thumbnail = True

            # 2023
            elif "pickling item for the first time" in line:
                uid = id_to_uid[id]
                if uid in events:
                    events[uid].end_time = event_time
                    events[uid].processing_duration = (
                        events[uid].end_time - events[uid].start_time
                    )
                    id_to_uid[id] = None

            # 2024
            elif "saving item to disk for the first time" in line:
                uid = id_to_uid[id]
                if uid in events:
                    events[uid].end_time = event_time
                    events[uid].processing_duration = (
                        events[uid].end_time - events[uid].start_time
                    )
                    id_to_uid[id] = None

            # 2023, early 2024
            elif "re-pickling freshened story" in line:
                uid = id_to_uid[id]
                if uid in events:
                    events[uid].end_time = event_time
                    events[uid].processing_duration = (
                        events[uid].end_time - events[uid].start_time
                    )
                    events[uid].freshened_story = True
                    id_to_uid[id] = None

            # 2023
            elif "re-pickling re-used cached story" in line:
                uid = id_to_uid[id]
                if uid in events:
                    events[uid].end_time = event_time
                    events[uid].processing_duration = (
                        events[uid].end_time - events[uid].start_time
                    )
                    events[uid].reused_story = True
                    id_to_uid[id] = None

            # 2024
            elif "re-using cached story" in line:
                uid = id_to_uid[id]
                if uid in events:
                    events[uid].reused_story = True
                    events[uid].cached_story = True

            # 2024
            elif "successfully freshened story" in line:
                uid = id_to_uid[id]
                if uid in events:
                    events[uid].freshened_story = True
                    events[uid].cached_story = True

            # 2024
            elif "successfully created story_card_html" in line:
                uid = id_to_uid[id]
                if uid in events:
                    events[uid].end_time = event_time
                    events[uid].processing_duration = (
                        events[uid].end_time - events[uid].start_time
                    )
                    id_to_uid[id] = None

            else:
                # 2023-01-13 00:16:28 CST [top]     INFO     supervisor(top) with unique id eadb8101687e4588fae5bae270d09145433f4c2a started at 2023-01-13T06:16:28Z
                match = re.search(
                    r"supervisor\(([^\)]+)\) with unique id ([a-f0-9]{40})", line
                )
                if match:
                    story_type = str(match.group(1))
                    session_id = str(match.group(2))

                    if "started" in line:
                        sessions[session_id] = StoryTypeSession(
                            id=session_id, start_time=event_time, story_type=story_type
                        )
                        cur_session_id = session_id
                    elif "completed" in line:
                        sessions[session_id].end_time = event_time
                        sessions[session_id].duration = (
                            sessions[session_id].end_time
                            - sessions[session_id].start_time
                            + 86400
                        ) % 86400

                        sessions[session_id].stories_per_second = (
                            sessions[session_id].num_stories
                            / sessions[session_id].duration
                        )
                        cur_session_id = None

                    continue

                # 2024-03-01T03:57:24Z [new]     INFO     supervisor(new) with id 5f351bbe0781: completed in 00:03:22.451 at 2024-03-01T03:57:24Z
                match = re.search(
                    r"supervisor\(([^\)]+)\) with id ([a-f0-9]{12})", line
                )
                if match:
                    story_type = str(match.group(1))
                    session_id = str(match.group(2))

                    if "started" in line:
                        sessions[session_id] = StoryTypeSession(
                            id=session_id, start_time=event_time, story_type=story_type
                        )
                        cur_session_id = session_id
                    elif "completed" in line:
                        sessions[session_id].end_time = event_time
                        sessions[session_id].duration = (
                            sessions[session_id].end_time
                            - sessions[session_id].start_time
                            + 86400
                        ) % 86400

                        sessions[session_id].stories_per_second = (
                            sessions[session_id].num_stories
                            / sessions[session_id].duration
                        )
                        cur_session_id = None

                    continue


for _ in range(10):
    print()


story_types = [
    "active",
    "best",
    "classic",
    "new",
    "top",
]
rates = {}

for each in story_types:
    rates[each] = []

for each_session in sessions.values():
    rates[each_session.story_type].append(each_session.stories_per_second)


for each in rates.keys():
    rates[each] = np.array(rates[each])

    try:
        mean_duration = statistics.mean(rates[each])
    except statistics.StatisticsError:
        mean_duration = "No mean found"

    try:
        median_duration = statistics.median(rates[each])
    except statistics.StatisticsError:
        median_duration = "No median found"

    try:
        mode_duration = statistics.mode(rates[each])
    except statistics.StatisticsError:
        mode_duration = "No unique mode found"

    try:
        first_quartile = np.percentile(rates[each], 25)
    except Exception as exc:
        first_quartile = f"Error: {exc}"

    try:
        third_quartile = np.percentile(rates[each], 75)
    except Exception as exc:
        third_quartile = f"Error: {exc}"

    try:
        min_val = min(rates[each])
        max_val = max(rates[each])
    except Exception as exc:
        min_val = f"Error: {exc}"
        max_val = f"Error: {exc}"

    print(
        f"""
Story Type: {each}
Events: {len(rates[each])}
Min: {min_val}
Max: {max_val}
Mean: {mean_duration}
Median: {median_duration}
Mode: {mode_duration}
First Quartile: {first_quartile}
Third Quartile: {third_quartile}
    """
    )


for _ in range(10):
    print()


processing_types = [
    "freshened",
    "reused",
    "uncached_with_thumb",
    "uncached_without_thumb",
]
durations = {}

for each in processing_types:
    durations[each] = []


for e in events.values():

    if e.processing_duration >= 0:
        if e.uncached_story:
            if e.has_thumbnail:
                durations["uncached_with_thumb"].append(e.processing_duration)
            else:
                durations["uncached_without_thumb"].append(e.processing_duration)
        elif e.freshened_story:
            durations["freshened"].append(e.processing_duration)
        elif e.reused_story:
            durations["reused"].append(e.processing_duration)


for each in durations.keys():
    durations[each] = np.array(durations[each])

    try:
        mean_duration = statistics.mean(durations[each])
    except statistics.StatisticsError:
        mean_duration = "No mean found"

    try:
        median_duration = statistics.median(durations[each])
    except statistics.StatisticsError:
        median_duration = "No median found"

    try:
        mode_duration = statistics.mode(durations[each])
    except statistics.StatisticsError:
        mode_duration = "No unique mode found"

    try:
        first_quartile = np.percentile(durations[each], 25)
    except Exception as exc:
        first_quartile = f"Error: {exc}"

    try:
        third_quartile = np.percentile(durations[each], 75)
    except Exception as exc:
        third_quartile = f"Error: {exc}"

    try:
        min_val = min(durations[each])
        max_val = max(durations[each])
    except Exception as exc:
        min_val = f"Error: {exc}"
        max_val = f"Error: {exc}"

    print(
        f"""
Processing Category: {each}
Events: {len(durations[each])}
Min: {min_val}
Max: {max_val}
Mean: {mean_duration}
Median: {median_duration}
Mode: {mode_duration}
First Quartile: {first_quartile}
Third Quartile: {third_quartile}
"""
    )
