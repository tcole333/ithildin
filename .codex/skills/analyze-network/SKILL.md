---
name: analyze-network
description: Graph structure analysis — centrality, bridges, clusters, cross-thread actors, coverage gaps
---

# /analyze-network

Analyze the investigation graph to find structurally important nodes, dense clusters, bridge positions, cross-thread actors, and under-investigated high-connectivity targets. Focuses on non-Epstein edges — what connects actors to each other independently?

## Arguments

- No arguments: full analysis
- `--thread N`: focus on a specific thread's subgraph

## Process

### 0. Session Setup

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

### 1. Register Analysis Run

```bash
uv run uv run python -c "
from tools.analysis_export import start_analysis_run
run_id = start_analysis_run('analyze-network')
print(f'Analysis run #{run_id}')
"
```

Save the `run_id` for later.

### 2. Export Data

```bash
uv run uv run python tools/analysis_export.py connections-graph --output $WORKDIR/graph.json
uv run uv run python tools/analysis_export.py coverage-matrix --top 100 --output $WORKDIR/coverage.json
uv run uv run python tools/analysis_export.py thread-summary --output $WORKDIR/threads.json
```

### 3. Graph Metrics

Run these analyses and save results:

```bash
uv run uv run python tools/graph_tools.py centrality --metric degree --top 50 --cache --output $WORKDIR/degree.json
uv run uv run python tools/graph_tools.py centrality --metric betweenness --top 50 --cache --output $WORKDIR/betweenness.json
uv run uv run python tools/graph_tools.py bridges --output $WORKDIR/bridges.json
uv run uv run python tools/graph_tools.py holes --min-degree 3 --output $WORKDIR/holes.json
uv run uv run python tools/graph_tools.py cliques --min-size 3 --output $WORKDIR/cliques.json
uv run uv run python tools/graph_tools.py components --min-size 3 --output $WORKDIR/components.json
uv run uv run python tools/graph_tools.py stats
```

### 3b. Institutional Analysis

```bash
uv run uv run python tools/pillar_tracker.py score --top 30 --cache --output $WORKDIR/orchestrator-scores.json
uv run uv run python tools/pillar_tracker.py cross-pillar --min-pillars 2 --output $WORKDIR/cross-pillar.json
uv run uv run python tools/graph_tools.py institutional-graph --min-shared 1 --output $WORKDIR/inst-graph.json
uv run uv run python tools/graph_tools.py pillar-subgraph --pillar-type legal --metric degree --top 20 --output $WORKDIR/legal-subgraph.json
uv run uv run python tools/graph_tools.py pillar-subgraph --pillar-type banking --metric degree --top 20 --output $WORKDIR/banking-subgraph.json
uv run uv run python tools/graph_tools.py pillar-subgraph --pillar-type government --metric degree --top 20 --output $WORKDIR/gov-subgraph.json
uv run uv run python tools/analysis_export.py pillar-dump --output $WORKDIR/pillar-dump.json
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
uv run uv run python tools/analysis_export.py findings-dump --output $WORKDIR/findings.json
```
Then identify target_names appearing across different thread_ids. These cross-thread actors may be system-level connectors, not just Epstein associates.

**f) Non-Epstein edges**
In the connections graph, find edges where neither endpoint is "Jeffrey Epstein". What's the densest non-Epstein subgraph? This reveals the system that exists independent of Epstein.

**g) Institutional patterns**
From orchestrator scores: who spans the most pillar types? Who has government↔private transitions (revolving door)? From the institutional graph: which institutions share the most alumni? From pillar-subgraph analysis: who is most central within each pillar type?

### 5. Record Findings

For each structural insight discovered:

```bash
uv run uv run python tools/findings_tracker.py add \
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
uv run uv run python tools/tag_manager.py bulk-tag --table findings --ids ID1,ID2,ID3 \
    --type cluster --value "CLUSTER_NAME" --created-by "agent:analyze-network"
```

### 7. Generate Hypotheses

For structural observations that suggest deeper investigation:

```bash
uv run uv run python tools/hypothesis_tracker.py add \
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
uv run uv run python tools/lead_tracker.py add \
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
uv run uv run python -c "
from tools.analysis_export import complete_analysis_run
complete_analysis_run(RUN_ID, findings_created=N, hypotheses_created=M,
                      leads_created=L, tags_created=T,
                      report_path='$WORKDIR/report-analyze-network.md')
"
```

## Notes

- All findings: `claim_type=synthesis`, max confidence `medium`
- Focus on NON-Epstein edges — what connects actors to each other?
- The coverage gap analysis is especially valuable: high-connectivity nodes with few findings indicate blind spots
- Use `--thread-id` on hypothesis/lead creation to assign to appropriate thread
- Tag everything you find for future analysis runs to build on
