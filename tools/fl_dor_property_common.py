"""Shared Florida DOR county identity helpers.

Florida DOR assessment files use publisher county numbers 11 through 77.
Those values are not Census county FIPS codes, so every projection resolves
the publisher number through this explicit crosswalk.
"""

from __future__ import annotations

import re
from typing import Final


COUNTY_BY_DOR_NUMBER: Final[dict[int, tuple[str, str]]] = {
    11: ("Alachua", "12001"),
    12: ("Baker", "12003"),
    13: ("Bay", "12005"),
    14: ("Bradford", "12007"),
    15: ("Brevard", "12009"),
    16: ("Broward", "12011"),
    17: ("Calhoun", "12013"),
    18: ("Charlotte", "12015"),
    19: ("Citrus", "12017"),
    20: ("Clay", "12019"),
    21: ("Collier", "12021"),
    22: ("Columbia", "12023"),
    23: ("Dade", "12086"),
    24: ("DeSoto", "12027"),
    25: ("Dixie", "12029"),
    26: ("Duval", "12031"),
    27: ("Escambia", "12033"),
    28: ("Flagler", "12035"),
    29: ("Franklin", "12037"),
    30: ("Gadsden", "12039"),
    31: ("Gilchrist", "12041"),
    32: ("Glades", "12043"),
    33: ("Gulf", "12045"),
    34: ("Hamilton", "12047"),
    35: ("Hardee", "12049"),
    36: ("Hendry", "12051"),
    37: ("Hernando", "12053"),
    38: ("Highlands", "12055"),
    39: ("Hillsborough", "12057"),
    40: ("Holmes", "12059"),
    41: ("Indian River", "12061"),
    42: ("Jackson", "12063"),
    43: ("Jefferson", "12065"),
    44: ("Lafayette", "12067"),
    45: ("Lake", "12069"),
    46: ("Lee", "12071"),
    47: ("Leon", "12073"),
    48: ("Levy", "12075"),
    49: ("Liberty", "12077"),
    50: ("Madison", "12079"),
    51: ("Manatee", "12081"),
    52: ("Marion", "12083"),
    53: ("Martin", "12085"),
    54: ("Monroe", "12087"),
    55: ("Nassau", "12089"),
    56: ("Okaloosa", "12091"),
    57: ("Okeechobee", "12093"),
    58: ("Orange", "12095"),
    59: ("Osceola", "12097"),
    60: ("Palm Beach", "12099"),
    61: ("Pasco", "12101"),
    62: ("Pinellas", "12103"),
    63: ("Polk", "12105"),
    64: ("Putnam", "12107"),
    65: ("Saint Johns", "12109"),
    66: ("Saint Lucie", "12111"),
    67: ("Santa Rosa", "12113"),
    68: ("Sarasota", "12115"),
    69: ("Seminole", "12117"),
    70: ("Sumter", "12119"),
    71: ("Suwannee", "12121"),
    72: ("Taylor", "12123"),
    73: ("Union", "12125"),
    74: ("Volusia", "12127"),
    75: ("Wakulla", "12129"),
    76: ("Walton", "12131"),
    77: ("Washington", "12133"),
}


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


DOR_NUMBER_BY_COUNTY_KEY: Final[dict[str, int]] = {
    _key(name): number
    for number, (name, _geoid) in COUNTY_BY_DOR_NUMBER.items()
}
DOR_NUMBER_BY_COUNTY_KEY.update(
    {
        "miamidade": 23,
        "stjohns": 65,
        "stlucie": 66,
    }
)
DOR_NUMBER_BY_GEOID: Final[dict[str, int]] = {
    geoid: number
    for number, (_name, geoid) in COUNTY_BY_DOR_NUMBER.items()
}


def resolve_county(value: str | int) -> tuple[int, str, str]:
    """Resolve a DOR number, county GEOID/FIPS suffix, or county name."""

    raw = str(value).strip()
    if not raw:
        raise ValueError("Florida county selector must not be blank")
    if raw in DOR_NUMBER_BY_GEOID:
        number = DOR_NUMBER_BY_GEOID[raw]
    elif raw.isdigit() and len(raw) == 3 and f"12{raw}" in DOR_NUMBER_BY_GEOID:
        number = DOR_NUMBER_BY_GEOID[f"12{raw}"]
    elif raw.isdigit() and int(raw) in COUNTY_BY_DOR_NUMBER:
        number = int(raw)
    else:
        try:
            number = DOR_NUMBER_BY_COUNTY_KEY[_key(raw)]
        except KeyError as error:
            raise ValueError(f"unknown Florida county selector: {value!r}") from error
    name, geoid = COUNTY_BY_DOR_NUMBER[number]
    return number, name, geoid
