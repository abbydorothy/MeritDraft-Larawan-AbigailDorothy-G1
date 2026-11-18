"""Word-level diff and point calculation for change submissions."""
import difflib
from decimal import Decimal

ADDITION = "addition"
REVISION = "revision"

# 1 point per word for additions, 0.5 point per word for revisions (per the project charter).
POINTS_PER_WORD = {ADDITION: Decimal("1"), REVISION: Decimal("0.5")}


def compare(old_text, new_text):
    """Compare two texts word by word.

    Returns {"segments": [(op, text), ...], "added": int, "removed": int}
    where op is "equal", "insert" or "delete". `added` counts the new words
    (inserted or replacing old words) - this is what earns points.
    """
    old, new = old_text.split(), new_text.split()
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    segments, added, removed = [], 0, 0
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            segments.append(("equal", " ".join(old[i1:i2])))
            continue
        if i2 > i1:
            segments.append(("delete", " ".join(old[i1:i2])))
            removed += i2 - i1
        if j2 > j1:
            segments.append(("insert", " ".join(new[j1:j2])))
            added += j2 - j1
    return {"segments": segments, "added": added, "removed": removed}


def calculate_points(tag, added_words):
    return POINTS_PER_WORD[tag] * added_words
