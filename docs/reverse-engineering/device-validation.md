# M-Vave BlackBox — live device validation over USB MIDI SysEx

Date: 2026-08-28
Host: macOS (Darwin 25.4.0), Apple Silicon
Device: M-Vave BlackBox, connected over USB, serial `4150353439333111`
Transport under test: USB MIDI SysEx (Base-128), **not** BLE.

**Every command sent during this session was read-only.** No `00 59 22` (RAM write)
header, no command type `0x64`, no Load Preset, no Toggle, no Knob, no Routing,
no Commit, no Write Flash Save was ever transmitted. The transport module
(`assert_read_only`) refuses to hand anything else to CoreMIDI.

## Attribution

Protocol documentation by **Joel Victor**, <https://github.com/jvsobrinho/mvave-blackbox-ble>,
licensed **CC BY-SA 4.0**. Reference packet/codec logic from
<https://github.com/jvsobrinho/mvave-blackbox-edit> (MIT) and, upstream of that,
the GPL-3.0 Cuvave MIDI parser. Work derived from these must carry the same
attribution and be licensed **GPL-3.0**.

## Artifacts

| File | Purpose |
| :--- | :--- |
| `scratchpad/proto/midi_transport.py` | CoreMIDI (ctypes) transport, Base-128 codec, checksum, read-only command builders, safety gate |
| `scratchpad/proto/validate.py` | Step-by-step validation driver (`codec`, `endpoints`, `ram`, `preset`, `cab`, `amp`, `flash`, `flash:N`, `all`) |
| `scratchpad/proto/log_all.txt` | Full transcript of the final end-to-end run |
| `scratchpad/proto/log_generic.txt` | Live re-run through the generalized `cmd_read()` primitive |
| `scratchpad/proto/base128_ref.py` | Independent codec by another agent, used as a cross-check (not written by this agent) |

## Note on the toolchain

pyobjc 12.2.2's `CoreMIDI` bindings on this machine **do not export**
`MIDISend`, `MIDISendSysex`, `MIDIReceived`, `MIDIPacketListInit` or
`MIDIPacketListAdd` (verified by enumerating `dir(CoreMIDI)` — 213 `MIDI*`
symbols, none of them a send function). `python-rtmidi` does not build here.
The transport therefore binds `/System/Library/Frameworks/CoreMIDI.framework`
directly with `ctypes`:

* send — `MIDISendSysex()` with a hand-built `MIDISysexSendRequest` (40 bytes,
  natural alignment; the struct sits *outside* the `#pragma pack(push,4)` region
  of `MIDIServices.h`).
* receive — `MIDIInputPortCreate()` with a `CFUNCTYPE` `MIDIReadProc`, parsing
  the `MIDIPacketList` by hand. `MIDIPacketList` and `MIDIPacket` **are** inside
  `#pragma pack(push,4)`: `numPackets` at 0, first packet at 4; within a packet
  `timeStamp` at 0, `length` at 8, `data` at 10, and on arm64 the next packet
  starts at `(&data[length] + 3) & ~3`.

---

## STEP 1 — Offline Base-128 / checksum self-test

Command: `validate.py codec`

```
doc raw          00 59 22 09 00 00 04 08 00 00 10 01 00 00 01 E1
doc encoded      00 32 09 49 00 00 40 02 09 00 00 00 18 00 00 00 01 5E 01
encode(doc raw)  00 32 09 49 00 00 00 02 08 00 00 00 11 00 00 00 01 42 03
MATCH doc pair:  False
decode(doc enc)  00 59 22 09 00 00 05 09 00 00 80 01 00 00 01 6F
  checksum of that packet: computed 0x6f stored 0x6f valid=True
  encode(decode(doc enc)) == doc enc : True
checksum(doc raw) = 0xe1 (doc says 0xe1)
roundtrip fuzz 1..219 bytes: True
```

### VERDICT — codec CORRECT, documentation example pair is MISMATCHED

The documented raw/encoded pair in `usb_sysex_protocol.md` **does not encode to
each other**, but this is a documentation defect, not a codec defect:

* `encode(decode(DOC_ENCODED)) == DOC_ENCODED` — bit-exact round trip.
* `decode(DOC_ENCODED)` = `00 59 22 09 00 00 05 09 00 00 80 01 00 00 01 6F`,
  which is a structurally valid packet whose stored checksum `0x6F` **validates**
  under the documented formula. A wrong algorithm producing a checksum-valid
  packet by chance is a 1-in-256 event.
* The checksum formula itself reproduces the documented `0xE1` exactly.
* Round-trip fuzz over 4380 random buffers of 1..219 bytes: all pass.

Conclusion: the CC BY-SA doc pasted an *encoded* packet from a different capture
next to the *raw* Toggle Block example. The algorithm is the LSB-first continuous
8→7 bit packer used by `mvave-blackbox-edit`. **CONFIRMED end to end below**, since
the packets this codec builds were understood by the real hardware and the
hardware's replies decoded to valid, checksum-correct, semantically correct data.

Secondary doc nit: the doc says "7 raw bytes pack perfectly into 8 SysEx bytes".
The reference encoder's unconditional trailing `push(accum & 0x7f)` makes 7 raw
bytes produce **9**, not 8. Harmless (the extra byte decodes to nothing) and it
does not arise for our 15-byte commands, which encode to 18 bytes.

---

## STEP 1b — CoreMIDI endpoint resolution

```
SOURCE      {'index': 0, 'ref': 241655832, 'name': 'USB Composite Device',
             'display': 'USB Composite Device', 'manufacturer': 'Jieli Technology'}
DESTINATION {'index': 0, 'ref': 241655833, 'name': 'USB Composite Device',
             'display': 'USB Composite Device', 'manufacturer': 'Jieli Technology'}
```

