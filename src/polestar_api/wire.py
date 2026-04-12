"""ProtoMessage base class — frozen dataclasses with automatic protobuf serialization.

Wire types are inferred from Python type hints:
    float       → double
    int         → int64 (varint)
    str         → string
    bool        → bool
    bytes       → bytes
    IntEnum     → enum (varint)
    ProtoMessage → nested message (length-delimited)
    X | None    → optional (unwraps to X)
"""

from __future__ import annotations

import types
from enum import IntEnum
from typing import Annotated, get_args, get_origin, get_type_hints

from . import codec


class Float32:
    """Marker for 32-bit float fields (protobuf 'float' vs 'double')."""


def _unwrap_optional(py_type: type) -> type:
    """Unwrap Optional[X] / X | None → X."""
    origin = get_origin(py_type)
    if origin is types.UnionType:
        args = [a for a in get_args(py_type) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return py_type


def _is_float32(py_type: type) -> bool:
    """Check if a type is Annotated[float, Float32]."""
    if get_origin(py_type) is Annotated:
        args = get_args(py_type)
        return len(args) >= 2 and args[0] is float and any(a is Float32 for a in args[1:])
    return False


def _infer_wire_type(py_type: type) -> str:
    py_type = _unwrap_optional(py_type)
    if _is_float32(py_type):
        return "float"
    if py_type is float:
        return "double"
    if py_type is int:
        return "int64"
    if py_type is str:
        return "string"
    if py_type is bool:
        return "bool"
    if py_type is bytes:
        return "bytes"
    if isinstance(py_type, type) and issubclass(py_type, IntEnum):
        return "enum"
    if isinstance(py_type, type) and issubclass(py_type, ProtoMessage):
        return "message"
    return "bytes"


class ProtoMessage:
    """Mixin that adds protobuf encode/decode to a frozen dataclass.

    Usage::

        @dataclass(frozen=True)
        class Battery(ProtoMessage, schema={2: "charge_level", 4: "range_km"}):
            charge_level: float = 0.0
            range_km: float = 0.0
    """

    _schema: dict[int, str]
    _decode_map: dict[int, tuple[str, str]]   # {field_num: (attr_name, wire_type)}
    _encode_map: dict[str, tuple[int, str]]   # {attr_name: (field_num, wire_type)}
    _type_hints: dict[str, type]

    def __init_subclass__(cls, schema: dict[int, str] | None = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if schema is None:
            return
        cls._schema = schema
        # Defer full init until first use (type hints may reference forward types)
        cls._decode_map = None
        cls._encode_map = None
        cls._type_hints = None

    @classmethod
    def _ensure_maps(cls):
        if cls._decode_map is not None:
            return
        hints = get_type_hints(cls, include_extras=True)
        cls._type_hints = hints
        cls._decode_map = {}
        cls._encode_map = {}
        for num, name in cls._schema.items():
            wt = _infer_wire_type(hints[name])
            cls._decode_map[num] = (name, wt)
            cls._encode_map[name] = (num, wt)

    def to_bytes(self) -> bytes:
        self._ensure_maps()
        values = {}
        for name, (num, wt) in self._encode_map.items():
            val = getattr(self, name)
            if val is None:
                continue
            if isinstance(val, ProtoMessage):
                val = val.to_bytes()
            elif isinstance(val, IntEnum):
                val = int(val)
            values[name] = val
        return codec.encode(self._encode_map, values)

    @classmethod
    def from_bytes(cls, data: bytes) -> "ProtoMessage":
        cls._ensure_maps()
        raw = codec.decode(data, cls._decode_map)
        kwargs = {}
        for num, name in cls._schema.items():
            val = raw.get(name)
            if val is None:
                continue
            py_type = _unwrap_optional(cls._type_hints[name])
            if isinstance(py_type, type) and issubclass(py_type, ProtoMessage):
                val = py_type.from_bytes(val)
            elif isinstance(py_type, type) and issubclass(py_type, IntEnum):
                val = py_type(val)
            kwargs[name] = val
        return cls(**kwargs)
