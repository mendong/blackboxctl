"""Wire protocol for the M-Vave BlackBox: Base-128 codec, frames, memory map.

Pure standard library. Nothing in this module touches hardware; it only builds
and parses byte strings, so it is safe to import and exercise anywhere.

Attribution
-----------
The protocol documented here was reverse engineered by the community:

* https://github.com/jvsobrinho/mvave-blackbox-ble  - protocol documentation by
  Joel Victor, licensed CC BY-SA 4.0; reference code GPL-3.0.
* https://github.com/jvsobrinho/mvave-blackbox-edit - Web Bluetooth editor, MIT.
* https://github.com/pferreir/cuvave-midi           - Base-128 codec, GPL-3.0.

This file is GPL-3.0 (see ../LICENSE and ../NOTICE).

Every constant below is annotated CONFIRMED (observed on the owner's own pedal,
see docs/reverse-engineering/device-validation.md) or HYPOTHESIS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

# ---------------------------------------------------------------------------
# Base-128 codec
# ---------------------------------------------------------------------------
#
# CONFIRMED: continuous LSB-first 8-to-7 bit repacking. Output byte k carries
# raw bit positions 7k..7k+6. The encoder always emits a final group, so
# len(encode(raw)) == len(raw) * 8 // 7 + 1. Two independently sourced
# implementations (bbedit's JS and cuvave-midi's Rust) agree bit for bit, and
# every packet built with this codec was answered correctly by the device.
#
# DO NOT unit-test this against the worked example in the upstream
# `usb_sysex_protocol.md`. That example's raw and encoded lines DO NOT
# correspond to each other - it is a documentation defect, not a codec defect:
#
#   encode(00 59 22 09 00 00 04 08 00 00 10 01 00 00 01 E1)
#       = 00 32 09 49 00 00 00 02 08 00 00 00 11 00 00 00 01 42 03
#   but the doc prints
#         00 32 09 49 00 00 40 02 09 00 00 00 18 00 00 00 01 5E 01
#   and decode(that) = 00 59 22 09 00 00 05 09 00 00 80 01 00 00 01 6F,
#   a structurally valid frame whose stored checksum 0x6F validates, and which
#   re-encodes to the doc's encoded line bit-exactly.
#
# So the doc pasted an encoded packet from a different capture beside an
# unrelated raw packet. The regression fixture to use instead is the real
# 340-byte SysEx -> 295-byte frame pair logged from this pedal; see
# tests/fixtures/device_frames.py and device-validation.md STEP 1 / STEP 4.


def base128_encode(data: bytes) -> bytes:
    """Pack 8-bit bytes into 7-bit SysEx data bytes, LSB-first and continuous."""
    out = bytearray()
    accum = 0
    bits = 0
    for byte in data:
        accum |= byte << bits
        bits += 8
        while bits >= 7:
            out.append(accum & 0x7F)
            accum >>= 7
            bits -= 7
    out.append(accum & 0x7F)
    return bytes(out)


def base128_decode(enc: bytes) -> bytes:
    """Unpack 7-bit SysEx data bytes back into 8-bit bytes. Leftover bits drop."""
    out = bytearray()
    accum = 0
    bits = 0
    for byte in enc:
        accum |= byte << bits
        bits += 7
        if bits >= 8:
            out.append(accum & 0xFF)
            accum >>= 8
            bits -= 8
    return bytes(out)


SYSEX_START = 0xF0
SYSEX_END = 0xF7


def sysex_wrap(raw: bytes) -> bytes:
    """Encode a raw command frame and wrap it as a complete SysEx message."""
    return bytes([SYSEX_START]) + base128_encode(raw) + bytes([SYSEX_END])


def sysex_unwrap(msg: bytes) -> bytes:
    """Strip F0/F7 and Base-128 decode one complete SysEx message."""
    if len(msg) < 2 or msg[0] != SYSEX_START or msg[-1] != SYSEX_END:
        raise ValueError("not a complete SysEx message (missing F0 ... F7)")
    return base128_decode(msg[1:-1])


# ---------------------------------------------------------------------------
# Checksums
# ---------------------------------------------------------------------------


def checksum_tx(frame: Sequence[int]) -> int:
    """Outbound checksum: 0xFF - sum(frame[4:-1]), as published upstream.

    CONFIRMED (offline): reproduces every documented literal (8F, D7, 51, 61,
    E1, D4, 0B). CONFIRMED (predecessor module on hardware): all seven commands
    built this way were accepted and answered by the pedal.

    This formula is only distinguishable from :func:`checksum_rx` when
    ``byte[4] != 0``, i.e. when the payload is 248 bytes or more. No outbound
    frame in that region has ever been transmitted, so which formula the pedal
    wants there is UNKNOWN. :func:`build_frame` refuses to build one.
    """
    return (0xFF - (sum(frame[4:len(frame) - 1]) & 0xFF)) & 0xFF


def checksum_rx(frame: Sequence[int]) -> int:
    """Inbound checksum: 0xFF - sum(frame[5:-1]).

    CONFIRMED empirically on this device (by the predecessor transport module;
    re-derived offline here from the logged hex in device-validation.md).
    Replies whose byte[4] is non-zero - the two 295-byte name blocks, byte[4]
    == 0x01 - validate only when the sum starts at offset 5.

    Reproducible figures: 7 requests were transmitted and 7 unique reply frames
    were observed (29 inbound SysEx messages in the logs collapse to those 7).
    Offset 5 validates 7/7 unique replies; offset 4 validates 5/7, failing on
    exactly the two name blocks. Offset 5 is also the natural rule under the
    confirmed field model: "everything after magic + length".
    """
    return (0xFF - (sum(frame[5:len(frame) - 1]) & 0xFF)) & 0xFF


def hexs(data: Iterable[int]) -> str:
    """Uppercase space-separated hex, the format used in the RE documentation."""
    return bytes(data).hex(" ").upper()


# ---------------------------------------------------------------------------
# Frame model
# ---------------------------------------------------------------------------
#
# CONFIRMED on every packet observed on this device: 7 requests transmitted and
# 7 unique reply frames returned (the 29 inbound SysEx messages in
# scratchpad/proto/log_*.txt collapse to those 7 unique frames).
#
#     magic(3) | length LE16 = len(payload) + 8 | space LE16
#              | address LE32 | size LE24 | payload | checksum
#
# The published docs describe this same layout as "command type / routing /
# target id / padding / sub-address", which is a field misalignment: their
# "command type" byte is the low byte of the length, and their "AMP names base
# address 90 18 01 00" is really address 0x90000000 plus the 24-bit size 280.

MAGIC_READ = bytes((0x00, 0x59, 0x23))
"""Read header. The only header this tool will ever transmit unattended."""

MAGIC_WRITE = bytes((0x00, 0x59, 0x22))
"""RAM/flash write header. Never transmitted to this pedal, ever, by anything in
this project. Every builder that emits it requires an explicit
:class:`WriteConsent`, and :meth:`transport.BlackBox.send` requires one too."""

HEADER_LEN = 14
"""Bytes before the payload in any frame. CONFIRMED: payload starts at 14."""

SPACE_PARAM = 0x0400
"""Address space for parameter/preset memory. CONFIRMED."""

SPACE_STRING = 0x0500
"""Address space for the amp/cab name string blocks. CONFIRMED."""

ADDR_PRESET_BASE = 0x00000000
"""Flash preset array base; slot n is at n * PRESET_SIZE. CONFIRMED."""

ADDR_LIVE_RAM = 0x10000000
"""Live, currently sounding 92-byte preset image. CONFIRMED."""

ADDR_CURRENT_PRESET = 0x20000000
"""Active preset id register (4 bytes, id at payload[0]). CONFIRMED."""

ADDR_LOAD_PRESET = 0xE0000000
"""Preset-load trigger: write 0x01 to ADDR_LOAD_PRESET + preset_id. HYPOTHESIS."""

ADDR_COMMIT = 0xF0000000
"""Zero-length write forces an OLED refresh / RAM reload. HYPOTHESIS."""

ADDR_CAB_NAMES = 0x80000000
"""20 x 14-byte CAB/IR name records, 280 bytes. CONFIRMED."""

ADDR_AMP_NAMES = 0x90000000
"""20 x 14-byte AMP capture name records, 280 bytes. CONFIRMED."""

PRESET_SIZE = 92
"""Bytes per preset image. CONFIRMED (0x5C)."""

PRESET_COUNT = 80
"""Preset slots P01..P80. HYPOTHESIS.

