# M-Vave BlackBox — reverse-engineering documentation

> **Dated evidence boundary.** The confidence tables in this directory close at the
> read-only 2026-08-28 protocol session. They are preserved as the derivation record, not as
> the current implementation status. Reversible RAM writes, preset flash save/restore,
> AMP/CAB staging and commits, and the P01–P12 migration were subsequently exercised on
> 2026-08-29. For current command support and safety limits, use
> [`tools/blackboxctl/STATUS.md`](../../tools/blackboxctl/STATUS.md).

Five documents in this directory describe the M-Vave BlackBox at four levels: the wire
protocol it speaks over USB MIDI SysEx and BLE GATT, the 92-byte preset image that protocol
reads and writes, the `.am2`/`.am3`/`.am4` neural-capture container and the `.wav` impulse
responses that feed the cab slot, and what the vendor's own manuals and firmware release
notes say about all of it. Most of the protocol layer began as a consolidation of published
prior art; on 2026-08-28 seven **distinct** read-only commands were transmitted to the
user's own pedal and seven unique reply frames were captured, which turned a large part of it
from inherited inference into measurement. Three counts of that session all appear in these
documents and all three are right: **four read command shapes, five address bases, seven
transmitted byte literals** — sixteen transmissions in total across the seven preserved
logs. **By the close of that session, the frame format, the 92-byte memory map, the five read
address bases and all 40 slot names were confirmed on this hardware. No write was sent in
that session, so its write-command labels record the evidence boundary as it stood then.**

---

## Reading order

1. **This page**, for the confidence summary below — it is the only place that states, in
   one list, what is measured and what is inferred.
