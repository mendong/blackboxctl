# BlackBox Capture and IR Library

The built-in amp models and factory presets are no longer the basis for any preset in
this repository. Presets are built from community capture files plus third-party IRs.

This is the shared vocabulary for every preset document here: presets refer to amp and IR
slots **by number**, and the numbers are defined in the two slot maps below.

## Why

Two Korean-community sources reach the same conclusion:

- A BlackBox owner's write-up: the factory presets are not catastrophic but there is no
  reason to use them once capture files are available. The author's working rig is an
  `OD + Friedman BE100` capture with an IR whose name starts with `ML BEST`.
  **Uncited.** The URL for this post was not recorded and could not be recovered. It may
  be the same petra7 muleboard post listed under Sources; until that is checked, do not
  treat it as independent corroboration of petra7's guide.
- petra7's BlackBox guide, appendix 3: the factory presets are described as a mess, and
  the 20 built-in IRs as clearly weaker than Soundwoofer/ML IRs. The recommendation is to
  keep the 20 stock M-VAVE amp captures if you like them but replace the IRs.

Sources are listed at the bottom of this file.

## Device and app state

- Captured: 2026-08-28 KST
- M-EFCS: `3.5.2615` (`CFBundleVersion` `3052615`), Mac App Store build, bundle id
  `com.digAmp.dgAmp`
- Connected device label reported by M-EFCS: `BLACKBOX v20`. This is the editor's label
  for the product, not a confirmed firmware version.
  `docs/reverse-engineering/official-docs.md` infers from a firmware filename on disk that
  this unit runs V19. The two have not been reconciled; neither should be quoted as the
  firmware version. The read-only device-name query would settle it.
- Last connection evidence: all read commands were re-verified on 2026-08-28, including all
  80 presets and both slot name tables; the migration completed on 2026-08-29. Re-check
  endpoints before assuming the pedal is still connected.
- Device capacity: 20 amp slots, 20 IR/CAB slots, both replaceable. The 20 factory amp
  models can be restored from the PC version of M-EFCS.

## Reading and writing device state

Since 2026-08-28 the pedal can be read directly, without the GUI and without loading
anything, using [`tools/blackboxctl`](../tools/blackboxctl/). On 2026-08-29 its bounded
write paths were also physically verified and the complete AMP/CAB library was applied
without GUI clicks.

```sh
cd tools/blackboxctl
python -m blackboxctl selftest      # offline protocol check; touches nothing
python -m blackboxctl device names  # all 20 amp and 20 IR slot names, straight from flash
python -m blackboxctl device preset N   # decode stored PNN without loading it
python -m blackboxctl library diff  # compare this file's slot maps against what is on disk
python -m blackboxctl device library-apply ../../presets/device-library.json  # dry run
```

`device names` is the live authority on what is actually in each slot;
[`device-library.json`](device-library.json) is the applied manifest. Its
`source_set_sha256` pins the ordered 40-file source set so a same-named changed
capture or IR is refused during offline preflight. This file
explains its design and dated evidence.
`device preset N` is the way to satisfy the "record current contents before overwriting"
rule in [AGENTS.md](../AGENTS.md). Read
[tools/blackboxctl/STATUS.md](../tools/blackboxctl/STATUS.md) before trusting any claim
about the tool.

## Mac-side library location

M-EFCS is sandboxed. Its file library lives at:

```
~/Library/Containers/com.digAmp.dgAmp/Data/Documents/M-EFCS/
```

It contains nine subfolders. Only the first three matter for this work:

| Folder | Contents | Backed up |
| --- | --- | --- |
| `ampFile` | capture files (`.am2`, `.am2Data`, `.am3Data`) shown in the AMP tab — 39 entries | yes |
| `cabFile` | IR files (`.wav`) shown in the CAB tab — 293 entries | yes |
| `dsFile` | drive-capture copies written by older imports — 14 entries | yes |
| `model` | 114 MB app-internal model blob, do not touch | no |
| `aiToneFile` | `amp` / `cab` / `ds` subfolders, all empty | no |
| `audio_library` | one `files` subfolder used by the app | no |
| `downloadFile`, `otherFile`, `shareFile` | empty | no |

Counts are a host-library snapshot verified read-only on 2026-08-28, after the additions
described below. Recount before relying on them in a later session.

Verified behaviour: files copied straight into `ampFile` / `cabFile` do **not** appear
while the app is running, but they do appear after M-EFCS is restarted. The app keeps no
index file, so the list is a directory scan at launch. This is the fast way to load a
whole library at once instead of using `Load AMP/CAB File to List` one file at a time.

Install procedure:

