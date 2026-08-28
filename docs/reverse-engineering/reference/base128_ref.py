#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M-Vave / CUVAVE proprietary protocol -- reference implementation of the
transport primitives:

  * base128_encode / base128_decode : the continuous 8-to-7 bit repacking used
    to squeeze arbitrary 8-bit packets through a 7-bit-clean MIDI SysEx body.
  * checksum                        : the trailing verification byte.
  * frame / unframe                 : the 00 59 <cmd> <len24> <payload> <cs>
    message envelope.
  * to_sysex / from_sysex           : F0 ... F7 wrapping over USB MIDI.

Derived from (and cross-checked against) three independent implementations:

  - pferreir/cuvave-midi        src/parser.rs  encode()/decode()   GPL-3.0
  - jvsobrinho/mvave-blackbox-edit  app.js  encodeSysEx()/decodeSysEx()  MIT
  - michaelforney's CUVAVE Looper Pro protocol gist (prose description)

and validated against empirical dumps from cbix/mvave-chocolate-sysex.

This file is a standalone reference: `python3 base128_ref.py` runs every test
vector as an assert and prints a report.  No device I/O happens here.

License: GPL-3.0 (derived from GPL-3.0 reference logic).
Protocol documentation attribution: https://github.com/jvsobrinho/mvave-blackbox-ble
(CC BY-SA 4.0, Joel Victor).
"""

from typing import Iterable, List, Sequence, Tuple

# ---------------------------------------------------------------------------
# Base-128 continuous 8-to-7 bit packing
# ---------------------------------------------------------------------------
#
# Model: treat the whole raw byte string as one arbitrarily long little-endian
# integer (byte 0 is the least significant byte, and within each byte bit 0 is
# the least significant bit).  Re-express that integer in base 128 and emit the
# base-128 digits least-significant first, one digit per output byte.
#
# Bit order is LSB-first end to end.  Output byte k carries raw bits
# [7k .. 7k+6] of the concatenated bit stream.
#
# 7 raw bytes (56 bits) map exactly onto 8 encoded bytes (8 x 7 = 56 bits).
#
# Trailing partial group: the encoder ALWAYS emits one final byte holding the
# leftover high bits, even when nothing is left over (then it emits 0x00).  So
# len(encoded) == ceil(len(raw) * 8 / 7) + (1 if len(raw) % 7 == 0 else 0),
# equivalently floor(len(raw) * 8 / 7) + 1 for every len(raw) >= 0.
#
# The decoder simply drops the leftover high bits at the end, so it round-trips
# whether or not that final byte is present.  Real devices are observed to omit
# a trailing all-zero byte (see cbix "Discovery" vector below), so a decoder
# MUST tolerate both lengths.


def base128_encode(raw: Sequence[int]) -> List[int]:
    """8-bit bytes -> 7-bit-safe bytes.  Every output byte is 0x00..0x7F."""
    out: List[int] = []
    accum = 0
    bits = 0
    for b in raw:
        accum |= (b & 0xFF) << bits
        bits += 8
        while bits >= 7:
            out.append(accum & 0x7F)
            accum >>= 7
            bits -= 7
    out.append(accum & 0x7F)  # unconditional trailing group
    return out


def base128_decode(enc: Sequence[int]) -> List[int]:
    """7-bit-safe bytes -> 8-bit bytes.  Leftover high bits are discarded."""
    out: List[int] = []
    accum = 0
    bits = 0
    for b in enc:
        accum |= (b & 0x7F) << bits
        bits += 7
        if bits >= 8:
            out.append(accum & 0xFF)
            accum >>= 8
            bits -= 8
    return out


def base128_encode_rust(raw: Sequence[int]) -> List[int]:
    """Literal transcription of cuvave-midi's parser.rs encode(), kept only to
    prove the two formulations agree bit for bit."""
    out: List[int] = []
    bit_num = 0
    accum = 0
    for b in raw:
        accum |= (b & 0xFF) << (bit_num & 0x1F)
        bit_num += 1
        while True:
            out.append(accum & 0x7F)
            accum >>= 7
            if bit_num < 7:
                break
            bit_num -= 7
    out.append(accum & 0x7F)
    return out


def base128_decode_rust(enc: Sequence[int]) -> List[int]:
    """Literal transcription of cuvave-midi's parser.rs decode()."""
    out: List[int] = []
    bit_num = 0
    last_val = 0
    for b in enc:
        mask = 0xFFFFFFFF >> (32 - bit_num) if bit_num else 0
        accum = b & mask
        if bit_num > 0:
            out.append(((last_val & 0x7F) | ((accum << (8 - bit_num)) & 0xFF)) & 0xFF)
        last_val = b >> bit_num
        bit_num = (bit_num + 1) % 8
    if last_val > 0:
        out.append(last_val)
    return out


