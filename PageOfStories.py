from dataclasses import dataclass
from typing import Dict, List


@dataclass
class PageOfStories:
    story_type: str
    page_number: int
    story_ids: List[int]
    rosters: Dict
    is_first_page: bool
    is_last_page: bool