**CONFIRMED.** Endpoints are resolved by `kMIDIPropertyManufacturer == "Jieli Technology"`,
never by the integer refs, which are not stable across replug.

---

## STEP 2 — Request RAM Dump

```
[OUT RAW  ] 00 59 23 08 00 00 04 00 00 00 10 5C 00 00 8F
[OUT SYSEX] F0 00 32 0D 41 00 00 00 02 00 00 00 00 41 0B 00 00 0F 01 F7
[OUT DONE ] complete=True remaining=0 in 0.012s

[IN  SYSEX] (125B)
F0 00 32 0D 21 06 00 00 02 00 00 00 00 41 0B 00 00 55 00 00 08 50 40 00 02 03 02
04 00 00 20 40 00 02 04 00 18 10 00 41 0A 00 6A 00 50 03 40 0C 00 00 00 00 00 70
02 40 21 00 56 00 70 02 40 0F 00 00 00 70 01 20 06 00 24 00 00 00 00 00 00 00 00
54 00 3C 01 70 01 00 00 00 00 00 00 00 40 02 00 0F 00 40 01 10 06 00 0F 00 00 00
20 04 40 05 00 64 00 00 00 00 00 00 00 00 2C 03 F7

[IN  RAW   ] (107B)
00 59 23 64 00 00 04 00 00 00 10 5C 00 00 55 00 00 01 05 02 04 03 01 01 00 00 01
01 02 02 00 03 01 04 15 00 35 00 3A 00 32 00 00 00 00 00 17 00 43 00 2B 00 2E 00
3E 00 00 00 3C 00 32 00 48 00 00 00 00 00 00 00 54 00 2F 00 0F 00 00 00 00 00 00
00 0A 00 0F 00 30 00 31 00 1E 00 00 00 44 00 16 00 64 00 00 00 00 00 00 00 D6
```

### VERDICT — CONFIRMED, exactly 107 bytes as documented

* Reply header `00 59 23`, **command type `0x64` in the reply** (the doc only
  documents `0x64` as the *Write Flash* command type; the device also uses it as
  the reply opcode for 92-byte-payload reads). We never *sent* `0x64`.
* Bytes 4..13 echo the request routing/sub-address (`00 00 04 00 00 00 10 5C 00 00`).
* Payload is `d[14:106]`, 92 bytes; `d[106]` is the checksum.
* Stored checksum `0xD6` validates.

Decoded against `memory_map.md`:

```
patch volume = 85
routing      = FX, AMP, CAB, MOD, REV, DLY        (raw 00 01 05 02 04 03)
on/off       = FX=ON AMP=ON MOD=off DLY=off REV=ON CAB=ON
models       = FX=2(Compress) AMP=2 MOD=0(Chorus) DLY=3(Dual) REV=1(Hall) CAB=4
FX  knobs    = 21, 53, 58, 50, 0, 0
AMP knobs    = Gain=23 Level=67 Bass=43 Mid=46 Treble=62
MOD knobs    = Speed=60 Depth=50 Mix=72
DLY knobs    = Time=84 FB=47 Mix=15
REV knobs    = Decay=10 Mix=15 HP=48 LP=49 k5=30
CAB knobs    = Level=68 L-Cut=22 H-Cut=100
```

---

## STEP 3 — Preset Sync / Stream

```
[OUT RAW  ] 00 59 23 08 00 00 04 00 00 00 20 04 00 00 D7
[OUT SYSEX] F0 00 32 0D 41 00 00 00 02 00 00 00 00 42 00 00 00 57 01 F7

[IN  SYSEX] (24B) F0 00 32 0D 61 00 00 00 02 00 00 00 00 42 00 00 00 02 04 00 00 30 1A F7
[IN  RAW   ] (19B) 00 59 23 0C 00 00 04 00 00 00 20 04 00 00 02 02 00 00 D3
```

### VERDICT — CONFIRMED, 19 bytes, active preset ID at offset 14

* `d[14] = 0x02` → **P03**, in range P01..P80. Sanity-checked against STEP 6 below,
  where flash preset index 2 returns a payload byte-identical to the live RAM dump.
* Reply command type is `0x0C`.
* Stored checksum `0xD3` validates.
* This packet is also emitted **spontaneously** by the device (five unsolicited
  copies were observed during the flash-read step, see `log_all.txt`). A client
  must tolerate unsolicited `20 04` frames arriving between request and reply.

---

## STEP 4 — Read String Blocks: CAB / IR names — THE DECISIVE TEST

