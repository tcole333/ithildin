# Triage, Deduplication, and Validation
## Design Document v1.0

### 1. Overview

Data quality is the foundation of credible research. This document specifies the systems that ensure:
- **Triage**: Incoming work is routed appropriately
- **Deduplication**: Redundant findings are merged, distinct findings preserved
- **Validation**: Citations are verified, claims are accurate, confidence is calibrated

These systems operate as queue jobs and gates throughout Ithildin.

### 2. Lead Triage System

#### 2.1 Lead Sources

| Source | Description | Frequency | Priority |
|--------|-------------|-----------|----------|
| `auto` | Auto-generated from findings | Real-time | Varies |
| `pattern` | Pattern spotter detections | Event-driven | High |
| `survey` | Surveyor discoveries | Every 6h | Medium |
| `synthesis` | Synthesist recommendations | Event-driven | High |
| `human` | Human-submitted | On-demand | User-set |
| `understanding` | Dossier/explainer triggers | Event-driven | Medium |

#### 2.2 Lead Lifecycle

```
┌──────────────┐
│   CREATED    │  Lead enters system from any source
└──────┬───────┘
       │
       ▼
┌──────────────┐
│pending_triage│  Queue for triage agent
└──────┬───────┘
       │
       ▼
┌──────────────┐     ┌──────────────┐
│  TRIAGE JOB  │────▶│  DUPLICATE?  │
│  (claimed)   │     │  Check       │
└──────────────┘     └──────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              │Yes          │No           │Similar
              ▼             ▼             ▼
       ┌──────────┐  ┌──────────┐  ┌──────────┐
       │  MERGE   │  │ PRIORITY │  │  DEFER   │
       │ with     │  │  SCORE   │  │ similar  │
       │ existing │  │          │  │ existing │
       └──────────┘  └────┬─────┘  └──────────┘
                          │
            ┌─────────────┼─────────────┐
            ▼             ▼             ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │ CRITICAL │ │   HIGH   │ │  MEDIUM  │
       │ (Epstein │ │(centrality│ │(general │
       │ direct)  │ │ nodes)   │ │ interest)│
       └────┬─────┘ └────┬─────┘ └────┬─────┘
            │            │            │
            ▼            ▼            ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │  OPEN    │ │  OPEN    │ │  OPEN    │
       │ immediate│ │ queue    │ │ queue    │
       └──────────┘ └──────────┘ └──────────┘
```

#### 2.3 Triage Decision Algorithm

```python
class LeadTriageEngine:
    def triage(self, lead: Lead) -> TriageDecision:
        """Route lead to appropriate queue."""
        
        # Check for exact duplicates
        duplicate = self.find_exact_duplicate(lead)
        if duplicate:
            return TriageDecision(
                action='merge',
                reason='Exact duplicate of existing lead',
                merge_into=duplicate.id
            )
        
        # Calculate priority score
        score = self.calculate_priority(lead)
        
        # Check for similar leads (not exact duplicates)
        similar = self.find_similar_leads(lead, threshold=0.75)
        if similar and score < 7:
            return TriageDecision(
                action='defer',
                reason=f'Similar to {len(similar)} existing leads',
                priority='low',
                related_leads=[s.id for s in similar]
            )
        
        # Route by score
        if score >= 9:
            return TriageDecision(action='open', priority='critical')
        elif score >= 7:
            return TriageDecision(action='open', priority='high')
        elif score >= 5:
            return TriageDecision(action='open', priority='medium')
        else:
            return TriageDecision(action='defer', priority='low')
    
    def calculate_priority(self, lead: Lead) -> float:
        """Calculate 0-10 priority score."""
        
        scores = {
            'network_proximity': self.network_score(lead),
            'evidence_strength': self.evidence_score(lead),
            'investigation_potential': self.potential_score(lead),
            'novelty': self.novelty_score(lead),
            'source_reliability': self.source_score(lead)
        }
        
        weights = {
            'network_proximity': 0.30,
            'evidence_strength': 0.25,
            'investigation_potential': 0.20,
            'novelty': 0.15,
            'source_reliability': 0.10
        }
        
        return sum(scores[k] * weights[k] for k in scores)
    
    def network_score(self, lead: Lead) -> float:
        """Score based on network position of target."""
        
        target = lead.target_name
        
        # Direct Epstein connection
        if target in self.get_epstein_direct_network():
            return 10
        
        # High centrality in network
        centrality = self.get_centrality(target)
        if centrality > 0.8:
            return 9
        elif centrality > 0.6:
            return 7
        elif centrality > 0.4:
            return 5
        
        # Bridge node (connects communities)
        if self.is_bridge_node(target):
            return 8
        
        # Isolated node
        return 3
    
    def evidence_score(self, lead: Lead) -> float:
        """Score based on strength of initial evidence."""
        
        if not lead.initial_evidence:
            return 3
        
        evidence = lead.initial_evidence
        
        # Primary source evidence
        if evidence.get('source_type') == 'primary':
            if evidence.get('confidence') == 'confirmed':
                return 9
            return 7
        
        # Secondary source
        if evidence.get('source_type') == 'secondary':
            return 5
        
        # Inference only
        return 3
```

