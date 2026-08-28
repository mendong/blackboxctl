# M-Vave BlackBox — Protocol Algorithms, Implementation Reference

Status: derived entirely from **static analysis of prior-art source code**. Nothing in this
document was verified against the physical pedal — no command was sent to the device while
producing it. Every claim below is labelled.

- **CONFIRMED (code)** — I read the byte string or the algorithm in a named source file at a
  named line, and/or reproduced it numerically with the reference implementation.
- **HYPOTHESIS** — inference, with the evidence and the test that would settle it.

Reference implementation with all vectors as executable asserts:
`/private/tmp/claude-501/-Users-mendong-Documents-black-box--claude-worktrees-blackbox-presets-ir-setup-d4cb38/ab32803c-e35f-4920-88d6-4f38bcbad797/scratchpad/proto/base128_ref.py` — 56/56 checks pass.

## Attribution and licensing

This document is derived from, and must credit:

| Source | Licence | What was taken |
| :--- | :--- | :--- |
| [jvsobrinho/mvave-blackbox-ble](https://github.com/jvsobrinho/mvave-blackbox-ble) (Joel Victor) | CC BY-SA 4.0 (docs) / GPL-3.0 (code) | BlackBox memory map, block/knob dictionaries, BLE GATT handles |
| [jvsobrinho/mvave-blackbox-edit](https://github.com/jvsobrinho/mvave-blackbox-edit) | MIT | `app.js` packet builders, polling loop, handshake, model name tables |
| [pferreir/cuvave-midi](https://github.com/pferreir/cuvave-midi) | GPL-3.0 | Authoritative Base-128 encode/decode, envelope grammar, command opcodes |
| [cbix/mvave-chocolate-sysex](https://github.com/cbix/mvave-chocolate-sysex) | see repo | Empirical SysEx dumps used as cross-check vectors |
| [michaelforney gist](https://gist.github.com/michaelforney/d3a2790bb5f8cbcb1c931eabb50b5f20) | see gist | Prose statement of the base-128 model and the envelope field layout |
| [walterwanderley/am2manager](https://github.com/walterwanderley/am2manager) | Apache-2.0 | `.am2` / `.am2Data` container layout |

Because this reference reproduces GPL-3.0 algorithm logic and CC BY-SA documentation, our CLI
should be **GPL-3.0** and must carry the attribution above.

---

## 1. Base-128 continuous 8-to-7 bit packing

**CONFIRMED (code).** Two independent implementations were read and proven bit-identical for
every input length 0..129 (`base128_ref.py`, "JS-style and Rust-style encoders agree"):

- `priorart/bbedit/app.js:573-604` — `encodeSysEx()` / `decodeSysEx()`
- `priorart/cuvave/src/parser.rs` — `encode()` / `decode()`

### The model, language-neutrally

Treat the whole raw byte string as **one arbitrarily long little-endian integer**: raw byte 0
is the least significant byte, and inside every byte bit 0 is the least significant bit.
Re-express that integer in **base 128** and emit its digits **least-significant digit first**,
one digit per output byte. Every output byte is therefore in `0x00..0x7F` and can never be
mistaken for a MIDI status byte.

Equivalently, as a bit stream: concatenate the raw bytes LSB-first into one bit stream, then
slice it into 7-bit groups from the low end. Output byte `k` carries raw bit positions
`7k .. 7k+6`. **The bit order is LSB-first end to end; there is no byte-swapping and no
nibble expansion anywhere.**

Seven raw bytes (56 bits) map exactly onto eight encoded bytes (8 × 7 = 56 bits).

### Encode

```
accum = 0            # unbounded integer, or >= 15-bit register
bits  = 0
out   = []
for b in raw:                    # b is 0..255
    accum |= b << bits
    bits  += 8
    while bits >= 7:
        out.append(accum & 0x7F)
        accum >>= 7
        bits  -= 7
out.append(accum & 0x7F)         # UNCONDITIONAL trailing group
```

**Trailing partial group.** The final `append` runs unconditionally, so when `len(raw)` is a
multiple of 7 (nothing is left over) the encoder still emits one extra `0x00`. Consequently

```
len(encoded) == floor(len(raw) * 8 / 7) + 1      for every len(raw) >= 0
```

(verified for lengths 0..199). A 16-byte command therefore becomes 19 encoded bytes, and a
107-byte flash-save frame becomes 123 encoded bytes plus `F0`/`F7` = **125 bytes of SysEx**.

The register only ever holds at most 6 leftover bits plus 8 new bits = 14 bits, so a 16-bit
accumulator is sufficient on a microcontroller. (The Rust version masks the shift with `0x1F`
because it uses a `u32`; that mask is a no-op for the values that actually occur.)

### Decode

```
accum = 0
bits  = 0
out   = []
for b in encoded:                # b is 0..127; mask defensively
    accum |= (b & 0x7F) << bits
    bits  += 7
    if bits >= 8:                # `if`, not `while` — bits can never reach 16
        out.append(accum & 0xFF)
        accum >>= 8
        bits  -= 8
```

**Trailing partial group on decode: the leftover high bits are simply discarded.** There is no
terminator and no length prefix at this layer — the frame's own 24-bit length field is what
tells you where the message really ends.

**Robustness requirement (CONFIRMED, cbix):** the device omits a trailing all-zero encoded
byte on the wire. cbix's Discovery request is `F0 00 32 45 00 00 00 40 7F F7` — 8 encoded
bytes — while the algorithm as written produces 9 (`... 40 7F 00`). Both decode to the same
7 raw bytes. **A decoder must therefore accept either length**, which the loop above does for
free. A decoder must *not* assume `len(encoded) == floor(len(raw)*8/7)+1`.

Dropping the trailing zero is only lossless when `7 * (len(encoded) - 1) >= 8 * len(raw)`;
for very short messages (1–2 raw bytes) it is not, so an *encoder* should always emit it.

---

## 2. Test vectors

All eight round-trip in `base128_ref.py`. Hex, spaces for readability.

### V1 — cuvave `parser.rs::test_encode_1` / `test_decode_1` — **CONFIRMED (code)**

```
raw     : 00 59 22 09 00 00 05 09 00 00 80 01 00 00 01 6F
encoded : 00 32 09 49 00 00 40 02 09 00 00 00 18 00 00 00 01 5E 01
sysex   : F0 00 32 09 49 00 00 40 02 09 00 00 00 18 00 00 00 01 5E 01 F7
```

### V2 — cuvave `parser.rs::test_encode_2`, "request name / version" — **CONFIRMED (code)**

```
raw     : 00 59 11 00 00 00 FF
encoded : 00 32 45 00 00 00 40 7F 00
on wire : F0 00 32 45 00 00 00 40 7F F7     <- cbix; note the dropped trailing 00
```

### V3 — cuvave `lib.rs::deserialize_set_parameters` — **CONFIRMED (code)**

The Rust test gives only the SysEx side plus the semantic decode; the raw bytes and the
checksum `5D` below were computed by the reference implementation and match the semantics
asserted in the test.

```
sysex   : F0 00 32 09 49 00 00 40 02 1B 00 00 00 18 00 00 00 01 3A 01 F7
raw     : 00 59 22 09 00 00 05 1B 00 00 80 01 00 00 01 5D
meaning : write 1 byte 0x01 to space 0x05, address 0x8000001B
```

### V4 — cbix "OK" response, real device output — **CONFIRMED (code)**

```
sysex   : F0 00 32 01 08 00 00 00 00 7F 01 F7
raw     : 00 59 00 01 00 00 00 FF
```

This is exactly the 8-byte ACK that the BlackBox docs describe, arriving here from a
completely different M-Vave product. Strong evidence the ACK is family-wide.

### V5 — cbix "switch to Program change C", real device input — **CONFIRMED (code)**

```
sysex   : F0 00 32 09 49 00 00 00 02 00 00 00 00 10 00 00 00 0B 5E 03 F7
raw     : 00 59 22 09 00 00 04 00 00 00 00 01 00 00 0B EF
meaning : write 1 byte 0x0B to space 0x04, address 0x00000000
```

### V6 — cbix "TRS = MIDI" — **CONFIRMED (code)**

```
sysex   : F0 00 32 09 49 00 00 00 02 0C 00 00 00 10 00 00 00 01 5A 03 F7
raw     : 00 59 22 09 00 00 04 0C 00 00 00 01 00 00 01 ED
```

### V6b — cbix Discovery *response* — **CONFIRMED (code)**

```
sysex   : F0 00 32 45 58 01 00 00 23 6F 5E 51 1B 44 4E 1C 36 5F 60 4C 09 03 00 00
          00 00 00 00 00 00 00 00 00 00 00 00 00 00 60 37 F7
raw     : 00 59 11 1B 00 00 | 46 6F 6F 74 43 74 72 6C 5F 30 33 31 <15 x 00> | DF
ASCII   : "FootCtrl_031"
```

This decoded cleanly with a valid checksum from an opaque hex blob, which is about as strong
a validation of the whole stack (base-128 + envelope + checksum) as static analysis can give.

### V7 / V8 — see `base128_ref.py`; V8 is cuvave's `Mystery1`, `00 59 24 09 00 00 04 64 07 00 00 01 00 00 00 8F`.

### The published CC BY-SA example is WRONG — do not test against it

`priorart/ble/docs/usb_sysex_protocol.md` presents this as its worked example:

```
raw     : 00 59 22 09 00 00 04 08 00 00 10 01 00 00 01 E1
encoded : 00 32 09 49 00 00 40 02 09 00 00 00 18 00 00 00 01 5E 01
```

**These two lines do not correspond.** The raw packet is valid (its `E1` checksum is
correct), and the encoded array is valid, but they are from different messages: the encoded
array is verbatim V1 above, i.e. the *cuvave Cube Baby* packet, evidently copied out of
`cuvave-midi`'s test suite. The true encoding is:

```
encode(00 59 22 09 00 00 04 08 00 00 10 01 00 00 01 E1)
  =    00 32 09 49 00 00 00 02 08 00 00 00 11 00 00 00 01 42 03
decode(00 32 09 49 00 00 40 02 09 00 00 00 18 00 00 00 01 5E 01)
  =    00 59 22 09 00 00 05 09 00 00 80 01 00 00 01 6F
```

A builder who unit-tests an encoder against the doc's pairing will conclude their correct
encoder is broken. `base128_ref.py` carries this as an explicit regression guard.

---

## 3. The real frame grammar

The CC BY-SA doc models a packet as *header(3) / command type(1) / routing(3) / target id(1) /
padding(2) / sub-address(2) / payload*. That model is a misreading. The actual grammar,
**CONFIRMED (code)** from `cuvave/src/parser.rs::parse_content` + `lib.rs::to_clear_vec` and
stated independently in prose by the michaelforney gist, is:

```
offset 0..1   00 59                       fixed magic
offset 2      command                     0x00 0x11 0x21 0x22 0x23 0x24
offset 3..5   payload length, 24-bit LE
offset 6..    payload (exactly `length` bytes)
last byte     checksum = (0xFF - (sum of payload bytes)) & 0xFF
```

Total frame length is always `7 + length`.

This reinterpretation is decisive. Under it, the doc's "**command type** `08 / 09 / 0A / 0E /
64`" is not a command type at all — **it is the payload length**, which is why those specific
values recur and why they always track the packet size:

| Doc "command type" | Really | Frame length |
| :--- | :--- | :--- |
| `08` | payload length 8 | 15 |
| `09` | payload length 9 | 16 |
| `0A` | payload length 10 | 17 |
| `0E` | payload length 14 | 21 |
| `64` | payload length 100 | 107 |

### Command opcodes (offset 2)

**CONFIRMED (code)**, `cuvave/src/parser.rs::parse_content`, corroborated by
`bbedit/app.js:1002-1016` which whitelists exactly `0x23 0x11 0x22 0x21`:

| Opcode | Meaning | R/W |
| :--- | :--- | :--- |
| `0x00` | Init (empty payload) / ACK (1-byte payload = success flag) | — |
| `0x11` | Query device name & version (empty payload = request; ASCII payload = response) | **read** |
| `0x21` | Erase flash block. Payload `[space][addr:4]`. Sets the block to `0xFF`. | **DESTRUCTIVE** |
| `0x22` | Write memory | **write** |
| `0x23` | Read memory (empty data = request; data present = response) | **read** |
| `0x24` | Vendor/unknown. Two forms seen on Cube Baby; never sent by bbedit. | unknown |

### Memory-access payload (inside `0x22` / `0x23`)

**CONFIRMED (code)**, `parse_read_msg` / `parse_write_msg` / `to_clear_vec`:

```
payload[0]     space      1 byte
payload[1..5]  address    4 bytes, little endian
payload[5..8]  length     3 bytes, little endian
payload[8..]   data       present on writes and on read *responses*; absent on read requests
```

So there is exactly **one read command and one write command**, parameterised by
`(space, address, length)`. Everything in the BlackBox docs' "System Commands / Live Memory
Write / DMA" tables is a special case of those two.

### Address spaces on the BlackBox

**HYPOTHESIS (high confidence).** Derived by reparsing every hard-coded packet in
`bbedit/app.js` through the grammar above; every one of them lands on a clean
`(space, address, length)` triple, and the addresses form an obviously deliberate map.
**Test that settles it:** issue `0x23` reads at these bases with our CLI and confirm the
response `MemoryContent` echoes the same address.

| Space | Base address | Region | Evidence |
| :--- | :--- | :--- | :--- |
| `0x04` | `0x00000000` | Flash preset array. Slot *n* at `n * 92`, 92 bytes each, 80 slots. | `app.js:1186` `address = presetId * 92` |
| `0x04` | `0x10000000` | Live RAM image of the active preset, 92 bytes. Offset within it == the "Write Addr" column of `memory_map.md`. | RAM-dump read is `addr 0x10000000 len 92`; toggling FX writes `addr 0x10000008`, and 8 is FX's dump index |
| `0x04` | `0x20000000` | Active-preset-id register, 4 bytes. | `app.js:1154` |
| `0x04` | `0xE0000000` | Preset-load trigger. Write `0x01` to `0xE0000000 + preset_id`. | `app.js:1168` |
| `0x04` | `0xF0000000` | Commit / OLED refresh. Zero-length write. | ble_protocol.md "Commit / UI Update" |
| `0x05` | `0x80000000` | CAB (IR) name strings, 280 bytes. | `app.js:879` handshake packet |
| `0x05` | `0x90000000` | AMP capture name strings, 280 bytes. | `app.js:862` handshake packet |

The `0x10000000` base is what makes the whole memory map click: **a block's "write address"
and its "dump index" are the same number**, because a write is just a 1- or 2-byte poke at
`0x10000000 + index` into the same 92-byte image the dump returns.

### Checksum

**CONFIRMED (code).** `checksum = (0xFF - (sum of payload bytes)) & 0xFF`, i.e. the bitwise
complement of the 8-bit payload sum (`cuvave/src/parser.rs::calc_checksum` is literally
`!sum`).

`bbedit/app.js:551` instead sums `frame[4 .. len-2]`. That is arithmetically identical for
every message whose payload is under 65536 bytes, because `frame[4]` and `frame[5]` are the
two high bytes of the 24-bit length and are always `0x00`. Verified equal on four real frames
in `base128_ref.py`. Use the payload form; it is the one that generalises.

---

## 4. Every command the editors actually send

Built from `(space, address, length)` first principles and then asserted byte-for-byte equal
to the strings hard-coded in `bbedit/app.js` — all **CONFIRMED (code)** in `base128_ref.py`.
`RAM` = `0x10000000`.

### Read-only — safe

| Name | Raw bytes | Variable fields | Source |
| :--- | :--- | :--- | :--- |
| Query name/version | `00 59 11 00 00 00 FF` | none | cuvave `test_encode_2`; cbix Discovery |
| Read RAM dump | `00 59 23 08 00 00 04 00 00 00 10 5C 00 00 8F` | none | `app.js:1076` `requestRamDump()` |
| Read active preset id | `00 59 23 08 00 00 04 00 00 00 20 04 00 00 D7` | none | `app.js:1154` `requestCurrentPresetId()` |
| Read AMP names | `00 59 23 08 00 00 05 00 00 00 90 18 01 00 51` | none | `app.js:862` `startHandshake()` |
| Read CAB names | `00 59 23 08 00 00 05 00 00 00 80 18 01 00 61` | none | `app.js:879` `processHandshakeBlock()` |
| Read flash preset *n* | `00 59 23 08 00 00 04 [A0 A1 A2 A3] 5C 00 00 [CS]` | `A` = `(n*92)` as 4-byte LE | ble_protocol.md |

> Note on the checksums: `app.js` passes `... 00` as the last byte of a literal string and
> then overwrites it in `buildPacket()`, so the correct constants above (`D7`, `51`, `61`)
> never appear in the source. They are computed here. `8F` for the RAM dump does appear in the
> doc and matches.

### State-changing — **do not send during validation work**

| Name | Raw bytes | Variable fields |
| :--- | :--- | :--- |
| Toggle block | `00 59 22 09 00 00 04 [T] 00 00 10 01 00 00 [S] [CS]` | `T` = toggle addr `08..0D`; `S` = `00`/`01` |
| Change model | `00 59 22 09 00 00 04 [M] 00 00 10 01 00 00 [ID] [CS]` | `M` = model addr `0E..13` |
| Change knob | `00 59 22 0A 00 00 04 [K] 00 00 10 02 00 00 [LSB] [MSB] [CS]` | 16-bit LE value, 0..100 |
| Patch volume | `00 59 22 0A 00 00 04 00 00 00 10 02 00 00 [LSB] 00 [CS]` | `index.html:446` calls `changeKnob(0, …)` |
| Change routing | `00 59 22 0E 00 00 04 02 00 00 10 06 00 00 [B1..B6] D4` | six block ids; `D4` really is constant, since `0+…+5` is |
| Load preset | `00 59 22 09 00 00 04 [P] 00 00 E0 01 00 00 01 [CS]` | `P` = 0-indexed preset (P01 = `00`) |
| Commit / OLED refresh | `00 59 22 08 00 00 04 00 00 00 F0 00 00 00 0B` | none |
| **Write flash (SAVE)** | `00 59 22 64 00 00 04 [A0 A1] 00 00 5C 00 00 [92 bytes] [CS]` | 107 bytes total; `A` = `n*92` |
| **Erase flash** | `00 59 21 05 00 00 [space] [addr:4] [CS]` | opcode `0x21`; not used by bbedit |

Two things worth flagging on the save path (`app.js:1186` `savePresetToSlot`):

- It writes only **two** address bytes (`addrL`, `addrH`) and hard-zeroes the upper two. Since
  the highest legal address is `79 * 92 = 7268 = 0x1C64`, that is fine, but a general
  implementation should emit the full 32-bit LE address.
- The 92-byte body is placed at frame offset **14**, i.e. `6` (envelope) + `8` (space+addr+len).
  The doc's "the header is strictly 14 bytes before the payload" is right, just unexplained.

`app.js` never sends the Commit/UI-update command, and never sends `0x21` erase.

---

## 5. Response formats

**CONFIRMED (code)** from `bbedit/app.js:970-1071`, re-derived under the frame grammar.

| Response | Length | Recognition | Where the data is |
| :--- | :--- | :--- | :--- |
| ACK | 8 | `raw[3]==0x01 && raw[7]==0xFF` (app.js); structurally `cmd==0x00, len==1` | `raw[6]` is the flag byte. Observed value is `0x00`. |
| Active preset id | 19 | `raw[10]==0x20 && raw[11]==0x04` (app.js); structurally `cmd==0x23, len==12` | `raw[14]`, 0-indexed |
| RAM dump | 107 | `raw[1]==0x59 && raw[2]==0x23` and length 107 | `raw[14:106]`, exactly 92 bytes |
| Name block | fragmented | during handshake only | see below |
| Device name | variable | `cmd==0x11` with non-empty payload | payload is NUL-padded ASCII |

**Discrepancy worth flagging.** cuvave's parser reads the ACK payload as `ACK(val[0] > 0)` —
i.e. `0x00` means *failure*. bbedit treats the identical `00 59 00 01 00 00 00 FF` packet as a
successful save confirmation (`app.js:975-987`). One of the two is wrong. **Test:** on our own
device, compare the ACK payload byte after a valid command vs. a deliberately bad checksum.
Not resolvable from source.

**Name-block fragmentation (CONFIRMED (code), `app.js:993-999`).** During the handshake the
client strips a 14-byte header (`raw[0]==0x00 && raw[1]==0x59 && len>=14` ⇒ `raw[14:]`) only
from the *first* fragment; continuation fragments are appended raw. Names are NUL-separated
ASCII with a 1- or 2-digit 1-based index prefix that must be stripped (`app.js:902`
`decodeNamesBlock` uses `/^\d+/`). Accumulate until 20 names are complete. **Caution:** that
regex also eats a leading digit from a genuinely numeric name (e.g. a capture called
`59Bassman` would render as `Bassman`). Our CLI should strip the prefix by *expected index*,
not by regex.

**USB SysEx reassembly (CONFIRMED (code), `app.js:922-962`).** A single logical response can
arrive as several Web MIDI events: first chunk starts `F0`, last ends `F7`. Buffer until `F7`.
Over CoreMIDI the same applies — a 107-byte RAM dump becomes 125 SysEx bytes, which will not
fit in one USB-MIDI packet.

---

## 6. Model id → name tables

### Block layout — **CONFIRMED (code)**, `app.js:7-120`

| Block id | Name | Toggle addr | Model addr | Knob base | Model count |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 0 | FX | `0x08` | `0x0E` | `0x14` | 4 |
| 1 | AMP | `0x09` | `0x0F` | `0x20` | 20 |
| 2 | MOD | `0x0A` | `0x10` | `0x2C` | 7 |
| 3 | DLY | `0x0B` | `0x11` | `0x38` | 5 |
| 4 | REV | `0x0C` | `0x12` | `0x44` | 6 |
| 5 | CAB | `0x0D` | `0x13` | `0x50` | 20 |

Patch volume is at `0x00`; routing occupies `0x02..0x07`. Each block reserves six 16-bit knob
slots (12 bytes); unused ones are "ghosts". `0x50 + 12 = 0x5C = 92`, so the map closes exactly.

### FX / MOD / DLY / REV — **CONFIRMED (code)**, `app.js` `modelNames` arrays

| id | FX | MOD | DLY | REV |
| :-- | :-- | :-- | :-- | :-- |
| 0 | Noise Gate++ | Chorus | Analog | Room |
| 1 | Boost | Phaser | Duck | Hall |
| 2 | Compress | Tremolo | Dtape | Swell |
| 3 | AI Gate MS | Flanger | Dual | Spring |
| 4 | — | Vibrato | Lofi | Shimmer |
| 5 | — | Univibe | — | Cloud |
| 6 | — | Autofilter | — | — |

Per-model knob names are in `app.js`'s `params` maps and agree with `memory_map.md` except for
one conflict, noted in §8.

### AMP and CAB factory names — **HYPOTHESIS (medium-high)**

`app.js` deliberately does **not** hard-code these; it fills `modelNames` with placeholders
and replaces them from the flash name blocks at handshake time, because a user's captures
overwrite the factory list. The tables below are the *factory defaults*, taken in file order
from `priorart/bbedit/descriptions.js:133-248`, which is a name→description dictionary, not an
indexed array. The ordering is an inference from insertion order.

**Corroboration:** `memory_map.md` quotes three flash reads with their 1-based indices —
`1AC-SeVin`, `2JVM_1960_57`, `14Recto_112` — and all three land on positions 1, 2 and 14 of the
CAB list below. **Test that settles it:** read the name blocks off our device and compare.

| idx (0-based) | AMP | CAB |
| :-- | :-- | :-- |
| 0 | J900_CL | AC-SeVin |
| 1 | FD CL | JVM 1960 57 |
| 2 | JC120_CL | V30 MD421 |
| 3 | BLUE OD | G12-EVH CT |
| 4 | RAT OD | HIFI OK |
| 5 | M-VAVE OD | WANGS212 ECM |
| 6 | SUPA OD | VOX AC30 |
| 7 | DARKS DS | FRMAN112 |
| 8 | J900 DS | MeOSick-III |
| 9 | JHS DS | SoldSC412 |
| 10 | EVH 5150 | FD TW1980 |
| 11 | FRIMAN | MESA 412 |
| 12 | XC DS | HIW412SWF |
| 13 | ROOM40 | Recto 112 |
| 14 | JVM | JC120 BOX |
| 15 | AgDb750 BS | Agula410 |
| 16 | ApSVT BS | AgSVT410 |
| 17 | PjBuddy BS | DgDG212N |
| 18 | DgXu BS | MbSway210 |
| 19 | MarkLm_BS | Tace412 |

`descriptions.js` also names the modelled hardware for each (Marshall JCM900, Fender 65 Deluxe
Reverb, Roland JC-120, …) — useful for CLI `--verbose` output.

---

## 7. Value scaling — what the pedal screen shows

All knobs are 16-bit little-endian on the wire but the app only ever uses the low byte, range
**0..100** (`app.js:1330` clamps with `Math.max(0, Math.min(100, value))`; `parseRamDump`
reads `data[addr]`, a single byte). Client-side display mappings, **CONFIRMED (code)**:

| Parameter | Mapping | Source |
| :--- | :--- | :--- |
| CAB Low Cut | `20 + v/100 * 280` Hz → 20–300 Hz | `app.js:171` `formatDisplayValue` |
| CAB High Cut | `5.0 + v/100 * 13.0` kHz → 5.0–18.0 kHz | same |
| CAB High Cut UI | **inverted**: slider shows `100 - v` | `app.js:1551`, `1624` |
| DLY Time, model 3 (Dual) | `50 + v/100 * 450` ms → 50–500 ms | `app.js:1696` `getDelayRange` |
| DLY Time, all other models | `100 + v/100 * 900` ms → 100–1000 ms | same |

The delay ranges are corroborated independently by `descriptions.js`, which labels Dual as
"1200–120 bpm" and the rest as "600–60 bpm" — the reciprocals of 50–500 ms and 100–1000 ms.

---

## 8. What the published documentation gets wrong or omits

Ordered by how much damage each would do to an implementer.

1. **The Base-128 worked example in `usb_sysex_protocol.md` is internally inconsistent.**
   Its raw and encoded arrays are from two different messages. §2 above gives the proof and
   the correct pairings. Highest-impact error in the whole doc set.

2. **"Command Type" at offset 3 is not a command type; it is the payload length.** The real
   command byte is at offset 2 (`0x22` write, `0x23` read, `0x11` query, `0x21` erase). This
   also means the doc's "Header `00 59 22` (RAM) / `00 59 23` (Flash & polling)" is a
   coincidence of RAM-writes-being-writes and flash-reads-being-reads: `00 59 22` writes to
   flash too (that is exactly the flash-save command), and `00 59 23` reads RAM.

3. **"Routing", "Target ID", "Padding", "Sub-address" are one 4-byte little-endian address
   plus one 3-byte little-endian length.** The doc's magic `10 01` / `10 02` / `E0 01` / `10 06`
   pairs are just the high byte of the address (`0x10……` = RAM, `0xE0……` = preset-load) sitting
   next to the low byte of the length (1, 2, 6). Anyone implementing from the doc's model will
   build a lookup table of magic constants instead of one address arithmetic function.

4. **`memory_map.md`'s "Offset Rule: `Write_Address = Dump_Index + 2`" contradicts its own
   table and the code.** Write address == dump index, exactly. The table lists write addresses
   in hex and dump indices in decimal — `0x0E` and `14` are the same number — which makes the
   two columns look different when they are identical. `app.js` proves the equality by using a
   single constant for both (`toggleAddr: 0x08` indexes `data[8]`; `knobStart: 0x14` indexes
   `data[0x14]`).

5. **"AMP Names Base Address: Flash `90 18 01 00` (Little Endian)" mis-splits the fields.**
   `90` is the top byte of address `0x90000000`; `18 01 00` is the 24-bit length `0x000118` =
   **280 bytes**. Same for CAB: address `0x80000000`, length 280. The doc's reading yields the
   nonsense address `0x000118 90`.

6. **The RAM-dump request is 15 bytes, not 16.** `ble_protocol.md` calls it "16-byte" while
   printing 15 bytes whose checksum `8F` only validates at 15. Cosmetic but it will trip a
   length assertion.

7. **The `.am4` claim is wrong for this device.** `memory_map.md` says the pedal stores amp
   captures as `.am4`. **CONFIRMED (observed on this machine):** every file in the user's
   library is `.am2` / `.am2Data` / `.am3Data`, 6144 or 6204 bytes. Details in §9.

8. **Omitted entirely: command `0x11`, the device name/version query.** It is the safest
   possible first contact — zero-length payload, read-only, and the response is a printable
   ASCII device string. It should be the first thing our CLI sends. Evidence: cuvave
   `test_encode_2` plus the cbix Discovery request/response pair (§2 V2, V6b, V7).

9. **Omitted entirely: command `0x21`, erase flash block.** Sets a block to `0xFF`. This is a
   *second* destructive opcode beyond the documented flash save, and it is absent from the
   BlackBox docs. Our CLI must refuse to emit `0x21` as firmly as it refuses `0x22`-to-flash.

10. **Omitted: the trailing-zero asymmetry.** The device drops a trailing all-zero encoded
    byte; the documented encoder always emits one. Decoders must tolerate both. Not mentioned
    anywhere in the doc set.

11. **The ACK semantics are contested.** See §5. cuvave reads the payload byte as a boolean
    where `0x00` = failure; bbedit reads the same packet as success.

12. **Knob params: one table conflict.** `memory_map.md` gives MOD 1 (Phaser) knob 2/3/4 as
    Midcut / Reso / Feedback, and `app.js` agrees — but `descriptions.js`'s Phaser text
    describes them as Dry / Wet / Feedback. Two of the three prior-art files disagree with the
    third. Resolve by reading the pedal screen.

13. **`memory_map.md` says the state dump is 92 bytes and separately that the RAM dump returns
    107.** Both are true and neither explains the other: 107 = 6 (envelope) + 8 (space/addr/len)
    + 92 (data) + 1 (checksum). Worth stating plainly.

### PocketEdit is not prior art for this protocol

The task brief lists `suckyble/PocketEdit` as "the ancestor editor that bbedit was adapted
from". **CONFIRMED (fetched):** its `tools/SYSEX_PAYLOAD_FORMAT.md` documents a completely
different wire format for a different product (Pocket Master) — **nibble expansion** (each
logical byte sent as two bytes) plus a **CRC-8/SMBus** checksum, packet-count/packet-index
fields, and a `0101 04xx` command taxonomy. No `00 59` magic, no base-128, no complement
checksum. The *user interface* may well be the ancestor of bbedit's; the protocol is not.
Its `tools/fulldumpanalyzer` and `tools/parametercommandanalyzer` are still worth reading as
methodology, but do not mine them for BlackBox byte formats.
Downloaded to `…/scratchpad/priorart/pocketedit/`.

---

## 9. `.am2` / `.am2Data` capture container

**CONFIRMED (code)**, `priorart/am2mgr/am2.go`, plus **CONFIRMED (observed)** by hexdumping the
user's own library read-only.

| Form | Size | Layout |
| :--- | :--- | :--- |
| `.am2` | 6144 | raw model payload only, no header |
| `.am2Data` / `.am3Data` | 6204 | 60-byte header + the 6144-byte `.am2` body |

Header fields used by am2manager: `[0x12]` Mix, `[0x13]` Level, `[0x14]` GainMax, `[0x15]`
GainMin. Defaults when promoting a bare `.am2`: Mix 100, Level 100, GainMax 60, GainMin 30.
Bytes `0x18..0x3B` are IEEE-754 floats (repeating `00 00 C8 42` = 100.0, `00 00 C0 C0` = -6.0,
`00 00 C0 40` = 6.0 triples — plausibly three EQ bands, **HYPOTHESIS**).

**New observation, CONFIRMED on this machine.** Two distinct header dialects coexist:

```
004_Clean_Marshall_JTM4544_NAM.am2Data  ->  41 4D 32 00 "1-JTM45-Jazz" 00 00 64 A0 3C 1E ...
                                            "AM2\0" + ASCII name, then Mix=64 Level=A0 GainMax=3C GainMin=1E
009_Clean_Vox_AC30_...am2data           ->  00 00 32 00 00 ... 00 00 64 64 50 28 ...
                                            am2manager's InitData shape, Mix=64 Level=64 GainMax=50 GainMin=28
```

The magic + name occupies the first 18 bytes, exactly up to where the Mix/Level/GainMax/GainMin
quad begins, so **both dialects agree on offsets `0x12..0x15`** and am2manager parses either.
am2manager appears not to know about the `AM2\0` magic at all. `.am3Data` presumably carries
`AM3\0`; not verified.

**`am2protector` does not touch the device or any protection flag.** It walks a directory,
SHA-256s the 6144-byte body of every capture, and emits
`INSERT OR IGNORE INTO protected_am2(am2_hash, ref) VALUES (…)` for a community *upload server*
so that others cannot re-upload your captures. "Protect" is about attribution on a website, not
about the file or the pedal. Nothing there is relevant to our CLI.

---

## 10. Client architecture the editors actually use

**CONFIRMED (code)**, `bbedit/app.js`.

Connection sequence:

1. Connect (`connect()` prefers USB MIDI with `requestMIDIAccess({sysex: true})`, falls back to
   BLE GATT `ae40`/`ae41`/`ae42`).
2. `startHandshake()` → read AMP names → accumulate fragments until 20 names → read CAB names →
   accumulate until 20 names.
3. Only then start polling. `app.js:887` sets `setInterval(2500)`; each tick sends the
   active-preset-id read, waits **250 ms**, then sends the RAM-dump read. An initial pair is
   sent immediately.

Anti-flicker rules the CLI should copy if it ever grows a live view:

- `parseRamDump` hashes the 92 bytes and returns early if unchanged (`lastDumpHex`).
- Incoming RAM dumps are **discarded** if a local edit happened in the last **1200 ms**
  (`lastUiEditTime`).
- After a preset load, wait **500 ms** before re-reading RAM.
- Flash-save waits for the ACK with a **3000 ms** timeout.

For a batch CLI none of this matters except the 250 ms / 500 ms / 3000 ms settling times,
which are the only empirical timing data in the whole prior-art corpus.

---

## 11. Files

| Path | What |
| :--- | :--- |
| `/private/tmp/…/scratchpad/proto/base128_ref.py` | Reference encode/decode/checksum/frame + 56 asserts |
| `/private/tmp/…/scratchpad/priorart/cuvave/` | pferreir/cuvave-midi, newly fetched (`src/parser.rs`, `src/lib.rs`, `examples/`) |
| `/private/tmp/…/scratchpad/priorart/chocolate/README.md` | cbix hex dumps, newly fetched |
| `/private/tmp/…/scratchpad/priorart/forney/` | michaelforney gist, newly fetched |
| `/private/tmp/…/scratchpad/priorart/pocketedit/` | PocketEdit docs, newly fetched — different protocol, see §8 |

(`…` = `/private/tmp/claude-501/-Users-mendong-Documents-black-box--claude-worktrees-blackbox-presets-ir-setup-d4cb38/ab32803c-e35f-4920-88d6-4f38bcbad797`)
