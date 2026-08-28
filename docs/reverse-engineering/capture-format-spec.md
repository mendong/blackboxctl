# M-Vave BlackBox — Neural Amp Capture Container Specification (`.am2` / `.am2Data` / `.am3Data`)

**Status:** Derived specification. Every statement is labelled CONFIRMED or HYPOTHESIS.
**Scope:** The on-disk capture container, the on-device flash record it becomes, the
neural topology inside it, and the `.wav` impulse-response side of the cab slot.
**Audience:** the BlackBox CLI, so it can *inspect, validate and rename* captures safely.

---

## 0. Provenance, attribution and licence

| Source | Author | Licence | Role here |
| :--- | :--- | :--- | :--- |
| [`am2manager`](https://github.com/walterwanderley/am2manager) — `am2.go`, `cmd/am2converter`, `cmd/am2protector` | Walter Wanderley | Apache-2.0 | Origin of the 60-byte-header / 6144-byte-payload split and the `Mix`/`Level`/`GainMax`/`GainMin` field names. |
| [`mvave-blackbox-ble`](https://github.com/jvsobrinho/mvave-blackbox-ble) — `docs/memory_map.md` | Joel Victor | **CC BY-SA 4.0** | Flash layout, amp/cab name blocks, the `.am4` mention corrected below. |
| `/Applications/M-EFCS.app/Contents/Frameworks/libamx_parser.dylib` | M-Vave / Zhuhai Shengke | proprietary | Static disassembly (`objdump`, `nm`) established the neural topology and the exact weight offsets. Inspected read-only; no debugger was attached and no code was copied. |
| `.../App.framework/.../lib/resources/bin/blackbox/*_ampCab.bin` | M-Vave | proprietary | Factory amp/cab blobs; read-only. Used to establish the flash record layout. |

Because this document builds on CC BY-SA 4.0 documentation, **this file is licensed
CC BY-SA 4.0**. Attribution: *based on protocol research by Joel Victor,
https://github.com/jvsobrinho/mvave-blackbox-ble, and on `am2manager` by Walter Wanderley.*
Code written from this specification is derived from GPL-3.0 reference logic elsewhere in
this project and should be licensed GPL-3.0.

M-VAVE and CUVAVE are trademarks of their owner. Two forms of that owner's name appear in
the vendor material used across this project — "Zhuhai Shengke Intelligent Technology Co.,
Ltd." (quoted here and in `protocol-spec.md`) and "Zhuhai Rich Technology" (the address on
the vendor's own ANN white paper, quoted in `official-docs.md` §5). **Neither has been
verified against a corporate registry and they are not obviously the same entity**; treat
both as unconfirmed. This is independent interoperability research on hardware and files the
user owns.

Start at [`README.md`](./README.md) in this directory for the reading order and the
consolidated confidence summary.

### Evidence labels

* **CONFIRMED** — observed on this machine, with the method stated inline.
* **HYPOTHESIS** — best current explanation, with the evidence and the test that settles it.

### Corpus used

| Source | 6144-byte | 6204-byte | other |
| :--- | ---: | ---: | ---: |
| `…/M-EFCS/ampFile` | 4 | 35 | — |
| `…/M-EFCS/dsFile` | 0 | 14 | — |
| `Black_Box_Captures_V16.8` pack (recursive) | 384 | 1249 | 1 zero-byte file |
| **total** | **388** | **1298** | **1** |

Naming note: `Black_Box_Captures_V16.8` is the *extracted directory*. `presets/library.md`
and `docs/sources.md` refer to the same artefact by its archive name,
`ANN_Captures_IRs_V16.8.zip` (44.3 MB). One community pack, two names. Neither its SHA-256
nor a per-file manifest was recorded, and its only host is a mutable Google Drive folder, so
**the install is not currently reproducible** — see `docs/sources.md` §2.1.

1686 parseable records, **741 distinct 1536-float payloads**, 786 distinct whole files.
Reference parser: [`reference/amx.py`](./reference/amx.py), preserved into the repository —
see [`reference/README.md`](./reference/README.md). The read-only corpus copy it was run
against lived at `…/ab32803c-…/scratchpad/fmt2/corpus/` in a session-scoped temporary
directory and **has not been preserved**; it was a copy of the community pack plus the
M-EFCS library, both of which still exist at their own locations.

---

## 1. Executive summary

* A capture is **a 60-byte header plus 1536 little-endian `float32`** (6144 bytes) =
  **6204 bytes**. CONFIRMED.
* `.am2` (6144 bytes) is the **same payload with the header stripped**. CONFIRMED.
* The 1536 floats are **not opaque**: they are a 256-tap FIR, a 16-unit 3-gate GRU with
  832 parameters, a second 256-tap FIR and three 64-tap blocks. CONFIRMED by disassembly
  *and* independently by a corpus variance map that lands on exactly the same boundaries.
* **There is no checksum anywhere in the container.** CONFIRMED by exhaustive search.
  Header fields — including the name — can be edited in place safely.
* `.am2Data` vs `.am2data` is **pure filename case**; 28 distinct byte-sequences each
  appear under both spellings. CONFIRMED.
* `AM2` vs `AM3` is a **version tag only**; both parse identically and are handled by the
  same DSP entry point. CONFIRMED.
* **`AM4` is real** — a 7868-byte record with a 928-parameter GRU, shipped in BlackBox
  factory data. It is *not* the same size or layout as AM2/AM3. CONFIRMED.
* **322 of 1298** header-bearing corpus files have a **corrupted magic** (`00 00 32 00`
  and friends) produced by `am2converter`. This is the strongest candidate explanation
  for the "auditions badly, works once saved to a slot" community report. HYPOTHESIS.

---

## 2. Container layout

### 2.1 File-level shapes

| Shape | Bytes | Meaning | Evidence |
| :--- | ---: | :--- | :--- |
| `.am2` | 6144 | payload only, no header | CONFIRMED |
| `.am2Data` / `.am2data` / `.am3Data` | 6204 | 60-byte header + payload | CONFIRMED |
| flash / factory amp record | 6204 | identical bytes, padded into an 8192-byte slot | CONFIRMED |
| flash record after DSP init | 6272 | 6204 + `LMT\0` + 16 `float32` appended at runtime | CONFIRMED |
| `AM4` record | 7868 | 60-byte header + 1952 `float32` | CONFIRMED |
| `AM4` record after DSP init | 7936 | 7868 + `LMT\0` + 16 `float32` | CONFIRMED |

**CONFIRMED — `.am2` is a headerless `.am2Data`.** SHA-256 of the 6144-byte body of every
6204-byte file was compared against SHA-256 of every 6144-byte file. **23 payloads occur
in both forms**, e.g. `028_Clean_Dumble_JB85.am2` ↔ `Dumble_Clean.am2data`,
`332_High_Gain_Marshall_JCM_2000.am2` ↔ `Marshall_JCM2000_AuditionX_A+.am2data`.
This matches `am2manager/am2.go`: `am2Length = 6144`, `am2dataLength = 6204`,
`d.OriginData = data[0:60]; d.Am2 = data[60:]`.

**CONFIRMED — 6144 is not an outlier, the task brief's "every file is 6204" is wrong.**
388 of 1687 capture-extension files in the corpus are exactly 6144 bytes and carry no
header at all. Method: `os.path.getsize` over the whole corpus.

### 2.2 The 60-byte header, complete offset table

All multi-byte numbers are **little-endian**. Offsets are from the start of the file.

| Off | Size | Type | Name | Observed values | Notes |
| ---: | ---: | :--- | :--- | :--- | :--- |
| `0x00` | 4 | ASCII | `magic` | `AM2\0`, `AM3\0`, `AM4\0` | Byte 3 is always `0x00` corpus-wide (n=1 distinct). See §6 for corrupt variants. |
| `0x04` | 14 | ASCII | `name` | ≤13 chars + NUL | NUL-terminated, NUL-padded. **Longest observed = 13 chars**, so 13 is the capacity and `0x11` is the guaranteed terminator. |
| `0x12` | 1 | `uint8` | `mix` | 0, 24, 40, 62, 64, 80, 90, 100 (8 distinct) | 0–100 %. 1277/1298 files use 100. `am2manager` default 100. |
| `0x13` | 1 | `uint8` | `level` | 50–255 (70 distinct), mode 100 (719 files) | Output level. `am2manager` allows 0–255, default 100. |
| `0x14` | 1 | `uint8` | `gain_max` | 40–100 (35 distinct), mode 60 (703 files) | Upper end of the capture's usable gain-knob range. |
| `0x15` | 1 | `uint8` | `gain_min` | 0–60 (38 distinct), mode 30 (857 files) | Lower end. |
| `0x16` | 2 | — | reserved | **always `00 00`** | n=1 distinct value across all 1298 header files. |
| `0x18` | 4 | `float32` | `eq1_freq` | 20.0 – 4392.0 Hz | Band 1 centre/corner frequency. |
| `0x1C` | 4 | `float32` | `eq1_gain_min` | −24.0 … +6.3 dB | |
| `0x20` | 4 | `float32` | `eq1_gain_max` | −14.1 … +24.0 dB | |
| `0x24` | 4 | `float32` | `eq2_freq` | 500.0 – 13647.0 Hz | Band 2. |
| `0x28` | 4 | `float32` | `eq2_gain_min` | −24.0 … +2.4 dB | |
| `0x2C` | 4 | `float32` | `eq2_gain_max` | −12.1 … +24.0 dB | |
| `0x30` | 4 | `float32` | `eq3_freq` | 20.0 – 11965.0 Hz | Band 3. |
| `0x34` | 4 | `float32` | `eq3_gain_min` | −24.0 … +13.0 dB | |
| `0x38` | 4 | `float32` | `eq3_gain_max` | −7.7 … +24.0 dB | |
| `0x3C` | | | *end of header* | | Payload begins here. |

**How the numeric types were chosen (CONFIRMED).** A per-byte distinct-value map over all
1298 header-bearing files gives the discriminating evidence:

* `0x18`, `0x24`, `0x30` have **exactly one** distinct value (`0x00`) and `0x1B`, `0x27`,
  `0x33` take only IEEE-754 exponent bytes `0x41`–`0x46`. That is the signature of three
  `float32` whose values are round numbers in the 8 Hz – 8 kHz range. `uint16`/`uint32`
  readings of the same bytes give nonsense (e.g. `0x44FA0000` = 1157627904 as `uint32`,
  2000.0 as `float32`).
* `0x1C`/`0x1D` etc. take only `{00,33,66,9a,cd}` / `{00,33,66,99,cc}` — the mantissa tails
  of values that are multiples of 0.1 dB. Again `float32`, not integers.
* `0x12`–`0x15` are single bytes — `uint8`, matching `am2manager`'s
  `cp[0x12]=Mix; cp[0x13]=Level; cp[0x14]=GainMax; cp[0x15]=GainMin`. What establishes the
  type is that all four stay within one byte and take few enough distinct values to be
  scalars rather than parts of a wider field.

  ⚠️ **Do not read maxima out of this bullet.** It originally said these four "top out at
  100/200/90/53", which contradicts the offset table above (`level` 50–255, `gain_max`
  40–100, `gain_min` 0–60) — 255 vs 200, 100 vs 90 and 60 vs 53 cannot both be corpus-wide
  maxima for the same fields. The two passes evidently covered different subsets and the
  discrepancy was never reconciled. **The offset table is the one to trust**, since it is
  the one stated as a range over the full 1298-file header corpus; the figures here are
  withdrawn rather than corrected, because nothing in this document establishes which subset
  produced them. Re-derive from the corpus before quoting either.

**CONFIRMED — `am2manager`'s `InitData` is exactly this header.** `InitData[24:28] =
{0,0,200,66}` = `float32` 100.0 at `0x18`; `InitData[28:32] = {0,0,192,192}` = −6.0;
`{0,0,250,68}` = 2000.0 at `0x24`; `{0,0,122,69}` = 4000.0 at `0x30`. Its bytes 18–21 are
`100,100,60,30` — mix/level/gain_max/gain_min. Its bytes 0–3, however, are `{0,0,50,0}`,
**not** `AM2\0`; see §6.

### 2.3 Name field semantics

* Capacity **13 ASCII characters**, terminator at `0x11`. CONFIRMED: name-length histogram
  over the corpus peaks at 13 and never reaches 14.
* Factory records prefix the 1-based slot index into the name, e.g. `1UWE-Twins`,
  `10FORTIN_CALI`, `20MarkLm_BS`. CONFIRMED from `blackbox_am3_ampCab.bin`. This is a
  convention, not a requirement — user captures such as `plexi` and `AGUILARCLEAN` have no
  prefix.
* **1076 of 1298** header-bearing corpus files have an entirely empty name field.
  CONFIRMED. M-EFCS therefore displays the *filename*, not the embedded name, for most
  community captures. A CLI that renames a capture should rewrite **both** unless the user
  says otherwise.
* 46 files have non-zero bytes *after* the terminating NUL (stale bytes from a longer
  previous name). Harmless, but a renamer should zero the whole field.

---

## 3. The payload: 1536 `float32`

### 3.1 Block map (AM2 / AM3)

| Float idx | Byte off (in record) | Count | Block | Purpose |
| ---: | ---: | ---: | :--- | :--- |
| 0 – 255 | 60 – 1083 | 256 | `fir_pre` | 256-tap FIR, stored time-reversed |
| 256 – 271 | 1084 – 1147 | 16 | `gru_Wi_a` | GRU gate A input weights |
| 272 – 287 | 1148 – 1211 | 16 | `gru_Wi_b` | GRU gate B input weights |
| 288 – 303 | 1212 – 1275 | 16 | `gru_Wi_c` | GRU gate C input weights |
| 304 – 559 | 1276 – 2299 | 256 | `gru_Wh_a` | GRU gate A recurrent, 16×16 row-major |
| 560 – 815 | 2300 – 3323 | 256 | `gru_Wh_b` | GRU gate B recurrent, 16×16 |
| 816 – 1071 | 3324 – 4347 | 256 | `gru_Wh_c` | GRU gate C recurrent, 16×16 |
| 1072 – 1087 | 4348 – 4411 | 16 | `gru_vec` | trailing 16-vector (output layer / bias) |
| 1088 – 1343 | 4412 – 5435 | 256 | `fir_post` | 256-tap FIR, stored time-reversed |
| 1344 – 1407 | 5436 – 5691 | 64 | `aux1` | 64-tap block |
| 1408 – 1471 | 5692 – 5947 | 64 | `aux2` | 64-tap block |
| 1472 – 1535 | 5948 – 6203 | 64 | `aux3` | 64-tap block |

**CONFIRMED — two independent methods agree on every boundary.**

*Method 1, disassembly.* `libamx_parser.dylib` exports `_calc_bias_gru`, which calls
`_ANN_Unit_init(x0 + 0x43c, 0)`. `0x43c = 1084 = 60 + 4×256` — i.e. the GRU weight base is
**float index 256** of the payload. `ANN_Unit_init` then runs 16 iterations (`i = 0…15`,
`cmp x8, #0x40`) reading, relative to that base:

```
float[i]                 -> gate A input weight,     i = 0..15
float[16+i]              -> gate B input weight
float[32+i]              -> gate C input weight
float[48  + 16i .. +15]  -> gate A recurrent row i   (16 wide)
float[304 + 16i .. +15]  -> gate B recurrent row i
float[560 + 16i .. +15]  -> gate C recurrent row i
float[816 + i]           -> trailing vector
```

which totals 3×16 + 3×256 + 16 = **832 floats**, occupying payload floats 256–1087.

*Method 2, corpus variance.* Mean `|w|` per index over all 1686 records shows sharp,
unambiguous steps at exactly 256, 1088, 1344, 1408, 1472:

```
index  1080..1087 : 0.2145 0.2206 0.2212 0.2330 0.2214 0.2220 0.2247 0.2142
index  1088..1095 : 0.0115 0.0057 0.0063 0.0046 0.0053 0.0046 0.0050 0.0055   <- step
index  1340..1343 : 0.2726 0.2254 0.2282
index  1344..1347 : 0.0411 0.0313 0.0332 0.0316                               <- step
```

and the mean-`|w|` plateaus inside 256–1087 sit at 0.766 / 0.414 / 0.666 for the three
16-value input vectors and 0.486 / 0.629 / 0.361 for the three 16×16 matrices — exactly the
seven sub-blocks the disassembly predicts, in exactly the predicted positions.

### 3.2 Topology

**CONFIRMED — a single-layer, 3-gate, 16-unit GRU with scalar input.** Exported symbols are
`_calc_bias_gru` and `_calc_bias_gru_am4`; the log strings inside `_ANN_Unit_init` are
`"GRU Unit init 0 ---- "`, `"GRU Unit init 1 ---- "`, `"GRU Unit init success ---- "`.

Parameter accounting, hidden size H = 16, input size 1:

| Term | Count | Matches file? |
| :--- | ---: | :--- |
| 3 gates × input weights (H × 1) | 48 | floats 256–303 ✔ |
| 3 gates × recurrent weights (H × H) | 768 | floats 304–1071 ✔ |
| 1 trailing vector (H) | 16 | floats 1072–1087 ✔ |
| **total** | **832** | ✔ exact |

Candidate topologies that also give 832 and were **rejected**:
* PyTorch `GRU(1, 16)` with the standard `b_ih` + `b_hh` needs 3·16·1 + 3·16·16 + 2·3·16 =
  912 — 80 too many, and the disassembly reads only one trailing 16-vector. Rejected.
* `LSTM(1, 12)` = 4·12·(1+12) + 2·4·12 = 720; `LSTM(1, 13)` = 832 **numerically matches**
  but is rejected because the loop is 16 iterations wide, the matrices are 16×16, and there
  are three gate blocks, not four.
* Two stacked GRUs, WaveNet, or a dense MLP do not produce three 16×16 matrices plus three
  16-vectors plus one 16-vector. Rejected.

**HYPOTHESIS — the trailing 16-vector `gru_vec` is the output (dense 16→1) layer, and the
network has no bias terms at all.** Evidence: only one 16-vector exists and no per-gate
bias block is read; the routine that consumes it is *named* `calc_bias_gru`, i.e. it
*computes* an operating bias at load time rather than reading one. Test: build the GRU in
NumPy with `gru_vec` as the output projection, run a guitar DI through it, and compare the
result against the same capture auditioned in M-EFCS.

**HYPOTHESIS — `fir_pre` / `fir_post` are 256-tap FIR filters stored newest-tap-last.**
Evidence: mean `|w|` rises monotonically across each block by a factor of ~35
(0.013 → 0.46 for `fir_pre`, 0.0058 → 0.225 for `fir_post`), and a single file's values
alternate sign — the classic shape of a decaying impulse response written in reverse, which
is how a convolution delay-line is normally laid out. Test: reverse the block, take its
FFT, and check for a smooth minimum-phase magnitude response.

**HYPOTHESIS — `aux1`/`aux2`/`aux3` are the three tone-stack filter kernels named by the
three EQ triples in the header.** Evidence: exactly three blocks, exactly three header EQ
bands, and each block shows the same reversed-FIR ramp. **Counter-evidence that must be
respected:** they are *not* derived from the header numbers — files sharing an identical
header EQ tuple have different `aux` bytes (44 of 164 distinct EQ tuples map to more than
one `aux` block). So if they are tone filters, they are trained per-capture rather than
synthesised from the header. Test: reverse each block, FFT it, and check whether the peak
of `aux1`'s response lands on `eq1_freq`.

### 3.3 Fixed-point conversion and the runtime `LMT` block

**CONFIRMED — the DSP is Q21 fixed point at 44.1 kHz.** `ANN_Unit_init` multiplies every
weight by the immediate `0x49FFFFF8` = `2097151.0` = 2²¹−1 and then `fcvtzs` to `int32`.
The activation tables are named `_tanh_tab_q23` / `_sigm_tab_q23`. `calc_bias_gru` runs the
network for `0xac44 = 44100` iterations, feeding
`expf(i × -6.907755 × 4.5351473e-05)` — that is `exp(-ln(1000) · i / 22050)`, a decaying
excitation over exactly one second at 44.1 kHz.

**CONFIRMED — the `LMT` block.** After the sweep, `calc_bias_gru` writes the ASCII sentinel
`LMT\0` (`0x00544D4C`, tested as `w8 - 0x544000 == 0xd4c`) at record offset `0x183c = 6204`
and 16 `float32` at 6208–6271. This is why flash amp slots are 8192 bytes for a 6204-byte
record: the firmware caches per-capture limiter coefficients immediately after the payload.
If the sentinel is already present the routine prints `"lmt already added, pass..."` and
returns −1.

Verified directly: `blackbox_am4_ampCab.bin` block 0 contains `4c 4d 54 00` at offset 7868,
followed by 16 plausible floats, and its last non-zero byte is 7936 = 7868 + 68.
`blackbox_am3_ampCab.bin` amp blocks are all-zero from 6204 onwards, i.e. AM2/AM3 factory
data ships *without* a precomputed `LMT` and the pedal fills it in on first load.

**Implication for the CLI:** never write a file of 6272 bytes and never treat trailing
`LMT\0` bytes as payload. A 6204-byte file is the correct interchange form.

---

## 4. AM2 vs AM3 vs AM4

### 4.1 AM2 vs AM3 — a version tag only

**CONFIRMED — identical structure.** 352 distinct `AM2\0` and 33 distinct `AM3\0` files were
compared block by block:

| block | AM2 mean `\|w\|` | AM3 mean `\|w\|` |
| :--- | ---: | ---: |
| `fir_pre` | 0.0665 | 0.0699 |
| GRU (832) | 0.4879 | 0.4855 |
| `fir_post` | 0.0290 | 0.0359 |
| `aux1`/`aux2`/`aux3` | 0.0616 / 0.0627 / 0.1433 | 0.0904 / 0.0893 / 0.1667 |

Same length, same block boundaries, same magnitudes. The disassembly agrees: only
`AM4` gets a distinct entry point (`calc_bias_gru_am4`); everything else goes through
`calc_bias_gru`. **A parser must accept `AM2\0` and `AM3\0` interchangeably.**

**CONFIRMED — the file extension does not determine the magic.** 9 files named `*.am2data`
carry `AM3\0`. Conversely no `*.am3Data` file carries `AM2\0`. Trust the magic, never the
extension.

The differences that do exist are in *user-set* header fields, not structure. The one that
survives scrutiny: in this corpus every `AM3\0` file has `eq3_freq` ≥ 2300 Hz, while `AM2\0`
files go as low as 20 Hz. `level` medians are identical (100 for both), so do not read
anything into that.
HYPOTHESIS: `AM3` marks captures produced by a later M-EFCS trainer with different
defaults. Test: create one capture in the current M-EFCS and read its magic.

### 4.2 AM4 — real, and a different size

**CONFIRMED.** `…/lib/resources/bin/blackbox/blackbox_am4_ampCab.bin` ships 20 records with
magic `AM4\0` (`1J900_CL`, `2FD_CL`, `3JC120_CL`, …). Same 60-byte header (verified: name
at `0x04`, `mix/level/gain_max/gain_min` = 100/170/60/30, three EQ triples at
300 Hz/−12/+12, 850 Hz, 2000 Hz). Payload is **1952 `float32` = 7808 bytes**, record length
**7868 bytes**.

`calc_bias_gru_am4` calls `ANN_Unit_init(x0 + 0x83c, 1)` — `0x83c = 2108 = 60 + 4×512`, so
the GRU base is float index **512**, and the `am4` branch reads seven extra 16-vectors
(floats 816–927 relative to base), giving **928 parameters**. Corpus-independent
confirmation from the factory blob's own variance map:

```
floats    0 – 511  : 512-tap FIR (ramp 0.0046 -> 0.294)
floats  512 – 1439 : 928-parameter GRU  (3x16 input, 3x 16x16 recurrent, 7x16 vectors)
floats 1440 – 1951 : 512-tap FIR (ramp 0.0031 -> 0.139)
```

512 + 928 + 512 = 1952. ✔

**Correction to `mvave-blackbox-ble/docs/memory_map.md`.** That document says the pedal
stores amp captures as `.am4`. This is **not wrong, but it is incomplete**: `AM4` is a real
record magic used by current BlackBox factory data, but it is a *different, larger* record
(7868 vs 6204 bytes, 928 vs 832 GRU parameters). Every user capture in this 1686-file
corpus is `AM2` or `AM3`. HYPOTHESIS: a `.am4` file extension exists for AM4-format
captures; no such file was found on this machine, so the extension itself is unconfirmed.

---

## 5. Checksums: a clean negative

**CONFIRMED — there is no checksum, CRC or hash anywhere in the container.**

Method: for a 400-file sample of well-formed `AM2`/`AM3` records, nine checksum functions
(`crc32`, `adler32`, `sum8`, `sum16`, `sum32`, `xor8`, `crc16-ccitt`, `crc16-xmodem`,
`crc16-ibm`, `crc16-modbus`) were computed over eight byte ranges (whole file, payload
only, header only, header 0–18, header 18–60, payload-plus-tail, pre-GRU region, GRU
region) and compared, both exactly and low-byte-only, against **every** `uint8`,
`uint16` LE, `uint16` BE and `uint32` LE window in the 60-byte header. Result: **zero
hits.**

Corroborating structural evidence: the only bytes in the header that could hold a checksum
are `0x16`–`0x17`, and those are `00 00` in all 1298 header-bearing files (one distinct
value). There is no trailer — the file ends on the last weight.

**Consequence, and it is the useful one:** header edits are safe. A CLI may rewrite the
name, the magic, `mix`, `level`, `gain_min`, `gain_max` and the EQ triples in place without
recomputing anything. Only the byte you touched changes.

---

## 6. Corrupt-magic files, and the "auditions badly, saves fine" report

### 6.1 The observation

Magic distribution over the 1298 header-bearing corpus files (CONFIRMED, first four bytes):

| Magic | Count | Interpretation |
| :--- | ---: | :--- |
| `41 4d 32 00` `AM2\0` | 917 | well-formed |
| `00 00 32 00` | 318 | **corrupt** — `A` and `M` zeroed, `'2'` survives |
| `41 4d 33 00` `AM3\0` | 59 | well-formed |
| `00 00 35 00` | 2 | corrupt, `'5'` in byte 2 |
| `00 00 38 00` | 1 | corrupt, `'8'` in byte 2 |
| `2f 0b 32 00` | 1 | corrupt, plus a garbage name field |

### 6.2 Provenance of the `00 00 32 00` family — CONFIRMED

`am2manager`'s `InitData` literal begins `{0, 0, 50, 0, …}`. `50 = 0x32 = '2'`. Its EQ
defaults are 100 Hz / 2000 Hz / 4000 Hz with ±6 dB, and its mix/level/gain defaults are
100/100/60/30. **Every** `00 00 32 00` file in this corpus reproduces that header byte for
byte, including the empty name:

```
00 00 32 00  00 00 00 00 00 00 00 00 00 00 00 00 00 00  64 64 3c 1e  00 00
00 00 c8 42  00 00 c0 c0  00 00 c0 40   <- 100 Hz, -6, +6
00 00 fa 44  00 00 c0 c0  00 00 c0 40   <- 2000 Hz
00 00 7a 45  00 00 c0 c0  00 00 c0 40   <- 4000 Hz
```

Decisive corroboration: **5 payloads appear in the corpus under both `AM2\0` and
`00 00 32 00`** — the same 6144 weight bytes with two different headers. These files are
`am2converter` output: a bare `.am2` was wrapped in `InitData` and shipped as `.am2Data`.
Someone transcribing `InitData` from a hex dump lost the leading `41 4d`.

The `00 00 35 00` and `00 00 38 00` files carry non-default mix/level/EQ, so they are *not*
plain `am2converter` output; their byte-2 values `'5'` and `'8'` remain unexplained.
HYPOTHESIS: a second, differently-broken converter. Test: ask the pack maintainers, or find
another file from the same uploader.

### 6.3 The audition-vs-slot report — HYPOTHESIS

The community reports that some `.am2Data` files sound wrong or fail in the editor's
audition but work once written to a pedal slot.

**HYPOTHESIS: the magic is the discriminator.** The host DSP has two entry points selected
by record type — `calc_bias_gru` for AM2/AM3 and `calc_bias_gru_am4` for AM4 — which read
weights from *different offsets* (`+0x43c` vs `+0x83c`) and consume *different* parameter
counts. A host that dispatches on the magic string, and finds `00 00 32 00`, has no valid
branch; it will either refuse, or fall through to a default that reads the wrong offsets and
produces garbage. The pedal's flash-write path, by contrast, plausibly just DMAs 6204 bytes
into a slot and lets the firmware assume AM2, so the same file behaves once it is stored.

**Supporting circumstantial evidence:** 322 of 1298 corpus files (24.8 %) carry a broken
magic — a large enough population to generate exactly this kind of folklore. All of them
also have an **empty name**, which is independently consistent with the "these ones look
odd in the editor" complaint.

**The test that settles it, and it is safe:** take one `00 00 32 00` file, copy it, patch
bytes 0–1 to `41 4d` (`amx.repair_magic`), and audition both copies in M-EFCS. No device
write is required. This is a read-only, reversible, purely local experiment. *It was not
run here* — driving the M-EFCS GUI is out of scope for this workflow.

**Alternative hypotheses not excluded:** (a) `level = 100` from `InitData` is far below the
capture's intended level and the difference is only loudness; (b) the audition path applies
the header EQ while the slot path does not. Both are testable with the same copy-and-patch
experiment plus a level match.

---

## 7. Flash and factory-blob layout (context for the CLI)

CONFIRMED from `…/lib/resources/bin/blackbox/*_ampCab.bin`, each 245760 bytes:

```
slot stride 8192 bytes, 30 slots
  slots  0..19 : one amp record each
                 blackbox_am3_ampCab.bin       -> magic AM2\0, 6204 bytes used
                 blackbox_choptones_ampCab.bin -> magic AM3\0, 6204 bytes used
                 blackbox_am4_ampCab.bin       -> magic AM4\0, 7936 bytes used (incl. LMT)
                 remainder of each slot zero-padded
  slots 20..29 : two CAB records each, stride 4096  -> 20 cab/IR slots
```

Note the filename generation (`am3`) and the record magic (`AM2`) are **independent**:
`blackbox_am3_ampCab.bin` contains `AM2\0` records. Do not infer one from the other.

One anomaly: `blackbox_am3_ampCab.bin` slot 7 (`8TH_DiselHgn`) has non-zero bytes out to
7990 instead of 6204 — leftover from a previous, larger record that was not erased. It
parses correctly as a 6204-byte AM2 record. CONFIRMED.

This corroborates `memory_map.md`'s "20 amp names / 20 cab names" name blocks.

### 7.1 The `CAB` record — on-device IR format

CONFIRMED, from `blackbox_*_ampCab.bin` slots 20–29:

| Off | Size | Field |
| ---: | ---: | :--- |
| `0x00` | 4 | magic `CAB\0` |
| `0x04` | 14 | name, NUL-terminated ASCII, ≤13 chars, factory names carry the 1-based odd slot index |
| `0x12` | 1 | unknown, values 1 / 2 |
| `0x13` | 1 | unknown, values 0x1e / 0x20 / 0x32 / 0x5a |
| `0x14` | 4074 | **1358 samples, 24-bit signed little-endian PCM** |
| `0xFFE` | 2 | trailer, varies |
| | **4096** | total; two per 8192-byte flash slot |

Endianness was settled empirically: decoding `blackbox_am4_ampCab.bin`'s first cab as
24-bit **little**-endian gives a clean impulse response — peak 1.000 at sample 5,
roughness 0.34, tail RMS 0.0036 — while big-endian gives noise (peak at sample 348,
roughness 1.30, tail RMS 0.549). The `blackbox_am3_ampCab.bin` cabs are palindromic in
each 3-byte group (byte 0 == byte 2 for 1358/1358 samples), i.e. they were up-converted
from 16-bit sources by bit replication, and decode identically either way.

**1358 taps at 44.1 kHz = 30.8 ms.** That is the entire IR budget of the pedal.

### Three IR length figures, reconciled

Three numbers circulate in this project — 1024, 1358 and 2048 — and each was at some point
labelled confirmed, which read as a contradiction. It is not one. They measure three
different things:

| Figure | What it actually is | Where |
| ---: | :--- | :--- |
| **1024** taps / 23.2 ms | The **vendor specification line**, from the Korean manual and the product copy. It is intent, not contract: the vendor's own factory content does not meet it. | `official-docs.md` §3 |
| **1358** taps / 30.8 ms | What an **on-device `CAB` flash record physically holds**. This is the real ceiling and the figure a validator should warn against. | this section |
| **2048** frames | The length of most **factory source `.wav` files** in the Mac-side M-EFCS library. Those are inputs to the upload path, not device storage. Measured across all twenty: sixteen are 2048 frames; 1AC-SeVin is 10000, 5HIFI_OK is 22026, 15JC120_BOX is 13230 and 10SoldSC412 is 1020. | `presets/library.md` |

**The on-device figure outranks the others**, because it is the one that determines what
survives. Wherever a threshold is quoted it should be 1358 taps / 30.8 ms, and it should
name the vendor's 1024 alongside so a reader who has seen the spec line is not left
wondering. `tools/blackboxctl/blackboxctl/captures.py` currently hard-codes `IR_TAPS = 1024`
and warns from 23.2 ms, with a comment noting that 1024 is a documented figure rather than a
validation requirement; that is a defensible conservative choice, but the code and §8.2 below
warn at different thresholds derived from different sources, and they should be made to
quote the same number and name the other. **Reported, not changed** — no code was modified,
per the workspace rules in `AGENTS.md`.

---

## 8. Validating `.wav` impulse responses

### 8.1 What is demonstrably in the user's library

CONFIRMED by parsing all 293 files in
`/Users/mendong/Library/Containers/com.digAmp.dgAmp/Data/Documents/M-EFCS/cabFile`
(RIFF chunk walk, `fmt ` and `data` chunks):

| Property | Observed |
| :--- | :--- |
| container | 293/293 valid RIFF/WAVE, no RF64, no WAVE_FORMAT_EXTENSIBLE |
| sample rate | 44100 (193), 48000 (97), 96000 (3) |
| channels | mono (261), **stereo (32)** |
| encoding | PCM 24-bit (285), PCM 16-bit (6), PCM 32-bit (1), IEEE float 32-bit (1) |
| length | 1000 – 88202 frames; 20.8 ms – 2000 ms; median 200 ms |
| extra chunks | `LIST`, `bext`, `iXML`, `_PMX`, `cart`, `id3 `, `cue `, `JUNK`, `LGWV`, `ResU` all present |
| file size | 3044 – 432736 bytes |

**The twenty factory IRs, broken out.** The table above mixes the vendor's own files with
the user's installed ones. Measured separately by reading each `fmt ` chunk (read-only,
2026-08-28), the twenty slot-prefixed factory files are:

