# Fujii Kaze `Hana` — M-VAVE BlackBox Presets

## Device

- Captured: 2026-07-20 KST, revised to capture-based presets 2026-08-28 KST
- M-EFCS app: `3.5.2615` (`CFBundleVersion` `3052615`)
- Connected device label: `BLACKBOX v20`
- Guitar: HSS Strat-style guitar
- Protected preset: P41 `Wonderwall Live` — do not modify
- Slot maps and library rules: [library.md](library.md)

## Before overwrite

All three slots had total volume `85`. Enabled/disabled states below are based on the visible colored/gray block state in M-EFCS.

### P01

- FX: `Compress`; Gate 50, Sustain 55, Attack 67, Level 50; disabled
- AMP: `12FRIMAN`; Gain 75, Level 70, Bass 50, Mid 50, Treble 50; enabled
- CAB: `1AC-SeVin`; Level 80, Low Cut 76, High Cut 18.0K; enabled
- MOD: `Chorus`; Speed 60, Depth 50, Mix 72; disabled
- REV: `Room`; Decay 23, Mix 14, HPass 66, LPass 53, Depth 66; enabled
- DLY: `Dual`; Time 41, Fb 30, Mix 29, Grit 7, Speed 50, Depth 50; enabled

### P02

- FX: `Compress`; Gate 50, Sustain 55, Attack 67, Level 50; enabled
- AMP: `5RAT_OD`; Gain 73, Level 60, Bass 51, Mid 60, Treble 72; enabled
- CAB: `2JVM_1960_57`; Level 66, Low Cut 76, High Cut 18.0K; enabled
- MOD: `Chorus`; Speed 60, Depth 50, Mix 72; disabled
- REV: `Hall`; Decay 40, Mix 9, HPass 80, LPass 80, Depth 40; enabled
- DLY: `Analog`; Time 43, Fb 36, Mix 8, Phaser 0, Pitch 0; enabled

### P03

- FX: `Compress`; Gate 50, Sustain 55, Attack 67, Level 50; disabled
- AMP: `6M-VAVE_OD`; Gain 78, Level 60, Bass 49, Mid 68, Treble 66; enabled
- CAB: `2JVM_1960_57`; Level 64, Low Cut 76, High Cut 18.0K; enabled
- MOD: `Chorus`; Speed 60, Depth 50, Mix 72; disabled
- REV: `Hall`; Decay 10, Mix 9, HPass 48, LPass 49, Depth 30; enabled
- DLY: `Dual`; Time 84, Fb 47, Mix 15, Grit 0, Speed 0, Depth 0; enabled

## Intended mapping

- P01: `Hana Warm Clean` — neck single-coil
- P02: `Hana Edge` — neck single-coil
- P03: `Hana Acoustic Clean` — neck+middle or middle single-coil

## Target values — capture based

Written against the amp and IR slot maps in [library.md](library.md). All slots use total
volume `85`. Amp EQ values are starting points; the amp block still applies EQ on top of a
capture.

### P01 — Hana Warm Clean

- Pickup: neck single-coil; guitar tone starting point 7-8
- FX: `Compress`; Gate 5, Sustain 35, Attack 55, Level 50; enabled
- AMP: slot 2 `014B_Clean_Fender_65_Deluxe_Reverb`; Gain 45, Level 75, Bass 45, Mid 20, Treble 45; enabled
- CAB: slot 5 `02F_Fender 1966 Deluxe Reverb Jensen C12K SM57 Cap Edge`; Level 85, Low Cut 87, High Cut 18.0K; enabled
- MOD: `Chorus`; Speed 20, Depth 20, Mix 10; enabled
- REV: `Room`; Decay 28, Mix 20, HPass 60, LPass 45, Depth 45; enabled
- DLY: `Dual`; Time 18, Fb 6, Mix 6, Grit 0, Speed 0, Depth 0; enabled

Notes: Fender capture with a Fender cab IR, per the family-pairing rule. Amp level starts
high because clean captures are recorded quiet. Mid sits at 20 to stop the mid-forward IR
family from making Strat clean chords feel stiff. If it turns dull instead, walk mid back
up toward 45 before touching treble. Alternative CAB: slot 1 ML Best IR.

### P02 — Hana Edge

