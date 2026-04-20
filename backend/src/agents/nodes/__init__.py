# backend/src/agents/nodes/__init__.py

from .demographic_depth import demographic_depth_node
from .legal import legal_node
from .synthesis import synthesis_node

__all__ = [
    "demographic_depth_node",
    "legal_node",
    "synthesis_node",
]
