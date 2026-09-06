from __future__ import annotations

import pytest

from tools import query_ny_law_reports as nylr


pytestmark = pytest.mark.live_data


def test_official_ny_law_reports_live_sentinel():
    payload = nylr.run_sentinel()
    challenged = [
        check for check in payload["checks"] if check["status"] == "access_challenge"
    ]
    if challenged:
        pytest.skip(
            "official nycourts.gov host returned its browser/security challenge: "
            + ", ".join(check["name"] for check in challenged)
        )

    assert payload["status"] == "ok", payload
    assert all(check["status"] == "ok" for check in payload["checks"])
    assert payload["exact_urls"]["other_rss"] == (
        "https://www.nycourts.gov/reporter/RSS/misc.xml"
    )
    assert payload["exact_urls"]["commercial_rss"] == (
        "https://www.nycourts.gov/reporter/RSS/ComDiv.xml"
    )
    assert payload["exact_urls"]["other_current_index"] == (
        "https://www.nycourts.gov/reporter/current/index/miscolo.shtml"
    )
    assert payload["exact_urls"]["commercial_current_index"] == (
        "https://www.nycourts.gov/reporter/current/index/"
        "com_div_idxtable.shtml"
    )
    assert payload["exact_urls"]["other_archive_index"] == (
        "https://www.nycourts.gov/reporter/current/index/"
        "other-courts-archive.shtml"
    )
    assert payload["exact_urls"]["commercial_archive_index"] == (
        "https://www.nycourts.gov/reporter/current/index/"
        "com-div-decisions-archive.shtml"
    )
    assert payload["exact_urls"]["opinion"] == (
        "https://www.nycourts.gov/reporter/current/3dseries/2026/"
        "2026_26113.shtml"
    )
