"""Minimal Android binary XML (AXML) writer for building a manifest without aapt2."""
import struct

ANDROID_NS = "http://schemas.android.com/apk/res/android"

T_REFERENCE = 0x01
T_STRING = 0x03
T_INT_DEC = 0x10
T_INT_BOOLEAN = 0x12

RES_XML_TYPE = 0x0003
RES_STRING_POOL_TYPE = 0x0001
RES_XML_RESOURCE_MAP_TYPE = 0x0180
RES_XML_START_NAMESPACE_TYPE = 0x0100
RES_XML_END_NAMESPACE_TYPE = 0x0101
RES_XML_START_ELEMENT_TYPE = 0x0102
RES_XML_END_ELEMENT_TYPE = 0x0103

ATTR_IDS = {
    "theme": 0x01010000, "label": 0x01010001, "icon": 0x01010002, "name": 0x01010003,
    "permission": 0x01010006, "process": 0x01010011, "taskAffinity": 0x01010012,
    "allowTaskReparenting": 0x0101000C, "enabled": 0x0101000E, "debuggable": 0x0101000F,
    "exported": 0x01010010, "stateNotNeeded": 0x01010016, "excludeFromRecents": 0x01010017,
    "authorities": 0x01010018, "launchMode": 0x0101001D, "screenOrientation": 0x0101001E,
    "configChanges": 0x0101001F, "value": 0x01010024, "resource": 0x01010025,
    "windowSoftInputMode": 0x0101002B, "noHistory": 0x0101002D,
    "minSdkVersion": 0x0101020C, "largeHeap": 0x01010211, "versionCode": 0x0101021B,
    "versionName": 0x0101021C, "targetSdkVersion": 0x01010270, "allowBackup": 0x01010280,
    "hardwareAccelerated": 0x010102D3, "stopWithTask": 0x0101034A,
    "supportsRtl": 0x010103AF, "extractNativeLibs": 0x010104EA,
    "usesCleartextTraffic": 0x010104EC, "resizeableActivity": 0x010104F6,
    "directBootAware": 0x01010505, "roundIcon": 0x0101052C,
    "foregroundServiceType": 0x01010599, "enableOnBackInvokedCallback": 0x0101063C,
}


class Element:
    def __init__(self, tag, attrs=None, children=None):
        self.tag = tag
        self.attrs = attrs or []
        self.children = children or []


class Pool:
    def __init__(self):
        self.items = []
        self.index = {}

    def add(self, s):
        i = self.index.get(s)
        if i is None:
            i = len(self.items)
            self.items.append(s)
            self.index[s] = i
        return i


def _pool_chunk(pool):
    data = b""
    offsets = []
    for s in pool.items:
        offsets.append(len(data))
        data += struct.pack("<H", len(s)) + s.encode("utf-16-le") + b"\x00\x00"
    while len(data) % 4:
        data += b"\x00"
    strings_start = 0x1C + 4 * len(pool.items)
    body = b"".join(struct.pack("<I", o) for o in offsets)
    size = strings_start + len(data)
    return (struct.pack("<HHIIIIII", RES_STRING_POOL_TYPE, 0x1C, size,
                        len(pool.items), 0, 0, strings_start, 0) + body + data)


def _chunk(ctype, extra, body, header_size=8):
    size = 8 + len(extra) + len(body)
    return struct.pack("<HHI", ctype, header_size, size) + extra + body


def _node(ctype, extra, body):
    # XML node chunks have a fixed 0x10 header (chunk header + line + comment); the rest
    # of the payload is addressed relative to it.
    return _chunk(ctype, extra, body, 0x10)


def _ns_chunk(ctype, prefix_idx, uri_idx):
    extra = struct.pack("<IIII", 0xFFFFFFFF, 0xFFFFFFFF, prefix_idx, uri_idx)
    return _node(ctype, extra, b"")


def _start_elem(name_idx, attrs_packed, count):
    extra = struct.pack("<IIII", 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, name_idx)
    extra += struct.pack("<HHHHHH", 0x14, 0x14, count, 0, 0, 0)
    return _node(RES_XML_START_ELEMENT_TYPE, extra, attrs_packed)


def _end_elem(name_idx):
    extra = struct.pack("<IIII", 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, name_idx)
    return _node(RES_XML_END_ELEMENT_TYPE, extra, b"")


def _attr_bytes(ns_idx, name_idx, dtype, data, raw_idx=0xFFFFFFFF):
    return struct.pack("<III", ns_idx, name_idx, raw_idx) + struct.pack("<HBBI", 8, 0, dtype, data)


def build(root):
    pool = Pool()
    prefix_idx = pool.add("android")
    uri_idx = pool.add(ANDROID_NS)
    res_ids = {}

    def intern(s):
        return pool.add(s)

    def pass1(el):
        for (ns, name, kind, value) in el.attrs:
            if ns == "android":
                res_ids[intern(name)] = ATTR_IDS[name]
            else:
                intern(name)
            if kind == "string":
                intern(str(value))
        intern(el.tag)
        for ch in el.children:
            pass1(ch)

    pass1(root)

    body = [_ns_chunk(RES_XML_START_NAMESPACE_TYPE, prefix_idx, uri_idx)]

    def emit(el):
        packed = b""
        for (ns, name, kind, value) in el.attrs:
            ns_idx = uri_idx if ns == "android" else 0xFFFFFFFF
            name_idx = intern(name)
            if kind == "string":
                raw = intern(str(value))
                packed += _attr_bytes(ns_idx, name_idx, T_STRING, raw, raw)
            elif kind == "int":
                packed += _attr_bytes(ns_idx, name_idx, T_INT_DEC, int(value) & 0xFFFFFFFF)
            elif kind == "bool":
                packed += _attr_bytes(ns_idx, name_idx, T_INT_BOOLEAN, 0xFFFFFFFF if value else 0)
            elif kind == "ref":
                packed += _attr_bytes(ns_idx, name_idx, T_REFERENCE, int(value) & 0xFFFFFFFF)
            else:
                raise ValueError("attr kind " + kind)
        name_idx = intern(el.tag)
        body.append(_start_elem(name_idx, packed, len(el.attrs)))
        for ch in el.children:
            emit(ch)
        body.append(_end_elem(name_idx))

    emit(root)
    body.append(_ns_chunk(RES_XML_END_NAMESPACE_TYPE, prefix_idx, uri_idx))

    remap = [res_ids.get(i, 0) for i in range(len(pool.items))]
    map_chunk = _chunk(RES_XML_RESOURCE_MAP_TYPE, b"",
                       b"".join(struct.pack("<I", rid) for rid in remap))

    chunks = _pool_chunk(pool) + map_chunk + b"".join(body)
    return struct.pack("<HHI", RES_XML_TYPE, 0x08, 8 + len(chunks)) + chunks
