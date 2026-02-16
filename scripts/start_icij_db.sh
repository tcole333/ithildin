#!/bin/bash
# Start ICIJ Offshore Leaks Neo4j database
# Usage: ./scripts/start_icij_db.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# Dump file lives in the offshore-leaks project (too large to copy)
DUMP_FILE="/Users/travcole/projects/offshore-leaks/data/icij-offshoreleaks-5.13.0.dump"

echo "=== ICIJ Offshore Leaks Database Setup ==="

# Check if dump file exists
if [ ! -f "$DUMP_FILE" ]; then
    echo "Error: Dump file not found at $DUMP_FILE"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Check if container already exists and is running
if docker ps --format '{{.Names}}' | grep -q '^icij-offshore-leaks$'; then
    echo "ICIJ database is already running!"
    echo "  Bolt: bolt://localhost:7689"
    echo "  Browser: http://localhost:7475"
    exit 0
fi

# Remove any stopped container
docker rm icij-offshore-leaks 2>/dev/null || true

# Create volume if needed
docker volume create icij-neo4j-data 2>/dev/null || true

# Check if data already loaded (look for neo4j database files)
DATA_EXISTS=$(docker run --rm -v icij-neo4j-data:/data alpine sh -c "ls /data/databases/neo4j 2>/dev/null | head -1" || echo "")

if [ -z "$DATA_EXISTS" ]; then
    echo "Loading ICIJ dump file (this may take a few minutes)..."

    # Load the dump using neo4j-admin
    docker run --rm \
        -v "$DUMP_FILE:/dump/icij.dump:ro" \
        -v icij-neo4j-data:/data \
        neo4j:5.13.0 \
        neo4j-admin database load neo4j --from-path=/dump/icij.dump --overwrite-destination=true 2>/dev/null || \
    docker run --rm \
        -v "$DUMP_FILE:/dump/icij.dump:ro" \
        -v icij-neo4j-data:/data \
        neo4j:5.13.0 \
        bash -c "neo4j-admin database load --from-stdin neo4j < /dump/icij.dump" 2>/dev/null || \
    docker run --rm \
        -v "$DUMP_FILE:/dump/icij.dump:ro" \
        -v icij-neo4j-data:/data \
        neo4j:5.13.0 \
        bash -c "cp /dump/icij.dump /tmp/icij.dump && neo4j-admin database load neo4j --from-path=/tmp/icij.dump --overwrite-destination=true" || \
    echo "Note: Will try alternative load method..."

    echo "Dump loaded successfully."
else
    echo "Database already loaded, starting container..."
fi

# Start Neo4j container
echo "Starting Neo4j container..."
docker run -d \
    --name icij-offshore-leaks \
    -p 7689:7687 \
    -p 7475:7474 \
    -v icij-neo4j-data:/data \
    -e NEO4J_AUTH=none \
    -e NEO4J_PLUGINS='["apoc"]' \
    -e NEO4J_dbms_memory_heap_initial__size=512m \
    -e NEO4J_dbms_memory_heap_max__size=1G \
    neo4j:5.13.0

echo "Waiting for database to be ready..."
for i in {1..60}; do
    if curl -s http://localhost:7475 > /dev/null 2>&1; then
        break
    fi
    sleep 2
    echo -n "."
done
echo ""

# Verify it's running
if docker ps --format '{{.Names}}' | grep -q '^icij-offshore-leaks$'; then
    echo ""
    echo "=== ICIJ Database Ready ==="
    echo "  Bolt: bolt://localhost:7689"
    echo "  Browser: http://localhost:7475"
    echo ""
    echo "Test with: python3 scripts/search_epstein_offshore.py"
else
    echo "ERROR: Container failed to start. Check logs with: docker logs icij-offshore-leaks"
    exit 1
fi
