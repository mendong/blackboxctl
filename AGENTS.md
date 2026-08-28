# M-VAVE BlackBox Workspace Guide

## Purpose

This workspace is for designing, documenting, and validating guitar presets for the user's connected M-VAVE BlackBox.

## Tone Source Policy

Presets are built from **community capture files plus third-party IRs**, not from the
built-in amp models and not from the factory presets. The factory presets are abandoned.

- Slot maps, install procedure, pairing rules, and sources: [presets/library.md](presets/library.md)
- Default IR when in doubt: `01A_ML Sound Lab's BEST IR IN THE WORLD` in IR slot 1.
- Built-in amp models may still be referenced, but only for the reserved slots that the
  protected P41 preset depends on.
- Earlier built-in-model preset values are kept in each song document under a
  `Superseded` heading. Do not treat them as targets.

## Known Hardware and Software

- Device: M-VAVE BlackBox
- M-EFCS connection label previously observed: `BLACKBOX v20`
- Preset editor: `/Applications/M-EFCS.app`, bundle id `com.digAmp.dgAmp`, Mac App Store build
- M-EFCS version last observed: `3.5.2615` (`CFBundleVersion` `3052615`)
- macOS audio-device label previously observed: `USB-Audio`
- Device capacity: 20 amp slots, 20 IR/CAB slots, both replaceable. Factory amp models can be restored from the PC version of M-EFCS.
- Sandboxed file library: `~/Library/Containers/com.digAmp.dgAmp/Data/Documents/M-EFCS/` with `ampFile` for captures and `cabFile` for IRs.
- Treat connection labels, installed-app state, preset slots, and current parameter values as time-sensitive. Verify them before changing the device.

## Loading a Capture or IR Library

M-EFCS scans `ampFile` and `cabFile` once at launch and keeps no index file. So:

1. Copy capture files into `ampFile` and IR `.wav` files into `cabFile`.
2. Quit and reopen M-EFCS. Files copied while it is running will not appear.
3. Reconnect the BlackBox from the `Connect` tab.
4. The entries appear in the AMP and CAB tabs, each with an `Audition` button.

This loads a whole library at once and avoids the one-file-at-a-time `Load AMP/CAB File to List` picker.

Back up `ampFile`, `cabFile`, and `dsFile` before adding to them.

## Existing Known-Good Preset

Preserve the existing preset:

- Slot: `P41`
- Working name: `Wonderwall Live`
- Amp: `J900_CL`
- Amp gain: `45`
- Cab: `VOX_AC30`
- Chorus mix: `12`
- Room reverb mix: `12`
- Delay: off
- Total volume: `85`

M-EFCS may not support separately renaming every internal preset. When a name cannot be stored on the device, document the slot-to-name mapping in this repository.

## Preset Safety Rules

1. Never overwrite `P41` unless the user explicitly requests it.
2. Presets reference amp and IR slots **by number**, so replacing a slot changes every
   preset that points at it. `P41` uses **amp slot 1** (`1J900_CL`) and **IR slot 7**
   (`7VOX_AC30`). Keep those two slots at their factory contents while `P41` is protected.
3. Build and audition new sounds in the user-selected slot only after inspecting and recording its current contents.
4. Before writing a preset, read and record the current slot, effect chain, parameter values, and device connection state.
5. Prefer reversible changes. Keep enough information to restore the previous preset.
6. After writing, verify both the saved parameter values in M-EFCS and the audible result through the connected guitar.

## blackboxctl: the CLI

The M-EFCS GUI is no longer the only way to work with the device. There is a CLI at
[tools/blackboxctl](tools/blackboxctl/) — no dependencies, GPL-3.0, `python -m blackboxctl`.
Read [tools/blackboxctl/STATUS.md](tools/blackboxctl/STATUS.md) before trusting any claim
about it; it separates what was verified on hardware from what was not.

It talks to the pedal over USB MIDI SysEx, so it does not need the GUI, does not need
screen coordinates, and cannot be derailed by another app taking focus.

**Device commands are read only and cannot be made otherwise.** No write path is enabled;
`python -m blackboxctl write-paths` shows each state-changing command and the exact
evidence for why it is disabled. Nothing has ever been written to this pedal.