Evidence is a vendor PDF and bbedit's app.js:227 - neither is an observation of
THIS pedal. The highest flash index ever read here is 40 (P41), so anything
above that is unverified. This matters: check_preset_index is the only bound on
cmd_write_flash_preset's target address, so if the real device has fewer slots
this constant is the difference between a refused frame and a write past the end
of the preset array. Test that settles it: read flash index 79 and index 80 and
see which one answers.
"""

NAME_STRIDE = 14
"""Fixed-width name record. CONFIRMED: 19 consecutive deltas of exactly 14."""

NAME_COUNT = 20
"""20 amp slots and 20 cab slots. CONFIRMED."""

NAME_TABLE_SIZE = NAME_STRIDE * NAME_COUNT  # 280

RAM_DUMP_FRAME_LEN = 107
"""HEADER_LEN + PRESET_SIZE + 1. CONFIRMED on the wire."""

PRESET_SYNC_FRAME_LEN = 19
"""CONFIRMED on the wire; active preset id at frame[14]."""

ACK_FRAME = bytes((0x00, 0x59, 0x00, 0x01, 0x00, 0x00, 0x00, 0xFF))
"""Documented success acknowledgement. HYPOTHESIS: never observed here, because
no write was ever transmitted.

Note it is only 8 bytes, i.e. shorter than HEADER_LEN + 1, so it does NOT fit
the confirmed field model and :func:`parse_frame` raises "frame too short" on
it. Either the upstream doc transcribed it wrongly or acknowledgements use a
different shape entirely. Compare against a real reply only after a write has
actually been performed - which has not happened."""


@dataclass(frozen=True)
class Frame:
    """A decoded protocol frame."""

    magic: bytes
    length: int
    space: int
    address: int
    size: int
    payload: bytes
    checksum: int
    checksum_ok: bool
    raw: bytes

    @property
    def is_read(self) -> bool:
        return self.magic == MAGIC_READ

    @property
    def is_write(self) -> bool:
        return self.magic == MAGIC_WRITE

    @property
    def length_ok(self) -> bool:
        """The confirmed invariant length == len(payload) + 8."""
        return self.length == len(self.payload) + 8

    @property
    def size_ok(self) -> bool:
        """The confirmed invariant size == len(payload) for a reply."""
        return self.size == len(self.payload)

    @property
    def well_formed(self) -> bool:
        return self.checksum_ok and self.length_ok and self.size_ok


MAX_TX_PAYLOAD = 247
"""Largest payload build_frame will assemble.

