# Green Day `Boulevard of Broken Dreams` — M-VAVE BlackBox Presets

## Device

- Built-in-model version written to the device 2026-07-26 KST; revised to capture-based
  targets 2026-08-28 KST
- M-EFCS app: `3.5.2615` (`CFBundleVersion` `3052615`)
- Connected device label: `BLACKBOX v20`. The pedal is currently unplugged.
- Guitar: HSS Strat-style guitar, bridge humbucker for both presets
- Protected preset: P41 `Wonderwall Live` — do not modify
- Slot maps and library rules: [library.md](library.md)

## What is on the device right now

**None of the capture-based targets below has been written.** As far as the record goes,
P04 and P05 still hold the built-in-amp-model values written on 2026-07-26 and recorded
under [Written on 2026-07-26](#written-on-2026-07-26--built-in-amp-model-version-superseded-as-a-target).

That is a record of a GUI session, not a read-back. Unlike Hana's P01 and P03, **P04 and
P05 have never been read out of flash**, so nothing independently confirms what is stored.
Reading them is now a two-command, read-only operation that does not load the preset:

```sh
cd tools/blackboxctl
python -m blackboxctl device preset 4
python -m blackboxctl device preset 5
```

Do that before writing anything.

## Before overwrite

**Never captured, deliberately.** The 2026-07-26 session recorded: "The user selected P04
and P05 and explicitly requested that no restoration backup be created. Both slots and
their selected identities were inspected before editing, but their prior values were not
retained as a backup." The pre-July-2026 contents of P04 and P05 are therefore gone.

## Intended mapping

- P04: `Boulevard Pulse Clean` — intro and verse clean pulse
- P05: `Boulevard Chorus Crunch` — chorus rhythm

## Target values — capture based, not yet written

These are the design targets. **Neither is on the device.** They depend on amp slots 13
and 15 and IR slots 11 and 12, none of which has been written either.

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

## Written on 2026-07-26 — built-in amp model version, superseded as a target

**Superseded as a target; still, on the record, what the pedal holds.** These were written
through M-EFCS on 2026-07-26 from the
[design document](../docs/superpowers/specs/2026-07-26-greenday-boulevard-blackbox-presets-design.md)
and its [plan](../docs/superpowers/plans/2026-07-26-greenday-boulevard-blackbox-presets.md),
both now superseded. The values and the write result below are recovered from commit
`da7aee9` (2026-07-26), whose version of this file was replaced by the capture-based
rewrite in `27b2042` and would otherwise have been lost.

They are no longer the target for P04 and P05. Unlike Hana's P01 and P03 they have never
been read back from flash, so the only evidence for them is that July GUI session.

Slot references, which matter because those slots are scheduled to be rewritten: P04 uses
amp slot 1 and IR slot 2; P05 uses amp slot 9 and IR slot 2. IR slot 2 is scheduled to
become `2GTRHACK45`. Amp slot 1 is reserved for P41 and will not change.

### P04 — built-in, as written 2026-07-26

- FX: `Compress`; Gate 10, Sustain 30, Attack 60, Level 50; enabled
- AMP: `1J900_CL` (amp slot 1); Gain 28, Level 70, Bass 45, Mid 62, Treble 55; enabled
- CAB: `2JVM_1960_57` (IR slot 2); Level 70, Low Cut 76, High Cut 18.0K; enabled
- MOD: `Tremolo`; Speed 39, Depth 60, Level 50; enabled
- REV: `Room`; Decay 25, Mix 12, HPass 65, LPass 50, Depth 25; enabled
- DLY: `Dual`; Time 84, Fb 49, Mix 20, Grit 0, Speed 0, Depth 0; disabled

### P05 — built-in, as written 2026-07-26

- FX: `Boost`; Gate 20, Gain 35; enabled
- AMP: `9J900_DS` (amp slot 9); Gain 58, Level 65, Bass 45, Mid 68, Treble 57; enabled
- CAB: `2JVM_1960_57` (IR slot 2); Level 68, Low Cut 76, High Cut 18.0K; enabled
- MOD: `Chorus`; Speed 60, Depth 50, Mix 72; disabled
- REV: `Room`; Decay 18, Mix 8, HPass 65, LPass 45, Depth 15; enabled
- DLY: `Dual`; Time 61, Fb 42, Mix 18, Grit 7, Speed 50, Depth 50; disabled

## Verification

Built-in-model version, 2026-07-26 — the version that should be on the device:

- Device write: passed. M-EFCS displayed `Success!` after saving P04 and P05.
- P04 persistence: passed. After switching to P05 and re-opening P04, every model, visible
  value, effect state, and total volume matched.
- P05 persistence: passed, by the same method.
- P41 safety: passed by read-only inspection. It read total volume 85, `1J900_CL` Gain 45,
  `7VOX_AC30`, Chorus Mix 12, Room Mix 12, Dual delay disabled — all of which the
  2026-08-28 flash decode later reproduced.
- P01-P03 safety: no edit or save action was performed on those slots.
- Independent confirmation by flash read: **not done.** P04 and P05 were not among the
  slots read on 2026-08-28.
- Player listening check: never completed.

Capture-based version — **nothing written**:

- Library install: passed. The captures and IRs named above are present in the M-EFCS AMP
  and CAB lists after an app restart, and `python -m blackboxctl library diff` resolves
  every one of them to a file on disk.
- Read-only inspection of the current P04 and P05: **not done.** Use
  `python -m blackboxctl device preset 4` and `... 5`.
- Amp and IR slot writes: **not done.** Only IR slot 1 has ever been written on this
  pedal. Amp slots 13 and 15 and IR slots 11 and 12 still hold their factory contents,
  confirmed by the 2026-08-28 flash read of both name tables.
- Preset writes for P04 and P05 in their capture-based form: **not done.**
- P41 safety: confirmed again on 2026-08-28 by decoding P41 from flash — amp model byte
  `0x00` (amp slot 1) and CAB model byte `0x06` (IR slot 7), both untouched.
- Player listening check: not done.

### Listening check, still pending from July

Play P04 and P05 at matched loudness with the bridge humbucker:

1. If the P04 pulse is too slow or fast, adjust Tremolo Speed first.
2. If P04 chops too deeply, reduce Tremolo Depth from 60 in steps of 5.
3. If P05 is fizzy, reduce Treble before reducing Mid.
4. If P05 is too saturated, reduce AMP Gain before disabling Boost.
5. Adjust output Level only after the gain and EQ feel correct.

The pedal is currently unplugged, so none of the remaining steps can proceed.