1. Copy files into `ampFile` (captures) or `cabFile` (IRs).
2. Quit and reopen M-EFCS.
3. Reconnect the BlackBox in the `Connect` tab.
4. The new entries are listed in the AMP / CAB tabs with an `Audition` button each.

`python -m blackboxctl library install` performs step 1 and `library restart-editor`
performs step 2. Both are dry runs unless given `--yes`.

A backup of the library as it was before this change is kept **outside the repository**
in durable user storage with mode `0600`:

```
~/.local/share/blackboxctl/backups/M-EFCS-library-before-20260828-041029.tgz
```

SHA-256 `8ba9355a2fec2c6e6acdef865eb79c68ef0d25a8a9d5305aa9c67d6bdb49e27a`;
3,525,756 bytes; contains `ampFile` (15 captures), `cabFile` (210 IRs) and `dsFile` (14)
as they were. Retain it in durable storage; it is the only restore point for the
pre-existing library, and the community pack it was displaced by is not archived anywhere
on this machine.

## What is installed

- Captures added to `ampFile`: 24, on top of the 15 that were already there — 39 total,
  which is what is on disk now.
- IRs added to `cabFile`: 83, on top of the 210 that were already there — 293 total.
- `01A_ML Sound Lab's BEST IR IN THE WORLD_Use_This_IR_as_Main_Default.wav` from the pack
  is byte-identical to the file in ML Sound Lab's own free Dropbox giveaway, so the pack
  copy is the genuine IR. SHA-256:
  `0cafcee04e2c9e6794b4d98c8fcf7168131b8eb78c460ed88d53f843983e4e2e`.

Not reproducible from this repository: there is no manifest of which 107 files came from
the pack, no archived copy of the pack, and no recorded hash for it. The only host is a
mutable Google Drive folder. If that link rots, the exact install cannot be re-created.

### IR format, measured rather than assumed

M-VAVE's own spec line, in the Korean manual and the official product copy, is
`44.1K/24Bit mono WAV, 1024 sampling points`. Measurement shows that line is a statement
of intent, not a contract — **the vendor does not hold its own factory IRs to it.**

Method: the RIFF `fmt ` chunk was read directly, so the format tag (integer PCM vs IEEE
float) is known, and the frame count comes from the `data` chunk size divided by the block
align. An earlier revision of this file used Python's `wave` module, which reports bit
depth but *not* the format tag, and that produced one wrong entry — corrected below.

**All 20 factory IRs, measured on disk:**

| Slot | File | Rate | Bits | Frames | Duration |
| ---: | --- | ---: | --- | ---: | ---: |
| 1 | `1AC-SeVin` | 44.1 k | 24 | 10000 | 227 ms |
| 2 | `2JVM_1960_57` | 44.1 k | 24 | 2048 | 46 ms |
| 3 | `3V30_MD421` | **48 k** | 24 | 2048 | 43 ms |
| 4 | `4G12-EVH_CT` | **48 k** | 24 | 2048 | 43 ms |
| 5 | `5HIFI_OK` | 44.1 k | 24 | 22026 | 500 ms |
| 6 | `6WANGS212_ECM` | 44.1 k | 24 | 2048 | 46 ms |
| 7 | `7VOX_AC30` | 44.1 k | **32 int** | 2048 | 46 ms |
| 8 | `8FRMAN112` | **96 k** | 24 | 2048 | 21 ms |
| 9 | `9MeOSick-III` | 44.1 k | 24 | 2048 | 46 ms |
| 10 | `10SoldSC412` | 44.1 k | **32 float** | 1020 | 23 ms |
| 11 | `11FD_TW1980` | **48 k** | 24 | 2048 | 43 ms |
| 12 | `12MESA_412` | 44.1 k | 24 | 2048 | 46 ms |
| 13 | `13HIW412SWF` | 44.1 k | 24 | 2048 | 46 ms |
| 14 | `14Recto_112` | **96 k** | 24 | 2048 | 21 ms |
| 15 | `15JC120_BOX` | 44.1 k | 24 | 13230 | 300 ms |
| 16 | `16Agula410` | 44.1 k | 24 | 2048 | 46 ms |
| 17 | `17AgSVT410 ` | 44.1 k | 24 | 2048 | 46 ms |
| 18 | `18DgDG212N` | 44.1 k | 24 | 2048 | 46 ms |
| 19 | `19MbSway210` | 44.1 k | 24 | 2048 | 46 ms |
| 20 | `20Tace412 ` | 44.1 k | 24 | 2048 | 46 ms |

All twenty are mono. What the vendor ships against its own spec line:

