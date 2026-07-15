from __future__ import annotations

import argparse
import io
import json
import sqlite3
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest

from tools.epstein_reporting import (
    connect, normalize_country, normalize_language, normalize_published_at, normalize_url,
    publication_date_from_url,
)
from tools.reporting_corpus import (
    _fetch_candidate,
    _records_from_ris,
    cmd_verify_claim,
    cmd_promote,
    cmd_link_release,
    ingest_record,
    fetch_json_with_429_retry,
    infer_item_type,
    parse_article_html,
    parse_wayback_cdx,
    parse_commoncrawl_index,
    extract_warc_http_payload,
    _archive_ingest_record,
    validate_archived_html,
    archive_url_variants,
    commoncrawl_capture,
    _fetch_bytes,
    wayback_domain_urls,
    cmd_discover_file,
    cmd_discover_page,
    cmd_import_file,
    cmd_materialize_candidates,
    cmd_cleanup_navigation,
    cmd_cleanup_canonical_aliases,
    cmd_audit_relevance,
    cmd_ingest_candidates,
    cmd_search,
    align_candidate_canonical,
    candidate_url_variants,
    extract_page_links,
    is_navigation_link,
    is_access_interstitial,
    is_topic_landing_page,
    contains_core_subject,
    is_direct_reporting,
    candidate_display_title,
    normalize_source_type,
    reconcile_candidate_statuses,
)


def test_normalize_url_drops_tracking_and_fragment():
    assert normalize_url(
        "http://www.Example.com/story/?utm_source=x&b=2&a=1#section"
    ) == "https://example.com/story?a=1&b=2"


def test_topic_landing_pages_are_not_articles():
    assert is_topic_landing_page("https://lemonde.fr/affaire-epstein")
    assert is_topic_landing_page("https://elpais.com/noticias/jeffrey-edward-epstein")
    assert is_topic_landing_page(
        "https://projects.propublica.org/nonprofits/organizations/134028567"
    )
    assert is_topic_landing_page(
        "https://theguardian.com/us-news/ghislaine-maxwell",
        "Ghislaine Maxwell | The Guardian",
    )
    assert is_topic_landing_page(
        "https://wyborcza.pl/0,128956.html?tag=Jeffrey+Epstein"
    )
    assert is_topic_landing_page("https://telex.hu/cimke/epstein-aktak?oldal=8")
    assert is_topic_landing_page("https://digi24.ro/eticheta/dosarele-epstein")
    assert is_topic_landing_page("https://corriere.it/argomenti/epstein/2/")
    assert is_topic_landing_page("https://g1.globo.com/assunto/jeffrey-epstein/")
    assert is_topic_landing_page("https://kommersant.ru/theme/4294?from=tag")
    assert is_topic_landing_page("https://apnews.com/hub/jeffrey-epstein")
    assert is_topic_landing_page(
        "https://aftonbladet.se/nyheter/a/Rr77qd/aftonbladet-direkt?pinnedEntry=1460935"
    )
    assert is_topic_landing_page("https://tv.nu/program/epstein-filene-avsloringene")
    assert not is_topic_landing_page(
        "https://theguardian.com/us-news/2020/jul/31/ghislaine-maxwell-story"
    )


def test_consent_interstitial_is_not_an_article_response():
    assert is_access_interstitial(
        "https://myprivacy.dpgmedia.nl/consent?callbackUrl=https%3A%2F%2Fwww.nu.nl%2Fstory"
    )
    assert not is_access_interstitial("https://www.nu.nl/buitenland/5962746/story.html")


def test_source_type_aliases_fit_reporting_schema():
    assert normalize_source_type("document_publisher") == "secondary_quality"
    assert normalize_source_type("magazine") == "secondary_quality"
    assert normalize_source_type("aggregator") == "unknown"
    assert normalize_source_type("wire_service") == "wire_service"


def test_normalize_language_collapses_names_and_locale_variants():
    assert normalize_language("English") == "en"
    assert normalize_language("en-US") == "en"
    assert normalize_language("pt_BR") == "pt"
    assert normalize_language("Turkish") == "tr"
    assert normalize_language("kr") == "ko"
    assert normalize_language("unknown") is None


@pytest.mark.parametrize("name", [
    "Jeffrey Epstein", "Ghislaine Maxwell", "Джеффри Эпштейн", "ג׳פרי אפשטיין",
    "جيفري إبستين", "ジェフリー・エプスタイン", "제프리 엡스타인", "杰弗里·爱泼斯坦",
    "Τζέφρι Έπσταϊν", "Γκισλέιν Μάξγουελ",
])
def test_direct_subject_matcher_supports_native_scripts(name):
    assert contains_core_subject(name)


def test_audit_relevance_uses_body_and_preserves_curated_imports(tmp_path):
    db_path = tmp_path / "reporting.db"
    db = connect(db_path)
    ingest_record(db, {
        "title": "A cabinet member resigns",
        "canonical_url": "https://news.example/body-evidence",
        "content_text": "Jeffrey Epstein appears in the evidence. Epstein appears again.",
        "scope_class": "direct",
    }, discovery_method="publisher_page")
    ingest_record(db, {
        "title": "A reviewed historical investigation",
        "canonical_url": "https://archive.example/reviewed",
        "scope_class": "direct",
    }, discovery_method="import:reviewed_seed")
    ingest_record(db, {
        "title": "An unrelated cabinet story",
        "canonical_url": "https://news.example/unrelated",
        "content_text": "This article concerns an unrelated election and cabinet reshuffle.",
        "scope_class": "direct",
    }, discovery_method="publisher_page")
    cmd_audit_relevance(argparse.Namespace(db=db_path))
    scopes = {
        row["canonical_url"]: row["scope_class"]
        for row in connect(db_path).execute(
            "SELECT canonical_url,scope_class FROM reporting_item"
        )
    }
    assert scopes["https://news.example/body-evidence"] == "direct"
    assert scopes["https://archive.example/reviewed"] == "direct"
    assert scopes["https://news.example/unrelated"] == "background"


def test_direct_reporting_can_use_descriptive_canonical_url():
    assert is_direct_reporting({
        "title": "Comments",
        "canonical_url": "https://news.example/live/jeffrey-epstein-investigation",
    })


def test_candidate_without_substantive_text_remains_metadata_only(monkeypatch):
    raw = b"""<html><head><meta property='og:title' content='Jeffrey Epstein report'></head></html>"""
    monkeypatch.setattr(
        "tools.reporting_corpus.fetch_candidate_url",
        lambda *_: (raw, "https://example.com/report", "text/html"),
    )
    result = _fetch_candidate({
        "id": 1,
        "url": "https://example.com/report",
        "metadata_json": "{}",
        "language": "en",
        "published_at": "2026-01-01",
        "scope_class": "direct",
    }, argparse.Namespace(
        timeout=3, access_status="open", rights_status="local_research",
        store_text=True, delay=0,
    ))
    assert result["status"] == "ingested"
    assert result["record"]["content_text"] is None
    assert result["record"]["rights_status"] == "metadata_only"


