"""
Entity resolution with confidence scoring for the Data Source Integrator.

Resolves extracted entity names to existing entities in the research graph
using multiple matching strategies with configurable thresholds.
"""

import hashlib
import logging
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

from .models import (
    EntityType,
    ExtractedEntity,
    MatchCandidate,
    MatchResult,
    MatchStatus,
)
from .neo4j_loader import SECNeo4jLoader

logger = logging.getLogger(__name__)


# Decision thresholds (from METHODOLOGY.md)
THRESHOLD_AUTO = 0.85      # Auto-match, no review needed
THRESHOLD_REVIEW = 0.50    # Create link but flag for review
THRESHOLD_NEW = 0.30       # Below this, likely new entity

# Scoring weights for match factors
WEIGHTS = {
    "identifier_match": 1.0,      # CUSIP, CIK, EIN match
    "exact_name": 1.0,            # Exact normalized name match
    "alias_match": 0.9,           # Known alias match
    "partial_name_3plus": 0.7,    # 3+ significant words match
    "partial_name_2": 0.5,        # 2 significant words match
    "name_similarity_high": 0.8,  # Levenshtein > 0.9
    "name_similarity_med": 0.6,   # Levenshtein 0.85-0.9
    "address_match": 0.3,         # Same address (additive)
    "shared_relationship": 0.2,   # Common connections (additive per connection)
    "same_jurisdiction": 0.1,     # For companies
}


@dataclass
class MatchFactor:
    """A factor contributing to match confidence."""
    name: str
    value: float
    description: str


