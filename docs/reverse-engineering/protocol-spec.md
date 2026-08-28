# M-Vave BlackBox — Consolidated Protocol Specification

**Status:** Derived specification. Every statement is labelled CONFIRMED or HYPOTHESIS.
**Scope:** Everything a client needs to talk to an M-Vave BlackBox over USB MIDI SysEx or
BLE GATT, without reading any other document.

---

## 0. Provenance, attribution and licence

This document is a **derivative work**. It reorganises, cross-checks and corrects three
upstream documents plus one upstream program.

| Source | Author | Licence | Role here |
| :--- | :--- | :--- | :--- |
| [`mvave-blackbox-ble`](https://github.com/jvsobrinho/mvave-blackbox-ble) — `README.md`, `docs/ble_protocol.md`, `docs/memory_map.md`, `docs/usb_sysex_protocol.md` | Joel Victor | **CC BY-SA 4.0** | Primary protocol documentation. All packet templates, the memory map and the name-handshake algorithm originate here. |
| [`mvave-blackbox-edit`](https://github.com/jvsobrinho/mvave-blackbox-edit) — `app.js` | Joel Victor | MIT | Working Web-Bluetooth/Web-MIDI editor. Used as the **arbiter** wherever the prose is ambiguous or self-contradictory. |
| [`cuvave-midi`](https://github.com/pferreir/cuvave-midi) | pferreir | GPL-3.0 | Named upstream of the Base-128 algorithm (not read directly for this document). |
| [Looper Pro protocol notes](https://gist.github.com/michaelforney/d3a2790bb5f8cbcb1c931eabb50b5f20) | michaelforney | — | Named upstream of the SysEx encapsulation (not read directly). |
| [`mvave-chocolate-sysex`](https://github.com/cbix/mvave-chocolate-sysex) | cbix | — | Named upstream, empirical dumps (not read directly). |

Because it is adapted from CC BY-SA 4.0 documentation, **this file is licensed
CC BY-SA 4.0**. Attribution: *based on protocol research by Joel Victor,
https://github.com/jvsobrinho/mvave-blackbox-ble*. Code written from this specification is
derived from GPL-3.0 reference logic and should be licensed GPL-3.0.

M-VAVE and CUVAVE are trademarks of Zhuhai Shengke Intelligent Technology Co., Ltd. This
is independent interoperability research, not endorsed by or affiliated with M-Vave.

### Evidence labels used throughout

* **CONFIRMED (docs+code)** — the upstream prose and `bbedit/app.js` agree, and where
  arithmetic is involved it was recomputed and verified on this machine.
* **CONFIRMED (computed)** — verified by running the arithmetic locally
  (checksums, Base-128 round-trip, memory-map closure).
* **CONFIRMED (code only)** — present in `bbedit/app.js`, absent or vaguer in the prose.
* **HYPOTHESIS** — asserted by one source only, unverified against silicon.
* **UNRESOLVED** — the sources disagree and the builder must not guess.

**Nothing in this document has been validated against the physical pedal.** No command in
here has been transmitted. Every "the device returns X" claim is HYPOTHESIS inherited from
upstream until a device probe confirms it.

---

## 1. Transport layers

The protocol is one byte format carried over two very different pipes. Build the raw
`00 59 …` packet once, then choose a pipe.

### 1.1 BLE — raw 8-bit frames on a proprietary GATT tunnel

**CONFIRMED (docs+code)** — `bbedit/app.js` constructor and `connectBLE()`.

| Item | Value |
| :--- | :--- |
| Advertised name | `BlackBox_BLE` (Web Bluetooth `namePrefix` filter) |
| Service UUID | `0000ae40-0000-1000-8000-00805f9b34fb` |
| TX / write | `0000ae41-0000-1000-8000-00805f9b34fb`, handle `0x0062` |
| RX / notify | `0000ae42-0000-1000-8000-00805f9b34fb`, handle `0x0064` |
| Write method | **Write Without Response** (`writeValueWithoutResponse`) |

This is **not** BLE MIDI. It does not use the MMA service
`03B80E5A-EDE8-4B33-A751-6CE34EC4C700`. Raw packets go onto `ae41` verbatim — no
Base-128, no SysEx framing. Responses arrive as `ae42` notifications, already raw.

Whether the pedal's BLE stack would *also* accept SysEx-wrapped payloads over BLE MIDI is
explicitly untested upstream — **HYPOTHESIS, untested**.

### 1.2 USB — Base-128 packed, SysEx wrapped

**CONFIRMED (docs+code)** — `usb_sysex_protocol.md` and `bbedit/app.js`
`encodeSysEx`/`decodeSysEx`/`sendCommand`/`processCompleteSysEx`.

The USB port is a class-compliant MIDI Streaming interface. MIDI forbids data bytes above
`0x7F`, and raw BlackBox packets are full of them (`0x90`, `0xE1`, `0xFF`). So the raw
packet is repacked 8-bit → 7-bit and wrapped:

```
F0 <base128(raw_packet)> F7
```

Send path: build raw → checksum → `encode()` → prepend `F0`, append `F7` → MIDI out.
Receive path: collect a complete `F0 … F7` message → strip both markers → `decode()` →
process the resulting `00 59 …` raw packet.

> **This is the pipe our CLI will use.** The device is on USB and CoreMIDI already
> enumerates it bidirectionally (see the environment notes: destination and source both
> named "USB Composite Device", manufacturer "Jieli Technology").

### 1.3 The Base-128 algorithm — exact, verified

The bit stream is **continuous and LSB-first**. Bits are drawn from each input byte
starting at bit 0, accumulated in a shift register, and emitted 7 at a time.
**CONFIRMED (computed)**: implemented locally and fuzz-tested for 3000 random buffers of
length 1–110; `decode(encode(x))[:len(x)] == x` in every case, 0 failures.

```python
def encode(raw: bytes) -> list[int]:
    out, acc, n = [], 0, 0
    for b in raw:
        acc |= b << n
        n += 8
        while n >= 7:
            out.append(acc & 0x7F)
            acc >>= 7
            n -= 7
    out.append(acc & 0x7F)      # see note on the final flush
    return out

def decode(packed: bytes) -> list[int]:
    out, acc, n = [], 0, 0
    for b in packed:
        acc |= (b & 0x7F) << n
        n += 7
        while n >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            n -= 8
    return out
```

`decode` drops the trailing partial group, which is exactly right — it is zero padding.

**Length table (CONFIRMED, computed):**

| Raw length | SysEx body | Total on the wire (`F0`…`F7`) |
| ---: | ---: | ---: |
| 8 (ACK) | 10 | 12 |
| 15 (most reads) | 18 | 20 |
| 16 (toggle / model / load) | 19 | 21 |
| 17 (knob) | 20 | 22 |
| 19 (preset-sync reply) | 22 | 24 |
| 21 (routing) | 25 | 27 |
| 107 (dump / flash write) | 123 | 125 |

**The final-flush subtlety (CONFIRMED, computed).** `bbedit` pushes the residual
accumulator unconditionally. When `len(raw) % 7 == 0` the residual is empty and this emits
one spurious trailing `0x00`. Of our packet lengths only **21 (Change Routing)** hits this:
`bbedit` emits 25 body bytes where 24 would suffice. It is harmless — the decoder discards
the extra 7 bits — but a conditional flush (`if n: out.append(...)`) is cleaner and still
byte-compatible for every other length. Either is safe.

### 1.4 ⚠️ The upstream worked example does not reproduce

**UNRESOLVED — the single most important thing to verify on real hardware.**

`usb_sysex_protocol.md` gives this pair:

```
raw     : 00 59 22 09 00 00 04 08 00 00 10 01 00 00 01 E1
encoded : 00 32 09 49 00 00 40 02 09 00 00 00 18 00 00 00 01 5E 01
```

Running the algorithm above on that raw packet produces:

```
computed: 00 32 09 49 00 00 00 02 08 00 00 00 11 00 00 00 01 42 03
                          ^^       ^^          ^^             ^^ ^^
```

The first six bytes match; five later bytes differ. **CONFIRMED (computed)**: I also tried
all four obvious bit-order variants (input LSB/MSB × output LSB/MSB); none reproduce the
documented encoding.

Worse, the discrepancy is *not* a simple typo. Decoding the document's encoded array with
the same algorithm yields a different but **structurally valid and checksum-correct**
packet:

```
00 59 22 09 00 00 05 09 00 00 80 01 00 00 01 6F      (checksum 6F verifies)
```

So the encoded line looks like a genuine capture of a *different* command that was pasted
next to the wrong raw line — not a hand-mangled transcription.

**What the builder must do:** implement §1.3 (it matches the only running code we have,
`bbedit`, which real users drive over USB), and treat §1.4 as an open question. The
settling test is a device round-trip: send the encoded **Request RAM Dump** from §2.3 and
see whether a 125-byte SysEx reply arrives that decodes to a 107-byte `00 59 23 …` frame.
If it does, §1.3 is right and the document's example is bad data. Do **not** ship a client
that silently assumes either answer.

---

## 2. Frame format

### 2.1 Common layout

**CONFIRMED (docs+code).** Every raw packet, in both directions:

| Offset | Size | Field | Notes |
| ---: | ---: | :--- | :--- |
| 0 | 3 | **Header** | `00 59 22` = RAM/write context. `00 59 23` = flash/poll/read context. |
| 3 | 1 | **Command type** | `08` read/DMA-read, `09` 1-byte write, `0A` 2-byte knob write, `0E` routing write, `64` flash write. |
| 4 | 3 | **Routing** | `00 00 04` normally; `00 00 05` **only** for the string-block (name) reads. |
| 7 | 7 | **Target / address / size** | Interpretation depends on command type — see §2.2. |
| 14 | *var* | **Payload** | Always starts at offset 14. 1, 2, 4, 6 or 92 bytes. |
| N−1 | 1 | **Checksum** | See §2.4. |

> **Offset 14 is the universal payload boundary.** It holds for the toggle value, the knob
> value, the routing sextet, the 92-byte flash-write body, the 92-byte RAM-dump body in
> responses, and the preset id in the sync reply. Hard-code 14, not a computed header
> length. **CONFIRMED (code)** — `bbedit` uses `dump.slice(14, 106)` for dumps,
> `payload.set(presetData, 14)` for writes, `bytes[14]` for the preset id, and
> `bytes.slice(14)` for name fragments.

Note this contradicts the upstream table, which splits offsets 7–13 as
*target(1) + padding(2) + sub-address(2)* and leaves offsets 12–13 undescribed. In every
observed packet offsets 12–13 are `00 00`, and treating 14 as the payload start reconciles
all cases.

### 2.2 The two readings of offsets 7–13

**CONFIRMED (docs+code).** Command type decides.

**Parameter form** (command `09`, `0A`, `0E` — the RAM writes):

| Offset | Field |
| ---: | :--- |
| 7 | Target id — the block/model/knob **write address**, i.e. an index into the 92-byte preset image (§4). |
| 8–9 | `00 00` |
| 10–11 | Sub-address: `10 01` = 1-byte set, `10 02` = knob set, `10 06` = routing set, `E0 01` = system/load-preset. |
| 12–13 | `00 00` |

**DMA form** (command `08` with routing `04`, and command `64`):

| Offset | Field |
| ---: | :--- |
| 7–10 | 32-bit **little-endian address** |
| 11–13 | 24-bit **little-endian length** — `5C 00 00` = 92 for a preset |

The two readings are consistent with each other: **Request RAM Dump**
(`… 04 | 00 00 00 10 | 5C 00 00 |`) is literally *read 92 bytes from address
`0x10000000`*, and **Read Flash Preset 0** is *read 92 bytes from address `0x00000000`* —
the two packets differ only at offset 10. `bbedit`'s `savePresetToSlot` writes
`addrL, addrH, 0x00, 0x00` at offsets 7–10 and `0x5C, 0x00, 0x00` at 11–13, which pins the
DMA form exactly. **CONFIRMED (code).**

**String form** (command `08` with routing `05` — name reads) is a third layout:
offsets 7–9 are `00 00 00` and the 32-bit LE address sits at **offsets 10–13**, with no
length field. This asymmetry with the DMA form is real, not a transcription slip — the
upstream template and `bbedit`'s two hard-coded handshake packets agree.
**CONFIRMED (docs+code).**

### 2.3 Checksum

**CONFIRMED (docs+code+computed).**

```
checksum = (0xFF - (sum(packet[4 : len-1]) & 0xFF)) & 0xFF
```

Bytes 0–3 are excluded; the checksum byte itself is excluded. `bbedit`'s
`calculateChecksum` is `0xff - (sum % 256)` over `[4, len-1)` — identical.
The pedal silently discards packets with a bad checksum (**HYPOTHESIS**, upstream claim).

I recomputed the checksum of every packet in this document; all documented literals verify.
Notably `D4` for Change Routing verifies and is genuinely constant, because the six routing
bytes are always a permutation of 0…5 and therefore always sum to `0x0F`.

---

## 3. Command catalogue

Legend: **R** = read, **W** = writes device state. Addresses in `[…]` are variables.
"Total" is the **raw** length; add §1.3's expansion for the USB wire length.

### 3.1 Read-only commands — safe

#### RAM Dump request
* **Purpose:** read the live, currently-sounding parameter set.
* **Raw (15 bytes):** `00 59 23 08 00 00 04 00 00 00 10 5C 00 00 8F` — fully constant.
* **USB (20 bytes):** `F0 00 32 0D 41 00 00 00 02 00 00 00 00 41 0B 00 00 0F 01 F7`
* **R/W:** R. **ACK:** none. **Returns:** one 107-byte frame (§3.4).
* **CONFIRMED (docs+code)** — `bbedit.requestRamDump()`. Checksum `8F` verified.
* ⚠️ The upstream prose calls this a "16-byte request". **It is 15 bytes.** Counted from
  the document's own hex literal, and the checksum only verifies at 15. Ignore the "16".

#### Preset Sync / current-preset poll
* **Purpose:** read which preset slot is active. Also used as a 2.5 s heartbeat.
* **Raw (15 bytes):** `00 59 23 08 00 00 04 00 00 00 20 04 00 00 D7`
* **USB (20 bytes):** `F0 00 32 0D 41 00 00 00 02 00 00 00 00 42 00 00 00 57 01 F7`
* **R/W:** R. **ACK:** none. **Returns:** one 19-byte frame (§3.4).
* **CONFIRMED (code)**, checksum `D7` computed here (upstream printed `[CS]`).
  Upstream flags this as a Wireshark discovery.

#### Read Flash Preset
* **Purpose:** read one stored preset slot without loading it (silent — does not change
  the sounding patch).
* **Raw (15 bytes):** `00 59 23 08 00 00 04 [A0] [A1] [A2] [A3] 5C 00 00 [CS]`
  where `A0..A3` = `preset_index * 92` as 32-bit little-endian.
* **Examples (CONFIRMED, computed):**
  * P01 (index 0, addr 0): `00 59 23 08 00 00 04 00 00 00 00 5C 00 00 9F`
  * P02 (index 1, addr 92 = `0x5C`): `00 59 23 08 00 00 04 5C 00 00 00 5C 00 00 43`
  * P04 (index 3, addr 276 = `0x114`): `00 59 23 08 00 00 04 14 01 00 00 5C 00 00 8A`
  * P80 (index 79, addr 7268 = `0x1C64`): `… 64 1C 00 00 5C 00 00 [CS]`
* **R/W:** R. **ACK:** none. **Returns:** presumed one 107-byte frame like the RAM dump.
* **HYPOTHESIS** — documented upstream, **never exercised by `bbedit`**, which has no
  flash-read path at all. The response length and framing are assumed, not observed.
  Highest-value unproven read command; a preset-backup CLI depends on it.

#### Read String Blocks — AMP names
* **Raw (15 bytes):** `00 59 23 08 00 00 05 00 00 00 90 18 01 00 51`
  (address `0x00011890` LE, routing `05`)
* **USB (20 bytes):** `F0 00 32 0D 41 00 00 40 02 00 00 00 00 09 23 00 00 51 00 F7`
* **R/W:** R. **ACK:** none. **Returns:** a fragmented ASCII stream, §6.
* **CONFIRMED (code)** — `bbedit.startHandshake()` sends this literal with a recomputed
  checksum; `51` verified here.

#### Read String Blocks — CAB / IR names
* **Raw (15 bytes):** `00 59 23 08 00 00 05 00 00 00 80 18 01 00 61`
  (address `0x00011880` LE)
* **USB (20 bytes):** `F0 00 32 0D 41 00 00 40 02 00 00 00 00 08 23 00 00 61 00 F7`
* **CONFIRMED (code)** — `bbedit.processHandshakeBlock()`; checksum `61` verified.

### 3.2 State-changing commands — DO NOT SEND during protocol validation

Catalogued for completeness and because a finished CLI needs them. **None of these may be
transmitted while the protocol is unverified.**

| Command | Raw template | Total | Payload | ACK | Evidence |
| :--- | :--- | ---: | :--- | :--- | :--- |
| **Load Preset** | `00 59 22 09 00 00 04 [PRESET_ID] 00 00 E0 01 00 00 01 [CS]` | 16 | `PRESET_ID` 0-based (`00`=P01 … `4F`=P80) | yes | docs+code |
| **Toggle Block** | `00 59 22 09 00 00 04 [ADDR] 00 00 10 01 00 00 [STATE] [CS]` | 16 | `ADDR` = `08`…`0D`; `STATE` `00`/`01` | yes | docs+code |
| **Change Model** | `00 59 22 09 00 00 04 [ADDR] 00 00 10 01 00 00 [MODEL] [CS]` | 16 | `ADDR` = `0E`…`13` | yes | docs+code |
| **Change Knob** | `00 59 22 0A 00 00 04 [ADDR] 00 00 10 02 00 00 [LSB] [MSB] [CS]` | 17 | 16-bit LE, 0–100 → `MSB` always `00` in range | yes | docs+code |
| **Change Routing** | `00 59 22 0E 00 00 04 02 00 00 10 06 00 00 [B1..B6] D4` | 21 | permutation of `00`…`05`; **`CS` is always `D4`** | yes | docs+code, `D4` recomputed |
| **Commit / UI Update** | `00 59 22 08 00 00 04 00 00 00 F0 00 00 00 0B` | 15 | none; forces OLED refresh + RAM reload | unknown | **docs only** — `bbedit` never sends it |
| **☠️ Write Flash (Save)** | `00 59 22 64 00 00 04 [A0..A3] 5C 00 00 [92 BYTES] [CS]` | **107** | header is exactly 14 bytes, body at offset 14 | **yes, required** | docs+code |

Notes:

* **Load Preset** and **Toggle Block** share command type `09` and are distinguished only
  by the sub-address at offsets 10–11 (`E0 01` vs `10 01`). Get this wrong and you write a
  parameter instead of switching patches.
* **Toggle Block** and **Change Model** are byte-identical in shape; only the target
  address distinguishes them. There is no structural guard against confusing them.
* **Change Knob** — `bbedit.changeKnob` clamps to 0–100 and emits `[val, 0x00]`. The
  16-bit field is real but the upper byte is never used in the documented 0–100 scale.
* **Write Flash** — `bbedit.savePresetToSlot` builds the 14-byte header, copies 92 bytes to
  offset 14, checksums at index 106, and then **waits up to 3000 ms for the ACK**, treating
  a timeout as failure. Any CLI that ever implements this must do the same.
  **This command permanently rewrites a slot and can destroy the user's presets.**

### 3.3 Acknowledgement

**CONFIRMED (docs+code).**

```
Success ACK (8 bytes):  00 59 00 01 00 00 00 FF
USB form (12 bytes):    F0 <10 base128 bytes> F7
```

The trailing `FF` is the checksum formula applied to an all-zero body (`0xFF - 0`), which
verifies. `bbedit` recognises an ACK loosely: `length === 8 && bytes[3] === 0x01 &&
bytes[7] === 0xFF` — it does **not** check bytes 0–2. Matching the full 8 bytes is
stricter and safer.

Emitted after a successful **live memory write** (toggle, model, knob, routing) and after
a **flash save**. Read commands are answered with data, not an ACK.
**HYPOTHESIS** for exactly which commands ACK — inherited from upstream, unverified.

### 3.4 Response frames

| Response | Length | Discriminator (as `bbedit` matches it) | Contents |
| :--- | ---: | :--- | :--- |
| **Success ACK** | 8 | `len==8 && b[3]==0x01 && b[7]==0xFF` | none |
| **Preset-sync reply** | 19 | `len==19 && b[10]==0x20 && b[11]==0x04` | `b[14]` = active preset id, 0-based. `b[18]` = checksum. |
| **RAM dump** | 107 | `len==107 && b[1]==0x59 && b[2]==0x23` | `b[14..105]` = the 92-byte preset image (§4). `b[106]` = checksum. |
| **String-block fragment** | variable | during handshake only | if `len>=14 && b[0]==0x00 && b[1]==0x59`, strip the first 14 bytes; otherwise use the whole packet. §6. |

`bbedit` additionally treats **`00 59 11 …`** and **`00 59 21 …`** as known-legitimate
inbound types alongside `00 59 22 …` / `00 59 23 …`, and logs anything else as an unknown
command (with a code comment referencing a `0x24` type seen in the Cube Baby source).
**CONFIRMED (code only)** — types `11`, `21` and `24` are entirely undocumented in the
prose. A robust client should log-and-ignore them rather than error.

**USB reassembly.** macOS/Web-MIDI may split a SysEx across several callbacks. `bbedit`
buffers from a packet starting `F0` until a packet ending `F7`. A 107-byte dump is a
125-byte SysEx and will very likely arrive fragmented. **CONFIRMED (code).**

---

## 4. The 92-byte preset image

### 4.1 ⚠️ Resolving `Write_Address = Dump_Index + 2` — the offset trap

`memory_map.md` states: *"The Write Address of a parameter is calculated using the formula:
`Write_Address = Dump_Index + 2`."* The task brief correctly flags that the document's own
MODELS rows appear to violate it (write `0E` / index `14`, write `0F` / index `15`, …).

**Resolution: the "+2" rule is WRONG, and the MODELS rows do not actually violate anything.**
The Write Addr column is printed in **hex** and the Dump Index column silently switches to
**decimal** for the MODELS rows. `0x0E = 14`, `0x0F = 15`, `0x10 = 16`, `0x11 = 17`,
`0x12 = 18`, `0x13 = 19`. They are the same six numbers written in two bases.

**The correct rule is identity:**

```
Write_Address == index into the 92-byte preset image
Frame_Offset  == Write_Address + 14        (position inside a 107-byte notification)
```

Four independent lines of evidence, all CONFIRMED:

1. **The document's own table.** Read consistently, *every* row has Write Addr == Dump
   Index — including the first eight (`00`/`00`, `02`/`02`, `08`/`08`, `09`/`09`,
   `0A`/`0A`, `0B`/`0B`, `0C`/`0C`, `0D`/`0D`). No row anywhere shows a difference of 2.
2. **`bbedit.parseRamDump`** takes `data = dump.slice(14, 106)` (the 92-byte body) and
   then reads `data[0]` for volume, `data[2..7]` for routing, `data[8..13]` for the
   on/off states, `data[14..19]` for models, and `data[block.knobStart + i*2]` for knobs —
   using the write addresses as direct indices with no offset at all.
3. **`bbedit`'s write paths mirror into the same indices.** `toggleModule` sets
   `currentRawData[toggleAddr]`, `changeModel` sets `currentRawData[modelAddr]`,
   `changeKnob` sets `currentRawData[addressDecimal]`, and `changeRouting` sets
   `currentRawData[2 + i]`. That mirrored buffer is what gets sent verbatim to flash, so
   any offset error would corrupt saves immediately and visibly.
4. **Arithmetic closure (CONFIRMED, computed).** The map runs `0x00`–`0x5B` with no gaps:
   2 + 6 + 6 + 6 + (6 blocks × 12) = **92** = `0x5C`. `0x5B` = 91 = the last index of a
   92-byte array. A "+2" rule would push the top write address to index 93 (past the end)
   and map write addresses `00` and `01` to negative indices. It is arithmetically
   impossible.

**Likely origin of the "+2":** consecutive knob slots are 2 apart, because each knob is a
16-bit value. That is a *stride*, not an offset, and it was probably miswritten as a
conversion rule.

> **Builder instruction:** use identity. Never add 2. If you are ever unsure which byte a
> write address refers to, read the RAM dump, change one parameter through the pedal's own
> front panel, read the dump again, and diff — that settles it non-destructively and
> without sending a single write.

### 4.2 Field table

**CONFIRMED (docs+code).** `Dump Index` = `Write Addr`, both shown in hex.
`Frame Offset` is the byte position inside a 107-byte notification.

| Write Addr | Dump Index | Frame Offset | Size | Block | Parameter | Encoding | Scale |
| :--: | :--: | :--: | :--: | :--- | :--- | :--- | :--- |
| `00` | `00` | 14 | 2 | GLOBAL | Patch Volume | u16 LE | 0–100 (`00 00`…`64 00`) |
| `02` | `02` | 16 | 1 | ROUTING | chain slot 1 | u8 | block id 0–5 |
| `03` | `03` | 17 | 1 | ROUTING | chain slot 2 | u8 | block id 0–5 |
| `04` | `04` | 18 | 1 | ROUTING | chain slot 3 | u8 | block id 0–5 |
| `05` | `05` | 19 | 1 | ROUTING | chain slot 4 | u8 | block id 0–5 |
| `06` | `06` | 20 | 1 | ROUTING | chain slot 5 | u8 | block id 0–5 |
| `07` | `07` | 21 | 1 | ROUTING | chain slot 6 | u8 | block id 0–5 |
| `08` | `08` | 22 | 1 | STATES | FX on/off | u8 | `00` off / `01` on |
| `09` | `09` | 23 | 1 | STATES | AMP on/off | u8 | `00` / `01` |
| `0A` | `0A` | 24 | 1 | STATES | MOD on/off | u8 | `00` / `01` |
| `0B` | `0B` | 25 | 1 | STATES | DLY on/off | u8 | `00` / `01` |
| `0C` | `0C` | 26 | 1 | STATES | REV on/off | u8 | `00` / `01` |
| `0D` | `0D` | 27 | 1 | STATES | CAB on/off | u8 | `00` / `01` |
| `0E` | `0E` (=14 dec) | 28 | 1 | MODELS | FX type | u8 | 0–3 |
| `0F` | `0F` (=15 dec) | 29 | 1 | MODELS | AMP type | u8 | 0–19 (`00`–`13`) |
| `10` | `10` (=16 dec) | 30 | 1 | MODELS | MOD type | u8 | 0–6 |
| `11` | `11` (=17 dec) | 31 | 1 | MODELS | DLY type | u8 | 0–4 |
| `12` | `12` (=18 dec) | 32 | 1 | MODELS | REV type | u8 | 0–5 |
| `13` | `13` (=19 dec) | 33 | 1 | MODELS | CAB type | u8 | 0–19 (`00`–`13`) |
| `14`–`1F` | same | 34–45 | 12 | FX | knobs 1–6 | 6 × u16 LE | 0–100 each |
| `20`–`2B` | same | 46–57 | 12 | AMP | knobs 1–6 | 6 × u16 LE | 0–100 each |
| `2C`–`37` | same | 58–69 | 12 | MOD | knobs 1–6 | 6 × u16 LE | 0–100 each |
| `38`–`43` | same | 70–81 | 12 | DLY | knobs 1–6 | 6 × u16 LE | 0–100 each |
| `44`–`4F` | same | 82–93 | 12 | REV | knobs 1–6 | 6 × u16 LE | 0–100 each |
| `50`–`5B` | same | 94–105 | 12 | CAB | knobs 1–6 | 6 × u16 LE | 0–100 each |

Total 92 bytes, `0x00`–`0x5B`, contiguous, no gaps, no unmapped bytes.

**Block ids and model tables (CONFIRMED, docs+code — `bbedit.BLOCKS`):**

| Block id | Name | Toggle addr | Model addr | Knob base | Models |
| :--: | :--- | :--: | :--: | :--: | :--- |
| 0 | FX | `08` | `0E` | `14` | `00` Noise Gate++, `01` Boost, `02` Compress, `03` AI Gate MS |
| 1 | AMP | `09` | `0F` | `20` | `00`–`13`, 20 amp captures, names read from flash (§6) |
| 2 | MOD | `0A` | `10` | `2C` | `00` Chorus, `01` Phaser, `02` Tremolo, `03` Flanger, `04` Vibrato, `05` Univibe, `06` Autofilter |
| 3 | DLY | `0B` | `11` | `38` | `00` Analog, `01` Duck, `02` Dtape, `03` Dual, `04` Lofi |
| 4 | REV | `0C` | `12` | `44` | `00` Room, `01` Hall, `02` Swell, `03` Spring, `04` Shimmer, `05` Cloud |
| 5 | CAB | `0D` | `13` | `50` | `00`–`13`, 20 cab IRs, names read from flash (§6) |

**Preset slot count:** 80 (P01–P80). Flash address = `index * 92`; index 79 → `0x1C64`.
**CONFIRMED (code)** — `bbedit` builds exactly 80 slots; upstream says `4F` = P80.

**⚠️ Preset names are not in the 92-byte image.** All 92 bytes are accounted for. `bbedit`
displays hard-coded placeholders (`"Preset 1"` … `"Preset 80"`) and never reads a name from
the device. Where the pedal stores per-preset names — or whether it stores them at all — is
**UNKNOWN**. A CLI that wants to show real preset names needs new research (a likely place
to look: further string blocks near the `0x000118xx` region used for amp/cab names).

**Doc inconsistency to flag:** `memory_map.md` says amp captures are stored as `.am4`.
The user's actual M-EFCS library contains only `.am2`, `.am2Data`, `.am3Data`. Treat `.am4`
as unverified upstream prose, not as fact.

### 4.3 Value scales

All parameters are normalised to **0–100** on the wire regardless of what the pedal's
screen shows. The client owns the display mapping. **CONFIRMED (docs+code).**

Concrete mappings implemented by `bbedit` (`formatDisplayValue`, `getDelayRange`) —
**CONFIRMED (code only)**, and to be treated as that editor's UI convention rather than a
verified DSP law:

* **CAB Low Cut:** `Hz = 20 + (raw/100) * 280` → 20 Hz … 300 Hz.
* **CAB High Cut — INVERTED:** `kHz = 5.0 + (raw/100) * 13.0` → raw 0 = 5.0 kHz,
  raw 100 = 18.0 kHz. `bbedit` displays the slider as `100 - raw` so that moving right
  darkens the tone, matching the manual's "18.0kHz – 5.0kHz" ordering. **A CLI must store
  and transmit the raw value, not the inverted display value.** This is the one parameter
  where an off-by-inversion is silent and audible.
* **DLY Time:** Dual delay (model 3) spans 50–500 ms (1200–120 bpm); all other delay
  models span 100–1000 ms (600–60 bpm). Tap tempo in `bbedit` is purely client-side — it
  computes a target ms, converts to 0–100, and issues an ordinary Change Knob at the DLY
  knob-1 address. **There is no tap-tempo command in the protocol.**

---

## 5. Routing and the 6-slot ghost rule

### 5.1 Signal chain

**CONFIRMED (docs+code).** Six bytes at write addresses `02`–`07` give the left-to-right
order of the chain. Each byte is a **block id**, and the six bytes are always a permutation
of `00`–`05`.

```
00 = FX   01 = AMP   02 = MOD   03 = DLY   04 = REV   05 = CAB

default : 00 01 02 03 04 05   -> FX -> AMP -> MOD -> DLY -> REV -> CAB
example : 04 00 01 02 03 05   -> REV -> FX -> AMP -> MOD -> DLY -> CAB
```

Because the sextet is always a permutation of 0…5 it always sums to `0x0F`, which is why
the Change Routing checksum is the constant `D4` — recomputed and verified here.

A client should validate that its candidate order is a genuine permutation before sending.
`bbedit` checks only `length === 6`; that is weaker than it should be.

### 5.2 The 6-slot ghost rule

**CONFIRMED (docs+code).** Every effect block reserves **12 bytes = 6 × 16-bit knob
slots**, whether or not the loaded model uses them. This is what keeps the preset exactly
92 bytes regardless of model selection.

Consequences a builder must respect:

* **A knob's address depends on the block and the slot number, never on the model.**
  Slot *n* (1-based) of a block is at `knob_base + (n-1) * 2`. Selecting a different model
  in the same block does **not** move any knob address.
* Slots the current model does not use are **Ghost Slots**: they exist in memory, read as
  `00 00`, and have no DSP effect. Cabinets use 3 of 6; Noise Gate++ uses 1 of 6.
* When rendering a UI or a CLI listing, **skip ghost slots by name lookup**, but keep the
  address arithmetic slot-based. `bbedit` does exactly this
  (`if (pName === "Ghost") return;` while still computing `knobStart + i*2`).
* When you change a model, the knob *meanings* change but the stored bytes do not. Slot 2
  of MOD holds "Depth" under Chorus and "Midcut" under Phaser — the same two bytes. Do not
  assume a model change zeroes anything. **HYPOTHESIS** on what the firmware actually does
  to those bytes at model-switch time; observable non-destructively by dumping RAM before
  and after a front-panel model change.

---

## 6. AMP and CAB name handshake

**CONFIRMED (docs+code)** for the request packets and the parsing rules;
**HYPOTHESIS** for the exact fragmentation behaviour over USB, which no source observed.

The pedal keeps the human-readable names of its 20 amp captures and 20 cabinet IRs in
hidden flash string blocks. A client must read both before it can render model names.

### 6.1 Sequence

```
1. send  00 59 23 08 00 00 05 00 00 00 90 18 01 00 51     # AMP names, addr 0x00011890
2. accumulate notifications until 20 names have been extracted
3. send  00 59 23 08 00 00 05 00 00 00 80 18 01 00 61     # CAB names, addr 0x00011880
4. accumulate again until 20 names
5. only now begin normal polling
```

Upstream is explicit that **normal operation and RAM polling must stay paused until both
blocks are read**. `bbedit` enforces this with a `syncState` machine
(`READING_AMPS` → `READING_CABS` → `READY`) and only starts its 2.5 s poll timer at
`READY`.

### 6.2 Fragmentation and framing

The full 20-name dictionary exceeds the BLE MTU, so the pedal splits it across several
notifications. Over USB the same stream arrives as one or more SysEx messages, each of
which may itself be split across MIDI callbacks (§3.4).

Per incoming raw packet, `bbedit` applies:

```
if len(packet) >= 14 and packet[0] == 0x00 and packet[1] == 0x59:
    payload = packet[14:]        # strip the standard 14-byte frame header
else:
    payload = packet             # continuation fragment, no header
rx_buffer.extend(payload)
```

⚠️ **Gap (CONFIRMED, code):** `bbedit` does **not** strip a trailing checksum byte from
these fragments. If the pedal does append one, a stray byte lands in the buffer. In
practice a checksum byte is either `0x00` (harmless — reads as a terminator) or a
non-printable byte (harmless — the decoder drops anything outside ASCII 32–126). So the
bug is masked, but a careful implementation should decide deliberately whether the last
byte of each framed fragment is data.

### 6.3 Stop condition

Two formulations exist and they are **not** equivalent:

* **Upstream prose:** count `0x00` bytes; stop when `Names_Found == 20`.
* **`bbedit` code:** split on `0x00`, discard empty/whitespace-only runs, stop when
  20 **non-empty** names have accumulated.

The code's version is strictly safer — it survives padding nulls, double terminators, and
a trailing null after the last name, all of which would make the prose version stop early
or hang. **Implement the code's version.** Also apply a wall-clock timeout: if fewer than
20 names arrive within a few seconds, fail loudly rather than blocking forever.

### 6.4 Decoding one name

```
1. take the bytes between two 0x00 terminators
2. keep only bytes in [0x20, 0x7E]; drop everything else
3. ASCII-decode
4. strip the LEADING 1-based index -- regex /^\d+/ -- it is 1 or 2 characters
5. the remainder is the display name; its ordinal position (0-based) is the model id
```

Worked examples from upstream, all consistent with the rule:

| Flash hex | Raw ASCII | Index prefix | Display name |
| :--- | :--- | :--: | :--- |
| `31 41 43 2D 53 65 56 69 6E 00` | `1AC-SeVin` | `1` | `AC-SeVin` |
| `32 4A 56 4D 5F 31 39 36 30 5F 35 37 00` | `2JVM_1960_57` | `2` | `JVM_1960_57` |
| `31 34 52 65 63 74 6F 5F 31 31 32 00` | `14Recto_112` | `14` | `Recto_112` |

⚠️ **The prefix strip is greedy and lossy.** `/^\d+/` would mangle a legitimately
numeric-leading name such as `59Bassman` → `Bassman`. Since the prefix is a known 1-based
counter, a correct implementation should **strip exactly the expected ordinal** (`str(i+1)`
for the *i*-th name) and warn if it does not match, rather than stripping any run of
digits. This matters for the user's ~617-file community capture pack, where user-supplied
names starting with digits are plausible.

Feed the resulting arrays into `BLOCKS[1].modelNames` (AMP, from `0x00011890`) and
`BLOCKS[5].modelNames` (CAB, from `0x00011880`), each truncated to the first 20.

---

## 7. Knob dictionaries

Transcribed exactly. **Every table below was diffed against `bbedit.BLOCKS[*].params` and
matches parameter-for-parameter, in order, with zero discrepancies** — the strongest
corroboration in this document. *[Ghost]* = reserved slot, reads `00 00`, no DSP effect.

Addresses are write addresses = dump indices; each slot is 2 bytes, u16 LE, 0–100.

### AMP (fixed, block id 1) and CAB (fixed, block id 5)

| AMP addr | CAB addr | Slot | AMP | CAB |
| :--: | :--: | :--: | :--- | :--- |
| `20` | `50` | 1 | Gain | Level |
| `22` | `52` | 2 | Level | Low Cut (L-CUT) |
| `24` | `54` | 3 | Bass | High Cut (H-CUT) — **inverted display**, see §4.3 |
| `26` | `56` | 4 | Mid | *[Ghost]* |
| `28` | `58` | 5 | Treble | *[Ghost]* |
| `2A` | `5A` | 6 | *[Ghost]* | *[Ghost]* |

### FX (block id 0, base `14`)

| Addr | Slot | 0: Noise Gate++ | 1: Boost | 2: Compress | 3: AI Gate MS |
| :--: | :--: | :--- | :--- | :--- | :--- |
| `14` | 1 | Gate | Gate | Gate | Gate |
| `16` | 2 | *[Ghost]* | Gain | Sustain | Bias |
| `18` | 3 | *[Ghost]* | *[Ghost]* | Attack | *[Ghost]* |
| `1A` | 4 | *[Ghost]* | *[Ghost]* | Level | *[Ghost]* |
| `1C` | 5 | *[Ghost]* | *[Ghost]* | *[Ghost]* | *[Ghost]* |
| `1E` | 6 | *[Ghost]* | *[Ghost]* | *[Ghost]* | *[Ghost]* |

### MOD (block id 2, base `2C`)

| Addr | Slot | 0: Chorus | 1: Phaser | 2: Tremolo | 3: Flanger | 4: Vibrato | 5: Univibe | 6: Autofilter |
| :--: | :--: | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `2C` | 1 | Speed | Speed | Speed | Speed | Speed | Speed | Speed |
| `2E` | 2 | Depth | Midcut | Depth | Depth | Depth | Depth | Min |
| `30` | 3 | Mix | Reso | Level | Feedback | *[Ghost]* | Mix | Max |
| `32` | 4 | *[Ghost]* | Feedback | *[Ghost]* | Mix | *[Ghost]* | *[Ghost]* | Mix |
| `34` | 5 | *[Ghost]* | *[Ghost]* | *[Ghost]* | *[Ghost]* | *[Ghost]* | *[Ghost]* | Feedback |
| `36` | 6 | *[Ghost]* | *[Ghost]* | *[Ghost]* | *[Ghost]* | *[Ghost]* | *[Ghost]* | *[Ghost]* |

### DLY (block id 3, base `38`)

| Addr | Slot | 0: Analog | 1: Duck | 2: Dtape | 3: Dual | 4: Lofi |
| :--: | :--: | :--- | :--- | :--- | :--- | :--- |
| `38` | 1 | Time | Time | Time | Time | Time |
| `3A` | 2 | Feedback | Feedback | Feedback | Feedback | Feedback |
| `3C` | 3 | Mix | Mix | Mix | Mix | Mix |
| `3E` | 4 | Phaser | Unpack | Grit | T-Mode | Grit |
| `40` | 5 | Pitch | Speed | Speed | Speed | Speed |
| `42` | 6 | *[Ghost]* | Depth | Depth | Depth | Depth |

### REV (block id 4, base `44`)

| Addr | Slot | 0: Room | 1: Hall | 2: Swell | 3: Spring | 4: Shimmer | 5: Cloud |
| :--: | :--: | :--- | :--- | :--- | :--- | :--- | :--- |
| `44` | 1 | Decay | Decay | Decay | Decay | Decay | Decay |
| `46` | 2 | Mix | Mix | Mix | Mix | Mix | Mix |
| `48` | 3 | High Pass | High Pass | High Pass | High Pass | Tone | High Pass |
| `4A` | 4 | Low Pass | Low Pass | Low Pass | Low Pass | Pitch | Low Pass |
| `4C` | 5 | Depth | Depth | Rise-T | Combs | Amount | Diffusion |
| `4E` | 6 | *[Ghost]* | *[Ghost]* | *[Ghost]* | *[Ghost]* | *[Ghost]* | *[Ghost]* |

---

## 8. Reference client flow

```
1. open the MIDI destination and source ("USB Composite Device" / "Jieli Technology")
2. handshake: read AMP names, then CAB names (§6). Do not poll during this.
3. steady state, every 2500 ms:
       send Preset Sync  -> 19-byte reply -> active preset id at b[14]
       wait ~250 ms
       send Request RAM Dump -> 107-byte reply -> 92-byte image at b[14..105]
4. suppress dump-driven UI refresh for ~1200 ms after any local edit, so a stale in-flight
   dump does not clobber the value the user just changed  (bbedit: lastUiEditTime)
5. skip a redundant re-render when the incoming 92 bytes are byte-identical to the last
   ones  (bbedit: lastDumpHex)
```

Steps 4 and 5 are `bbedit`'s solutions to real race conditions on a polled protocol with no
change notifications. A CLI that only reads does not need them; an interactive CLI does.

---

## 9. Confidence and risk

### 9.1 Safe to implement now — read-only, high confidence

| Item | Why it is safe |
| :--- | :--- |
| Frame layout, offset-14 payload rule, checksum | Two independent sources agree; every documented checksum recomputed and verified locally. |
| Base-128 encode/decode (§1.3) | Matches the only running code available; round-trip fuzz-tested locally, 3000/3000 pass. |
| Request RAM Dump, Preset Sync | Constant packets, verified checksums, exercised continuously by a shipped editor. |
| Read String Blocks (AMP/CAB names) | Byte-identical literals in `bbedit`'s handshake; checksums verified. |
| The 92-byte field table and identity offset rule | Four independent confirmations, including arithmetic closure at exactly 92 bytes. |
| Knob dictionaries | Doc and code match parameter-for-parameter with zero discrepancies. |
| Routing semantics, `D4` constant, 6-slot ghost rule | Doc and code agree; the `D4` invariant is proven arithmetically. |

**A read-only CLI — dump live state, decode it, list amp and cab names, report the active
preset — can be built entirely from confirmed material.** That is the right first
deliverable.

### 9.2 Needs empirical confirmation before anyone relies on it

| Item | The settling test |
| :--- | :--- |
| **⚠️ The Base-128 worked example (§1.4)** | Send the encoded Request RAM Dump; check for a 125-byte SysEx that decodes to 107 bytes of `00 59 23 …`. Failure here invalidates the whole USB path. **Do this first.** |
| Response lengths (107 / 19 / 8) | Observe them. All three are inherited claims. |
| **Read Flash Preset** | Entirely unexercised by `bbedit`. Read slot 0, verify a 107-byte reply, and compare the body against a RAM dump taken while slot 0 is loaded. Read-only, so this is safe to attempt. |
| USB SysEx fragmentation | Observe how CoreMIDI actually delivers a 125-byte SysEx; the reassembler must handle both cases. |
| Response types `11`, `21`, `24` | Log everything and see what actually arrives unsolicited. |
| ACK coverage | Which commands ACK is untested; all of the ACK-producing commands are writes, so this cannot be settled read-only. |
| Where preset names live | Unknown. §4.2. Probe neighbouring string blocks around `0x000118xx` — read-only. |
| `.am4` vs `.am2`/`.am3` | The user's library contradicts the doc. Treat the doc as wrong until shown otherwise. |
| Model-switch effect on ghost bytes | Dump RAM, change model on the front panel, dump again, diff. Fully non-destructive. |

### 9.3 Dangerous — do not send

| Command | Risk |
| :--- | :--- |
| **☠️ Write Flash (Save), type `64`** | Permanently overwrites a preset slot. A wrong address, a wrong checksum, or a wrong 92-byte body destroys the user's work; upstream explicitly disclaims bricking risk. **Never send during protocol validation.** Any eventual implementation must first read every one of the 80 slots to a backup file. |
| **Load Preset** | Changes what the pedal is playing and discards unsaved live edits. |
| **Toggle / Change Model / Change Knob / Change Routing** | Overwrite live RAM. Individually recoverable by reloading the preset, but they silently destroy unsaved edits, and each is one wrong byte away from writing a different parameter than intended. |
| **Commit / UI Update** | Documented but never exercised by any code we have. Its stated effect ("forces RAM reload") could discard live state. Lowest-confidence write command in the catalogue. |

**Structural hazards to guard against in code, independent of the protocol:**

1. **Load Preset vs Toggle Block** differ only at offsets 10–11 (`E0 01` vs `10 01`) with
   the same command type `09`. Build them through separate, named constructors.
2. **Toggle vs Change Model** are structurally identical; only the address differs.
   Validate the address against the allowed set (`08`–`0D` vs `0E`–`13`) before sending.
3. **CAB High Cut inversion** (§4.3) is silent when wrong. Store raw, invert only at the
   display layer, and never round-trip a display value back into a write.
4. **The `+2` offset myth** (§4.1). Assert `len(image) == 92` and that every write address
   is in `range(0, 92)`; add a unit test pinning volume→0, models→`0x0E`–`0x13`,
   knob bases→`14/20/2C/38/44/50`.

---

## 10. Inconsistency register

Every place the sources disagree, in one list.

| # | Issue | Verdict |
| :-- | :--- | :--- |
| 1 | `usb_sysex_protocol.md`'s encoded example does not match its own raw example under the `bbedit` algorithm, or any of four bit-order variants. It decodes instead to a different, checksum-valid packet. | **UNRESOLVED.** Implement the `bbedit` algorithm; settle on hardware before shipping. §1.4 |
| 2 | `memory_map.md`: "`Write_Address = Dump_Index + 2`". | **The rule is wrong.** Identity is correct, proven four ways. §4.1 |
| 3 | The apparent MODELS violation (write `0E` / index `14`, …). | **Not a violation** — the Dump Index column silently switches from hex to decimal. `0x0E = 14`. §4.1 |
| 4 | `ble_protocol.md` calls Request RAM Dump "16-byte"; the literal it prints is 15 bytes. | **Doc is wrong.** 15 bytes; the checksum only verifies at 15. §3.1 |
| 5 | Offsets 12–13 are undescribed by the upstream field table but are always `00 00`, and the payload always begins at 14. | **Use offset 14 as the payload boundary.** Confirmed in four separate `bbedit` code paths. §2.1 |
| 6 | The address field sits at offsets 7–10 for DMA reads (routing `04`) but at 10–13 for string reads (routing `05`). | **Real asymmetry**, not a typo — doc and code agree on both forms. §2.2 |
| 7 | Name-block stop condition: doc counts 20 nulls, `bbedit` counts 20 non-empty names. | **Use the code's version**; it is strictly more robust. §6.3 |
| 8 | `bbedit` does not strip a trailing checksum byte from name fragments. | Masked by the printable-ASCII filter, but decide deliberately. §6.2 |
| 9 | `bbedit`'s `/^\d+/` prefix strip is greedy and would corrupt a name that legitimately starts with digits. | Strip the *expected* ordinal instead, and warn on mismatch. §6.4 |
| 10 | `bbedit.encodeSysEx` flushes the accumulator unconditionally, emitting a spurious trailing `0x00` when `len(raw) % 7 == 0` (only Change Routing, 21 bytes). | Harmless — the decoder discards it. Prefer a conditional flush. §1.3 |
| 11 | Inbound types `11`, `21` (accepted by `bbedit`) and `24` (referenced in a code comment) are undocumented in the prose. | **Undocumented.** Log and ignore; do not error. §3.4 |
| 12 | Commit / UI Update exists in the prose but in no code. | **Doc only, unexercised.** Treat as unproven and dangerous. §3.2 |
| 13 | Read Flash Preset exists in the prose but in no code. | **Doc only, unexercised** — but read-only, so safe to test. §3.1 |
| 14 | Preset names have no home in the 92-byte image and are hard-coded placeholders in `bbedit`. | **Unknown storage location.** Open research question. §4.2 |
| 15 | `memory_map.md` says amp captures are `.am4`; the user's library holds `.am2` / `.am2Data` / `.am3Data`. | **Doc is inconsistent with observed reality.** Do not rely on `.am4`. §4.2 |
| 16 | `bbedit.changeRouting` validates only `length === 6`, not that the input is a permutation of 0–5. | Client-side weakness; validate properly. §5.1 |
| 17 | `bbedit`'s ACK matcher ignores bytes 0–2. | Match all 8 bytes. §3.3 |

---

*Compiled from CC BY-SA 4.0 documentation by Joel Victor
(https://github.com/jvsobrinho/mvave-blackbox-ble), cross-checked against the MIT-licensed
`mvave-blackbox-edit` editor by the same author. This derived specification is likewise
CC BY-SA 4.0. No command described here has been transmitted to a physical device.*
