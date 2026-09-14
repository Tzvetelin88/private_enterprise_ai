#!/bin/bash
# Bulk-load docs/tech/*.md into a RAG service's /upload endpoint.
#
# Useful for populating an otherwise-empty knowledge base (e.g. so
# "What is pgvector?" against agentic-rag/hybrid-rag has real content to
# retrieve instead of "No relevant information found").
#
# Usage: bash scripts/load-tech-docs.sh [base_url]
#   base_url defaults to http://localhost:8001 (hybrid-rag). Pass another
#   RAG service's URL (e.g. http://localhost:8003 for graph-rag) to load
#   the same docs there instead.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DOCS_DIR="${PROJECT_ROOT}/docs/tech"
BASE_URL="${1:-http://localhost:8001}"

if [ ! -d "$DOCS_DIR" ]; then
    echo "❌ ${DOCS_DIR} not found"
    exit 1
fi

echo "📚 Loading ${DOCS_DIR}/*.md into ${BASE_URL}/upload"
echo ""

response_file="$(mktemp)"
trap 'rm -f "$response_file"' EXIT

count=0
failed=0
for f in "${DOCS_DIR}"/*.md; do
    name="$(basename "$f")"
    http_code=$(curl -s -o "$response_file" -w "%{http_code}" \
        -X POST "${BASE_URL}/upload" \
        -F "file=@${f}")

    if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then
        chunks=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('chunks_created', '?'))" "$response_file" 2>/dev/null || echo "?")
        echo "  ✅ ${name} (${chunks} chunks)"
        count=$((count + 1))
    else
        echo "  ❌ ${name} — HTTP ${http_code}: $(cat "$response_file")"
        failed=$((failed + 1))
    fi
done

echo ""
echo "✅ Loaded ${count} document(s), ${failed} failed"
echo ""
echo "Verify: curl ${BASE_URL}/documents"
