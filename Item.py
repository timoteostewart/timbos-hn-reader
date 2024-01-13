import datetime
from typing import List

import time_utils


class Item:
    id: int  # item ID (required attribute)
    # 'story' or 'comment' ('job', 'poll', and 'pollopt' not yet implemented)
    type: str
    # title: str
    text: str  # in HTML format
    # url: str
    by: str  # username of item's author
    time: int  # in Unix time format
    publication_time_ISO_8601: str
    seconds_ago: int  # diff between time.time() and self.time
    time_ago_display: str  # display formatted with various time units
    # score: int

    # parent: int  # item ID
    kids: List[int]  # item IDs
    # descendants: int  # comment count for stories (and polls)

    deleted: bool
    dead: bool

    poll: int  # item ID; not implemented
    parts: List[int]  # for polls; not implemented

    def __init__(
        self, id: str, type: str, text: str, by: str, ztime: str, kids: List[str]
    ) -> None:
        self.id: int = int(id)
        self.type: str = type
        self.text: str = text
        self.by: str = by

        self.time = int(ztime)
        self.publication_time_ISO_8601: str = datetime.datetime.utcfromtimestamp(
            self.time
        ).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )  # note: in ISO 8601 in UTC

        time_now = time_utils.get_time_now_in_epoch_seconds_int()
        seconds_ago = time_now - ztime
        self.time_ago_display = time_utils.convert_seconds_ago_to_human_readable(
            seconds_ago
        )

        self.kids: List[int]
        if kids:
            self.kids = kids
        else:
            self.kids = []