# ---------------------------------------------------------------------------
# Checksum
# ---------------------------------------------------------------------------
#
# checksum = (0xFF - (sum of payload bytes)) & 0xFF
#
# "payload" = the bytes AFTER the 6-byte envelope header (00 59 <cmd> <len24>)
# and BEFORE the checksum byte itself, i.e. frame[6:-1].
#
# jvsobrinho's app.js sums frame[4:-1] instead.  That is the same number for
# every packet whose payload is shorter than 65536 bytes, because frame[4] and
# frame[5] are the two high bytes of the 24-bit length and are therefore 0x00.
# Both are given here; `checksum` is the structurally correct one.


def checksum(payload: Sequence[int]) -> int:
    return (0xFF - (sum(payload) & 0xFF)) & 0xFF


def checksum_from_offset4(frame_without_cs: Sequence[int]) -> int:
    """app.js formulation: sum frame[4 .. end], where end excludes the cs byte."""
    return (0xFF - (sum(frame_without_cs[4:]) & 0xFF)) & 0xFF


# ---------------------------------------------------------------------------
# Message envelope:  00 59 | cmd(1) | length(3, LE) | payload(length) | cs(1)
# ---------------------------------------------------------------------------

HEADER = (0x00, 0x59)

CMD_INIT_ACK = 0x00
CMD_QUERY_NAME_VERSION = 0x11
CMD_ERASE = 0x21
CMD_WRITE = 0x22
CMD_READ = 0x23
CMD_VENDOR_24 = 0x24


def frame(cmd: int, payload: Sequence[int]) -> List[int]:
    n = len(payload)
    body = [0x00, 0x59, cmd & 0xFF, n & 0xFF, (n >> 8) & 0xFF, (n >> 16) & 0xFF]
    body += list(payload)
    body.append(checksum(payload))
    return body


def unframe(msg: Sequence[int]) -> Tuple[int, List[int]]:
    """Returns (cmd, payload). Raises ValueError on a malformed frame."""
    if len(msg) < 7:
        raise ValueError("frame too short")
    if msg[0] != 0x00 or msg[1] != 0x59:
        raise ValueError("bad header %02X %02X" % (msg[0], msg[1]))
    n = msg[3] | (msg[4] << 8) | (msg[5] << 16)
    payload = list(msg[6:6 + n])
    if len(payload) != n:
        raise ValueError("declared length %d, got %d" % (n, len(payload)))
    if len(msg) != 6 + n + 1:
        raise ValueError("frame length %d, expected %d" % (len(msg), 6 + n + 1))
    if msg[-1] != checksum(payload):
        raise ValueError("checksum %02X, expected %02X" % (msg[-1], checksum(payload)))
    return msg[2], payload


# Memory access payloads carried inside CMD_READ / CMD_WRITE:
#   [space(1)] [addr(4, LE)] [length(3, LE)] [data...]

def mem_payload(space: int, addr: int, length: int, data: Sequence[int] = ()) -> List[int]:
    return ([space & 0xFF]
            + list(addr.to_bytes(4, "little"))
            + list(length.to_bytes(3, "little"))
            + list(data))


def parse_mem_payload(payload: Sequence[int]) -> Tuple[int, int, int, List[int]]:
    space = payload[0]
    addr = int.from_bytes(bytes(payload[1:5]), "little")
    length = int.from_bytes(bytes(payload[5:8]), "little")
    return space, addr, length, list(payload[8:])


# ---------------------------------------------------------------------------
# USB MIDI SysEx wrapping
# ---------------------------------------------------------------------------

