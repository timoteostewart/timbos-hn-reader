import sys

if __name__ == "__main__":

    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print(
            'Usage: find-unfinished-stories.py <log-file> ["list of specific story ids"]'
        )
        exit()

    # if len(sys.argv) == 2:
    #     exit()

    # if len(sys.argv) == 3:
    #     exit()

    log_file = sys.argv[1]

    with open(log_file, mode="r", encoding="utf-8") as f:
        log_lines = f.readlines()

    unfinished_ids = set()

    for line in log_lines:
        # 2024-03-09T01:34:27.911Z [new]     INFO     id 39646062: ppp(afcfe55a21db): cached story found (last updated from firebaseio.com 89 minutes ago)
        if line[44:47] == "id ":
            candidate_id = line[47:55]
            try:
                id = int(candidate_id)
            except Exception:
                continue
            if "no cached story found" in line:
                unfinished_ids.add(id)
            elif "cached story found" in line:
                unfinished_ids.add(id)
            elif "successfully created story_card_html" in line:
                unfinished_ids.discard(id)
            elif "discarding this story" in line:
                unfinished_ids.discard(id)

    print(f"unfinished_ids = {unfinished_ids}")