| Property | Factory subset (n = 20) |
| :--- | :--- |
| channels | mono, 20/20 |
| sample rate | 44100 (15), **48000 (3** — 3V30_MD421, 4G12-EVH_CT, 11FD_TW1980**)**, **96000 (2** — 8FRMAN112, 14Recto_112**)** |
| encoding | PCM 24-bit (18), PCM 32-bit integer (1 — 7VOX_AC30), IEEE float 32-bit (1 — 10SoldSC412) |
| length | 2048 frames (16); 1020 (10SoldSC412), 10000 (1AC-SeVin), 13230 (15JC120_BOX), 22026 (5HIFI_OK) |

This is the strongest single piece of evidence that the vendor's "44.1K/24Bit mono WAV,
1024 sampling points" line is intent rather than contract: **five of the vendor's own twenty
factory IRs violate the sample-rate half of it, and nineteen violate the length half.**
Note also that two of the files carry a trailing space before the extension —
`17AgSVT410 .wav` and `20Tace412 .wav` — which will break any restore tooling that looks
them up by their slot-table name.

**Important caveat on what this proves.** These files are present in M-EFCS's own
`cabFile` library directory, so the application at minimum accepted them into its library.
It does **not** prove the pedal loaded each one, because that was not observable without
sending state-changing commands. Treat the table as "the importer tolerates this variety",
HYPOTHESIS, not as "the device plays all of these", which is untested. The single
demonstrated import of a non-conforming file, and the exact limits of what it proves, are
stated once in `presets/library.md` under "What that does and does not prove"; every other
document defers to it.

