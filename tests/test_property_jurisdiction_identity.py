"""County aliases must preserve geographic identity before any database write."""
import pytest

from tools.ingest_property_records import PropertyIngestError, _upsert_jurisdiction
from tools.public_records_store import connect_property


@pytest.mark.parametrize("jurisdiction", [
    {"county_geoid": "53001", "county_fips": "001", "state_fips": "53"},
    {"county_geoid": "53001", "county_fips": "001"},
    {"county_fips": "001", "state_fips": "53"},
    {"county_geoid": "53001", "county_fips": "53001", "state_fips": "53"},
    {"county_fips": "53001"},
    {"county_geoid": "53001"},
])
def test_county_components_and_full_aliases_preserve_one_identity(tmp_path, jurisdiction):
    db = connect_property(tmp_path / "property.db")
    try:
        record = {"jurisdiction": {**jurisdiction, "county_name": "Adams", "state_code": "WA"}}
        assert _upsert_jurisdiction(db, record) == "53001"
        assert _upsert_jurisdiction(db, record) == "53001"
        rows = db.execute("SELECT geoid, name FROM jurisdiction ORDER BY geoid").fetchall()
        assert [tuple(row) for row in rows] == [("53", "Washington"), ("53001", "Adams County")]
    finally:
        db.close()


@pytest.mark.parametrize("jurisdiction", [
    {"county_geoid": "53001", "county_fips": "003", "state_fips": "53"},
    {"county_geoid": "53001", "county_fips": "41001"},
    {"county_geoid": "53001", "county_fips": "001", "state_fips": "41"},
    {"county_fips": "53001", "state_fips": "41"},
    {"county_fips": "001"},
    {"county_fips": "001", "state_fips": "5"},
    {"county_fips": "bad", "state_fips": "53"},
])
def test_conflicting_or_unscoped_county_aliases_make_no_writes(tmp_path, jurisdiction):
    db = connect_property(tmp_path / "property.db")
    try:
        before = [tuple(row) for row in db.execute("SELECT * FROM jurisdiction")]
        with pytest.raises(PropertyIngestError):
            _upsert_jurisdiction(db, {"jurisdiction": jurisdiction})
        assert [tuple(row) for row in db.execute("SELECT * FROM jurisdiction")] == before
    finally:
        db.close()
