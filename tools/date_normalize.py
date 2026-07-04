#!/usr/bin/env python3
"""Shared partial-date normalizer for the investigation platform.

The core problem this solves: `findings.date_of_event` is free text. SQLite's
date() parses a bare year like '2015' as a Julian day number (-> year -4707),
so bare-year and year-month findings silently vanish from BETWEEN/date() range
queries in event_timeline. This module converts any supported string into an
explicit (iso_date, precision) pair plus the inclusive [start, end] interval the
value really denotes, so a year-precision date matches its whole year.

Contract:
    normalize_date("2015")         -> ("2015-01-01", "year")
    normalize_date("2015-10")      -> ("2015-10-01", "month")
    normalize_date("2015-10-14")   -> ("2015-10-14", "day")
    normalize_date("garbage")      -> (None, "unknown")

    date_interval("2015", "year")  -> ("2015-01-01", "2015-12-31")

Deterministic and dependency-free (no dateutil). Prose dates are handled for a
few common, unambiguous shapes only; anything uncertain returns unknown rather
than guessing — the platform norm is reject-don't-guess for dates.
"""

import calendar
import re
from datetime import date

# Plausible corpus span; values outside this are almost always OCR/paste noise
# (e.g. "1/1/4501") and are rejected rather than coerced.
MIN_YEAR = 1900
MAX_YEAR = 2030

PRECISION_DAY = "day"
PRECISION_MONTH = "month"
PRECISION_YEAR = "year"
PRECISION_UNKNOWN = "unknown"

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

_ISO_DAY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_ISO_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
_YEAR = re.compile(r"^(\d{4})$")
# US-style M/D/Y or M/D/YY (also handles single-digit month/day)
_US_SLASH = re.compile(r"^(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})$")
# "September 30, 2017" / "Sept 30 2017" / "30 September 2017"
_PROSE_MDY = re.compile(r"^([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})$")
_PROSE_DMY = re.compile(r"^(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})$")
# "September 2017" (month + year, no day)
_PROSE_MY = re.compile(r"^([A-Za-z]{3,9})\.?\s+(\d{4})$")


def _valid_ymd(y, m, d):
    if not (MIN_YEAR <= y <= MAX_YEAR):
        return False
    if not (1 <= m <= 12):
        return False
    return 1 <= d <= calendar.monthrange(y, m)[1]


def _expand_two_digit_year(yy):
    """Century pivot: 30..99 -> 19xx, 00..29 -> 20xx (corpus is 1985-2024)."""
    return 1900 + yy if yy >= 30 else 2000 + yy


def normalize_date(raw):
    """Return (iso_date_or_None, precision). Never raises."""
    if raw is None:
        return (None, PRECISION_UNKNOWN)
    s = str(raw).strip()
    if not s:
        return (None, PRECISION_UNKNOWN)

    # Intra-day prose ranges ("December 24-26, 2013") -> anchor on the first day.
    s = re.sub(r"(\d{1,2})\s*[-–—]\s*\d{1,2}(\s*,?\s+\d{4})", r"\1\2", s)
    # Full-token ranges ("2/1/13 to 2/28/13") -> anchor on the start token.
    for sep in (" to ", " through ", " – ", " — ", " -- "):
        if sep in s:
            s = s.split(sep, 1)[0].strip()
            break

    m = _ISO_DAY.match(s)
    if m:
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
        return (f"{y:04d}-{mo:02d}-{d:02d}", PRECISION_DAY) if _valid_ymd(y, mo, d) else (None, PRECISION_UNKNOWN)

    m = _ISO_MONTH.match(s)
    if m:
        y, mo = int(m[1]), int(m[2])
        if MIN_YEAR <= y <= MAX_YEAR and 1 <= mo <= 12:
            return (f"{y:04d}-{mo:02d}-01", PRECISION_MONTH)
        return (None, PRECISION_UNKNOWN)

    m = _YEAR.match(s)
    if m:
        y = int(m[1])
        return (f"{y:04d}-01-01", PRECISION_YEAR) if MIN_YEAR <= y <= MAX_YEAR else (None, PRECISION_UNKNOWN)

    # Year range ("1997-1998") -> anchor on the first year, year precision.
    m = re.match(r"^(\d{4})\s*[-–—]\s*\d{4}$", s)
    if m:
        y = int(m[1])
        return (f"{y:04d}-01-01", PRECISION_YEAR) if MIN_YEAR <= y <= MAX_YEAR else (None, PRECISION_UNKNOWN)

    m = _US_SLASH.match(s)
    if m:
        mo, d, yr = int(m[1]), int(m[2]), int(m[3])
        y = _expand_two_digit_year(yr) if yr < 100 else yr
        return (f"{y:04d}-{mo:02d}-{d:02d}", PRECISION_DAY) if _valid_ymd(y, mo, d) else (None, PRECISION_UNKNOWN)

    m = _PROSE_MDY.match(s)
    if m and m[1].lower() in _MONTHS:
        y, mo, d = int(m[3]), _MONTHS[m[1].lower()], int(m[2])
        return (f"{y:04d}-{mo:02d}-{d:02d}", PRECISION_DAY) if _valid_ymd(y, mo, d) else (None, PRECISION_UNKNOWN)

    m = _PROSE_DMY.match(s)
    if m and m[2].lower() in _MONTHS:
        y, mo, d = int(m[3]), _MONTHS[m[2].lower()], int(m[1])
        return (f"{y:04d}-{mo:02d}-{d:02d}", PRECISION_DAY) if _valid_ymd(y, mo, d) else (None, PRECISION_UNKNOWN)

    m = _PROSE_MY.match(s)
    if m and m[1].lower() in _MONTHS:
        y, mo = int(m[2]), _MONTHS[m[1].lower()]
        if MIN_YEAR <= y <= MAX_YEAR:
            return (f"{y:04d}-{mo:02d}-01", PRECISION_MONTH)

    return (None, PRECISION_UNKNOWN)


def date_interval(iso_date, precision):
    """Inclusive [start, end] ISO interval a normalized date denotes.

    A year-precision date spans its whole year; a month its whole month; a day
    is a point. Returns (None, None) for unknown/None input.
    """
    if not iso_date:
        return (None, None)
    y, mo, d = int(iso_date[0:4]), int(iso_date[5:7]), int(iso_date[8:10])
    if precision == PRECISION_YEAR:
        return (f"{y:04d}-01-01", f"{y:04d}-12-31")
    if precision == PRECISION_MONTH:
        last = calendar.monthrange(y, mo)[1]
        return (f"{y:04d}-{mo:02d}-01", f"{y:04d}-{mo:02d}-{last:02d}")
    return (iso_date, iso_date)


def to_epoch_day(iso_date):
    """Integer days since 1970-01-01 (for the sidecar's interval index)."""
    if not iso_date:
        return None
    y, mo, d = int(iso_date[0:4]), int(iso_date[5:7]), int(iso_date[8:10])
    return (date(y, mo, d) - date(1970, 1, 1)).days


if __name__ == "__main__":
    import sys
    for arg in sys.argv[1:]:
        iso, prec = normalize_date(arg)
        lo, hi = date_interval(iso, prec)
        print(f"{arg!r:30} -> {iso} [{prec}]  interval [{lo}, {hi}]")
