from Trie import Trie

hrequests_exceptions_suffixes = [
    "context deadline exceeded (Client.Timeout exceeded while awaiting headers)",
    "http2: unsupported scheme",
    "i/o timeout (Client.Timeout exceeded while awaiting headers)",
    "no such host",
    "remote error: tls: user canceled",
    "stream error: stream ID 1; INTERNAL_ERROR",
    "unexpected EOF",
    "x509: certificate signed by unknown authority",
]

hrequests_exceptions_suffixes_trie = Trie(suffix_search=True)
for _ in hrequests_exceptions_suffixes:
    hrequests_exceptions_suffixes_trie.add_member(_)

exc_msgs = [
    "foo bar baz: context deadline exceeded (Client.Timeout exceeded while awaiting headers)",
    "foo bar baz: i/o timeout (Client.Timeout exceeded while awaiting headers)",
]

for _ in exc_msgs:
    print(hrequests_exceptions_suffixes_trie.search(_))
