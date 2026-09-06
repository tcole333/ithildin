from __future__ import annotations

import argparse
import io
import json
from urllib.error import HTTPError

from tools.government_releases import connect
from tools.government_release_corpus import (
    parse_sec_archive_listing,
    parse_sec_modern_listing,
    source_ref,
    sec_index_record,
    upsert_release,
    get_bytes,
    parse_doj_archive_month,
    extract_doj_archive_body,
    begin_run,
    cmd_search,
    doj_api_params,
    doj_state_key,
    extract_sec_body,
)


def test_schema_and_versioned_upsert_are_idempotent(tmp_path):
    db = connect(tmp_path / "government.db")
    assert db.execute("PRAGMA busy_timeout").fetchone()[0] == 60000
    record = {
        "agency": "DOJ",
        "native_id": "uuid-1",
        "release_number": "26-1",
        "title": "Justice Department announces a case",
        "canonical_url": "https://www.justice.gov/opa/pr/example",
        "published_at": "2026-01-01",
        "content_text": "Primary government release text.",
    }
    release_id, changed = upsert_release(db, record)
    assert changed is True
    same_id, changed = upsert_release(db, record)
    assert same_id == release_id
    assert changed is False
    assert db.execute("SELECT COUNT(*) FROM government_release_version").fetchone()[0] == 1

    changed_record = dict(record, content_text="Corrected primary government release text.")
    _, changed = upsert_release(db, changed_record)
    assert changed is True
    assert db.execute("SELECT COUNT(*) FROM government_release_version").fetchone()[0] == 2
    assert db.execute("SELECT COUNT(*) FROM government_release_version WHERE version_status='current'").fetchone()[0] == 1
    fts = db.execute("SELECT rowid,release_id,title FROM government_release_fts").fetchone()
    assert fts["rowid"] == release_id
    assert fts["release_id"] == release_id
    assert fts["title"] == record["title"]
    assert db.execute("SELECT COUNT(*) FROM government_release_fts").fetchone()[0] == 1


def test_doj_source_ref_uses_uuid_to_avoid_release_number_collisions():
    assert source_ref("DOJ", "uuid-1", "26-1") == "DOJ-PR:uuid-1"
    assert source_ref("SEC", "2026-1", "2026-1") == "SEC-PR:2026-1"


def test_doj_backfill_uses_versioned_deterministic_cursor():
    assert doj_state_key() == "doj_next_page:created-asc-v1"
    assert doj_state_key("Jeffrey Epstein").endswith(":title:jeffrey-epstein")
    assert doj_api_params(12) == {
        "pagesize": 50,
        "page": 12,
        "sort": "created",
        "direction": "ASC",
    }


def test_parse_modern_sec_listing():
    page = """
    <tr class="pr-list-page-row">
      <td><time datetime="2026-07-10T12:00:32Z">July 10, 2026</time></td>
      <td><a href="/newsroom/press-releases/2026-66-example">SEC Example Headline</a></td>
      <td>2026-66</td>
    </tr>
    """
    rows = parse_sec_modern_listing(page)
    assert rows == [{
        "url": "https://www.sec.gov/newsroom/press-releases/2026-66-example",
        "title": "SEC Example Headline",
        "published_at": "2026-07-10T12:00:32Z",
        "release_number": "2026-66",
    }]
    normalized = sec_index_record(rows[0])
    assert normalized["canonical_url"].endswith("/2026-66-example")
    assert normalized["native_id"] == "2026-66"


def test_extract_sec_body_preserves_nested_joint_release_layout():
    page = '''
    <meta property="og:title" content="Agencies Extend Comment Period" />
    <div class="field field--name-body field__item"><p></p>
      <div class="colspan-12"><div class="colspan-4">Joint Release</div></div>
      <p>Five federal financial regulatory agencies extended the comment period.</p>
    </div><footer>Unrelated navigation</footer>
    '''
    body, title, _ = extract_sec_body(page)
    assert title == "Agencies Extend Comment Period"
    assert "Joint Release" in body
    assert "Five federal" in body
    assert "Unrelated navigation" not in body


def test_extract_sec_legacy_markers_ignore_early_chart_rule():
    page = '''<!-- BEGIN TEXT -->
      <h1>SEC Charges Executives</h1>
      <div class="chart"><a>Chart caption</a><hr></div>
      <p>The Commission today charged six former executives with securities fraud.</p>
      <p>The release continues with substantive allegations and procedural detail.</p>
      <!-- END TEXT --><div class="footer">Navigation</div>'''
    body, _, _ = extract_sec_body(page)
    assert "The Commission today charged" in body
    assert "procedural detail" in body
    assert "Navigation" not in body


def test_parse_legacy_sec_listing_ignores_template_row():
    page = """
    <tr><td><a href="/news/press/2011/2011-xx.htm">2011-xx</a></td>
        <td>Dec. xx, 2011</td><td>template</td></tr>
    <tr><td><a href="/news/press/2011/2011-279.htm">2011-279</a></td>
        <td>Dec. 29, 2011</td><td>SEC Charges Example Company</td></tr>
    """
    rows = parse_sec_archive_listing(page, 2011)
    assert len(rows) == 1
    assert rows[0]["release_number"] == "2011-279"
    assert rows[0]["published_at"] == "2011-12-29"
    assert rows[0]["title"] == "SEC Charges Example Company"