### 8.2 What a validator should warn about

Ranked by how likely the user is to be surprised:

1. **Length.** The device stores **1358 taps at 44.1 kHz (30.8 ms)** — §7.1, measured from
   the on-device record. 285 of the 293 IRs in the library are longer than that and are
   necessarily truncated on import. Warn above 30.8 ms; warn loudly above ~100 ms, where a
   reverb tail is clearly being discarded. When reporting this to a user, name the vendor's
   published figure too — 1024 taps / 23.2 ms — and say which is which, or the two numbers
   look like a contradiction. See the reconciliation table in §7.1.
2. **Sample rate ≠ 44100.** The DSP runs at 44.1 kHz (CONFIRMED from the 44100-iteration
   sweep in `calc_bias_gru`). 48 kHz and 96 kHz files must be resampled by the host; a
   1024-tap 48 kHz IR becomes ~941 taps at 44.1 kHz. Warn, and state the resampled length.
   Warn, but do not refuse: **five of the pedal's own twenty factory IRs are not 44.1 kHz** —
   3V30_MD421, 4G12-EVH_CT and 11FD_TW1980 at 48 kHz, 8FRMAN112 and 14Recto_112 at 96 kHz —
   so the vendor does not hold its own content to the published spec line.
3. **Stereo.** 32 library files are stereo. The cab slot holds one mono channel. Warn that
   a channel will be dropped or summed, and say which.