def to_sysex(raw: Sequence[int]) -> List[int]:
    return [0xF0] + base128_encode(raw) + [0xF7]


def from_sysex(sysex: Sequence[int]) -> List[int]:
    if len(sysex) < 3 or sysex[0] != 0xF0 or sysex[-1] != 0xF7:
        raise ValueError("not a SysEx message")
    return base128_decode(sysex[1:-1])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def h(s: str) -> List[int]:
    return [int(x, 16) for x in s.split()]


def hx(b: Iterable[int]) -> str:
    return " ".join("%02X" % x for x in b)


# ---------------------------------------------------------------------------
# TEST VECTORS
# ---------------------------------------------------------------------------

def main() -> None:
    passed = 0
    notes: List[str] = []

    def check(name: str, got, want) -> None:
        nonlocal passed
        assert got == want, "%s\n  got  %s\n  want %s" % (name, hx(got) if isinstance(got, list) else got,
                                                          hx(want) if isinstance(want, list) else want)
        passed += 1
        print("PASS  %s" % name)

    print("=" * 78)
    print("BASE-128 ENCODE / DECODE")
    print("=" * 78)

    # ---- Vector 1 -------------------------------------------------------
    # Source: pferreir/cuvave-midi src/parser.rs, test_encode_1 / test_decode_1.
    # A CUVAVE Cube Baby "write 1 byte to space 5, addr 0x80000009" command.
    V1_RAW = h("00 59 22 09 00 00 05 09 00 00 80 01 00 00 01 6F")
    V1_ENC = h("00 32 09 49 00 00 40 02 09 00 00 00 18 00 00 00 01 5E 01")
    check("V1 encode  (cuvave parser.rs test_encode_1)", base128_encode(V1_RAW), V1_ENC)
    check("V1 decode  (cuvave parser.rs test_decode_1)", base128_decode(V1_ENC), V1_RAW)
    check("V1 checksum", checksum(V1_RAW[6:-1]), 0x6F)
    check("V1 unframe", unframe(V1_RAW), (0x22, V1_RAW[6:-1]))
    check("V1 mem fields (space, addr, len, data)",
          parse_mem_payload(unframe(V1_RAW)[1]), (0x05, 0x80000009, 1, [0x01]))

    # ---- Vector 2 -------------------------------------------------------
    # Source: pferreir/cuvave-midi src/parser.rs, test_encode_2.
    # "Request name/version" -- command 0x11 with an empty payload.
    V2_RAW = h("00 59 11 00 00 00 FF")
    V2_ENC = h("00 32 45 00 00 00 40 7F 00")
    check("V2 encode  (cuvave parser.rs test_encode_2)", base128_encode(V2_RAW), V2_ENC)
    check("V2 decode", base128_decode(V2_ENC), V2_RAW)
    check("V2 frame() rebuild", frame(0x11, []), V2_RAW)
    # 7 raw bytes -> 8 significant + 1 all-zero trailing byte.
    check("V2 trailing byte is zero-filler", V2_ENC[-1], 0x00)
    # The device drops that trailing zero on the wire (cbix Discovery dump):
    V2_ENC_SHORT = h("00 32 45 00 00 00 40 7F")
    check("V2 decode tolerates dropped trailing zero (cbix wire form)",
          base128_decode(V2_ENC_SHORT), V2_RAW)

    # ---- Vector 3 -------------------------------------------------------
    # Source: pferreir/cuvave-midi src/lib.rs, deserialize_set_parameters test.
    # Given as a complete SysEx message including F0/F7.
    V3_SYSEX = h("F0 00 32 09 49 00 00 40 02 1B 00 00 00 18 00 00 00 01 3A 01 F7")
    V3_RAW = h("00 59 22 09 00 00 05 1B 00 00 80 01 00 00 01 5D")
    check("V3 from_sysex (cuvave lib.rs deserialize_set_parameters)",
          from_sysex(V3_SYSEX), V3_RAW)
    check("V3 to_sysex", to_sysex(V3_RAW), V3_SYSEX)
    check("V3 checksum (computed, not quoted anywhere)", checksum(V3_RAW[6:-1]), 0x5D)
    check("V3 mem fields", parse_mem_payload(unframe(V3_RAW)[1]),
          (0x05, 0x8000001B, 1, [0x01]))  # 0x80000000 + Preset::B(0x10) + DelaySection(0x0b)

    # ---- Vector 4 -------------------------------------------------------
    # Source: cbix/mvave-chocolate-sysex README, "OK" response emitted by the
    # controller after each config change.  Empirical device output.
    V4_SYSEX = h("F0 00 32 01 08 00 00 00 00 7F 01 F7")
    V4_RAW = from_sysex(V4_SYSEX)
    check("V4 cbix OK-response decodes to the documented 8-byte ACK",
          V4_RAW, h("00 59 00 01 00 00 00 FF"))
    check("V4 ACK round-trips through unframe", unframe(V4_RAW), (0x00, [0x00]))
    check("V4 re-encode reproduces the wire bytes", to_sysex(V4_RAW), V4_SYSEX)

    # ---- Vector 5 -------------------------------------------------------
    # Source: cbix/mvave-chocolate-sysex README, "switch to Program change C".
    # Empirical device input, captured with aseqsend on a real M-Vave Chocolate.
    V5_SYSEX = h("F0 00 32 09 49 00 00 00 02 00 00 00 00 10 00 00 00 0B 5E 03 F7")
    V5_RAW = from_sysex(V5_SYSEX)
    check("V5 cbix 'Program change C' decodes to a well-formed 0x22 write",
          V5_RAW, h("00 59 22 09 00 00 04 00 00 00 00 01 00 00 0B EF"))
    check("V5 checksum validates (unframe would raise otherwise)",
          unframe(V5_RAW)[0], 0x22)
    check("V5 mem fields", parse_mem_payload(unframe(V5_RAW)[1]),
          (0x04, 0x00000000, 1, [0x0B]))
    check("V5 re-encode reproduces the wire bytes", to_sysex(V5_RAW), V5_SYSEX)

    # ---- Vector 6 -------------------------------------------------------
    # Source: cbix/mvave-chocolate-sysex README, "TRS = MIDI".
    V6_SYSEX = h("F0 00 32 09 49 00 00 00 02 0C 00 00 00 10 00 00 00 01 5A 03 F7")
    V6_RAW = from_sysex(V6_SYSEX)
    check("V6 cbix 'TRS = MIDI' decodes to a valid frame",
          V6_RAW, h("00 59 22 09 00 00 04 0C 00 00 00 01 00 00 01 ED"))
    check("V6 cbix 'TRS = MIDI' round-trips", to_sysex(V6_RAW), V6_SYSEX)
    check("V6 mem fields", parse_mem_payload(unframe(V6_RAW)[1]),
          (0x04, 0x0000000C, 1, [0x01]))

    # ---- Vector 6b ------------------------------------------------------
    # Source: cbix/mvave-chocolate-sysex README, "Discovery" response.
    # Proves command 0x11 is a read-only device-identity query: the payload is
    # the device name as NUL-padded ASCII.
    V6B_SYSEX = h("F0 00 32 45 58 01 00 00 23 6F 5E 51 1B 44 4E 1C 36 5F 60 4C 09 "
                  "03 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 60 37 F7")
    V6B_CMD, V6B_PAYLOAD = unframe(from_sysex(V6B_SYSEX))
    check("V6b cbix Discovery response is cmd 0x11", V6B_CMD, 0x11)
    check("V6b Discovery payload is the ASCII device name",
          bytes(V6B_PAYLOAD).rstrip(b"\x00").decode("ascii"), "FootCtrl_031")
    check("V6b Discovery response round-trips",
          to_sysex(from_sysex(V6B_SYSEX)), V6B_SYSEX)

    # ---- Vector 7 -------------------------------------------------------
    # Source: cbix/mvave-chocolate-sysex README, "Discovery" request.
    # Same message as V2 but as it actually appears on the wire.
    V7_SYSEX = h("F0 00 32 45 00 00 00 40 7F F7")
    check("V7 cbix Discovery request == query-name-version",
          from_sysex(V7_SYSEX), h("00 59 11 00 00 00 FF"))

    # ---- Vector 8 -------------------------------------------------------
    # Source: pferreir/cuvave-midi src/parser.rs, test_decode_3 ("Mystery1").
    V8_ENC = h("00 32 11 49 00 00 00 02 64 0E 00 00 10 00 00 00 00 1E 02")
    V8_RAW = base128_decode(V8_ENC)
    check("V8 cuvave Mystery1 decodes to a 0x24 command",
          V8_RAW, h("00 59 24 09 00 00 04 64 07 00 00 01 00 00 00 8F"))
    check("V8 Mystery1 payload matches lib.rs Message::Mystery1",
          unframe(V8_RAW)[1], h("04 64 07 00 00 01 00 00 00"))

    print()
    print("=" * 78)
    print("BLACKBOX COMMAND TEMPLATES  (built from first principles, then")
    print("compared to the byte strings hard-coded in bbedit/app.js)")
    print("=" * 78)

    RAM = 0x10000000   # live RAM image of the active preset, 92 bytes
    SPACE = 0x04       # memory space byte used by the Blackbox for RAM+flash
    SPACE_STR = 0x05   # memory space byte used for the name-string blocks

    # Request RAM dump -- app.js requestRamDump()
    got = frame(CMD_READ, mem_payload(SPACE, RAM, 92))
    check("BB read RAM dump == app.js requestRamDump()",
          got, h("00 59 23 08 00 00 04 00 00 00 10 5C 00 00 8F"))

    # Preset-sync poll -- app.js requestCurrentPresetId()
    got = frame(CMD_READ, mem_payload(SPACE, 0x20000000, 4))
    check("BB read current-preset-id == app.js requestCurrentPresetId()",
          got, h("00 59 23 08 00 00 04 00 00 00 20 04 00 00 D7"))

    # Read AMP name block -- app.js startHandshake()
    got = frame(CMD_READ, mem_payload(SPACE_STR, 0x90000000, 280))
    check("BB read AMP names == app.js startHandshake() AMP packet",
          got, h("00 59 23 08 00 00 05 00 00 00 90 18 01 00 51"))

    # Read CAB name block -- app.js processHandshakeBlock()
    got = frame(CMD_READ, mem_payload(SPACE_STR, 0x80000000, 280))
    check("BB read CAB names == app.js processHandshakeBlock() CAB packet",
          got, h("00 59 23 08 00 00 05 00 00 00 80 18 01 00 61"))

    # Read flash preset slot 0 -- docs "Read Flash Preset", ADDR = index * 92
    got = frame(CMD_READ, mem_payload(SPACE, 3 * 92, 92))
    check("BB read flash preset #3 (addr 276 = 0x114)",
          got, h("00 59 23 08 00 00 04 14 01 00 00 5C 00 00 8A"))

    # --- write-side templates, reproduced for completeness. NOT sent here. ---
    got = frame(CMD_WRITE, mem_payload(SPACE, RAM + 0x08, 1, [0x01]))
    check("BB toggle FX on == docs/app.js toggleModule(0x08, true)",
          got, h("00 59 22 09 00 00 04 08 00 00 10 01 00 00 01 E1"))

    got = frame(CMD_WRITE, mem_payload(SPACE, RAM + 0x20, 2, [50, 0]))
    check("BB set AMP Gain=50 == app.js changeKnob(0x20, 50) shape",
          got, h("00 59 22 0A 00 00 04 20 00 00 10 02 00 00 32 00 97"))

    got = frame(CMD_WRITE, mem_payload(SPACE, RAM + 0x02, 6, [4, 0, 1, 2, 3, 5]))
    check("BB routing write has the fixed 0xD4 checksum claimed in the docs",
          got[-1], 0xD4)
    check("BB routing write == app.js changeRouting([4,0,1,2,3,5])",
          got, h("00 59 22 0E 00 00 04 02 00 00 10 06 00 00 04 00 01 02 03 05 D4"))

    got = frame(CMD_WRITE, mem_payload(SPACE, 0xE0000000 + 0x07, 1, [0x01]))
    check("BB load preset P08 == app.js loadPreset(7)",
          got, h("00 59 22 09 00 00 04 07 00 00 E0 01 00 00 01 12"))

    got = frame(CMD_WRITE, mem_payload(SPACE, 0xF0000000, 0))
    check("BB commit/UI-refresh == docs 'Commit / UI Update'",
          got, h("00 59 22 08 00 00 04 00 00 00 F0 00 00 00 0B"))

    # Save to flash: 14-byte header + 92 data + checksum = 107 bytes.
    demo = list(range(92))
    got = frame(CMD_WRITE, mem_payload(SPACE, 5 * 92, 92, demo))
    check("BB flash-save frame length is 107", len(got), 107)
    check("BB flash-save header matches app.js savePresetToSlot(5, ...)",
          got[:14], h("00 59 22 64 00 00 04 CC 01 00 00 5C 00 00"))
    check("BB flash-save data starts at offset 14", got[14:106], demo)

    print()
    print("=" * 78)
    print("REGRESSION GUARD: the published CC BY-SA example is internally")
    print("inconsistent -- do NOT unit-test an encoder against it.")
    print("=" * 78)
    DOC_RAW = h("00 59 22 09 00 00 04 08 00 00 10 01 00 00 01 E1")
    DOC_CLAIMED_ENC = h("00 32 09 49 00 00 40 02 09 00 00 00 18 00 00 00 01 5E 01")
    check("doc raw packet is itself checksum-valid", unframe(DOC_RAW)[0], 0x22)
    check("doc encoded array does NOT come from the doc raw packet",
          base128_encode(DOC_RAW) != DOC_CLAIMED_ENC, True)
    check("true encoding of the doc raw packet",
          base128_encode(DOC_RAW),
          h("00 32 09 49 00 00 00 02 08 00 00 00 11 00 00 00 01 42 03"))
    check("the doc's encoded array actually belongs to the cuvave V1 packet",
          base128_decode(DOC_CLAIMED_ENC), V1_RAW)

    print()
    print("=" * 78)
    print("STRUCTURAL PROPERTIES")
    print("=" * 78)

    # app.js's "sum from offset 4" and the structural "sum the payload" agree
    # for every frame whose payload is < 65536 bytes.
    for name, f in [("toggle", h("00 59 22 09 00 00 04 08 00 00 10 01 00 00 01 E1")),
                    ("ramdump", h("00 59 23 08 00 00 04 00 00 00 10 5C 00 00 8F")),
                    ("routing", h("00 59 22 0E 00 00 04 02 00 00 10 06 00 00 04 00 01 02 03 05 D4")),
                    ("ack", h("00 59 00 01 00 00 00 FF"))]:
        check("checksum(payload) == app.js checksum(frame[4:]) for %s" % name,
              checksum(f[6:-1]), checksum_from_offset4(f[:-1]))

    # The two published encoder formulations agree, on random-ish data.
    import random
    random.seed(0x5922)
    for n in range(0, 130):
        blob = [random.randrange(256) for _ in range(n)]
        assert base128_encode(blob) == base128_encode_rust(blob), n
        assert base128_decode(base128_encode(blob)) == blob, n
        # A trailing all-zero encoded byte may be dropped on the wire, but only
        # when the remaining bytes still carry >= 8*len(raw) bits.
        e = base128_encode(blob)
        if e[-1] == 0 and 7 * (len(e) - 1) >= 8 * n:
            assert base128_decode(e[:-1]) == blob, n
    passed += 1
    print("PASS  JS-style and Rust-style encoders agree for all lengths 0..129")
    passed += 1
    print("PASS  encode->decode round-trips for all lengths 0..129")

    # Length law.
    for n in range(0, 200):
        assert len(base128_encode([0xFF] * n)) == (n * 8) // 7 + 1, n
    passed += 1
    print("PASS  len(encode(raw)) == floor(len(raw)*8/7) + 1 for lengths 0..199")

    # Every encoded byte is 7-bit clean and can never collide with F0/F7.
    for n in range(0, 60):
        blob = [random.randrange(256) for _ in range(n)]
        assert all(0 <= x <= 0x7F for x in base128_encode(blob))
    passed += 1
    print("PASS  every encoded byte is in 0x00..0x7F")

    print()
    print("=" * 78)
    print("%d checks passed, 0 failed" % passed)
    print("=" * 78)
    for n in notes:
        print(n)


if __name__ == "__main__":
    main()