def test_cross_domain_redirect_does_not_inherit_candidate_publisher(monkeypatch):
    raw = b"""<html><head><meta property='og:title' content='Jeffrey Epstein report'></head></html>"""
    monkeypatch.setattr(
        "tools.reporting_corpus.fetch_candidate_url",
        lambda *_: (raw, "https://destination.example/report", "text/html"),
    )
    result = _fetch_candidate({
        "id": 2,
        "url": "https://origin.example/report",
        "metadata_json": json.dumps({"publisher": "Origin News"}),
        "language": "en",
        "published_at": "2026-01-01",
        "scope_class": "direct",
    }, argparse.Namespace(
        timeout=3, access_status="open", rights_status="local_research",
        store_text=True, delay=0,
    ))
    assert result["status"] == "ingested"
    assert result["record"]["canonical_url"] == "https://destination.example/report"
    assert result["record"]["publisher"] is None


def test_existing_canonical_publisher_name_is_not_overwritten_by_bad_hint(tmp_path):
    db = connect(tmp_path / "reporting.db")
    ingest_record(db, {
        "title": "First Jeffrey Epstein report",
        "canonical_url": "https://news.example/first",
        "publisher": "Canonical News",
    }, discovery_method="test")
    ingest_record(db, {
        "title": "Second Jeffrey Epstein report",
        "canonical_url": "https://news.example/second",
        "publisher": "Syndication Host",
    }, discovery_method="test")
    publisher = db.execute(
        "SELECT name FROM publisher WHERE domain='news.example'"
    ).fetchone()
    assert publisher["name"] == "Canonical News"


def test_normalize_compact_discovery_timestamp():
    assert normalize_published_at("20260523T083000Z") == "2026-05-23T08:30:00Z"
    assert normalize_published_at("20060724") == "2006-07-24"
    assert normalize_published_at("2026-05-23") == "2026-05-23"
    assert normalize_published_at("2026-04-23T12:00:00+09:00+09:00") == "2026-04-23T12:00:00+09:00"
    assert normalize_published_at("08/02/2026 à 09h55") == "2026-02-08T09:55:00"
    assert normalize_published_at(
        "أربعاء, 12/29/2021 - 16:00"
    ) == "2021-12-29T16:00:00"
    assert normalize_published_at("TZ") is None
    assert publication_date_from_url(
        "https://corriere.it/esteri/24_gennaio_05/jeffrey-epstein.shtml"
    ) == "2024-01-05"


def test_infer_item_type_classifies_video_paths_as_broadcasts():
    assert infer_item_type({}, "https://news.example/video/epstein-report") == "broadcast_transcript"
    assert infer_item_type({}, "https://news.example/news/epstein-report") == "article"
    assert infer_item_type(
        {"item_type": "other"}, "https://news.example/video/epstein-report"
    ) == "other"


def test_parse_article_date_falls_back_to_time_datetime():
    raw = b"""<html><head>
      <title>Jeffrey Epstein report</title>
      <script type="application/ld+json">{"datePublished":"broken",}</script>
    </head><body><article>
      <time datetime="2026-05-16T18:17:26+02:00">16 May 2026</time>
      <p>Jeffrey Epstein reporting with enough context to identify the article.</p>
    </article></body></html>"""
    record = parse_article_html(raw, "https://news.example/epstein")
    assert record["published_at"] == "2026-05-16T18:17:26+02:00"
    assert record["metadata"]["jsonld_parse_error"] is True


def test_parse_article_does_not_use_jsonld_ids_as_entity_names():
    raw = b"""<html><head><script type="application/ld+json">
    {"@type":"NewsArticle","headline":"Jeffrey Epstein report",
     "publisher":{"@id":"https://news.example/#/schema/Organization/1"},
     "author":{"@id":"https://news.example/#/schema/Person/1"}}
    </script></head><body></body></html>"""
    record = parse_article_html(raw, "https://news.example/epstein")
    assert record["publisher"] is None
    assert record["authors"] == []
    assert record["metadata"]["jsonld"]["publisher"]["@id"].startswith("https://")


def test_publication_date_from_known_article_url_patterns():
    assert publication_date_from_url(
        "https://theguardian.com/us-news/live/2026/apr/24/story"
    ) == "2026-04-24"
    assert publication_date_from_url(
        "https://lemonde.fr/international/article/2026/06/10/story.html"
    ) == "2026-06-10"
    assert publication_date_from_url(
        "https://podcasts.lemonde.fr/show/202603040300-episode"
    ) == "2026-03-04"
    assert publication_date_from_url(
        "https://bloomberg.com/news/articles/2026-02-05/example"
    ) == "2026-02-05"
    assert publication_date_from_url("https://example.com/2026/02/31/not-real") is None


def test_normalize_country_collapses_gdelt_names_and_invalid_values():
    assert normalize_country("United States") == "US"
    assert normalize_country("United Kingdom") == "GB"
    assert normalize_country("de") == "DE"
    assert normalize_country("0") is None


def test_schema_v1_migration_keeps_candidates_unreviewed(tmp_path):
    db_path = tmp_path / "reporting.db"
    db = connect(db_path)
    db.execute("UPDATE schema_meta SET value='1' WHERE key='schema_version'")
    db.execute("ALTER TABLE reporting_item DROP COLUMN scope_class")
    db.execute("ALTER TABLE discovery_candidate DROP COLUMN scope_class")
    db.commit()
    db.close()

    migrated = connect(db_path)
    migrated.execute(
        "INSERT INTO discovery_candidate(url,discovery_method) VALUES(?,?)",
        ("https://example.com/legacy", "migration-test"),
    )
    assert migrated.execute(
        "SELECT scope_class FROM discovery_candidate"
    ).fetchone()[0] == "candidate"


def test_ingest_is_idempotent_and_versions_real_changes(tmp_path):
    db = connect(tmp_path / "reporting.db")
    base = {
        "title": "An investigation",
        "canonical_url": "https://example.com/report?utm_campaign=x",
        "publisher": "Example News",
        "published_at": "2025-01-02",
        "authors": ["Reporter One"],
        "content_text": "First version",
        "rights_status": "local_research",
    }
    item_id, created, version_created = ingest_record(db, base, discovery_method="test")
    assert (created, version_created) == (True, True)

    same_id, created, version_created = ingest_record(db, base, discovery_method="test")
    assert same_id == item_id
    assert (created, version_created) == (False, False)

    same_with_provenance = dict(base, metadata={"local_text_ref": "EFTA000001"})
    same_id, created, version_created = ingest_record(
        db, same_with_provenance, discovery_method="test"
    )
    assert (created, version_created) == (False, False)
    metadata = db.execute(
        "SELECT metadata_json FROM item_version WHERE item_id=?", (same_id,)
    ).fetchone()[0]
    assert json.loads(metadata)["local_text_ref"] == "EFTA000001"

    changed = dict(base, content_text="Corrected version", updated_at="2025-01-03")
    same_id, created, version_created = ingest_record(db, changed, discovery_method="test")
    assert same_id == item_id
    assert (created, version_created) == (False, True)
    assert db.execute("SELECT COUNT(*) FROM item_version").fetchone()[0] == 2
    assert db.execute(
        "SELECT COUNT(*) FROM item_version WHERE version_status='current'"
    ).fetchone()[0] == 1
    fts = db.execute("SELECT rowid,item_id FROM reporting_fts").fetchone()
    assert fts["rowid"] == item_id
    assert fts["item_id"] == item_id


