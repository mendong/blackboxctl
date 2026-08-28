# BlackBox Capture and IR Library

The built-in amp models and factory presets are no longer the basis for any preset in
this repository. Presets are built from community capture files plus third-party IRs.

## Why

Two independent Korean-community sources reach the same conclusion:

- A BlackBox owner's write-up: the factory presets are not catastrophic but there is no
  reason to use them once capture files are available. The author's working rig is an
  `OD + Friedman BE100` capture with an IR whose name starts with `ML BEST`.
- petra7's BlackBox guide, appendix 3: the factory presets are described as a mess, and
  the 20 built-in IRs as clearly weaker than Soundwoofer/ML IRs. The recommendation is to
  keep the 20 stock M-VAVE amp captures if you like them but replace the IRs.

Sources are listed at the bottom of this file.

## Device and app state

- Captured: 2026-08-28 KST
- M-EFCS: `3.5.2615` (`CFBundleVersion` `3052615`), Mac App Store build, bundle id
  `com.digAmp.dgAmp`
- Connected device label: `BLACKBOX v20`
- Device capacity: 20 amp slots, 20 IR/CAB slots, both replaceable. The 20 factory amp
  models can be restored from the PC version of M-EFCS.

## Mac-side library location

M-EFCS is sandboxed. Its file library lives at:

```
~/Library/Containers/com.digAmp.dgAmp/Data/Documents/M-EFCS/
```

| Folder | Contents |
| --- | --- |
| `ampFile` | capture files (`.am2`, `.am2Data`, `.am3Data`) shown in the AMP tab |
| `cabFile` | IR files (`.wav`) shown in the CAB tab |
| `dsFile` | drive-capture copies written by older imports |
| `model` | 114 MB app-internal model blob, do not touch |

Verified behaviour: files copied straight into `ampFile` / `cabFile` do **not** appear
while the app is running, but they do appear after M-EFCS is restarted. The app keeps no
index file, so the list is a directory scan at launch. This is the fast way to load a
whole library at once instead of using `Load AMP/CAB File to List` one file at a time.

Install procedure:

1. Copy files into `ampFile` (captures) or `cabFile` (IRs).
2. Quit and reopen M-EFCS.
3. Reconnect the BlackBox in the `Connect` tab.
4. The new entries are listed in the AMP / CAB tabs with an `Audition` button each.

A backup of the library as it was before this change is kept outside the repository at
`M-EFCS-library-before-20260828-041029.tgz` in the session scratchpad. It contains
`ampFile`, `cabFile`, and `dsFile` as they were: 15 captures and 210 IRs.

## What is installed

- Captures added to `ampFile`: 24, on top of the 15 that were already there.
- IRs added to `cabFile`: 83, on top of the 210 that were already there.
- `01A_ML Sound Lab's BEST IR IN THE WORLD_Use_This_IR_as_Main_Default.wav` from the pack
  is byte-identical (SHA-256 `0cafcee0…3e4e2e`) to the file in ML Sound Lab's own free
  Dropbox giveaway, so the pack copy is the genuine IR.

### IR format, measured rather than assumed

M-VAVE's own spec line, in the Korean manual and the official product copy, is
`44.1K/24Bit mono WAV, 1024 sampling points`. That line is not literally accurate about
length: the pedal's own factory IRs measure **2048** frames, not 1024. Treat the spec as a
statement of intent, not a hard contract.

What is actually installed, measured with `wave`:

| | frames | duration | note |
| --- | ---: | ---: | --- |
| factory `2JVM_1960_57` | 2048 | 46 ms | 44.1 kHz, 24-bit, mono |
| factory `7VOX_AC30` | 2048 | 46 ms | 44.1 kHz, **32-bit float** |
| `01A ML Best IR` | 65536 | 1365 ms | **48 kHz**, 24-bit, mono |

So the pedal is demonstrably running a 32-bit float factory IR and a 48 kHz user IR, which
means it converts rather than rejects. It cannot be storing 1365 ms, so long IRs are
certainly being shortened somewhere in the upload path.

**This matters for the slot map below.** Of the 19 IRs mapped to slots, only 7 match the
vendor spec exactly. 7 are **stereo** and 5 are **48 kHz**:

- stereo: slots 2, 3, 4, 8, 9, 11, 12
- 48 kHz: slots 1, 5, 15, 16, 18
- fully conforming: slots 6, 10, 13, 14, 17, 19, 20

Slot 1 proves 48 kHz survives the trip, because it is the ML Best IR and it is what both
community sources actually play through. Stereo is the untested risk: nothing here
establishes which channel the pedal keeps, or whether it sums them. If a slot sounds thin,
phasey, or quieter than its neighbours, check this table first — a stereo source is the
prime suspect, and converting it to 44.1 kHz 24-bit mono before installing is the fix.

Because the truncation point is unknown, prefer IRs whose useful energy is early. Most of a
guitar cabinet's character lives in the first 20–50 ms, which is why the heavily truncated
ML Best IR still sounds right.

## Slot reservations

`P41 Wonderwall Live` is protected, and it references slots by number, not by file. It
uses **amp slot 1** (`1J900_CL`) and **IR slot 7** (`7VOX_AC30`). Those two slots keep
their factory contents so that P41 keeps its sound. Everything else is replaced.

## Amp slot map (20)

| Slot | File | Role |
| --- | --- | --- |
| 1 | *(reserved)* `1J900_CL` factory | P41 Wonderwall Live |
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

