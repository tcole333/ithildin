import json
import subprocess
from pathlib import Path

import pytest

from pipeline import compute_backlinks, export_preview_index, export_search_index
from pipeline.article_metadata import load_article


def test_all_indexes_use_filename_routes_and_full_yaml(tmp_path, monkeypatch):
    directory = tmp_path / "articles"
    directory.mkdir()
    article = directory / "actual-route.mdx"
    article.write_text('---\ntitle: "Title: with colon"\nsubtitle: >-\n  First line\n  second line\ncluster: different-cluster\ntargets:\n  - Example Person\n---\nA short body.\n')
    expected = load_article(article)
    assert expected["title"] == "Title: with colon"
    assert expected["subtitle"] == "First line second line"
    assert expected["targets"] == ["Example Person"]
    assert expected["wordCount"] == 3
    monkeypatch.setattr(export_search_index, "CONTENT_DIR", tmp_path)
    monkeypatch.setattr(export_preview_index, "CONTENT_DIR", tmp_path)
    monkeypatch.setattr(compute_backlinks, "ARTICLES_DIR", directory)
    search = export_search_index.export_articles()[0]
    preview = {}
    export_preview_index.export_articles(preview)
    assert search["href"] == "/articles/actual-route"
    assert preview["articles/actual-route"]["title"] == expected["title"]
    assert compute_backlinks.load_articles() == [expected]
    # The web adapter calls exactly this JSON boundary, not another YAML parser.
    import sys
    output = subprocess.check_output([sys.executable, "pipeline/article_metadata.py", "--articles-dir", str(directory)], cwd=Path(__file__).parents[1])
    assert json.loads(output) == [expected]


@pytest.mark.parametrize("metadata", ['title: []', 'title: Name\ntargets: [5]', '[]', 'title: false', 'subtitle: Missing title'])
def test_invalid_frontmatter_fails_with_source_path(tmp_path, metadata):
    article = tmp_path / "example.mdx"
    article.write_text(f"---\n{metadata}\n---\nBody")
    with pytest.raises(ValueError, match="example.mdx"):
        load_article(article)


def test_crlf_and_quoted_delimiters_do_not_truncate_frontmatter(tmp_path):
    article = tmp_path / "example.mdx"
    article.write_bytes(b'---\r\ntitle: "Before --- after"\r\ntargets: "One, Two"\r\n---\r\nBody')
    assert load_article(article)["title"] == "Before --- after"
    assert load_article(article)["targets"] == ["One", "Two"]