```
[OUT RAW  ] 00 59 23 08 00 00 05 00 00 00 80 18 01 00 61
[OUT SYSEX] F0 00 32 0D 41 00 00 40 02 00 00 00 00 08 23 00 00 61 00 F7

[IN  SYSEX] (340B, ONE message — no fragmentation over USB)
F0 00 32 0D 01 12 00 40 02 00 00 00 00 08 23 00 00 31 1A 31 7A 25 28 51 29 54 3E
25 12 05 00 00 00 32 14 59 6A 74 2B 4C 1C 36 60 7C 2A 73 06 00 00 33 2C 4D 01 73
2B 13 22 34 64 44 01 00 00 00 00 34 0E 45 11 53 25 11 2B 48 3E 0D 22 05 00 00 00
35 10 25 32 14 69 57 27 4B 00 00 00 00 00 00 00 36 2E 05 72 74 68 14 19 31 64 7C
2A 34 28 13 00 37 2C 3D 42 75 2B 50 21 33 60 00 00 00 00 00 00 38 0C 49 6A 14 48
53 18 31 64 00 00 00 00 00 00 39 1A 15 7B 34 2A 5A 31 6B 5A 24 4A 14 09 00 00 31
60 4C 7A 46 0D 59 29 43 68 44 11 03 00 00 00 31 62 18 22 74 0B 55 2B 31 72 60 01
03 00 00 00 31 64 34 2A 34 2A 50 2F 34 62 48 01 00 00 00 00 31 66 20 4A 74 0A 4D
18 32 26 5D 32 04 00 00 00 31 68 48 2A 36 0C 5D 37 5F 62 44 11 03 00 00 00 31 6A
28 1A 14 46 0C 18 5F 04 3D 42 05 00 00 00 31 6C 04 3A 56 0E 5B 30 34 62 40 01 00
00 00 00 31 6E 04 3A 36 4A 15 2A 34 62 40 01 00 00 00 00 31 70 10 3A 46 68 11 19
31 64 38 02 00 00 00 00 31 72 34 12 36 6A 5D 30 79 64 44 01 03 00 00 00 32 60 50
0A 36 2C 19 1A 31 64 00 00 00 00 00 00 20 00 F7

[IN  RAW   ] (295B)
00 59 23 20 01 00 05 00 00 00 80 18 01 00 31 4D 4C 5F 42 45 53 54 5F 49 52 00 00
00 32 4A 56 4D 5F 31 39 36 30 5F 35 37 00 00 33 56 33 30 5F 4D 44 34 32 31 00 00
00 00 34 47 31 32 2D 45 56 48 5F 43 54 00 00 00 35 48 49 46 49 5F 4F 4B 00 00 00
00 00 00 36 57 41 4E 47 53 32 31 32 5F 45 43 4D 00 37 56 4F 58 5F 41 43 33 30 00
00 00 00 00 38 46 52 4D 41 4E 31 31 32 00 00 00 00 00 39 4D 65 4F 53 69 63 6B 2D
49 49 49 00 00 31 30 53 6F 6C 64 53 43 34 31 32 00 00 00 31 31 46 44 5F 54 57 31
39 38 30 00 00 00 31 32 4D 45 53 41 5F 34 31 32 00 00 00 00 31 33 48 49 57 34 31
32 53 57 46 00 00 00 31 34 52 65 63 74 6F 5F 31 31 32 00 00 00 31 35 4A 43 31 32
30 5F 42 4F 58 00 00 00 31 36 41 67 75 6C 61 34 31 30 00 00 00 00 31 37 41 67 53
56 54 34 31 30 00 00 00 00 31 38 44 67 44 47 32 31 32 4E 00 00 00 00 31 39 4D 62
53 77 61 79 32 31 30 00 00 00 32 30 54 61 63 65 34 31 32 00 00 00 00 00 20
```

### VERDICT — PROTOCOL CONFIRMED END TO END ON THIS DEVICE

All nine slots whose names were already known from the M-EFCS GUI came back
**character-for-character identical**, including the recently-overwritten slot 1:

| # | Expected from GUI | Read from device | |
| -: | :--- | :--- | :-: |
| 1 | ML_BEST_IR | `1ML_BEST_IR` | match |
| 2 | JVM_1960_57 | `2JVM_1960_57` | match |
| 3 | V30_MD421 | `3V30_MD421` | match |
| 4 | G12-EVH_CT | `4G12-EVH_CT` | match |
| 5 | HIFI_OK | `5HIFI_OK` | match |
| 6 | WANGS212_ECM | `6WANGS212_ECM` | match |
| 7 | VOX_AC30 | `7VOX_AC30` | match |
| 8 | FRMAN112 | `8FRMAN112` | match |
| 9 | MeOSick-III | `9MeOSick-III` | match |

**All 20 IR / CAB slots (previously unknown from slot 10 onward):**

| Slot | Raw (with 1-based prefix) | Clean name |
| ---: | :--- | :--- |
| 1 | `1ML_BEST_IR` | ML_BEST_IR |
| 2 | `2JVM_1960_57` | JVM_1960_57 |
| 3 | `3V30_MD421` | V30_MD421 |
| 4 | `4G12-EVH_CT` | G12-EVH_CT |
| 5 | `5HIFI_OK` | HIFI_OK |
| 6 | `6WANGS212_ECM` | WANGS212_ECM |
| 7 | `7VOX_AC30` | VOX_AC30 |
| 8 | `8FRMAN112` | FRMAN112 |
| 9 | `9MeOSick-III` | MeOSick-III |
| 10 | `10SoldSC412` | SoldSC412 |
| 11 | `11FD_TW1980` | FD_TW1980 |
| 12 | `12MESA_412` | MESA_412 |
| 13 | `13HIW412SWF` | HIW412SWF |
| 14 | `14Recto_112` | Recto_112 |
| 15 | `15JC120_BOX` | JC120_BOX |
| 16 | `16Agula410` | Agula410 |
| 17 | `17AgSVT410` | AgSVT410 |
| 18 | `18DgDG212N` | DgDG212N |
| 19 | `19MbSway210` | MbSway210 |
| 20 | `20Tace412` | Tace412 |

Cross-check against the doc's own captured examples: `14Recto_112` matches
`memory_map.md`'s worked example byte-for-byte (`31 34 52 65 63 74 6F 5F 31 31 32 00`).

**Deviation from the documentation:** `memory_map.md` describes an MTU
fragmentation problem and prescribes a stateful accumulator that counts null
terminators until 20 are seen. Over **USB SysEx that does not happen** — the whole
dictionary arrives as a single 340-byte SysEx message. The accumulator is still
implemented (it is needed on BLE and harmless here), but a USB-only client can
treat this as one shot.