#### 2.4 Duplicate Detection

```python
class DuplicateDetector:
    def find_exact_duplicate(self, lead: Lead) -> Optional[Lead]:
        """Find exact duplicate lead."""
        
        return self.db.query_one("""
            SELECT * FROM leads
            WHERE target_name = :target
              AND category = :category
              AND description = :description
              AND status NOT IN ('dead_end', 'completed')
            LIMIT 1
        """, {
            "target": lead.target_name,
            "category": lead.category,
            "description": lead.description
        })
    
    def find_similar_leads(self, lead: Lead, threshold: float = 0.75) -> List[Lead]:
        """Find semantically similar leads."""
        
        # Same target, different angle
        same_target = self.db.query("""
            SELECT * FROM leads
            WHERE target_name = :target
              AND id != :lead_id
              AND status NOT IN ('dead_end', 'completed')
        """, {"target": lead.target_name, "lead_id": lead.id})
        
        # Similar targets (fuzzy name match)
        similar_names = self.fuzzy_search_leads(lead.target_name, threshold=0.85)
        
        # Similar descriptions (vector similarity if available)
        similar_desc = self.semantic_search_leads(lead.description, threshold=threshold)
        
        return list(set(same_target + similar_names + similar_desc))
```

### 3. Finding Deduplication

#### 3.1 Finding Similarity Scoring

```python
class FindingSimilarity:
    def calculate_similarity(self, finding_a: Finding, finding_b: Finding) -> float:
        """Calculate 0-1 similarity score between findings."""
        
        components = {
            'target': self.target_similarity(finding_a, finding_b),
            'type': self.type_similarity(finding_a, finding_b),
            'summary': self.text_similarity(finding_a.summary, finding_b.summary),
            'evidence': self.evidence_overlap(finding_a, finding_b),
            'date': self.date_proximity(finding_a, finding_b)
        }
        
        weights = {
            'target': 0.25,
            'type': 0.15,
            'summary': 0.30,
            'evidence': 0.20,
            'date': 0.10
        }
        
        return sum(components[k] * weights[k] for k in components)
    
    def target_similarity(self, a: Finding, b: Finding) -> float:
        """Score name similarity."""
        return fuzz.ratio(a.target_name.lower(), b.target_name.lower()) / 100
    
    def evidence_overlap(self, a: Finding, b: Finding) -> float:
        """Score evidence source overlap."""
        
        evidence_a = set(e.evidence_ref for e in a.evidence)
        evidence_b = set(e.evidence_ref for e in b.evidence)
        
        if not evidence_a or not evidence_b:
            return 0.0
        
        intersection = evidence_a & evidence_b
        union = evidence_a | evidence_b
        
        return len(intersection) / len(union)
```

#### 3.2 Merge vs Keep Separate Decision

```python
class DedupeDecision:
    def should_merge(self, finding_a: Finding, finding_b: Finding, similarity: float) -> bool:
        """Decide whether to merge two findings."""
        
        # High similarity + same evidence = merge
        if similarity > 0.90 and self.same_primary_evidence(finding_a, finding_b):
            return True
        
        # High similarity + different evidence = corroboration, keep separate
        if similarity > 0.90 and not self.same_primary_evidence(finding_a, finding_b):
            return False  # Keep as corroborating findings
        
        # Medium similarity + same evidence = likely same finding, different phrasing
        if 0.75 < similarity < 0.90 and self.same_primary_evidence(finding_a, finding_b):
            return True
        
        # Different evidence sources = keep separate (corroboration)
        if not self.evidence_overlap(finding_a, finding_b):
            return False
        
        return False
    
    def merge_findings(self, primary: Finding, duplicate: Finding) -> Finding:
        """Merge duplicate into primary finding."""
        
        # Combine evidence (keep all unique evidence refs)
        all_evidence = primary.evidence + [
            e for e in duplicate.evidence 
            if e.evidence_ref not in [pe.evidence_ref for pe in primary.evidence]
        ]
        
        # Update primary with merged info
        merged = primary.copy()
        merged.evidence = all_evidence
        merged.source_datasets = list(set(primary.source_datasets + duplicate.source_datasets))
        
        # If duplicate had higher confidence, upgrade
        if CONFIDENCE_RANK[duplicate.confidence] > CONFIDENCE_RANK[primary.confidence]:
            merged.confidence = duplicate.confidence
        
        # Add merge record
        merged.merge_history.append({
            'merged_finding_id': duplicate.id,
            'merged_at': datetime.now().isoformat()
        })
        
        # Mark duplicate as merged
        self.db.mark_finding_merged(duplicate.id, primary.id)
        
        return merged
```

