"""JSON serialisation helpers using orjson for performance."""

from datetime import datetime
from typing import Any
from uuid import UUID

import orjson
from pydantic import BaseModel


def _default(obj: Any) -> Any:
    """Fallback serialiser for types orjson does not handle natively."""
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serialisable")


def to_json(obj: Any, *, indent: bool = False) -> bytes:
    """Serialise *obj* to JSON bytes using orjson.

    Args:
        obj: Any JSON-serialisable value or Pydantic model.
        indent: If True, produce pretty-printed output.
    """
    opts = orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_UUID
    if indent:
        opts |= orjson.OPT_INDENT_2
    return orjson.dumps(obj, default=_default, option=opts)


def to_json_str(obj: Any, *, indent: bool = False) -> str:
    """Serialise *obj* to a JSON string."""
    return to_json(obj, indent=indent).decode("utf-8")


def from_json(data: bytes | str) -> Any:
    """Deserialise JSON bytes or string."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return orjson.loads(data)


def model_to_dict(model: BaseModel) -> dict[str, Any]:
    """Convert a Pydantic model to a plain dict, serialising nested models."""
    result: dict[str, Any] = from_json(to_json(model.model_dump()))
    return result
