"""Conservative, country-scoped club identity reconciliation.

OpenFootball fixture files sometimes call the same team "Aston Villa" and
"Aston Villa FC" in adjacent seasons. Stable IDs must not fragment a career
when source spelling changes or a club switches divisions.

Only join within one country. Never merge an athlete with a team, or two
clubs from different countries. Explicitly listed aliases are reviewed.
"""
from __future__ import annotations
import re
import unicodedata


def slug(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    without_accents = "".join(c for c in normalized if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", without_accents.casefold()).strip("-")


# Alternative *club spellings*, not fuzzy matching between similar names.
# The country code prevents merging identically named teams internationally.
ALIASES = {
    ("en", "manchester-united-fc"): "manchester-united",
    ("en", "manchester-city-fc"): "manchester-city",
    ("en", "aston-villa-fc"): "aston-villa",
    ("en", "newcastle-united-fc"): "newcastle-united",
    ("en", "tottenham-hotspur-fc"): "tottenham-hotspur",
    ("en", "arsenal-fc"): "arsenal",
    ("en", "chelsea-fc"): "chelsea",
    ("en", "liverpool-fc"): "liverpool",
    ("en", "everton-fc"): "everton",
    ("en", "west-ham-united-fc"): "west-ham-united",
    ("en", "leicester-city-fc"): "leicester-city",
    ("en", "leeds-united-fc"): "leeds-united",
    ("en", "brighton-hove-albion-fc"): "brighton-hove-albion",
    ("en", "nottingham-forest-fc"): "nottingham-forest",
    ("en", "fulham-fc"): "fulham",
    ("en", "brentford-fc"): "brentford",
    ("en", "crystal-palace-fc"): "crystal-palace",
    ("en", "sunderland-afc"): "sunderland",
    ("en", "afc-bournemouth"): "bournemouth",
    ("en", "bournemouth-afc"): "bournemouth",
    ("es", "fc-barcelona"): "barcelona",
    ("es", "barcelona-fc"): "barcelona",
    ("es", "real-madrid-cf"): "real-madrid",
    ("es", "club-atletico-de-madrid"): "atletico-madrid",
    ("es", "atletico-de-madrid"): "atletico-madrid",
    ("it", "fc-internazionale-milano"): "internazionale",
    ("it", "inter-milan"): "internazionale",
    ("it", "inter"): "internazionale",
    ("it", "ac-milan"): "milan",
    ("de", "fc-bayern-munchen"): "bayern-munchen",
    ("de", "bayern-munich"): "bayern-munchen",
    ("de", "borussia-dortmund"): "borussia-dortmund",
}


def club_id(name: str, competition_code: str) -> str:
    """Return a stable ID for a real *team*, never an individual player."""
    code = str(competition_code).split(".", 1)[0].casefold()
    if not re.fullmatch(r"[a-z]{2}", code):
        raise ValueError("Football competition must include a valid country code")
    key = slug(name)
    if not key:
        raise ValueError("Club name is missing")
    # Strip unambiguous legal/club suffixes for broad season-to-season
    # consistency; do not strip initial FC or terms such as 'United'.
    # Rare collisions are handled by explicit alias exceptions.
    key = ALIASES.get((code, key), key)
    if key.endswith("-fc") and key not in {"fc"}:
        key = key[:-3]
    if key.endswith("-afc") and key not in {"afc"}:
        key = key[:-4]
    key = ALIASES.get((code, key), key)
    return f"openfootball:club:{code}:{key}"


def is_club_identity(value: str) -> bool:
    return str(value).startswith("openfootball:club:")