4. **Bit depth other than 24.** The on-device format is 24-bit signed. 16-bit input loses
   nothing that matters; 32-bit float input can exceed ±1.0 and will clip. Warn if any
   sample of a float file exceeds ±1.0. Determine float-vs-integer from the `fmt ` chunk's
   `wFormatTag` (1 = PCM, 3 = IEEE float), **not** from bit depth alone: Python's `wave`
   module reports `sampwidth == 4` for both and cannot tell them apart. The single IEEE-float
   file in this library is the factory `10SoldSC412.wav` (tag 3, 32-bit, 1020 frames); the
   single 32-bit *integer* file is the factory `7VOX_AC30.wav` (tag 1, 32-bit, 2048 frames).
   Those two have been confused elsewhere in this repository for exactly this reason.
5. **Non-normalised peak.** The device format is fixed-point with hard headroom at ±2²³.
   Warn if the peak is below −20 dBFS (the IR will be too quiet after truncation) or at
   exactly 0 dBFS with more than a handful of samples at full scale (already clipped).
6. **Leading silence.** A long pre-delay eats the 1358-tap budget. Warn if the peak sample
   is more than ~64 samples into the file.
7. **Exotic containers.** Reject RF64 and `WAVE_FORMAT_EXTENSIBLE` with a non-PCM
   sub-format rather than guessing; none appear in the library, so there is no evidence the
   importer handles them.