### 4. Citation Verification System

#### 4.1 Verification Levels

| Level | Description | Action |
|-------|-------------|--------|
| `verified` | Quote matches document exactly | Accept |
| `paraphrase_verified` | Paraphrase accurately represents source | Accept |
| `page_mismatch` | Document found, page reference wrong | Flag for correction |
| `quote_mismatch` | Document found, quote doesn't match | Flag for review |
| `document_not_found` | Cannot locate cited document | Reject / escalate |
| `access_denied` | Document exists but cannot access | Flag for human |

#### 4.2 Verification Process

```python
class CitationVerifier:
    def verify(self, citation: Citation) -> VerificationResult:
        """Verify a single citation."""
        
        # Step 1: Locate document
        doc = self.locate_document(citation.evidence_ref)
        if not doc:
            return VerificationResult(
                status='document_not_found',
                citation=citation,
                recommendation='escalate'
            )
        
        # Step 2: Verify page/reference (if specified)
        if citation.page:
            page_valid = self.verify_page(doc, citation.page, citation.context)
            if not page_valid:
                return VerificationResult(
                    status='page_mismatch',
                    citation=citation,
                    actual_location=self.find_in_document(doc, citation.context),
                    recommendation='correct'
                )
        
        # Step 3: Verify quote (if direct quote)
        if citation.claim_type == 'direct_quote':
            quote_match = self.verify_quote(doc, citation.source_quote)
            if not quote_match:
                return VerificationResult(
                    status='quote_mismatch',
                    citation=citation,
                    found_text=self.find_similar_text(doc, citation.source_quote),
                    recommendation='review'
                )
        
        # Step 4: Verify paraphrase (if paraphrase)
        if citation.claim_type == 'paraphrase':
            context_match = self.verify_context(doc, citation.source_quote)
            if not context_match:
                return VerificationResult(
                    status='paraphrase_mismatch',
                    citation=citation,
                    recommendation='review'
                )
        
        return VerificationResult(
            status='verified',
            citation=citation
        )
    
    def locate_document(self, ref: str) -> Optional[Document]:
        """Locate document by reference."""
        
        # Try different reference formats
        if ref.startswith('EFTA'):
            return self.query_doj(ref)
        elif ref.startswith('LMSBAND:'):
            return self.query_lmsband(ref.split(':')[1])
        elif ref.startswith('DOJ11:'):
            return self.query_doj(ref.split(':')[1])
        elif ref.startswith('http'):
            return self.fetch_url(ref)
        else:
            # Try unified DB
            return self.query_unified(ref)
    
    def verify_quote(self, doc: Document, quote: str) -> bool:
        """Check if quote exists exactly in document."""
        
        # Normalize whitespace
        normalized_doc = self.normalize_text(doc.text)
        normalized_quote = self.normalize_text(quote)
        
        # Exact match
        if normalized_quote in normalized_doc:
            return True
        
        # Fuzzy match (handle OCR errors)
        best_match = self.find_best_match(normalized_doc, normalized_quote)
        if best_match.similarity > 0.95:
            return True
        
        return False
```

#### 4.3 Batch Verification Jobs

```python
class BatchVerificationJob:
    """Queue job for verifying multiple findings."""
    
    def execute(self, payload):
        """Verify all citations in specified findings."""
        
        findings = self.get_findings(payload['finding_ids'])
        
        results = []
        for finding in findings:
            for citation in finding.evidence:
                result = self.verifier.verify(citation)
                results.append(result)
                
                # Update citation status
                self.update_citation_status(citation.id, result.status)
        
        # Summary statistics
        summary = {
            'total_citations': len(results),
            'verified': sum(1 for r in results if r.status == 'verified'),
            'mismatches': sum(1 for r in results if 'mismatch' in r.status),
            'not_found': sum(1 for r in results if r.status == 'document_not_found')
        }
        
        # Flag findings with failed verifications
        if summary['mismatches'] > 0 or summary['not_found'] > 0:
            self.flag_for_review(payload['finding_ids'], summary)
        
        return {
            'verified_count': summary['verified'],
            'flagged_count': summary['mismatches'] + summary['not_found'],
            'details': [r.to_dict() for r in results]
        }
```