def test_parse_legacy_sec_listing_supports_all_historical_url_shapes():
    samples = [
        (1997, "/news/press/pressarchive/1997/97-109.txt", "97-109"),
        (2001, "/news/press/2001-146.txt", "2001-146"),
        (2004, "/news/press/2004-171.htm", "2004-171"),
        (2006, "/news/press/2006/2006-223.htm", "2006-223"),
    ]
    for year, href, number in samples:
        page = f'<tr><td><a href="{href}">{number}</a></td><td>Dec. 29, {year}</td><td>Release {number}</td></tr>'
        rows = parse_sec_archive_listing(page, year)
        assert len(rows) == 1, (year, href)
        assert rows[0]["release_number"] == number


def test_official_fetch_retries_transient_503(monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return b"ok"
    calls=[]
    def fake_open(req, timeout):
        calls.append(req.full_url)
        if len(calls)==1:
            raise HTTPError(req.full_url,503,"unavailable",{"Retry-After":"0"},io.BytesIO())
        return Response()
    monkeypatch.setattr("tools.government_release_corpus.urlopen",fake_open)
    monkeypatch.setattr("tools.government_release_corpus.time.sleep",lambda _:None)
    assert get_bytes("https://example.gov/release",retries=1)==b"ok"
    assert len(calls)==2


def test_search_treats_currency_punctuation_as_literal_terms(tmp_path):
    db_path = tmp_path / "government.db"
    db = connect(db_path)
    upsert_release(
        db,
        {
            "agency": "DOJ",
            "native_id": "currency-release",
            "title": "DaVita resolves $270 million Medicare Advantage matter",
            "canonical_url": "https://www.justice.gov/example",
            "published_at": "2026-01-01",
            "content_text": "The resolution totals $270 million.",
        },
    )
    db.commit()
    db.close()
    output = tmp_path / "search.json"

    cmd_search(
        argparse.Namespace(
            db=db_path,
            query="DaVita $270 million Medicare Advantage",
            agency="DOJ",
            limit=10,
            output=str(output),
            json_out=False,
        )
    )

    assert json.loads(output.read_text())[0]["source_ref"] == "DOJ-PR:currency-release"


def test_parse_doj_legacy_month_and_release():
    month = '<a href="/archive/opa/pr/2008/January/08_opa_001.html">Read more</a>'
    assert parse_doj_archive_month(month)[0]["url"] == \
        "https://www.justice.gov/archive/opa/pr/2008/January/08_opa_001.html"
    release = """<div>FOR IMMEDIATE RELEASE<br />WEDNESDAY, JANUARY 2, 2008<br /></div>
      <h1 class="prtitle">Statement on an Investigation</h1>
      <p>The Justice Department announced the investigation.</p><p>###</p>"""
    body,title,published = extract_doj_archive_body(release)
    assert title == "Statement on an Investigation"
    assert published == "2008-01-02"
    assert body == "The Justice Department announced the investigation."


def test_parse_doj_legacy_month_retains_searchable_title_and_teaser():
    month = """<h3>Case Headline <span class="small">(08-100)</span></h3>
      <p>Agency summary of the action. <a href="/archive/opa/pr/2008/January/08-crm-100.html">(Read more)</a></p>"""
    row=parse_doj_archive_month(month)[0]
    assert row["title"] == "Case Headline"
    assert row["release_number"] == "08-100"
    assert row["teaser"] == "Agency summary of the action."


def test_parse_doj_pre_1998_archive_links():
    samples=[
        ('/archive/opa/pr/Pre_96/January95/59.txt.html','#059 Justice Department Suit'),
        ('/archive/opa/pr/1996/January96/022.txt','#022 DOJ Sues New York'),
        ('/archive/opa/pr/1997/January97/045ag.htm','#045 AG Reno Visit'),
    ]
    for href,label in samples:
        rows=parse_doj_archive_month(f'<a href="{href}">{label}</a>')
        assert len(rows)==1,(href,rows)
        assert rows[0]["title"]==label
    relative=parse_doj_archive_month(
        '<a href="94387.txt.html">Microsoft Agreement</a>',
        'https://www.justice.gov/archive/opa/pr/Pre_96/July94/',
    )
    assert relative[0]["url"].endswith('/Pre_96/July94/94387.txt.html')


def test_begin_run_closes_stale_interrupted_run(tmp_path):
    db=connect(tmp_path/"gov.db")
    stale=begin_run(db,"DOJ","api",{})
    current=begin_run(db,"DOJ","api",{})
    old=db.execute("SELECT * FROM ingest_run WHERE id=?",(stale,)).fetchone()
    new=db.execute("SELECT * FROM ingest_run WHERE id=?",(current,)).fetchone()
    assert old["completed_at"] is not None
    assert "interrupted" in old["error"]
    assert new["completed_at"] is None