def test_metadata_import_enriches_existing_fulltext_without_superseding_it(tmp_path):
    db = connect(tmp_path / "reporting.db")
    item_id, _, _ = ingest_record(db, {
        "title": "Historical investigation",
        "canonical_url": "https://example.com/historical-report",
        "publisher": "Example News",
        "content_text": "Searchable original article text.",
        "metadata": {"http_final_url": "https://example.com/historical-report"},
    }, discovery_method="direct_url")

    same_id, created, version_created = ingest_record(db, {
        "title": "Historical investigation",
        "canonical_url": "https://example.com/historical-report",
        "publisher": "Example News",
        "source_native_id": "HOUSE_OVERSIGHT_000001",
        "metadata": {"local_text_ref": "HOUSE_OVERSIGHT_000001"},
    }, discovery_method="import:historical")

    assert same_id == item_id
    assert (created, version_created) == (False, False)
    item = db.execute("SELECT source_native_id,current_version_id FROM reporting_item").fetchone()
    version = db.execute("SELECT * FROM item_version WHERE id=?", (item["current_version_id"],)).fetchone()
    assert item["source_native_id"] == "HOUSE_OVERSIGHT_000001"
    assert version["content_text"] == "Searchable original article text."
    assert json.loads(version["metadata_json"])["local_text_ref"] == "HOUSE_OVERSIGHT_000001"
    assert db.execute("SELECT COUNT(*) FROM item_version").fetchone()[0] == 1


def test_file_import_links_metadata_alias_to_discovery_candidate(tmp_path):
    db_path = tmp_path / "reporting.db"
    db = connect(db_path)
    db.execute(
        "INSERT INTO discovery_candidate(url,discovery_method) VALUES(?,?)",
        ("https://example.com/old-path", "file"),
    )
    candidate_id = db.execute("SELECT id FROM discovery_candidate").fetchone()[0]
    db.commit()
    seed = tmp_path / "seed.jsonl"
    seed.write_text(
        json.dumps({
            "title": "Historical report",
            "canonical_url": "https://example.com/old-path",
            "publisher": "Example News",
        }) + "\n",
        encoding="utf-8",
    )
    cmd_import_file(argparse.Namespace(
        path=str(seed), source="test", access_status="unknown",
        rights_status="metadata_only", db=str(db_path),
    ))
    imported = connect(db_path).execute(
        "SELECT metadata_json FROM item_version"
    ).fetchone()[0]
    assert json.loads(imported)["source_candidate_id"] == candidate_id


def test_cleanup_canonical_aliases_merges_released_document_provenance(tmp_path):
    db_path = tmp_path / "reporting.db"
    db = connect(db_path)
    db.execute(
        "INSERT INTO discovery_candidate(url,discovery_method) VALUES(?,?)",
        ("https://example.com/old-path", "file"),
    )
    candidate_id = db.execute("SELECT id FROM discovery_candidate").fetchone()[0]
    ingest_record(db, {
        "title": "Historical report",
        "canonical_url": "https://example.com/old-path",
        "publisher": "Example News",
        "source_native_id": "EFTA000001",
        "metadata": {
            "source_candidate_id": candidate_id,
            "local_text_ref": "EFTA000001",
        },
    }, discovery_method="import:test")
    fetched_id, _, _ = ingest_record(db, {
        "title": "Historical report",
        "canonical_url": "https://example.com/new-path",
        "publisher": "Example News",
        "content_text": "Fetched searchable article body.",
        "metadata": {"discovery_candidate_id": candidate_id},
    }, discovery_method="file")

    cmd_cleanup_canonical_aliases(argparse.Namespace(db=str(db_path)))

    checked = connect(db_path)
    assert checked.execute("SELECT COUNT(*) FROM reporting_item").fetchone()[0] == 1
    item = checked.execute("SELECT * FROM reporting_item").fetchone()
    version = checked.execute(
        "SELECT * FROM item_version WHERE id=?", (item["current_version_id"],)
    ).fetchone()
    assert item["id"] == fetched_id
    assert item["source_native_id"] == "EFTA000001"
    assert version["content_text"] == "Fetched searchable article body."
    metadata = json.loads(version["metadata_json"])
    assert metadata["local_text_ref"] == "EFTA000001"
    assert metadata["canonical_aliases"] == ["https://example.com/old-path"]


def test_cleanup_canonical_aliases_preserves_richer_archived_version(tmp_path):
    db_path = tmp_path / "reporting.db"
    db = connect(db_path)
    db.execute(
        "INSERT INTO discovery_candidate(url,discovery_method) VALUES(?,?)",
        ("https://example.co.uk/old-path", "file"),
    )
    candidate_id = db.execute("SELECT id FROM discovery_candidate").fetchone()[0]
    ingest_record(db, {
        "title": "Historical report",
        "canonical_url": "https://example.co.uk/old-path",
        "publisher": "Example News",
        "content_text": "Archived complete article body. " * 20,
        "archive_url": "https://web.archive.org/example",
        "metadata": {"source_candidate_id": candidate_id},
    }, discovery_method="archive")
    fetched_id, _, _ = ingest_record(db, {
        "title": "Historical report",
        "canonical_url": "https://example.com/new-path",
        "publisher": "Example News",
        "content_text": "Short live excerpt.",
        "metadata": {"discovery_candidate_id": candidate_id},
    }, discovery_method="file")

    cmd_cleanup_canonical_aliases(argparse.Namespace(db=str(db_path)))

    checked = connect(db_path)
    item = checked.execute("SELECT * FROM reporting_item").fetchone()
    current = checked.execute(
        "SELECT * FROM item_version WHERE id=?", (item["current_version_id"],)
    ).fetchone()
    assert item["id"] == fetched_id
    assert current["content_text"] == "Archived complete article body. " * 20
    assert current["archive_url"] == "https://web.archive.org/example"
    assert checked.execute(
        "SELECT COUNT(*) FROM item_version WHERE item_id=?", (fetched_id,)
    ).fetchone()[0] == 2
    assert checked.execute(
        "SELECT COUNT(*) FROM item_version WHERE item_id=? AND version_status='current'",
        (fetched_id,),
    ).fetchone()[0] == 1


def test_file_reimport_uses_known_fetched_canonical_without_alias_churn(tmp_path):
    db_path = tmp_path / "reporting.db"
    db = connect(db_path)
    db.execute(
        "INSERT INTO discovery_candidate(url,discovery_method,status) VALUES(?,?,'ingested')",
        ("https://example.com/old-path", "file"),
    )
    candidate_id = db.execute("SELECT id FROM discovery_candidate").fetchone()[0]
    fetched_id, _, _ = ingest_record(db, {
        "title": "Historical report",
        "canonical_url": "https://example.com/new-path",
        "publisher": "Example News",
        "content_text": "Fetched searchable article body.",
        "metadata": {"discovery_candidate_id": candidate_id},
    }, discovery_method="file")
    seed = tmp_path / "seed.jsonl"
    seed.write_text(json.dumps({
        "title": "Historical report",
        "canonical_url": "https://example.com/old-path",
        "publisher": "Example News",
        "source_native_id": "EFTA000002",
        "metadata": {"local_text_ref": "EFTA000002"},
    }) + "\n", encoding="utf-8")

    cmd_import_file(argparse.Namespace(
        path=str(seed), source="test", access_status="unknown",
        rights_status="metadata_only", db=str(db_path),
    ))

    checked = connect(db_path)
    assert checked.execute("SELECT COUNT(*) FROM reporting_item").fetchone()[0] == 1
    item = checked.execute("SELECT * FROM reporting_item").fetchone()
    version = checked.execute(
        "SELECT * FROM item_version WHERE id=?", (item["current_version_id"],)
    ).fetchone()
    assert item["id"] == fetched_id
    assert item["source_native_id"] == "EFTA000002"
    metadata = json.loads(version["metadata_json"])
    assert metadata["local_text_ref"] == "EFTA000002"
    assert metadata["canonical_aliases"] == ["https://example.com/old-path"]


