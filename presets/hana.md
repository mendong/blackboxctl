# Fujii Kaze `Hana` — M-VAVE BlackBox Presets

## Device

- Captured: 2026-07-20 KST, revised to capture-based presets 2026-08-28 KST
- M-EFCS app: `3.5.2615` (`CFBundleVersion` `3052615`)
- Last observed connection label: `BLACKBOX v20` (2026-08-29). Re-check endpoints before
  assuming the pedal is still connected.
- Guitar: HSS Strat-style guitar
- P41 was retired by the owner on 2026-08-29; it is no longer protected
- Slot maps and library rules: [library.md](library.md)

## Recorded device state after the 2026-08-29 migration

The capture-based P01, P02 and P03 below were written by `blackboxctl` on 2026-08-29.
Each 92-byte image was built from the pre-write backup, saved to its inactive slot, and
read back byte-for-byte. The older built-in-model section is retained as history.

All three capture-based images were confirmed by the final 2026-08-29 flash read. The
following earlier evidence is a **pre-migration snapshot**: P01 and P03 were read on
2026-08-28, and P02 was read later the same day. That old P02 image pointed at amp slot 4
`4BLUE_OD` and IR slot 7 `7VOX_AC30`, matching the July record.

The 2026-08-28 slot-sharing audit remains useful historical evidence, but every AMP/CAB
slot was intentionally reassigned on 2026-08-29.

To check any of this without loading a preset:

```sh
cd tools/blackboxctl
python -m blackboxctl device preset 1   # and 2, 3
```

## Historical record — state before the 2026-07-20 overwrite

This is what P01-P03 held **before** the July built-in-model session. It is history, not a
restore point and not a description of the device today.

It is also no longer directly restorable: P01's cab here is `1AC-SeVin`, which is IR
slot 1, and IR slot 1 was overwritten with `1ML_BEST_IR` on 2026-08-28. Reloading these
values would give P01 the ML Best IR, not the factory AC-SeVin. Restoring the recorded
chain would require putting `cabFile/1AC-SeVin.wav` back into IR slot 1 first.

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

## Target values — capture based, written 2026-08-29

These are the design targets now stored on the device. They use amp slots 2, 12 and 20
and IR slots 5, 8 and 19 from the new library.

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

## Historical snapshot — built-in-amp-model version before 2026-08-29

**Superseded and no longer stored.** These values were written on 2026-07-20 from the
built-in amp models and were still present when read on 2026-08-28. The capture-based
images above replaced them on 2026-08-29. This section remains as pre-migration evidence.

Corroborated on 2026-08-28 by reading flash over USB MIDI SysEx, read-only. P01 (flash
index 0) and P03 (flash index 2) decoded field for field to the values below, including the
model-byte-to-slot mapping.

The two CAB Low Cut figures need one caveat, and it is the same caveat everywhere it
appears. The display mapping is `Hz = 20 + (raw/100) * 280`
([protocol-spec.md](../docs/reverse-engineering/protocol-spec.md) §4.3), so the stored raw
24 in P01 is exactly **87.2 Hz** and the stored raw 22 in P03 is exactly **81.6 Hz**. The
figures below, 87 and 81, were read off the M-EFCS GUI. Both reproduce if the display
truncates toward zero; under round-half-up P03 would read 82. Truncation is therefore what
both records are consistent with, but that convention is inferred from these two samples
and is documented nowhere upstream — so these two fields agree **to within one display
step**, not bit-exactly. Every other field is an exact integer match. See
[device-validation.md](../docs/reverse-engineering/device-validation.md) STEP 6a and 6b.
P02 was not read in the first session, but a second read-only session on 2026-08-28 closed
that gap and matched the July GUI record.

At that snapshot, P01 used amp slot 2 and IR slot 11; P03 used amp slot 3 and IR slot 5.
The 2026-08-29 migration later reassigned those shared slots and rewrote all three presets.

### P01 — built-in (confirmed present in flash, 2026-08-28)

- FX: `Compress`; Gate 5, Sustain 35, Attack 55, Level 50; enabled
- AMP: `2FD_CL`; Gain 25, Level 70, Bass 45, Mid 55, Treble 47; enabled
- CAB: `11FD_TW1980`; Level 70, Low Cut 87, High Cut 18.0K; enabled
- MOD: `Chorus`; Speed 20, Depth 20, Mix 10; enabled
- REV: `Room`; Decay 28, Mix 20, HPass 60, LPass 45, Depth 45; enabled
- DLY: `Dual`; Time 18, Fb 6, Mix 6, Grit 0, Speed 0, Depth 0; enabled

### P02 — built-in (confirmed in the second 2026-08-28 read session)

- FX: `Compress`; Gate 15, Sustain 35, Attack 60, Level 50; enabled
- AMP: `4BLUE_OD`; Gain 38, Level 70, Bass 42, Mid 58, Treble 50; enabled
- CAB: `7VOX_AC30`; Level 70, Low Cut 78, High Cut 18.0K; enabled
- MOD: `Chorus`; Speed 60, Depth 50, Mix 72; disabled
- REV: `Hall`; Decay 29, Mix 12, HPass 80, LPass 80, Depth 40; enabled
- DLY: `Analog`; Time 30, Fb 15, Mix 8, Phaser 0, Pitch 0; enabled

### P03 — built-in (confirmed present in flash, 2026-08-28)

- FX: `Compress`; Gate 21, Sustain 53, Attack 58, Level 50; enabled
- AMP: `3JC120_CL`; Gain 23, Level 67, Bass 43, Mid 46, Treble 62; enabled
- CAB: `5HIFI_OK`; Level 68, Low Cut 81, High Cut 18.0K; enabled
- MOD: `Chorus`; Speed 60, Depth 50, Mix 72; disabled
- REV: `Hall`; Decay 10, Mix 15, HPass 48, LPass 49, Depth 30; enabled
- DLY: `Dual`; Time 84, Fb 47, Mix 15, Grit 0, Speed 0, Depth 0; disabled

## Verification

Built-in-model version, 2026-07-20 — historical verification before replacement:

- Device write: passed; M-EFCS displayed `Success!` after saving P01, P02, and P03.
- Persistence: passed; each slot was switched away from and re-opened, and the values
  remained stored.
- Independent confirmation, 2026-08-28: P01 and P03 read back in the first session; P02
  read back in the second. They matched the recorded values subject to the two Low Cut
  display-step caveats above.
- P41 safety: passed. Confirmed again on 2026-08-28 by decoding P41 from flash: amp model
  byte `0x00` (amp slot 1) and CAB model byte `0x06` (IR slot 7), both untouched.
- Player listening check: never completed.

Capture-based version — **written and byte-verified 2026-08-29**:

- Library install: passed. The captures and IRs named above are present in the M-EFCS
  AMP and CAB lists after an app restart, verified by searching the lists, and
  `python -m blackboxctl library diff` resolves every one of them to a file on disk.
- Amp and IR slot writes: done; the full 20+20 name tables match
  [`device-library.json`](device-library.json).
- Preset writes for P01-P03: done; every 92-byte read-back matched its rendered image.
- Player listening check: not done.

The remaining check needs the guitar, a listener, and a fresh connection check; it is not
proved by another stored-state read.