---

## STEP 5 — Read String Blocks: AMP names

```
[OUT RAW  ] 00 59 23 08 00 00 05 00 00 00 90 18 01 00 51
[OUT SYSEX] F0 00 32 0D 41 00 00 40 02 00 00 00 00 09 23 00 00 51 00 F7

[IN  SYSEX] (340B)
F0 00 32 0D 01 12 00 40 02 00 00 00 00 09 23 00 00 31 14 65 01 03 66 57 21 4C 00
00 00 00 00 00 00 32 0C 11 7A 35 08 13 00 00 00 00 00 00 00 00 00 33 14 0D 0A 23
06 4C 2F 43 18 01 00 00 00 00 00 34 04 31 2A 55 68 57 27 44 00 00 00 00 00 00 00
35 24 05 22 75 6B 13 22 00 00 00 00 00 00 00 00 36 1A 35 31 15 48 55 22 5F 1E 11
02 00 00 00 00 37 26 55 02 15 68 57 27 44 00 00 00 00 00 00 00 38 08 05 12 35 69
54 2F 44 26 01 00 00 00 00 00 39 14 65 01 03 66 17 22 53 00 00 00 00 00 00 00 31
60 28 42 34 6A 17 22 53 00 00 00 00 00 00 00 31 62 14 32 05 69 57 1A 31 6A 40 01
00 00 00 00 31 64 18 12 15 29 53 20 4E 00 00 00 00 00 00 00 31 66 60 1A 74 0B 51
29 00 00 00 00 00 00 00 00 31 68 48 7A 74 29 13 1A 30 00 00 00 00 00 00 00 31 6A
28 32 55 09 00 00 00 00 00 00 00 00 00 00 31 6C 04 3A 46 48 58 1B 35 60 7C 12 34
0A 00 00 31 6E 04 02 37 4A 15 2A 5F 04 4D 02 00 00 00 00 31 70 40 52 26 28 1D 32
64 72 7D 12 34 0A 00 00 31 72 10 3A 06 2B 5D 2F 42 26 01 00 00 00 00 00 32 60 34
0A 26 6E 1A 26 6D 3E 09 1A 05 00 00 00 36 00 F7

[IN  RAW   ] (295B)
00 59 23 20 01 00 05 00 00 00 90 18 01 00 31 4A 39 30 30 5F 43 4C 00 00 00 00 00
00 32 46 44 5F 43 4C 00 00 00 00 00 00 00 00 33 4A 43 31 32 30 5F 43 4C 00 00 00
00 00 34 42 4C 55 45 5F 4F 44 00 00 00 00 00 00 35 52 41 54 5F 4F 44 00 00 00 00
00 00 00 36 4D 2D 56 41 56 45 5F 4F 44 00 00 00 00 37 53 55 50 41 5F 4F 44 00 00
00 00 00 00 38 44 41 52 4B 53 5F 44 53 00 00 00 00 00 39 4A 39 30 30 5F 44 53 00
00 00 00 00 00 31 30 4A 48 53 5F 44 53 00 00 00 00 00 00 31 31 45 56 48 5F 35 31
35 30 00 00 00 00 31 32 46 52 49 4D 41 4E 00 00 00 00 00 00 31 33 58 43 5F 44 53
00 00 00 00 00 00 00 31 34 52 4F 4F 4D 34 30 00 00 00 00 00 00 31 35 4A 56 4D 00
00 00 00 00 00 00 00 00 31 36 41 67 44 62 37 35 30 5F 42 53 00 00 31 37 41 70 53
56 54 5F 42 53 00 00 00 00 31 38 50 6A 42 75 64 64 79 5F 42 53 00 00 31 39 44 67
58 75 5F 42 53 00 00 00 00 00 32 30 4D 61 72 6B 4C 6D 5F 42 53 00 00 00 36
```

### VERDICT — CONFIRMED. All 20 AMP capture slots:

| Slot | Raw (with 1-based prefix) | Clean name |
| ---: | :--- | :--- |
| 1 | `1J900_CL` | J900_CL |
| 2 | `2FD_CL` | FD_CL |
| 3 | `3JC120_CL` | JC120_CL |
| 4 | `4BLUE_OD` | BLUE_OD |
| 5 | `5RAT_OD` | RAT_OD |
| 6 | `6M-VAVE_OD` | M-VAVE_OD |
| 7 | `7SUPA_OD` | SUPA_OD |
| 8 | `8DARKS_DS` | DARKS_DS |
| 9 | `9J900_DS` | J900_DS |
| 10 | `10JHS_DS` | JHS_DS |
| 11 | `11EVH_5150` | EVH_5150 |
| 12 | `12FRIMAN` | FRIMAN |
| 13 | `13XC_DS` | XC_DS |
| 14 | `14ROOM40` | ROOM40 |
| 15 | `15JVM` | JVM |
| 16 | `16AgDb750_BS` | AgDb750_BS |
| 17 | `17ApSVT_BS` | ApSVT_BS |
| 18 | `18PjBuddy_BS` | PjBuddy_BS |
| 19 | `19DgXu_BS` | DgXu_BS |
| 20 | `20MarkLm_BS` | MarkLm_BS |

Parsing gotcha: the final byte of the reply is the packet checksum, and for these
two replies it happens to be printable ASCII (`0x20` = space for CAB, `0x36` = `"6"`
for AMP). A naive null-split parser yields a spurious 21st name `"6"` for the AMP
block. **Strip the trailing checksum byte before splitting**, or take only the
first 20 entries.

### Name-block record layout — CONFIRMED, fixed 14-byte stride