Left in the Mac library for auditioning, not written to a slot:
`101_OD_Friedman BE100 C45 SAT`, `108_OD_Vox_AC30_Drive`,
`021_Clean_Marshall_JCM2000_DSL`, `128_OD_Klon_Centaur`,
`137A_OD_BOSS_SD1_good_with_Rocksta_Fender_IR`.

## IR slot map (20)

Device slot names are limited to roughly 12 characters, so each slot gets a short name
that keeps the factory convention of a leading slot number.

| Slot | Device name | File | Role |
| --- | --- | --- | --- |
| 1 | `1ML_BEST_IR` **written** | `01A_ML Sound Lab's BEST IR IN THE WORLD_Use_This_IR_as_Main_Default` | default IR for everything |
| 2 | `2GTRHACK45` | `01B_GuitarHack JJ CENTRE45 0_High` | brighter general IR |
| 3 | `3RKS_CUSTOM` | `01C_Rocksta Reactions Custom Cab NT1-A A -2 1 5_Low_High_Heavy` | heavy general IR |
| 4 | `4FD_TWIN57` | `02A_Fender 1 Twin Reverb SM57 A 2 3 3 45_Rocksta` | Fender Twin |
| 5 | `5FD_DLX_C12K` | `02F_Fender 6 1966 Deluxe Reverb 1x12 Jensen C12K - SM57 - Cap Edge` | Fender Deluxe, P01 |
| 6 | `6FD_PRINCE` | `02C_Fender 3 1964 Princeton Amp_Jensen P10R-SM57` | Fender Princeton |
| 7 | *(reserved)* `7VOX_AC30` | factory IR, do not replace | P41 Wonderwall Live |
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

Factory contents being replaced, for reference if a restore is ever needed. All twenty were
later read straight out of the pedal's flash over USB MIDI SysEx and confirmed, so the
names below are the device's own, not an inference from filenames
(see [device-validation.md](../docs/reverse-engineering/device-validation.md)):

`1AC-SeVin`, `2JVM_1960_57`, `3V30_MD421`, `4G12-EVH_CT`, `5HIFI_OK`, `6WANGS212_ECM`,
`7VOX_AC30`, `8FRMAN112`, `9MeOSick-III`, then `10SoldSC412`, `11FD_TW1980`, `12MESA_412`,
`13HIW412SWF`, `14Recto_112`, `15JC120_BOX`, `16Agula410`, `17AgSVT410`, `18DgDG212N`,
`19MbSway210`, `20Tace412`. All twenty are still present as files in `cabFile`, so any slot
can be put back.

## How to write one slot in M-EFCS

Confirmed by writing IR slot 1. The same dialog is used in the AMP tab.

1. Open the `CAB` tab for IRs or the `AMP` tab for captures.
2. Type a distinctive part of the filename in `Search`. The match is a fuzzy subsequence
   match, so a long query is safer than a short one.
3. Click the row. It turns orange to show it is selected.
4. Click `Save to Device`. A dialog appears with a `name` field, a `Position` dropdown, and
   a `Save` button.
5. Set `name`. It is pre-filled with a truncation of the filename; about 12 characters fit.
6. Set `Position` to the target slot. The dropdown lists all 20 slots with their current
   contents, and defaults to slot 1.
7. Click `Save`. The dialog closes.
8. Verify by reopening `Save to Device` and reading the `Position` dropdown. It now shows
   the new name at that slot number. Reading the whole dropdown verifies all 20 slots at
   once.

## Device write log

| Date | Target | Result |
| --- | --- | --- |
| 2026-08-28 | IR slot 1: `1AC-SeVin` to `1ML_BEST_IR` | passed, verified in the `Position` dropdown |

Remaining: IR slots 2-6 and 8-20, amp slots 2-20, presets P01-P05.

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
- Firmware updates run only from a Windows PC via M-UPGRADE.
- If a helicopter-like noise appears while the device is connected to the Mac over USB,
  turn the BlackBox Bluetooth off or pair it with a phone. The noise comes from an
  unconnected Bluetooth radio.

## Sources

- petra7, BlackBox amp modeler and effects processor review (V16.8):
  <https://www.mule.co.kr/m/guide/63185935>
- petra7, BlackBox capture and IR update information:
  <https://www.mule.co.kr/m/guide/63692036>
- petra7, free IRs and M-VAVE BlackBox capture profile material:
  <https://mule.co.kr/m/muleboard/63236984>
- Capture and IR pack `ANN_Captures_IRs_V16.8.zip`, 44.3 MB, from the folder linked in
  those posts: <https://drive.google.com/drive/folders/1f9G_xo7ev32TdYt5zyP6fjiXbPGMSi8->
- ML Sound Lab, The Best IR in the World, free:
  <http://bit.ly/MLSoundLab>
- Fractal forum thread on that IR:
  <https://forum.fractalaudio.com/threads/the-best-ir-in-the-world-free.137347/>
- Soundwoofer free IR library (recommended by petra7, host was unreachable during this
  session): <https://soundwoofer.com/Library/Index>
- Official M-VAVE capture and IR sharing community, also reachable from the `Community`
  tab inside M-EFCS: <https://community.m-vave.com>
- Capture search site: <https://am2manager.fly.dev/find-capture>

The pack redistributes third-party captures and IRs collected by community members. The
ML Best IR in it is the vendor's own free giveaway; the provenance of the other files is
whatever the original uploaders provided.