def test_reconcile_candidate_statuses_clears_stale_failure(tmp_path):
    db = connect(tmp_path / "reporting.db")
    ingest_record(db, {
        "title": "Jeffrey Epstein report",
        "canonical_url": "https://example.com/report",
        "publisher": "Example News",
        "content_text": "Searchable report.",
    }, discovery_method="direct")
    db.execute(
        """INSERT INTO discovery_candidate(url,discovery_method,status,status_note)
           VALUES(?,?,'failed','later retry timed out')""",
        ("https://example.com/report", "test"),
    )
    db.commit()

    assert reconcile_candidate_statuses(db) == 1
    candidate = db.execute(
        "SELECT status,status_note FROM discovery_candidate"
    ).fetchone()
    assert candidate["status"] == "ingested"
    assert candidate["status_note"] == "Canonical reporting item already present"


def test_reconcile_candidate_statuses_preserves_materialized_fetch_queue(tmp_path):
    db_path = tmp_path / "reporting.db"
    db = connect(db_path)
    db.execute(
        """INSERT INTO discovery_candidate(
               url,title,publisher_domain,discovery_method,status,metadata_json
           ) VALUES(?,?,?,?,?,?)""",
        (
            "https://news.example/jeffrey-epstein-report",
            "Jeffrey Epstein report",
            "news.example",
            "file:test",
            "failed",
            json.dumps({"publisher": "Example News"}),
        ),
    )
    db.commit()
    cmd_materialize_candidates(argparse.Namespace(
        db=db_path, status=["failed"], method="file:test", run_id=None,
        limit=10, access_status="unavailable", require_direct=True,
    ))

    db = connect(db_path)
    assert reconcile_candidate_statuses(db) == 0
    assert db.execute(
        "SELECT status FROM discovery_candidate"
    ).fetchone()[0] == "failed"


def test_unreviewed_publisher_metadata_is_preserved_without_quality_assumption(tmp_path):
    db = connect(tmp_path / "reporting.db")
    ingest_record(db, {
        "title": "Jeffrey Epstein report",
        "canonical_url": "https://new-outlet.example/report",
        "publisher": "New Outlet",
        "publisher_country": "Turkey",
        "publisher_default_language": "Turkish",
        "content_text": "Jeffrey Epstein reporting text.",
    }, discovery_method="gdelt")
    publisher = db.execute(
        "SELECT country,default_language,source_type FROM publisher"
    ).fetchone()
    assert publisher["country"] == "TR"
    assert publisher["default_language"] == "tr"
    assert publisher["source_type"] == "unknown"


def test_ingest_uses_existing_publisher_default_language(tmp_path):
    db = connect(tmp_path / "reporting.db")
    db.execute(
        "INSERT INTO publisher(name,domain,default_language) VALUES(?,?,?)",
        ("Example News", "example.com", "en"),
    )
    db.commit()
    item_id, _, _ = ingest_record(db, {
        "title": "Jeffrey Epstein report",
        "canonical_url": "https://example.com/report",
        "publisher": "Example News",
        "content_text": "Reporting text.",
    }, discovery_method="test")
    assert db.execute(
        "SELECT language FROM reporting_item WHERE id=?", (item_id,)
    ).fetchone()[0] == "en"


def test_html_parser_uses_structured_article_metadata():
    raw = b"""
    <html><head><link rel="canonical" href="https://news.example/story">
    <script type="application/ld+json">{
      "@type":"NewsArticle","headline":"Structured title",
      "datePublished":"2024-02-03","author":{"name":"Jane Reporter"},
      "publisher":{"name":"News Example"}
    }</script></head><body><article>Substantive reporting text.</article></body></html>
    """
    parsed = parse_article_html(raw, "https://news.example/amp/story")
    assert parsed["title"] == "Structured title"
    assert parsed["canonical_url"] == "https://news.example/story"
    assert parsed["authors"] == ["Jane Reporter"]
    assert "Substantive reporting text" in parsed["content_text"]


def test_html_parser_normalizes_list_valued_jsonld_scalars():
    raw = b'''
    <html><head><script type="application/ld+json">{
      "@type":"NewsArticle","headline":["List headline"],
      "datePublished":["2026-05-07T09:30:00Z"],
      "dateModified":{"@value":"2026-05-08T10:00:00Z"},
      "inLanguage":[{"name":"en"}],
      "publisher":[{"name":"List Publisher"}],
      "description":["List description"]
    }</script></head><body><article>Jeffrey Epstein reporting text.</article></body></html>
    '''
    parsed = parse_article_html(raw, "https://news.example/story")
    assert parsed["title"] == "List headline"
    assert parsed["published_at"] == "2026-05-07T09:30:00Z"
    assert parsed["updated_at"] == "2026-05-08T10:00:00Z"
    assert parsed["language"] == "en"
    assert parsed["publisher"] == "List Publisher"
    assert parsed["abstract"] == "List description"


def test_archive_index_parsers_preserve_capture_identity():
    cdx = json.dumps([
        ["timestamp", "original", "statuscode", "digest"],
        ["20260102030405", "https://news.example/story", "200", "ABC123"],
    ]).encode()
    assert parse_wayback_cdx(cdx)[0]["digest"] == "ABC123"
    commoncrawl = (
        b'{"url":"https://news.example/story","timestamp":"20260103000000",'
        b'"status":"200","digest":"XYZ"}\n'
    )
    assert parse_commoncrawl_index(commoncrawl)[0]["timestamp"] == "20260103000000"


def test_wayback_domain_discovery_uses_server_side_urlkey_filter(monkeypatch):
    captured = {}
    payload = json.dumps([
        ["timestamp", "original", "statuscode", "mimetype", "digest"],
        ["20190718", "https://news.example/jeffrey-epstein-report", "200", "text/html", "ABC"],
    ]).encode()
    def fake_fetch(url, timeout=30, headers=None, retries=2):
        captured["url"] = url
        return payload, url, "application/json"
    monkeypatch.setattr("tools.reporting_corpus._fetch_bytes", fake_fetch)
    rows = wayback_domain_urls("news.example", "Epstein", limit=25)
    query = parse_qs(urlsplit(captured["url"]).query)
    assert query["matchType"] == ["domain"]
    assert "urlkey:.*epstein.*" in query["filter"]
    assert query["collapse"] == ["urlkey"]
    assert rows[0]["original"].endswith("epstein-report")


