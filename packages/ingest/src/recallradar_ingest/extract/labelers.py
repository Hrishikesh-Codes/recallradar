"""Company names on FDA product labels: "Distributed by: EzriCare, LLC, Lakewood, NJ".

openFDA gives a brand only for some drugs; for everything else, the distributor or "manufactured
for" company printed on the label is usually the name a consumer knows (store brands, private
labels). The recalling firm is often a contract manufacturer the consumer never sees.
"""

import re

_PHRASE = re.compile(
    r"\b(?:distributed|dist\.?|manufactured|mfd\.?|mfg\.?|marketed|packed|packaged|made|"
    r"produced|bottled|imported)\s+(?:exclusively\s+)?(?:by|for)\b\s*[:.\-]?\s*",
    re.I,
)
# The name ends at the first comma, semicolon, parenthesis, sentence break, or address digits.
# "Mrs. Gerry's" is not a sentence break.
_END = re.compile(r"\s*(?:[,;(]|(?<!\bMrs)(?<!\bMr)(?<!\bMs)(?<!\bDr)(?<!\bSt)\.\s|\s\d|$)")
_SUFFIX = re.compile(
    r"\s+(?:inc|llc|l\.l\.c|ltd|limited|corp|corporation|co|company|lp|plc|pvt|usa)\.?$", re.I
)
_MAX_WORDS = 5


def labelers(text: str) -> list[str]:
    """Companies named after "Distributed by", "Manufactured for", ... in order, deduplicated."""
    found: list[str] = []
    for phrase in _PHRASE.finditer(text):
        rest = text[phrase.end() :]
        end = _END.search(rest)
        name = rest[: end.start() if end else len(rest)].strip(" .:")
        while (trimmed := _SUFFIX.sub("", name)) != name:
            name = trimmed
        words = name.split()
        if not words or len(words) > _MAX_WORDS or not re.match(r"[A-Za-z0-9]", name):
            continue
        if name.lower() not in {n.lower() for n in found}:
            found.append(name)
    return found