- Pickup: neck single-coil; guitar tone starting point 7-8
- FX: `Compress`; Gate 15, Sustain 30, Attack 60, Level 50; enabled
- AMP: slot 12 `109_OD_Vox_AC30_Crunch`; Gain 40, Level 60, Bass 42, Mid 45, Treble 48; enabled
- CAB: slot 8 `04D_Vox AC30 1966 Top Boost e906 Tone junkie`; Level 80, Low Cut 78, High Cut 18.0K; enabled
- MOD: `Chorus`; Speed 60, Depth 50, Mix 72; disabled
- REV: `Hall`; Decay 29, Mix 12, HPass 80, LPass 80, Depth 40; enabled
- DLY: `Analog`; Time 30, Fb 15, Mix 8, Phaser 0, Pitch 0; enabled

Notes: an overdrive capture, so gain and level start mid rather than high. Target is clean
under light picking with grit only on accents. If it breaks up too early, drop amp gain
before dropping level, so the preset stays level-matched with P01.

### P03 — Hana Acoustic Clean

- Pickup: neck+middle or middle single-coil; guitar tone starting point 7-8
- FX: `Compress`; Gate 20, Sustain 50, Attack 58, Level 50; enabled
- AMP: slot 20 `501_Acoustic_G_Preamp_noCAB`; Gain 50, Level 70, Bass 45, Mid 40, Treble 55; enabled
- CAB: slot 19 `102_Acoustic_G_IR_Martin_D35SA`; Level 85, Low Cut 60, High Cut 18.0K; enabled
- MOD: `Chorus`; Speed 60, Depth 50, Mix 72; disabled
- REV: `Hall`; Decay 25, Mix 15, HPass 55, LPass 60, Depth 35; enabled
- DLY: `Dual`; Time 84, Fb 47, Mix 15, Grit 0, Speed 0, Depth 0; disabled

Notes: this replaces the earlier substitution that faked an acoustic tone with
`3JC120_CL` plus `5HIFI_OK`. The acoustic preamp capture is explicitly meant to be paired
with one of the acoustic IRs, so the pairing is now the intended one rather than a
workaround. Low Cut is lower than on the electric presets because an acoustic simulation
needs its body resonance. Alternative CAB: slot 20 Taylor 414.

## Superseded — built-in amp model version

Kept for reference. These were the values before the move to capture files. They are no
longer the target for P01-P03.

### P01 — built-in

- FX: `Compress`; Gate 5, Sustain 35, Attack 55, Level 50; enabled
- AMP: `2FD_CL`; Gain 25, Level 70, Bass 45, Mid 55, Treble 47; enabled
- CAB: `11FD_TW1980`; Level 70, Low Cut 87, High Cut 18.0K; enabled
- MOD: `Chorus`; Speed 20, Depth 20, Mix 10; enabled
- REV: `Room`; Decay 28, Mix 20, HPass 60, LPass 45, Depth 45; enabled
- DLY: `Dual`; Time 18, Fb 6, Mix 6, Grit 0, Speed 0, Depth 0; enabled

### P02 — built-in

- FX: `Compress`; Gate 15, Sustain 35, Attack 60, Level 50; enabled
- AMP: `4BLUE_OD`; Gain 38, Level 70, Bass 42, Mid 58, Treble 50; enabled
- CAB: `7VOX_AC30`; Level 70, Low Cut 78, High Cut 18.0K; enabled
- MOD: `Chorus`; Speed 60, Depth 50, Mix 72; disabled
- REV: `Hall`; Decay 29, Mix 12, HPass 80, LPass 80, Depth 40; enabled
- DLY: `Analog`; Time 30, Fb 15, Mix 8, Phaser 0, Pitch 0; enabled

### P03 — built-in

- FX: `Compress`; Gate 21, Sustain 53, Attack 58, Level 50; enabled
- AMP: `3JC120_CL`; Gain 23, Level 67, Bass 43, Mid 46, Treble 62; enabled
- CAB: `5HIFI_OK`; Level 68, Low Cut 81, High Cut 18.0K; enabled
- MOD: `Chorus`; Speed 60, Depth 50, Mix 72; disabled
- REV: `Hall`; Decay 10, Mix 15, HPass 48, LPass 49, Depth 30; enabled
- DLY: `Dual`; Time 84, Fb 47, Mix 15, Grit 0, Speed 0, Depth 0; disabled

## Verification

Built-in-model version, 2026-07-20:

- Device write: passed; M-EFCS displayed `Success!` after saving P01, P02, and P03.
- Persistence: passed; each slot was switched away from and re-opened, and the values
  remained stored.
- P41 safety: passed by read-only inspection.
- Player listening check: never completed.

Capture-based version, 2026-08-28:

- Library install: passed. The captures and IRs named above are present in the M-EFCS
  AMP and CAB lists after an app restart, verified by searching the lists.
- Amp and IR slot writes: not done yet.
- Preset writes for P01-P03: not done yet.
- Player listening check: not done yet.
