"""Offline CLI discovery must not run tool imports or source health probes."""
from pathlib import Path

from tools.tool_catalog import catalog, declarations


def test_catalog_reuses_inventory_and_docs_without_importing(tmp_path: Path):
    (tmp_path / 'tools').mkdir()
    (tmp_path / 'docs/modules').mkdir(parents=True)
    marker = tmp_path / 'import-ran'
    (tmp_path / 'tools/query_example.py').write_text(f'''"""Find example court records."""
from pathlib import Path
Path({str(marker)!r}).touch()
import argparse

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=20)
    parser.parse_args()

if __name__ == "__main__":
    main()
''')
    (tmp_path / 'tools/source_report.py').write_text('sources["Example Court"] = {"query_tool": "tools/query_example.py", **run_live_probe()}\n')
    (tmp_path / 'docs/modules/legal.md').write_text('# Legal\n## Example court\nUse `query_example.py` for court records.\n')
    entries = catalog(tmp_path)
    assert len(entries) == 1
    assert entries[0]['domains'] == ['legal']
    assert entries[0]['sources'] == ['Example Court']
    assert entries[0]['documentation'][0]['section'] == 'Example court'
    schema = declarations(tmp_path / 'tools/query_example.py', 'search')
    assert any(item['names'] == ['--limit'] for item in schema['commands'][0]['arguments'])
    assert not marker.exists()