---

## 9. Validation rules for a capture file

Implemented in `amx.py`. Errors reject the file; warnings inform.

**Errors**

| Rule | Rationale |
| :--- | :--- |
| size ∈ {6144, 6204} (or 6272 with a trailing `LMT\0`) | any other size is not a capture |
| magic ∈ {`AM2\0`, `AM3\0`} for 6204-byte records | §6; `AM4\0` implies a 7868-byte record |
| name field NUL-terminated within 14 bytes | otherwise the device reads past the field |
| name characters printable ASCII 0x20–0x7E | non-printable names are heap garbage, §6 |
| bytes `0x16`–`0x17` == `00 00` | one distinct value corpus-wide |
| `mix` ≤ 100 | documented range |
| every EQ frequency in (0, 22050) | Nyquist at the device's 44.1 kHz |
| EQ `gain_min` ≤ `gain_max` per band | an inverted range is meaningless |
| all 1536 floats finite | NaN/Inf would propagate through the GRU |
| all `\|w\|` < 1024 | `w × (2²¹−1)` must fit `int32`; observed max is 34.88 |

**Warnings**

| Rule | Count in corpus |
| :--- | ---: |
| empty name field | 1092 (1076 genuinely empty + 16 whose name failed the ASCII check) |
| magic looks like `am2manager` `InitData` damage (`00 00 xx 00`) | 321 |
| EQ gain range does not bracket 0 dB | 104 |
| non-zero bytes after the name terminator | 46 |
| EQ band frequencies not ascending | 19 |
| record carries a runtime `LMT` block | 0 in files, 20 in `blackbox_am4_ampCab.bin` |

