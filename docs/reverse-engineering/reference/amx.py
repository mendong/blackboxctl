#!/usr/bin/env python3
"""
amx.py -- reference parser / validator for M-VAVE BlackBox neural amp capture
containers (.am2 / .am2Data / .am2data / .am3Data), and for the on-device
AM*/CAB flash records found in M-EFCS factory .bin blobs.

Derived from analysis of the M-EFCS macOS app (libamx_parser.dylib) and of a
1686-file capture corpus.  Prior art: github.com/walterwanderley/am2manager
(Apache-2.0) for the 60-byte header field names, and
github.com/jvsobrinho/mvave-blackbox-ble (docs CC BY-SA 4.0 / code GPL-3.0).

Usage:
    python3 amx.py <path> [<path> ...]      # walk and report
    python3 amx.py --json <path>            # dump one file as JSON
"""
from __future__ import annotations

import json
import os
import struct
import sys
from dataclasses import dataclass, field, asdict

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------

HEADER_LEN   = 60          # 0x3C
AM2_PAYLOAD  = 6144        # 1536 float32
AM2_RECORD   = HEADER_LEN + AM2_PAYLOAD          # 6204
AM4_RECORD   = 7868                              # header + 1952 float32
LMT_MAGIC    = b"LMT\x00"                        # runtime sentinel appended by the DSP
LMT_LEN      = 4 + 16 * 4                        # sentinel + 16 float32
FLASH_SLOT   = 8192                              # amp slot stride in flash / factory .bin
CAB_RECORD   = 4096                              # cab (IR) record stride, 2 per flash slot
CAB_HDR      = 20
CAB_TAPS     = (CAB_RECORD - CAB_HDR - 2) // 3   # 1358
SAMPLE_RATE  = 44100                             # from calc_bias_gru: 0xac44 iterations
Q_SCALE      = 2097151.0                         # 2**21 - 1, float -> Q21 fixed point
MAX_ABS_W    = 1024.0                            # Q21 headroom

KNOWN_MAGIC  = (b"AM2\x00", b"AM3\x00", b"AM4\x00")

NAME_OFF, NAME_MAX = 4, 13    # 13 usable chars, NUL terminator at 0x11

# float32 index layout of the 1536-float AM2/AM3 payload
LAYOUT = [
    ("fir_pre",   0,    256),   # 256-tap FIR, stored time-reversed
    ("gru_Wi_a",  256,  272),   # GRU gate A input weights   (16)
    ("gru_Wi_b",  272,  288),   # GRU gate B input weights   (16)
    ("gru_Wi_c",  288,  304),   # GRU gate C input weights   (16)
    ("gru_Wh_a",  304,  560),   # GRU gate A recurrent 16x16 (256)
    ("gru_Wh_b",  560,  816),   # GRU gate B recurrent 16x16 (256)
    ("gru_Wh_c",  816,  1072),  # GRU gate C recurrent 16x16 (256)
    ("gru_vec",   1072, 1088),  # trailing 16-vector (output layer / bias)
    ("fir_post",  1088, 1344),  # 256-tap FIR, stored time-reversed
    ("aux1",      1344, 1408),  # 64-tap block
    ("aux2",      1408, 1472),  # 64-tap block
    ("aux3",      1472, 1536),  # 64-tap block
]
GRU_OFF, GRU_LEN = 256, 832     # byte offset 1084 == 0x43c in the record


# ----------------------------------------------------------------------------
# Model
# ----------------------------------------------------------------------------

@dataclass
class Capture:
    path: str
    size: int
    has_header: bool
    magic: bytes | None = None
    magic_ok: bool = False
    name: str | None = None
    name_raw: bytes | None = None
    mix: int | None = None
    level: int | None = None
    gain_max: int | None = None
    gain_min: int | None = None
    reserved_16_17: bytes | None = None
    eq: list = field(default_factory=list)     # [(freq_hz, gain_min_db, gain_max_db)] x3
    floats: object = None                      # list[float] when parsed
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self):
        d = asdict(self)
        d.pop("floats", None)
        d["magic"] = self.magic.decode("latin1") if self.magic else None
        d["name_raw"] = self.name_raw.hex() if self.name_raw else None
        d["reserved_16_17"] = self.reserved_16_17.hex() if self.reserved_16_17 else None
        return d


