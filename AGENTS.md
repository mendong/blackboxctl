# M-VAVE BlackBox Workspace Guide

## Purpose

This workspace is for designing, documenting, and validating guitar presets for the user's connected M-VAVE BlackBox.

The current goal is to create a guitar-accompaniment preset inspired by Fujii Kaze's `Hana` and validate it on the physical device.

## Known Hardware and Software

- Device: M-VAVE BlackBox
- M-EFCS connection label previously observed: `BLACKBOX v20`
- Preset editor: `/Applications/M-EFCS.app`
- macOS audio-device label previously observed: `USB-Audio`
- Treat connection labels, installed-app state, preset slots, and current parameter values as time-sensitive. Verify them before changing the device.

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
2. Build and audition new sounds in the user-selected slot only after inspecting and recording its current contents.
3. Before writing a preset, read and record the current slot, effect chain, parameter values, and device connection state.
4. Prefer reversible changes. Keep enough information to restore the previous preset.
5. After writing, verify both the saved parameter values in M-EFCS and the audible result through the connected guitar.

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
3. Propose the complete effect chain and parameter values before writing to the device.
4. Use the user-selected slot only after confirming whether its current contents may be overwritten.
5. Audition against the original track or backing track at matched loudness.
6. Adjust in this order: gain and dynamics, amp EQ, cab, modulation, delay, reverb, then output volume.
7. Record the final slot mapping and all reproducible values in this repository.

## Current Preset Target

- Artist: Fujii Kaze
- Song: `Hana`
- Intended role: guitar accompaniment
- Guitar: HSS Strat-style guitar (single / single / humbucker)
- Initial pickup target: neck single-coil
- Target slot: `P01`, subject to inspecting and recording its current contents before writing
- Status: tone design and P01 overwrite safety still need confirmation