248 bytes would make length == 256, so byte[4] becomes non-zero and
checksum_tx and checksum_rx diverge. No observation distinguishes the two
formulas there, and build_frame must never emit a frame its own parse_frame
rejects, so the undetermined region is refused rather than guessed."""


def build_frame(magic: bytes, space: int, address: int, size: int,
                payload: bytes = b"") -> bytes:
    """Assemble a frame and append the outbound checksum."""
    if len(magic) != 3:
        raise ValueError("magic must be 3 bytes")
    if not 0 <= address <= 0xFFFFFFFF:
        raise ValueError(f"address {address:#x} does not fit in 32 bits")
    if not 0 <= size <= 0xFFFFFF:
        raise ValueError(f"size {size} does not fit in 24 bits")
    if len(payload) > MAX_TX_PAYLOAD:
        raise ValueError(
            f"payload is {len(payload)} bytes; refusing to build a frame with "
            f"more than {MAX_TX_PAYLOAD}. At 248 bytes the length field reaches "
            f"256, byte[4] stops being zero, and the outbound (offset 4) and "
            f"inbound (offset 5) checksum formulas disagree. Nothing observed "
            f"on this pedal says which one it wants there, so the frame would "
            f"be a guess - and parse_frame would reject our own output.")
    body = bytearray(magic)
    body += (len(payload) + 8).to_bytes(2, "little")
    body += space.to_bytes(2, "little")
    body += address.to_bytes(4, "little")
    body += size.to_bytes(3, "little")
    body += payload
    body.append(0x00)                      # checksum placeholder
    body[-1] = checksum_tx(body)
    return bytes(body)


def parse_frame(raw: bytes) -> Frame:
    """Decompose a raw frame. Does not raise on a bad checksum; reports it."""
    if len(raw) < HEADER_LEN + 1:
        raise ValueError(f"frame too short ({len(raw)} bytes): {hexs(raw)}")
    return Frame(
        magic=raw[0:3],
        length=int.from_bytes(raw[3:5], "little"),
        space=int.from_bytes(raw[5:7], "little"),
        address=int.from_bytes(raw[7:11], "little"),
        size=int.from_bytes(raw[11:14], "little"),
        payload=raw[HEADER_LEN:-1],
        checksum=raw[-1],
        checksum_ok=raw[-1] == checksum_rx(raw),
        raw=bytes(raw),
    )


# ---------------------------------------------------------------------------
# Read commands - safe, all four CONFIRMED against the owner's pedal
# ---------------------------------------------------------------------------


def build_read(address: int, size: int, space: int = SPACE_PARAM) -> bytes:
    """Generic memory read request. Read-only by construction (magic 00 59 23)."""
    return build_frame(MAGIC_READ, space, address, size)


def cmd_ram_dump() -> bytes:
    """Read the live 92-byte preset image. -> 00 59 23 08 00 00 04 ... 8F"""
    return build_read(ADDR_LIVE_RAM, PRESET_SIZE)


def cmd_preset_sync() -> bytes:
    """Read the active preset id register. -> 19-byte reply, id at frame[14]."""
    return build_read(ADDR_CURRENT_PRESET, 4)


def cmd_read_flash_preset(index0: int) -> bytes:
    """Read stored preset slot `index0` (0-based) without loading it."""
    check_preset_index(index0)
    return build_read(ADDR_PRESET_BASE + index0 * PRESET_SIZE, PRESET_SIZE)


def cmd_read_amp_names() -> bytes:
    """Read the 20 amp capture slot names."""
    return build_read(ADDR_AMP_NAMES, NAME_TABLE_SIZE, SPACE_STRING)


def cmd_read_cab_names() -> bytes:
    """Read the 20 cabinet / IR slot names."""
    return build_read(ADDR_CAB_NAMES, NAME_TABLE_SIZE, SPACE_STRING)


def check_preset_index(index0: int) -> None:
    """Validate a 0-based protocol preset index. UI numbering is 1-based (P01)."""
    if not 0 <= index0 < PRESET_COUNT:
        raise ValueError(
            f"preset index {index0} out of range 0..{PRESET_COUNT - 1} "
            f"(protocol is 0-based; the pedal displays P01..P{PRESET_COUNT:02d})")


def check_slot_number(slot1: int, what: str = "slot") -> None:
    """Validate a 1-based amp/cab slot number as the user types it."""
    if not 1 <= slot1 <= NAME_COUNT:
        raise ValueError(f"{what} {slot1} out of range 1..{NAME_COUNT}")


# ---------------------------------------------------------------------------
# Read-only allowlist gate
# ---------------------------------------------------------------------------


class UnsafePacket(RuntimeError):
    """Raised when a packet fails the read-only gate."""


MAX_READ_SIZE = NAME_TABLE_SIZE                # 280
"""Largest read this tool will ever request.