Measured on both blocks: after the 14-byte reply header and before the 1-byte
checksum there are exactly **280 body bytes = 20 records × 14 bytes**, and the
start offset of every name is an exact multiple of 14 (deltas: 14 ×19 for both
blocks, no exceptions).

```
reply = header[0:14] + body[14:294] + checksum[294]
body  = 20 records, stride 14
record = ASCII "<1-based index><name>", null-padded to 14 bytes
```

Slot *N* (1-based) therefore lives at body offset `(N-1) * 14`, which means a
client can index a slot directly instead of null-splitting. The longest observed
record is `6WANGS212_ECM` at 13 characters plus one null terminator, so the usable
field is **13 characters including the numeric prefix** (12 for slots 10–20, whose
prefix is 2 digits).

---

## STEP 6 — Read Flash Preset

`Address = preset_index * 92`, injected 4-byte little-endian at offset 7.

### 6a. Index 0 (P01), address 0

```
[OUT RAW  ] 00 59 23 08 00 00 04 00 00 00 00 5C 00 00 9F
[OUT SYSEX] F0 00 32 0D 41 00 00 00 02 00 00 00 00 40 0B 00 00 1F 01 F7

[IN  SYSEX] (125B)
F0 00 32 0D 21 06 00 00 02 00 00 00 00 40 0B 00 00 55 00 04 28 20 00 01 00 03 02
04 08 10 20 40 00 02 02 00 18 00 40 42 02 00 46 00 38 03 40 0C 00 00 00 00 00 10
03 00 23 00 5A 00 38 03 60 0B 00 00 00 50 00 40 02 00 05 00 00 00 00 00 00 00 00
12 00 18 00 60 00 00 00 00 00 00 00 00 00 07 00 14 00 70 01 50 05 40 16 00 00 00
30 04 00 06 00 64 00 00 00 00 00 00 00 00 14 03 F7

[IN  RAW   ] (107B)
00 59 23 64 00 00 04 00 00 00 00 5C 00 00 55 00 01 05 02 04 00 03 01 01 01 01 01
01 02 01 00 03 00 0A 05 00 23 00 37 00 32 00 00 00 00 00 19 00 46 00 2D 00 37 00
2F 00 00 00 14 00 14 00 0A 00 00 00 00 00 00 00 12 00 06 00 06 00 00 00 00 00 00
00 1C 00 14 00 3C 00 2D 00 2D 00 00 00 46 00 18 00 64 00 00 00 00 00 00 00 CA
```

Decoded (checksum `0xCA` validates):

```
patch volume = 85
routing      = AMP, CAB, MOD, REV, FX, DLY
on/off       = all ON
models       = FX=2(Compress) AMP=1 -> "FD_CL"  MOD=0(Chorus) DLY=3(Dual)
               REV=0(Room) CAB=10 -> "FD_TW1980"
AMP knobs    = Gain=25 Level=70 Bass=45 Mid=55 Treble=47
MOD knobs    = Speed=20 Depth=20 Mix=10
DLY knobs    = Time=18 FB=6 Mix=6
REV knobs    = Decay=28 Mix=20 HP=60 LP=45 k5=45
CAB knobs    = Level=70 L-Cut=24 H-Cut=100
```

### 6b. Index 2 (P03), address 184 — the address/index cross-check

```
[OUT RAW  ] 00 59 23 08 00 00 04 B8 00 00 00 5C 00 00 E7
[OUT SYSEX] F0 00 32 0D 41 00 00 00 02 38 01 00 00 40 0B 00 00 67 01 F7

[IN  RAW   ] (107B)
00 59 23 64 00 00 04 B8 00 00 00 5C 00 00 55 00 00 01 05 02 04 03 01 01 00 00 01
01 02 02 00 03 01 04 15 00 35 00 3A 00 32 00 00 00 00 00 17 00 43 00 2B 00 2E 00
3E 00 00 00 3C 00 32 00 48 00 00 00 00 00 00 00 54 00 2F 00 0F 00 00 00 00 00 00
00 0A 00 0F 00 30 00 31 00 1E 00 00 00 44 00 16 00 64 00 00 00 00 00 00 00 2E
```

**CONFIRMED — the 92-byte payload is byte-identical to the live RAM dump from
STEP 2**, and Preset Sync reported the active preset as `0x02`.

This resolves the write-address versus dump-index ambiguity for DMA:

* `Address = preset_index * 92`, **0-based**, so P01 = index 0, P03 = index 2
  (address 184 = `B8 00 00 00` LE), P41 = index 40 (address 3680 = `60 0E 00 00` LE).
* The RAM dump and the flash read of the currently active slot return the same
  92 bytes with the same internal layout — one decoder serves both.

### 6c. Index 40 (P41) — "Wonderwall Live", the memory-map ground truth

```
[OUT RAW  ] 00 59 23 08 00 00 04 60 0E 00 00 5C 00 00 31
[OUT SYSEX] F0 00 32 0D 41 00 00 00 02 60 1C 00 00 40 0B 00 00 31 00 F7

[IN  SYSEX] (125B)
F0 00 32 0D 21 06 00 00 02 60 1C 00 00 40 0B 00 00 55 00 04 28 20 00 01 00 03 02
04 08 00 20 40 00 02 00 00 18 00 40 41 07 00 46 00 38 03 60 0D 00 00 00 00 00 50
05 00 23 00 50 00 70 03 00 0F 00 00 00 50 00 60 02 00 06 00 00 00 00 00 00 00 00
29 00 78 00 50 03 40 03 00 64 00 10 03 20 06 00 0C 00 70 01 70 06 40 07 00 00 00
58 04 40 06 00 64 00 00 00 00 00 00 00 00 26 02 F7

[IN  RAW   ] (107B)
00 59 23 64 00 00 04 60 0E 00 00 5C 00 00 55 00 01 05 02 04 00 03 01 01 01 00 01
01 02 00 00 03 00 06 0F 00 23 00 37 00 37 00 00 00 00 00 2D 00 46 00 28 00 3E 00
3C 00 00 00 14 00 16 00 0C 00 00 00 00 00 00 00 29 00 1E 00 1D 00 07 00 32 00 32
00 19 00 0C 00 3C 00 37 00 0F 00 00 00 4B 00 1A 00 64 00 00 00 00 00 00 00 93
```

