from .model import SOFInfo, SOSInfo, HuffTable, QuantTable
import numpy as np

SOI = 0xD8  # Start of Image
EOI = 0xD9  # End of Image
SOS = 0xDA  # Start of Scan
DQT = 0xDB  # Define Quantization Table
DHT = 0xC4  # Define Huffman Table
SOF0 = 0xC0  # Start of Frame (Baseline DCT)
SOF2 = 0xC2  # Start of Frame (Extended DCT)
DRI = 0xDD  # Define Restart Interval

class BitReader:
    """
    A helper class to read bits from a byte stream,
    handling JPEG-specific byte stuffing and restart markers.

    """
    def __init__(self, data: bytes):
        self.data = data
        self.i = 0
        self.buf = []

    def _next_byte(self):
        if self.i >= len(self.data):
            return None
        b = self.data[self.i]
        self.i += 1
        if b == 0xFF and self.i < len(self.data):
            n = self.data[self.i]
            if n == 0x00:
                self.i += 1
            elif 0xD0 <= n <= 0xD7:
                self.i += 1
                self.buf = []
                return self._next_byte()
            else:
                self.i -= 1
                return None
        return b

    def read_bit(self):
        """
        Reads the next bit from the stream,
        handling byte stuffing and restart markers.
        """
        if not self.buf:
            # Buffer is empty, read the next byte
            b = self._next_byte()
            if b is None:
                return None
            # Convert byte to bits
            self.buf = [(b >> (7 - k)) & 1 for k in range(8)]
        return self.buf.pop(0)  # Return the next bit, removing it from the buffer

def u16be(b, i):
    """
    Reads a 16-bit big-endian unsigned integer from byte array b starting at index i.
    """
    return (b[i] << 8) | b[i + 1]


def canonical_tables(bits_counts: list[int], huffvals: list[int]):
    """
    Given the bits counts and huffman values, constructs the
    canonical Huffman encoding and decoding tables.
    """
    enc = {}
    dec = {}
    code = 0
    p = 0  #
    for length in range(1, 17):
        code <<= 1
        for _ in range(bits_counts[length - 1]):
            sym = huffvals[p]
            s = f"{code:0{length}b}"
            enc[sym] = s
            dec[s] = sym
            code += 1
            p += 1
    return enc, dec


def decode_symbol(reader: BitReader, ht: HuffTable):
    code = ""
    while len(code) <= 16:
        bit = reader.read_bit()
        if bit is None:
            raise EOFError
        code += str(bit)
        if code in ht.dec:
            return ht.dec[code]
    raise ValueError("Invalid Huffman code")


def receive_extend(reader: BitReader, s: int):
    if s == 0:
        return 0
    v = 0
    for _ in range(s):
        bit = reader.read_bit()
        if bit is None:
            raise EOFError
        v = (v << 1) | bit
    if v < (1 << (s - 1)):
        v -= (1 << s) - 1
    return v


