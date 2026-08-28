# M-VAVE BlackBox workspace — working guide

This file is the operational guide for anyone, human or agent, about to change something
on the pedal or in its file library. It assumes you already know what the project is;
[README.md](README.md) explains that and maps the repository.

The one thing to read before anything else: **presets reference amp and IR slots by
number**, so replacing a slot silently changes every preset that points at it.

## 1. Current state

- **The pedal is unplugged.** Every device command, read or write, is blocked on plugging
  it back in.
- **Exactly one amp or IR slot has ever been written by this project.** On 2026-08-28,
  through the M-EFCS GUI, IR slot 1 went from the factory `1AC-SeVin` to `1ML_BEST_IR`.
  Confirmed twice: in the GUI `Position` dropdown, and later by reading the IR name table
  out of flash. Five *preset* slots were also written, earlier and through the same GUI —
  see the bullet below.
- **Pending, designed but not written:** amp slots 2-20, IR slots 2-6 and 8-20, and the
  capture-based versions of presets P01-P05. Amp slot 1 and IR slot 7 stay factory
  because P41 points at them.
- **Presets currently on the device:** P01-P03 hold the built-in-amp-model values written
  on 2026-07-20; P01 and P03 were confirmed by flash read on 2026-08-28, P02 was not.
  P04-P05 hold the built-in-model values written on 2026-07-26, never confirmed by a
  read-back. P06-P40 have never been read by anyone here. P41 is protected.
- **On the Mac:** 24 captures and 83 IRs installed into the M-EFCS library, on top of the
  15 captures and 210 IRs already there, and confirmed visible after an app restart.
- **Nothing has ever been written to this pedal over the wire.** Every device command sent
  by `blackboxctl` or its predecessor was read-only, and every write path in the tool is
  hard-disabled.

The slot maps and the write log live in [presets/library.md](presets/library.md); the
per-preset state lives in the song documents. Do not restate either here — link.

## 2. Hard rules

1. **Never overwrite `P41`** unless the user explicitly asks. See section 5.
2. **Keep amp slot 1 and IR slot 7 at their factory contents** while P41 is protected.
   P41 references them by number, so replacing either changes P41's sound without
   touching P41.
3. **Record a slot's current contents before overwriting it.** For a preset that is one
   read-only command: `python -m blackboxctl device preset N`.
4. **Treat the M-EFCS sandbox container as read-only** unless the task is explicitly a
   library install. It belongs to another application.
5. **Prefer reversible changes.** Keep enough information to restore what was there.
6. **Verify connection labels, installed-app state, slot contents, and parameter values
   before acting on them.** They are time-sensitive and this file may be stale.

## 3. Tone source policy

Presets are built from **community capture files plus third-party IRs**, not from the
built-in amp models and not from the factory presets. The factory presets are abandoned.

- Slot maps, install procedure, pairing rules, and sources:
  [presets/library.md](presets/library.md).
- Default IR when in doubt: `01A_ML Sound Lab's BEST IR IN THE WORLD`, IR slot 1.
- Built-in amp models may still be referenced, but only for the reserved slots that P41
  depends on.
- Earlier built-in-model preset values are kept in each song document under a heading that
  says so. They are history and, in some cases, a record of what is currently stored —
  never a target.
- The four July 2026 documents under [docs/superpowers/](docs/superpowers/) planned the
  abandoned built-in-model presets. They are marked superseded and **must not be
  executed**, despite reading as live agentic plans with unchecked checkboxes.

## 4. Hardware and software

| | |
| --- | --- |
| Pedal | M-VAVE BlackBox, USB-C to the Mac. Currently unplugged. |
| M-EFCS connection label | `BLACKBOX v20` — the editor's product label, not a confirmed firmware version |
| Editor | `/Applications/M-EFCS.app`, bundle id `com.digAmp.dgAmp`, Mac App Store build, version `3.5.2615` (`CFBundleVersion` `3052615`) |
| macOS audio-device label | `USB-Audio` |
| CoreMIDI identity | manufacturer `Jieli Technology`, product `USB Composite Device` |
| Capacity | 20 amp slots, 20 IR/CAB slots, both replaceable; presets `P01`-`P41` used here |
| File library | `~/Library/Containers/com.digAmp.dgAmp/Data/Documents/M-EFCS/` — `ampFile` for captures, `cabFile` for IRs |

Factory amp models can be restored from the PC version of M-EFCS. Firmware updates run
only from a Windows PC via M-UPGRADE.