Decoded (checksum `0x93` validates):

```
92-byte payload:
55 00 01 05 02 04 00 03 01 01 01 00 01 01 02 00 00 03 00 06 0F 00 23 00 37 00 37
00 00 00 00 00 2D 00 46 00 28 00 3E 00 3C 00 00 00 14 00 16 00 0C 00 00 00 00 00
00 00 29 00 1E 00 1D 00 07 00 32 00 32 00 19 00 0C 00 3C 00 37 00 0F 00 00 00 4B
00 1A 00 64 00 00 00 00 00 00 00

patch volume = 85
routing      = AMP, CAB, MOD, REV, FX, DLY
on/off       = FX=ON AMP=ON MOD=ON DLY=off REV=ON CAB=ON
models       = FX=2(Compress) AMP=0 MOD=0(Chorus) DLY=3(Dual) REV=0(Room) CAB=6
AMP knobs    = Gain=45 Level=70 Bass=40 Mid=62 Treble=60
MOD knobs    = Speed=20 Depth=22 Mix=12
REV knobs    = Decay=25 Mix=12 HP=60 LP=55 k5=15
CAB knobs    = Level=75 L-Cut=26 H-Cut=100
```

### VERDICT — MEMORY MAP CONFIRMED. All seven known GUI values match:

| Known from GUI | Decoded from flash | |
| :--- | :--- | :-: |
| amp = J900_CL | model byte `0x00` → AMP name list entry 1 = `J900_CL` | match |
| amp gain = 45 | `[0x20]` LE = 45 | match |
| cab = VOX_AC30 | model byte `0x06` → CAB name list entry 7 = `VOX_AC30` | match |
| chorus mix = 12 | MOD type 0 (Chorus), `[0x30]` LE = 12 | match |
| room reverb mix = 12 | REV type 0 (Room), `[0x46]` LE = 12 | match |
| delay off | state byte `[0x0B]` = 0x00 | match |
| total volume = 85 | `[0x00]` LE = 85 | match |

Seven independent fields agreeing is decisive. The 92-byte memory map,
the little-endian 16-bit knob encoding, the 0–100 normalized scale, the block
on/off byte order, the model-byte dictionaries, and the **model byte → name-list
index mapping (0-based model byte indexes the 20-name list)** are all CONFIRMED
on this hardware.

---

## STEP 7 — A unified packet field model (CONFIRMED on 14/14 packets: 7 sent, 7 unique replies)

The published protocol doc describes the packet as
`header(3) | command type(1) | routing(3) | target id(1) | padding(2) | sub-address(2) | payload | cs`
and then has to describe each command's bytes as a special case. That framing is
**one byte out of alignment**. Every packet observed in this session — 7 distinct
requests we sent and the 7 unique reply frames the device returned (the 29 inbound
SysEx messages across the logs collapse to those 7), 14 packets total —
fits this single model with no exceptions:

| Offset | Size | Field | Notes |
| :--- | :--- | :--- | :--- |
| 0 | 3 | magic | `00 59 22` (write) / `00 59 23` (read) |
| 3 | 2 | **length, LE16** | always `payload_len + 8` |
| 5 | 2 | **space selector** | `00 04` = parameter/preset space, `00 05` = string space |
| 7 | 4 | **address, LE32** | |
| 11 | 3 | **size, LE24** | bytes requested (request) / bytes returned (reply) |
| 14 | var | payload | absent in requests |
| N-1 | 1 | checksum | `0xFF - (sum of bytes 5 .. N-2)` |

Measured, every row independently verified:

```
packet               N hdr        len    sp         addr  size24  pay len=pay+8 size24=pay  cs@5
RAM dump req        15 005923       8  0004   0x10000000      92    0      True       True  True
preset sync req     15 005923       8  0004   0x20000000       4    0      True       True  True
CAB names req       15 005923       8  0005   0x80000000     280    0      True       True  True
AMP names req       15 005923       8  0005   0x90000000     280    0      True       True  True
flash0 req          15 005923       8  0004   0x00000000      92    0      True       True  True
flash2 req          15 005923       8  0004   0x000000B8      92    0      True       True  True
flash40 req         15 005923       8  0004   0x00000E60      92    0      True       True  True
reply len107       107 005923     100  0004   0x10000000      92   92      True       True  True
reply len19         19 005923      12  0004   0x20000000       4    4      True       True  True
reply len295       295 005923     288  0005   0x80000000     280  280      True       True  True
reply len295       295 005923     288  0005   0x90000000     280  280      True       True  True
reply len107       107 005923     100  0004   0x00000000      92   92      True       True  True
reply len107       107 005923     100  0004   0x000000B8      92   92      True       True  True
reply len107       107 005923     100  0004   0x00000E60      92   92      True       True  True
```

The protocol is simply **memory-mapped read/write with an address space**:

