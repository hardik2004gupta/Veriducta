"""Storage backend abstractions.

Re-exports ``BaseStorage`` so pipeline packages can import from ``storage``
rather than reaching into ``core.interfaces`` directly.
"""

from storage.base import BaseStorage

__all__ = ["BaseStorage"]