The biggest legitimate read is a 280-byte name table. Anything larger is a DMA
request for a region nobody has mapped, and what the firmware does with an
oversized read is UNTESTED - so it is refused rather than tried."""


def _read_allowlist() -> list[tuple[int, int, int, str]]:
    """(space, first address, last address, description) regions reads may target.

    Everything here has been read from this pedal successfully. The two
    documented write triggers, ADDR_LOAD_PRESET (0xE0000000) and ADDR_COMMIT
    (0xF0000000), are deliberately absent: they exist to cause side effects, and
    what a *read* at a trigger register does is untested and unknown.
    """
    return [
        (SPACE_PARAM, ADDR_PRESET_BASE,
         ADDR_PRESET_BASE + PRESET_COUNT * PRESET_SIZE - 1, "flash preset array"),
        (SPACE_PARAM, ADDR_LIVE_RAM, ADDR_LIVE_RAM + PRESET_SIZE - 1, "live RAM"),
        (SPACE_PARAM, ADDR_CURRENT_PRESET, ADDR_CURRENT_PRESET + 3,
         "current preset id"),
        (SPACE_STRING, ADDR_CAB_NAMES, ADDR_CAB_NAMES + NAME_TABLE_SIZE - 1,
         "CAB/IR name table"),
        (SPACE_STRING, ADDR_AMP_NAMES, ADDR_AMP_NAMES + NAME_TABLE_SIZE - 1,
         "AMP name table"),
    ]


def assert_read_only(raw: bytes) -> None:
    """Hard gate. Refuse anything that is not one of the confirmed read commands.

    Checks, in order: length, write magic, read magic, empty payload, address
    space, an address+size allowlist of regions actually read from this pedal,
    and the outbound checksum. Everything else is refused.

    This is the gate every device command in this package passes through. It is
    exercised by tests/test_read_gate.py, including a 300k-frame fuzz.
    """
    if len(raw) < HEADER_LEN + 1:
        raise UnsafePacket(f"REFUSED: packet too short: {hexs(raw)}")
    if raw[0:3] == MAGIC_WRITE:
        raise UnsafePacket(
            f"REFUSED: 00 59 22 is the WRITE header. Never sent by a read path. "
            f"{hexs(raw)}")
    if raw[0:3] != MAGIC_READ:
        raise UnsafePacket(f"REFUSED: header is not 00 59 23: {hexs(raw)}")
    frame = parse_frame(raw)
    if frame.length != 8 or len(frame.payload) != 0:
        raise UnsafePacket(
            f"REFUSED: a read request carries no payload, got {len(frame.payload)} "
            f"bytes: {hexs(raw)}")
    if frame.space not in (SPACE_PARAM, SPACE_STRING):
        raise UnsafePacket(
            f"REFUSED: address space {frame.space:#06x} is neither "
            f"{SPACE_PARAM:#06x} nor {SPACE_STRING:#06x}: {hexs(raw)}")
    if frame.size == 0:
        raise UnsafePacket(f"REFUSED: zero-size read: {hexs(raw)}")
    if frame.size > MAX_READ_SIZE:
        raise UnsafePacket(
            f"REFUSED: read size {frame.size} exceeds the {MAX_READ_SIZE}-byte "
            f"ceiling (the largest mapped region is the {NAME_TABLE_SIZE}-byte "
            f"name table). An oversized DMA read is untested on this firmware: "
            f"{hexs(raw)}")
    last = frame.address + frame.size - 1
    for space, first, region_last, what in _read_allowlist():
        if frame.space == space and first <= frame.address and last <= region_last:
            break
    else:
        raise UnsafePacket(
            f"REFUSED: {frame.size} bytes at {frame.address:#010x} in space "
            f"{frame.space:#06x} is not inside any region this tool has ever "
            f"read from the pedal. Allowed: "
            + "; ".join(f"{w} {f:#010x}..{l:#010x} (space {s:#06x})"
                        for s, f, l, w in _read_allowlist())
            + f". Note 0xE0000000 (load-preset trigger) and 0xF0000000 (commit) "
              f"are excluded on purpose - they are documented WRITE triggers and "
              f"the firmware's behaviour on a read there is unknown: {hexs(raw)}")
    if raw[-1] != checksum_tx(raw):
        raise UnsafePacket(f"REFUSED: bad checksum: {hexs(raw)}")


# ---------------------------------------------------------------------------
# Write commands
# ---------------------------------------------------------------------------
#
# NOT YET ENABLED. No write frame has ever been transmitted to this pedal, and
# nothing in this package will transmit one without an explicit WriteConsent
# object naming a WRITE_PATHS key. Because every WritePath below currently has
# hardware_confirmed=False, transport.BlackBox.send refuses all of them: there
# is at present NO reachable path from any CLI command to the wire with magic
# 00 59 22. tests/test_no_write_path.py asserts exactly that.


@dataclass(frozen=True)
class WriteConsent:
    """Capability object required to build or transmit a state-changing frame.

    A bare boolean is not enough: it is too easy to pass by accident from a REPL
    or a future script, and it carries no record of *what* was consented to.
    Every field must be set deliberately.

    Parameters
    ----------
    path_key:
        Which :data:`WRITE_PATHS` entry this consent authorises. Consent for one
        write path never authorises another.
    confirmed_by_user:
        The human said yes, in this session, to this specific action.
    accept_unverified:
        The caller has read :attr:`WritePath.evidence` and accepts that the
        address/encoding is HYPOTHESIS, not confirmed on this pedal.
    allow_flash:
        Additionally authorises a frame that rewrites the permanent flash preset
        array. Required on top of everything else. Flash writes can destroy the
        owner's presets and are the only irreversible operation here.
    """

    path_key: str
    confirmed_by_user: bool = False
    accept_unverified: bool = False
    allow_flash: bool = False

    def authorise(self, path_key: str) -> "WritePath":
        """Validate this consent against a write path, or raise UnsafePacket."""
        path = WRITE_PATHS.get(path_key)
        if path is None:
            raise UnsafePacket(f"REFUSED: unknown write path {path_key!r}")
        if self.path_key != path_key:
            raise UnsafePacket(
                f"REFUSED: consent was granted for write path "
                f"{self.path_key!r}, not {path_key!r}. Consent is per-action.")
        if not self.confirmed_by_user:
            raise UnsafePacket(
                f"REFUSED: {path_key}: WriteConsent.confirmed_by_user is False. "
                f"No state-changing frame is built without a human saying yes.")
        if not path.hardware_confirmed and not self.accept_unverified:
            raise UnsafePacket(
                f"REFUSED: {path_key}: this write path is NOT confirmed on this "
                f"pedal. {path.evidence} Pass "
                f"WriteConsent(accept_unverified=True) only if you understand "
                f"that the address and encoding are a hypothesis.")
        if path.touches_flash and not self.allow_flash:
            raise UnsafePacket(
                f"REFUSED: {path_key} writes the permanent flash preset array "
                f"and WriteConsent.allow_flash is False. This is the one "
                f"irreversible operation in this protocol.")
        return path


@dataclass(frozen=True)
class WritePath:
    """One state-changing command and how well it is actually verified."""

    key: str
    description: str
    hardware_confirmed: bool
    touches_flash: bool
    evidence: str


WRITE_PATHS: dict[str, WritePath] = {
    "load-preset": WritePath(
        key="load-preset",
        description="Load preset slot N into live RAM (no flash write)",
        hardware_confirmed=False,
        touches_flash=False,
        evidence=("Documented upstream and built by bbedit, but device-validation.md "
                  "records that NO write path of any kind was transmitted to this "
                  "pedal. The address 0xE0000000 + id is a reparse of bbedit's "
                  "literal, not an observation."),
    ),
    "set-knob": WritePath(
        key="set-knob",
        description="Write one 16-bit knob value into live RAM",
        hardware_confirmed=False,
        touches_flash=False,
        evidence=("Address 0x10000000 + dump_index is HYPOTHESIS(high): it decodes "
                  "every read correctly, but no write was ever sent to confirm the "
                  "direction."),
    ),
    "set-toggle": WritePath(
        key="set-toggle",
        description="Turn one effect block on or off in live RAM",
        hardware_confirmed=False,
        touches_flash=False,
        evidence="Same as set-knob: read-direction evidence only.",
    ),
    "set-model": WritePath(
        key="set-model",
        description="Select a model / capture slot for one block in live RAM",
        hardware_confirmed=False,
        touches_flash=False,
        evidence="Same as set-knob: read-direction evidence only.",
    ),
    "set-routing": WritePath(
        key="set-routing",
        description="Reorder the six-block signal chain in live RAM",
        hardware_confirmed=False,
        touches_flash=False,
        evidence="Same as set-knob: read-direction evidence only.",
    ),
    "commit": WritePath(
        key="commit",
        description="Zero-length write that forces an OLED refresh",
        hardware_confirmed=False,
        touches_flash=False,
        evidence=("Documentation only. bbedit never sends it, so not even a second "
                  "implementation corroborates the address 0xF0000000."),
    ),
    "restore": WritePath(
        key="restore",
        description="Write a full 92-byte preset image into a FLASH slot",
        hardware_confirmed=False,
        touches_flash=True,
        evidence=("Write Flash Save permanently rewrites a slot and can destroy the "
                  "owner's presets. Unconfirmed on this pedal and deliberately "
                  "untested."),
    ),
}


def cmd_load_preset(index0: int, *, consent: WriteConsent) -> bytes:
    """Build Load Preset. HYPOTHESIS - see WRITE_PATHS['load-preset'].

    Requires ``consent=WriteConsent(path_key="load-preset", ...)``.
    """
    consent.authorise("load-preset")
    check_preset_index(index0)
    return build_frame(MAGIC_WRITE, SPACE_PARAM, ADDR_LOAD_PRESET + index0, 1,
                       bytes((0x01,)))


def cmd_write_byte(dump_index: int, value: int, *,
                   consent: WriteConsent) -> bytes:
    """Build a 1-byte live-RAM poke (toggle or model). HYPOTHESIS.

    Requires ``consent`` for ``set-toggle`` or ``set-model``; which of the two
    is up to the caller, since the frame is identical.
    """
    if consent.path_key not in ("set-toggle", "set-model"):
        raise UnsafePacket(
            f"REFUSED: a 1-byte RAM poke needs consent for 'set-toggle' or "
            f"'set-model', got {consent.path_key!r}")
    consent.authorise(consent.path_key)
    if not 0 <= dump_index < PRESET_SIZE:
        raise ValueError(f"dump index {dump_index} out of range 0..{PRESET_SIZE - 1}")
    if not 0 <= value <= 0xFF:
        raise ValueError(f"byte value {value} out of range 0..255")
    return build_frame(MAGIC_WRITE, SPACE_PARAM, ADDR_LIVE_RAM + dump_index, 1,
                       bytes((value,)))


def cmd_write_u16(dump_index: int, value: int, *,
                  consent: WriteConsent) -> bytes:
    """Build a 2-byte little-endian live-RAM poke (a knob). HYPOTHESIS.

    Requires ``consent=WriteConsent(path_key="set-knob", ...)``.
    """
    consent.authorise("set-knob")
    if not 0 <= dump_index < PRESET_SIZE - 1:
        raise ValueError(f"dump index {dump_index} out of range 0..{PRESET_SIZE - 2}")
    if not 0 <= value <= 0xFFFF:
        raise ValueError(f"u16 value {value} out of range 0..65535")
    return build_frame(MAGIC_WRITE, SPACE_PARAM, ADDR_LIVE_RAM + dump_index, 2,
                       value.to_bytes(2, "little"))


def cmd_write_routing(order: Sequence[int], *,
                      consent: WriteConsent) -> bytes:
    """Build Change Routing from a permutation of block ids 0..5. HYPOTHESIS.

    Requires ``consent=WriteConsent(path_key="set-routing", ...)``.
    """
    consent.authorise("set-routing")
    if sorted(order) != list(range(6)):
        raise ValueError(
            f"routing must be a permutation of 0..5, got {list(order)}")
    return build_frame(MAGIC_WRITE, SPACE_PARAM, ADDR_LIVE_RAM + 0x02, 6,
                       bytes(order))


def cmd_commit(*, consent: WriteConsent) -> bytes:
    """Build the Commit / UI-refresh write. HYPOTHESIS, documentation only.

    Requires ``consent=WriteConsent(path_key="commit", ...)``.
    """
    consent.authorise("commit")
    return build_frame(MAGIC_WRITE, SPACE_PARAM, ADDR_COMMIT, 0)


def cmd_write_flash_preset(index0: int, image: bytes, *,
                           consent: WriteConsent) -> bytes:
    """Build Write Flash Save. DANGEROUS and IRREVERSIBLE. HYPOTHESIS.

    Requires ``consent=WriteConsent(path_key="restore", confirmed_by_user=True,
    accept_unverified=True, allow_flash=True)`` - all four. This permanently
    rewrites a preset slot. It has never been transmitted to this pedal and
    transport.BlackBox.send refuses it regardless of consent while
    ``WRITE_PATHS["restore"].hardware_confirmed`` is False.
    """
    consent.authorise("restore")
    check_preset_index(index0)
    if len(image) != PRESET_SIZE:
        raise ValueError(f"preset image must be {PRESET_SIZE} bytes, got {len(image)}")
    return build_frame(MAGIC_WRITE, SPACE_PARAM,
                       ADDR_PRESET_BASE + index0 * PRESET_SIZE, PRESET_SIZE, image)


# ---------------------------------------------------------------------------
# The 92-byte preset image
# ---------------------------------------------------------------------------
#
# The addresses below are the offsets that decode every read correctly, and all
# seven known P41 GUI values match under them. That part is CONFIRMED.
#
# HYPOTHESIS (high confidence): Write_Address == index into the 92-byte image
# (identity), i.e. a RAM write targets 0x10000000 + dump_index. This is
# read-direction evidence only - NO write has ever been transmitted to this
# pedal, so the write direction is unverified. See device-validation.md item 7,
# which records the same fact as HYPOTHESIS and names the test that settles it.
#
# The published "Write_Address = Dump_Index + 2" rule is refuted, but not by
# arithmetic: a uniform +2 shift is perfectly consistent (it would map
# 0x02..0x5D). It is refuted by the documented write literals themselves -
# Change Routing targets ...02 and routing lives at 0x02; Toggle Block targets
# ...08 and FX on/off is at 0x08; Change Knob's AMP Gain example targets ...20
# and gain is at 0x20. All three are the identity, none is +2. The "+2" in the
# doc looks like an artifact of its Dump Index column being decimal while its
# Write Addr column is hex.

GHOST = "[Ghost]"
"""Reserved knob slot: exists in memory, reads 00 00, no DSP effect."""


@dataclass(frozen=True)
class Block:
    """One of the six effect blocks."""

    block_id: int
    key: str
    name: str
    toggle_addr: int
    model_addr: int
    knob_base: int
    models: tuple[str, ...]
    knobs: tuple[tuple[str, ...], ...]
    """knobs[model_index] is the 6 knob names for that model, GHOST where unused.

    For a block with ``is_dynamic=False`` this holds exactly one entry, which
    applies to every model index."""
    is_dynamic: bool = True
    """Whether the knob layout changes with the model byte.

    True for FX/MOD/DLY/REV, whose model byte selects an algorithm and therefore
    a different knob set. False for AMP and CAB, whose "model" byte is a 0..19
    capture/IR SLOT number: loading a different capture into the amp does not
    change the fact that the amp has Gain/Level/Bass/Mid/Treble. This mirrors
    bbedit's ``isDynamic`` flag, which marks amp and cab false with a single flat
    ``params`` array. Getting this wrong silently drops every AMP and CAB knob
    for 19 of the 20 slots."""

    def knob_addr(self, slot1: int) -> int:
        """Address of 1-based knob slot `slot1`. Never depends on the model."""
        if not 1 <= slot1 <= 6:
            raise ValueError(f"knob slot {slot1} out of range 1..6")
        return self.knob_base + (slot1 - 1) * 2

    def knob_names(self, model_index: int) -> tuple[str, ...]:
        """Knob names for a model index.

        A block whose layout does not depend on the model (AMP, CAB) returns its
        single fixed list for every index. Anything else raises rather than
        returning an all-ghost placeholder: an unknown model index means the
        model dictionary is wrong, and a silent empty decode looks like a preset
        with no knobs set instead of like the bug it is.
        """
        if not self.is_dynamic:
            return self.knobs[0]
        if 0 <= model_index < len(self.knobs):
            return self.knobs[model_index]
        raise ValueError(
            f"{self.name}: model index {model_index} has no knob dictionary "
            f"(this block knows {len(self.knobs)} models, 0..{len(self.knobs) - 1})")


_AMP_KNOBS = ("Gain", "Level", "Bass", "Mid", "Treble", GHOST)
_CAB_KNOBS = ("Level", "Low Cut", "High Cut", GHOST, GHOST, GHOST)

BLOCKS: tuple[Block, ...] = (
    Block(
        block_id=0, key="fx", name="FX",
        toggle_addr=0x08, model_addr=0x0E, knob_base=0x14,
        models=("Noise Gate++", "Boost", "Compress", "AI Gate MS"),
        knobs=(
            ("Gate", GHOST, GHOST, GHOST, GHOST, GHOST),
            ("Gate", "Gain", GHOST, GHOST, GHOST, GHOST),
            ("Gate", "Sustain", "Attack", "Level", GHOST, GHOST),
            ("Gate", "Bias", GHOST, GHOST, GHOST, GHOST),
        ),
    ),
    Block(
        block_id=1, key="amp", name="AMP",
        toggle_addr=0x09, model_addr=0x0F, knob_base=0x20,
        models=(),                      # 20 capture slot names, read from flash
        knobs=(_AMP_KNOBS,), is_dynamic=False,
    ),
    Block(
        block_id=2, key="mod", name="MOD",
        toggle_addr=0x0A, model_addr=0x10, knob_base=0x2C,
        models=("Chorus", "Phaser", "Tremolo", "Flanger", "Vibrato", "Univibe",
                "Autofilter"),
        knobs=(
            ("Speed", "Depth", "Mix", GHOST, GHOST, GHOST),
            ("Speed", "Midcut", "Reso", "Feedback", GHOST, GHOST),
            ("Speed", "Depth", "Level", GHOST, GHOST, GHOST),
            ("Speed", "Depth", "Feedback", "Mix", GHOST, GHOST),
            ("Speed", "Depth", GHOST, GHOST, GHOST, GHOST),
            ("Speed", "Depth", "Mix", GHOST, GHOST, GHOST),
            ("Speed", "Min", "Max", "Mix", "Feedback", GHOST),
        ),
    ),
    Block(
        block_id=3, key="dly", name="DLY",
        toggle_addr=0x0B, model_addr=0x11, knob_base=0x38,
        models=("Analog", "Duck", "Dtape", "Dual", "Lofi"),
        knobs=(
            ("Time", "Feedback", "Mix", "Phaser", "Pitch", GHOST),
            ("Time", "Feedback", "Mix", "Unpack", "Speed", "Depth"),
            ("Time", "Feedback", "Mix", "Grit", "Speed", "Depth"),
            ("Time", "Feedback", "Mix", "T-Mode", "Speed", "Depth"),
            ("Time", "Feedback", "Mix", "Grit", "Speed", "Depth"),
        ),
    ),
    Block(
        block_id=4, key="rev", name="REV",
        toggle_addr=0x0C, model_addr=0x12, knob_base=0x44,
        models=("Room", "Hall", "Swell", "Spring", "Shimmer", "Cloud"),
        knobs=(
            ("Decay", "Mix", "High Pass", "Low Pass", "Depth", GHOST),
            ("Decay", "Mix", "High Pass", "Low Pass", "Depth", GHOST),
            ("Decay", "Mix", "High Pass", "Low Pass", "Rise-T", GHOST),
            ("Decay", "Mix", "High Pass", "Low Pass", "Combs", GHOST),
            ("Decay", "Mix", "Tone", "Pitch", "Amount", GHOST),
            ("Decay", "Mix", "High Pass", "Low Pass", "Diffusion", GHOST),
        ),
    ),
    Block(
        block_id=5, key="cab", name="CAB",
        toggle_addr=0x0D, model_addr=0x13, knob_base=0x50,
        models=(),                      # 20 IR slot names, read from flash
        knobs=(_CAB_KNOBS,), is_dynamic=False,
    ),
)

BLOCKS_BY_KEY: dict[str, Block] = {b.key: b for b in BLOCKS}
BLOCKS_BY_ID: dict[int, Block] = {b.block_id: b for b in BLOCKS}

ADDR_PATCH_VOLUME = 0x00
"""Patch volume, u16 LE at dump index 0. CONFIRMED (P41 read back 85)."""

ADDR_ROUTING = 0x02
"""Six routing bytes at dump indices 2..7. CONFIRMED."""

MODELLESS_BLOCKS = ("amp", "cab")
"""Blocks whose 20 model names live in flash, not in a fixed table."""


def display_low_cut_hz(raw: int) -> float:
    """CAB Low Cut display mapping. CONFIRMED (code) - 20 Hz .. 300 Hz."""
    return 20.0 + (raw / 100.0) * 280.0


def display_high_cut_khz(raw: int) -> float:
    """CAB High Cut display mapping. CONFIRMED (code).

    NOTE the inversion: the editor's slider shows ``100 - raw`` so that moving
    right darkens the tone, but the stored/transmitted value is ``raw``, where
    raw 0 = 5.0 kHz and raw 100 = 18.0 kHz. Storing the inverted value is a
    silent, audible bug; this tool always reports and transmits ``raw``.
    """
    return 5.0 + (raw / 100.0) * 13.0


def display_delay_ms(raw: int, dly_model: int) -> float:
    """DLY Time display mapping. CONFIRMED (code).

    Dual delay (model 3) spans 50-500 ms; every other model spans 100-1000 ms.
    """
    lo, hi = (50.0, 500.0) if dly_model == 3 else (100.0, 1000.0)
    return lo + (raw / 100.0) * (hi - lo)


@dataclass
class BlockState:
    """Decoded state of one effect block."""

    key: str
    name: str
    enabled: bool
    model_index: int
    model_name: str
    knobs: list[tuple[int, str, int, int]] = field(default_factory=list)
    """(slot1, knob_name, address, value) for non-ghost slots only."""


@dataclass
class PresetImage:
    """The decoded 92-byte preset image."""

    raw: bytes
    volume: int
    routing: list[int]
    blocks: list[BlockState]

    @property
    def routing_names(self) -> list[str]:
        return [BLOCKS_BY_ID[b].name if b in BLOCKS_BY_ID else f"?{b}"
                for b in self.routing]


def decode_preset(image: bytes,
                  amp_names: Sequence[str] | None = None,
                  cab_names: Sequence[str] | None = None) -> PresetImage:
    """Decode a 92-byte preset image into named fields.

    `amp_names` / `cab_names` are the 20-entry slot dictionaries read from flash;
    when omitted the AMP and CAB model names are reported as bare indices.
    """
    if len(image) != PRESET_SIZE:
        raise ValueError(f"preset image must be {PRESET_SIZE} bytes, got {len(image)}")

    volume = int.from_bytes(image[ADDR_PATCH_VOLUME:ADDR_PATCH_VOLUME + 2], "little")
    routing = list(image[ADDR_ROUTING:ADDR_ROUTING + 6])

    flash_names = {"amp": list(amp_names or []), "cab": list(cab_names or [])}
    blocks: list[BlockState] = []
    for block in BLOCKS:
        model_index = image[block.model_addr]
        if block.key in MODELLESS_BLOCKS:
            names = flash_names[block.key]
            model_name = (names[model_index]
                          if 0 <= model_index < len(names)
                          else f"slot {model_index + 1}")
        else:
            model_name = (block.models[model_index]
                          if model_index < len(block.models)
                          else f"unknown model {model_index}")
        state = BlockState(
            key=block.key,
            name=block.name,
            enabled=bool(image[block.toggle_addr]),
            model_index=model_index,
            model_name=model_name,
        )
        try:
            names_for_model = block.knob_names(model_index)
        except ValueError as exc:
            raise ValueError(
                f"cannot decode this image: {exc}. The model byte at "
                f"{block.model_addr:#04x} reads {model_index}, which is outside "
                f"the model dictionary for {block.name}. Either the image is not "
                f"a valid preset or this firmware has models we do not know "
                f"about.") from exc
        for slot1, knob_name in enumerate(names_for_model, start=1):
            if knob_name == GHOST:
                continue
            addr = block.knob_addr(slot1)
            value = int.from_bytes(image[addr:addr + 2], "little")
            state.knobs.append((slot1, knob_name, addr, value))
        blocks.append(state)
    return PresetImage(raw=bytes(image), volume=volume, routing=routing, blocks=blocks)


def format_knob_value(block_key: str, knob_name: str, value: int,
                      dly_model: int = 0) -> str:
    """Human-readable rendering of a raw 0-100 knob value."""
    if block_key == "cab" and knob_name == "Low Cut":
        return f"{value} ({display_low_cut_hz(value):.0f} Hz)"
    if block_key == "cab" and knob_name == "High Cut":
        return f"{value} ({display_high_cut_khz(value):.1f} kHz, display slider " \
               f"shows {100 - value})"
    if block_key == "dly" and knob_name == "Time":
        return f"{value} ({display_delay_ms(value, dly_model):.0f} ms)"
    return str(value)


# ---------------------------------------------------------------------------
# Name blocks
# ---------------------------------------------------------------------------


def parse_name_table(payload: bytes) -> list[str]:
    """Split a 280-byte name block into 20 records of 14 bytes.

    CONFIRMED: fixed stride, not a packed null-separated list. Each record is
    NUL-padded ASCII beginning with the 1-based slot number, e.g. "1ML_BEST_IR".
    A naive null-split also picks up the frame's trailing checksum byte as a
    phantom 21st name, which is why the payload must exclude it.

    Raises on a short payload rather than returning a truncated list: a
    truncated reply that silently yields 3 names instead of 20 is much worse
    than an error, because the caller has no way to tell it apart from a pedal
    with 3 captures loaded.
    """
    if len(payload) != NAME_TABLE_SIZE:
        raise ValueError(
            f"name table payload is {len(payload)} bytes, expected "
            f"{NAME_TABLE_SIZE} ({NAME_COUNT} records x {NAME_STRIDE} bytes). "
            f"A short payload means the reply was truncated; returning the "
            f"names that did arrive would silently under-report the pedal.")
    names: list[str] = []
    for i in range(NAME_COUNT):
        record = payload[i * NAME_STRIDE:(i + 1) * NAME_STRIDE]
        text = record.split(b"\x00", 1)[0]
        names.append("".join(chr(b) for b in text if 0x20 <= b <= 0x7E))
    return names


def strip_slot_prefix(name: str, slot1: int) -> str:
    """Remove the leading 1-based slot number the pedal stores in each record."""
    prefix = str(slot1)
    return name[len(prefix):] if name.startswith(prefix) else name
