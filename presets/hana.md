# Fujii Kaze `Hana` — M-VAVE BlackBox Presets

## Device

- Captured: 2026-07-20 KST
- M-EFCS app: `3.5.2615` (`CFBundleVersion` `3052615`)
- Connected device label: `BLACKBOX v20`
- Guitar: HSS Strat-style guitar
- Protected preset: P41 `Wonderwall Live` — do not modify

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

## Final values

All slots use total volume `85`.

### P01 — Hana Warm Clean

- Pickup: neck single-coil; guitar tone starting point 7-8
- FX: `Compress`; Gate 5, Sustain 35, Attack 55, Level 50; enabled
- AMP: `2FD_CL`; Gain 25, Level 70, Bass 45, Mid 55, Treble 47; enabled
- CAB: `11FD_TW1980`; Level 70, Low Cut 87, High Cut 18.0K; enabled
- MOD: `Chorus`; Speed 20, Depth 20, Mix 10; enabled
- REV: `Room`; Decay 28, Mix 20, HPass 60, LPass 45, Depth 45; enabled
- DLY: `Dual`; Time 18, Fb 6, Mix 6, Grit 0, Speed 0, Depth 0; enabled

### P02 — Hana Edge

- Pickup: neck single-coil; guitar tone starting point 7-8
- FX: `Compress`; Gate 15, Sustain 35, Attack 60, Level 50; enabled
- AMP: `4BLUE_OD`; Gain 38, Level 70, Bass 42, Mid 58, Treble 50; enabled
- CAB: `7VOX_AC30`; Level 70, Low Cut 78, High Cut 18.0K; enabled
- MOD: `Chorus`; Speed 60, Depth 50, Mix 72; disabled
- REV: `Hall`; Decay 29, Mix 12, HPass 80, LPass 80, Depth 40; enabled
- DLY: `Analog`; Time 30, Fb 15, Mix 8, Phaser 0, Pitch 0; enabled

### P03 — Hana Acoustic Clean

- Pickup: neck+middle or middle single-coil; guitar tone starting point 7-8
- Substitution: no acoustic simulator was present, so `3JC120_CL` and `5HIFI_OK` provide the neutral clean path.
- FX: `Compress`; Gate 21, Sustain 53, Attack 58, Level 50; enabled
- AMP: `3JC120_CL`; Gain 23, Level 67, Bass 43, Mid 46, Treble 62; enabled
- CAB: `5HIFI_OK`; Level 68, Low Cut 81, High Cut 18.0K; enabled
- MOD: `Chorus`; Speed 60, Depth 50, Mix 72; disabled
- REV: `Hall`; Decay 10, Mix 15, HPass 48, LPass 49, Depth 30; enabled
- DLY: `Dual`; Time 84, Fb 47, Mix 15, Grit 0, Speed 0, Depth 0; disabled

## Verification

- Device write: passed; M-EFCS displayed `Success!` after saving P01, P02, and P03.
- Persistence: passed; each slot was switched away from and re-opened, and the values above remained stored.
- P41 safety: passed by read-only inspection. It still showed total volume 85, `1J900_CL` Gain 45, `7VOX_AC30`, Chorus Mix 12, Room Mix 12, and disabled Dual delay.
- Output level: all three slots are set to total volume 85, but perceived loudness still needs an instrument listening check.
- Player listening check: pending. Compare the three presets against `Hana` with the connected HSS Strat and adjust only after hearing the actual guitar/pickup output.