**Deliberately *not* a rule:** there is no checksum to verify (§5).

**Note on the `magic looks like InitData damage` count.** §1 and §6.1 count **322** files
with a corrupt magic; the warning row above says **321**. Both are right and the split is
worth stating: the warning fires only on the `00 00 xx 00` family (321 files), while the
error-side count also includes one file whose magic is `2f 0b 32 00`, which is damaged but
not `InitData`-shaped. 321 + 1 = 322.

### The shipped tool does not implement these rules exactly

`tools/blackboxctl` deliberately diverges, and the difference is a policy choice rather than
a defect on either side. Two of the errors above are demoted to **warnings** there:

* **Corrupt magic** is a warning, not a refusal. A hard refusal would block four of the
  capture files that `presets/library.md` requires for its amp slot map, and those files play
  correctly once installed. With the demotion, all 39 `ampFile` entries parse; under the
  rules as written above, six amp files and one IR were refused.
* **The IR format rules** in §8.2 are advisory there for the same reason — the pedal's own
  factory content does not satisfy them (§8.1).

Both policies are defensible; two rule sets standing unreconciled is not, which is why this
is recorded here. If a validator is ever meant to be strict, §9 is the strict rule set and
`tools/blackboxctl/STATUS.md` records what the tool actually enforces.