| Address | Space | Meaning |
| :--- | :--- | :--- |
| `0x00000000 + index*92` | 04 | preset slot in flash, 92 bytes, index 0-based (P01 = 0) |
| `0x10000000` | 04 | live RAM state, 92 bytes — same layout as a preset |
| `0x20000000` | 04 | current preset id, 4 bytes, id in byte 0 |
| `0x80000000` | 05 | CAB / IR name table, 280 bytes |
| `0x90000000` | 05 | AMP capture name table, 280 bytes |
| `0xE0000000 + id` | 04 | preset load trigger (documented, **never sent**) |
| `0xF0000000` | 04 | commit / UI refresh (documented, **never sent**) |

Consequences that matter for the CLI:

* The doc's "command type" byte at offset 3 is really the length low byte. It is
  `0x08` in every read request only because those carry no payload; it is `0x64`
  in a 92-byte reply because 92 + 8 = 100; it is `0x20 01` in a name reply because
  280 + 8 = 288. There is no `0x64` "write" opcode being echoed back at us.
* The doc's "AMP Names Base Address: Flash `90 18 01 00` (Little Endian)" is that
  same off-by-one misparse. The real address is `0x90000000`; the `18 01 00` beside
  it is the 24-bit **size** field, 280 = 20 names × 14 bytes. Reading it as a
  little-endian address (0x00011890) would be wrong, and the value only worked
  because the bytes land in the right places by accident.
* A single generic `read(space, address, size)` primitive replaces all four
  documented read commands.

### The model verified live

`midi_transport.cmd_read(address, size, space)` implements the model. It
reproduces all seven read commands used in this session **byte-for-byte** against
the hand-written builders, and a live re-run through the generic path
(`scratchpad/proto/log_generic.txt`) returned the same 92-byte RAM state and the
same 20 IR names, with the names now indexed directly by `body[(N-1)*14]` instead
of null-splitting:

```
parsed: space=0x0400 addr=0x10000000 size=92  payload=92  cs_ok=True
parsed: space=0x0500 addr=0x80000000 size=280 payload=280 cs_ok=True
names by 14-byte stride: ['1ML_BEST_IR', '2JVM_1960_57', ..., '20Tace412']
```

`parse_reply()` also parses the unsolicited `0x20000000` frames cleanly, which
gives the CLI its demultiplexing rule: **route replies by the `address` field,
never by arrival order.**

### HYPOTHESIS — the same model explains every documented *write* command

Not tested (writes are out of scope for this session), but the model reproduces
each documented write example exactly, which is strong evidence:

| Documented command | Under this model |
| :--- | :--- |
| Toggle Block `…09 00 00 04 [BLK] 00 00 10 01 00 00 [STATE] CS` | len 9 = 1+8; addr `0x10000000` + BLK; size 1; payload 1 |
| Change Knob `…0A 00 00 04 [KNB] 00 00 10 02 00 00 [LSB][MSB] CS` | len 10 = 2+8; addr `0x10000000` + KNB; size 2; payload 2 |
| Change Routing `…0E 00 00 04 02 00 00 10 06 00 00 [6 bytes]` | len 14 = 6+8; addr `0x10000002`; size 6; payload 6 |
| Write Flash Save `…64 00 00 04 [ADDR4] 5C 00 00 [92 bytes] CS` | len 100 = 92+8; size 92; payload 92 |
| Commit/UI `00 59 22 08 00 00 04 00 00 00 F0 00 00 00 0B` | len 8; addr `0xF0000000`; size 0; **checksum 0x0B reproduces exactly** |

Note that Change Routing's address `0x10000002` is `0x10000000 + 2`, and `0x02` is
exactly the routing field's offset in the 92-byte map; Toggle Block's `0x08` is the
FX on/off offset; Change Knob's `0x20` is the AMP Gain offset. **The RAM write address
is `0x10000000 + dump_index`, an identity mapping** — which is the cleanest available
refutation of the `Write_Address = Dump_Index + 2` rule in `memory_map.md`.

Test that settles it: send a Change Knob to `0x10000000 + 0x20` and read the RAM
dump back; byte `0x20` should change. **Do not run this without explicit user
consent** — it is a write.

---

## Independent cross-check of the codec

A second agent in this workflow independently implemented the Base-128 codec at
`scratchpad/proto/base128_ref.py`, derived from the GPL-3.0 Rust `cuvave-midi`
parser's own test vectors rather than from the JavaScript editor this module
followed. The two implementations were compared directly:

* identical output on 299 random buffers of length 1..299, encode and decode;
* identical decode of **all 13 SysEx messages captured from the device** in this
  session.

Two independently sourced implementations agreeing bit-for-bit, plus the hardware
answering correctly, is the strongest available evidence that the mismatched
example in `usb_sysex_protocol.md` is a documentation defect and not a real
algorithm difference.

---

## Corrections and clarifications to the published documentation

1. **CONFIRMED — the Base-128 example pair in `usb_sysex_protocol.md` is
   mismatched.** The encoded string decodes to a *different* raw packet
   (`00 59 22 09 00 00 05 09 00 00 80 01 00 00 01 6F`) than the raw string printed
   beside it. The algorithm itself is correct. Anyone using that pair as a unit-test
   vector will conclude, wrongly, that their encoder is broken.

