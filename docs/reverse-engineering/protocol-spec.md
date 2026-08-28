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
| [Looper Pro protocol notes](https://gist.github.com/michaelforney/d3a2790bb5f8cbcb1c931eabb50b5f20) | michaelforney | **not recorded** | Named upstream of the SysEx encapsulation (not read directly). |
| [`mvave-chocolate-sysex`](https://github.com/cbix/mvave-chocolate-sysex) | cbix | **not recorded** | Named upstream, empirical dumps (not read directly). |

"Not recorded" means exactly that: no licence file or statement was checked for, so the
terms are unknown. An unknown licence is not a permissive one. Both are used here only as
cross-check vectors, and `protocol-algorithms.md` §2 records where cbix's hex actually
contributed. `docs/sources.md` is the repository-wide inventory and carries the same gap.

Because it is adapted from CC BY-SA 4.0 documentation, **this file is licensed
CC BY-SA 4.0**. Attribution: *based on protocol research by Joel Victor,
https://github.com/jvsobrinho/mvave-blackbox-ble*. Code written from this specification is
derived from GPL-3.0 reference logic and should be licensed GPL-3.0.

M-VAVE and CUVAVE are trademarks of their owner. Two forms of that owner's name appear in
the vendor material used across this project — "Zhuhai Shengke Intelligent Technology Co.,
Ltd." (quoted here and in `capture-format-spec.md`) and "Zhuhai Rich Technology" (the address
on the vendor's own ANN white paper, quoted in `official-docs.md` §5). **Neither has been
verified against a corporate registry and they are not obviously the same entity**; treat
both as unconfirmed until one is checked. This is independent interoperability research, not
endorsed by or affiliated with M-Vave.

### Evidence labels used throughout

* **CONFIRMED (docs+code)** — the upstream prose and `bbedit/app.js` agree, and where
  arithmetic is involved it was recomputed and verified on this machine.
* **CONFIRMED (computed)** — verified by running the arithmetic locally
  (checksums, Base-128 round-trip, memory-map closure).
* **CONFIRMED (code only)** — present in `bbedit/app.js`, absent or vaguer in the prose.
* **HYPOTHESIS** — asserted by one source only, unverified against silicon.
* **UNRESOLVED** — the sources disagree and the builder must not guess.

**Where this document was originally written, nothing in it had been validated against the
physical pedal.** That is no longer true of all of it. On 2026-08-28 seven distinct
read-only commands were transmitted to the user's own BlackBox and seven unique reply frames
were captured; the
raw hex is in [`device-validation.md`](./device-validation.md). §2 has since been rewritten
against those bytes and is **canonical for the wire frame format**. Elsewhere in this
document, where a statement conflicts with `device-validation.md`, that document wins,
because it holds measurements and this one holds inferences. Claims still labelled
HYPOTHESIS remain inherited from upstream and unverified against silicon.

Start at [`README.md`](./README.md) in this directory for the reading order and for the
consolidated confidence summary — the single list of what is CONFIRMED on the real pedal,
what is HYPOTHESIS and what is UNRESOLVED. Companion documents:
[`protocol-algorithms.md`](./protocol-algorithms.md) (Base-128 codec, test vectors, opcode
and model tables, prior-art commentary), [`device-validation.md`](./device-validation.md)
(raw device logs and empirical results), [`capture-format-spec.md`](./capture-format-spec.md),
[`official-docs.md`](./official-docs.md).

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

### 1.4 The upstream worked example does not reproduce — a documentation defect

**CONFIRMED. This was the single most important thing to verify on real hardware, and it
has been verified.** The codec in §1.3 is correct; the upstream document pasted an encoded
array from a different message next to the raw one. This section was written when the
answer was unknown and said "do not ship a client that silently assumes either answer";
the answer is now known and is recorded below.

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

**Settled on hardware, 2026-08-28.** The proposed test was run: the encoded **Request RAM
Dump** from §3.1 was transmitted and a 125-byte SysEx reply arrived that decoded to a
107-byte, checksum-valid `00 59 23 …` frame carrying semantically correct data. So did the
other six commands. §1.3 is right and the document's example is bad data.
`device-validation.md` STEP 1 has the arithmetic and STEPS 2–6 the round trips.

Two further confirmations, both independent of the hardware: the encoded array is verbatim
`cuvave`'s `test_encode_1` vector, i.e. a real capture of a *different* command
(`protocol-algorithms.md` §2 V1), and a second codec written from `cuvave`'s Rust tests
rather than from `bbedit`'s JavaScript agrees bit-for-bit with the one used here on 299
random buffers and on all 13 captured SysEx messages.

**Test vectors, in priority order.** Use the request/reply pairs logged in
`device-validation.md` (mirrored in `tools/blackboxctl/tests/fixtures/device_frames.py`,
raw transcripts in `logs/`), then `cuvave`'s `parser.rs` vectors as transcribed in
`protocol-algorithms.md` §2. **Never unit-test an encoder against the
`usb_sysex_protocol.md` pair** — a correct encoder fails it.

---

## 2. Frame format — the canonical model

**This section is the single canonical account of the wire frame format for this
project.** Three descriptions of it were written independently, in this document
(§2 as originally published), in `protocol-algorithms.md` §3, and in
`device-validation.md` STEP 7. They were reconciled against the raw bytes this
pedal actually sent and received. The result of that reconciliation is stated
here; §2.7 records how each of the three earlier descriptions maps onto it and
where the wording misleads. `protocol-algorithms.md` and `device-validation.md`
now defer to this section rather than restating a model of their own.

**Evidence base — 25 distinct frames.** 14 were observed on the user's own pedal on
2026-08-28: 7 **distinct** requests transmitted (sixteen transmissions in total across the
seven preserved logs, all of them these seven literals) and 7 unique reply frames returned
(the 29 inbound SysEx messages in the logs collapse to those 7). 11 more are documented in
prior art but were **never sent to or received from this pedal**: the 8-byte ACK,
the `0x11` name/version query, cbix's `0x11` discovery reply, the Commit, Toggle
Block and Change Routing write literals, `cuvave`'s two `0x22` test vectors and
`Mystery1` (`0x24`), and cbix's two Cube Baby write captures. All 25 were re-parsed
under each competing model during this reconciliation, and the arithmetic below was
re-run from the hex rather than copied. The raw hex of the 14 observed frames lives
in `device-validation.md` STEPS 2–6 and is mirrored in
`tools/blackboxctl/tests/fixtures/device_frames.py`.

### 2.1 The grammar

**CONFIRMED.** Every frame, in both directions, on every transport:

```
offset 0..1    00 59                     fixed magic
offset 2       opcode                    1 byte
offset 3..5    payload length, 24-bit LE
offset 6..     payload, exactly `length` bytes
last byte      checksum = (0xFF - (sum of payload bytes)) & 0xFF
```

```
total frame length == 7 + length          (6 header bytes + payload + 1 checksum)
```

| Offset | Size | Field | Notes |
| ---: | ---: | :--- | :--- |
| 0 | 2 | **Magic** | `00 59`, always. |
| 2 | 1 | **Opcode** | `00` init/ACK, `11` name+version query, `21` erase flash block, `22` write memory, `23` read memory, `24` vendor/unknown. |
| 3 | 3 | **Payload length** | 24-bit little-endian. Counts payload bytes only — not the 6 header bytes, not the checksum. |
| 6 | *len* | **Payload** | Structure depends on the opcode; see §2.2 for `22`/`23`. |
| N−1 | 1 | **Checksum** | §2.3. |

The header before the payload is **6 bytes, not 14**. The "payload starts at
offset 14" rule that the rest of this document relies on is a true *consequence*
of §2.2 for opcodes `22` and `23` only — 6 header bytes plus an 8-byte
`space`/`address`/`size` prologue — and it does not generalise to other opcodes.

There are exactly **two memory commands**: `0x23` read and `0x22` write, each
parameterised by `(space, address, size)`. Every entry in the upstream
"System Commands / Live Memory Write / DMA" tables is a special case of one of
those two. There is no per-command opcode taxonomy to memorise.

### 2.2 The memory-access payload — opcodes `0x22` and `0x23`

**CONFIRMED.** Inside a read or write frame the payload is itself structured:

| Payload offset | Frame offset | Size | Field |
| ---: | ---: | ---: | :--- |
| 0 | 6 | 1 | **Space selector** — `04` parameter/preset memory, `05` name-string memory |
| 1 | 7 | 4 | **Address**, 32-bit little-endian |
| 5 | 11 | 3 | **Size**, 24-bit little-endian — bytes requested (request) or bytes returned (reply) |
| 8 | 14 | *var* | **Data** — absent on a read *request*; present on a read *reply* and on every write |

Two invariants hold on all 14 observed frames and on every documented one that
carries a `0x22` / `0x23` opcode:

```
length == len(data) + 8
size   == len(data)          on replies and writes; data is empty on read requests
```

**This is where the universal "offset 14" boundary comes from:** 6 + 1 + 4 + 3 = 14.
It holds for the toggle value, the knob value, the routing sextet, the 92-byte
flash-write body, the 92-byte RAM-dump body, and the preset id in the sync
reply. Hard-code 14 for these opcodes rather than computing a header length. It
does **not** hold for an ACK or for a `0x11` reply, which have no
space/address/size prologue at all (§2.5).

**CONFIRMED (code)** — four independent call sites in `bbedit` use the literal 14:
`dump.slice(14, 106)` for RAM dumps, `payload.set(presetData, 14)` for writes,
`bytes[14]` for the preset id in a sync reply, and `bytes.slice(14)` for name
fragments. **CONFIRMED on this pedal** — the same boundary holds on all 14
frames observed on 2026-08-28 (`device-validation.md` STEP 7).

**Address map (CONFIRMED except as marked).** The protocol is a memory-mapped
read/write over an address space:

| Address | Space | Meaning | Status |
| :--- | :--: | :--- | :--- |
| `0x00000000 + index * 92` | `04` | preset slot in flash, 92 bytes, index 0-based (P01 = 0) | CONFIRMED — read at indices 0, 2, 40 |
| `0x10000000` | `04` | live RAM image of the sounding preset, 92 bytes, same layout | CONFIRMED |
| `0x10000000 + dump_index` | `04` | one parameter inside that image — the identity mapping of §4.1 | CONFIRMED for reads; HYPOTHESIS for writes |
| `0x20000000` | `04` | active preset id register, 4 bytes, id in byte 0 | CONFIRMED |
| `0x80000000` | `05` | CAB / IR name table, 280 bytes = 20 × 14 | CONFIRMED |
| `0x90000000` | `05` | AMP capture name table, 280 bytes = 20 × 14 | CONFIRMED |
| `0xE0000000 + preset_id` | `04` | preset-load trigger, write `01` | HYPOTHESIS — documented, **never sent** |
| `0xF0000000` | `04` | commit / OLED refresh, zero-length write | HYPOTHESIS — documented, **never sent** |

### 2.3 Checksum

**CONFIRMED, with one refutation recorded.**

```
checksum = (0xFF - (sum(payload) & 0xFF)) & 0xFF        # payload = frame[6 : N-1]
```

It is the bitwise complement of the 8-bit sum of the payload — `cuvave`'s
`calc_checksum` is literally `!sum(payload)`.

Three start offsets have been proposed in this project's documents: 4, 5 and 6.
They coincide whenever bytes 4 and 5 are both zero, which is true of every frame
in the upstream documentation and of every frame this pedal has ever been sent.
Recomputed over all 25 frames during this reconciliation:

| Start offset | Frames explained | Verdict |
| :--- | :--- | :--- |
| 4 — `bbedit/app.js:551`, `0xFF - sum(frame[4 : N-1])` | 23 / 25 | **Refuted.** Fails on exactly the two 295-byte name replies, whose `byte[4]` is `0x01`. |
| 5 — `device-validation.md` correction 2 | 25 / 25 | Correct on all evidence, but indistinguishable from 6. |
| 6 — the payload sum, `cuvave` | 25 / 25 | **Canonical.** Same output as 5 on all evidence, and it is the form that follows from the grammar. |

`byte[5]` is `0x00` in all 25 frames, so offsets 5 and 6 cannot be told apart by
any observation available here. Offset 6 is canonical because it is what the
grammar says the field is, and because it is what the reference source computes.

Practical consequence: outbound commands built with the upstream offset-4 formula
are still correct — the pedal accepted and answered all seven — but **a client
that verifies inbound checksums must not use offset 4**, or it will reject both
name-table replies.

The pedal silently discards packets with a bad checksum (**HYPOTHESIS**, upstream
claim, untested).

`D4` for Change Routing verifies and is genuinely constant, because the six
routing bytes are always a permutation of 0…5 and therefore always sum to `0x0F`.
All documented checksum literals in this document were recomputed and verify.

### 2.4 Worked examples — the frames this pedal actually sent and received

Each row is one real frame parsed under §2.1 and §2.2. `data` is the payload
after the 8-byte prologue. Full hex in `device-validation.md` STEPS 2–6.

```
frame              N   op   len  7+len==N  sp        addr   size  data  size==data  cs
req RAM dump      15  0x23    8      True  04  0x10000000     92     0        True  ok
req preset sync   15  0x23    8      True  04  0x20000000      4     0        True  ok
req CAB names     15  0x23    8      True  05  0x80000000    280     0        True  ok
req AMP names     15  0x23    8      True  05  0x90000000    280     0        True  ok
req flash idx 0   15  0x23    8      True  04  0x00000000     92     0        True  ok
req flash idx 2   15  0x23    8      True  04  0x000000B8     92     0        True  ok
req flash idx 40  15  0x23    8      True  04  0x00000E60     92     0        True  ok
rep RAM dump     107  0x23  100      True  04  0x10000000     92    92        True  ok
rep preset sync   19  0x23   12      True  04  0x20000000      4     4        True  ok
rep CAB names    295  0x23  288      True  05  0x80000000    280   280        True  ok
rep AMP names    295  0x23  288      True  05  0x90000000    280   280        True  ok
rep flash idx 0  107  0x23  100      True  04  0x00000000     92    92        True  ok
rep flash idx 2  107  0x23  100      True  04  0x000000B8     92    92        True  ok
rep flash idx 40 107  0x23  100      True  04  0x00000E60     92    92        True  ok
```

Byte by byte, the request that read the AMP name table:

```
00 59   23   08 00 00   05   00 00 00 90   18 01 00   51
|___|   ||   |______|   ||   |_________|   |______|   ||
magic   op   length 8   sp   addr          size 280   checksum
        23   = the 8    05   0x90000000    = 20 x 14  = 0xFF - (sum of the 8 payload bytes)
        read payload         string space  name bytes
             bytes
```

The eight payload bytes are `05 00 00 00 90 18 01 00`: space, address, size, and
no data — a read *request* asks for bytes and sends none. Length 8 therefore
appears at offset 3 as `08`, which the upstream model calls "command type `08`,
read/DMA-read".

The 295-byte reply echoes the same space, address and size and appends 280 bytes
of data, so its length is 280 + 8 = 288:

```
00 59   23   20 01 00   05   00 00 00 90   18 01 00   31 4A 39 ... 42 53 00 00 00   36
             len = 288  sp   addr          size 280   280 data bytes                cs
```

Note `20 01 00` at offsets 3–5: little-endian 288. The upstream model reads the
`20` as a command type and the `01 00 05` as a routing field — see §2.7.1.

### 2.5 Frames only the general grammar explains

Three documented frames are shorter than 14 bytes or carry a payload that is not
`(space, address, size, data)`. A model that treats offsets 5–13 as fixed header
fields cannot express them at all. Under §2.1 all three parse cleanly with a
correct payload-sum checksum. **None was ever sent to or received from this
pedal**; they are prior-art frames, verified arithmetically here.

| Frame | Raw | Parse | Checksum |
| :--- | :--- | :--- | :--- |
| Success ACK | `00 59 00 01 00 00 00 FF` | op `00`, length 1, payload `00` | `0xFF` = `0xFF - 0x00` ✓ |
| Name/version query | `00 59 11 00 00 00 FF` | op `11`, length 0, empty payload | `0xFF` ✓ |
| cbix discovery reply | `00 59 11 1B 00 00 46 6F 6F 74 43 74 72 6C 5F 30 33 31` + 15 × `00` + `DF` | op `11`, length 27, payload = ASCII `FootCtrl_031` NUL-padded | `0xDF` ✓ |

The discovery reply is the load-bearing one. Its payload content is
self-identifying ASCII, and the `F` of `FootCtrl_031` sits at **frame offset 6**.
That pins the header at 6 bytes directly, from the bytes rather than from any
model: with a 5-byte header the frame would be 33 bytes and with a 7-byte header
35, but it is 34. It also shows that offsets 5–6 do not universally hold a space
selector — here they hold `00` and `46`, the length's top byte and the letter `F`.

A practical consequence for this project, reported and not acted on:
`tools/blackboxctl/blackboxctl/protocol.py`'s `parse_frame` requires at least 15
bytes and raises "frame too short" on a real 8-byte ACK. That is unreachable today
because every write path is gated behind `hardware_confirmed=False`, so no ACK can
ever arrive; it would need fixing before any write support is enabled. No code was
changed — see the workspace rules in `AGENTS.md`.

### 2.6 The `0x22` / `0x23` derived view — a fixed 14-byte header

For opcodes `22` and `23` only, §2.1 and §2.2 collapse into a flat fixed-offset
header, which is what a read-only client such as `blackboxctl` actually
implements. It is a specialisation, not a competing model:

| Offset | Size | Field |
| ---: | ---: | :--- |
| 0 | 3 | magic `00 59 22` (write) / `00 59 23` (read) |
| 3 | 2 | length, LE16 — always `len(data) + 8` |
| 5 | 2 | space selector, LE16 — `0x0400` parameter, `0x0500` string |
| 7 | 4 | address, LE32 |
| 11 | 3 | size, LE24 |
| 14 | var | data |
| N−1 | 1 | checksum |

This is byte-for-byte identical to §2.1 + §2.2 on every frame in evidence, and
`tools/blackboxctl/blackboxctl/protocol.py` `build_frame`/`parse_frame`
implements exactly this. Use it only where the opcode is known to be `22` or `23`;
fall back to §2.1 for anything else.

**The one genuinely unresolved byte.** The two readings disagree about who owns
`byte[5]`. §2.1 calls it bits 16–23 of the 24-bit length; §2.6 calls it the low
byte of a 16-bit space selector. Both readings produce identical results on every
frame ever observed, because `byte[5]` is `0x00` in all 25 of them. It is
**UNRESOLVED**, and it is harmless: it can only be settled by a frame with a
payload of 65536 bytes or more (which would set it under §2.1) or a space
selector above `0x00FF` (which would set it under §2.6), and neither exists in
any evidence. `blackboxctl` refuses to build a frame with a payload over 247
bytes for the related reason that the checksum start offsets diverge there.

### 2.7 How this relates to the other descriptions

Nothing below is deleted; it is kept so a reader arriving from the upstream
repository, or from either of the other two documents here, can follow along.

#### 2.7.1 The upstream published wording — and where it misleads

`ble_protocol.md` and `usb_sysex_protocol.md` model a packet as:

```
header(3) | command type(1) | routing(3) | target id(1) | padding(2) | sub-address(2) | payload | cs
```

with the command type at offset 3 taking values `08` read/DMA-read, `09` 1-byte
write, `0A` knob write, `0E` routing write, `64` flash write; routing at offsets
4–6 being `00 00 04` normally and `00 00 05` for the name reads; and, for the
name reads only, a 32-bit little-endian address at offsets 10–13 instead of 7–10.

**This model is one byte out of alignment and must be retired.** It is refuted by
frames this pedal actually returned:

1. **The "routing" field takes a value the model does not allow.** On both
   295-byte name replies, offsets 4–6 read `01 00 05`, not `00 00 05`. Under §2.1
   the `01` is bits 8–15 of the length 288, and the `05` is the space selector,
   which is the first payload byte. There is no routing field.
2. **The "command type" is the low byte of the length.** `08` → length 8;
   `09` → 9; `0A` → 10; `0E` → 14; `64` → 100. The device returns `0x64` in every
   92-byte read reply (92 + 8 = 100), `0x0C` in the 19-byte preset-sync reply
   (4 + 8 = 12) and `20 01` in the name replies (280 + 8 = 288). **None of those
   was ever sent as a command.** A client following the upstream model reads every
   RAM-dump reply as if it carried the Write Flash Save opcode. The real opcode
   byte is at offset 2, which the upstream model treats as part of the header:
   `00 59 22` and `00 59 23` are magic + opcode, not two header constants.
3. **The "string form" address is a misparse.** Upstream reads the AMP name base
   address as `90 18 01 00` at offsets 10–13, giving `0x00011890`, with no length
   field. The device's own reply echoes address `00 00 00 90` at offsets 7–10 and
   size `18 01 00` = 280 at offsets 11–13, and carries length `20 01` = 288 =
   280 + 8 at offsets 3–4, which the upstream reading leaves entirely
   unexplained. The real address is `0x90000000` (CAB: `0x80000000`) and `18 01 00`
   is the 24-bit size, 280 = 20 records × 14 bytes. The upstream literal works only
   because the bytes happen to land in the right places; a client built on it
   cannot form a generalised `read(space, address, size)` and cannot vary the size.
4. **The "real asymmetry" between a DMA form and a string form is not real.** Both
   are the same `(space, address, size)` payload. The earlier verdict in this
   document's own §10 that called the asymmetry genuine is struck.
5. **`00 59 22` is not "RAM context" and `00 59 23` is not "flash context".** They
   are write and read. `00 59 22` writes to flash too — that is exactly the flash
   save command — and `00 59 23` reads RAM.

What the upstream wording gets right, and why it worked in practice: every
outbound literal it prints is byte-correct, its checksum formula produces correct
outbound commands (§2.3), and its "payload starts at offset 14" rule is right for
the two memory opcodes (§2.2). It fails on *parsing replies* and on
*generalising*, not on the specific packets it prints.

#### 2.7.2 `protocol-algorithms.md` §3

Same model as §2.1 and §2.2 here, described in the same terms and derived
independently, by static analysis of `cuvave/src/parser.rs::parse_content`,
`lib.rs::to_clear_vec` and the michaelforney gist. §2.1 above is that account,
promoted to canonical. That document now points here and keeps what is unique to
it: the Base-128 codec, the test vectors, the opcode table, the model and knob
dictionaries, and the prior-art commentary.

#### 2.7.3 `device-validation.md` STEP 7

**Not a third model.** STEP 7's "unified packet field model" is §2.6 above — the
`0x22`/`0x23` specialisation — carved from the identical bytes and producing
identical values. It differs from §2.1 in exactly one place, the ownership of
`byte[5]`, which no observation can settle (§2.6). Its two substantive findings —
that the upstream "command type" byte and the upstream AMP-names base address are
both one-byte field misalignments — are correct and are carried into §2.7.1 here.
Its only limitation is generality: because it assumes space/address/size are
universal header fields rather than the payload structure of two opcodes, it
cannot express the ACK, the `0x11` query, or the cbix discovery reply (§2.5).
That document now points here and keeps what is unique to it: the raw hex logs
and the empirical results.

#### 2.7.4 Reconciliation verdict

| Question | Answer |
| :--- | :--- |
| Were there three models? | **No — two.** `protocol-algorithms.md` §3 and `device-validation.md` STEP 7 are the same model; the second is a specialisation of the first to opcodes `22`/`23`. The upstream model in this document's original §2 was genuinely different, and wrong. |
| Which is canonical? | §2.1 + §2.2, the general grammar. §2.6 is its derived fixed-offset view and is what the CLI implements. |
| What is still unresolved? | Ownership of `byte[5]` (§2.6), and the checksum start offset 5 vs 6 (§2.3). Both are undecidable on all available evidence and both are harmless: every reading gives identical bytes on every frame in evidence. |
| What changed for a client? | Parse replies by the length field and route them by the `address` field, never by a "command type" byte and never by arrival order. Verify inbound checksums from offset 6 (or 5), never from 4. Read the name tables at `0x90000000` / `0x80000000` with size 280, not at `0x00011890` / `0x00011880`. |

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
* **Purpose:** read one stored preset slot without loading it. It does not change the
  *active preset* — see the confirmation note below for exactly what was measured.
* **Raw (15 bytes):** `00 59 23 08 00 00 04 [A0] [A1] [A2] [A3] 5C 00 00 [CS]`
  where `A0..A3` = `preset_index * 92` as 32-bit little-endian.
* **Examples (CONFIRMED, computed):**
  * P01 (index 0, addr 0): `00 59 23 08 00 00 04 00 00 00 00 5C 00 00 9F`
  * P02 (index 1, addr 92 = `0x5C`): `00 59 23 08 00 00 04 5C 00 00 00 5C 00 00 43`
  * P04 (index 3, addr 276 = `0x114`): `00 59 23 08 00 00 04 14 01 00 00 5C 00 00 8A`
  * P80 (index 79, addr 7268 = `0x1C64`): `… 64 1C 00 00 5C 00 00 [CS]`
* **R/W:** R. **ACK:** none. **Returns:** one 107-byte frame, same framing as the RAM dump.
* **CONFIRMED on this pedal** — `device-validation.md` STEP 6 read indices 0, 2 and 40.
  Each returned exactly 107 bytes with a valid checksum, echoing the requested space,
  address and size. Index 2 returned a 92-byte payload **byte-identical to the live RAM
  dump** while Preset Sync reported P03 active, which is what confirms both the 0-based
  index and that one decoder serves flash and RAM alike. **On silence, state only what was
  measured:** the active-preset-id register at `0x20000000` still returned `0x02` after the
  reads at indices 0, 2 and 40, so the read does not change the active preset. No audio was
  monitored and no before/after RAM comparison was recorded, so "does not change the
  sounding patch" is an inference from the register, not an observation of the audio.
* This command is unexercised by `bbedit`, which has no flash-read path at all, so it was
  the highest-value unproven read command until this session. A preset-backup CLI depends
  on it and can now rely on it.

#### Read String Blocks — AMP names
* **Raw (15 bytes):** `00 59 23 08 00 00 05 00 00 00 90 18 01 00 51`
  (space `05`, address `0x90000000`, size 280 — see §2.2. The upstream reading of
  these bytes as "address `0x00011890`, routing `05`" is a field misalignment, §2.7.1.)
* **USB (20 bytes):** `F0 00 32 0D 41 00 00 40 02 00 00 00 00 09 23 00 00 51 00 F7`
* **R/W:** R. **ACK:** none. **Returns:** a fragmented ASCII stream, §6.
* **CONFIRMED (code)** — `bbedit.startHandshake()` sends this literal with a recomputed
  checksum; `51` verified here.

#### Read String Blocks — CAB / IR names
* **Raw (15 bytes):** `00 59 23 08 00 00 05 00 00 00 80 18 01 00 61`
  (space `05`, address `0x80000000`, size 280. Upstream reads this as `0x00011880`; see §2.7.1.)
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

* **Load Preset** and **Toggle Block** have the same shape and are distinguished only by
  the **address space region**: Load Preset targets `0xE0000000 + preset_id`, Toggle Block
  targets `0x10000000 + dump_index`. On the wire that is the byte at offset 10 — `E0` vs
  `10` — which the upstream model calls a "sub-address at offsets 10–11" (`E0 01` vs
  `10 01`); the `01` beside it is the low byte of the 24-bit size, not part of any
  sub-address (§2.2). Get the address wrong and you write a parameter instead of switching
  patches.
* **Toggle Block** and **Change Model** are byte-identical in shape; only the target
  address distinguishes them. There is no structural guard against confusing them.
* **Change Knob** — `bbedit.changeKnob` clamps to 0–100 and emits `[val, 0x00]`. The
  16-bit field is real but the upper byte is never used in the documented 0–100 scale.
* **Write Flash** — `bbedit.savePresetToSlot` builds the 14-byte header, copies 92 bytes to
  offset 14, checksums at index 106, and then **waits up to 3000 ms for the ACK**, treating
  a timeout as failure. Any CLI that ever implements this must do the same.
  **This command permanently rewrites a slot and can destroy the user's presets.**

### 3.3 Acknowledgement

**The frame is CONFIRMED (docs+code); whether it means success is UNRESOLVED.**
**Never observed on this pedal** — every ACK-producing command is a write, and no write has
been sent.

```
8-byte acknowledgement:  00 59 00 01 00 00 00 FF
USB form (12 bytes):     F0 <10 base128 bytes> F7
```

Under the canonical grammar (§2.1) this parses as opcode `00`, length 1, payload `00`,
checksum `FF` — see §2.5, where it is one of the three frames only the general grammar can
express.

⚠️ **The payload byte's meaning is disputed and the dispute is not resolvable from source.**
`cuvave`'s parser reads it as `ACK(val[0] > 0)`, which makes the documented `0x00`
signal **failure**; `bbedit` treats the identical packet as a **successful** save
confirmation (`app.js:975-987`). One of the two is wrong.
*Settling test:* compare the ACK payload byte after a valid command against one sent with a
deliberately bad checksum. That requires a write, so it needs explicit user consent.
Recorded also at `protocol-algorithms.md` §5.

Until it is settled, a client must not report "saved" on the strength of this byte alone.
Verify a flash write by reading the slot back.

The trailing `FF` is the checksum formula applied to an all-zero body (`0xFF - 0`), which
verifies. `bbedit` recognises an ACK loosely: `length === 8 && bytes[3] === 0x01 &&
bytes[7] === 0xFF` — it does **not** check bytes 0–2. Matching the full 8 bytes is
stricter and safer.

Emitted after a **live memory write** (toggle, model, knob, routing) and after a **flash
save**. Read commands are answered with data, not an ACK — **CONFIRMED** for the four read
commands exercised in `device-validation.md`, none of which produced an ACK.
**HYPOTHESIS** for exactly which commands ACK — inherited from upstream, unverified.

A latent limitation in this project's own client, reported and not acted on:
`tools/blackboxctl/blackboxctl/protocol.py`'s `parse_frame` requires at least 15 bytes and
would raise "frame too short" on a real 8-byte ACK. It is unreachable today because every
write path is gated behind `hardware_confirmed=False`, so no ACK can arrive, but it must be
fixed before any write support is enabled.

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

**USB reassembly.** macOS/Web-MIDI *may* split a SysEx across several callbacks, and
`bbedit` buffers from a packet starting `F0` until a packet ending `F7` accordingly.
**CONFIRMED (code)** that `bbedit` does this.

⚠️ **The prediction that it would be necessary was wrong.** This document originally said a
125-byte SysEx "will very likely arrive fragmented". On this pedal over CoreMIDI it does
not: `device-validation.md` observed every 125-byte dump reply and both **340-byte** name
replies arriving as single, complete SysEx messages. Keep the reassembler — it costs
nothing and BLE genuinely needs it — but do not build a design around fragmentation being
the normal case, and do not treat a whole-message arrival as anomalous.

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

**The claim has two halves and they carry different labels.**

* **Read direction — CONFIRMED on this pedal.** Decoding a 92-byte flash or RAM image under
  identity reproduces real values. P41 matched all seven values known from the M-EFCS GUI;
  P01 and P03 matched every field recorded in `presets/hana.md`, roughly forty fields across
  the three presets. The one qualification: the two CAB Low Cut fields match only after
  §4.3's display mapping is applied, and only under a truncating convention (raw 24 = 87.2 Hz
  shown as 87, raw 22 = 81.6 Hz shown as 81). Every other field is an exact integer match.
  `device-validation.md` STEP 6.
* **Write direction — HYPOTHESIS (high confidence).** That a write to
  `0x10000000 + dump_index` pokes that same byte is inferred from the documented write
  literals only: Change Routing targets `0x10000002` and routing lives at index `0x02`;
  Toggle Block's example targets `…08` and FX on/off is at `0x08`; Change Knob's AMP Gain
  example targets `…20` and gain is at `0x20`. **No write has ever been sent to this pedal.**
  Settling test: one Change Knob to `0x10000000 + 0x20`, then re-read the RAM dump and check
  byte `0x20`. That is a write and needs explicit user consent.
  `device-validation.md` correction 7, `tools/blackboxctl/STATUS.md`.

The four lines of evidence below establish that the "+2" rule is wrong and that identity is
the relationship. Lines 1, 2 and 4 are about the map itself; line 3 is about writes and
inherits the label above.

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

**FX model count, 4 not 3.** The Korean manual's spec table lists three FX types — Noise
Gate, Boost, Compressor (`official-docs.md` §6). That is not a conflict with the four
above: the vendor's own release note records that firmware **V17 (2025-06-06) added
"AI Ms Gate"**, so the manual simply predates the fourth model. Four is correct for any
firmware from V17 onward. Not independently verified on this pedal, since reading the FX
model *list* is not something the protocol offers — only the selected id.

**AMP and CAB names — CONFIRMED on this pedal.** The 20 amp and 20 cab factory names, and
the slot ordering, were read out of flash (`device-validation.md` STEP 4–5) and match the
official lists in `official-docs.md` §2.1–§2.2. `protocol-algorithms.md` §6 had inferred
that ordering from `descriptions.js` insertion order and labelled it a medium-high
hypothesis; the inference was exactly right, position for position, with CAB slot 1 the
only difference and only because the user had overwritten it.

**Preset slot count:** 80 (P01–P80). Flash address = `index * 92`; index 79 → `0x1C64`.

The label depends on what is being claimed:

* **CONFIRMED as a product specification.** `bbedit` builds exactly 80 slots and upstream
  says `4F` = P80; independently, three official vendor sources say 80, and the manual's
  spec line reads "40+40" — P01–P40 factory, P41–P80 user (`official-docs.md` §2).
* **HYPOTHESIS as a flash bound on this unit.** The highest flash index ever read here is
  40. Nothing has established that index 79 answers and index 80 does not. This matters
  because an index check is the only bound on a flash-write target address
  (`tools/blackboxctl/STATUS.md`). *Settling test, cheap and read-only:* read flash index
  79, then index 80.

**⚠️ Preset names are not in the 92-byte image.** All 92 bytes are accounted for. `bbedit`
displays hard-coded placeholders (`"Preset 1"` … `"Preset 80"`) and never reads a name from
the device. Where the pedal stores per-preset names — or whether it stores them at all — is
**UNKNOWN**. A CLI that wants to show real preset names needs new research (a likely place
to look: further string blocks near the `0x000118xx` region used for amp/cab names).

**On `.am4` — this document's earlier verdict is superseded.** It previously said to treat
`.am4` as unverified upstream prose. That was wrong, and the correct statement now lives in
`capture-format-spec.md` §4.2 and `official-docs.md` §5, which this section defers to:

* The record magic **`AM4\0` is real and confirmed** in current BlackBox factory data — a
  7868-byte record with a 928-parameter GRU, shipped in `blackbox_am4_ampCab.bin`. It is a
  different, larger record than the 6204-byte AM2/AM3 form.
* AM2 → AM3 → AM4 are **firmware generations**, with dated vendor release notes; AM4 support
  arrives in V20.
* The **file extension** `.am4` has never been observed on this machine; every capture in
  the user's library and in the 1686-record community corpus is `.am2`, `.am2Data` or
  `.am3Data`. The extension alone remains unconfirmed.
* The upstream document conflated the record magic with the file extension. It is
  incomplete rather than false.

Whether *this* pedal can load AM4 depends on its firmware version, which is currently
**UNRESOLVED** — see `official-docs.md` §5 and the confidence summary in `README.md`.

### 4.3 Value scales

All parameters are normalised to **0–100** on the wire regardless of what the pedal's
screen shows. The client owns the display mapping. **CONFIRMED (docs+code).**

Concrete mappings implemented by `bbedit` (`formatDisplayValue`, `getDelayRange`) —
**CONFIRMED (code only)**, and to be treated as that editor's UI convention rather than a
verified DSP law:

* **CAB Low Cut:** `Hz = 20 + (raw/100) * 280` → 20 Hz … 300 Hz. The formula gives
  non-integers (raw 24 = 87.2, raw 22 = 81.6) and **the rounding convention is not
  documented upstream.** The two GUI figures recorded in `presets/hana.md` — 87 for raw 24
  and 81 for raw 22 — are both consistent with truncation toward zero and not with
  round-half-up, which is the only evidence either way. Do not present a computed Hz value
  as bit-exact agreement with a GUI reading; it agrees to within one display step.
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

**CONFIRMED on this pedal** for the request packets, the reply framing, the record layout
and the resulting names — `device-validation.md` STEP 4–5 read all 40 names out of flash.
Fragmentation behaviour was originally a HYPOTHESIS here; it has since been observed and
the answer is that **over USB there is none** (§6.2).

The pedal keeps the human-readable names of its 20 amp captures and 20 cabinet IRs in
hidden flash string blocks. A client must read both before it can render model names.

> **Read this first, because the rest of §6 is written around the BLE case.** Over USB the
> whole 20-name dictionary arrives as **one 340-byte SysEx message**, and the 280 body bytes
> are **20 fixed-width records of 14 bytes**. So slot *N* is directly indexable at
> `body[(N-1) * 14]` and none of the accumulator, null-counting or fragment-stitching
> machinery below is needed. A USB-only client should index directly; it is simpler and it
> cannot produce the phantom-name failure of §6.2. The accumulator remains documented
> because BLE genuinely fragments.
>
> ```
> reply  = header[0:14] + body[14:294] + checksum[294]
> body   = 20 records, stride 14
> record = ASCII "<1-based index><name>", NUL-terminated, NUL-padded to 14 bytes
> ```
>
> Capacity is therefore **13 characters including the numeric prefix** — 12 for slots 10–20,
> whose prefix is two digits. The longest record observed is `6WANGS212_ECM` at 13. Measured
> from 19 consecutive 14-byte deltas on both blocks, `device-validation.md` STEP 5.

### 6.1 Sequence

```
1. send  00 59 23 08 00 00 05 00 00 00 90 18 01 00 51     # AMP names: space 05, addr 0x90000000, size 280
2. accumulate notifications until 20 names have been extracted
3. send  00 59 23 08 00 00 05 00 00 00 80 18 01 00 61     # CAB names: space 05, addr 0x80000000, size 280
4. accumulate again until 20 names
5. only now begin normal polling
```

Upstream is explicit that **normal operation and RAM polling must stay paused until both
blocks are read**. `bbedit` enforces this with a `syncState` machine
(`READING_AMPS` → `READING_CABS` → `READY`) and only starts its 2.5 s poll timer at
`READY`.

### 6.2 Fragmentation and framing — the BLE path

The full 20-name dictionary exceeds the BLE MTU, so the pedal splits it across several
notifications. **Over USB it does not:** the entire block arrives as a single 340-byte
SysEx message, observed on both the AMP and the CAB read
(`device-validation.md` STEP 4, correction 3). What follows is the BLE algorithm, kept
because it is still needed there.

Per incoming raw packet, `bbedit` applies:

```
if len(packet) >= 14 and packet[0] == 0x00 and packet[1] == 0x59:
    payload = packet[14:]        # strip the standard 14-byte frame header
else:
    payload = packet             # continuation fragment, no header
rx_buffer.extend(payload)
```

⚠️ **Bug (CONFIRMED, code) — and it is NOT masked.** `bbedit` does **not** strip the
trailing checksum byte from these fragments, so a stray byte lands in the buffer. This
document originally argued the bug was harmless, on the reasoning that a checksum byte is
either `0x00` (reads as a terminator) or non-printable (dropped by the ASCII filter).

**That reasoning is refuted by this pedal.** The AMP name reply's checksum is `0x36`, which
is ASCII `"6"`, and the CAB reply's is `0x20`, a space. A naive null-split therefore yields
a phantom 21st name `"6"` (`device-validation.md` correction 4, STEP 5). The stop condition
in §6.3 — stop at 20 non-empty names — happens to discard it, but only by luck of ordering;
any parser that collects first and counts later gets 21 names.

**Strip the trailing checksum byte before splitting, or take only the first 20 records.**
Indexing by the 14-byte stride, as recommended at the top of §6, avoids the problem
entirely.

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

Worked examples **from the upstream documentation**, all consistent with the rule. These are
upstream illustrations of a factory device, **not this pedal's current state**: CAB slot 1
was overwritten with `1ML_BEST_IR` on 2026-08-28 (`presets/library.md` device write log,
confirmed by the flash read in `device-validation.md` STEP 4). For this pedal's actual 40
slot names, read STEP 4–5 there.

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

Feed the resulting arrays into `BLOCKS[1].modelNames` (AMP, from `0x90000000`) and
`BLOCKS[5].modelNames` (CAB, from `0x80000000`), each truncated to the first 20.

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

> The repository-wide version of this section — every CONFIRMED, HYPOTHESIS and UNRESOLVED
> claim across all five documents, in one list — is the confidence summary in
> [`README.md`](./README.md). What follows is this document's own view, updated after the
> 2026-08-28 device session.

### 9.1 Safe to implement now — read-only, high confidence

| Item | Why it is safe |
| :--- | :--- |
| Frame layout, offset-14 payload rule, checksum | **Confirmed on this pedal**, 25 frames re-parsed; §2. Note the offset-14 rule holds for opcodes `22`/`23` only, and that inbound checksums must not be verified from offset 4. |
| Base-128 encode/decode (§1.3) | **Confirmed on this pedal** end to end; also fuzz-tested locally and cross-checked against a second, independently written implementation. §1.4. |
| Request RAM Dump, Preset Sync | **Both sent and answered on this pedal.** Constant packets, verified checksums, also exercised continuously by a shipped editor. |
| Read String Blocks (AMP/CAB names) | **Both sent and answered on this pedal**; all 40 names read out of flash. Byte-identical literals in `bbedit`'s handshake; checksums verified. |
| The 92-byte field table and identity offset rule | **Confirmed on this pedal for reads** — three presets decode field-for-field against values known from the GUI and from `presets/hana.md`. Writes remain untested. §4.1. |
| Knob dictionaries | Doc and code match parameter-for-parameter with zero discrepancies. |
| Routing semantics, `D4` constant, 6-slot ghost rule | Doc and code agree; the `D4` invariant is proven arithmetically. |

**A read-only CLI — dump live state, decode it, list amp and cab names, report the active
preset — can be built entirely from confirmed material.** That is the right first
deliverable.

### 9.2 Needed empirical confirmation — most of it has now been done

**Settled since this table was written** — all by `device-validation.md`, 2026-08-28:

| Item | Outcome |
| :--- | :--- |
| ~~The Base-128 worked example (§1.4)~~ | **CONFIRMED a documentation defect.** The codec is correct; all seven commands round-tripped. §1.4. |
| ~~Response lengths (107 / 19)~~ | **CONFIRMED.** 107-byte dump and flash replies, 19-byte preset-sync reply, both observed. The 8-byte ACK remains unobserved because it needs a write. |
| ~~Read Flash Preset~~ | **CONFIRMED.** Indices 0, 2 and 40 read; index 2's payload is byte-identical to the live RAM dump. §3.1. |
| ~~USB SysEx fragmentation~~ | **Observed and it does not occur.** 125-byte and 340-byte replies each arrived as one complete SysEx. Keep the reassembler for BLE. §3.4, §6.2. |
| ~~Response types `11`, `21`, `24`~~ | Partly. Nothing unsolicited arrived except `20 04` preset-sync frames — six in the end-to-end run, thirteen across all seven logs. `11`/`21`/`24` were never seen; the demultiplexing rule (route by `address`, never by arrival order) is confirmed. |

**Still open:**

| Item | The settling test |
| :--- | :--- |
| ACK coverage and ACK **semantics** | Which commands ACK, and whether the payload byte means success or failure (§3.3). All ACK-producing commands are writes, so neither is settleable read-only. |
| Where preset names live | Unknown. §4.2. Probe neighbouring string blocks around the known name-table bases — read-only. |
| Whether flash indices above 40 answer | Read index 79, then index 80. Read-only and cheap. §4.2. |
| Whether this pedal accepts AM4 | Depends on its firmware version, which is UNRESOLVED — `official-docs.md` §5. The read-only `0x11` query would settle the version. |
| Model-switch effect on ghost bytes | Dump RAM, change model on the front panel, dump again, diff. Fully non-destructive. |
| Whether the unsolicited `20 04` frames are pedal-initiated | Repeat the session with M-EFCS closed. |

### 9.3 Dangerous — do not send

| Command | Risk |
| :--- | :--- |
| **☠️ Write Flash (Save)** — opcode `0x22`, 92-byte payload to a flash address; the `64` at offset 3 is the length, 92 + 8 = 100 (§2.1) | Permanently overwrites a preset slot. A wrong address, a wrong checksum, or a wrong 92-byte body destroys the user's work; upstream explicitly disclaims bricking risk. **Never send during protocol validation.** Any eventual implementation must first read every one of the 80 slots to a backup file. |
| **Load Preset** | Changes what the pedal is playing and discards unsaved live edits. |
| **Toggle / Change Model / Change Knob / Change Routing** | Overwrite live RAM. Individually recoverable by reloading the preset, but they silently destroy unsaved edits, and each is one wrong byte away from writing a different parameter than intended. |
| **Commit / UI Update** | Documented but never exercised by any code we have. Its stated effect ("forces RAM reload") could discard live state. Lowest-confidence write command in the catalogue. |

**Structural hazards to guard against in code, independent of the protocol:**

1. **Load Preset vs Toggle Block** differ only in the address high byte — `0xE0000000 +
   preset_id` vs `0x10000000 + dump_index`, i.e. offset 10 reading `E0` vs `10` — and are
   otherwise identical 1-byte writes. Build them through separate, named constructors and
   validate the target address region, not a "command type".
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
| 1 | `usb_sysex_protocol.md`'s encoded example does not match its own raw example under the `bbedit` algorithm, or any of four bit-order variants. It decodes instead to a different, checksum-valid packet. | **CONFIRMED documentation defect** — settled on hardware. The `bbedit` algorithm is correct; the encoded array is verbatim `cuvave`'s `test_encode_1`, pasted next to the wrong raw line. Never unit-test against that pair. §1.4 |
| 2 | `memory_map.md`: "`Write_Address = Dump_Index + 2`". | **The rule is wrong.** Identity is correct. **CONFIRMED on this pedal for reads** (three presets decode field-for-field under identity); **HYPOTHESIS for writes**, since none has been sent. §4.1 |
| 3 | The apparent MODELS violation (write `0E` / index `14`, …). | **Not a violation** — the Dump Index column silently switches from hex to decimal. `0x0E = 14`. §4.1 |
| 4 | `ble_protocol.md` calls Request RAM Dump "16-byte"; the literal it prints is 15 bytes. | **Doc is wrong.** 15 bytes; the checksum only verifies at 15. §3.1 |
| 5 | Offsets 12–13 are undescribed by the upstream field table but are always `00 00`, and the payload always begins at 14. | **Resolved by the canonical model.** Offsets 11–13 are a 24-bit size field, of which 12–13 are the always-zero high bytes; payload at 14 follows arithmetically as 6 + 1 + 4 + 3. True for opcodes `22`/`23` only. §2.2 |
| 6 | The address field sits at offsets 7–10 for DMA reads (routing `04`) but at 10–13 for string reads (routing `05`). | **STRUCK — there is no asymmetry.** Both forms are the same `(space, address, size)` payload; the string form is an upstream misparse of `0x90000000` + size 280 as address `0x00011890`. Refuted by the device's own reply. §2.7.1 |
| 5b | The upstream "command type" byte at offset 3, the "routing" field at 4–6, the "target id" at 7 and the "sub-address" at 10–11. | **All one byte out of alignment.** Offset 2 is the opcode, 3–5 a 24-bit payload length, 6 the space, 7–10 the address, 11–13 the size. The device returns "command types" `0x64`, `0x0C` and `0x20 01` that were never sent as commands, and a "routing" of `01 00 05` that the model does not allow. §2.1, §2.7.1 |
| 7 | Name-block stop condition: doc counts 20 nulls, `bbedit` counts 20 non-empty names. | **Use the code's version**; it is strictly more robust. §6.3 |
| 8 | `bbedit` does not strip a trailing checksum byte from name fragments. | **Not masked** — refuted by this pedal, whose AMP name reply's checksum is `0x36` = ASCII `"6"` and would become a phantom 21st name. Strip it, or index by the 14-byte stride. §6.2 |
| 9 | `bbedit`'s `/^\d+/` prefix strip is greedy and would corrupt a name that legitimately starts with digits. | Strip the *expected* ordinal instead, and warn on mismatch. §6.4 |
| 10 | `bbedit.encodeSysEx` flushes the accumulator unconditionally, emitting a spurious trailing `0x00` when `len(raw) % 7 == 0` (only Change Routing, 21 bytes). | Harmless — the decoder discards it. Prefer a conditional flush. §1.3 |
| 11 | Inbound types `11`, `21` (accepted by `bbedit`) and `24` (referenced in a code comment) are undocumented in the prose. | **Undocumented.** Log and ignore; do not error. §3.4 |
| 12 | Commit / UI Update exists in the prose but in no code. | **Doc only, unexercised.** Treat as unproven and dangerous. §3.2 |
| 13 | Read Flash Preset exists in the prose but in no code. | **Tested and CONFIRMED.** Read at flash indices 0, 2 and 40; index 2 returned a payload byte-identical to the live RAM dump. §3.1 |
| 14 | Preset names have no home in the 92-byte image and are hard-coded placeholders in `bbedit`. | **Unknown storage location.** Open research question. §4.2 |
| 15 | `memory_map.md` says amp captures are `.am4`; the user's library holds `.am2` / `.am2Data` / `.am3Data`. | **Verdict revised — the doc is incomplete, not wrong.** The record magic `AM4\0` is real and confirmed in factory data (`capture-format-spec.md` §4.2) and AM2/AM3/AM4 are firmware generations (`official-docs.md` §5). Only the *file extension* `.am4` is unobserved. §4.2 |
| 16 | `bbedit.changeRouting` validates only `length === 6`, not that the input is a permutation of 0–5. | Client-side weakness; validate properly. §5.1 |
| 17 | `bbedit`'s ACK matcher ignores bytes 0–2. | Match all 8 bytes. §3.3 |
| 18 | The ACK payload byte: `cuvave` reads it as `ACK(val[0] > 0)`, so the documented `0x00` means failure; `bbedit` reads the same packet as success. | **UNRESOLVED**, and not resolvable read-only. Do not report "saved" on this byte alone; read the slot back. §3.3 |
| 19 | This document predicted that a 125-byte SysEx "will very likely arrive fragmented" over USB, and §6 is built around MTU fragmentation. | **Refuted on this pedal.** Every reply, including two 340-byte name blocks, arrived as one complete SysEx. Keep the reassembler for BLE; do not design around fragmentation. §3.4, §6.2 |

---

*Compiled from CC BY-SA 4.0 documentation by Joel Victor
(https://github.com/jvsobrinho/mvave-blackbox-ble), cross-checked against the MIT-licensed
`mvave-blackbox-edit` editor by the same author. This derived specification is likewise
CC BY-SA 4.0.*

*This document originally closed with "no command described here has been transmitted to a
physical device". **That is no longer true, and the distinction matters.** On 2026-08-28 the
four read-only commands in §3.1 were transmitted to the user's own pedal — seven literals in
all — and answered; the raw bytes are in [`device-validation.md`](./device-validation.md) and
[`logs/`](./logs/). **No write of any kind has ever been sent.** Every command in §3.2 and
every claim about writes in §4.1 remains untested against silicon.*