def _f32(buf, off, n):
    return list(struct.unpack_from("<%df" % n, buf, off))


def parse(path: str, data: bytes | None = None) -> Capture:
    if data is None:
        with open(path, "rb") as fh:
            data = fh.read()
    size = len(data)

    if size == AM2_RECORD:
        c = Capture(path=path, size=size, has_header=True)
        payload = data[HEADER_LEN:]
    elif size == AM2_PAYLOAD:
        c = Capture(path=path, size=size, has_header=False)
        payload = data
    elif size == AM2_RECORD + LMT_LEN and data[AM2_RECORD:AM2_RECORD + 4] == LMT_MAGIC:
        c = Capture(path=path, size=size, has_header=True)
        c.warnings.append("record carries a runtime LMT block (device/flash form)")
        payload = data[HEADER_LEN:AM2_RECORD]
    else:
        c = Capture(path=path, size=size, has_header=False)
        c.errors.append(
            "bad size %d: expected %d (bare payload) or %d (header+payload)"
            % (size, AM2_PAYLOAD, AM2_RECORD))
        return c

    if c.has_header:
        h = data[:HEADER_LEN]
        c.magic = h[0:4]
        c.magic_ok = c.magic in KNOWN_MAGIC
        if not c.magic_ok:
            c.errors.append("bad magic %s (expected AM2\\0 / AM3\\0)" % c.magic.hex())
            if c.magic[:2] == b"\x00\x00" and c.magic[3] == 0:
                c.warnings.append(
                    "magic looks like am2manager InitData damage "
                    "(00 00 %02x 00); byte 0 and 1 zeroed" % c.magic[2])
        c.name_raw = h[NAME_OFF:NAME_OFF + NAME_MAX + 1]
        nul = c.name_raw.find(b"\x00")
        if nul < 0:
            c.errors.append("name field is not NUL-terminated within 14 bytes")
            raw = c.name_raw
        else:
            raw = c.name_raw[:nul]
            if any(b for b in c.name_raw[nul + 1:]):
                c.warnings.append("non-zero bytes after the name NUL terminator")
        if any(b < 0x20 or b > 0x7E for b in raw):
            c.errors.append("name contains non-printable bytes: %s" % raw.hex())
            c.name = ""
        else:
            c.name = raw.decode("ascii")
        if c.name == "":
            c.warnings.append("empty name")

        c.mix, c.level, c.gain_max, c.gain_min = h[0x12], h[0x13], h[0x14], h[0x15]
        c.reserved_16_17 = h[0x16:0x18]
        if c.reserved_16_17 != b"\x00\x00":
            c.errors.append("reserved bytes 0x16..0x17 not zero: %s"
                            % c.reserved_16_17.hex())
        if c.mix > 100:
            c.errors.append("mix %d out of range 0..100" % c.mix)
        if c.gain_min > c.gain_max:
            c.warnings.append("gain_min %d > gain_max %d" % (c.gain_min, c.gain_max))

        eqf = _f32(h, 0x18, 9)
        for i in range(3):
            f, lo, hi = eqf[3 * i], eqf[3 * i + 1], eqf[3 * i + 2]
            c.eq.append((f, lo, hi))
            if not (0.0 < f < SAMPLE_RATE / 2):
                c.errors.append("eq band %d frequency %r outside (0, %d)"
                                % (i + 1, f, SAMPLE_RATE // 2))
            if lo > hi:
                c.errors.append("eq band %d gain range inverted: min %.1f > max %.1f"
                                % (i + 1, lo, hi))
            if not (-48.0 <= lo <= 48.0 and -48.0 <= hi <= 48.0):
                c.warnings.append("eq band %d gain range [%.1f, %.1f] outside "
                                  "+/-48 dB" % (i + 1, lo, hi))
            if not (lo <= 0.0 <= hi):
                c.warnings.append("eq band gain range does not bracket 0 dB")
        if c.eq[0][0] > c.eq[1][0] or c.eq[1][0] > c.eq[2][0]:
            c.warnings.append("eq band frequencies are not ascending")

    w = _f32(payload, 0, AM2_PAYLOAD // 4)
    c.floats = w
    bad = [i for i, v in enumerate(w) if v != v or v in (float("inf"), float("-inf"))]
    if bad:
        c.errors.append("%d non-finite float32 in payload, first at index %d"
                        % (len(bad), bad[0]))
    big = [i for i, v in enumerate(w) if abs(v) >= MAX_ABS_W]
    if big:
        c.errors.append("%d weights with |w| >= %.0f would overflow Q21, first at "
                        "index %d" % (len(big), MAX_ABS_W, big[0]))
    return c


def regions(c: Capture):
    """Return {region_name: list[float]} for a parsed capture."""
    return {n: c.floats[a:b] for n, a, b in LAYOUT}


def repair_magic(data: bytes, version: int = 2) -> bytes:
    """Return a copy with a well-formed AM<version> magic. Header only, no weights."""
    if len(data) != AM2_RECORD:
        raise ValueError("repair_magic needs a %d-byte record" % AM2_RECORD)
    return b"AM%d\x00" % version + data[4:]


def set_name(data: bytes, name: str) -> bytes:
    if len(data) != AM2_RECORD:
        raise ValueError("set_name needs a %d-byte record" % AM2_RECORD)
    b = name.encode("ascii")
    if len(b) > NAME_MAX:
        raise ValueError("name longer than %d ASCII characters" % NAME_MAX)
    if any(x < 0x20 or x > 0x7E for x in b):
        raise ValueError("name must be printable ASCII")
    return data[:NAME_OFF] + b.ljust(NAME_MAX + 1, b"\x00") + data[NAME_OFF + NAME_MAX + 1:]


# ----------------------------------------------------------------------------
# Flash / factory .bin records
# ----------------------------------------------------------------------------

def split_ampcab_bin(data: bytes):
    """Split a *_ampCab.bin factory blob into amp records and cab (IR) records."""
    amps, cabs = [], []
    for off in range(0, len(data), FLASH_SLOT):
        slot = data[off:off + FLASH_SLOT]
        if slot[:4] in KNOWN_MAGIC:
            amps.append((off, slot))
        elif slot[:4] == b"CAB\x00":
            for k in (0, CAB_RECORD):
                if slot[k:k + 4] == b"CAB\x00":
                    cabs.append((off + k, slot[k:k + CAB_RECORD]))
    return amps, cabs


def decode_cab(rec: bytes):
    """Decode one 4096-byte CAB record -> (name, taps as floats in -1..1)."""
    assert rec[:4] == b"CAB\x00"
    name = rec[4:18].split(b"\x00")[0].decode("latin1")
    body = rec[CAB_HDR:CAB_HDR + CAB_TAPS * 3]
    taps = [int.from_bytes(body[3 * k:3 * k + 3], "little", signed=True) / 2 ** 23
            for k in range(CAB_TAPS)]
    return name, taps


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

CAPTURE_EXT = (".am2", ".am2data", ".am3data", ".am4", ".am4data")


def walk(paths):
    for p in paths:
        if os.path.isdir(p):
            for dp, _dn, fn in os.walk(p):
                for f in sorted(fn):
                    if f.lower().endswith(CAPTURE_EXT):
                        yield os.path.join(dp, f)
        else:
            yield p


def main(argv):
    as_json = "--json" in argv
    args = [a for a in argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2

    files = list(walk(args))
    n_ok = n_warn = n_fail = 0
    fails, warns = [], []
    for p in files:
        c = parse(p)
        if as_json:
            print(json.dumps(c.to_dict(), indent=2, ensure_ascii=False))
            continue
        if c.errors:
            n_fail += 1
            fails.append((p, c.errors))
        else:
            n_ok += 1
            if c.warnings:
                n_warn += 1
                warns.append((p, c.warnings))
    if as_json:
        return 0

    print("files examined : %d" % len(files))
    print("PASS           : %d" % n_ok)
    print("  of which with warnings: %d" % n_warn)
    print("FAIL           : %d" % n_fail)
    if fails:
        print("\n--- failures ---")
        for p, errs in fails:
            print("%s" % p)
            for e in errs:
                print("    ERROR %s" % e)
    if warns:
        from collections import Counter
        cnt = Counter()
        for _p, ws in warns:
            for w in ws:
                cnt[w.split("(")[0].split(":")[0].strip()] += 1
        print("\n--- warning histogram ---")
        for k, v in cnt.most_common():
            print("  %5d  %s" % (v, k))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