2. **CONFIRMED — the checksum sum starts at offset 5, not offset 4.**
   The two string-block replies carry `byte[4] = 0x01` and their stored checksums
   validate **only** with the sum taken over `[5 : N-1]`:

   | Packet | len | byte[4] | stored | sum from 4 | sum from 5 |
   | :--- | --: | :-- | :-- | :-- | :-- |
   | RAM dump reply | 107 | 0x00 | 0xD6 | 0xD6 ✓ | 0xD6 ✓ |
   | preset sync reply | 19 | 0x00 | 0xD3 | 0xD3 ✓ | 0xD3 ✓ |
   | flash idx 0 reply | 107 | 0x00 | 0xCA | 0xCA ✓ | 0xCA ✓ |
   | flash idx 2 reply | 107 | 0x00 | 0x2E | 0x2E ✓ | 0x2E ✓ |
   | flash idx 40 reply | 107 | 0x00 | 0x93 | 0x93 ✓ | 0x93 ✓ |
   | CAB names reply | 295 | **0x01** | 0x20 | 0x1F ✗ | 0x20 ✓ |
   | AMP names reply | 295 | **0x01** | 0x36 | 0x35 ✗ | 0x36 ✓ |

   Offset 5 explains 7/7 observed packets; offset 4 explains 5/7. Every example in
   the documentation has `byte[4] == 0x00`, which makes the two indistinguishable
   there. Our outbound commands also all have `byte[4] == 0x00`, so the published
   formula still produces correct commands — the device accepted and answered every
   one — but **a client that verifies inbound checksums must use offset 5.**

3. **CONFIRMED — no MTU fragmentation on USB.** `memory_map.md` prescribes a
   null-terminator-counting accumulator because BLE fragments the name dictionary.
   Over USB SysEx the whole 20-name block arrives as a single 340-byte message.

4. **CONFIRMED — the name-block reply's trailing checksum byte can be printable
   ASCII** and will produce a phantom 21st name if you split on nulls naively
   (observed: `"6"` from `0x36` on the AMP block).

5. **CONFIRMED — there is no "command type" byte; offset 3–4 is a 16-bit length.**
   The bytes that look like reply opcodes (`0x64` for 92-byte reads, `0x0C` for
   preset sync, `0x20 01` for string blocks) are `payload_len + 8` in little-endian.
   See STEP 7. This matters because `0x64` is documented as the *Write Flash Save*
   command type, so a client following the doc will see every RAM dump reply as if
   it were a flash-write opcode.

6. **CONFIRMED — the device emits unsolicited `20 04` preset-sync frames.** Five
   arrived unrequested during the flash-read step. Clients must demultiplex replies
   rather than assuming the next inbound message answers the last request. (Whether
   these are self-initiated by the pedal or triggered by the concurrently running
   M-EFCS GUI was not isolated — see open questions.)

7. **HYPOTHESIS, high confidence — `Write_Address = Dump_Index + 2` does not hold;
   the mapping is the identity.** Two independent lines of evidence:
   * On reads, every field decoded correctly with `dump_index ==` the hex "Write Addr"
     column: volume 0x00, routing 0x02, states 0x08–0x0D, models 0x0E–0x13, knobs
     0x14/0x20/0x2C/0x38/0x44/0x50. All seven known P41 GUI values match under that
     mapping. The table's "Dump Index" column for the model rows reads 14–19, which is
     those same addresses written in **decimal** — the `+2` rule looks like an artifact
     of that mixed radix.
   * Under the field model in STEP 7, the documented *write* commands address
     `0x10000000 + dump_index` directly: Change Routing targets `0x10000002` and
     routing lives at dump index 0x02; Toggle Block's example targets `…08` and FX
     on/off is at 0x08; Change Knob's AMP Gain example targets `…20` and gain is at
     0x20.

   Not promoted to CONFIRMED because no write was performed. Test that settles it:
   Change Knob to `0x10000000 + 0x20`, then re-read the RAM dump and check byte 0x20.
   That is a write — **requires explicit user consent.**

8. **HYPOTHESIS (minor) — "7 raw bytes pack into 8 SysEx bytes"** understates by one.
   The reference encoder's unconditional trailing push makes 7 → 9. It does not affect
   any packet used here. Test: encode a 7-byte buffer and count.

9. **Unresolved from the task brief — `memory_map.md` calls amp captures `.am4`**,
   while the user's library holds `.am2` / `.am3Data`. Nothing in the wire protocol
   touches the file extension, so this validation neither confirms nor refutes it.
   Flagged as a doc inconsistency, not a fact.

---

## Open questions for later agents

* The `am2`/`am3` capture files (6204 bytes) were not exercised here. The name
  dictionary read confirms only the *names* the pedal holds, not the payloads.
* The 14-byte name-record stride is confirmed for *reads*. Whether a writer must
  pad to the same stride, and what the pedal does with a name longer than 13
  characters, is untested.
* Whether the unsolicited `20 04` frames are pedal-initiated or a side effect of
  M-EFCS polling concurrently was not isolated (M-EFCS was left untouched by
  instruction).
* No write path of any kind was tested, by design.

## Safety record for this session

Commands transmitted, in order, and nothing else:

```
00 59 23 08 00 00 04 00 00 00 10 5C 00 00 8F   Request RAM Dump
00 59 23 08 00 00 04 00 00 00 20 04 00 00 D7   Preset Sync
00 59 23 08 00 00 05 00 00 00 80 18 01 00 61   Read String Blocks, CAB
00 59 23 08 00 00 05 00 00 00 90 18 01 00 51   Read String Blocks, AMP
00 59 23 08 00 00 04 00 00 00 00 5C 00 00 9F   Read Flash Preset index 0
00 59 23 08 00 00 04 B8 00 00 00 5C 00 00 E7   Read Flash Preset index 2
00 59 23 08 00 00 04 60 0E 00 00 5C 00 00 31   Read Flash Preset index 40
```

All seven use the `00 59 23` read header with command type `0x08`. The
`assert_read_only()` gate in `midi_transport.py` was unit-tested to reject the
`00 59 22` write header, command type `0x64`, command type `0x0A`, routing bytes
other than `04`/`05`, and any packet with a bad checksum.
