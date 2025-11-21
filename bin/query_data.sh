#!/bin/bash
# Query coaching data from database (agent-friendly wrapper)
#
# Usage examples:
#   bash bin/query_data.sh recent-runs --limit 5
#   bash bin/query_data.sh training-status
#   bash bin/query_data.sh recent-sleep --days 7
#   bash bin/query_data.sh upcoming-races

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

python3 src/query_data.py "$@"
