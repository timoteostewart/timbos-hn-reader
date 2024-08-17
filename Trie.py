class Trie:
    class TrieNode:
        def __init__(self):
            self.children = {}
            self.is_end_of_word = False
            self.word = None

    def __init__(
        self,
        prefix_search: bool = False,
        suffix_search: bool = False,
    ):
        if not isinstance(prefix_search, bool) or not isinstance(suffix_search, bool):
            raise TypeError(
                "prefix_search and suffix_search parameters must be boolean values"
            )
        if prefix_search and suffix_search:
            raise ValueError(
                "prefix_search and suffix_search parameters cannot both be True"
            )

        self.root = Trie.TrieNode()
        self.prefix_search = prefix_search
        self.suffix_search = suffix_search

        if self.suffix_search:
            self.step = -1
        else:
            self.step = 1

    def add_member(self, query_term: str):
        if not query_term.strip():
            raise ValueError("query_term parameter must be a non-empty string")

        node = self.root

        for char in query_term[:: self.step]:
            if char not in node.children:
                node.children[char] = Trie.TrieNode()
            node = node.children[char]
        node.is_end_of_word = True
        node.word = query_term

    def show_contents(self):
        def _show_contents(node, prefix):
            if node.is_end_of_word:
                print(prefix)
            for char in node.children:
                _show_contents(node.children[char], prefix + char)

        _show_contents(self.root, "")

    def search(self, query: str):
        node = self.root

        for cur_char in query[:: self.step]:
            if cur_char not in node.children:
                if node.is_end_of_word:
                    return node.word
                elif not node.children and (self.prefix_search or self.suffix_search):
                    return node.word
                else:
                    return None
            else:
                node = node.children[cur_char]

        return node.word
