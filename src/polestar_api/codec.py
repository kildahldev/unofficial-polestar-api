"""
Minimal protobuf encoder/decoder using raw wire format.
No .proto files or protoc needed.

Wire types:
  0 = varint (int32, int64, uint32, uint64, bool, enum)
  1 = 64-bit (double, fixed64)
  2 = length-delimited (string, bytes, embedded message, repeated)
  5 = 32-bit (float, fixed32)
"""

import struct


def encode_varint(value):
    if value < 0:
        value = value & 0xFFFFFFFFFFFFFFFF
    result = []
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value & 0x7F)
    return bytes(result)


def decode_varint(data, pos):
    result = 0
    shift = 0
    while True:
        b = data[pos]
        result |= (b & 0x7F) << shift
        pos += 1
        if not (b & 0x80):
            break
        shift += 7
    return result, pos


def encode_field(field_number, wire_type, value):
    tag = encode_varint((field_number << 3) | wire_type)
    return tag + value


def encode_string(field_number, value):
    encoded = value.encode("utf-8")
    return encode_field(field_number, 2, encode_varint(len(encoded)) + encoded)


def encode_bytes(field_number, value):
    return encode_field(field_number, 2, encode_varint(len(value)) + value)


def encode_int32(field_number, value):
    return encode_field(field_number, 0, encode_varint(value))


def encode_int64(field_number, value):
    return encode_field(field_number, 0, encode_varint(value))


def encode_bool(field_number, value):
    return encode_field(field_number, 0, encode_varint(1 if value else 0))


def encode_double(field_number, value):
    return encode_field(field_number, 1, struct.pack("<d", value))


def encode_float(field_number, value):
    return encode_field(field_number, 5, struct.pack("<f", value))


def encode_message(field_number, data):
    return encode_field(field_number, 2, encode_varint(len(data)) + data)


def encode(schema, values):
    """Encode a dict into protobuf bytes using a schema.

    Schema is a dict of {field_name: (field_number, type_str)}.
    type_str is one of: string, int32, int64, uint32, uint64, bool, double, float, enum, message, bytes.
    """
    result = b""
    for name, value in values.items():
        if name not in schema:
            continue
        field_number, field_type = schema[name]
        if value is None:
            continue
        if field_type == "string":
            result += encode_string(field_number, value)
        elif field_type in ("int32", "int64", "uint32", "uint64", "enum"):
            result += encode_int32(field_number, value)
        elif field_type == "bool":
            result += encode_bool(field_number, value)
        elif field_type == "double":
            result += encode_double(field_number, value)
        elif field_type == "float":
            result += encode_float(field_number, value)
        elif field_type == "bytes":
            result += encode_bytes(field_number, value)
        elif field_type == "message":
            result += encode_message(field_number, value)
    return result


def decode_packed_varints(data: bytes) -> list[int]:
    """Decode a packed repeated varint field into a list of ints."""
    values = []
    pos = 0
    while pos < len(data):
        val, pos = decode_varint(data, pos)
        values.append(val)
    return values


def encode_packed_varints(field_number: int, values: list[int]) -> bytes:
    """Encode a list of ints as a packed repeated varint field."""
    packed = b""
    for v in values:
        packed += encode_varint(v)
    return encode_field(field_number, 2, encode_varint(len(packed)) + packed)


def _skip_group(data: bytes, pos: int, field_number: int) -> int:
    """Skip a deprecated protobuf group until its matching end-group tag."""
    while pos < len(data):
        tag, pos = decode_varint(data, pos)
        wt = tag & 0x07
        fn = tag >> 3
        if wt == 4 and fn == field_number:
            return pos
        if wt == 0:
            _, pos = decode_varint(data, pos)
        elif wt == 1:
            pos += 8
        elif wt == 2:
            length, pos = decode_varint(data, pos)
            pos += length
        elif wt == 3:
            pos = _skip_group(data, pos, fn)
        elif wt == 5:
            pos += 4
    return pos


def decode(data, schema=None):
    """Decode protobuf bytes into a dict.

    If schema is provided ({field_number: (field_name, type_str)}), field names and
    types are used. Otherwise returns {field_number: raw_value}.
    """
    result = {}
    pos = 0
    while pos < len(data):
        tag, pos = decode_varint(data, pos)
        field_number = tag >> 3
        wire_type = tag & 0x07

        if wire_type == 0:  # varint
            value, pos = decode_varint(data, pos)
        elif wire_type == 1:  # 64-bit
            value = struct.unpack("<d", data[pos : pos + 8])[0]
            pos += 8
        elif wire_type == 2:  # length-delimited
            length, pos = decode_varint(data, pos)
            value = data[pos : pos + length]
            pos += length
        elif wire_type == 3:  # start group (deprecated)
            pos = _skip_group(data, pos, field_number)
            continue
        elif wire_type == 4:  # end group (handled by _skip_group)
            continue
        elif wire_type == 5:  # 32-bit
            value = struct.unpack("<f", data[pos : pos + 4])[0]
            pos += 4
        else:
            raise ValueError(f"Unknown wire type {wire_type} at pos {pos}")

        if schema and field_number in schema:
            name, field_type = schema[field_number]
            if field_type == "string" and isinstance(value, bytes):
                value = value.decode("utf-8")
            elif field_type == "message" and isinstance(value, bytes):
                pass  # caller decodes nested messages
            elif field_type == "bool" and isinstance(value, int):
                value = bool(value)

            # Handle repeated fields
            if name in result:
                existing = result[name]
                if not isinstance(existing, list):
                    result[name] = [existing]
                result[name].append(value)
            else:
                result[name] = value
        else:
            name = field_number
            if name in result:
                existing = result[name]
                if not isinstance(existing, list):
                    result[name] = [existing]
                result[name].append(value)
            else:
                result[name] = value

    return result
