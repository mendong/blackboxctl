#!/usr/bin/env python3
"""
Live read-only validation of the M-Vave BlackBox USB SysEx protocol.

Usage:  python validate.py [codec|endpoints|ram|preset|cab|amp|flash|all]

Every command this script can emit is one of the four documented READ-ONLY
commands. midi_transport.assert_read_only() refuses anything else.
"""
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import midi_transport as T  # noqa: E402

DOC_RAW = bytes.fromhex("00592209000004080000100100000" + "1E1")
DOC_ENC = bytes.fromhex("0032094900004002090000001800000001" + "5E01")


def step_codec():
    print("=== STEP 1: offline codec self-test ===")
    got = T.encode_base128(DOC_RAW)
    print(f"doc raw          {T.hexs(DOC_RAW)}")
    print(f"doc encoded      {T.hexs(DOC_ENC)}")
    print(f"encode(doc raw)  {T.hexs(got)}")
    print(f"MATCH doc pair:  {got == DOC_ENC}")
    back = T.decode_base128(DOC_ENC)
    print(f"decode(doc enc)  {T.hexs(back)}")
    print(f"  checksum of that packet: computed {T.checksum(back):#04x} "
          f"stored {back[-1]:#04x} valid={T.checksum(back) == back[-1]}")
    print(f"  encode(decode(doc enc)) == doc enc : {T.encode_base128(back) == DOC_ENC}")
    print(f"checksum(doc raw) = {T.checksum(DOC_RAW):#04x} (doc says 0xe1)")
    import random
    ok = all(T.decode_base128(T.encode_base128(b))[:len(b)] == b
             for n in range(1, 220)
             for b in [bytes(random.randrange(256) for _ in range(n))])
    print(f"roundtrip fuzz 1..219 bytes: {ok}")


def step_endpoints():
    print("=== STEP 1b: CoreMIDI endpoints ===")
    s, d = T.list_endpoints()
    for x in s:
        print("SOURCE     ", x)
    for x in d:
        print("DESTINATION", x)


def _decode_92(p, label):
    """Decode a 92-byte preset/state block against memory_map.md."""
    BLOCK = {0: "FX", 1: "AMP", 2: "MOD", 3: "DLY", 4: "REV", 5: "CAB"}
    FX = ["NoiseGate++", "Boost", "Compress", "AIGate MS"]
    MOD = ["Chorus", "Phaser", "Tremolo", "Flanger", "Vibrato", "Univibe", "Autofilter"]
    DLY = ["Analog", "Duck", "Dtape", "Dual", "Lofi"]
    REV = ["Room", "Hall", "Swell", "Spring", "Shimmer", "Cloud"]
    print(f"--- decode {label} (92 bytes) ---")
    print(f"  raw92 {T.hexs(p)}")
    print(f"  [00] patch volume      = {p[0]} (hi byte {p[1]})")
    print(f"  [02] routing           = {[BLOCK.get(x, x) for x in p[2:8]]}  raw {T.hexs(p[2:8])}")
    names = ["FX", "AMP", "MOD", "DLY", "REV", "CAB"]
    print(f"  [08] on/off            = " +
          ", ".join(f"{n}={'ON' if p[8+i] else 'off'}" for i, n in enumerate(names)))
    print(f"  [0E] models            = FX={p[14]}({FX[p[14]] if p[14] < len(FX) else '?'}) "
          f"AMP={p[15]} MOD={p[16]}({MOD[p[16]] if p[16] < len(MOD) else '?'}) "
          f"DLY={p[17]}({DLY[p[17]] if p[17] < len(DLY) else '?'}) "
          f"REV={p[18]}({REV[p[18]] if p[18] < len(REV) else '?'}) CAB={p[19]}")
    KN = {"FX": (0x14, ["k1", "k2", "k3", "k4", "k5", "k6"]),
          "AMP": (0x20, ["Gain", "Level", "Bass", "Mid", "Treble", "-"]),
          "MOD": (0x2C, ["Speed", "Depth", "Mix", "k4", "k5", "-"]),
          "DLY": (0x38, ["Time", "FB", "Mix", "k4", "k5", "k6"]),
          "REV": (0x44, ["Decay", "Mix", "HP", "LP", "k5", "-"]),
          "CAB": (0x50, ["Level", "L-Cut", "H-Cut", "-", "-", "-"])}
    for blk, (start, labels) in KN.items():
        vals = [int.from_bytes(p[start + 2 * i: start + 2 * i + 2], "little") for i in range(6)]
        print(f"  [{start:02X}] {blk:3s} knobs      = " +
              ", ".join(f"{labels[i]}={vals[i]}" for i in range(6)))