### 5. Confidence Calibration

#### 5.1 Confidence Rules

```python
CONFIDENCE_RULES = {
    'direct_quote': {
        'primary_source': 'confirmed',
        'secondary_source': 'high',
        'tertiary_source': 'medium'
    },
    'paraphrase': {
        'primary_source': 'high',
        'secondary_source': 'medium',
        'tertiary_source': 'low'
    },
    'inference': {
        'max': 'medium'  # Inferences can never be confirmed
    },
    'synthesis': {
        'max': 'medium'  # Syntheses can never be confirmed
    },
    'calculation': {
        'verified_data': 'high',
        'partial_data': 'medium'
    }
}

def calibrate_confidence(finding: Finding) -> str:
    """Apply confidence ceiling based on claim type."""
    
    claim_type = finding.claim_type
    source_tier = finding.source_tier
    
    rules = CONFIDENCE_RULES.get(claim_type, {})
    
    if 'max' in rules:
        return min_confidence(finding.confidence, rules['max'])
    
    ceiling = rules.get(source_tier, 'low')
    return min_confidence(finding.confidence, ceiling)
```

#### 5.2 Source Tier Classification

```python
SOURCE_TIERS = {
    'primary': [
        'DOJ_EFTA', 'FBI_files', 'court_filings', 
        'actual_emails', 'corporate_registries',
        'SEC_filings', 'IRS_990', 'KPMG_review'
    ],
    'secondary': [
        'Miami_Herald', 'Bloomberg', 'Reuters',
        'investigative_reporting', 'analyst_reports'
    ],
    'tertiary': [
        'Wikipedia', 'social_media', 'blogs',
        'unverified_claims'
    ]
}

def classify_source_tier(source: str) -> str:
    """Classify source into tier."""
    
    for tier, sources in SOURCE_TIERS.items():
        if any(s.lower() in source.lower() for s in sources):
            return tier
    
    return 'tertiary'  # Default to lowest tier
```

### 6. Validation Gates

#### 6.1 Finding Submission Gate

Every finding passes through validation before being recorded:

```python
class FindingSubmissionGate:
    def validate(self, finding: Finding) -> GateResult:
        """Validate finding before recording."""
        
        checks = []
        
        # 1. Duplicate check
        duplicate = self.dedupe.find_similar(finding, threshold=0.85)
        if duplicate:
            if self.dedupe.should_merge(finding, duplicate):
                return GateResult(
                    action='merge',
                    merge_into=duplicate.id,
                    reason='Duplicate finding'
                )
        
        # 2. Citation verification (async)
        if finding.claim_type == 'direct_quote':
            # Queue verification job
            self.queue.spawn_job(
                job_type='verify_finding',
                payload={'finding': finding.to_dict()}
            )
        
        # 3. Confidence calibration
        finding.confidence = calibrate_confidence(finding)
        
        # 4. Required fields check
        if not finding.evidence:
            return GateResult(
                action='reject',
                reason='Finding must have evidence'
            )
        
        return GateResult(action='accept', finding=finding)
```

#### 6.2 Connection Validation

```python
class ConnectionValidation:
    def validate_connection(self, conn: Connection) -> GateResult:
        """Validate connection before recording."""
        
        # 1. Both persons must exist
        if not self.db.person_exists(conn.person_a):
            return GateResult(action='reject', reason=f'Person {conn.person_a} not found')
        
        if not self.db.person_exists(conn.person_b):
            return GateResult(action='reject', reason=f'Person {conn.person_b} not found')
        
        # 2. Check for duplicate connection
        existing = self.db.find_connection(conn.person_a, conn.person_b, conn.relationship_type)
        if existing:
            # Merge evidence
            return GateResult(action='merge', merge_into=existing.id)
        
        # 3. Validate evidence supports relationship type
        if not self.evidence_supports_type(conn.evidence, conn.relationship_type):
            return GateResult(
                action='flag',
                reason='Evidence may not support claimed relationship type'
            )
        
        return GateResult(action='accept', connection=conn)
```

#### 6.3 Understanding Output Validation

Each output modality has specific quality dimensions applied during editor review:

