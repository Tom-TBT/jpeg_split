from __future__ import annotations
from .model import SOFInfo, SOSInfo
from .decode import SOF0, SOF2

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


def make_tile_header(header: bytes, sof: SOFInfo, new_w: int, new_h: int):
    data = bytearray(header)
    i = 0
    while i < len(data) - 1:
        if data[i] == 0xFF and data[i + 1] in (SOF0, SOF2):
            L = (data[i + 2] << 8) | data[i + 3]
            data[i + 5] = (new_h >> 8) & 0xFF
            data[i + 6] = new_h & 0xFF
            data[i + 7] = (new_w >> 8) & 0xFF
            data[i + 8] = new_w & 0xFF
            return bytes(data)
        i += 1
    raise ValueError("SOF not found in header")

def rebuild_tile_jpeg(header: bytes, tile_scan: bytes):
    return header + tile_scan + b"\xFF\xD9"