def test_discover_file_adds_fetch_candidates_idempotently(tmp_path):
    seed = tmp_path / "historical.jsonl"
    seed.write_text(json.dumps({
        "title": "Opaque publisher URL",
        "canonical_url": "https://news.example/local/article12345.html",
        "publisher": "Example News",
        "published_at": "2019-07-01",
        "language": "en",
        "scope_class": "direct",
    }) + "\n", encoding="utf-8")
    db_path = tmp_path / "reporting.db"
    args = argparse.Namespace(path=str(seed), source="curated", db=db_path)
    cmd_discover_file(args)
    cmd_discover_file(args)
    db = connect(db_path)
    row = db.execute("SELECT * FROM discovery_candidate").fetchone()
    assert db.execute("SELECT COUNT(*) FROM discovery_candidate").fetchone()[0] == 1
    assert row["title"] == "Opaque publisher URL"
    assert row["published_at"] == "2019-07-01"
    assert row["language"] == "en"
    assert row["scope_class"] == "direct"
    assert json.loads(row["metadata_json"])["publisher"] == "Example News"


def test_discover_file_reactivation_tracks_current_run(tmp_path):
    seed = tmp_path / "reactivate.jsonl"
    seed.write_text(json.dumps({
        "title": "Jeffrey Epstein report",
        "canonical_url": "https://news.example/epstein-report",
        "language": "en",
    }) + "\n", encoding="utf-8")
    db_path = tmp_path / "reporting.db"
    args = argparse.Namespace(path=str(seed), source="first", db=db_path)
    cmd_discover_file(args)
    db = connect(db_path)
    first_run = db.execute(
        "SELECT discovery_run_id FROM discovery_candidate"
    ).fetchone()[0]
    db.execute("UPDATE discovery_candidate SET status='excluded'")
    db.commit()
    args.source = "second"
    cmd_discover_file(args)
    row = connect(db_path).execute(
        "SELECT discovery_run_id,discovery_method,status FROM discovery_candidate"
    ).fetchone()
    assert row["discovery_run_id"] != first_run
    assert row["discovery_method"] == "file:second"
    assert row["status"] == "pending"


def test_materialize_candidates_keeps_fetch_queue(tmp_path):
    db_path = tmp_path / "reporting.db"
    db = connect(db_path)
    db.execute(
        """INSERT INTO discovery_candidate(
               url,title,publisher_domain,language,discovery_method,metadata_json,scope_class
           ) VALUES(?,?,?,?,?,?,?)""",
        (
            "https://news.example/jeffrey-epstein-report", "Jeffrey Epstein report",
            "news.example", "en", "publisher_page",
            json.dumps({"publisher": "Example News"}), "candidate",
        ),
    )
    db.commit()
    cmd_materialize_candidates(argparse.Namespace(
        db=db_path, status=None, method="publisher_page", limit=10,
        access_status="unknown", require_direct=True,
    ))
    db = connect(db_path)
    assert db.execute("SELECT status FROM discovery_candidate").fetchone()[0] == "pending"
    item = db.execute("SELECT title,scope_class,rights_status FROM reporting_item").fetchone()
    assert tuple(item) == ("Jeffrey Epstein report", "direct", "metadata_only")