class EntityResolver:
    """
    Resolves extracted entity names to existing entities in Neo4j.

    Uses multiple matching strategies:
    1. Identifier matching (CUSIP, CIK, EIN) - highest confidence
    2. Known alias matching from EntityAlias nodes
    3. Exact normalized name matching
    4. Fuzzy matching with token overlap and string similarity

    Example:
        resolver = EntityResolver(loader)
        result = resolver.resolve(ExtractedEntity(name="ACME CORP", entity_type=EntityType.COMPANY))
        if result.status == MatchStatus.AUTO_MATCHED:
            print(f"Matched to {result.matched_entity} with {result.confidence:.2f} confidence")
    """

    def __init__(
        self,
        loader: SECNeo4jLoader,
        auto_threshold: float = THRESHOLD_AUTO,
        review_threshold: float = THRESHOLD_REVIEW,
    ):
        """
        Initialize the resolver.

        Args:
            loader: SECNeo4jLoader instance for database queries
            auto_threshold: Minimum score for automatic matching
            review_threshold: Minimum score to flag for review (below creates new entity)
        """
        self.loader = loader
        self.auto_threshold = auto_threshold
        self.review_threshold = review_threshold

    def resolve(self, entity: ExtractedEntity) -> MatchResult:
        """
        Attempt to resolve an extracted entity to an existing node.

        Args:
            entity: ExtractedEntity with name and type

        Returns:
            MatchResult with status, matched entity, confidence, and factors
        """
        normalized = self.loader.normalize_name(entity.name)
        entity_type_str = entity.entity_type.value if entity.entity_type else "person"

        candidates: list[MatchCandidate] = []
        factors: list[MatchFactor] = []

        # Step 1: Check by identifier (highest confidence)
        if entity.identifiers:
            for id_type, id_value in entity.identifiers.items():
                id_matches = self.loader.find_by_identifier(id_value)
                for match in id_matches:
                    candidates.append(MatchCandidate(
                        name=match["entity_name"],
                        entity_type=EntityType(match["entity_type"].lower()) if match.get("entity_type") else entity.entity_type,
                        score=1.0,
                        method="identifier",
                        factors=[f"{id_type}={id_value}"],
                    ))
                    factors.append(MatchFactor("identifier_match", 1.0, f"Matched by {id_type}={id_value}"))

        # Step 2: Check known aliases
        alias_matches = self.loader.search_aliases(normalized, entity_type_str)
        for alias in alias_matches:
            if alias.get("canonical_name"):
                candidates.append(MatchCandidate(
                    name=alias["canonical_name"],
                    entity_type=EntityType(alias.get("type", entity_type_str)),
                    score=0.9,
                    method="alias",
                    factors=[f"alias: {alias.get('original', normalized)}"],
                ))

        # Step 3: Exact normalized name search
        exact_matches = self._find_exact_name(normalized, entity_type_str)
        for match in exact_matches:
            candidates.append(MatchCandidate(
                name=match["name"],
                entity_type=EntityType(entity_type_str),
                score=1.0,
                method="exact",
                factors=["exact_name_match"],
            ))

        # Step 4: Fuzzy name matching
        fuzzy_matches = self._find_similar_names(normalized, entity_type_str)
        for match_name, similarity in fuzzy_matches:
            match_factors = self._compute_match_factors(entity.name, match_name)
            score = self._compute_score(match_factors)
            candidates.append(MatchCandidate(
                name=match_name,
                entity_type=EntityType(entity_type_str),
                score=score,
                method="fuzzy",
                factors=[f.description for f in match_factors],
            ))

        # Select best candidate
        if not candidates:
            return MatchResult(
                extracted_name=entity.name,
                normalized_name=normalized,
                entity_type=entity.entity_type or EntityType.PERSON,
                status=MatchStatus.NEW_ENTITY,
                matched_entity=None,
                confidence=0.0,
                factors=["No matching entities found"],
                alternatives=[],
            )

        # Deduplicate candidates by name, keeping highest score
        unique_candidates = {}
        for c in candidates:
            if c.name not in unique_candidates or c.score > unique_candidates[c.name].score:
                unique_candidates[c.name] = c
        candidates = list(unique_candidates.values())

        # Sort by score descending
        candidates.sort(key=lambda c: c.score, reverse=True)
        best = candidates[0]

        # Determine status based on score
        if best.score >= self.auto_threshold:
            status = MatchStatus.AUTO_MATCHED
        elif best.score >= self.review_threshold:
            status = MatchStatus.NEEDS_REVIEW
        else:
            status = MatchStatus.NEW_ENTITY

        return MatchResult(
            extracted_name=entity.name,
            normalized_name=normalized,
            entity_type=entity.entity_type or EntityType.PERSON,
            status=status,
            matched_entity=best.name if status != MatchStatus.NEW_ENTITY else None,
            confidence=best.score,
            factors=best.factors,
            alternatives=candidates[1:4] if len(candidates) > 1 else [],  # Top 3 alternatives
        )

    def resolve_batch(self, entities: list[ExtractedEntity]) -> list[MatchResult]:
        """
        Resolve multiple entities.

        Args:
            entities: List of ExtractedEntity objects

        Returns:
            List of MatchResult objects
        """
        return [self.resolve(entity) for entity in entities]

    def generate_match_id(self, extracted_name: str, source_id: str) -> str:
        """
        Generate a unique match ID.

        Args:
            extracted_name: Name as extracted
            source_id: Source document ID

        Returns:
            Unique hash-based ID
        """
        content = f"{source_id}:{extracted_name}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _find_exact_name(self, normalized_name: str, entity_type: str) -> list[dict]:
        """
        Find entities with exact normalized name match.

        Args:
            normalized_name: Normalized name to search
            entity_type: Entity type filter

        Returns:
            List of matching entity dicts
        """
        with self.loader.driver.session() as session:
            label = {"person": "Person", "company": "Company", "organization": "Organization"}.get(entity_type, "Person")
            result = session.run(f"""
                MATCH (e:{label})
                WHERE toUpper(e.name) = $normalized_name
                   OR e.name = $normalized_name
                RETURN e.name AS name, labels(e)[0] AS type
                LIMIT 5
            """, normalized_name=normalized_name)
            return [dict(record) for record in result]

    def _find_similar_names(self, normalized_name: str, entity_type: str, limit: int = 20) -> list[tuple[str, float]]:
        """
        Find entities with similar names using token overlap.

        Args:
            normalized_name: Normalized name to search
            entity_type: Entity type filter
            limit: Maximum results

        Returns:
            List of (name, similarity_score) tuples
        """
        # Get tokens from normalized name
        tokens = normalized_name.split()
        if not tokens:
            return []

        # Search for entities containing any of the significant tokens
        significant_tokens = [t for t in tokens if len(t) >= 3]
        if not significant_tokens:
            return []

        with self.loader.driver.session() as session:
            label = {"person": "Person", "company": "Company", "organization": "Organization"}.get(entity_type, "Person")

            # Search for entities containing first significant token
            first_token = significant_tokens[0]
            result = session.run(f"""
                MATCH (e:{label})
                WHERE toUpper(e.name) CONTAINS $token
                RETURN e.name AS name
                LIMIT $limit
            """, token=first_token, limit=limit)

            candidates = []
            for record in result:
                name = record["name"]
                # Compute similarity
                similarity = SequenceMatcher(None, normalized_name, self.loader.normalize_name(name)).ratio()
                if similarity >= 0.5:  # Minimum threshold
                    candidates.append((name, similarity))

            # Sort by similarity
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[:10]

    def _compute_match_factors(self, extracted_name: str, candidate_name: str) -> list[MatchFactor]:
        """
        Compute all matching factors between extracted and candidate names.

        Args:
            extracted_name: Original extracted name
            candidate_name: Candidate entity name

        Returns:
            List of MatchFactor objects
        """
        factors = []

        norm_extracted = self.loader.normalize_name(extracted_name)
        norm_candidate = self.loader.normalize_name(candidate_name)

        # Token overlap analysis
        extracted_tokens = set(norm_extracted.split())
        candidate_tokens = set(norm_candidate.split())
        common_tokens = extracted_tokens & candidate_tokens

        if len(common_tokens) >= 3:
            factors.append(MatchFactor(
                "partial_name_3plus",
                WEIGHTS["partial_name_3plus"],
                f"{len(common_tokens)} common tokens: {', '.join(list(common_tokens)[:3])}",
            ))
        elif len(common_tokens) >= 2:
            factors.append(MatchFactor(
                "partial_name_2",
                WEIGHTS["partial_name_2"],
                f"2 common tokens: {', '.join(common_tokens)}",
            ))

        # String similarity
        similarity = SequenceMatcher(None, norm_extracted, norm_candidate).ratio()
        if similarity > 0.9:
            factors.append(MatchFactor(
                "name_similarity_high",
                WEIGHTS["name_similarity_high"] * similarity,
                f"High string similarity: {similarity:.2f}",
            ))
        elif similarity > 0.85:
            factors.append(MatchFactor(
                "name_similarity_med",
                WEIGHTS["name_similarity_med"] * similarity,
                f"Medium string similarity: {similarity:.2f}",
            ))

        return factors

    def _compute_score(self, factors: list[MatchFactor]) -> float:
        """
        Compute overall match score from factors.

        Args:
            factors: List of MatchFactor objects

        Returns:
            Overall score 0.0-1.0
        """
        if not factors:
            return 0.0

        # Take the maximum factor value (dominant match type)
        # Plus small bonuses for additional factors
        scores = sorted([f.value for f in factors], reverse=True)
        total = scores[0]  # Best factor
        for score in scores[1:]:
            total += score * 0.2  # 20% bonus for additional factors

        return min(1.0, total)


