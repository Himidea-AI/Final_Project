# backend/src/agents/nodes/__init__.py

from .legal import legal_node
from .synthesis import synthesis_node

__all__ = [
    "legal_node",
    "synthesis_node",
]
