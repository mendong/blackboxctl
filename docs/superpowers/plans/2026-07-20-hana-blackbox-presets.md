# Fujii Kaze `Hana` BlackBox Presets Implementation Plan

> ## SUPERSEDED — HISTORY ONLY. DO NOT EXECUTE.
>
> This plan was fully executed on 2026-07-20 (commits `c47a50a` and `fc841a6`). Every
> unchecked `- [ ]` below is done, not pending. Its goal — presets built from the BlackBox's
> **built-in amp models** — was later abandoned: presets are now built from community
> capture files plus third-party IRs. See [`presets/hana.md`](../../../presets/hana.md) for
> the current targets and [`presets/library.md`](../../../presets/library.md) for the tone
> source policy. The current project phase sends **nothing** to the pedal, not even reads.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store three validated `Hana` guitar-accompaniment tones in BlackBox slots P01, P02, and P03 without changing P41.

**Architecture:** M-EFCS is the authoritative device editor. First capture the live slot/model state, then translate the approved tone ranges into available BlackBox models, save one slot at a time, and document the exact persisted values and listening results.

**Tech Stack:** M-VAVE BlackBox, M-EFCS desktop app, HSS Strat-style guitar, optional GarageBand monitoring, Markdown documentation

---

### Task 1: Capture Device and Slot State

**Files:**
- Create: `presets/hana.md`

- [ ] **Step 1: Open M-EFCS and verify the connected-device label**

Expected: M-EFCS reports the connected BlackBox; record the exact label and editor-visible firmware/version in `presets/hana.md`.

- [ ] **Step 2: Inspect P01, P02, and P03 without changing controls**

Record each slot's amp, cab, enabled effects, parameter values, and total volume under `Before overwrite` headings.

- [ ] **Step 3: Confirm P41 remains the known-good preset**

Expected: selecting P41 shows the existing `Wonderwall Live` chain or its previously recorded equivalent. Do not edit or save P41.

- [ ] **Step 4: Commit the captured state**

```bash
git add presets/hana.md
git commit -m "docs: capture BlackBox slots before Hana presets"
```

### Task 2: Build and Verify P01 Hana Warm Clean

**Files:**
- Modify: `presets/hana.md`

- [ ] **Step 1: Select P01 and configure the warm-clean chain**

Use the closest available American/Fender clean amp and open-back clean cab. Apply the approved P01 starting ranges from the design document.

- [ ] **Step 2: Save P01 and switch to another slot**

Expected: M-EFCS completes the device write without disconnecting or reporting an error.

- [ ] **Step 3: Re-open P01 and compare every persisted value**

Expected: model selections, effect on/off states, and values match the intended chain. Correct and save any value that did not persist.

- [ ] **Step 4: Audition P01 with the neck single-coil**

Play soft arpeggios, full chords, and hard accents. Reduce gain if hard accents crunch; reduce chorus if pitch motion is obvious; reduce reverb if chord changes smear.

- [ ] **Step 5: Record exact P01 values**

Write the final model names, all visible parameters, pickup position, guitar controls, and listening notes to `presets/hana.md`.

### Task 3: Build and Verify P02 Hana Edge

**Files:**
- Modify: `presets/hana.md`

- [ ] **Step 1: Select P02 and configure the edge-of-breakup chain**

Use the closest available British chime/VOX-style amp and matching open-back 2x12 cab. Add a transparent low-gain drive only if the amp alone cannot move from clean to soft grit with picking dynamics.

- [ ] **Step 2: Save P02, switch away, and re-open it**

Expected: all model selections, effect states, and values persist.

- [ ] **Step 3: Audition P02 with the neck single-coil**

Expected: light picking remains clean and hard chord accents add restrained grit. Lower drive or amp gain if sustained chords become distorted.

- [ ] **Step 4: Match P02 loudness to P01**

Alternate P01 and P02 while playing the same chord figure. Adjust only final output level until neither preset sounds louder.

- [ ] **Step 5: Record exact P02 values**

Write the final model names, values, pickup position, guitar controls, and listening notes to `presets/hana.md`.

### Task 4: Build and Verify P03 Hana Acoustic Clean

**Files:**
- Modify: `presets/hana.md`

- [ ] **Step 1: Select P03 and check for an acoustic simulator**

If available, use it with a neutral/full-range cab path. Otherwise use the cleanest neutral amp at very low gain with a bright open-back cab. Record which route was used.

- [ ] **Step 2: Configure and save the P03 chain**

Apply the approved P03 ranges, keep delay off, and use only short room/plate ambience.

- [ ] **Step 3: Switch away, re-open P03, and compare every value**

Expected: all values persist and delay remains off.

- [ ] **Step 4: Audition with neck+middle or middle single-coil**

Expected: chords remain fully clean and percussive without harsh top end. Lower treble/presence if pick attack becomes sharp; lower compressor sustain if chords pump.

- [ ] **Step 5: Match P03 loudness to P01 and P02**

Alternate the three slots with the same chord figure and adjust only final output volume.

- [ ] **Step 6: Record exact P03 values**

Write the final model names, values, pickup position, guitar controls, and listening notes to `presets/hana.md`.

### Task 5: Final Persistence and Safety Check

**Files:**
- Modify: `presets/hana.md`

- [ ] **Step 1: Cycle through P01, P02, and P03**

Expected mapping: P01 `Hana Warm Clean`, P02 `Hana Edge`, P03 `Hana Acoustic Clean`.

- [ ] **Step 2: Re-open P41 without saving**

Expected: P41 is unchanged from the initial check.

- [ ] **Step 3: Record the final verification result**

Add the verification date, connected-device label, persistence result, loudness-match result, and any substitutions from the design to `presets/hana.md`.

- [ ] **Step 4: Validate documentation and commit**

Run:

```bash
git diff --check
rg -n "P01|P02|P03|P41|Before overwrite|Final values|Verification" presets/hana.md
```

Expected: `git diff --check` exits 0 and every required slot/safety heading is present.

```bash
git add presets/hana.md
git commit -m "feat: document Hana BlackBox presets"
```
