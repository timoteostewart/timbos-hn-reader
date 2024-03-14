import datetime
from typing import List


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
    # score: int

    # parent: int  # item ID
    kids: List[int]  # item IDs
    # descendants: int  # comment count for stories (and polls)

    deleted: bool
    dead: bool

    poll: int  # item ID; not implemented
    parts: List[int]  # for polls; not implemented

    def __init__(
        self, id: str, type: str, text: str, by: str, time: str, kids: List[str]
    ) -> None:
        self.id: int = id
        self.type: str = type
        self.text: str = text
        self.by: str = by

        self.time = int(time)
        self.publication_time_ISO_8601: str = datetime.datetime.utcfromtimestamp(
            self.time
        ).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )  # note: in ISO 8601 in UTC

        self.kids: List[int]
        if kids:
            self.kids = kids
        else:
            self.kids = []