- **Length.** 16 of 20 are 2048 frames — double the stated 1024. The exceptions are
  slot 1 (10000), slot 5 (22026), slot 15 (13230) and slot 10 (1020). Only slot 10 is
  near the stated figure.
- **Sample rate.** 5 of 20 are not 44.1 kHz: slots 3, 4 and 11 are 48 kHz; slots 8 and 14
  are 96 kHz.
- **Bit depth.** 2 of 20 are not 24-bit: slot 7 is 32-bit **integer** PCM (format tag 1),
  slot 10 is 32-bit **IEEE float** (format tag 3).

Only 13 of the 20 factory IRs are 44.1 kHz / 24-bit / mono, and none of the twenty is
1024 frames.

**What that does and does not prove — the canonical statement.** Other documents refer
here rather than restating it:

* **Demonstrated.** The vendor's own factory *source* IRs do not meet the vendor's own
  spec line: one is 32-bit float, one is 32-bit integer, two are 96 kHz, three are 48 kHz,
  and none is 1024 frames.
* **Demonstrated, once.** The import path accepts a non-conforming file. A 48 kHz,
  65536-frame mono source was written into IR slot 1 through M-EFCS on 2026-08-28 and the
  slot works. That is the only observed import of a non-conforming file.
* **Not demonstrated.** What the pedal does with a *stereo* source, or with a bit depth
  other than 24. Nothing here establishes which channel it keeps or whether it sums them.
* **Not demonstrated, and not what the table above shows.** That the pedal is *running* a
  32-bit float or 96 kHz IR. The table measures `.wav` files in the Mac-side library, which
  are inputs to the upload path. The observed user-CAB staging record and the bundled
  factory-blob records are both signed 24-bit PCM, so something converts before or during
  upload. The final user-slot waveform cannot be read back.

**On the 1024/1358/2048 figures.** They measure different artifacts. 1024 is the vendor's
published spec line. A bundled factory-blob CAB record holds 1358 taps. Most factory source
`.wav` files have 2048 frames, and M-EFCS 3.5.2615 also staged 2048 samples in the observed
2026-08-29 user upload.
The latter two are independently observed facts, not proof that the final flash layout has
2048 taps. See
[capture-format-spec.md §7.1](../docs/reverse-engineering/capture-format-spec.md).

**Pre-migration selected-IR snapshot, measured the same way on 2026-08-28:**

| Slot | Ch | Rate | Bits | Frames | Duration |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1 | **48 k** | 24 | 65536 | 1365 ms |
| 2 | **2** | 44.1 k | 24 | 13769 | 312 ms |
| 3 | **2** | 44.1 k | 24 | 6302 | 143 ms |
| 4 | **2** | 44.1 k | 24 | 6302 | 143 ms |
| 5 | 1 | **48 k** | 24 | 24000 | 500 ms |
| 6 | 1 | 44.1 k | 24 | 8850 | 201 ms |
| 8 | **2** | 44.1 k | 24 | 66150 | **1500 ms** |
| 9 | **2** | 44.1 k | 24 | 1837 | 42 ms |
| 10 | 1 | 44.1 k | 24 | 22050 | 500 ms |
| 11 | **2** | 44.1 k | 24 | 6302 | 143 ms |
| 12 | **2** | 44.1 k | 24 | 6302 | 143 ms |
| 13 | 1 | 44.1 k | 24 | 22051 | 500 ms |
| 14 | 1 | 44.1 k | 24 | 8192 | 186 ms |
| 15 | 1 | **48 k** | 24 | 24001 | 500 ms |
| 16 | 1 | **48 k** | 24 | 28801 | 600 ms |
| 17 | 1 | 44.1 k | 24 | 16538 | 375 ms |
| 18 | 1 | **48 k** | 24 | 24001 | 500 ms |
| 19 | 1 | 44.1 k | 24 | 2048 | 46 ms |
| 20 | 1 | 44.1 k | 24 | 22050 | 500 ms |

Slot 7 was omitted from this dated table because it still held its factory IR at the time.
The 2026-08-29 migration subsequently replaced it with `7HIWATT412`; this table remains the
measurement record for the other nineteen selected source files. Every listed file is
24-bit integer PCM.

Of the 19, seven match the vendor spec **on channel count, sample rate and bit depth** —
slots 6, 10, 13, 14, 17, 19, 20. None matches on length; the closest is slot 19 at 2048
frames. The other twelve deviate:

- stereo: slots 2, 3, 4, 8, 9, 11, 12
- 48 kHz: slots 1, 5, 15, 16, 18