def step_ram(bb):
    print("=== STEP 2: Request RAM Dump ===")
    sx, dec = bb.request(T.cmd_ram_dump(), "RAM Dump", timeout=3.0)
    for d in dec:
        print(f"  -> decoded length {len(d)} (doc says 107)")
        if len(d) >= 107 and d[0] == 0 and d[1] == 0x59:
            _decode_92(d[14:106], "RAM dump payload d[14:106]")
    return dec


def step_preset(bb):
    print("=== STEP 3: Preset Sync / Stream ===")
    sx, dec = bb.request(T.cmd_preset_sync(), "Preset Sync", timeout=3.0)
    for d in dec:
        if len(d) >= 15:
            pid = d[14]
            print(f"  -> len {len(d)}, offset14 = {pid} (0x{pid:02X}) -> "
                  f"P{pid+1:02d} {'IN RANGE P01..P80' if 0 <= pid <= 79 else 'OUT OF RANGE'}")
    return dec


def step_names(bb, which):
    addr = T.CAB_NAMES_ADDR if which == "cab" else T.AMP_NAMES_ADDR
    print(f"=== STEP: Read String Blocks ({which.upper()} names, addr {T.hexs(addr)}) ===")
    want = lambda dec: _count_names(dec) >= 20  # noqa: E731
    sx, dec = bb.request(T.cmd_read_string_block(addr), f"{which} names",
                         timeout=8.0, quiet_for=1.5, want=want)
    buf = bytearray()
    for k, d in enumerate(dec):
        payload = d[14:] if (len(d) >= 14 and d[0] == 0x00 and d[1] == 0x59) else d
        if k == len(dec) - 1 and payload:
            payload = payload[:-1]   # last byte of the final packet is the checksum
        buf.extend(payload)
    print(f"  accumulated payload ({len(buf)} bytes): {T.hexs(buf)}")
    names = T.parse_names(bytes(buf))[:20]
    print(f"  parsed {len(names)} names:")
    for i, (raw, clean) in enumerate(names, 1):
        print(f"    {i:2d}  raw={raw!r}  clean={clean!r}")
    return names


def _count_names(dec):
    buf = bytearray()
    for d in dec:
        buf.extend(d[14:] if (len(d) >= 14 and d[0] == 0x00 and d[1] == 0x59) else d)
    return sum(1 for b in buf if b == 0)


def step_flash(bb, index):
    print(f"=== STEP 6: Read Flash Preset index {index} (P{index+1:02d}), "
          f"address {index*92} ===")
    sx, dec = bb.request(T.cmd_read_flash_preset(index), f"flash preset {index}",
                         timeout=4.0, quiet_for=1.0)
    for d in dec:
        print(f"  -> decoded length {len(d)}")
        if len(d) >= 106:
            _decode_92(d[14:106], f"flash preset {index} payload d[14:106]")
    return dec


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("codec", "all"):
        step_codec()
        print()
    if what in ("endpoints", "all"):
        step_endpoints()
        print()
    if what == "codec" or what == "endpoints":
        return
    bb = T.BlackBox().open()
    try:
        time.sleep(0.4)
        if what in ("ram", "all"):
            step_ram(bb); print()
        if what in ("preset", "all"):
            step_preset(bb); print()
        if what in ("cab", "all"):
            step_names(bb, "cab"); print()
        if what in ("amp", "all"):
            step_names(bb, "amp"); print()
        if what.startswith("flash:"):
            step_flash(bb, int(what.split(":")[1])); print()
        elif what in ("flash", "all"):
            step_flash(bb, 0); print()
            step_flash(bb, 2); print()
            step_flash(bb, 40); print()
    finally:
        bb.close()


if __name__ == "__main__":
    main()
