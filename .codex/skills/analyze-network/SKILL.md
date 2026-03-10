---
name: analyze-network
description: Graph structure analysis — centrality, bridges, clusters, cross-thread actors, coverage gaps
user_invocable: true
---

# /analyze-network

**LAYER 2: ANALYSIS AGENT** — This is a theory-building skill. You identify structural patterns in the graph and generate hypotheses, but every hypothesis MUST produce a testable prediction queued as a research lead for Layer 1 agents. Do not apply analytical frameworks as interpretive lenses — use them only as pattern detectors. See `research/INVESTIGATIVE_METHODOLOGY.md#framework-discipline`. Distinguish structural observations (fact: "Node X has high betweenness") from interpretive claims (theory: "Node X is a gatekeeper") — label them differently.

Analyze the investigation graph to find structurally important nodes, dense clusters, bridge positions, cross-thread actors, and under-investigated high-connectivity targets. Focuses on non-subject edges — what connects actors to each other independently?

## Arguments

- No arguments: full analysis
- `--thread N`: focus on a specific thread's subgraph

### Context Loading
Load the active investigation context before executing:
```bash
uv run python tools/investigation_context.py show
```
This provides: primary_subject, key_persons, threads, corpus_tools, key_dates, known_addresses.
Use these values instead of hardcoded names throughout this skill.

## Process

### 0. Session Setup

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

### 1. Register Analysis Run

```bash
uv run python -c "
from tools.analysis_export import start_analysis_run
run_id = start_analysis_run('analyze-network')
print(f'Analysis run #{run_id}')
"
```

Save the `run_id` for later.

### 2. Export Data

```bash
uv run python tools/analysis_export.py connections-graph --output $WORKDIR/graph.json
uv run python tools/analysis_export.py coverage-matrix --top 100 --output $WORKDIR/coverage.json
uv run python tools/analysis_export.py thread-summary --output $WORKDIR/threads.json
```

### 3. Graph Metrics

Run these analyses and save results:

```bash
uv run python tools/graph_tools.py centrality --metric degree --top 50 --cache --output $WORKDIR/degree.json
uv run python tools/graph_tools.py centrality --metric betweenness --top 50 --cache --output $WORKDIR/betweenness.json
uv run python tools/graph_tools.py bridges --output $WORKDIR/bridges.json
uv run python tools/graph_tools.py holes --min-degree 3 --output $WORKDIR/holes.json
uv run python tools/graph_tools.py cliques --min-size 3 --output $WORKDIR/cliques.json
uv run python tools/graph_tools.py components --min-size 3 --output $WORKDIR/components.json
uv run python tools/graph_tools.py triangles --top 30 --output $WORKDIR/triangles.json
uv run python tools/graph_tools.py clustering --min-degree 3 --top 50 --output $WORKDIR/clustering.json
uv run python tools/graph_tools.py stats
```

### 3b. Institutional Analysis

```bash
uv run python tools/pillar_tracker.py score --top 30 --cache --output $WORKDIR/orchestrator-scores.json
uv run python tools/pillar_tracker.py cross-pillar --min-pillars 2 --output $WORKDIR/cross-pillar.json
uv run python tools/graph_tools.py institutional-graph --min-shared 1 --output $WORKDIR/inst-graph.json
uv run python tools/graph_tools.py pillar-subgraph --pillar-type legal --metric degree --top 20 --output $WORKDIR/legal-subgraph.json
uv run python tools/graph_tools.py pillar-subgraph --pillar-type banking --metric degree --top 20 --output $WORKDIR/banking-subgraph.json
uv run python tools/graph_tools.py pillar-subgraph --pillar-type government --metric degree --top 20 --output $WORKDIR/gov-subgraph.json
uv run python tools/analysis_export.py pillar-dump --output $WORKDIR/pillar-dump.json
```

### 4. Analyze Results

Read the exported files and look for:

**a) High-centrality under-investigated nodes**
Cross-reference betweenness centrality against coverage matrix. A node with high betweenness but few findings is a critical gap — it bridges parts of the network but we know little about it.

**b) Bridge nodes**
Nodes whose removal disconnects graph regions. These are brokers, gatekeepers, or intermediaries. Check if their role is already documented in findings. If not, they need investigation.

