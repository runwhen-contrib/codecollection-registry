"""
RunWhen MCP Server utilities package.

Primary runtime entry point is `RegistryClient` — a thin HTTP client
that delegates all data access to the backend Registry API.

Legacy utilities (DataLoader, SearchEngine, SemanticSearch, VectorStore,
embeddings) are still available for the standalone indexer and ad-hoc scripts
but are NOT used by the HTTP server or MCP tools.
"""

# ── Primary (API-driven) ────────────────────────────────────────────
from .registry_client import RegistryClient, get_registry_client

# ── Legacy / Indexer helpers (imported lazily by scripts that need them) ──
# These are kept for backward compatibility with indexer.py,
# server.py (stdio), and Taskfile one-liners.
from .robot_parser import RobotParser
from .python_parser import PythonParser

__all__ = [
    # Primary
    'RegistryClient',
    'get_registry_client',
    # Legacy parsers still used by the indexer
    'RobotParser',
    'PythonParser',
]

