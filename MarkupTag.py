from typing import Dict, List


class MarkupTag:
    tag_name: str = None
    tag_literal: str = None
    start_index: int = None
    attribs: Dict = None
    empty_attribs: List = None

    def __init__(
        self, tag_name: str, tag_as_string: str, start_index: int, attribs: Dict = None
    ):
        self.tag_name = tag_name
        self.tag_literal = tag_as_string
        self.start_index = start_index
        self.attribs = {}
        self.empty_attribs = []

        if attribs:
            self.attribs.update(attribs)

    def __str__(self):
        return self.tag_literal

    def dump(self):
        print(f"\t{self.tag_name}")
        # print(f"\t\torig={self.tag_literal}")
        print(f"\t\tstart_index={self.start_index}")

        print("\t\tattribs:", end="")
        if self.attribs:
            print()
            for k, v in self.attribs.items():
                print(f'\t\t\t{k}="{v}"')
        else:
            print(" None")

        print("\t\tempty attribs:", end="")
        if self.empty_attribs:
            print()
            for each in self.empty_attribs:
                print(f"\t\t\t{each}")
        else:
            print(" None")
