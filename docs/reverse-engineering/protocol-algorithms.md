# M-Vave BlackBox — Protocol Algorithms, Implementation Reference

Status: derived entirely from **static analysis of prior-art source code**. No command was
sent to the device while producing it. Every claim below is labelled.

> **Scope and precedence.** The wire frame format is *not* defined here. It is defined once,
> in [`protocol-spec.md` §2](./protocol-spec.md#2-frame-format--the-canonical-model), which is
> canonical; §3 below defers to it and keeps only this document's unique contribution, the
> source-code provenance of each part of that grammar. Several claims first made here were
> later checked against the real pedal in
> [`device-validation.md`](./device-validation.md); where anything here conflicts with that
> document, the measurement wins. This document remains authoritative for the Base-128 codec
> (§1), the test vectors (§2), the command literals (§4), the response formats (§5), the model
> and knob tables (§6–§7), the prior-art commentary (§8) and the capture container (§9).

- **CONFIRMED (code)** — I read the byte string or the algorithm in a named source file at a
  named line, and/or reproduced it numerically with the reference implementation.
- **HYPOTHESIS** — inference, with the evidence and the test that would settle it.

Reference implementation with all vectors as executable asserts:
[`reference/base128_ref.py`](./reference/base128_ref.py) — 56/56 checks pass. It was
written in a session-scoped temporary directory and has been preserved into the repository;
see [`reference/README.md`](./reference/README.md). Earlier revisions of this document cited
it by its original absolute path under `/private/tmp/claude-501/…`, which no longer resolves.

Start at [`README.md`](./README.md) in this directory for the reading order and the
consolidated confidence summary.

## Attribution and licensing

This document is derived from, and must credit:

| Source | Licence | What was taken |
| :--- | :--- | :--- |
| [jvsobrinho/mvave-blackbox-ble](https://github.com/jvsobrinho/mvave-blackbox-ble) (Joel Victor) | CC BY-SA 4.0 (docs) / GPL-3.0 (code) | BlackBox memory map, block/knob dictionaries, BLE GATT handles |
| [jvsobrinho/mvave-blackbox-edit](https://github.com/jvsobrinho/mvave-blackbox-edit) | MIT | `app.js` packet builders, polling loop, handshake, model name tables |
| [pferreir/cuvave-midi](https://github.com/pferreir/cuvave-midi) | GPL-3.0 | Authoritative Base-128 encode/decode, envelope grammar, command opcodes |
| [cbix/mvave-chocolate-sysex](https://github.com/cbix/mvave-chocolate-sysex) | **not recorded** | Empirical SysEx dumps used as cross-check vectors |
| [michaelforney gist](https://gist.github.com/michaelforney/d3a2790bb5f8cbcb1c931eabb50b5f20) | **not recorded** | Prose statement of the base-128 model and the envelope field layout |
| [walterwanderley/am2manager](https://github.com/walterwanderley/am2manager) | Apache-2.0 | `.am2` / `.am2Data` container layout |

Two of the six sources have **no recorded licence**. That is a gap, not a permission: their
terms were never checked, and an unknown licence is not a permissive one. Both contributed
material that was actually used — cbix's hex dumps as cross-check vectors (§2 V4–V6b) and the
gist as the prose statement of the base-128 model — and that material feeds the frame grammar
which in turn feeds GPL-3.0 code. `docs/sources.md` carries the same gap.

**Licence of this document.** It is adapted from CC BY-SA 4.0 documentation, and CC BY-SA is
a share-alike licence, so **this file is itself licensed CC BY-SA 4.0**. Attribution: *based
on protocol research by Joel Victor, https://github.com/jvsobrinho/mvave-blackbox-ble*.
Crediting the source is not enough on its own; share-alike is the operative half.

Separately, because this reference reproduces GPL-3.0 algorithm logic, code written from it
should be **GPL-3.0** and must carry the attribution above. `tools/blackboxctl/` is.

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

## 3. Frame grammar — canonical account is elsewhere

> **The wire frame format is defined once, in
> [`protocol-spec.md` §2](./protocol-spec.md#2-frame-format--the-canonical-model).**
> This document no longer states a model of its own. What was §3 here — the
> `00 59 | opcode | 24-bit LE payload length | payload | checksum` grammar, the
> `(space, address, size, data)` payload of opcodes `0x22`/`0x23`, and the
> demonstration that the upstream "command type" byte is really the low byte of
> the payload length — was derived here first, was reconciled against the bytes
> the pedal actually returned, and is now §2.1–§2.3 of `protocol-spec.md`,
> canonical and unchanged in substance. `protocol-spec.md` §2.7.2 records that
> provenance; §2.7.1 there carries the point-by-point refutation of the upstream
> wording that this section used to make.

What remains below is what is unique to this document: **where each part of that
grammar came from in the prior-art source code**, which `protocol-spec.md` does not
record.

Sources for the grammar: `cuvave/src/parser.rs::parse_content` +
`lib.rs::to_clear_vec` (**CONFIRMED (code)**), stated independently in prose by the
michaelforney gist, and reproduced as executable asserts in `base128_ref.py`.
Sources for the payload structure of `0x22`/`0x23`: `parse_read_msg` /
`parse_write_msg` / `to_clear_vec` (**CONFIRMED (code)**).

### Command opcodes (frame offset 2)

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

Everything in the BlackBox docs' "System Commands / Live Memory Write / DMA"
tables is a special case of `0x22` and `0x23` parameterised by
`(space, address, length)`.

### Address spaces on the BlackBox — where each base address was found

The address map itself is in `protocol-spec.md` §2.2, where seven of its nine rows
are now **CONFIRMED** by device reads. This table records the *static-analysis
provenance* of each base, which is how they were found before the pedal was ever
queried. Originally labelled **HYPOTHESIS (high confidence)**; the `0x04` and `0x05`
spaces and the five read bases below were subsequently confirmed on hardware
(`device-validation.md` STEPS 2–6). The `0xE0000000` and `0xF0000000` bases remain
HYPOTHESIS — they are write triggers and were never sent.

| Space | Base address | Region | Evidence |
| :--- | :--- | :--- | :--- |
| `0x04` | `0x00000000` | Flash preset array. Slot *n* at `n * 92`, 92 bytes each, 80 slots. | `app.js:1186` `address = presetId * 92` |
| `0x04` | `0x10000000` | Live RAM image of the active preset, 92 bytes. Offset within it == the "Write Addr" column of `memory_map.md`. | RAM-dump read is `addr 0x10000000 len 92`; toggling FX writes `addr 0x10000008`, and 8 is FX's dump index |
| `0x04` | `0x20000000` | Active-preset-id register, 4 bytes. | `app.js:1154` |
| `0x04` | `0xE0000000` | Preset-load trigger. Write `0x01` to `0xE0000000 + preset_id`. | `app.js:1168` |
| `0x04` | `0xF0000000` | Commit / OLED refresh. Zero-length write. | `ble_protocol.md` "Commit / UI Update" |
| `0x05` | `0x80000000` | CAB (IR) name strings, 280 bytes. | `app.js:879` handshake packet |
| `0x05` | `0x90000000` | AMP capture name strings, 280 bytes. | `app.js:862` handshake packet |

The `0x10000000` base is what makes the whole memory map click: **a block's "write
address" and its "dump index" are the same number**, because a write is just a 1-
or 2-byte poke at `0x10000000 + index` into the same 92-byte image the dump
returns. (Read direction CONFIRMED on hardware; write direction still HYPOTHESIS,
since no write has been performed — `device-validation.md` correction 7.)

### Checksum — source provenance

The canonical definition is `protocol-spec.md` §2.3. Its provenance:

* `cuvave/src/parser.rs::calc_checksum` is literally `!sum` over the payload —
  i.e. `(0xFF - (sum of payload bytes)) & 0xFF`. **CONFIRMED (code).** This is the
  canonical form.
* `bbedit/app.js:551` instead sums `frame[4 .. len-2]`. That is arithmetically
  identical for every message whose payload is under 65536 bytes, because
  `frame[4]` and `frame[5]` are the two high bytes of the 24-bit length and are
  normally `0x00`. Verified equal on four real frames in `base128_ref.py`.
* **Correction to what this document originally claimed:** the two are *not*
  always identical. The pedal's two 295-byte name replies carry `frame[4] == 0x01`,
  a 288-byte payload, and stored checksums that validate under the payload sum but
  not under `app.js`'s offset-4 sum. Offset 4 is refuted for inbound frames; it
  still produces correct outbound commands, all of which have `frame[4] == 0x00`.
  Details and the 26-frame recount are in `protocol-spec.md` §2.3.

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

**Discrepancy worth flagging — UNRESOLVED.** cuvave's parser reads the ACK payload as
`ACK(val[0] > 0)` — i.e. `0x00` means *failure*. bbedit treats the identical
`00 59 00 01 00 00 00 FF` packet as a successful save confirmation (`app.js:975-987`). One of
the two is wrong. **Test:** on our own device, compare the ACK payload byte after a valid
command vs. a deliberately bad checksum. Not resolvable from source, and not resolvable
read-only — it needs a write, so it needs explicit user consent. No ACK has ever been
observed on this pedal for the same reason. Carried canonically at `protocol-spec.md` §3.3,
which also records the consequence: do not report "saved" on this byte alone.

**Name-block fragmentation (CONFIRMED (code), `app.js:993-999`).** During the handshake the
client strips a 14-byte header (`raw[0]==0x00 && raw[1]==0x59 && len>=14` ⇒ `raw[14:]`) only
from the *first* fragment; continuation fragments are appended raw. On USB there are no
continuation fragments and the 280 body bytes are 20 fixed 14-byte records, so a USB client
should index slot *N* at `body[(N-1)*14]` and skip this machinery entirely — see
`protocol-spec.md` §6 and `device-validation.md` STEP 5. Note also that the reply's trailing
checksum byte is **not** stripped by `app.js`, and on this pedal the AMP block's checksum is
`0x36` = ASCII `"6"`, which a naive null-split turns into a phantom 21st name. Names are NUL-separated
ASCII with a 1- or 2-digit 1-based index prefix that must be stripped (`app.js:902`
`decodeNamesBlock` uses `/^\d+/`). Accumulate until 20 names are complete. **Caution:** that
regex also eats a leading digit from a genuinely numeric name (e.g. a capture called
`59Bassman` would render as `Bassman`). Our CLI should strip the prefix by *expected index*,
not by regex.

**USB SysEx reassembly (CONFIRMED (code), `app.js:922-962`).** A single logical response
*can* arrive as several Web MIDI events: first chunk starts `F0`, last ends `F7`. Buffer
until `F7`.

⚠️ **Correction to what this section originally claimed.** It said a 125-byte SysEx "will not
fit in one USB-MIDI packet" and would therefore always fragment. **Refuted on this pedal:**
over CoreMIDI every 125-byte reply, and both 340-byte name replies, arrived as a single
complete SysEx message (`device-validation.md` STEP 4, correction 3). Keep the reassembler —
BLE genuinely fragments, and it costs nothing — but do not treat fragmentation as the normal
case on USB.

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

### AMP and CAB factory names — **CONFIRMED**

`app.js` deliberately does **not** hard-code these; it fills `modelNames` with placeholders
and replaces them from the flash name blocks at handshake time, because a user's captures
overwrite the factory list. The tables below are the *factory defaults*, taken in file order
from `priorart/bbedit/descriptions.js:133-248`, which is a name→description dictionary, not an
indexed array. **The ordering below was an inference from insertion order, labelled
HYPOTHESIS (medium-high), and the proposed test has now been run.**

**The inference was exactly right.** `device-validation.md` STEP 4–5 read all 40 names out of
this pedal's flash. All 20 AMP names match position for position, and 19 of 20 CAB names do;
CAB slot 1 differs only because the user overwrote `1AC-SeVin` with `1ML_BEST_IR` on
2026-08-28, so the factory value below is still the correct one. Independently, both lists
match the official vendor lists in `official-docs.md` §2.1–§2.2. Three lines of evidence,
two of them external to this project.

The earlier corroboration, kept because it is what justified the inference at the time:
`memory_map.md` quotes three flash reads with their 1-based indices — `1AC-SeVin`,
`2JVM_1960_57`, `14Recto_112` — and all three land on positions 1, 2 and 14 of the CAB list
below.

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

Ordered by how much damage each would do to an implementer. This is a flat, numbered list
of 13 items with no subsections; other documents cite it as **"§8 item *N*"**, and the
numbering below is stable. A citation of the form "§8.4" is a stale form of "§8 item 4".

1. **The Base-128 worked example in `usb_sysex_protocol.md` is internally inconsistent.**
   Its raw and encoded arrays are from two different messages. §2 above gives the proof and
   the correct pairings. Highest-impact error in the whole doc set.

2. **"Command Type" at offset 3 is not a command type; it is the payload length.**
   (Canonical statement, with the device bytes that prove it: `protocol-spec.md` §2.7.1
   item 2.) The real command byte is at offset 2 (`0x22` write, `0x23` read, `0x11` query, `0x21` erase). This
   also means the doc's "Header `00 59 22` (RAM) / `00 59 23` (Flash & polling)" is a
   coincidence of RAM-writes-being-writes and flash-reads-being-reads: `00 59 22` writes to
   flash too (that is exactly the flash-save command), and `00 59 23` reads RAM.

3. **"Routing", "Target ID", "Padding", "Sub-address" are one space byte plus one 4-byte
   little-endian address plus one 3-byte little-endian length.** (Canonical statement:
   `protocol-spec.md` §2.2 and §2.7.1 item 1, which also records that the device's own name
   replies carry a "routing" of `01 00 05`, a value the upstream model does not allow.) The doc's magic `10 01` / `10 02` / `E0 01` / `10 06`
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
   (Canonical statement: `protocol-spec.md` §2.7.1 item 3.)
   `90` is the top byte of address `0x90000000`; `18 01 00` is the 24-bit length `0x000118` =
   **280 bytes**. Same for CAB: address `0x80000000`, length 280. The doc's reading yields the
   nonsense address `0x000118 90`.

6. **The RAM-dump request is 15 bytes, not 16.** `ble_protocol.md` calls it "16-byte" while
   printing 15 bytes whose checksum `8F` only validates at 15. Cosmetic but it will trip a
   length assertion.

7. **The `.am4` claim — verdict revised; this document's original wording was too strong.**
   It said "the `.am4` claim is wrong for this device". It is not wrong, it is *incomplete*,
   and this entry now defers to `capture-format-spec.md` §4.2 and `official-docs.md` §5,
   which have the evidence:
   * The record magic `AM4\0` is **real and CONFIRMED** in current BlackBox factory data —
     a 7868-byte record with a 928-parameter GRU, shipped in `blackbox_am4_ampCab.bin`.
   * AM2 → AM3 → AM4 are **firmware generations** with dated vendor release notes.
   * What is genuinely unobserved is only the **file extension** `.am4`. **CONFIRMED
     (observed on this machine):** every file in the user's library and in the 1686-record
     community corpus is `.am2` / `.am2Data` / `.am3Data`, 6144 or 6204 bytes. Container
     details in §9.

   Whether *this* pedal can load AM4 depends on its firmware version, which is **UNRESOLVED**
   (`official-docs.md` §5).

8. **Omitted entirely: command `0x11`, the device name/version query.** It is the safest
   possible first contact — zero-length payload, read-only, and the response is a printable
   ASCII device string. Evidence: cuvave `test_encode_2` plus the cbix Discovery
   request/response pair (§2 V2, V6b, V7).

   **Status in this project: not sent, and currently not sendable.** `blackboxctl`'s
   `assert_read_only` accepts only the `00 59 23` read header, so `00 59 11 00 00 00 FF` is
   refused and the CLI cannot emit it. That is a deliberate narrowing rather than a bug, but
   it is worth knowing, because this query is the cheapest read-only way to settle the
   firmware-version question that `official-docs.md` §5 leaves **UNRESOLVED** — whether this
   pedal runs V19 (inferred from a filename, and therefore no AM4) or V20 (the label four
   preset documents record from the M-EFCS connection screen). Either widen the gate to
   `0x11` with an empty payload, or read the version off the device's settings screen.
   Reported only; no code was changed.

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

**Preserved in the repository:**

| Path | What |
| :--- | :--- |
| [`reference/base128_ref.py`](./reference/base128_ref.py) | Reference encode/decode/checksum/frame + 56 asserts. Preserved; see [`reference/README.md`](./reference/README.md). |
| [`reference/midi_transport.py`](./reference/midi_transport.py) | The transport that actually talked to the pedal, with its read-only gate. |
| [`logs/`](./logs/) | The seven raw device transcripts from the 2026-08-28 session. |

**Not preserved — these paths no longer resolve.** They were session-scoped working copies
of upstream material in `/private/tmp/claude-501/…/scratchpad/priorart/`, and that directory
does not survive. Everything this document took from them is transcribed above; to re-fetch,
use the source URLs in the attribution table rather than these paths.

| Original path | What it held |
| :--- | :--- |
| `…/scratchpad/priorart/cuvave/` | pferreir/cuvave-midi (`src/parser.rs`, `src/lib.rs`, `examples/`) — origin of §1, §2 and the opcode table |
| `…/scratchpad/priorart/chocolate/README.md` | cbix hex dumps — origin of vectors V4, V5, V6, V6b |
| `…/scratchpad/priorart/forney/` | michaelforney gist — prose statement of the base-128 model |
| `…/scratchpad/priorart/pocketedit/` | PocketEdit docs — a *different* protocol, see §8 |
