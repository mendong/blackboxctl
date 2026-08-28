# Official vendor documentation: M-Vave ANN BLACKBOX

Probe date: 2026-08-28. Every claim below is labelled **CONFIRMED** (observed on this
machine, with the method stated) or **HYPOTHESIS** (with evidence and the test that
settles it).

**Headline result: an official MIDI implementation chart exists.** It is not in any user
manual. M-Vave published it inside the plain-text firmware release note
`BlackBox.txt` on their own download server, under the entry `BLACKBOX_2024_07_08`.
It documents USB MIDI *and* BLE-MIDI, PC for presets, and CC 0–5 for the six module
toggles. Full transcription in section 1.

---

## 0. Source inventory

All files fetched to
`/private/tmp/claude-501/-Users-mendong-Documents-black-box--claude-worktrees-blackbox-presets-ir-setup-d4cb38/ab32803c-e35f-4920-88d6-4f38bcbad797/scratchpad/manuals/`

| File | Origin | What it is |
|---|---|---|
| `BlackBox_releaseNote.txt` (+ `_utf8.txt`) | `https://yms-file-store.oss-cn-hongkong.aliyuncs.com/software/releaseNote/firmware/BlackBox.txt` | **Official per-firmware release notes. Contains the MIDI chart.** GBK-encoded, CRLF. |
| `ANNBLACKBOX_en.pdf` | `https://community.m-vave.com/bbs/api/software?file=ANNBLACKBOX_en.pdf` | Official AMP list (20), CAB list (20), and factory preset P01–P40 AMP/CAB table |
| `ANNBLACKBOX_cn.pdf` | same, `_cn` | Chinese edition of the above |
| `ANN_whitepaper.pdf` | `https://yms-file-store.oss-cn-hongkong.aliyuncs.com/manual/white-paper/ANN.pdf` | "ANN White Paper" — what ANN (Audio Neural Network) is |
| `MK300_MIDI_Control_Mapping_Table.docx` | `https://yms-file-store.oss-cn-hongkong.aliyuncs.com/software/releaseNote/firmware/MK300%20MIDI%20Control%20Mapping%20Table.docx` | Sibling product's full MIDI CC chart — establishes family conventions |
| `chocolate_plus_software_instructions.pdf` | `https://manualf.oss-cn-hongkong.aliyuncs.com/manual/CUBE-TURNER/Chocolate%20Plus-Software%20instructions.pdf` | Chocolate Plus MIDI sender modes (needed to decode the BlackBox chart's mode names) |
| `mvave_download.html` | `https://www.m-vave.com/download` | Official download index; source of every URL above |
| `BlackBox_Manual_kor_web.pdf` | pre-existing | **Not an M-Vave manual.** Gopherwood "SquareMoon" Korean manual — see section 6 |
| `BlackBox-V19-Firmware-2025-10-17.fwsc` | pre-existing | Firmware. SHA-256 `6ce0c976bc1a563388d5d8acade9912044543823a0825891b1716aec419db993` |

Deleted as worthless: an SEO-spam PDF from a webflow CDN that keyword-stuffed the manual.

---

## 1. THE MIDI IMPLEMENTATION CHART (official)

**CONFIRMED** — transcribed verbatim from `BlackBox_releaseNote.txt`, entry
`----------BLACKBOX_2024_07_08------------`, decoded with `iconv -f GBK`:

```
Added USB MIDI and BLE-MIDI functions (official recommendation: Chocolate and Chocolate Plus can be used)
The specific content is as follows:
 PC code corresponds to the control of 80 presets
 CC code can independently control each module (such as reverberation module, delay module, etc.)
 Manufacaturer can control some internal functions
PC CODE:PC00-PC80(chocolate Program B/chocolate plus Program A )

CC CODE:CC0 0-CC5 0 (chocolate Program C/chocolate plus Program B)
        CC0 0 FX
        CC1 0 AMP
        CC2 0 MOD
        CC3 0 DLY
        CC4 0 REV
        CC5 0 CAB
Manufacaturer
        A  HOME
        B  Confirm button pressed by PARA encoder
        C  Left footswtich
        D  Right footswtich
```

(`Manufacaturer` and `footswtich` are the vendor's own typos, preserved.)

### 1.1 Structured form

| Message | Number | Target | Notes |
|---|---|---|---|
| Program Change | `PC00`–`PC80` | Preset 1–80 | Vendor writes 81 values for 80 presets — numbering base unresolved, see 1.3 |
| Control Change | `CC0` | **FX** module toggle | |
| Control Change | `CC1` | **AMP** module toggle | |
| Control Change | `CC2` | **MOD** module toggle | |
| Control Change | `CC3` | **DLY** module toggle | |
| Control Change | `CC4` | **REV** module toggle | |
| Control Change | `CC5` | **CAB** module toggle | |
| Manufacturer mode | switch A | HOME button | Chocolate "Manufacturer Device Control Mode" |
| Manufacturer mode | switch B | PARA encoder confirm press | |
| Manufacturer mode | switch C | Left footswitch | |
| Manufacturer mode | switch D | Right footswitch | |

The `CC0 0 … CC5 0` notation is `CC<number> <value>`, matching the Chocolate Plus
software's own `CC(0,0)`–`CC(127,0)` notation for its "Program Change B (CC Code)" mode
(**CONFIRMED** from `chocolate_plus_software_instructions.pdf` page 2). So the chart
means CC number 0 through 5, sent with value 0.

### 1.2 What is NOT in the official chart

**CONFIRMED absent** — there is no documented CC for:
- tap tempo
- master / preset volume
- tuner
- any per-knob parameter
- bank select (CC0 is used as the FX toggle, so the device does not follow the MIDI
  bank-select convention)

And no MIDI channel is stated anywhere.

### 1.3 Open questions on the chart — HYPOTHESES

**H1: PC numbering is 0-based over 80 presets, i.e. PC 0 → P01 … PC 79 → P80, and
"PC00-PC80" is vendor sloppiness.** *Confidence: medium.*
Evidence: 80 presets is stated everywhere; `PC00-PC80` inclusive is 81 values, which
cannot map 1:1. The Chocolate Plus doc says its PC mode spans "PC 0 to PC 127".
*Test:* send Program Change 0 and observe the front-panel preset readout, then send
PC 79 and PC 80. Requires a device write and is out of scope for a read-only probe —
but PC is the *safe* control path (RAM-level preset load, no flash write), so this is
the right first experiment for the agent authorised to send.

**H2: The device listens on MIDI channel 1, or omni.** *Confidence: low-medium.*
Evidence: the sibling MK300 chart states "B0 is the Control Change header for MIDI
Channel 1" (**CONFIRMED** from `MK300_MIDI_Control_Mapping_Table.docx`). Chocolate
Plus modes 1 and 2 — the two modes the BlackBox chart names — do *not* offer a channel
selector, while modes 3+ do; that is consistent with the BlackBox expecting a fixed
channel. *Test:* send the same PC on channel 1 and on channel 2 and compare.

**H3: CC value semantics are the family convention: send ≥64 for ON, <64 for OFF
(127 = ON, 0 = OFF).** *Confidence: medium.*
Evidence: the MK300 chart states this convention explicitly for the same vendor and
same firmware family. But the BlackBox chart itself writes value `0` for every entry,
and Chocolate Plus's mode 3 sends a toggle *pair* `CC(1,1)` and `CC(1,0)`. So the
BlackBox may treat CC arrival as a toggle regardless of value.
*Test:* send CC1 value 0 twice and see whether AMP toggles twice (toggle semantics) or
stays off (absolute semantics).

**H4: The "Manufacturer" mode is Chocolate's Mode 6 "Manufacturer Device Control Mode"
and rides proprietary SysEx, not standard CC.** *Confidence: medium-high.*
Evidence: the Chocolate Plus doc describes Mode 6 as "Internal mode for controlling
M-VAVE brand products such as TANK-G, LOOPER PRO, and LOST TEMPO" with four footswitches
A–D — exactly the A/B/C/D lettering the BlackBox chart uses. Note the Chocolate Plus
doc does **not** list BLACKBOX among Mode 6's supported products, while the BlackBox
release note says it works; treat that as a doc lag, not a contradiction.
Also **CONFIRMED** from that doc: Chocolate's SysEx payloads are capped at 200 bytes
(the Chinese text says `SYSEX码（限定200字节）`).

### 1.4 Why this matters for the CLI

**Recommendation:** prefer Program Change for preset switching. It is a vendor-documented,
RAM-level operation on a standard transport, and the device is already visible to CoreMIDI
bidirectionally on USB. It is categorically safer than the proprietary flash-write path
(command type `0x64`), which can destroy user presets. CC 0–5 give the six module toggles
for free on the same safe path.

The proprietary protocol remains necessary for everything the standard layer does not
cover: reading state, reading names, changing models, changing knob values, changing
routing, and saving.

**Also CONFIRMED, and important:** the release note says "USB MIDI **and** BLE-MIDI".
The MIDI layer is available over the USB connection this project is already using.
This does not contradict `priorart/ble/docs/ble_protocol.md`, which says the *proprietary
editor protocol* is not Universal MIDI over BLE — both stacks coexist.

---

## 2. Preset count and factory preset table

**CONFIRMED — 80 presets.** Stated in three independent official sources:
- English user manual (via manuals.plus): "Blackbox includes 80 Presets, with the first
  40 (P01~P40) containing default factory effects."
- Official M-Vave TikTok product copy: "Built-in 80 presets, customizable tones can be
  overwritten and stored".
- Korean SquareMoon manual p.6: "80개의 프리셋을 포함합니다" and p.13 spec "프리셋 수량: 40+40".

The "40+40" spec line plus "can reset these 40 or all 80 Presets separately" means:
P01–P40 ship with factory content and have a separate factory-restore; P41–P80 are empty
user slots. This cross-checks the 80 figure the protocol work assumes.

**CONFIRMED** — the official `ANNBLACKBOX_en.pdf` gives the exact factory AMP/CAB
assignment for P01–P40. Extracted with pdfminer using text coordinates (not OCR), so
column alignment is exact. Blank CAB cells are blank in the source.

| P | AMP | CAB | | P | AMP | CAB |
|---|---|---|---|---|---|---|
| P01 | 1J900_CL | 1AC-SeVin | | P21 | 2FD_CL | 2JVM_1960_57 |
| P02 | 5RAT_OD | 2JVM_1960_57 | | P22 | 9J900_DS | 2JVM_1960_57 |
| P03 | 6M-VAVE_OD | 2JVM_1960_57 | | P23 | 12FRIMAN | 2JVM_1960_57 |
| P04 | 9J900_DS | 2JVM_1960_57 | | P24 | 15JVM | 2JVM_1960_57 |
| P05 | 2FD_CL | *(blank)* | | P25 | 4BLUE_OD | 1AC-SeVin |
| P06 | 4BLUE_OD | 5HIFI_OK | | P26 | 2FD_CL | 5HIFI_OK |
| P07 | 6M-VAVE_OD | 5HIFI_OK | | P27 | 5RAT_OD | 3V30_MD421 |
| P08 | 13XC_DS | 2JVM_1960_57 | | P28 | 11EVH_5150 | 13HIW412SWF |
| P09 | 3JC120_CL | *(blank)* | | P29 | 4BLUE_OD | 5HIFI_OK |
| P10 | 4BLUE_OD | 15JC120_BOX | | P30 | 4BLUE_OD | 9MeOSick-III |
| P11 | 8DARKS_DS | 15JC120_BOX | | P31 | 5RAT_OD | 11FD_TW1980 |
| P12 | 13XC_DS | 15JC120_BOX | | P32 | 6M-VAVE_OD | 15JC120_BOX |
| P13 | 5RAT_OD | 7VOX_AC30 | | P33 | 14ROOM40 | 12MESA_412 |
| P14 | 5RAT_OD | 7VOX_AC30 | | P34 | 11EVH_5150 | 10SoldSC412 |
| P15 | 5RAT_OD | 8FRMAN112 | | P35 | 15JVM | 4G12-EVH_CT |
| P16 | 10JHS_DS | 8FRMAN112 | | P36 | 13XC_DS | 12MESA_412 |
| P17 | 1J900_CL | 12MESA_412 | | P37 | 16AgDb750_BS | 16Agula410 |
| P18 | 9J900_DS | 12MESA_412 | | P38 | 17ApSVT_BS | 17AgSVT410 |
| P19 | 12FRIMAN | 6WANGS212_ECM | | P39 | 19DgXu_BS | *(blank)* |
| P20 | 15JVM | 4G12-EVH_CT | | P40 | 18PjBuddy_BS | *(blank)* |

**This table is a free, no-write validation oracle** for the Read Flash Preset command
(`00 59 23 08 00 00 04 [ADDR_4B_LE] 5C 00 00 [CS]`, address = index × 92): read slot 0
and check that its AMP model id decodes to `1J900_CL` and its CAB id to `1AC-SeVin`.
If the decoded model ids for P01–P40 match this table, the 92-byte memory map is
validated without ever writing.

### 2.1 Official AMP names (20) — matches the AMP name string block

**CONFIRMED** from `ANNBLACKBOX_en.pdf` p.1. Names are stored with a 1-based index
prefix baked into the name itself, exactly as `memory_map.md` describes for the
string-block read at base `90 18 01 00` LE.

`1J900_CL`, `2FD_CL`, `3JC120_CL`, `4BLUE_OD`, `5RAT_OD`, `6M-VAVE_OD`, `7SUPA_OD`,
`8DARKS_DS`, `9J900_DS`, `10JHS_DS`, `11EVH_5150`, `12FRIMAN`, `13XC_DS`, `14ROOM40`,
`15JVM`, `16AgDb750_BS`, `17ApSVT_BS`, `18PjBuddy_BS`, `19DgXu_BS`, `20MarkLm_BS`

Types: 1–3 Clean, 4–7 Overdrive, 8–15 Distortion, 16–20 Bass.
This **CONFIRMS** the manual's "1–15 guitar preamp, 16–20 bass preamp" split.

### 2.2 Official CAB names (20) — matches the CAB name string block

**CONFIRMED** from `ANNBLACKBOX_en.pdf` p.2. CAB name base address per `memory_map.md`
is `80 18 01 00` LE.

`1AC-SeVin` (1x12), `2JVM_1960_57` (4x12), `3V30_MD421` (4x12), `4G12-EVH_CT` (4x12),
`5HIFI_OK` (1x12), `6WANGS212_ECM` (2x12), `7VOX_AC30` (2x12), `8FRMAN112` (1x12),
`9MeOSick-III` (4x12), `10SoldSC412` (4x12), `11FD_TW1980` (2x12), `12MESA_412` (4x12),
`13HIW412SWF` (4x12), `14Recto_112` (1x12), `15JC120_BOX` (2x12), `16Agula410` (4x10),
`17AgSVT410` (4x10), `18DgDG212N` (2x12), `19MbSway210` (2x10), `20Tace412` (4x12)

Note the manual claims 1–15 guitar CAB, 16–20 bass CAB; the official list's bass cabs
(Aguilar, Ampeg SVT, Darkglass, Mesa Subway, Trace Elliot) are indeed 16–20.

---

## 3. IR .wav limits — this settles the truncation question

**CONFIRMED. The BlackBox accepts 44.1 kHz / 24-bit / MONO WAV, 1024 sampling points.**

Three independent official statements:

1. Korean SquareMoon manual p.13, spec list, verbatim:
   `IR 처리: 44.1K/24Bit 모노 WAV 파일, 1024 샘플링 포인트`
   ("IR processing: 44.1K/24Bit mono WAV file, 1024 sampling points")
2. Official M-VAVE TikTok product description, verbatim:
   "Cabinet simulation (CAB): 20 types, support third-party IR loading (44.1K/24Bit,
   mono WAV file, 1024 sampling points)."
3. Web search over m-vave sources returns the same 1024-sample figure for BlackBox, and
   notes the sibling **IR BOX** supports "1024/2048 sampling point IR files" — i.e. 1024
   is a real per-product limit, not boilerplate.

**Consequence: 1024 taps at 44.1 kHz = 23.2 ms of impulse response.** Anything longer
is truncated. A typical 500 ms commercial IR (22050 samples) keeps only its first 4.6%.
This is the answer to "are long IRs truncated": yes, hard, at 1024 samples.

Related **CONFIRMED** IR CAB module parameters, Korean manual p.12:
- Level
- Low Cut, adjustable **20–300 Hz**
- High Cut, adjustable **5000–18000 Hz**

**HYPOTHESIS (low confidence):** the on-device conversion resamples or force-downmixes
non-conforming files rather than rejecting them. No official source says what happens to
a 48 kHz or stereo file. *Test:* feed M-EFCS a 48 kHz stereo IR and compare the bytes it
uploads against a known 44.1 kHz mono one. Does not require touching the pedal.

---

## 4. Bluetooth and USB behaviour

### Bluetooth — CONFIRMED

From the English manual (manuals.plus) and Korean manual p.6 / p.7, agreeing:
- **Long-press HOME** turns BT on/off. There is no pairing button and no PIN.
- HOME button LED: **off** = BT off; **flashing** = BT on but not connected;
  **steady on** = BT connected.
- Screen BT icon: off = not enabled; **white** = started, not connected;
  **blue** = connected.
- BT carries **music playback** ("BT accompaniment: supported") *and* the editor app
  connection, and per section 1, **BLE-MIDI**.

The device advertises as `BlackBox_BLE` per `priorart/ble/docs/ble_protocol.md`; no
official source names the advertised string, so that stays third-party.

### USB — CONFIRMED

Official USB jack description, verbatim from the English manual:
> "USB jack: Use to charge the battery/The BLACKBOX can be a sound card of computer/
> Computer software can be connected for interactive data transmission."

Spec line: **USB Audio (OTG) 44.1K/24-bit, Loopback ON/OFF switchable**
(the 2024-07-31 release note calls it "Add a Computer Loopback switch";
the 2024-12-05 note says Master Knob now controls guitar volume only, while
"Bluetooth and USB volumes are managed by the playback device").

**There is no USB mass-storage / removable-disk mode.** No official source mentions one.
File transfer is exclusively "interactive data transmission" through M-EFCS over the
MIDI/SysEx path, and firmware upgrade is a separate HID-based path (see section 5).

**HYPOTHESIS (medium):** the vendor's USB file transfer is exactly the SysEx-wrapped
proprietary protocol the prior art documents, i.e. there is no second, hidden bulk
channel. Evidence: the firmware's internal file table names `usb_hid_ota.bin` — a HID
OTA path used only for firmware — and no mass-storage descriptor was seen in ioreg
(only Audio subclasses 1/2 and MIDIStreaming subclass 3). *Test:* full `ioreg`/USB
descriptor dump; if no bInterfaceClass 8 (Mass Storage) interface exists, confirmed.

---

## 5. Capture file extensions — the .am2 vs .am4 inconsistency, resolved

`memory_map.md` says the pedal stores amp captures as `.am4`; the local library holds
`.am2`, `.am2Data`, `.am3Data`. **Both are right. They are successive generations, and
which one applies depends on firmware version.**

**CONFIRMED** from `BlackBox_releaseNote.txt`:

| Firmware | Date | ANN model format change |
|---|---|---|
| `BLACKBOX_2024_12_28` | 2024-12-28 | "Supports **AM3** Psychoacoustic AI Model" |
| `BLACKBOX_2026 01 31 V20` | 2026-01-31 | "Supports **AM4** format files for AMP modules" (CN: `支持AM4格式的文件用于AMP模块`) |

**CONFIRMED** from the official download page (`mvave_download.html`), SINCO ANN
training-software changelog, verbatim:
> `1.1.1 Fix bug where file paths contained spaces · 1.1.0 Add LMT verification ·
> 1.0.9 Add NAM→AM4DATA conversion · 1.0.8 Add AM4DATA · 1.0.7 Add NAM→AM3DATA
> conversion · 1.0.6 Fix lossrec/loudness file name error, auto delay removal for IR
> training`
> `v2.0.0 New: Exclude system dependencies · Upgrade libtorch to CU13 (Geforce 50
> series) · **AM2 model training removed**`

So the generation order is **AM2 → AM3 → AM4**, AM2 is deprecated and no longer
trainable, and NAM (Neural Amp Modeler) files can be converted into AM3DATA/AM4DATA.

### The operationally important consequence

**The pedal in this project runs V19 (2025-10-17). AM4 support arrives only in V20
(2026-01-31). So this device supports AM2 and AM3 but NOT AM4.**
This is **CONFIRMED** for the documentation; it is a **HYPOTHESIS (high confidence)**
that the device on the desk is actually running V19 rather than V20 — that was inferred
from the filename of the firmware file sitting next to the manual. *Test:* read the
version over the proprietary protocol, or look at the device's settings screen.

Also **CONFIRMED**: the vendor's own term for these captures is **ANN = "Audio Neural
Network"**, from `ANN_whitepaper.pdf` p.1: "ANN(Audio Neural Network) is the latest
modeling technology from Sinco's research team." The whitepaper explains ANN as a hybrid
of white-box circuit modelling, black-box Wiener-Hammerstein modelling, and a simplified
WaveNet-style network, plus two in-house algorithms named **WANT** (Waveform Automatic
Nonlinear Tracking) and **HHAG** (High Harmonic Automatic Generation). Vendor address on
the whitepaper: Zhuhai Rich Technology, Jinwan District, Zhuhai. This corroborates the
`_ANN_Unit_proc` symbol found in `libamx_parser.dylib`.

The whitepaper says nothing about the on-disk file format, so the 6204-byte AM2/AM3
container layout remains unspecified by the vendor.

---

## 6. The Korean manual is a rebrand — read it with that caveat

**CONFIRMED.** `BlackBox_Manual_kor_web.pdf` is 16 pages, no extractable text layer
(pypdf returns 0 characters on every page), read as page images. It is branded
**GOPHERWOOD "SquareMoon"**, published by 주식회사 고퍼우드 (Gopherwood Co., Ltd.),
Yangju, Gyeonggi-do, `sales@gopherwood.co.kr`, `gopherwood.co.kr`. The word "BlackBox"
does not appear anywhere in it. The app it tells you to pair with is called "SquareMoon".

**It is nevertheless the same hardware.** Its spec page gives
`113(L) x 109(W) x 41(H) mm`, `410 g`, `2000 mAh` — identical to M-Vave's own official
figures for the ANN BLACKBOX (`113 (L) x 109 (W) x 41 (H) mm`, `410 grams`, per the
official M-VAVE TikTok product post). Module set, 20 amps, 20 IRs, 80 presets, 6+1
simultaneous slots, and the 44.1K/24-bit 1024-point IR line all match exactly.

**Beware of one bad third-party source.** The manuals.plus scrape reports the BlackBox as
`310(L)X65(W)X40(H)mm, 613g, 3000mah` with an XLR output. That contradicts the vendor's
own figures and is almost certainly a different M-Vave pedal's spec table spliced in.
Treat the manuals.plus *body text* as usable and its *spec table* as unreliable.

**CONFIRMED: the Korean manual contains no MIDI section whatsoever.** Zero occurrences
of MIDI, PC, or CC across all 16 pages. Neither does the English M-Vave user manual — a
targeted fetch of the manuals.plus transcription returned the section list
(Preface, Effectors module, Power Supply, Effects Chain, Connection, Storage, FAQ,
chain diagram, Rear panel, Front panel, FX/AMP/Modulation/Delay/Reverb/IR CAB modules,
Technical parameters, Download Software, FCC) and reported the words MIDI / Program
Change / PC code / Control Change absent. **The MIDI chart lives only in the release
note.** This is why the `mvave-blackbox-ble` README's claim that "the manual documents
PC for presets, CC for basic toggles" is right in substance and wrong about the location.

**CONFIRMED, corroborating evidence that no MIDI doc is published per-manual:** on
`https://www.m-vave.com/download`, only **FM-1** and **MK300** carry "MIDI CONTROL EN /
MIDI CONTROL CN" document links. ANNBLACKBOX carries only "Preset EN / Preset CN".

### Other hard limits from the Korean manual — CONFIRMED

| Item | Value |
|---|---|
| Sample rate | 44.1 kHz / 24-bit |
| Dynamic range | 105 dB |
| Total effects | 60+ |
| Simultaneous slots | 6+1, user-orderable |
| Modules | FX → AMP → MOD → DLY → REV → CAB (order user-assignable) |
| FX types | Noise Gate, Boost, Compressor (3) |
| MOD types | Chorus, Phaser, Tremolo, Flanger, Vibrato, Univibe, Auto Filter (7) |
| DLY types | Analog, Ducking, dTape, Dual, Lofi (5) |
| REV types | Room, Hall, Swell, Spring, Shimmer, Cloud (6) |
| Delay time range | 600–60 bpm (Analog / Ducking / dTape / Lofi); **1200–120 bpm** (Dual) |
| Tuner reference A | 430–450 Hz; mode Bypass or Mute |
| Battery | 2000 mAh, ≥10 h; ~5 h to charge from 5V/2A; charge limit ~408 mA |
| Operating current | ~200 mA |
| Power / data | Type-C, 5V ≥ 300 mA |
| I/O | 1/4" mono TS in, 1/4" mono TS out, 1/8" stereo (headphone) |
| Software | Windows, macOS, iOS, Android |

**Doc bug worth knowing about:** Korean manual p.6 says
`P01~P40은 공장 초기 일렉기타 프리셋, P36-P40은 베이스 기타 프리셋`
— "P01–P40 are factory electric-guitar presets, P36–P40 are bass-guitar presets", which
is self-contradictory. The official `ANNBLACKBOX_en.pdf` settles it: **P37–P40 use bass
amps** (16AgDb750_BS, 17ApSVT_BS, 19DgXu_BS, 18PjBuddy_BS); P36 still uses a guitar amp
(13XC_DS). So neither the "P36–P40" nor the "P01–P40" reading is exactly right.

---

## 7. Firmware container: static analysis only

`BlackBox-V19-Firmware-2025-10-17.fwsc`, 692 244 bytes (0xA9014),
SHA-256 `6ce0c976bc1a563388d5d8acade9912044543823a0825891b1716aec419db993`.
**Nothing was flashed, patched, or uploaded. All observations are from `xxd`, `strings`,
and a Python entropy script.**

### 7.1 Identification — CONFIRMED

| Fact | Evidence |
|---|---|
| Not a recognised type to `file(1)` | `file` reports plain `data`; no ELF/PE/archive magic |
| **Trailer magic `JLUFW` at offset 692 228** | exactly 16 bytes from EOF: `4a4c554657` + 11 × `00`. This is JieLi's "JL Upgrade FirmWare" marker. |
| **Target SoC: JieLi AC791N** | plaintext `AC791N_STORY` at offset 0x0428, preceded by `0.01` at 0x0418 |
| Matches the device on this desk | UTF-16LE string `USB Composite Device` at 0xA664C — byte-identical to the CoreMIDI `DisplayName` observed for the connected pedal |
| Declares a USB MIDI interface | UTF-16LE string `Midi` at 0xA6681, alongside the composite-device name — consistent with the `bInterfaceSubClass 3` / `USB-Midi` entry seen in `ioreg` |
| Contains a JieLi bootloader file table | plaintext run at 0xA66xx–0xA67xx: `BTIF`, `UTTX`, `UTBD`, `.bin`, `flash`, `USBDP`, `PM`, `success`, `UPDATE_JUMP`, `POWER_PIN`, `cfg_tool4`, `app_dir_head`, `uboot.`, `isd_config.ini` |
| OTA payload name | `usb_hid_ota.bin` appears twice, at offsets 672 004 and 672 036, each followed by a 4-byte little-endian size/offset pair. Consistent with a HID-based USB OTA, matching M-Vave's `M-UPGRADE` tool. |
| JieLi SDK config keys survive in plaintext | `SDRAM_PLL3_NOUSB_EN` at 0x3E2E, `SDRAM_DQ_DLY_INNER_TRM` at 0x3F84 |
| A BT address-like string | UTF-16LE `6F64096B22E7` at 0xA6631 |

**Verdict: this is a recognisable JieLi (Zhuhai Jieli / 杰理) AC791N `.fwsc` upgrade
container.** That is consistent with the USB vendor id observed on this Mac,
`0x4C4A` = "Jieli Technology".

### 7.2 Is it encrypted? — mostly, but not uniformly

Measured with a Python script over the whole file:

- Global Shannon entropy **7.9928 bits/byte**; all 256 byte values present.
- Per-4 KB blocks: 169 blocks, min 6.699, max 7.954, **mean 7.886**. No low-entropy
  plateau anywhere — even the "plaintext" regions are only locally plaintext.
- Longest printable/NUL runs ≥ 24 bytes: **only 6 in the entire file.** Everything else
  is opaque.
- 16-byte block duplication: 43 265 blocks, 43 123 unique, 142 duplicates. The single
  most repeated block is `ff × 16`, occurring **136 times**.
- Byte-lag autocorrelation over the first 200 KB peaks weakly at lags 64 and 32
  (2.6% / 2.5% vs a 0.49% baseline) — structure, but nothing like a short repeating key.

**HYPOTHESIS (high confidence): the bulk payload is encrypted or compressed per-section,
with header, USB descriptors, the bootloader file table, and 0xFF erase filler left in
the clear.** *Evidence:* 7.99 entropy plus 256/256 byte coverage rules out plaintext
code; but a whole-file stream cipher or XOR would have scrambled the 136 runs of
`ff × 16`, and a whole-file ECB block cipher would have produced far more than 142
duplicate blocks. So the transform is applied selectively.
*Test that settles it:* obtain the V20 `BlackBox.fwsc` from
`https://yms-file-store.oss-cn-hongkong.aliyuncs.com/software/firmware/BlackBox.fwsc`
and diff it against V19. If the two files share long byte-identical stretches at the same
offsets, the transform is position-keyed (a scramble/XOR, breakable); if they differ
essentially everywhere, it is a real cipher or a whole-image compressor.

**HYPOTHESIS (medium): the file is not signed, only obfuscated.** *Evidence:* the trailer
is a 16-byte `JLUFW` marker with no room for a signature, and JieLi's stock upgrade flow
is a CRC-checked container. *Test:* the V19/V20 diff above; a signature block would show
as a fixed-size, fully-changed region at a fixed offset.

### 7.3 Firmware version history relevant to this project — CONFIRMED

From the official release note:

| Version | Date | Highlights |
|---|---|---|
| — | 2024-07-04 | Fixed AMP module; fixed MOD tap speed |
| — | **2024-07-08** | **USB MIDI + BLE-MIDI added. This is where the MIDI chart comes from.** |
| — | 2024-07-31 | Latency optimisation; **Computer Loopback switch added**; charging display fix |
| — | 2024-12-05 | Master Knob now controls guitar volume only; BT/USB volume moves to the host |
| — | 2024-12-28 | AI NATEC noise reduction; **AM3 model support**; 40% performance gain; USB sample-rate jitter fix |
| V17 | 2025-06-06 | M-EFCS can audition AMP/IR/DS together; GATE gains "AI Ms Gate"; button debounce |
| **V19** | **2025-10-17** | **The build in this project.** Boot speed, stability; tone-switch latency and switching-noise fix |
| V20 | 2026-01-31 | **AM4 format support for AMP modules** |

---

## 8. Summary of what this probe changes

1. **The safe control path is real and documented.** Use PC for preset switching and
   CC 0–5 for module toggles, over the USB MIDI endpoint CoreMIDI already exposes.
   Prefer it over the proprietary flash path for anything it can do.
2. **1024 samples is the IR ceiling.** 23.2 ms. Long IRs are truncated. Stop wondering.
3. **.am2 / .am3 / .am4 are generations, not a doc error.** V19 hardware takes AM2 and
   AM3; AM4 needs V20.
4. **The official amp, cab, and P01–P40 tables are a write-free validation oracle** for
   the 92-byte preset memory map and the name string blocks.
5. **The firmware is a JieLi AC791N container**, mostly opaque, with a clean V19↔V20 diff
   available as the next step if anyone needs to go further.
6. **The Korean PDF in this repo is a Gopherwood SquareMoon rebrand manual**, same
   hardware, and it has no MIDI content. Cite it for specs, not for protocol.

---

## Attribution and licensing

- The user manuals, preset lists, release notes, ANN white paper, and MK300 MIDI mapping
  table quoted here are © M-VAVE / Sinco / Cuvave (Zhuhai Rich Technology), retrieved
  from `m-vave.com`, `community.m-vave.com`, and `yms-file-store.oss-cn-hongkong.aliyuncs.com`.
  Quoted for interoperability documentation of the owner's own hardware.
- The Korean manual is © 주식회사 고퍼우드 (Gopherwood Co., Ltd.), `gopherwood.co.kr`.
- Protocol context cross-referenced against
  <https://github.com/jvsobrinho/mvave-blackbox-ble> — documentation CC BY-SA 4.0 by
  Joel Victor, reference code GPL-3.0. Our CLI derives from that work and should ship
  GPL-3.0 with a LICENSE file and this attribution in the README.
