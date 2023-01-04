import logging
import math

import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_frac(number, precision):

    fractions_halves = {
        0.0: "",
        0.5: "½",
    }

    fractions_fourths = {0.0: "", 0.25: "¼", 0.5: "½", 0.75: "¾"}

    fractions_to_use = None
    if precision == "halves":
        fractions_to_use = fractions_halves
    elif precision == "fourths":
        fractions_to_use = fractions_fourths
    else:
        fractions_to_use = fractions_halves

    whole_part = int(number)
    frac_part = number - whole_part
    min_diff = 1
    best_fraction = 0
    for each_fraction in fractions_to_use.keys():
        cur_diff = abs(frac_part - each_fraction)
        if cur_diff < min_diff:
            min_diff = cur_diff
            best_fraction = each_fraction

    return f"{whole_part}{fractions_to_use[best_fraction]}"


def add_singular_plural(number, unit, force_int=False):
    if force_int:
        if number == 0 or number == 0.0:
            return f"zero {unit}s"
        elif number == 1 or number == 1.0:
            return f"1 {unit}"
        else:
            return f"{int(math.ceil(number))} {unit}s"

    if number == 0 or number == 0.0:
        return f"0 {unit}s"
    elif number == 1 or number == 1.0:
        return f"1 {unit}"
    else:
        x = ""
        if unit in ["hour"]:
            x = f"{get_frac(number, 'fourths')} {unit}s"
        elif unit in ["day", "week", "month", "year"]:
            x = f"{get_frac(number, 'halves')} {unit}s"
        else:
            x = f"{int(math.ceil(number))} {unit}s"
        if x[:2] == "1 ":
            return x[:-1]
        else:
            return x


def get_text_between(
    left_pattern: str,
    right_pattern: str,
    text: str,
    okay_to_elide_right_pattern=False,
    force_lowercase=False,
):

    left_index = text.find(left_pattern)
    if left_index == -1:
        return None

    right_index = text.find(
        right_pattern, left_index + len(left_pattern)
    )  # note: lazy find
    if right_index == -1:
        if okay_to_elide_right_pattern:
            return text[slice(left_index + len(left_pattern), len(text))]
        else:
            return None

    # check for zero-length string between left_pattern and right_pattern
    if left_index + len(left_pattern) == right_index:
        return config.EMPTY_STRING

    result = text[slice(left_index + len(left_pattern), right_index)]

    if not result:
        return None

    if force_lowercase:
        return result.lower()
    else:
        return result


def insert_possible_line_breaks(orig_title):

    title_slug = ""

    words_by_spaces = orig_title.split(" ")

    # we will break each "word" down further, if possible or necessary
    break_after_these = "/-"
    break_before_these = "\\"

    LINE_BREAK_HYPHEN = "⸗"

    for i in range(len(words_by_spaces)):

        intraword_tokens = []

        cur_word = ""
        for char in words_by_spaces[i]:

            if char in break_after_these:
                intraword_tokens.append(cur_word)
                cur_word = char
                cur_word += "&ZeroWidthSpace;"
                intraword_tokens.append(cur_word)
                cur_word = ""
            elif char in break_before_these:
                intraword_tokens.append(cur_word)
                cur_word = "&ZeroWidthSpace;"
                cur_word += char
                intraword_tokens.append(cur_word)
                cur_word = ""
            else:
                cur_word += char
        if cur_word:
            intraword_tokens.append(cur_word)

        for j in range(len(intraword_tokens)):
            if "&ZeroWidthSpace;" in intraword_tokens[j]:
                continue
            # check if hyphenation is needed

            MAX_ALLOWED_WORD_LENGTH = config.settings["SLUGS"]["MAX_SUBSTRING_LENGTH"]

            if len(intraword_tokens[j]) > MAX_ALLOWED_WORD_LENGTH:
                t = intraword_tokens[j]
                t_conv = []
                while len(t) >= MAX_ALLOWED_WORD_LENGTH:
                    if len(t) <= 1.5 * MAX_ALLOWED_WORD_LENGTH:
                        len_to_use = len(t) // 2
                        t_conv.append(t[slice(len_to_use)])
                        t_conv.append(f"{LINE_BREAK_HYPHEN}&ZeroWidthSpace;")
                        t_conv.append(t[slice(len_to_use, len(t))])
                        # t_conv.append("-&ZeroWidthSpace;")
                        t = ""
                    elif len(t) <= 2 * MAX_ALLOWED_WORD_LENGTH:
                        len_to_use = len(t) // 3
                        twice_len_to_use = int(2 * len_to_use)
                        t_conv.append(t[slice(len_to_use)])
                        t_conv.append(f"{LINE_BREAK_HYPHEN}&ZeroWidthSpace;")
                        t_conv.append(t[slice(len_to_use, twice_len_to_use)])
                        t_conv.append(f"{LINE_BREAK_HYPHEN}&ZeroWidthSpace;")
                        t_conv.append(t[slice(twice_len_to_use, len(t))])
                        # t_conv.append("-&ZeroWidthSpace;")
                        t = ""
                    else:
                        t_conv.append(t[:MAX_ALLOWED_WORD_LENGTH])
                        t_conv.append(f"{LINE_BREAK_HYPHEN}&ZeroWidthSpace;")
                        t = t[24:]
                intraword_tokens[j] = "".join(t_conv)
        words_by_spaces[i] = "".join(intraword_tokens)

    title_slug = " ".join(words_by_spaces)

    return title_slug


def word_count(text):
    return len(text.split(" "))
