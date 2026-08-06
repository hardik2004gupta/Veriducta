"""Storage backend abstractions.

Concrete backends (Qdrant, MinIO, SQLite) are implemented in Phase 1+.
This module re-exports ``BaseStorage`` for convenient import.
"""

from core.interfaces import BaseStorage

__all__ = ["BaseStorage"]