---

## 10. Reference parser

[`reference/amx.py`](./reference/amx.py) — pure Python 3, no third-party imports. Preserved
as an artefact, not maintained; the supported tool is `tools/blackboxctl`, whose validation
policy differs from §9 in the ways recorded there.

```
parse(path)            -> Capture (magic, name, mix/level/gain, 3 EQ triples, 1536 floats,
                          errors[], warnings[])
regions(capture)       -> {"fir_pre": [...], "gru_Wh_a": [...], ...}
repair_magic(data, 2)  -> bytes with a well-formed AM2\0 / AM3\0 magic
set_name(data, "x")    -> bytes with the 14-byte name field rewritten and zero-padded
split_ampcab_bin(data) -> ([(off, amp_slot)], [(off, cab_record)])
decode_cab(record)     -> (name, [1358 floats in -1..1])
```

### 10.1 Verbatim run over the whole corpus

```
$ .../venv313/bin/python .../scratchpad/fmt2/amx.py .../scratchpad/fmt2/corpus
files examined : 1684
PASS           : 1346
  of which with warnings: 786
FAIL           : 338

--- warning histogram ---
    752  empty name
     87  eq band gain range does not bracket 0 dB
     30  non-zero bytes after the name NUL terminator
     15  eq band frequencies are not ascending
```