Slot 1 is the one demonstrated import of a non-conforming file: 48 kHz survives the trip,
because it is the ML Best IR, it is written to the device, and it is what both community
sources actually play through. Stereo is the untested risk: nothing here establishes which
channel the pedal keeps, or whether it sums them. If a slot sounds thin,
phasey, or quieter than its neighbours, check this table first — a stereo source is the
prime suspect, and converting it to 44.1 kHz 24-bit mono before installing is the fix.

Because the observed staging path keeps only the first 2048 samples, prefer IRs whose useful
energy is early. Most of a guitar cabinet's character lives in the first 20–50 ms, which is
why heavily shortened IRs can still work. **Slot 8 is the most exposed file in the map**:
at 66150 frames it is the longest by a wide margin, 1500 ms, of which only about 3 % enters
the staging record — and it is also stereo, and it is the CAB for Hana P02. If P02 sounds
wrong, that is the first thing to change.

## Slot replacement decision

The owner explicitly retired the old P41 sound on 2026-08-29, so no AMP/CAB slot remains
reserved for it. AMP slot 1 is now Friedman BE100 C45 (`1BE100_C45`) and CAB slot 7 is a
Hiwatt 4x12 (`7HIWATT412`). All 20 AMP and all 20 CAB slots now belong to the new library.
P01–P12 were rewritten against that map. P13–P80 retain their pre-migration numeric slot
references, so their sounds changed with the shared slots and must be treated as unverified
until intentionally rewritten or auditioned.

### Slot exposure: what a slot write actually changes

Replacing a slot silently changes every preset that points at it. This audit was the
precondition for the first slot write, and it is now **done**: all 80 presets were read
from flash on 2026-08-28 with `blackboxctl device preset N`, read-only, without loading
any of them. **This section is a pre-migration snapshot:** the names and references in the
two tables below are the **2026-08-28 state**, not the current AMP/CAB name tables.

The headline result is that **P06–P40 are not empty.** They are fully populated factory
presets, every one of them pointing at an amp slot and an IR slot. The planned map
replaces amp slots 2–20 and IR slots 2–6 and 8–20, which repoints most of them.

**Presets P42–P80 exist and are unused defaults**: every one reads amp slot 1, IR slot 1,
volume 85. They also settle the preset count — flash indices 0–79 answer and index 80 is
refused, so **80 presets is confirmed**, not assumed.

Pre-migration amp-slot demand across P01–P41:

| Amp slot | Factory name | Presets pointing at it |
| ---: | --- | --- |
| 1 | `J900_CL` | P04 P17 P41 — plus every unused default P42–P80 |
| 2 | `FD_CL` | P01 P21 P26 |
| 3 | `JC120_CL` | P03 P09 |
| 4 | `BLUE_OD` | P02 P06 P10 P25 P29 P30 |
| 5 | `RAT_OD` | P13 P14 P15 P27 P31 |
| 6 | `M-VAVE_OD` | P07 P32 |
| 7 | `SUPA_OD` | **none** |
| 8 | `DARKS_DS` | P11 |
| 9 | `J900_DS` | P05 P18 P22 |
| 10 | `JHS_DS` | P16 |
| 11 | `EVH_5150` | P28 P34 |
| 12 | `FRIMAN` | P19 P23 |
| 13 | `XC_DS` | P08 P12 P36 |
| 14 | `ROOM40` | P33 |
| 15 | `JVM` | P20 P24 P35 |
| 16 | `AgDb750_BS` | P37 |
| 17 | `ApSVT_BS` | P38 |
| 18 | `PjBuddy_BS` | P40 |
| 19 | `DgXu_BS` | P39 |
| 20 | `MarkLm_BS` | **none** |

Pre-migration IR-slot demand across P01–P41:

| IR slot | Factory name | Presets pointing at it |
| ---: | --- | --- |
| 1 | `ML_BEST_IR` (already replaced on 2026-08-28) | P09 P25 — plus every unused default P42–P80 |
| 2 | `JVM_1960_57` | P04 P05 P08 P21 P22 P23 P24 |
| 3 | `V30_MD421` | P27 |
| 4 | `G12-EVH_CT` | P20 P35 |
| 5 | `HIFI_OK` | P03 P06 P07 P26 P29 |
| 6 | `WANGS212_ECM` | P19 |
| 7 | `VOX_AC30` | P02 P13 P14 P41 |
| 8 | `FRMAN112` | P15 P16 |
| 9 | `MeOSick-III` | P30 |
| 10 | `SoldSC412` | P34 |
| 11 | `FD_TW1980` | P01 P31 |
| 12 | `MESA_412` | P17 P18 P33 P36 |
| 13 | `HIW412SWF` | P28 |
| 14 | `Recto_112` | **none** |
| 15 | `JC120_BOX` | P10 P11 P12 P32 |
| 16 | `Agula410` | P37 |
| 17 | `AgSVT410` | P38 P40 |
| 18 | `DgDG212N` | P39 |
| 19 | `MbSway210` | **none** |
| 20 | `Tace412` | **none** |

