# Green Day `Boulevard of Broken Dreams` — M-VAVE BlackBox Presets

## Device

- Written up: 2026-08-28 KST
- M-EFCS app: `3.5.2615` (`CFBundleVersion` `3052615`)
- Connected device label: `BLACKBOX v20`
- Guitar: HSS Strat-style guitar, bridge humbucker for both presets
- Protected preset: P41 `Wonderwall Live` — do not modify
- Slot maps and library rules: [library.md](library.md)

## Intended mapping

- P04: `Boulevard Pulse Clean` — intro and verse clean pulse
- P05: `Boulevard Chorus Crunch` — chorus rhythm

## Before overwrite

Not captured. The 2026-07-26 plan and design documents specify P04 and P05, but no
`presets/` record was ever committed for them, so it is unknown whether those built-in-model
values were actually written to the device. Inspect P04 and P05 read-only and record what
is there before writing anything.

## Target values — capture based

Written against the amp and IR slot maps in [library.md](library.md). Both slots use total
volume `85`.

### P04 — Boulevard Pulse Clean

- Pickup: bridge humbucker; guitar volume 10, tone 7-8
- FX: `Compress`; Gate 10, Sustain 30, Attack 60, Level 50; enabled
- AMP: slot 13 `004_Clean_Marshall_JTM4544_NAM`; Gain 45, Level 72, Bass 45, Mid 55, Treble 50; enabled
- CAB: slot 11 `03E_Marshall 1960VB SM57 A 0 0 0_Rocksta_center`; Level 85, Low Cut 76, High Cut 18.0K; enabled
- MOD: `Tremolo`; Speed 39, Depth 60, Level 50; enabled
- REV: `Room`; Decay 25, Mix 12, HPass 65, LPass 50, Depth 25; enabled
- DLY: disabled

Notes: Marshall capture with a Marshall 1960 IR, matching the real rig's 1960B cabinets.
It is a clean capture, so amp level starts high. The tremolo pulse must stay audible on
sustained chords without chopping the attack. There is no BPM entry on the BlackBox, so
tremolo speed has to be matched to the track by ear; 39 is only a starting point.

### P05 — Boulevard Chorus Crunch

- Pickup: bridge humbucker; guitar volume 10, tone 7-8
- FX: `Boost`; Gate 20, Gain 25; enabled
- AMP: slot 15 `125_OD_JCM800_AuditionX`; Gain 55, Level 62, Bass 45, Mid 60, Treble 52; enabled
- CAB: slot 12 `03B_Marshall JCM800 Lead Series SM57 C -5 0 1_Rocksta`; Level 80, Low Cut 76, High Cut 18.0K; enabled
- MOD: disabled
- REV: `Room`; Decay 18, Mix 8, HPass 65, LPass 45, Depth 15; enabled
- DLY: disabled

Notes: an overdrive capture, so gain and level start mid. Boost gain is 25 rather than the
35 in the built-in-model design, because the capture already carries the amp's own
saturation and stacking too much in front smears the chord changes. Mid stays forward;
this is not a scooped metal tone. If the chorus is not big enough, raise boost gain before
raising amp gain.

## Superseded — built-in amp model version

From the 2026-07-26 design document. No longer the target for P04 and P05.

### P04 — built-in

- FX: `Compress`; Gate 10, Sustain 30, Attack 60, Level 50; enabled
- AMP: `1J900_CL`; Gain 28, Level 70, Bass 45, Mid 62, Treble 55; enabled
- CAB: `2JVM_1960_57`; Level 70, Low Cut 76, High Cut 18.0K; enabled
- MOD: `Tremolo`; Speed 39, Depth 60, Level 50; enabled
- REV: `Room`; Decay 25, Mix 12, HPass 65, LPass 50, Depth 25; enabled
- DLY: disabled

### P05 — built-in

- FX: `Boost`; Gate 20, Gain 35; enabled
- AMP: `9J900_DS`; Gain 58, Level 65, Bass 45, Mid 68, Treble 57; enabled
- CAB: `2JVM_1960_57`; Level 68, Low Cut 76, High Cut 18.0K; enabled
- MOD: disabled
- REV: `Room`; Decay 18, Mix 8, HPass 65, LPass 45, Depth 15; enabled
- DLY: disabled

## Verification

- Library install: passed. The captures and IRs named above are present in the M-EFCS AMP
  and CAB lists after an app restart.
- Read-only inspection of the current P04 and P05: not done yet.
- Amp and IR slot writes: not done yet.
- Preset writes for P04 and P05: not done yet.
- Player listening check: not done yet.