# Relationship type mapping for extracted predicates
RELATIONSHIP_MAPPING = {
    # Employment
    "employed": "EMPLOYED_BY",
    "employed by": "EMPLOYED_BY",
    "works for": "EMPLOYED_BY",
    "employee of": "EMPLOYED_BY",
    "worked for": "EMPLOYED_BY",
    "ceo of": ("OFFICER_OF", {"title": "CEO"}),
    "president of": ("OFFICER_OF", {"title": "President"}),
    "cfo of": ("OFFICER_OF", {"title": "CFO"}),
    "director of": "DIRECTOR_OF",
    "board member": "DIRECTOR_OF",
    "officer of": "OFFICER_OF",
    "founded": "FOUNDED",
    "founder of": "FOUNDED",

    # Legal
    "attorney for": "ATTORNEY_FOR",
    "counsel for": "ATTORNEY_FOR",
    "represents": "REPRESENTS",
    "represented by": "REPRESENTED_BY",
    "plaintiff in": ("PARTY_TO", {"role": "plaintiff"}),
    "defendant in": ("PARTY_TO", {"role": "defendant"}),
    "sued": "PARTY_TO",
    "creditor of": "CREDITOR_OF",
    "debtor of": "DEBTOR_OF",

    # Ownership
    "owns": "BENEFICIAL_OWNER",
    "owned by": "BENEFICIAL_OWNER",
    "shareholder of": "BENEFICIAL_OWNER",
    "beneficial owner of": "BENEFICIAL_OWNER",
    "subsidiary of": "SUBSIDIARY_OF",
    "parent of": "PARENT_OF",
    "acquired": "ACQUIRED_BY",
    "acquired by": "ACQUIRED_BY",
    "merged with": "MERGED_WITH",

    # Financial
    "sold to": "SOLD_TO",
    "purchased from": "PURCHASED_FROM",
    "borrowed from": "BORROWED_FROM",
    "lender to": "LENDER_TO",
    "guarantor for": "GUARANTOR_FOR",

    # Location
    "located at": "LOCATED_AT",
    "headquartered in": "LOCATED_AT",
    "registered at": "LOCATED_AT",

    # Generic (fallback)
    "associated with": "ASSOCIATED_WITH",
    "connected to": "ASSOCIATED_WITH",
    "related to": "ASSOCIATED_WITH",
    "affiliated with": "ASSOCIATED_WITH",
}


def map_relationship(predicate: str) -> tuple[str, dict]:
    """
    Map an extracted predicate to a schema relationship type.

    Args:
        predicate: Extracted relationship predicate

    Returns:
        Tuple of (relationship_type, properties_dict)
    """
    predicate_lower = predicate.lower().strip()

    if predicate_lower in RELATIONSHIP_MAPPING:
        mapping = RELATIONSHIP_MAPPING[predicate_lower]
        if isinstance(mapping, tuple):
            return mapping
        return (mapping, {})

    # Check for partial matches
    for key, value in RELATIONSHIP_MAPPING.items():
        if key in predicate_lower:
            if isinstance(value, tuple):
                return value
            return (value, {})

    # Default to generic relationship with original predicate stored
    return ("ASSOCIATED_WITH", {"predicate": predicate})
