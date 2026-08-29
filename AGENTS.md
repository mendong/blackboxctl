# M-VAVE BlackBox workspace — working guide

This file is the operational guide for anyone, human or agent, about to change something
on the pedal or in its file library. It assumes you already know what the project is;
[README.md](README.md) explains that and maps the repository.

The one thing to read before anything else: **presets reference amp and IR slots by
number**, so replacing a slot silently changes every preset that points at it.

## 1. Last verified state

- **Last connection verification:** read commands worked on 2026-08-28, and the write
  migration completed on 2026-08-29. `device sync`, `device names`, `device dump` and
  `device preset N` for N = 1..80 all succeeded. Re-check endpoints before relying on the
  pedal still being connected.
- **All 80 presets have been read from flash.** The slot-exposure audit that used to be a
  precondition for the first slot write is done; the tables are in
  [presets/library.md](presets/library.md#slot-exposure-what-a-slot-write-actually-changes).
  P06–P40 are populated factory presets, not empty. P42–P80 are unused defaults, which also
  confirms the preset count is 80.
- **All 20 AMP and 20 CAB slots were migrated by `blackboxctl` on 2026-08-29.** The final
  persistent names match [presets/device-library.json](presets/device-library.json).
- **P01-P12 are the current core bank.** They were rendered from declarative specs, saved
  with rollback copies, and all twelve 92-byte flash images matched a final independent
  read. See [presets/core-bank.md](presets/core-bank.md).
- **P41 is retired, not protected.** The owner explicitly released it on 2026-08-29. Its
  old raw image remains below only as historical recovery data.
- **On the Mac, verified 2026-08-29:** 24 captures and 83 IRs installed into the M-EFCS
  library, on top of the 15 captures and 210 IRs already there, and confirmed visible after
  an app restart.
- **CLI writes are physically verified.** Reversible RAM edits, an inactive P80 save and
  restore, all 40 AMP/CAB commits, and P01-P12 saves completed. Audible validation remains
  separate from stored-state validation.

The slot maps and the write log live in [presets/library.md](presets/library.md); the
per-preset state lives in the song documents. Do not restate either here — link.

## 2. Hard rules

1. **Record a slot's current contents before overwriting it.** For a preset that is one
   read-only command: `blackboxctl device preset N`.
2. **Keep rollback assets outside the editor sandbox.** Verify the full backup before a
   write and retain the source manifest and journal.
3. **Treat the M-EFCS sandbox container as read-only** unless the task is explicitly a
   library install. It belongs to another application.
4. **Prefer reversible changes.** Keep enough information to restore what was there.
5. **Verify connection labels, installed-app state, slot contents, and parameter values
   before acting on them.** They are time-sensitive and this file may be stale.

## 3. Tone source policy

Presets are built from **community capture files plus third-party IRs**, not from the
built-in amp models and not from the factory presets. The factory presets are abandoned.

- Slot maps, install procedure, pairing rules, and sources:
  [presets/library.md](presets/library.md).
- Default IR when in doubt: `01A_ML Sound Lab's BEST IR IN THE WORLD`, IR slot 1.
- Built-in amp models remain documentation history; no slot is reserved for P41.
- Earlier built-in-model preset values are kept in each song document under a heading that
  says so. They record what was stored before the 2026-08-29 migration; they are history,
  never a current target.
- The four July 2026 documents under [docs/superpowers/](docs/superpowers/) planned the
  abandoned built-in-model presets. They are marked superseded and **must not be
  executed**, despite reading as live agentic plans with unchecked checkboxes.

## 4. Hardware and software

| | |
| --- | --- |
| Pedal | M-VAVE BlackBox, USB-C to the Mac. Last read verification: 2026-08-28; migration: 2026-08-29. |
| M-EFCS connection label | `BLACKBOX v20` — the editor's product label, not a confirmed firmware version |
| Editor | `/Applications/M-EFCS.app`, bundle id `com.digAmp.dgAmp`, Mac App Store build, version `3.5.2615` (`CFBundleVersion` `3052615`) |
| macOS audio-device label | `USB-Audio` |
| CoreMIDI identity | manufacturer `Jieli Technology`, product `USB Composite Device` |
| Capacity | 20 amp slots, 20 IR/CAB slots, both replaceable; **80 preset slots**, confirmed by read (index 79 answers, 80 refused). `P01`-`P12` are the documented core bank |
| File library | `~/Library/Containers/com.digAmp.dgAmp/Data/Documents/M-EFCS/` — `ampFile` for captures, `cabFile` for IRs |

Factory content can be restored through M-EFCS. Firmware updates and firmware recovery
belong to M-UPGRADE, not `blackboxctl`; see [docs/blackboxctl-recovery.md](docs/blackboxctl-recovery.md).

Device slot names live in a fixed 14-byte flash record: **13 usable characters including
the numeric prefix** for slots 1-9, 12 for slots 10-20.

## 5. Retired preset history: P41 `Wonderwall Live`

P41 is no longer protected. Its full 92-byte flash image was read on 2026-08-28 and is
retained here only as a historical recovery image.

```
55 00 01 05 02 04 00 03 01 01 01 00 01 01 02 00 00 03 00 06 0F 00 23 00 37 00 37
00 00 00 00 00 2D 00 46 00 28 00 3E 00 3C 00 00 00 14 00 16 00 0C 00 00 00 00 00
00 00 29 00 1E 00 1D 00 07 00 32 00 32 00 19 00 0C 00 3C 00 37 00 0F 00 00 00 4B
00 1A 00 64 00 00 00 00 00 00 00
```

Decoded:

- Total volume: `85`
- Block routing: AMP, CAB, MOD, REV, FX, DLY
- FX: `Compress`, on; Gate 15, Sustain 35, Attack 55, Level 55
- AMP: model byte `0x00` = **amp slot 1** `1J900_CL`, on; Gain 45, Level 70, Bass 40,
  Mid 62, Treble 60
- CAB: model byte `0x06` = **IR slot 7** `7VOX_AC30`, on; Level 75, Low Cut raw 26
  (93 Hz), High Cut raw 100 (18.0 kHz)
- MOD: `Chorus`, on; Speed 20, Depth 22, Mix 12
- DLY: `Dual`, **off**; Time 41, Fb 30, Mix 29, T-Mode 7, Speed 50, Depth 50
- REV: `Room`, on; Decay 25, Mix 12, HPass 60, LPass 55, Depth 15

Inspect its current replacement with `blackboxctl device preset 41`, or decode the old
hex above offline with `blackboxctl decode --hex "…"`. Restoring the old bytes would
require writing that 92-byte image with `device save`, after switching away from P41.
Source and raw bytes:
[device-validation.md](docs/reverse-engineering/device-validation.md) STEP 6c.

M-EFCS may not support separately renaming every internal preset. When a name cannot be
stored on the device, document the slot-to-name mapping in this repository.

## 6. Preset safety rules

1. Presets reference amp and IR slots **by number**. Replacing a slot changes every preset
   pointing at it. The full exposure map for all 80 presets is in
   [presets/library.md](presets/library.md#slot-exposure-what-a-slot-write-actually-changes)
   — consult it before any slot write. The 2026-08-29 migration intentionally replaced all
   40 shared slots after backing up all 80 preset images.
2. Build and audition new sounds in the user-selected slot only after inspecting and
   recording its current contents.
3. Before writing a preset, read and record the current slot, effect chain, parameter
   values, and device connection state. `python -m blackboxctl device preset N` does this
   without loading the preset.
4. Prefer reversible changes. Keep enough information to restore the previous preset.
5. After a preset write, verify the full 92-byte flash image through `blackboxctl`; after an
   AMP/CAB write, verify its persistent slot name and retain the source hash. Then verify
   the audible result through the connected guitar. M-EFCS is an optional visual cross-check,
   not the stored-state authority.

## 7. blackboxctl: controlling the device from a terminal

The GUI is no longer the only way to inspect the device. There is a CLI at
[tools/blackboxctl](tools/blackboxctl/) — no third-party Python package dependencies,
Python 3.10+, GPL-3.0, `python -m blackboxctl`. Device commands use macOS CoreMIDI, and
preparing a new AMP record needs the installed M-EFCS `libamx_parser.dylib`. Read
[tools/blackboxctl/STATUS.md](tools/blackboxctl/STATUS.md) before trusting any claim about
it; it separates what was verified on hardware from what was not.

It talks to the pedal over USB MIDI SysEx, so it does not need the GUI, does not need
screen coordinates, and cannot be derailed by another app taking focus.

Device mutations are dry runs by default and require `--yes`. Reads are allowlisted;
writes require operation-specific consent, flash requires a second capability, and no
generic arbitrary-address or firmware writer is exposed. See the CLI README for exact
rollback and verification behavior.

| Command | What it does |
| --- | --- |
| `selftest` / `doctor` | offline protocol check, then host/MIDI/M-EFCS readiness. Run `doctor` first. |
| `device endpoints` / `sync` / `dump` / `names` / `preset N` | read endpoints, the active preset id, the live preset, the 40 slot names, or stored `PNN` — decoded, without loading it |
| `inspect FILES` | validate `.am2` / `.am3Data` captures and `.wav` IRs |
| `rename FILE NAME` | edit a capture's 13-char header name; `--repair-magic` fixes an `am2converter` magic |
| `decode --hex …` | decode a 92-byte preset image offline |
| `library list` / `diff` / `install` / `restart-editor` | list files, compare `presets/library.md` to disk, copy files in, restart the GUI so it rescans |
| `backup verify` / `extract` / `extract-all` | checksum a JSON backup or write P01.bin..P80.bin |
| `device backup` / `load` / `audition` / `save` | preserve, audition, and save presets with read-back and rollback |
| `device amp …` / `device cab …` | prepare, stage, and save capture or IR slots |
| `device library-apply MANIFEST` | preflight and resume a verified 40-slot migration |
| `write-paths` | state-changing commands and their safeguards |

Caveats worth knowing before you run it:

- `library install`, `library restart-editor` and `rename --in-place` are **dry runs by
  default** and need `--yes`. `install --force` keeps a timestamped `.bak`.
- `restart-editor --yes` quits M-EFCS with an AppleScript `quit`, which discards unsaved
  GUI work. Do not run it while someone is using the app.
- The default `--library-root` is the M-EFCS sandbox container, so `library list` and
  `library diff` reach outside the repository by default.
- `library diff` finds `presets/library.md` from this checkout, or by walking up
  from the current working directory. Pass `--doc PATH` if neither layout exists.
- The `device` commands are macOS-only and need the pedal plugged in. Everything else
  works offline.

## 8. The M-EFCS file library

M-EFCS is sandboxed and scans `ampFile` and `cabFile` once at launch, keeping no index
file. That is what makes bulk installs possible:

1. Copy capture files into `ampFile` and IR `.wav` files into `cabFile`.
2. Quit and reopen M-EFCS. Files copied while it is running will not appear.
3. Reconnect the BlackBox from the `Connect` tab.
4. The entries appear in the AMP and CAB tabs, each with an `Audition` button.

This loads a whole library at once and avoids the one-file-at-a-time
`Load AMP/CAB File to List` picker. `library install` and `library restart-editor` automate
steps 1 and 2.

**Back up `ampFile`, `cabFile` and `dsFile` before adding to them**, and put the backup
somewhere that is not a temp directory. Full folder inventory, install detail and the
current backup's location: [presets/library.md](presets/library.md).

## 9. M-EFCS manual fallback

**Last-resort GUI notes, not the supported write path.** Use `blackboxctl`
whenever it can perform the operation. Coordinate clicks are historical
recovery knowledge from before the CLI could save AMP/CAB/preset slots.

`blackboxctl` now writes and auditions AMP, CAB, and preset content without the GUI.
M-EFCS remains useful for factory restore, visual comparison, and operations the CLI has
not implemented. It is a Flutter app, so its accessibility tree exposes only the window,
not its controls — there is no way to click a named button.

What works:

- `osascript -e 'tell application "System Events" to tell process "m_efcs" to get {position, size} of window 1'`
  gives the window frame in points.
- `cliclick` (`/opt/homebrew/bin/cliclick`) moves and clicks at screen coordinates, and
  types text.
- `screencapture -x -o out.png` then reading the image confirms visible GUI state. It does
  not replace CLI flash read-back or an audible check.

Rules learned the hard way:

- Always confirm M-EFCS is frontmost immediately before clicking, and refuse to click if
  it is not. A stray coordinate click lands on whatever window is in front.
- Refuse to click outside the M-EFCS window frame.
- The Mac may be in a Korean input source, in which case typed search text arrives as
  Hangul. Switch to an English input source before typing.
- Text fields do not reliably answer Cmd+A. Clear them with `kp:end` then repeated
  `kp:delete`, with a `w:70` wait between presses, or the presses get coalesced.
- Search in the AMP and CAB lists is a fuzzy subsequence match, not a substring match, so
  a long query is safer than a short one.
- Another app taking focus mid-run aborts the click guard, and a Flutter dropdown dismisses
  when focus leaves. Long unattended slot-writing runs are unreliable while other apps post
  notifications. **Write in short batches and re-verify the frontmost app before each
  batch.**
- After each batch, verify from flash with `python -m blackboxctl device names` rather than
  trusting the screenshot alone.

The step-by-step `Save to Device` dialog procedure is in
[presets/library.md](presets/library.md).

## 10. Mac monitoring path

The previously working signal path:

1. Guitar into `BlackBox IN`.
2. BlackBox connected to the Mac over USB-C.
3. GarageBand audio track input set to `USB-Audio`.
4. Enable input monitoring on the track.
5. Try input channel 1 first, then channel 2 if there is no signal.
6. Use MacBook speakers when convenient, or headphones connected directly to BlackBox when
   low latency matters.

When using the BlackBox amp/cab tone, avoid stacking an additional GarageBand amp
simulation unless that is intentional.

If a helicopter-like noise appears while the device is connected over USB, turn the
BlackBox Bluetooth off or pair it with a phone. The noise comes from an unconnected
Bluetooth radio.

## 11. Preset workflow

For each song preset:

1. Identify the musical role: rhythm/accompaniment, lead, or a section-specific sound.
2. Note the guitar and pickup position used for testing.
3. Choose the capture and the IR before the parameter values, and pair them by amp family
   where possible.
4. Propose the complete effect chain and parameter values before writing to the device.
5. Use the user-selected slot only after confirming whether its current contents may be
   overwritten, and after recording them.
6. Audition against the original track or backing track at matched loudness.
7. Adjust in this order: gain and dynamics, amp EQ, IR choice and IR level, modulation,
   delay, reverb, then output volume.
8. Record the final slot mapping and all reproducible values in this repository.

Capture-specific handling: the eight working rules for capture-based presets are in
[presets/library.md](presets/library.md#working-rules-for-capture-based-presets). The three
that catch people out most often:

- Clean captures are recorded quiet, so raise amp gain and level. Overdrive and higher-gain
  captures are recorded loud, so start near the middle.
- A capture named `IR_included`, `CabOn`, or `full rig` already has a cabinet. Turn CAB
  off, or leave it on only to reshape.
- To audition an IR, use a capture already saved on the device; to audition a capture, use
  an IR already saved on the device. If neither is saved, the first one loaded goes silent.