| Command | What it does |
| --- | --- |
| `selftest` | offline protocol check; touches nothing. Run it first. |
| `device endpoints` / `sync` / `dump` / `names` / `preset N` | read endpoints, the active preset id, the live preset, the 40 slot names, or stored `PNN` — decoded, without loading it |
| `inspect FILES` | validate `.am2` / `.am3Data` captures and `.wav` IRs |
| `rename FILE NAME` | edit a capture's 13-char header name; `--repair-magic` fixes an `am2converter` magic |
| `decode --hex …` | decode a 92-byte preset image offline |
| `library list` / `diff` / `install` / `restart-editor` | list files, compare `presets/library.md` to disk, copy files in, restart the GUI so it rescans |

`library install`, `library restart-editor` and `rename --in-place` are **dry runs by
default** and need `--yes`. `install --force` keeps a timestamped `.bak`.
`restart-editor --yes` quits M-EFCS with an AppleScript `quit`, which discards unsaved GUI
work — do not run it while someone is using the app.

Reading a preset with the CLI is now the fastest way to satisfy Preset Safety Rule 4
(record the current slot contents before writing). `device preset 41` dumps P41 without
loading it.

## Driving M-EFCS from a Session

Still needed for anything the CLI cannot do: writing presets, and auditioning captures and
IRs. M-EFCS is a Flutter app, so its accessibility tree exposes only the window, not its
controls. There is no way to click a named button. What works:

- `osascript -e 'tell application "System Events" to tell process "m_efcs" to get {position, size} of window 1'` gives the window frame in points.
- `cliclick` (`/opt/homebrew/bin/cliclick`) moves and clicks at screen coordinates, and types text.
- `screencapture -x -o out.png` then reading the image is the only way to confirm what happened. Verify after every step.

Rules learned the hard way:

- Always confirm M-EFCS is frontmost immediately before clicking, and refuse to click if
  it is not. A stray coordinate click lands on whatever window is in front.
- Refuse to click outside the M-EFCS window frame.
- The Mac may be in a Korean input source, in which case typed search text arrives as
  Hangul. Switch to an English input source before typing.
- Text fields do not reliably answer Cmd+A. Clear them with `kp:end` then repeated
  `kp:delete`, with a `w:70` wait between presses, or the presses get coalesced.
- Search in the AMP and CAB lists is a fuzzy subsequence match, not a substring match.

## Mac Monitoring Path

The previously working signal path was:

1. Guitar into `BlackBox IN`.
2. BlackBox connected to the Mac over USB-C.
3. GarageBand audio track input set to `USB-Audio`.
4. Enable input monitoring on the track.
5. Try input channel 1 first, then channel 2 if there is no signal.
6. Use MacBook speakers when convenient, or headphones connected directly to BlackBox when low latency matters.

When using the BlackBox amp/cab tone, avoid stacking an additional GarageBand amp simulation unless that is intentional.

## Preset Workflow

For each song preset:

1. Identify the musical role: rhythm/accompaniment, lead, or a section-specific sound.
2. Note the guitar and pickup position used for testing.
3. Choose the capture and the IR before the parameter values, and pair them by amp family where possible.
4. Propose the complete effect chain and parameter values before writing to the device.
5. Use the user-selected slot only after confirming whether its current contents may be overwritten.
6. Audition against the original track or backing track at matched loudness.
7. Adjust in this order: gain and dynamics, amp EQ, IR choice and IR level, modulation, delay, reverb, then output volume.
8. Record the final slot mapping and all reproducible values in this repository.

Capture-specific handling:

- Clean captures are recorded quiet; raise amp gain and level. Overdrive and higher-gain captures are recorded loud; start near the middle.
- A capture named `IR_included`, `CabOn`, or `full rig` already has a cabinet. Turn CAB off, or leave it on only to reshape.
- To audition an IR, use a capture already saved on the device. To audition a capture, use an IR already saved on the device. If neither is saved, the first one loaded goes silent.

## Current State

- P01-P03: `Hana` presets. Capture-based targets defined in [presets/hana.md](presets/hana.md); device not yet rewritten.
- P04-P05: `Boulevard of Broken Dreams` presets. Capture-based targets defined in [presets/boulevard-of-broken-dreams.md](presets/boulevard-of-broken-dreams.md); current device contents not yet inspected.
- P41: protected `Wonderwall Live`.
- Library: 24 captures and 83 IRs installed and confirmed visible in M-EFCS.
- IR slot 1 is written and verified: `1AC-SeVin` replaced by `1ML_BEST_IR`. IR slots 2-6 and 8-20, amp slots 2-20, and all five preset writes are still pending.

## Known Obstacle to Long GUI Runs

Another app taking focus mid-run aborts the click guard, and a Flutter dropdown dismisses
when focus leaves. Long unattended slot-writing runs are unreliable while other apps post
notifications. Write in short batches and re-verify the frontmost app before each batch.