```python
MODALITY_QUALITY_GATES = {
    'wiki_dossier_update': {
        'dimensions': {
            'factual_accuracy': 'All claims must have citations. Direct quotes verified.',
            'completeness': 'All known findings for target must be incorporated.',
            'link_integrity': 'All entity mentions link to valid dossier pages.',
            'currency': 'No stale data (findings older than dossier last_updated).',
            'structure': 'Consistent section ordering, valid frontmatter.'
        },
        'auto_approve_threshold': 8.5,  # High bar — dossiers are the reference layer
        'reject_threshold': 5.0
    },
    'mechanism_explainer': {
        'dimensions': {
            'mechanism_accuracy': 'Description matches evidence. Steps are verifiable.',
            'clarity': 'Informed general reader can follow. No unexplained jargon.',
            'accessibility': 'Analogies and examples aid understanding.',
            'sourcing': 'Each mechanism step cites at least one primary source.',
            'examples': 'At least 2 concrete instances from the investigation.'
        },
        'auto_approve_threshold': 8.0,
        'reject_threshold': 5.5
    },
    'analytical_article': {
        'dimensions': {
            'sourcing_depth': 'Minimum 70% primary sources. No unsourced factual claims.',
            'analytical_rigor': 'Thesis is stated, supported, and counter-evidence acknowledged.',
            'factual_accuracy': 'All citations verified. Claim types match confidence.',
            'novelty': 'Adds genuine insight beyond restating known findings.',
            'coherence': 'Logical flow from evidence to conclusion. No contradictions.'
        },
        'auto_approve_threshold': 8.0,
        'reject_threshold': 5.0
    },
    'visual_export': {
        'dimensions': {
            'data_integrity': 'Nodes and edges match current database state.',
            'readability': 'Labels visible, layout not overcrowded.',
            'entity_resolution': 'No duplicate nodes for same entity.'
        },
        'auto_approve_threshold': 9.0,  # Data accuracy is binary
        'reject_threshold': 7.0
    }
}
```

### 7. Automated Audit Jobs

```python
class AuditScheduler:
    """Schedule periodic validation jobs."""
    
    def schedule_audits(self):
        """Create scheduled validation jobs."""
        
        # Daily: Verify recent findings
        self.queue.spawn_job(
            job_type='finding_audit',
            payload={
                'filter': 'recent',
                'days': 1,
                'confidence': 'unverified'
            },
            cron='0 2 * * *'  # 2 AM daily
        )
        
        # Weekly: Check for duplicates in recent findings
        self.queue.spawn_job(
            job_type='dedupe_review',
            payload={
                'days': 7,
                'similarity_threshold': 0.80
            },
            cron='0 3 * * 0'  # Sunday 3 AM
        )
        
        # Monthly: Full citation verification
        self.queue.spawn_job(
            job_type='citation_audit',
            payload={
                'confidence_levels': ['confirmed', 'high'],
                'sample_size': 100  # Spot check
            },
            cron='0 4 1 * *'  # 1st of month, 4 AM
        )

        # Daily: Wiki dossier freshness audit
        self.queue.spawn_job(
            job_type='dossier_freshness_audit',
            payload={
                'staleness_threshold_days': 7,
                'min_new_findings': 3  # Flag if 3+ new findings since last update
            },
            cron='0 5 * * *'  # 5 AM daily
        )
```

### 8. Validation Reporting

```python
class ValidationDashboard:
    def generate_report(self) -> ValidationReport:
        """Generate validation status report."""
        
        return {
            'findings': {
                'total': self.db.count_findings(),
                'verified': self.db.count_by_verification('verified'),
                'unverified': self.db.count_by_verification('unverified'),
                'disputed': self.db.count_by_verification('disputed'),
                'verification_rate': self.calc_verification_rate()
            },
            'citations': {
                'total': self.db.count_citations(),
                'verified': self.db.count_citations_by_status('verified'),
                'mismatches': self.db.count_citations_by_status('quote_mismatch'),
                'not_found': self.db.count_citations_by_status('document_not_found')
            },
            'duplicates': {
                'potential': self.db.count_potential_duplicates(),
                'merged_this_week': self.db.count_recent_merges(days=7),
                'flagged_for_review': self.db.count_flagged_duplicates()
            },
            'audit_queue': {
                'pending_verification': self.queue.count_jobs('verify_finding'),
                'pending_dedupe': self.queue.count_jobs('dedupe_review'),
                'stuck_jobs': self.queue.count_stuck_jobs()
            }
        }
```

---

See next: `06-context-management.md` for report submission patterns