Historical consequences established before the 2026-08-29 replacement:

- **Free slots.** Amp slots 7 and 20, and IR slots 14, 19 and 20, are referenced by no
  preset in P01–P41. They are the only slots that can be replaced with zero side effects,
  and the natural place to start.
- **IR slot 7 had four dependents, not one.** P02, P13, P14 and P41 all pointed at it;
  after the approved replacement, all four therefore changed until rewritten.
- **Amp slots 16–20 are bass amps** (`_BS`), used only by P37–P40, which are the factory
  bass presets. For a guitarist those five slots are the cheapest to give up — but doing so
  does change P37–P40.
- **The busiest slots are IR 2 (seven presets) and amp 4 (six presets).** Replacing those
  has the widest blast radius.
- P01–P12 were subsequently rewritten, so their temporary exposure was accepted.

Before migration, the preservation choices were to replace only the five free slots or to
accept that P06–P40 would change. The owner chose the latter, retired the factory bank, and
the 2026-08-29 migration replaced all 40 shared slots after the 80-preset backup.

## Amp slot map (20)

File names below are **abbreviated stems**. The real files carry longer suffixes
(`_AuditionX`, `_A+`, and so on) and the extension case is inconsistent on disk.
`python -m blackboxctl library diff` resolves stems to real files by prefix. The applied
40-entry authority is now [`device-library.json`](device-library.json).

| Slot | File | Role |
| --- | --- | --- |
| 1 | `101_OD_Friedman BE100 C45 SAT_100K Epochs_use_Friedman_IR` | Friedman BE100 C45, general lead |
| 2 | `014B_Clean_Fender_65_Deluxe_Reverb_use_Fender IR` | Fender clean, P01 |
| 3 | `013_Clean_Fender_Twin_Rev_AuditionX_A+` | bigger Fender clean |
| 4 | `016B_Clean_Fender_Princeton_1962_Chris_Stapleton_Edition_V7_T8` | small-box clean |
| 5 | `011_Clean_Fender_Tweed_Lux_59_v2` | tweed clean |
| 6 | `001_Clean_SansAmp_GT2_Fender_IR_included_Low_Volume` | petra7's top clean pick; IR baked in, so turn CAB off |
| 7 | `027_Clean_CoryWong_Funk_Console_(N_DSP)` | petra7's Strat pairing with ML Best IR |
| 8 | `028_Clean_Dumble_JB85` | Dumble clean, petra7 suggests CAB off |
| 9 | `009_Clean_Vox_AC30_212g12_30k` | AC30 clean |
| 10 | `010_Clean_Vox_AC50_BR` | Vox clean, good with ML Best IR |
| 11 | `024_Clean_Matchless_DC_94_good_with_ML_BEST_IR` | chime clean |
| 12 | `109_OD_Vox_AC30_Crunch` | AC30 edge of breakup, P02 |
| 13 | `004_Clean_Marshall_JTM4544_NAM` | Marshall clean, P04 |
| 14 | `020_Clean_Marshall_JCM800 2203 Master 4 Gain 8 _086` | JCM800 clean to edge |
| 15 | `125_OD_JCM800_AuditionX` | JCM800 crunch, P05 |
| 16 | `119_OD_1959_Classic_NAM` | Plexi |
| 17 | `103_OD_OD+Friedman_BE100_C45_SAT_Bright_Gain3_100K_Epochs` | the tone from the owner write-up |
| 18 | `201_Dist_RAT+Friedman_BE-100_loss=0571_100K Epochs_use_Friedman_IR` | petra7's distortion pick |
| 19 | `221B_Dist_RAT_D11_F2_V2_AuditionX_A+` | RAT, pairs with a Fender Twin IR |
| 20 | `501_Acoustic_G_Preamp_noCAB_use_Acoustic_IR(101-109)_Best_Recommend` | acoustic sim, P03 |

Slots 4 and 9 are the two most heavily abbreviated: on disk they are
`016B_..._V7_T8_AuditionX_A+.am2data` and `009_Clean_Vox_AC30_212g12_30k_AuditionX.am2data`.

Left in the Mac library for auditioning, not written to a slot:
`101_OD_Friedman BE100 C45 SAT` (full stem `..._100K Epochs_use_Friedman_IR`),
`108_OD_Vox_AC30_Drive` (`..._AuditionX`),
`021_Clean_Marshall_JCM2000_DSL` (`..._AuditionX`),
`128_OD_Klon_Centaur`, `137A_OD_BOSS_SD1_good_with_Rocksta_Fender_IR`.

