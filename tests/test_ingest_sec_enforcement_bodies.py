"""Offline tests for SEC enforcement release-body retrieval.

The original ingester was index-only: it stored respondent/release/date/URL and
left `body_text` NULL on all 37,592 rows, which made statutory-conduct
classification impossible. These tests cover the body-fetch pass that closes
that gap, and pin the corpus rule that agency posture language
(alleged / charged / settled / convicted) is stored verbatim.
"""

from __future__ import annotations

from urllib.error import HTTPError

import pytest

from tools import ingest_sec_enforcement as ing

# ── Fixtures ─────────────────────────────────────────────────

ALLEGATION_TEXT = (
    "The SEC's complaint alleges that Doe violated Section 10(b) of the "
    "Exchange Act and Rule 10b-5 thereunder. Doe consented to the entry of a "
    "final judgment without admitting or denying the allegations. A parallel "
    "criminal case charged Doe, who later pleaded guilty and was convicted."
)


def _page(body_html: str) -> str:
    return (
        "<!DOCTYPE html><html><head><title>t</title></head><body>"
        "<nav>Menu</nav><p>Skip to main content</p>"
        f'<div class="field field--name-body field--type-text">{body_html}</div>'
        "<footer>Return to top</footer></body></html>"
    )


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A fresh sec_enforcement DB carrying the body-provenance migration."""
    monkeypatch.setattr(ing, "DB_PATH", tmp_path / "sec.db")
    connection = ing.get_db()
    yield connection
    connection.close()


def _insert(db, release_number, url, date="2023-05-16", source_type="admin"):
    db.execute(
        """INSERT INTO enforcement_actions
           (release_number, source_type, date_published, respondent_text, release_url)
           VALUES (?, ?, ?, ?, ?)""",
        (release_number, source_type, date, "Doe", url),
    )
    db.commit()


# ── Schema migration ─────────────────────────────────────────


class TestMigration:
    def test_body_provenance_columns_exist(self, db):
        cols = {row[1] for row in db.execute("PRAGMA table_info(enforcement_actions)")}
        assert set(ing.BODY_COLUMNS) <= cols

    def test_migration_is_idempotent(self, db, monkeypatch, tmp_path):
        monkeypatch.setattr(ing, "DB_PATH", tmp_path / "sec.db")
        again = ing.get_db()
        cols = {row[1] for row in again.execute("PRAGMA table_info(enforcement_actions)")}
        assert set(ing.BODY_COLUMNS) <= cols
        again.close()


# ── Extraction ───────────────────────────────────────────────


class TestBoilerplate:
    def test_removes_whole_line_navigation(self):
        text = "Menu\nHome\nUNITED STATES OF AMERICA\n|\nReturn to top"
        assert ing._drop_boilerplate(text) == "UNITED STATES OF AMERICA"

    def test_preserves_posture_wording(self):
        assert ing._drop_boilerplate(ALLEGATION_TEXT) == ALLEGATION_TEXT

    def test_does_not_strip_content_containing_a_nav_word(self):
        line = "Doe was ordered to return home to the district."
        assert ing._drop_boilerplate(line) == line


class TestExtractHtmlBody:
    def test_prefers_drupal_body_field(self):
        body, method = ing.extract_html_body(_page(f"<p>{ALLEGATION_TEXT}</p>"))
        assert method == "html:field-body"
        assert "Rule 10b-5" in body
        assert "Menu" not in body

    def test_legacy_text_markers(self):
        page = (
            "<html><body>chrome<!-- BEGIN TEXT -->"
            f"<p>{ALLEGATION_TEXT}</p><!-- END TEXT -->more chrome</body></html>"
        )
        body, method = ing.extract_html_body(page)
        assert method == "html:text-markers"
        assert "pleaded guilty" in body
        assert "chrome" not in body

    def test_full_page_fallback(self):
        page = f"<html><body><p>{ALLEGATION_TEXT}</p></body></html>"
        body, method = ing.extract_html_body(page)
        assert method == "html:full-page"
        assert "Section 10(b)" in body


class TestDeriveOrderPdfUrl:
    def test_uses_url_slug_not_release_number(self):
        url = ing.derive_order_pdf_url(
            "https://www.sec.gov/enforcement-litigation/administrative-proceedings/34-97381",
            "2023-04-26",
        )
        assert url == "https://www.sec.gov/files/litigation/admin/2023/34-97381.pdf"

    def test_lowercases_slug(self):
        url = ing.derive_order_pdf_url(
            "https://www.sec.gov/enforcement-litigation/administrative-proceedings/33-11184",
            "2023-05-16",
        )
        assert url.endswith("/2023/33-11184.pdf")

    def test_returns_none_for_file_urls(self):
        assert (
            ing.derive_order_pdf_url(
                "https://www.sec.gov/files/litigation/admin/2021/34-93882.pdf",
                "2021-12-30",
            )
            is None
        )

    def test_returns_none_without_a_year(self):
        url = "https://www.sec.gov/enforcement-litigation/administrative-proceedings/34-97381"
        assert ing.derive_order_pdf_url(url, None) is None


# ── resolve_body dispatch ────────────────────────────────────


class TestResolveBody:
    def test_plain_text_is_stored_verbatim(self, monkeypatch):
        payload = (ALLEGATION_TEXT + "\n") * 3
        monkeypatch.setattr(
            ing, "_fetch_raw", lambda *a, **k: ("text/plain", payload.encode())
        )
        body, method, source = ing.resolve_body(
            "https://www.sec.gov/files/litigation/litreleases/lr16154.txt", "1999-05-19"
        )
        assert method == "text:verbatim"
        assert body == payload.strip()
        assert source.endswith("lr16154.txt")

    def test_pdf_payload_uses_pdf_extractor(self, monkeypatch):
        monkeypatch.setattr(
            ing, "_fetch_raw", lambda *a, **k: ("application/pdf", b"%PDF-1.6 fake")
        )
        monkeypatch.setattr(
            ing, "_extract_pdf_text", lambda raw: (ALLEGATION_TEXT, "pdftotext")
        )
        body, method, source = ing.resolve_body(
            "https://www.sec.gov/files/litigation/admin/2021/34-93882.pdf", "2021-12-30"
        )
        assert method == "pdf:pdftotext"
        assert body == ALLEGATION_TEXT
        assert source.endswith("34-93882.pdf")

    def test_html_release_page(self, monkeypatch):
        page = _page(f"<p>{ALLEGATION_TEXT}</p>")
        monkeypatch.setattr(
            ing, "_fetch_raw", lambda *a, **k: ("text/html", page.encode())
        )
        body, method, _ = ing.resolve_body(
            "https://www.sec.gov/enforcement-litigation/litigation-releases/lr-26503",
            "2026-03-18",
        )
        assert method == "html:field-body"
        assert "without admitting or denying" in body

    def test_modern_stub_falls_back_to_derived_order_pdf(self, monkeypatch):
        stub = (
            "<!DOCTYPE html><html><body><h1>DNA Brands, Inc.</h1>"
            "<p>Menu</p><p>Return to top</p></body></html>"
        )
        calls = []

        def fake_fetch(url, timeout=45, retries=3):
            calls.append(url)
            if url.endswith(".pdf"):
                return "application/pdf", b"%PDF-1.6 fake"
            return "text/html", stub.encode()

        monkeypatch.setattr(ing, "_fetch_raw", fake_fetch)
        monkeypatch.setattr(
            ing, "_extract_pdf_text", lambda raw: (ALLEGATION_TEXT, "pdftotext")
        )
        body, method, source = ing.resolve_body(
            "https://www.sec.gov/enforcement-litigation/administrative-proceedings/33-11184",
            "2023-05-16",
        )
        assert method == "pdf:pdftotext"
        assert source == "https://www.sec.gov/files/litigation/admin/2023/33-11184.pdf"
        assert calls[-1] == source
        assert "Rule 10b-5" in body

    def test_stub_without_a_reachable_pdf_is_body_unavailable(self, monkeypatch):
        stub = "<!DOCTYPE html><html><body><h1>Doe</h1><p>Menu</p></body></html>"

        def fake_fetch(url, timeout=45, retries=3):
            if url.endswith(".pdf"):
                raise HTTPError(url, 404, "Not Found", {}, None)
            return "text/html", stub.encode()

        monkeypatch.setattr(ing, "_fetch_raw", fake_fetch)
        with pytest.raises(ing.BodyUnavailable, match="derived fallbacks exhausted"):
            ing.resolve_body(
                "https://www.sec.gov/enforcement-litigation/administrative-proceedings/34-1",
                "2023-04-26",
            )

    def test_header_only_litigation_page_falls_back_to_legacy_static_release(
        self, monkeypatch
    ):
        """Some modern litigation pages publish only the release header.

        The body container exists but holds two lines, so a container-present
        check is not enough to accept it; the legacy static file has the text.
        """
        header_only = _page(
            "<p>U.S. SECURITIES AND EXCHANGE COMMISSION</p>"
            "<p>Litigation Release No. 23328 / August 25, 2015</p>"
        )
        legacy = (
            "<html><body><p>Home</p><p>|</p><p>Previous Page</p>"
            f"<p>{ALLEGATION_TEXT}</p></body></html>"
        )
        calls = []

        def fake_fetch(url, timeout=45, retries=3):
            calls.append(url)
            if url.endswith(".htm"):
                return "text/html", legacy.encode()
            return "text/html", header_only.encode()

        monkeypatch.setattr(ing, "_fetch_raw", fake_fetch)
        body, _, source = ing.resolve_body(
            "https://www.sec.gov/enforcement-litigation/litigation-releases/lr-23328",
            "2015-08-25",
        )
        assert source == (
            "https://www.sec.gov/files/litigation/litreleases/2015/lr23328.htm"
        )
        assert "Rule 10b-5" in body
        assert "Previous Page" not in body
        # The admin PDF convention must not be tried for a litigation release.
        assert not any(".pdf" in url for url in calls)

    def test_litigation_release_never_derives_an_admin_pdf(self):
        url = "https://www.sec.gov/enforcement-litigation/litigation-releases/lr-23328"
        assert ing.derive_order_pdf_url(url, "2015-08-25") is None
        candidates = ing.derived_body_urls(url, "2015-08-25")
        assert candidates[0] == (
            "https://www.sec.gov/files/litigation/litreleases/2015/lr23328.htm"
        )
        assert not any("/admin/" in candidate for candidate in candidates)

    def test_admin_stub_never_derives_a_legacy_litrelease(self):
        url = "https://www.sec.gov/enforcement-litigation/administrative-proceedings/33-11184"
        assert ing.derive_legacy_litrelease_url(url, "2023-05-16") is None
        candidates = ing.derived_body_urls(url, "2023-05-16")
        assert candidates[0] == (
            "https://www.sec.gov/files/litigation/admin/2023/33-11184.pdf"
        )
        assert not any("/litreleases/" in candidate for candidate in candidates)

    def test_image_only_pdf_is_body_unavailable(self, monkeypatch):
        monkeypatch.setattr(
            ing, "_fetch_raw", lambda *a, **k: ("application/pdf", b"%PDF-1.6 fake")
        )
        monkeypatch.setattr(ing, "_extract_pdf_text", lambda raw: ("", "pdftotext"))
        with pytest.raises(ing.BodyUnavailable, match="image-only scan"):
            ing.resolve_body(
                "https://www.sec.gov/files/litigation/admin/2021/34-1.pdf", "2021-01-01"
            )

    def test_transport_error_is_not_body_unavailable(self, monkeypatch):
        def fake_fetch(url, timeout=45, retries=3):
            raise HTTPError(url, 500, "Server Error", {}, None)

        monkeypatch.setattr(ing, "_fetch_raw", fake_fetch)
        with pytest.raises(HTTPError):
            ing.resolve_body("https://www.sec.gov/files/x.pdf", "2021-01-01")


# ── fetch_bodies ─────────────────────────────────────────────


class TestFetchBodies:
    def test_stores_body_status_and_provenance(self, db, monkeypatch):
        _insert(db, "LR-100", "https://www.sec.gov/files/litigation/litreleases/lr100.txt")
        payload = (ALLEGATION_TEXT + "\n") * 3
        monkeypatch.setattr(
            ing, "_fetch_raw", lambda *a, **k: ("text/plain", payload.encode())
        )

        completed, failed = ing.fetch_bodies(db, workers=1)
        assert (completed, failed) == (1, 0)

        row = db.execute(
            """SELECT body_text, body_fetch_status, body_fetch_error,
                      body_source_url, body_extraction_method, body_fetched_at
               FROM enforcement_actions WHERE release_number = 'LR-100'"""
        ).fetchone()
        assert row["body_fetch_status"] == "complete"
        assert row["body_fetch_error"] is None
        assert row["body_extraction_method"] == "text:verbatim"
        assert row["body_source_url"].endswith("lr100.txt")
        assert row["body_fetched_at"]
        assert "Rule 10b-5" in row["body_text"]

    def test_posture_language_survives_the_round_trip(self, db, monkeypatch):
        _insert(db, "LR-101", "https://www.sec.gov/files/litigation/litreleases/lr101.txt")
        payload = (ALLEGATION_TEXT + "\n") * 3
        monkeypatch.setattr(
            ing, "_fetch_raw", lambda *a, **k: ("text/plain", payload.encode())
        )
        ing.fetch_bodies(db, workers=1)

        stored = db.execute(
            "SELECT body_text FROM enforcement_actions WHERE release_number = 'LR-101'"
        ).fetchone()["body_text"]
        for phrase in (
            "complaint alleges",
            "consented to the entry",
            "without admitting or denying",
            "charged Doe",
            "pleaded guilty",
            "was convicted",
        ):
            assert phrase in stored, phrase

    def test_one_document_writes_every_row_that_cites_it(self, db, monkeypatch):
        shared = "https://www.sec.gov/enforcement-litigation/administrative-proceedings/34-97381"
        _insert(db, "34-97381", shared, source_type="admin")
        _insert(db, "AAER-4403", shared, source_type="aaer")

        calls = []

        def fake_fetch(url, timeout=45, retries=3):
            calls.append(url)
            if url.endswith(".pdf"):
                return "application/pdf", b"%PDF-1.6 fake"
            return "text/html", _page(f"<p>{ALLEGATION_TEXT}</p>").encode()

        monkeypatch.setattr(ing, "_fetch_raw", fake_fetch)
        completed, failed = ing.fetch_bodies(db, workers=1)

        assert (completed, failed) == (2, 0)
        assert len(calls) == 1, "a shared document must be fetched once"
        bodies = [
            r["body_text"]
            for r in db.execute("SELECT body_text FROM enforcement_actions")
        ]
        assert len(bodies) == 2
        assert all("Rule 10b-5" in b for b in bodies)

    def test_unavailable_body_is_recorded_as_empty_not_failed(self, db, monkeypatch):
        _insert(db, "34-1", "https://www.sec.gov/files/litigation/admin/2023/34-1.pdf")
        monkeypatch.setattr(
            ing, "_fetch_raw", lambda *a, **k: ("application/pdf", b"%PDF-1.6 fake")
        )
        monkeypatch.setattr(ing, "_extract_pdf_text", lambda raw: ("", "pdftotext"))

        completed, failed = ing.fetch_bodies(db, workers=1)
        assert (completed, failed) == (0, 1)
        row = db.execute(
            "SELECT body_text, body_fetch_status, body_fetch_error FROM enforcement_actions"
        ).fetchone()
        assert row["body_fetch_status"] == "empty"
        assert row["body_text"] is None, "chrome or empty text must never be stored"
        assert "image-only scan" in row["body_fetch_error"]

    def test_transport_failure_is_recorded_as_failed(self, db, monkeypatch):
        _insert(db, "34-2", "https://www.sec.gov/files/litigation/admin/2023/34-2.pdf")

        def fake_fetch(url, timeout=45, retries=3):
            raise HTTPError(url, 500, "Server Error", {}, None)

        monkeypatch.setattr(ing, "_fetch_raw", fake_fetch)
        ing.fetch_bodies(db, workers=1)
        row = db.execute(
            "SELECT body_fetch_status, body_fetch_error FROM enforcement_actions"
        ).fetchone()
        assert row["body_fetch_status"] == "failed"
        assert "500" in row["body_fetch_error"]

    def test_completed_rows_are_not_refetched(self, db, monkeypatch):
        _insert(db, "LR-102", "https://www.sec.gov/files/litigation/litreleases/lr102.txt")
        payload = (ALLEGATION_TEXT + "\n") * 3
        calls = []

        def fake_fetch(url, timeout=45, retries=3):
            calls.append(url)
            return "text/plain", payload.encode()

        monkeypatch.setattr(ing, "_fetch_raw", fake_fetch)
        ing.fetch_bodies(db, workers=1)
        ing.fetch_bodies(db, workers=1)
        assert len(calls) == 1, "fetch-bodies must be resumable, not repeat work"

    def test_failed_rows_are_only_retried_on_request(self, db, monkeypatch):
        _insert(db, "34-3", "https://www.sec.gov/files/litigation/admin/2023/34-3.pdf")
        calls = []

        def failing(url, timeout=45, retries=3):
            calls.append(url)
            raise HTTPError(url, 500, "Server Error", {}, None)

        monkeypatch.setattr(ing, "_fetch_raw", failing)
        ing.fetch_bodies(db, workers=1)
        ing.fetch_bodies(db, workers=1)
        assert len(calls) == 1

        ing.fetch_bodies(db, workers=1, retry_failed=True)
        assert len(calls) == 2

    def test_date_window_filters_rows(self, db, monkeypatch):
        _insert(db, "LR-200", "https://www.sec.gov/a.txt", date="2019-01-01")
        _insert(db, "LR-201", "https://www.sec.gov/b.txt", date="2023-01-01")
        payload = (ALLEGATION_TEXT + "\n") * 3
        monkeypatch.setattr(
            ing, "_fetch_raw", lambda *a, **k: ("text/plain", payload.encode())
        )

        ing.fetch_bodies(db, start="2021-01-01", end="2025-12-31", workers=1)
        rows = dict(
            db.execute(
                "SELECT release_number, body_fetch_status FROM enforcement_actions"
            ).fetchall()
        )
        assert rows["LR-201"] == "complete"
        assert rows["LR-200"] is None

    def test_body_text_becomes_fts_searchable(self, db, monkeypatch):
        _insert(db, "LR-300", "https://www.sec.gov/files/litigation/litreleases/lr300.txt")
        payload = (ALLEGATION_TEXT + "\n") * 3
        monkeypatch.setattr(
            ing, "_fetch_raw", lambda *a, **k: ("text/plain", payload.encode())
        )
        ing.fetch_bodies(db, workers=1)

        hits = db.execute(
            "SELECT COUNT(*) FROM enforcement_actions_fts "
            "WHERE enforcement_actions_fts MATCH ?",
            ('"10b-5"',),
        ).fetchone()[0]
        assert hits == 1, "conduct classification depends on FTS seeing body text"

        db.execute("INSERT INTO enforcement_actions_fts(enforcement_actions_fts) VALUES('integrity-check')")


# ── stats ────────────────────────────────────────────────────


class TestStatsCoverage:
    def test_stats_reports_body_coverage(self, db, monkeypatch, capsys):
        _insert(db, "LR-400", "https://www.sec.gov/files/litigation/litreleases/lr400.txt")
        _insert(db, "LR-401", "https://www.sec.gov/files/litigation/litreleases/lr401.txt")

        class Args:
            output = None
            output_format = "json"

        ing.show_stats(db, Args())
        printed = capsys.readouterr().out
        assert "Bodies fetched:    0/2 (0.0%)" in printed
        assert "pending" in printed


class TestEraConventions:
    """Static-file paths changed around 2005: per-year directory, then year-less.

    All 15 documents that survived the first full backfill as `empty` were
    pre-2005 pages whose body container held only the release header.
    """

    def test_litigation_ladder_covers_both_eras(self):
        urls = ing.derived_body_urls(
            "https://www.sec.gov/enforcement-litigation/litigation-releases/lr-18775",
            "2004-07-06",
        )
        assert urls == [
            "https://www.sec.gov/files/litigation/litreleases/2004/lr18775.htm",
            "https://www.sec.gov/files/litigation/litreleases/lr18775.htm",
            "https://www.sec.gov/files/litigation/litreleases/lr18775.txt",
        ]

    def test_admin_ladder_covers_both_eras(self):
        urls = ing.derived_body_urls(
            "https://www.sec.gov/enforcement-litigation/administrative-proceedings/34-50429",
            "2004-09-23",
        )
        assert urls == [
            "https://www.sec.gov/files/litigation/admin/2004/34-50429.pdf",
            "https://www.sec.gov/files/litigation/admin/34-50429.htm",
            "https://www.sec.gov/files/litigation/admin/34-50429.txt",
        ]

    def test_ladders_never_cross_families(self):
        lit = ing.derived_body_urls(
            "https://www.sec.gov/enforcement-litigation/litigation-releases/lr-18775",
            "2004-07-06",
        )
        adm = ing.derived_body_urls(
            "https://www.sec.gov/enforcement-litigation/administrative-proceedings/34-50429",
            "2004-09-23",
        )
        assert not any("/admin/" in u for u in lit)
        assert not any("/litreleases/" in u for u in adm)

    def test_header_only_page_walks_to_the_year_less_file(self, monkeypatch):
        header_only = _page("<p>Litigation Release No. 18775 / July 6, 2004</p>")
        legacy = f"<html><body><p>Home</p><p>{ALLEGATION_TEXT}</p></body></html>"
        calls = []

        def fake_fetch(url, timeout=45, retries=3):
            calls.append(url)
            if url == "https://www.sec.gov/files/litigation/litreleases/lr18775.htm":
                return "text/html", legacy.encode()
            if url.startswith("https://www.sec.gov/files/"):
                raise HTTPError(url, 404, "Not Found", {}, None)
            return "text/html", header_only.encode()

        monkeypatch.setattr(ing, "_fetch_raw", fake_fetch)
        body, _, source = ing.resolve_body(
            "https://www.sec.gov/enforcement-litigation/litigation-releases/lr-18775",
            "2004-07-06",
        )
        assert source == "https://www.sec.gov/files/litigation/litreleases/lr18775.htm"
        assert "Rule 10b-5" in body
        # The dated convention is tried first, then abandoned on 404.
        assert calls[1].endswith("/2004/lr18775.htm")
