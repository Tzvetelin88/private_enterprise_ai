"""Configure sys.path so mcp.shared.* imports resolve from the project root."""
import sys
from pathlib import Path

# Ensure project root is first on sys.path so our local mcp/ package is found
# before pytest's test-directory insertion (which would shadow mcp/ with tests/unit/mcp/)
root = str(Path(__file__).parents[3])
if root not in sys.path:
    sys.path.insert(0, root)