**c) Structural holes**
Nodes with high brokerage score (low neighbor density). Their neighbors don't know each other — the node controls information flow. Compare against entity registry: are these lawyers, financial advisors, or fixers?

**d) Dense subgraphs (cliques)**
Groups where everyone knows everyone. These may represent: boards, partnerships, social circles, or operational teams. Cross-reference with threads — does the clique span multiple threads?

**e) Cross-thread actors**
Using findings-dump, find persons who appear in 2+ threads:
```bash
uv run python tools/analysis_export.py findings-dump --output $WORKDIR/findings.json
```
Then identify target_names appearing across different thread_ids. These cross-thread actors may be system-level connectors, not just direct associates of the primary subject.

**f) Non-subject edges**
In the connections graph, find edges where neither endpoint is the primary_subject from the investigation profile. What's the densest non-subject subgraph? This reveals the system that exists independent of the primary subject.

**g) Open triads (triadic closure)**
Which missing edges are most surprising? High closure scores mean B and C share strong connections through mutual pivots, have overlapping relationship types, and share institutional affiliations — yet have no documented direct link. Cross-reference with the coverage matrix: if both B and C are under-investigated, the gap may reflect our ignorance rather than reality. If both are well-documented with many findings, the missing edge is genuinely surprising and may indicate a deliberate separation or a relationship conducted through intermediaries.

**h) Clustering coefficients**
Nodes with low clustering (neighbors don't know each other) are brokers — compare against structural holes output. Nodes with high clustering are embedded in tight groups — cross-reference with cliques. A high-centrality node with low clustering is a system-level connector worth prioritizing.

**i) Institutional patterns (pillar analysis)**
From orchestrator scores: who spans the most pillar types? Who has government↔private transitions (revolving door)? From the institutional graph: which institutions share the most alumni? From pillar-subgraph analysis: who is most central within each pillar type?

### 5. Record Findings

For each structural insight discovered:

```bash
uv run python tools/findings_tracker.py add \
    --target "NETWORK_TARGET" \
    --type relationship \
    --summary "INSIGHT" \
    --detail "DETAIL" \
    --confidence medium \
    --claim-type synthesis \
    --evidence "analysis-run-{RUN_ID}" \
    --source-quote "graph_tools output: METRIC=VALUE"
```

### 6. Tag Clusters

For each cluster or pattern identified:

```bash
uv run python tools/tag_manager.py bulk-tag --table findings --ids ID1,ID2,ID3 \
    --type cluster --value "CLUSTER_NAME" --created-by "agent:analyze-network"
```

### 7. Generate Hypotheses

For structural observations that suggest deeper investigation:

```bash
uv run python tools/hypothesis_tracker.py add \
    --title "HYPOTHESIS" \
    --pattern-type structural \
    --description "EVIDENCE AND REASONING" \
    --predicted-evidence "What we'd find if true" \
    --search-plan "Specific searches to test" \
    --originated-from "analysis:analyze-network"
```

### 8. Create Leads for Gaps

For high-connectivity under-investigated nodes:

```bash
uv run python tools/lead_tracker.py add \
    --target "NAME" \
    --category person \
    --priority high \
    --description "High betweenness centrality (rank N) with only M findings. Bridge between CLUSTER_A and CLUSTER_B." \
    --source "analysis:analyze-network"
```

### 9. Write Report

Write analysis report to `$WORKDIR/report-analyze-network.md` with:
- Graph statistics summary
- Top 20 centrality rankings (degree + betweenness)
- Bridge nodes identified
- Structural holes with brokerage scores
- Dense subgraphs / cliques
- Cross-thread actors
- Coverage gaps (high connectivity, low findings)
- Hypotheses generated
- Leads created

### 10. Complete Analysis Run

```bash
uv run python -c "
from tools.analysis_export import complete_analysis_run
complete_analysis_run(RUN_ID, findings_created=N, hypotheses_created=M,
                      leads_created=L, tags_created=T,
                      report_path='$WORKDIR/report-analyze-network.md')
"
```

## Notes

- All findings: `claim_type=synthesis`, max confidence `medium`
- Focus on NON-subject edges — what connects actors to each other?
- The coverage gap analysis is especially valuable: high-connectivity nodes with few findings indicate blind spots
- Use `--thread-id` on hypothesis/lead creation to assign to appropriate thread
- Tag everything you find for future analysis runs to build on
