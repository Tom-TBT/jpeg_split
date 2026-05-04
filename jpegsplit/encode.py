from __future__ import annotations
from .model import SOFInfo, SOSInfo
from .model import HuffTable
from .decode import DHT, SOF0, SOF2, canonical_tables

def bit_length_signed(v: int) -> int:
    v = int(v)
    if v == 0:
        return 0
    return abs(v).bit_length()


def vli_bits(v: int, size: int) -> list[int]:
    if size == 0:
        return []
    if v >= 0:
        x = v
    else:
        x = (1 << size) - 1 + v
    return [(x >> (size - 1 - k)) & 1 for k in range(size)]


def bits_to_bytes_with_stuffing(bits: list[int]) -> bytes:
    out = bytearray()
    acc = 0
    n = 0
    for b in bits:
        acc = (acc << 1) | (b & 1)
        n += 1
        if n == 8:
            out.append(acc)
            if acc == 0xFF:
                out.append(0x00)
            acc = 0
            n = 0
    if n:
        acc <<= (8 - n)
        out.append(acc)
        if acc == 0xFF:
            out.append(0x00)
    return bytes(out)


def encode_scan(blocks, sof: SOFInfo, sos: SOSInfo, tables):
    bw = []
    prev_dc = {}
    for mcu in blocks:
        for cid, coeffs in mcu:
            td = next(td for c, td, ta in sos.components if c == cid)
            ta = next(ta for c, td, ta in sos.components if c == cid)
            if cid not in prev_dc:
                prev_dc[cid] = 0
            diff = int(coeffs[0]) - prev_dc[cid]
            prev_dc[cid] = int(coeffs[0])
            size = bit_length_signed(diff)
            bw.extend(int(c) for c in tables["ht"][(0, td)].enc[size])
            bw.extend(vli_bits(diff, size))
            ac_ht = tables["ht"][(1, ta)]
            run = 0
            for k in range(1, 64):
                v = int(coeffs[k])
                if v == 0:
                    run += 1
                    continue
                while run > 15:
                    bw.extend(int(c) for c in ac_ht.enc[0xF0])
                    run -= 16
                sz = bit_length_signed(v)
                sym = (run << 4) | sz
                bw.extend(int(c) for c in ac_ht.enc[sym])
                bw.extend(vli_bits(v, sz))
                run = 0
            if run:
                bw.extend(int(c) for c in ac_ht.enc[0x00])
    return bits_to_bytes_with_stuffing(bw)


def clone_tables(tables):
    cloned = {"qt": dict(tables.get("qt", {})), "ht": {}}
    for (tc, th), ht in tables.get("ht", {}).items():
        bits = list(ht.bits)
        huffval = list(ht.huffval)
        enc, dec = canonical_tables(bits, huffval)
        cloned["ht"][(tc, th)] = HuffTable(tc, th, bits, huffval, enc, dec)
    return cloned


def _required_dc_sizes_by_table(tile_blocks, sos: SOSInfo):
    td_by_cid = {cid: td for cid, td, _ta in sos.components}
    prev_dc = {cid: 0 for cid, _td, _ta in sos.components}
    required = {}

    for mcu in tile_blocks:
        for cid, coeffs in mcu:
            if cid not in td_by_cid:
                continue
            td = td_by_cid[cid]
            diff = int(coeffs[0]) - prev_dc[cid]
            prev_dc[cid] = int(coeffs[0])
            size = bit_length_signed(diff)
            if td not in required:
                required[td] = set()
            required[td].add(size)

    return required


def ensure_tile_dc_huffman(tile_blocks, sos: SOSInfo, tables):
    required_sizes = _required_dc_sizes_by_table(tile_blocks, sos)
    for td, sizes in required_sizes.items():
        ht = tables["ht"][(0, td)]
        bits = list(ht.bits)
        huffval = list(ht.huffval)
        for size in sorted(sizes):
            if size in ht.enc or size in huffval:
                continue
            bits[15] += 1
            huffval.append(size)
        enc, dec = canonical_tables(bits, huffval)
        tables["ht"][(0, td)] = HuffTable(0, td, bits, huffval, enc, dec)
    return tables


def _build_dht_segments(tables) -> bytes:
    payload = bytearray()
    for tc, th in sorted(tables["ht"]):
        ht = tables["ht"][(tc, th)]
        payload.append(((tc & 0x0F) << 4) | (th & 0x0F))
        payload.extend(int(v) & 0xFF for v in ht.bits)
        payload.extend(int(v) & 0xFF for v in ht.huffval)

    out = bytearray()
    i = 0
    max_payload = 65533
    while i < len(payload):
        chunk = payload[i:i + max_payload]
        L = len(chunk) + 2
        out.extend((0xFF, DHT, (L >> 8) & 0xFF, L & 0xFF))
        out.extend(chunk)
        i += len(chunk)
    return bytes(out)


def make_tile_header(header: bytes, sof: SOFInfo, new_w: int, new_h: int, tables=None):
    data = bytes(header)
    out = bytearray()

    if not (len(data) >= 2 and data[0] == 0xFF and data[1] == 0xD8):
        raise ValueError("Header does not start with SOI")

    dht_bytes = _build_dht_segments(tables) if tables is not None else None
    inserted_dht = False
    found_sof = False

    i = 0
    while i < len(data):
        if data[i] != 0xFF:
            raise ValueError("Invalid marker alignment in JPEG header")
        marker = data[i + 1]

        if marker == 0xD8:
            out.extend(data[i:i + 2])
            i += 2
            continue

        if marker == 0xD9:
            out.extend(data[i:i + 2])
            i += 2
            continue

        L = (data[i + 2] << 8) | data[i + 3]
        seg = bytearray(data[i:i + 2 + L])

        if marker == DHT and dht_bytes is not None:
            if not inserted_dht:
                out.extend(dht_bytes)
                inserted_dht = True
        else:
            if marker in (SOF0, SOF2):
                seg[5] = (new_h >> 8) & 0xFF
                seg[6] = new_h & 0xFF
                seg[7] = (new_w >> 8) & 0xFF
                seg[8] = new_w & 0xFF
                found_sof = True
            if marker == 0xDA and dht_bytes is not None and not inserted_dht:
                out.extend(dht_bytes)
                inserted_dht = True
            out.extend(seg)

        i += 2 + L

    if not found_sof:
        raise ValueError("SOF not found in header")
    return bytes(out)

def rebuild_tile_jpeg(header: bytes, tile_scan: bytes):
    return header + tile_scan + b"\xFF\xD9"