## IR slot map (20)

Device slot names live in a fixed 14-byte flash record holding an ASCII string plus a
terminator, measured on both name blocks on 2026-08-28. The usable field is therefore
**13 characters including the numeric prefix** for slots 1–9, and 12 for slots 10–20 whose
prefix is two digits. The longest name on the device is `6WANGS212_ECM`, at exactly 13.
Every short name below fits.

| Slot | Device name | File | Role |
| --- | --- | --- | --- |
| 1 | `1ML_BEST_IR` | `01A_ML Sound Lab's BEST IR IN THE WORLD_Use_This_IR_as_Main_Default` | default IR for everything |
| 2 | `2GTRHACK45` | `01B_GuitarHack JJ CENTRE45 0_High` | brighter general IR |
| 3 | `3RKS_CUSTOM` | `01C_Rocksta Reactions Custom Cab NT1-A A -2 1 5_Low_High_Heavy` | heavy general IR |
| 4 | `4FD_TWIN57` | `02A_Fender 1 Twin Reverb SM57 A 2 3 3 45_Rocksta` | Fender Twin |
| 5 | `5FD_DLX_C12K` | `02F_Fender 6 1966 Deluxe Reverb 1x12 Jensen C12K - SM57 - Cap Edge` | Fender Deluxe, P01 |
| 6 | `6FD_PRINCE` | `02C_Fender 3 1964 Princeton Amp_Jensen P10R-SM57` | Fender Princeton |
| 7 | `7HIWATT412` | `29_Hiwatt Maxwatt M412 SM57 1` | broad clean/crunch 4x12 |
| 8 | `8VOX_AC30_TB` | `04D_Vox 4 AC30 1966 Top Boost - e906 - Tone junkie` | AC30 Top Boost, P02 |
| 9 | `9VOX_AC15` | `04A_Vox 1 AC15C1 SM57 1` | AC15 |
| 10 | `10VOX_BLUE` | `04E_Vox 5 AC30 WT Blue 2x12 160+SM57 EQ` | AC30 Blue |
| 11 | `11MR_1960VB` | `03E_Marshall 5 1960VB SM57 A 0 0 0_Rocksta_center` | Marshall 1960, P04 |
| 12 | `12MR_JCM800` | `03B_Marshall 2 JCM800 Lead Series SM57 C -5 0 1_Rocksta` | JCM800, P05 |
| 13 | `13MR_412_V30` | `03G_Marshall 7 1960 412 V30 57 - 01` | Marshall 4x12 V30 |
| 14 | `14FRIEDMAN` | `09_Friedman BE100 Cab II` | pairs with amp slots 17 and 18 |
| 15 | `15V30_BALL` | `07A_Celestion_V30 2x12 Ball 0.0in 0in_High_Quality` | Mesa / Orange / Diezel / Soldano |
| 16 | `16JC120` | `16_ Roland® JC-120_dc 2x12` | JC-120 clean |
| 17 | `17DUMBLE` | `14_Dumble_LR-MD421-G1265_bip_1_dc` | pairs with amp slot 8 |
| 18 | `18CL80_MD421` | `01D_CL80 2x12 MD421 2.5in 0.0in-Middle_High` | mid-forward general IR |
| 19 | `19AC_D35` | `102_Acoustic_G_IR_Martin_D35SA_Gplus_44100_Bld` | acoustic, P03 |
| 20 | `20AC_TAYLOR` | `107_Acoustic_G_IR_Taylor 414 57v Pz1` | acoustic alternative |

Slot 15's file name is abbreviated; on disk it is
`07A_Celestion_V30 2x12 Ball 0.0in 0in_High_Quality For_Mesa_Orange_Diezel_Soldano_BlackStar.wav`.

Factory contents that were replaced, for reference if a restore is ever needed. Nineteen of
these twenty were read straight out of the pedal's flash over USB MIDI SysEx on 2026-08-28
(see [device-validation.md](../docs/reverse-engineering/device-validation.md) STEP 4), so
those nineteen names are the device's own rather than an inference from filenames. **Slot 1
is the exception:** the final 2026-08-29 name read returns `1ML_BEST_IR` there, because this
project overwrote it. `1AC-SeVin` is recorded from the pre-write GUI state and from the file
present in `cabFile` at the time of the library audit.