(The CLI walks by file extension, so it sees 1684 files: it misses 3 extension-less
6204-byte copies of `MAsato Better Call Saul CMP+AMP1 NoCAB  Loss = 0078 am2Data` and its
warning histogram counts only files that passed.)

Walking by **size or extension** — 1687 files — gives the fuller picture:

```
files examined: 1687
PASS: 1349   (of which with warnings: 789 )
FAIL: 338

error histogram:
    318  bad magic 00003200
     16  name contains non-printable bytes
      2  bad magic 00003500
      1  bad magic 2f0b3200
      1  bad magic 00003800
      1  bad size 0

warning histogram:
   1092  empty name
    321  magic looks like am2manager InitData damage
    104  eq band gain range does not bracket 0 dB
     46  non-zero bytes after the name NUL terminator
     19  eq band frequencies are not ascending
```

Per source directory:

```
--- ampFile   files 39   PASS 33   (13 with warnings)   FAIL 6
--- dsFile    files 14   PASS 14   ( 0 with warnings)   FAIL 0
--- pack      files 1631 PASS 1299 (773 with warnings)  FAIL 332
```

**Every failure is a real defect in the file, not a parser gap.** 322 are corrupt magics,
16 are heap-garbage name fields, 1 is a zero-byte file
(`pack/3_Best_Captures_Picked_By_Users/1_Андрей_Полевой/_FULL RIG with CAB/BognerShiva ch2 g12 wCAB ext 110 16b+.am2Data`).
All 40 factory amp records in `blackbox_am3_ampCab.bin` and
`blackbox_choptones_ampCab.bin` parse with **zero** errors and zero warnings, and both
files' first cab record decodes to 1358 taps with peak 0.965 / 0.978.

### 10.2 Weight statistics, for sanity thresholds

Over all 1686 records (1686 × 1536 = 2.59 M floats): no NaN, no Inf, global range
−34.882 … +25.629, mean 0.0045, σ 0.590.

| block | n | min | max | mean `\|w\|` | p99.9 `\|w\|` |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `fir_pre` | 256 | −17.498 | 12.188 | 0.0678 | 2.797 |
| `gru_Wi_a` | 16 | −34.882 | 25.629 | 0.7664 | 20.255 |
| `gru_Wi_b` | 16 | −7.984 | 9.402 | 0.4142 | 5.090 |
| `gru_Wi_c` | 16 | −25.269 | 21.134 | 0.6661 | 16.409 |
| `gru_Wh_a` | 256 | −16.662 | 16.581 | 0.4855 | 5.421 |
| `gru_Wh_b` | 256 | −11.212 | 10.718 | 0.6288 | 5.627 |
| `gru_Wh_c` | 256 | −19.610 | 14.667 | 0.3606 | 4.284 |
| `gru_vec` | 16 | −3.570 | 4.339 | 0.2278 | 2.242 |
| `fir_post` | 256 | −3.139 | 2.993 | 0.0270 | 1.281 |
| `aux1` | 64 | −2.258 | 2.539 | 0.0596 | 0.967 |
| `aux2` | 64 | −3.355 | 2.120 | 0.0597 | 1.163 |
| `aux3` | 64 | −14.416 | 5.063 | 0.1451 | 2.455 |

Per-file max `|w|`: min 0.780, median 4.184, p99 24.739, max 34.882. A capture whose max
`|w|` is below ~0.5 or above ~200 is worth flagging as anomalous even though it is not
strictly invalid.

---

## 11. Open questions

1. Are `aux1`/`aux2`/`aux3` the tone-stack kernels named by the header EQ triples?
   (§3.2; FFT test.)
2. Is `gru_vec` the output projection or a bias? (§3.2; NumPy reimplementation test.)
3. What do `CAB` header bytes `0x12`/`0x13` mean, and what is the 2-byte record trailer?
   Values 1/2 and 0x1e/0x20/0x32/0x5a were observed; too few samples to decide.
4. Does a `.am4` file extension exist in the wild, and does M-EFCS import it?
5. What produced the `00 00 35 00` / `00 00 38 00` magics? (§6.2.)
6. Does patching a corrupt magic fix the audition problem? (§6.3 — the one experiment
   worth running next, and it needs no device write.)