def parse_jpeg(data: bytes):
    b = np.frombuffer(data, dtype=np.uint8)
    i = 0
    if not (b[i] == 0xFF and b[i + 1] == SOI):
        raise ValueError("Not a JPEG")
    i += 2
    header_end = None
    sof = None
    sos = None
    restart_interval = 0
    tables = {"qt": {}, "ht": {}}
    header_parts = [bytes(b[:2])]
    while i < len(b):
        while i < len(b) and b[i] != 0xFF:
            i += 1
        if i >= len(b):
            break
        while i < len(b) and b[i] == 0xFF:
            i += 1
        marker = int(b[i]); i += 1
        if marker == SOS:
            L = u16be(b, i)
            seg = bytes(b[i - 2:i + L])
            header_parts.append(seg)
            i += L
            header_end = i
            ns = b[i - L + 2]
            p = i - L + 3
            comps = []
            for _ in range(ns):
                cid = int(b[p]); tdta = int(b[p + 1])
                comps.append((cid, tdta >> 4, tdta & 0x0F))
                p += 2
            ss, se, ahal = int(b[p]), int(b[p + 1]), int(b[p + 2])
            sos = SOSInfo(comps, ss, se, ahal >> 4, ahal & 0x0F)
            break
        L = u16be(b, i)
        seg = bytes(b[i - 2:i + L])
        header_parts.append(seg)
        payload = bytes(b[i + 2:i + L])
        if marker == DQT:
            p = 0
            while p < len(payload):
                pq_tq = payload[p]; p += 1
                pq = pq_tq >> 4; tq = pq_tq & 0x0F
                if pq != 0:
                    raise ValueError("16-bit quant tables unsupported here")
                vals = np.array(list(payload[p:p+64]), dtype=np.uint8).reshape(8, 8)
                tables["qt"][tq] = QuantTable(tq, vals)
                p += 64
        elif marker == DHT:
            p = 0
            while p < len(payload):
                tc_th = payload[p]; p += 1
                tc = tc_th >> 4; th = tc_th & 0x0F
                bits = list(payload[p:p+16]); p += 16
                total = sum(bits)
                huffval = list(payload[p:p+total]); p += total
                enc, dec = canonical_tables(bits, huffval)
                tables["ht"][(tc, th)] = HuffTable(tc, th, bits, huffval, enc, dec)
        elif marker in (SOF0, SOF2):
            precision = payload[0]
            height = u16be(payload, 1)
            width = u16be(payload, 3)
            nf = payload[5]
            p = 6
            comps = []
            for _ in range(nf):
                cid = payload[p]; hv = payload[p + 1]; tq = payload[p + 2]
                comps.append({"id": cid, "h": hv >> 4, "v": hv & 0x0F, "tq": tq})
                p += 3
            sof = SOFInfo(marker, precision, height, width, comps)
        elif marker == DRI:
            restart_interval = u16be(payload, 0)
        i += L
    if header_end is None:
        raise ValueError("No SOS")
    scan = bytes(b[header_end:])
    return b"", b"", bytes().join(header_parts), scan, sof, sos, tables, restart_interval


def decode_scan(scan: bytes, sof: SOFInfo, sos: SOSInfo, tables, restart_interval=0):
    comp_map = {c["id"]: c for c in sof.components}
    scan_comp_info = [(cid, td, ta, comp_map[cid]) for cid, td, ta in sos.components]
    max_h = max(c["h"] for c in sof.components)
    max_v = max(c["v"] for c in sof.components)
    mcu_w = 8 * max_h
    mcu_h = 8 * max_v
    mcus_x = (sof.width + mcu_w - 1) // mcu_w
    mcus_y = (sof.height + mcu_h - 1) // mcu_h
    reader = BitReader(scan)
    blocks = []
    prev_dc = {cid: 0 for cid, _, _, _ in scan_comp_info}
    for mcu_idx in range(mcus_x * mcus_y):
        if restart_interval and mcu_idx % restart_interval == 0 and mcu_idx != 0:
            prev_dc = {cid: 0 for cid, _, _, _ in scan_comp_info}
        mcu = []
        for cid, td, ta, comp in scan_comp_info:
            for _vy in range(comp["v"]):
                for _hx in range(comp["h"]):
                    dht = tables["ht"][(0, td)]
                    s = decode_symbol(reader, dht)
                    diff = receive_extend(reader, s)
                    dc = prev_dc[cid] + diff
                    prev_dc[cid] = dc
                    ac_ht = tables["ht"][(1, ta)]
                    coeffs = np.zeros(64, dtype=np.int32)
                    coeffs[0] = dc
                    k = 1
                    while k < 64:
                        sym = decode_symbol(reader, ac_ht)
                        if sym == 0x00:
                            break
                        if sym == 0xF0:
                            k += 16
                            continue
                        run = sym >> 4
                        sz = sym & 0x0F
                        k += run
                        if k >= 64:
                            break
                        coeffs[k] = receive_extend(reader, sz)
                        k += 1
                    mcu.append((cid, coeffs))
        blocks.append(mcu)
    return blocks
