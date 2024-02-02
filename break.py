def process(input):
    output = None

    x = input  # a working copy

    while True:
        # if blocks need to be logically ordered

        if x == "text/plain":
            pass
            # test x for actual content type
            # if it's actually text/plain, then break.
            # if it's actually text/html, then change x to "text/html" and fall through.

        if x == "application/json":
            pass
            # test x for actual content type
            # if it's actually application/json, then break.
            # if it's actually text/html, then change x to "text/html" and fall through.

        if x == "application/xhtml":
            pass
            # test x for actual content type
            # if it's actually application/xhtml, then break.
            # if it's actually text/html, then change input to "text/html" and fall through.

        if x == "text/html":
            pass
            # test x for actual content type
            # if it's actually text/html, then break.
            # if it's actually text/plain, then change x to "text/plain" and continue
            # if it can't be identified, change input to "" and fall through.

        if x == "grapes":
            x = "round fruit"
            # fall through and be processed by a future block

        if x == "orange":
            x = "round fruit"
            # fall through and be processed by a future block

        if x == "long fruit":
            output = "long fruit"
            break

        if x == "quince":
            output = "quince"
            break  # we say no fall through in this case

        if x == "round fruit":
            output = "round fruit"
            break

        if x == "unknown":
            output = "unknown"
            break

        print(f"Fell through all cases due to unexpected input. {input=}")
        output = "unknown"

        break

    return output


# for samples in [

#     ("application/json", "text/html"),
#     ("application/json", "text/html"),
#     ("application/xhtml", "text/html"),
#     ("text/plain", "text/plain"),

#     (),
#     (),
#     (),

#     "apple",
#     "avocado",
#     "banana",
#     "long fruit",
#     "orange",
#     "round fruit",
# ]:
# print(f"input={content_type}, output={process(content_type)}")