Device slot names live in a fixed 14-byte flash record: **13 usable characters including
the numeric prefix** for slots 1-9, 12 for slots 10-20.

## 5. The protected preset: P41 `Wonderwall Live`

Do not modify it. Its full 92-byte flash image was read on 2026-08-28, so unlike before,
there is now enough here to restore it if it is ever damaged.

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

Recover it at any time with `python -m blackboxctl device preset 41`, or decode the hex
above offline with `python -m blackboxctl decode --hex "…"`. Source and raw bytes:
[device-validation.md](docs/reverse-engineering/device-validation.md) STEP 6c.

M-EFCS may not support separately renaming every internal preset. When a name cannot be
stored on the device, document the slot-to-name mapping in this repository.

## 6. Preset safety rules

1. Never overwrite `P41` unless the user explicitly requests it.
2. Presets reference amp and IR slots **by number**. Replacing a slot changes every preset
   pointing at it, including presets nobody here has read. `P41` uses **amp slot 1** and
   **IR slot 7**; keep those two at their factory contents while `P41` is protected. Known
   live exposures: P01 points at IR slot 11 and amp slot 2, P03 at IR slot 5 and amp
   slot 3, P04 and P05 at IR slot 2 — all scheduled to be replaced. **P06-P40 have never
   been read**, so their exposure is unknown; audit them before the first slot write.
3. Build and audition new sounds in the user-selected slot only after inspecting and
   recording its current contents.
4. Before writing a preset, read and record the current slot, effect chain, parameter
   values, and device connection state. `python -m blackboxctl device preset N` does this
   without loading the preset.
5. Prefer reversible changes. Keep enough information to restore the previous preset.
6. After writing, verify both the saved parameter values in M-EFCS and the audible result
   through the connected guitar.

## 7. blackboxctl: reading the device from a terminal

The GUI is no longer the only way to inspect the device. There is a CLI at
[tools/blackboxctl](tools/blackboxctl/) — no dependencies, Python 3.10+, GPL-3.0,
`python -m blackboxctl`. Read
[tools/blackboxctl/STATUS.md](tools/blackboxctl/STATUS.md) before trusting any claim about
it; it separates what was verified on hardware from what was not.

It talks to the pedal over USB MIDI SysEx, so it does not need the GUI, does not need
screen coordinates, and cannot be derailed by another app taking focus.

**Device commands are read-only and cannot be made otherwise.** No write path is enabled;
`python -m blackboxctl write-paths` shows each state-changing command and the exact
evidence for why it is disabled.

| Command | What it does |
| --- | --- |
| `selftest` | offline protocol check; touches nothing. Run it first. |
| `device endpoints` / `sync` / `dump` / `names` / `preset N` | read endpoints, the active preset id, the live preset, the 40 slot names, or stored `PNN` — decoded, without loading it |
| `inspect FILES` | validate `.am2` / `.am3Data` captures and `.wav` IRs |
| `rename FILE NAME` | edit a capture's 13-char header name; `--repair-magic` fixes an `am2converter` magic |
| `decode --hex …` | decode a 92-byte preset image offline |
| `library list` / `diff` / `install` / `restart-editor` | list files, compare `presets/library.md` to disk, copy files in, restart the GUI so it rescans |
| `write-paths` | every state-changing command and why it is disabled |

Caveats worth knowing before you run it:

- `library install`, `library restart-editor` and `rename --in-place` are **dry runs by
  default** and need `--yes`. `install --force` keeps a timestamped `.bak`.
- `restart-editor --yes` quits M-EFCS with an AppleScript `quit`, which discards unsaved
  GUI work. Do not run it while someone is using the app.
- The default `--library-root` is the M-EFCS sandbox container, so `library list` and
  `library diff` reach outside the repository by default.
- `library diff` locates `presets/library.md` by walking up from its own file, so it works
  in place and under `pip install -e .`, but not under a plain `pip install .`.
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

## 9. Driving M-EFCS from a session

Still needed for anything the CLI cannot do: **writing slots, writing presets, and
auditioning**. Those are GUI-only. M-EFCS is a Flutter app, so its accessibility tree
exposes only the window, not its controls — there is no way to click a named button.

What works:

- `osascript -e 'tell application "System Events" to tell process "m_efcs" to get {position, size} of window 1'`
  gives the window frame in points.
- `cliclick` (`/opt/homebrew/bin/cliclick`) moves and clicks at screen coordinates, and
  types text.
- `screencapture -x -o out.png` then reading the image is the only way to confirm what
  happened. Verify after every step.

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