def test_materialize_candidates_can_target_discovery_run(tmp_path):
    db_path = tmp_path / "reporting.db"
    db = connect(db_path)
    run_ids = []
    for source in ("first", "second"):
        cursor = db.execute(
            "INSERT INTO discovery_run(method,source_name) VALUES('publisher_page',?)",
            (source,),
        )
        run_ids.append(cursor.lastrowid)
    for run_id, suffix in zip(run_ids, ("one", "two")):
        db.execute(
            """INSERT INTO discovery_candidate(
                   url,title,publisher_domain,language,discovery_run_id,
                   discovery_method,metadata_json,status,scope_class
               ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                f"https://news.example/jeffrey-epstein-{suffix}",
                f"Jeffrey Epstein {suffix}", "news.example", "en", run_id,
                "publisher_page", "{}", "excluded", "candidate",
            ),
        )
    db.commit()
    cmd_materialize_candidates(argparse.Namespace(
        db=db_path, status=["excluded"], method="publisher_page",
        run_id=run_ids[1], limit=10, access_status="paywalled",
        require_direct=True,
    ))
    items = connect(db_path).execute(
        "SELECT canonical_url FROM reporting_item ORDER BY canonical_url"
    ).fetchall()
    assert [row["canonical_url"] for row in items] == [
        "https://news.example/jeffrey-epstein-two"
    ]


def test_materialize_candidates_skips_topic_landing_page(tmp_path):
    db_path = tmp_path / "reporting.db"
    db = connect(db_path)
    db.execute(
        """INSERT INTO discovery_candidate(
               url,title,publisher_domain,language,discovery_method,status,scope_class
           ) VALUES(?,?,?,?,?,?,?)""",
        (
            "https://wyborcza.pl/0,128956.html?tag=Jeffrey+Epstein",
            "Jeffrey Epstein", "wyborcza.pl", "pl", "publisher_page",
            "excluded", "candidate",
        ),
    )
    db.commit()
    cmd_materialize_candidates(argparse.Namespace(
        db=db_path, status=["excluded"], method="publisher_page",
        run_id=None, limit=10, access_status="paywalled", require_direct=True,
    ))
    assert connect(db_path).execute(
        "SELECT COUNT(*) FROM reporting_item"
    ).fetchone()[0] == 0


def test_candidate_url_variants_preserve_origin_and_try_www():
    variants = candidate_url_variants(
        "https://miamiherald.com/news/local/article123.html",
        {"source_record": {"canonical_url": "https://www.miamiherald.com/news/local/article123.html"}},
    )
    assert variants == [
        "https://www.miamiherald.com/news/local/article123.html",
        "https://miamiherald.com/news/local/article123.html",
    ]


def test_candidate_url_variants_map_asahi_mobile_article_id():
    assert candidate_url_variants(
        "https://smart.asahi.com/v/article/ASV2313ZDV23SFVU0JCM.php"
    ) == [
        "https://smart.asahi.com/v/article/ASV2313ZDV23SFVU0JCM.php",
        "https://www.asahi.com/articles/ASV2313ZDV23SFVU0JCM.html",
        "https://www.smart.asahi.com/v/article/ASV2313ZDV23SFVU0JCM.php",
    ]


def test_extract_page_links_resolves_and_deduplicates():
    raw = b'''<a href="/news/jeffrey-epstein-one"><span>First</span> report</a>
             <a href="/news/jeffrey-epstein-one">Duplicate</a>
             <a href="https://other.example/maxwell">Other</a>'''
    assert extract_page_links(raw, "https://news.example/topic") == [
        ("https://news.example/news/jeffrey-epstein-one", "First report"),
        ("https://other.example/maxwell", "Other"),
    ]


def test_discover_page_skips_source_page_self_link(tmp_path, monkeypatch):
    raw = b'''<a href="/topic/epstein">Epstein reports</a>
             <a href="/news/epstein-story">Epstein investigation</a>'''
    monkeypatch.setattr(
        "tools.reporting_corpus.fetch_url",
        lambda *_: (raw, "https://news.example/topic/epstein", "text/html"),
    )
    db_path = tmp_path / "reporting.db"
    cmd_discover_page(argparse.Namespace(
        url="https://news.example/topic/epstein", timeout=3, query=["Epstein"],
        link_regex=None, same_domain=True, language="en", publisher="Example News",
        db=db_path,
    ))
    db = connect(db_path)
    rows = db.execute("SELECT url FROM discovery_candidate").fetchall()
    assert [row[0] for row in rows] == ["https://news.example/news/epstein-story"]


def test_navigation_links_are_not_reporting_items():
    assert is_navigation_link("12")
    assert is_navigation_link("Siguiente >")
    assert is_navigation_link("Próxima »")
    assert is_navigation_link("Vis ældre")
    assert is_navigation_link("Vis nyere")
    assert is_navigation_link("כתבות נוספות")
    assert is_navigation_link("29 April 2026")
    assert not is_navigation_link("12 facts about Jeffrey Epstein")


def test_subscription_landing_pages_are_not_reporting_items():
    assert is_topic_landing_page("https://elpais.com/subscriptions")
    assert is_topic_landing_page("https://elpais.com/suscripciones")
    assert is_topic_landing_page(
        "https://telex.hu/tamogatas?referer=https%3A%2F%2Ftelex.hu%2Fcimke%2Fepstein"
    )
    assert is_topic_landing_page(
        "https://aajtak.in/userfeedback?siteId=1&type=feedback"
    )
    assert not is_topic_landing_page(
        "https://news.example/2026/01/02/subscriptions-funded-the-investigation"
    )


def test_candidate_display_title_uses_only_descriptive_slugs():
    assert candidate_display_title({
        "title": None,
        "url": "https://news.example/2026/jun/10/bill-gates-testimony-jeffrey-epstein",
    }) == "Bill gates testimony jeffrey epstein"
    opaque = "https://news.example/article/syrglxhibx"
    assert candidate_display_title({"title": None, "url": opaque}) == opaque


def test_cleanup_navigation_removes_generated_item(tmp_path):
    db_path = tmp_path / "reporting.db"
    db = connect(db_path)
    db.execute(
        """INSERT INTO discovery_candidate(
               url,title,publisher_domain,discovery_method,metadata_json,scope_class
           ) VALUES(?,?,?,?,?,?)""",
        (
            "https://news.example/jeffrey-epstein?page=2", "2", "news.example",
            "publisher_page", json.dumps({"publisher": "Example News"}), "candidate",
        ),
    )
    db.commit()
    cmd_materialize_candidates(argparse.Namespace(
        db=db_path, status=None, method="publisher_page", limit=10,
        access_status="unknown", require_direct=True,
    ))
    cmd_cleanup_navigation(argparse.Namespace(db=db_path))
    db = connect(db_path)
    assert db.execute("SELECT COUNT(*) FROM reporting_item").fetchone()[0] == 0
    row = db.execute("SELECT status,status_note FROM discovery_candidate").fetchone()
    assert row["status"] == "excluded"
    assert "pagination" in row["status_note"]


def test_cleanup_navigation_removes_topic_item_after_canonical_redirect(tmp_path):
    db_path = tmp_path / "reporting.db"
    db = connect(db_path)
    db.execute(
        """INSERT INTO discovery_candidate(
               url,title,publisher_domain,discovery_method,status
           ) VALUES(?,?,?,'publisher_page','ingested')""",
        (
            "https://news.example/theme/4294",
            "Jeffrey Epstein topic",
            "news.example",
        ),
    )
    candidate_id = db.execute("SELECT id FROM discovery_candidate").fetchone()[0]
    ingest_record(db, {
        "title": "Jeffrey Epstein topic",
        "canonical_url": "https://news.example/",
        "publisher": "Example News",
        "content_text": "Jeffrey Epstein topic landing page. " * 10,
        "metadata": {"discovery_candidate_id": candidate_id},
    }, discovery_method="publisher_page")

    cmd_cleanup_navigation(argparse.Namespace(db=db_path))

    checked = connect(db_path)
    assert checked.execute("SELECT COUNT(*) FROM reporting_item").fetchone()[0] == 0
    candidate = checked.execute(
        "SELECT status,status_note FROM discovery_candidate"
    ).fetchone()
    assert candidate["status"] == "excluded"
    assert "topic/index" in candidate["status_note"]


def test_cleanup_navigation_excludes_subscription_candidate_once(tmp_path, capsys):
    db_path = tmp_path / "reporting.db"
    db = connect(db_path)
    db.execute(
        """INSERT INTO discovery_candidate(
               url,title,publisher_domain,discovery_method,status
           ) VALUES(?,?,?,?,?)""",
        (
            "https://news.example/subscriptions", "Subscribe", "news.example",
            "publisher_page", "failed",
        ),
    )
    db.commit()

    args = argparse.Namespace(db=db_path)
    cmd_cleanup_navigation(args)
    assert "Excluded 1 navigation candidates" in capsys.readouterr().out
    cmd_cleanup_navigation(args)
    assert "Excluded 0 navigation candidates" in capsys.readouterr().out
    row = connect(db_path).execute(
        "SELECT status,status_note FROM discovery_candidate"
    ).fetchone()
    assert row["status"] == "excluded"
    assert "topic/index" in row["status_note"]


def test_ingest_marks_candidate_id_when_article_canonical_changes(tmp_path, monkeypatch):
    db_path = tmp_path / "reporting.db"
    db = connect(db_path)
    ingest_record(db, {
        "title": "Metadata title",
        "canonical_url": "https://news.example/story?from=search",
        "publisher": "Example News",
    }, discovery_method="metadata")
    db.execute("UPDATE discovery_candidate SET status='pending'")
    db.commit()
    db.execute(
        """INSERT INTO discovery_candidate(
               url,title,publisher_domain,discovery_method,metadata_json,scope_class
           ) VALUES(?,?,?,?,?,?)""",
        (
            "https://news.example/story?from=search", "Jeffrey Epstein report",
            "news.example", "publisher_page", "{}", "direct",
        ),
    )
    db.commit()
    monkeypatch.setattr("tools.reporting_corpus._fetch_candidate", lambda candidate, args: {
        "status": "ingested",
        "record": {
            "title": "Jeffrey Epstein report",
            "canonical_url": "https://news.example/story",
            "publisher": "Example News",
            "content_text": "Jeffrey Epstein reporting " * 30,
            "rights_status": "local_research",
            "metadata": {},
        },
    })
    cmd_ingest_candidates(argparse.Namespace(
        db=db_path, limit=10, workers=1, timeout=1, delay=0,
        store_text=True, rights_status="local_research", access_status="unknown",
    ))
    db = connect(db_path)
    assert db.execute("SELECT status FROM discovery_candidate").fetchone()[0] == "ingested"
    assert db.execute("SELECT COUNT(*) FROM reporting_item").fetchone()[0] == 1
    assert db.execute("SELECT canonical_url FROM reporting_item").fetchone()[0] == "https://news.example/story"


def test_search_falls_back_to_literal_cjk_substring(tmp_path, capsys):
    db_path = tmp_path / "reporting.db"
    db = connect(db_path)
    ingest_record(db, {
        "title": "エプスタイン文書を解析",
        "canonical_url": "https://news.example/japanese-report",
        "publisher": "Example Japan",
        "language": "ja",
    }, discovery_method="test")
    cmd_search(argparse.Namespace(
        db=db_path, query="エプスタイン", include_background=False,
        limit=5, output=None, json_out=True,
    ))
    assert json.loads(capsys.readouterr().out)[0]["title"] == "エプスタイン文書を解析"


def test_commoncrawl_warc_extraction_returns_embedded_html():
    html_body = b"<html><article>Archived reporting text.</article></html>"
    warc = (
        b"WARC/1.0\r\nContent-Type: application/http; msgtype=response\r\n\r\n"
        b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + html_body
    )
    body, headers = extract_warc_http_payload(warc)
    assert body == html_body
    assert headers["content-type"] == "text/html"


def test_archive_ingest_preserves_original_outlet_and_snapshot_path(tmp_path):
    db = connect(tmp_path / "reporting.db")
    raw = ('''<html><head><title>Archived investigation</title></head>
      <body><article>''' + ("Archived substantive reporting text. " * 20) +
      '''</article></body></html>''').encode()
    item_id, created, version_created = _archive_ingest_record(
        db,
        "https://news.example/investigation",
        raw,
        "https://web.archive.org/web/20260102030405id_/https://news.example/investigation",
        {"archive_provider": "wayback", "archive_timestamp": "20260102030405"},
        store_text=True,
        context={"title": "Archived investigation", "access_status": "paywalled"},
        discovery_method="archive:wayback",
    )
    assert created and version_created
    item = db.execute("SELECT * FROM reporting_item WHERE id=?", (item_id,)).fetchone()
    version = db.execute("SELECT * FROM item_version WHERE item_id=?", (item_id,)).fetchone()
    assert item["canonical_url"] == "https://news.example/investigation"
    assert item["access_status"] == "paywalled"
    assert item["independence_group"] == "outlet:news.example"
    assert version["archive_url"].startswith("https://web.archive.org/")
    assert "Archived substantive" in version["content_text"]


def test_archive_ingest_replaces_metadata_placeholder_title(tmp_path):
    db = connect(tmp_path / "reporting.db")
    original = "https://news.example/investigation"
    ingest_record(db, {
        "title": "Untitled reporting item",
        "canonical_url": original,
        "publisher": "Example News",
        "published_at": "2006-07-24",
        "access_status": "unavailable",
    }, discovery_method="metadata_seed")
    raw = ('''<html><head><title>Publisher archive headline</title></head>
      <body><article>''' + ("Jeffrey Epstein archive reporting. " * 20) +
      '''</article></body></html>''').encode()
    item_id, created, version_created = _archive_ingest_record(
        db, original, raw,
        "https://web.archive.org/web/20060724id_/https://news.example/investigation",
        {"archive_provider": "wayback"}, store_text=True,
        discovery_method="archive:wayback",
    )
    item = db.execute(
        "SELECT title,published_at,access_status FROM reporting_item WHERE id=?",
        (item_id,),
    ).fetchone()
    assert not created and version_created
    assert item["title"] == "Publisher archive headline"
    assert item["published_at"] == "2006-07-24"
    assert item["access_status"] == "archive_only"


def test_parse_article_uses_legacy_story_markers_without_navigation():
    raw = ('''<html><head><title>Archived headline</title></head><body>
      <nav>Home Sports Weather Unrelated navigation</nav>
      <!--begintext--><h2>Archived headline</h2><p>''' +
      ("Jeffrey Epstein first story segment. " * 10) +
      '''</p><!--endtext--><aside>More unrelated links</aside>
      <!--begintext--><p>''' + ("Continuation reporting detail. " * 10) +
      '''</p><!--endtext--><footer>Subscribe now</footer></body></html>''').encode()
    record = parse_article_html(raw, "https://news.example/archive")
    assert "Jeffrey Epstein first story segment" in record["content_text"]
    assert "Continuation reporting detail" in record["content_text"]
    assert "Unrelated navigation" not in record["content_text"]
    assert "Subscribe now" not in record["content_text"]
    assert record["metadata"]["body_extraction"] == "html_comment_markers"


def test_archive_validation_rejects_empty_replay():
    with pytest.raises(ValueError, match="not substantive HTML"):
        validate_archived_html(b"[]")


def test_archive_candidate_rejects_unrelated_context(tmp_path):
    db = connect(tmp_path / "reporting.db")
    raw = ("<html><article>" + ("Unrelated financial reporting. " * 30) + "</article></html>").encode()
    with pytest.raises(ValueError, match="lacks direct Epstein/Maxwell"):
        _archive_ingest_record(
            db, "https://news.example/unrelated", raw,
            "https://web.archive.org/web/20250101id_/https://news.example/unrelated",
            {"archive_provider": "wayback"}, store_text=True,
            context={"scope_class": "candidate"}, discovery_method="archive:wayback",
        )


def test_archive_url_variants_cover_www_and_trailing_slash():
    variants = archive_url_variants("https://news.example/story")
    assert "https://news.example/story" in variants
    assert "https://www.news.example/story/" in variants


def test_commoncrawl_404_continues_to_older_index(monkeypatch):
    collections = json.dumps([
        {"id": "new", "cdx-api": "https://index.example/new"},
        {"id": "old", "cdx-api": "https://index.example/old"},
    ]).encode()
    record = b'{"url":"https://news.example/story","timestamp":"20250101","status":"200","mime":"text/html"}\n'
    def fake_fetch(url, timeout=30, headers=None, retries=2):
        if url.endswith("collinfo.json"):
            return collections, url, "application/json"
        if "index.example/new" in url:
            raise HTTPError(url, 404, "not found", {}, io.BytesIO())
        return record, url, "application/x-ndjson"
    monkeypatch.setattr("tools.reporting_corpus._fetch_bytes", fake_fetch)
    monkeypatch.setattr("tools.reporting_corpus._COMMONCRAWL_COLLECTIONS_CACHE", None)
    result = commoncrawl_capture("https://news.example/story", indexes=2)
    assert result["collection"] == "old"


def test_archive_fetch_retries_transient_network_failure(monkeypatch):
    class Headers:
        def get_content_type(self): return "text/html"
    class Response:
        headers = Headers()
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return b"<html>recovered</html>"
        def geturl(self): return "https://archive.example/story"
    calls = []
    def fake_open(req, timeout):
        calls.append(req.full_url)
        if len(calls) == 1:
            raise URLError("temporary refusal")
        return Response()
    monkeypatch.setattr("tools.reporting_corpus.urlopen", fake_open)
    monkeypatch.setattr("tools.reporting_corpus.time.sleep", lambda _: None)
    raw, _, _ = _fetch_bytes("https://archive.example/story", retries=1)
    assert raw.startswith(b"<html>")
    assert len(calls) == 2


def test_ris_import_preserves_licensed_metadata(tmp_path):
    path = tmp_path / "export.ris"
    path.write_text(
        "TY  - NEWS\nTI  - Database story\nAU  - Reporter, Jane\n"
        "DA  - 2025/03/04\nUR  - https://example.com/db-story\n"
        "JO  - Example Daily\nER  -\n",
        encoding="utf-8",
    )
    rows = _records_from_ris(path)
    assert rows[0]["title"] == "Database story"
    assert rows[0]["authors"] == ["Reporter, Jane"]
    assert rows[0]["access_status"] == "licensed"


def test_supported_claim_requires_quoted_primary_evidence(tmp_path):
    db_path = tmp_path / "reporting.db"
    db = connect(db_path)
    item_id, _, _ = ingest_record(
        db,
        {"title": "Story", "canonical_url": "https://example.com/story"},
        discovery_method="test",
    )
    claim_id = db.execute(
        "INSERT INTO reporting_claim(item_id,claim_text) VALUES(?,?)",
        (item_id, "A reported claim"),
    ).lastrowid
    db.execute(
        """INSERT INTO claim_source(claim_id,source_type,source_ref,is_primary)
           VALUES(?,'primary_document','EFTA00000001',1)""",
        (claim_id,),
    )
    db.commit()
    args = argparse.Namespace(
        db=db_path, claim_id=claim_id, status="primary_supported",
        confidence="high", by="reviewer",
    )
    with pytest.raises(ValueError, match="requires a primary evidence link with --quote"):
        cmd_verify_claim(args)

    db.execute(
        "UPDATE claim_source SET source_quote='Primary text' WHERE claim_id=?", (claim_id,)
    )
    db.commit()
    cmd_verify_claim(args)
    assert db.execute(
        "SELECT verification_status FROM reporting_claim WHERE id=?", (claim_id,)
    ).fetchone()[0] == "primary_supported"


def test_verify_claim_rejects_unknown_claim(tmp_path):
    db_path = tmp_path / "reporting.db"
    connect(db_path).close()
    args = argparse.Namespace(
        db=db_path, claim_id=999, status="reported_only",
        confidence="unverified", by="reviewer",
    )
    with pytest.raises(ValueError, match=r"Claim #999 not found"):
        cmd_verify_claim(args)


def test_entity_ids_are_external_not_foreign_keys(tmp_path):
    db = connect(tmp_path / "reporting.db")
    item_id, _, _ = ingest_record(
        db, {"title": "Story", "canonical_url": "https://example.com/story"},
        discovery_method="test",
    )
    db.execute(
        """INSERT INTO item_entity(item_id,entity_id,mention_text,match_method)
           VALUES(?,999999,'External entity','test')""",
        (item_id,),
    )
    db.commit()
    assert db.execute("SELECT entity_id FROM item_entity").fetchone()[0] == 999999


def test_promotion_requires_and_preserves_quoted_primary_evidence(tmp_path, monkeypatch):
    core_path = tmp_path / "investigation.db"
    monkeypatch.setattr("tools.lead_tracker.DB_PATH", core_path)
    monkeypatch.setattr("tools.lead_tracker._schema_initialized", False)
    monkeypatch.setattr("tools.findings_tracker.DB_PATH", core_path)
    monkeypatch.setattr("tools.findings_tracker._schema_initialized", False)
    from tools.lead_tracker import get_db
    core = get_db()
    cols = {row[1] for row in core.execute("PRAGMA table_info(findings)")}
    for column in ("event_date_iso", "date_precision"):
        if column not in cols:
            core.execute(f"ALTER TABLE findings ADD COLUMN {column} TEXT")
    core.commit()

    reporting_path = tmp_path / "reporting.db"
    db = connect(reporting_path)
    item_id, _, _ = ingest_record(
        db,
        {"title": "Epstein report", "canonical_url": "https://example.com/epstein"},
        discovery_method="test",
    )
    claim_id = db.execute(
        """INSERT INTO reporting_claim(
               item_id,claim_text,subject_text,verification_status,confidence,
               reviewed_by,reviewed_at)
           VALUES(?,?,'Example Subject','primary_supported','high','reviewer','2026-01-01')""",
        (item_id, "Primary document establishes the reported event."),
    ).lastrowid
    db.execute(
        """INSERT INTO claim_source(
               claim_id,source_type,source_ref,source_quote,source_page,is_primary)
           VALUES(?,'primary_document','EFTA00000001','Quoted primary text','p.1',1)""",
        (claim_id,),
    )
    db.commit()

    cmd_promote(argparse.Namespace(
        db=reporting_path, claim_id=claim_id, by="reviewer",
        finding_type="document", confidence="high",
    ))

    finding = core.execute(
        "SELECT id,source_datasets,claim_type,confidence FROM findings"
    ).fetchone()
    assert finding["source_datasets"] == '["reporting"]'
    assert finding["claim_type"] == "paraphrase"
    evidence = core.execute(
        "SELECT evidence_ref,source_quote,source_page FROM finding_evidence WHERE finding_id=?",
        (finding["id"],),
    ).fetchone()
    assert tuple(evidence) == ("EFTA00000001", "Quoted primary text", "p.1")
    assert db.execute(
        "SELECT finding_id FROM claim_promotion WHERE claim_id=?", (claim_id,)
    ).fetchone()[0] == finding["id"]


def test_json_fetch_retries_one_429(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps({"articles": []}).encode()

    calls = []

    def fake_open(req, timeout):
        calls.append((req, timeout))
        if len(calls) == 1:
            raise HTTPError(req.full_url, 429, "rate limited", {"Retry-After": "0"}, io.BytesIO())
        return Response()

    monkeypatch.setattr("tools.reporting_corpus.urlopen", fake_open)
    monkeypatch.setattr("tools.reporting_corpus.time.sleep", lambda _: None)
    from urllib.request import Request
    assert fetch_json_with_429_retry(Request("https://example.com"), 3) == {"articles": []}
    assert len(calls) == 2


def test_json_fetch_uses_bounded_exponential_429_retries(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps({"articles": []}).encode()

    calls = []
    delays = []

    def fake_open(req, timeout):
        calls.append((req, timeout))
        if len(calls) <= 3:
            raise HTTPError(req.full_url, 429, "rate limited", {}, io.BytesIO())
        return Response()

    monkeypatch.setattr("tools.reporting_corpus.urlopen", fake_open)
    monkeypatch.setattr("tools.reporting_corpus.time.sleep", delays.append)
    from urllib.request import Request
    assert fetch_json_with_429_retry(Request("https://example.com"), 3) == {"articles": []}
    assert len(calls) == 4
    assert delays == [8.0, 16.0, 30.0]


def test_link_release_uses_citable_official_url(tmp_path):
    from tools.government_releases import connect as connect_government
    from tools.government_release_corpus import upsert_release

    gov_path = tmp_path / "government.db"
    gov = connect_government(gov_path)
    release_id, _ = upsert_release(gov, {
        "agency": "SEC", "native_id": "2026-1", "release_number": "2026-1",
        "title": "SEC primary release", "canonical_url": "https://www.sec.gov/newsroom/press-releases/2026-1-example",
        "published_at": "2026-01-01", "content_text": "Official quoted support.",
    })
    gov.commit()

    reporting_path = tmp_path / "reporting.db"
    db = connect(reporting_path)
    item_id, _, _ = ingest_record(
        db, {"title": "Reporting", "canonical_url": "https://example.com/reporting"},
        discovery_method="test",
    )
    claim_id = db.execute(
        "INSERT INTO reporting_claim(item_id,claim_text) VALUES(?,?)",
        (item_id, "Attributed claim"),
    ).lastrowid
    db.commit()
    cmd_link_release(argparse.Namespace(
        db=reporting_path, releases_db=gov_path, claim_id=claim_id,
        identifier=str(release_id), quote="Official quoted support.", page=None,
        assessment="Direct support",
    ))
    source = db.execute("SELECT * FROM claim_source WHERE claim_id=?", (claim_id,)).fetchone()
    assert source["source_ref"] == "https://www.sec.gov/newsroom/press-releases/2026-1-example"
    assert source["source_description"].startswith("SEC-PR:2026-1 |")
    assert source["is_primary"] == 1
