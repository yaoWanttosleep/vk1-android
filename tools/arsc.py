"""Minimal resources.arsc writer: one mipmap drawable, enough for android:icon."""
import struct

RES_TABLE_TYPE = 0x0002
RES_TABLE_PACKAGE_TYPE = 0x0200
RES_TABLE_TYPE_SPEC_TYPE = 0x0202
RES_TABLE_TYPE_TYPE = 0x0201
RES_STRING_POOL_TYPE = 0x0001

TYPE_STRING = 0x03
CONFIG_SIZE = 64
PACKAGE_ID = 0x7F
TYPE_ID = 0x01
TYPE_NAME = "mipmap"
ENTRY_NAME = "ic_launcher"
DRAWABLE_PATH = "res/mipmap/ic_launcher.png"


def _pool(strings):
    """ResStringPool with UTF-16 payloads — the conservative encoding aapt used."""
    data = b""
    offsets = []
    for s in strings:
        offsets.append(len(data))
        data += struct.pack("<H", len(s)) + s.encode("utf-16-le") + b"\x00\x00"
    while len(data) % 4:
        data += b"\x00"
    body = b"".join(struct.pack("<I", o) for o in offsets)
    strings_start = 0x1C + 4 * len(strings)
    size = strings_start + len(data)
    return struct.pack("<HHIIIIII", RES_STRING_POOL_TYPE, 0x1C, size,
                       len(strings), 0, 0, strings_start, 0) + body + data


def _config():
    return struct.pack("<I", CONFIG_SIZE) + b"\x00" * (CONFIG_SIZE - 4)


def _chunk(ctype, header_fields, header_size, payload):
    size = 8 + len(header_fields) + len(payload)
    assert size == header_size + len(payload), (size, header_size, len(payload))
    return struct.pack("<HHI", ctype, header_size, size) + header_fields + payload


def build():
    values = _pool([DRAWABLE_PATH])
    type_names = _pool([TYPE_NAME])
    key_names = _pool([ENTRY_NAME])

    # ResTable_typeSpec: header 16 (id/res0/res1/entryCount), then one flags word.
    spec_fields = struct.pack("<BBHI", TYPE_ID, 0, 0, 1)
    type_spec = _chunk(RES_TABLE_TYPE_SPEC_TYPE, spec_fields, 16, struct.pack("<I", 0))

    # ResTable_type: header is 20 + config; then entry offsets, then the entries.
    entry = struct.pack("<HHI", 8, 0, 0) + struct.pack("<HBBI", 8, 0, TYPE_STRING, 0)
    entries_start = (20 + CONFIG_SIZE) + 4
    type_fields = struct.pack("<BBH", TYPE_ID, 0, 0) + struct.pack("<II", 1, entries_start) + _config()
    type_chunk = _chunk(RES_TABLE_TYPE_TYPE, type_fields, 20 + CONFIG_SIZE,
                        struct.pack("<I", 0) + entry)

    # ResTable_package: 288-byte header (id, 128 UTF-16 chars of name, four offsets,
    # typeIdOffset), followed by the type/key string pools and the two chunks above.
    header_size = 0x11C          # classic ResTable_package: no typeIdOffset field
    fields = struct.pack("<I", PACKAGE_ID)
    fields += "com.vk1.pet".encode("utf-16-le").ljust(256, b"\x00")[:256]
    payload = type_names + key_names + type_spec + type_chunk
    fields += struct.pack("<IIII", header_size, 1, header_size + len(type_names), 1)
    package = _chunk(RES_TABLE_PACKAGE_TYPE, fields, header_size, payload)

    chunks = values + package
    return struct.pack("<HHII", RES_TABLE_TYPE, 12, 12 + len(chunks), 1) + chunks
