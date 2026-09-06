"""Explicit jurisdiction/identifier evidence must survive every matching path."""

import pytest

from tools import lead_tracker
from tools.entity_resolution import EntityResolutionAmbiguity, resolve_or_create_entity


@pytest.fixture
def entities(tmp_path, monkeypatch):
    monkeypatch.setattr(lead_tracker, "DB_PATH", tmp_path / "entities.db")
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    db = lead_tracker.get_db()
    yield db
    db.close()


def seed_alias(db):
    original = resolve_or_create_entity(db, "Example Holdings LLC", entity_type="llc", jurisdiction="Delaware", ein="11-1111111")
    variant = resolve_or_create_entity(db, "Example  Holdings LLC", entity_type="llc", jurisdiction="Delaware", ein="11-1111111")
    assert variant.action == "fuzzy" and variant.entity_id == original.entity_id
    return original.entity_id


@pytest.mark.parametrize("backfill", [True, False])
def test_alias_does_not_override_conflicting_jurisdiction_or_ein(entities, backfill):
    original_id = seed_alias(entities)
    florida = resolve_or_create_entity(entities, "Example  Holdings LLC", entity_type="llc", jurisdiction="Florida", ein="22-2222222", backfill=backfill)
    assert florida.entity_id != original_id
    assert tuple(entities.execute("SELECT jurisdiction,ein FROM entities WHERE id=?", (florida.entity_id,)).fetchone()) == ("Florida", "22-2222222")
    assert tuple(entities.execute("SELECT jurisdiction,ein FROM entities WHERE id=?", (original_id,)).fetchone()) == ("Delaware", "11-1111111")


def test_alias_ein_guard_applies_even_without_jurisdiction(entities):
    original_id = seed_alias(entities)
    separate = resolve_or_create_entity(entities, "Example  Holdings LLC", entity_type="llc", ein="22-2222222")
    assert separate.entity_id != original_id


def test_exact_identity_conflict_requires_review(entities):
    original_id = seed_alias(entities)
    with pytest.raises(EntityResolutionAmbiguity, match="conflicts"):
        resolve_or_create_entity(entities, "Example Holdings LLC", entity_type="llc", jurisdiction="Delaware", ein="22-2222222")
    assert entities.execute("SELECT ein FROM entities WHERE id=?", (original_id,)).fetchone()[0] == "11-1111111"


def test_compatible_ein_punctuation_still_resolves_alias(entities):
    original_id = seed_alias(entities)
    match = resolve_or_create_entity(entities, "Example  Holdings LLC", entity_type="llc", jurisdiction="Delaware", ein="111111111")
    assert match.entity_id == original_id and match.action == "alias"


def test_person_alias_cannot_swallow_an_organization(entities):
    person = resolve_or_create_entity(entities, "Alex Example", entity_type="person")
    entities.execute("INSERT INTO name_aliases(canonical_name,alias,alias_type,entity_id) VALUES ('Alex Example','Example Group','person_variant',?)", (person.entity_id,))
    organization = resolve_or_create_entity(entities, "Example Group", entity_type="corporation")
    assert organization.entity_id != person.entity_id
    assert entities.execute("SELECT entity_type FROM entities WHERE id=?", (organization.entity_id,)).fetchone()[0] == "corporation"