`1AC-SeVin`, `2JVM_1960_57`, `3V30_MD421`, `4G12-EVH_CT`, `5HIFI_OK`, `6WANGS212_ECM`,
`7VOX_AC30`, `8FRMAN112`, `9MeOSick-III`, then `10SoldSC412`, `11FD_TW1980`, `12MESA_412`,
`13HIW412SWF`, `14Recto_112`, `15JC120_BOX`, `16Agula410`, `17AgSVT410`, `18DgDG212N`,
`19MbSway210`, `20Tace412`.

As verified on 2026-08-29, all twenty remained as files in `cabFile`, so their source files
were available for a later official restore or deliberate re-upload. Two are stored with a
**trailing space before the extension**: `17AgSVT410 .wav` and `20Tace412 .wav`. An
exact-name lookup written from the list above will miss those two.

## How to write one slot

`blackboxctl` now writes AMP and CAB slots directly; M-EFCS clicking is no longer needed.
Every command is a dry run until `--yes` is supplied:

```sh
blackboxctl device amp save 1 path/to/capture.am2Data --name 1BE100_C45 --yes
blackboxctl device cab save 7 path/to/ir.wav --name 7HIWATT412 --level 50 --yes
blackboxctl device library-apply presets/device-library.json --yes
```

The batch command validates every source before opening MIDI, commits one slot at a time,
verifies the stored name, journals every result, and resumes only from a journaled,
verified save with the same source hash and a still-matching persistent name. The full
manifest is [`device-library.json`](device-library.json).

For reference, the old GUI process was:

1. Open the `CAB` tab for IRs or the `AMP` tab for captures.
2. Type a distinctive part of the filename in `Search`. The match is a fuzzy subsequence
   match, so a long query is safer than a short one.
3. Click the row. It turns orange to show it is selected.
4. Click `Save to Device`. A dialog appears with a `name` field, a `Position` dropdown, and
   a `Save` button.
5. Set `name`. It is pre-filled with a truncation of the filename. The field holds 13
   characters including the leading slot number, 12 for slots 10–20.
6. Set `Position` to the target slot. The dropdown lists all 20 slots with their current
   contents, and defaults to slot 1.
7. Click `Save`. The dialog closes.
8. Verify by reopening `Save to Device` and reading the `Position` dropdown. It now shows
   the new name at that slot number. Reading the whole dropdown verifies all 20 slots at
   once. `python -m blackboxctl device names` verifies the same thing from flash, without
   the GUI.

## Device write log

All 20 AMP and all 20 CAB names now match `device-library.json`. Five presets were
written earlier through the GUI — P01-P03 on 2026-07-20 and P04-P05 on 2026-07-26 — and
remain recorded in [hana.md](hana.md) and
[boulevard-of-broken-dreams.md](boulevard-of-broken-dreams.md).

| Date | Target | Result |
| --- | --- | --- |
| 2026-08-28 | IR slot 1: `1AC-SeVin` to `1ML_BEST_IR` | passed |
| 2026-08-29 | AMP slot 20: factory to `20AC_PREAMP`, CLI protocol proof | exact ACKs + name passed |
| 2026-08-29 | CAB slot 20: factory to `20AC_TAYLOR`, CLI protocol proof | exact ACKs + name passed |
| 2026-08-29 | Full 40-entry library manifest | 37 saved, 3 matching-name skips; all 40 names passed |
| 2026-08-29 | P01–P12 core bank | all twelve 92-byte flash reads matched their rendered images |

Evidence, two independent readings:

- the M-EFCS `Position` dropdown showed `1ML_BEST_IR` at slot 1 immediately after the save;
- later the same day the IR name table was read straight out of flash over USB MIDI SysEx
  and slot 1 came back `1ML_BEST_IR`
  ([device-validation.md](../docs/reverse-engineering/device-validation.md) STEP 4).

The definitive 2026-08-29 result is the live `device names` read plus the mode-0600
journal at
`~/.local/share/blackboxctl/journal/library-apply-20260829-123820.json`. AMP weights and
CAB waveforms have no known read-back path, so name verification is not a listening test.

## Remaining steps, in order

1. Audition P01–P12 through the intended guitar/pickup/output path at matched loudness.
2. Adjust gain/dynamics, AMP EQ, CAB, modulation, delay, reverb, then output volume.
3. Re-render, save, and re-read any adjusted preset; keep the final 92-byte images and slot
   map in this repository.

## Working rules for capture-based presets

1. Pair by family. Fender capture with a Fender IR, Vox with Vox, Friedman with the
   Friedman cab, Mesa/Orange/Diezel/Soldano with a Celestion V30 IR. ML Best IR works
   with anything and is the fallback.
2. Clean captures are recorded quiet. Raise amp gain and amp level. Overdrive,
   distortion, and high-gain captures are recorded loud, so start their gain and level
   near the middle before auditioning.
