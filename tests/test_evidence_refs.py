import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "site" / "pipeline" / "evidence_refs.py"
SPEC = importlib.util.spec_from_file_location("evidence_refs", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)

canonicalize_evidence_ref = MODULE.canonicalize_evidence_ref
canonicalize_evidence_rows = MODULE.canonicalize_evidence_rows


class EvidenceRefCanonicalizationTests(unittest.TestCase):
    def test_splits_and_normalizes_mixed_ref_string(self):
        value = "NY SoS DOS ID 3714818; DS10 EFTA01285128/EFTA01285681/EFTA01287118/EFTA00130951"
        self.assertEqual(
            canonicalize_evidence_ref(value),
            [
                "NY-SoS:3714818",
                "DS10",
                "EFTA01285128",
                "EFTA01285681",
                "EFTA01287118",
                "EFTA00130951",
            ],
        )

    def test_normalizes_registry_and_fec_tokens(self):
        value = "FL_SunBiz F08000003048, FEC:C00384123-2003"
        self.assertEqual(
            canonicalize_evidence_ref(value),
            ["FL-SunBiz:F08000003048", "FEC:C00384123-2003"],
        )

    def test_expands_rows_and_dedupes(self):
        rows = [
            {
                "evidence_type": "ref",
                "evidence_ref": "EFTA02397051,EFTA01885793",
                "source_quote": "quote",
                "source_page": "p1",
                "assessment": "assessment",
            },
            {
                "evidence_type": "ref",
                "evidence_ref": "EFTA02397051",
                "source_quote": "quote",
                "source_page": "p1",
                "assessment": "assessment",
            },
        ]

        expanded = canonicalize_evidence_rows(rows)
        refs = [row["evidence_ref"] for row in expanded]
        self.assertEqual(refs, ["EFTA02397051", "EFTA01885793"])

    def test_normalizes_non_accession_sec_refs_to_search_url(self):
        value = "SEC:901359:Form4:2021-07-20"
        self.assertEqual(
            canonicalize_evidence_ref(value),
            ["https://www.sec.gov/edgar/search/#/q=CIK+901359+Form4+2021-07-20"],
        )


if __name__ == "__main__":
    unittest.main()