2. [`protocol-spec.md` §2](./protocol-spec.md#2-frame-format--the-canonical-model) — the
   canonical wire frame format. Read this before any other protocol text, including the
   upstream repository's, because §2.7 there retires a published field model that is one
   byte out of alignment.
3. [`device-validation.md`](./device-validation.md) — the raw bytes. Read it second so that
   everything after it is read against evidence rather than against prose.
4. The rest of `protocol-spec.md` — command catalogue, the 92-byte image, routing, the name
   handshake, knob dictionaries.
5. Whichever of [`capture-format-spec.md`](./capture-format-spec.md),
   [`official-docs.md`](./official-docs.md) and
   [`protocol-algorithms.md`](./protocol-algorithms.md) your task needs.

If you are here to write code, `tools/blackboxctl/` implements the supported read and write
paths. Its [`STATUS.md`](../../tools/blackboxctl/STATUS.md) records what has and has not been
exercised on hardware after this documentation snapshot.

---

## The five documents

| Document | What it is for | Read it when |
| :--- | :--- | :--- |
| [`protocol-spec.md`](./protocol-spec.md) (~76 KB) | The consolidated protocol specification, and the **canonical** definition of the wire frame format (§2), the 92-byte preset image (§4), routing (§5), the name handshake (§6) and the knob dictionaries (§7). Ends with an inconsistency register (§10). | You are building or debugging anything that talks to the pedal, or you need to know what a parameter byte means. |
| [`device-validation.md`](./device-validation.md) (~44 KB) | The live read-only session against the real pedal: seven distinct requests, seven unique replies, full hex, decoded results, and nine numbered corrections to the published documentation. Holds the only data in this directory that cannot be recaptured without the hardware. | You need evidence rather than an account, or two documents disagree and you need a tiebreaker. |
| [`protocol-algorithms.md`](./protocol-algorithms.md) (~37 KB) | Where each part of the protocol was found in prior-art source code: the Base-128 codec with executable test vectors, the opcode table, every command literal, the model and knob tables, and a catalogue of what the published documentation gets wrong. | You are implementing the codec, need a test vector, or want the provenance of a claim. |
| [`capture-format-spec.md`](./capture-format-spec.md) (~42 KB) | The `.am2`/`.am2Data`/`.am3Data` capture container, the neural topology, bundled factory-content records, observed AMP/CAB upload staging, and validation rules for capture and `.wav` files. The final persistent user-slot payload is explicitly not claimed. Derived from a 1686-record corpus plus static disassembly. | You are inspecting, validating or renaming capture files, or deciding whether an IR will survive import. |
| [`official-docs.md`](./official-docs.md) (~34 KB) | What the vendor publishes: the official MIDI implementation chart (which exists only inside a firmware release note), the factory P01–P40 amp/cab table, the official 20 amp and 20 cab name lists, hard limits from the manuals, and the firmware version history. | You want a safe standard-MIDI control path instead of the proprietary one, or you need a vendor figure to check something against. |

Supporting material in this directory:

| Path | What |
| :--- | :--- |
| [`logs/`](./logs/) | The seven raw device transcripts from the 2026-08-28 session, preserved verbatim. `log_all.txt` is the full end-to-end run; unsolicited `20 04` frames appear there (six) and also in `log_flash.txt` (five) and `log_generic.txt` (two). |
| [`reference/`](./reference/) | Preserved predecessor artefacts, not maintained code: `midi_transport.py` (the transport used for the 2026-08-28 read-only session), `validate.py` (its driver), `base128_ref.py` (an independently written codec used as the cross-check) and `amx.py` (the capture parser behind `capture-format-spec.md`). All four lived in a temporary directory that does not survive; see [`reference/README.md`](./reference/README.md). |
| [`contradiction-register.md`](./contradiction-register.md) | The pre-consolidation audit that drove the corrections to these five documents. Its dispositions close at the 2026-08-28 snapshot and are preserved as audit history; later write evidence belongs to the CLI status document. |

---

## Consolidated confidence summary

This is the single place the **2026-08-28 snapshot labels** are collected. Each row names
the document that carries the detail. Nothing here is a summary of intent — a row is
CONFIRMED on hardware only if a byte from this pedal established it by that date. Later
write evidence is intentionally summarized in `tools/blackboxctl/STATUS.md`, not folded
back into this historical table.

### A. CONFIRMED on this pedal — 2026-08-28, read-only

| Claim | Evidence |
| :--- | :--- |
| The USB transport works end to end: Base-128 packed proprietary frames inside `F0 … F7` SysEx, over a class-compliant MIDI Streaming interface that CoreMIDI enumerates as manufacturer "Jieli Technology", product "USB Composite Device". | All seven commands were understood and answered. `device-validation.md` STEP 1b–STEP 6. |
| The Base-128 codec (LSB-first continuous 8→7 packing). | Every command re-encodes bit-exactly to the SysEx logged beside it; every reply decodes to a checksum-valid, semantically correct frame. Two independently written implementations agree bit-for-bit. `device-validation.md` STEP 1 and the codec cross-check. |
| The frame grammar: magic `00 59`, then opcode, then a 24-bit LE payload length, then the payload, then a checksum — total = 7 + length. | `protocol-spec.md` §2.1, re-derived from 25 frames. |
| For opcodes `0x22`/`0x23` the payload is `(space, address, size, data)`, which is where the fixed 14-byte header comes from. | `protocol-spec.md` §2.2; measured on all 14 observed frames, `device-validation.md` STEP 7. |
| Byte 3 is the low byte of the payload length, **not** a command type. | The device returned `0x64`, `0x0C` and `20 01` there, none of which was ever sent. `device-validation.md` STEP 7, correction 5. |
| The checksum is the complement of the payload sum. Start offset 4 is **refuted**. | The two 295-byte name replies carry `byte[4] = 0x01` and fail at offset 4. `protocol-spec.md` §2.3, `device-validation.md` correction 2. |
| Five read address bases: flash presets at `index * 92`, live RAM at `0x10000000`, active-preset id at `0x20000000`, CAB names at `0x80000000`, AMP names at `0x90000000`. | Each requested and answered, with the space, address and size echoed back. `device-validation.md` STEP 7. |
| The 92-byte preset memory map, the 16-bit LE knob encoding, the 0–100 scale, the block on/off order, the model-byte dictionaries, and model byte → name-list index. | P41 matched all seven values known from the GUI. P01 and P03 matched every field recorded in `presets/hana.md` except the two CAB Low Cut fields, which match only after `protocol-spec.md` §4.3's display mapping and only under a truncating convention (raw 24 → 87.2 Hz shown as 87; raw 22 → 81.6 Hz shown as 81) — explained in `presets/hana.md`. `device-validation.md` STEP 6. |
| `Write_Address == Dump_Index` **in the read direction**. | Every field of three presets decodes correctly under identity. `protocol-spec.md` §4.1. |
| All 20 AMP names and 19 of 20 CAB names, and the factory ordering that had been inferred from `descriptions.js` insertion order. | Read out of flash character-for-character. CAB slot 1 returns `1ML_BEST_IR`, the name this project wrote, so its factory name `1AC-SeVin` comes from the pre-write GUI record and the file in `cabFile`, not from flash. `device-validation.md` STEP 4–5. |
| The name table is 20 records of fixed 14-byte stride, so slot *N* is directly indexable at `body[(N-1)*14]`; capacity is 13 characters including the numeric prefix, 12 for slots 10–20. | Nineteen consecutive deltas of 14 on both blocks. `device-validation.md` STEP 5. |
| Over USB the whole 20-name dictionary arrives as **one** 340-byte SysEx. The BLE MTU fragmentation the upstream documentation prescribes an accumulator for does not occur here. | `device-validation.md` STEP 4, correction 3. |
| A name reply's trailing checksum byte can be printable ASCII and will produce a phantom 21st name if you split on nulls naively. | Observed `0x36` = `"6"` on the AMP block. `device-validation.md` correction 4. |
| The device emits unsolicited `20 04` preset-sync frames. Replies must be demultiplexed by their `address` field, never by arrival order. | Six arrived unrequested in the end-to-end run — one during the CAB-name read, five during the flash-index-2 read — and more in the per-step runs (five in `log_flash.txt`, two in `log_generic.txt`). `device-validation.md` correction 6, `logs/`. |
| Read Flash Preset returns a 107-byte frame, and it does not change the **active preset**. | Read at indices 0, 2 and 40; the active-preset-id register at `0x20000000` still returned `0x02` afterwards. No audio was monitored and no before/after RAM comparison is recorded, so the stronger claim "does not change the sounding patch" is an inference from that register, not an observation. `device-validation.md` STEP 6, `protocol-spec.md` §3.1. |
| The upstream Base-128 worked example is a documentation defect: its encoded array belongs to a different message. | `device-validation.md` STEP 1, `protocol-algorithms.md` §2. |
| The upstream `Write_Address = Dump_Index + 2` rule and the upstream AMP-names address `0x00011890` are both wrong. | `protocol-spec.md` §4.1 and §2.7.1 item 3. |

### B. CONFIRMED off-device — measured, but not on this pedal

These rest on file measurement, static disassembly or arithmetic. They are solid, and they
are a different kind of solid from section A.

| Claim | Method | Document |
| :--- | :--- | :--- |
| A capture is a 60-byte header plus 1536 `float32`; `.am2` is the same payload headerless; there is no checksum anywhere in the container, so header edits and renames are safe. | 1686-record corpus, exhaustive checksum search | `capture-format-spec.md` §1–§5 |
| The neural topology: 256-tap FIR, 16-unit 3-gate GRU with 832 parameters, second 256-tap FIR, three 64-tap blocks. | `libamx_parser.dylib` disassembly **and** an independent corpus variance map landing on the same boundaries | `capture-format-spec.md` §3 |
| `AM4\0` is a real record magic in current BlackBox factory data — 7868 bytes, 928 GRU parameters — and is a different, larger record than AM2/AM3. | `blackbox_am4_ampCab.bin` | `capture-format-spec.md` §4.2 |
| A `CAB` record inside the bundled factory `*_ampCab.bin` blobs is 4096 bytes holding **1358 samples of 24-bit LE PCM** = 30.8 ms. | Factory `*_ampCab.bin` blobs | `capture-format-spec.md` §7.1 |
| An official MIDI implementation chart exists, published only inside the firmware release note: PC 0–80 for presets, CC 0–5 for the six module toggles. | Vendor download server | `official-docs.md` §1 |
| The factory P01–P40 amp/cab assignment, and the official 20 amp and 20 cab name lists. | `ANNBLACKBOX_en.pdf` | `official-docs.md` §2 |
| AM2 → AM3 → AM4 are firmware generations with dated release notes, not a documentation error. | Vendor release note and training-software changelog | `official-docs.md` §5 |
| The Base-128 codec, every command literal, the opcode table and the model/knob dictionaries, as read out of prior-art source. | Static analysis, reproduced as executable asserts | `protocol-algorithms.md` §1–§7 |

### C. HYPOTHESIS at the 2026-08-28 snapshot boundary

Several write rows below were resolved by the bounded 2026-08-29 probes. They remain here
to show what the read-only session had and had not established; use the CLI status document
for their current disposition. The unexercised generic commit and firmware-related paths
remain outside that later evidence.

| Claim | What would settle it |
| :--- | :--- |
| **Every write command.** Toggle Block, Change Model, Change Knob, Change Routing, Load Preset, Commit, Write Flash Save, Erase Flash. All are documented, none has been transmitted. | A write, with explicit user consent. |
| `Write_Address == Dump_Index` **in the write direction**, i.e. `0x10000000 + dump_index`. | One Change Knob to `0x10000000 + 0x20`, then re-read the RAM dump. `protocol-spec.md` §4.1. |
| The `0xE0000000 + preset_id` load trigger and the `0xF0000000` commit address. | Both are write triggers. Never sent. |
| Which commands ACK, and the ACK's coverage. | All ACK-producing commands are writes. |
| 80 preset slots **as a flash bound on this unit**. Eighty is confirmed as a product specification by three vendor sources; the highest index ever read here is 40. | Read flash index 79, then index 80. Cheap and read-only. |
| What the pedal does with a non-conforming **capture**, and with a stereo or non-24-bit **IR**. | Not observable without state-changing commands. For IRs there is one demonstrated case — a 48 kHz 65536-frame source was accepted into IR slot 1 through the GUI — and the canonical statement of what that does and does not prove is in `presets/library.md`, under "What that does and does not prove". |
| The pedal on the desk runs firmware V19. | See section D — this is contradicted by other records. |
| Corrupt `InitData`-style magic explains the "auditions badly, works once saved" community report. | A copy-and-patch experiment in M-EFCS. `capture-format-spec.md` §6. |
| What the firmware does to ghost knob bytes at model-switch time. | Dump RAM, change model on the front panel, dump again, diff. Non-destructive. |
| Where per-preset names are stored, if they are stored at all. | Probe string blocks near the known name-table bases. Read-only. |

### D. UNRESOLVED — the evidence does not settle it

| Question | Why it is open |
| :--- | :--- |
| **Who owns `byte[5]`** — bits 16–23 of the 24-bit length, or the low byte of a 16-bit space selector. | `byte[5]` is `0x00` in all 25 frames in evidence. Only a payload of 65536+ bytes or a space selector above `0x00FF` could decide it, and neither exists. Harmless: both readings give identical bytes everywhere. `protocol-spec.md` §2.6. |
| **Checksum start offset 5 vs 6.** | Same reason. Offset 6, the payload sum, is canonical because it is what the grammar and the reference source specify. `protocol-spec.md` §2.3. |
| **ACK semantics.** `cuvave`'s parser reads the payload byte as `ACK(val[0] > 0)`, so the observed `0x00` means *failure*; `bbedit` treats the identical packet as a successful save. One is wrong. | Not resolvable from source, and not resolvable read-only. `protocol-spec.md` §3.3, `protocol-algorithms.md` §5. |
| **The firmware version of this pedal.** `official-docs.md` §5 infers V19 from a firmware filename on disk and concludes the device cannot load AM4; four preset documents independently record the M-EFCS connection label as `BLACKBOX v20`. These may not be comparable — the label may be a product name rather than a firmware version. | The read-only `0x11` query (`00 59 11 00 00 00 FF`) or the device's own settings screen. Note that `blackboxctl`'s read-only gate currently refuses `0x11`. |
| **The IR length budget: 1024, 1358 or 2048.** They measure three different things — see below. | Nothing; the three figures are all correct about their own subject. What was unresolved was which one a validator should quote. |
| **Whether the unsolicited `20 04` frames are pedal-initiated** or a side effect of M-EFCS polling concurrently. | Repeat the read session with M-EFCS closed. |
| **The corporate identity behind the M-VAVE and CUVAVE marks.** Two forms appear in the vendor material: "Zhuhai Shengke Intelligent Technology Co., Ltd." and "Zhuhai Rich Technology". Neither was verified against a registry. | A corporate registry lookup. |

### The three IR figures, reconciled

This came up as a three-way contradiction. The later transfer capture added a fourth
distinction: a factory-blob record and a user-CAB staging record are not the same object.

* **1024 samples / 23.2 ms** is the *vendor specification line*, from the Korean manual and
  the product copy (`official-docs.md` §3). It is intent, not contract — the vendor's own
  factory content does not meet it.
* **1358 samples / 30.8 ms** is what one 4096-byte `CAB` record in the bundled factory
  `*_ampCab.bin` files holds (`capture-format-spec.md` §7.1). That is confirmed for those
  factory blobs, not by reading a user CAB slot back from the pedal.
* **2048 samples / 46.4 ms** is what M-EFCS 3.5.2615 staged for a user CAB upload: a
  20-byte header plus 6144 sample bytes, captured byte-for-byte on 2026-08-29. The firmware
  exposes no known waveform read-back, so the final persistent representation is not proven.
* **2048 source frames** is also, independently, the length of most factory `.wav` inputs
  in the Mac-side M-EFCS library (`presets/library.md`). Sixteen of twenty have that length;
  the coincidence does not make those source files a flash-layout measurement.

---

## Hard rules that apply to everything here

1. **These derivation documents do not authorize a device write.** Use only the named,
   capability-gated `blackboxctl` commands, and consult its current `STATUS.md` and recovery
   runbook first. Never run a preserved reference script against the pedal.
2. **Never delete a raw byte log.** The hex in `device-validation.md` and in `logs/` cannot
   be recaptured without the hardware.
3. Treat the M-EFCS sandbox library at
   `~/Library/Containers/com.digAmp.dgAmp/Data/Documents/M-EFCS` as read-only unless the
   task explicitly requests a library install through the guarded CLI path.
4. Where a statement in any document conflicts with a *measurement* in
   `device-validation.md`, the measurement wins. Where two documents infer differently and
   no measurement decides, say so and label it unresolved rather than picking one.

---

## Provenance and licence

The protocol documentation these five files build on is by **Joel Victor**,
<https://github.com/jvsobrinho/mvave-blackbox-ble>, licensed **CC BY-SA 4.0**. Because
CC BY-SA is a share-alike licence, every document in this directory that adapts it is
itself licensed **CC BY-SA 4.0**, with the attribution *based on protocol research by Joel
Victor, https://github.com/jvsobrinho/mvave-blackbox-ble*. **That includes this index and
`contradiction-register.md`: both are licensed CC BY-SA 4.0 under the same attribution.**
Each document carries its own full source table; `docs/sources.md` is the repository-wide
inventory.

Reference logic also derives from `mvave-blackbox-edit` (MIT, same author),
`pferreir/cuvave-midi` (GPL-3.0), `walterwanderley/am2manager` (Apache-2.0), and empirical
dumps by `cbix` and `michaelforney` whose licence terms are not recorded. Code written from
these specifications is derived from GPL-3.0 reference logic; `tools/blackboxctl/` is
GPL-3.0-or-later accordingly and carries its own `LICENSE` and `NOTICE`.

Vendor manuals, release notes and preset tables quoted in `official-docs.md` are © the
vendor and are quoted for interoperability documentation of hardware the user owns. This is
independent interoperability research, not endorsed by or affiliated with M-Vave.