3. A capture whose name says `IR_included`, `CabOn`, or `full rig` already contains a
   cabinet. Turn the CAB block off, or leave it on with a different-EQ IR only if you
   want to reshape it. The last IR in the chain dominates the final tone.
4. ML Best IR is mid-forward. On a Strat clean tone it can feel stiff; petra7's fix is to
   pull the amp MID down to roughly 15-20.
5. If an IR level or EQ feels overbearing, drop IR level to about 80 rather than fighting
   it with amp EQ.
6. Auditioning has a device-side quirk: at least one of the capture or the IR must already
   be saved on the device. To audition IRs, use a saved capture; to audition captures, use
   a saved IR. Both unsaved means the first one loaded goes silent. This is the most likely
   explanation for the write-up's "other IRs produced no sound" symptom.
7. Into a real amp's return, petra7 prefers AMP on and CAB-IR off. For headphones, an
   audio interface, or PA, CAB-IR must be on.
8. Level reference from the pack author: master volume 50, preset volume 80, IR volume
   100, amp volume and gain as needed. This repository uses preset total volume 85 for
   consistency with the existing presets, and trims IR level per preset instead.

## Known device limits

- Latency is about 6 ms for amp plus IR, about 9 ms with the time-based effects. The
  audible gap is on preset changes and effect on/off, not on picking.
- There is no BPM entry, so dotted-eighth delay has to be dialled by ear.
- The `Analog` delay behaves closer to a digital delay. `Dual` and `Dtape` can be pushed
  toward a digital delay with their parameters.
- Firmware updates and recovery belong to the official M-UPGRADE workflow, not
  `blackboxctl`. Platform availability can change; use M-VAVE's current download page and
  the exact ANNBLACKBOX firmware. See
  [blackboxctl-recovery.md](../docs/blackboxctl-recovery.md).
- If a helicopter-like noise appears while the device is connected to the Mac over USB,
  turn the BlackBox Bluetooth off or pair it with a phone. The noise comes from an
  unconnected Bluetooth radio.
- M-EFCS 3.5.2615 staged a user CAB as a 6,164-byte transfer record on 2026-08-29: a 20-byte header plus
  2,048 samples of 24-bit mono PCM, about 46 ms at 44.1 kHz. Separately, the bundled
  factory `*_ampCab.bin` files use 4,096-byte CAB records holding 1,358 taps, about 31 ms
  ([capture-format-spec.md](../docs/reverse-engineering/capture-format-spec.md) §7.1).
  The firmware exposes no user-slot waveform read-back, so neither factory layout nor
  staging length proves the final persistent representation. Preserve early IR energy and
  verify the sound rather than claiming a byte-for-byte payload read-back.

## Sources

- petra7, BlackBox amp modeler and effects processor review (V16.8):
  <https://www.mule.co.kr/m/guide/63185935>
- petra7, BlackBox capture and IR update information:
  <https://www.mule.co.kr/m/guide/63692036>
- petra7, free IRs and M-VAVE BlackBox capture profile material:
  <https://mule.co.kr/m/muleboard/63236984>
- Capture and IR pack `ANN_Captures_IRs_V16.8.zip`, 44.3 MB, from the folder linked in
  those posts: <https://drive.google.com/drive/folders/1f9G_xo7ev32TdYt5zyP6fjiXbPGMSi8->
  `capture-format-spec.md` calls the same material the `Black_Box_Captures_V16.8` pack;
  whether that is the extracted directory name or a second download was never recorded,
  and no hash or byte size for the archive itself exists.
- ML Sound Lab, The Best IR in the World, free: <http://bit.ly/MLSoundLab>. This is a
  link shortener; the canonical vendor URL was not recorded, and neither were the terms
  attached to the giveaway. The SHA-256 above establishes that the file is genuine, not
  that it may be redistributed.
- Fractal forum thread on that IR:
  <https://forum.fractalaudio.com/threads/the-best-ir-in-the-world-free.137347/>
- Soundwoofer free IR library (recommended by petra7, host was unreachable during this
  session): <https://soundwoofer.com/Library/Index>
- Official M-VAVE capture and IR sharing community, also reachable from the `Community`
  tab inside M-EFCS: <https://community.m-vave.com>
- Capture search site: <https://am2manager.fly.dev/find-capture>

Full source inventory with licences: [docs/sources.md](../docs/sources.md).

The pack redistributes third-party captures and IRs collected by community members. The
ML Best IR in it is the vendor's own free giveaway; the provenance of the other files is
whatever the original uploaders provided. No capture or IR is committed to this
repository.
