# Green Day `Boulevard of Broken Dreams` BlackBox Presets Implementation Plan

> ## SUPERSEDED — HISTORY ONLY. DO NOT EXECUTE.
>
> This plan was fully executed on 2026-07-26. Every unchecked `- [ ]` below is done, not
> pending, and Tasks 2 and 3 already wrote P04 and P05 to the device. Two commits record it:
> `1c0a85d` (this plan and its spec) on `main`, and `da7aee9`
> (`feat: document Boulevard BlackBox presets`, which adds
> `presets/boulevard-of-broken-dreams.md` — Task 4 Step 6) on the branch
> `codex/greenday-boulevard-presets`. **`da7aee9` was never merged into `main` or into this
> branch, so `git show da7aee9` fails in a clone that has only `main`.** The preset file on
> this branch is the later capture-based rewrite from `27b2042`.
>
> Note that `docs/staleness-register.md` A2 and A3 originally concluded that this plan was
> never executed and that its completion commit does not exist. Both are refuted by
> `git log --all`; A3 carries the correction. Its goal — presets built from the BlackBox's **built-in amp models** — was
> later abandoned: presets are now built from community capture files plus third-party IRs.
> See [`presets/boulevard-of-broken-dreams.md`](../../../presets/boulevard-of-broken-dreams.md)
> for the current targets and [`presets/library.md`](../../../presets/library.md) for the
> tone source policy. The current project phase sends **nothing** to the pedal, not even
> reads.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store a clean tremolo verse preset in P04 and a British chorus-crunch preset in P05 without changing P01-P03 or P41.

**Architecture:** M-EFCS is the authoritative device editor. Work on one slot at a time, verify the selected slot before every save, re-open each saved slot to prove persistence, and record the exact final state separately from the player listening check.

**Tech Stack:** M-VAVE BlackBox, M-EFCS desktop app, HSS Strat-style guitar, Markdown documentation

---

### Task 1: Read-Only Device Preflight

**Files:**
- Reference: `AGENTS.md`
- Create after device writes: `presets/boulevard-of-broken-dreams.md`

- [ ] **Step 1: Confirm the live device**

Open `/Applications/M-EFCS.app`, connect to the discovered device, and confirm the editor header reads `BLACKBOX v20`.

Expected: exactly one BlackBox is connected and the parameter editor loads without a handshake error.

- [ ] **Step 2: Confirm the target and protected slots**

Open P04 and P05 without saving either one. Confirm the preset selector shows `Preset 4` and `Preset 5` respectively. Open P41 read-only and compare it with `AGENTS.md`.

Expected P41: total volume 85, `1J900_CL` Gain 45, `7VOX_AC30`, Chorus Mix 12, Room Mix 12, and delay disabled.

- [ ] **Step 3: Respect the backup decision**

Do not create a restoration backup for P04 or P05. Continue only with the approved target slots P04 and P05.

### Task 2: Build and Persist P04 Boulevard Pulse Clean

**Files:**
- Create after verification: `presets/boulevard-of-broken-dreams.md`

- [ ] **Step 1: Select P04**

Use the preset selector and confirm the editor displays `Preset 4`.

- [ ] **Step 2: Set the shared output**

Set total volume to 85.

- [ ] **Step 3: Configure FX**

Select `Compress`; set Gate 10, Sustain 30, Attack 60, Level 50; enable FX.

- [ ] **Step 4: Configure AMP**

Select `1J900_CL`; set Gain 28, Level 70, Bass 45, Mid 62, Treble 55; enable AMP.

- [ ] **Step 5: Configure CAB**

Select `2JVM_1960_57`; set Level 70, Low Cut 76, High Cut 18.0K; enable CAB.

- [ ] **Step 6: Configure MOD**

Select `Tremolo`; set Speed 39, Depth 60, Level 50; enable MOD.

- [ ] **Step 7: Configure REV and DLY**

Select `Room`; set Decay 25, Mix 12, HPass 65, LPass 50, Depth 25; enable REV. Disable DLY.

- [ ] **Step 8: Save P04**

Reconfirm `Preset 4`, click `Save`, and wait for the M-EFCS success response.

Expected: the save completes without disconnecting the device or showing an error.

- [ ] **Step 9: Verify P04 persistence**

Switch to P05, return to P04, and compare every model, value, enable state, and total volume with steps 2-7.

Expected: all P04 values persist exactly.

### Task 3: Build and Persist P05 Boulevard Chorus Crunch

**Files:**
- Create after verification: `presets/boulevard-of-broken-dreams.md`

- [ ] **Step 1: Select P05**

Use the preset selector and confirm the editor displays `Preset 5`.

- [ ] **Step 2: Set the shared output**

Set total volume to 85.

- [ ] **Step 3: Configure FX**

Select `Boost`; set Gate 20 and Gain 35; enable FX.

- [ ] **Step 4: Configure AMP**

Select `9J900_DS`; set Gain 58, Level 65, Bass 45, Mid 68, Treble 57; enable AMP.

- [ ] **Step 5: Configure CAB**

Select `2JVM_1960_57`; set Level 68, Low Cut 76, High Cut 18.0K; enable CAB.

- [ ] **Step 6: Configure MOD**

Disable MOD. The inactive model and values do not affect the sound.

- [ ] **Step 7: Configure REV and DLY**

Select `Room`; set Decay 18, Mix 8, HPass 65, LPass 45, Depth 15; enable REV. Disable DLY.

- [ ] **Step 8: Save P05**

Reconfirm `Preset 5`, click `Save`, and wait for the M-EFCS success response.

Expected: the save completes without disconnecting the device or showing an error.

- [ ] **Step 9: Verify P05 persistence**

Switch to P04, return to P05, and compare every model, value, enable state, and total volume with steps 2-7.

Expected: all P05 values persist exactly.

### Task 4: Document and Safety-Check the Result

**Files:**
- Create: `presets/boulevard-of-broken-dreams.md`

- [ ] **Step 1: Write the final preset record**

Create the file with the device label, guitar and pickup guidance, exact P04/P05 model names, all visible values, enable states, and total volume.

- [ ] **Step 2: Verify protected slots**

Open P41 read-only and confirm its known-good values remain unchanged. Do not click Save. Do not edit or save P01-P03.

- [ ] **Step 3: Leave the device ready to play**

Return to P04 so the first footswitch state is the intro/verse sound.

- [ ] **Step 4: Mark proof layers separately**

Record device-write and persistence results as passed only if the UI proves them. Record the audible guitar comparison as pending until the user plays the connected HSS Strat.

- [ ] **Step 5: Validate the documentation**

Run:

```bash
git diff --check
rg -n "P04|P05|P41|BLACKBOX v20|Persistence|Listening" presets/boulevard-of-broken-dreams.md
```

Expected: `git diff --check` exits 0 and the search prints every required safety and verification heading.

- [ ] **Step 6: Commit the reproducible result**

```bash
git add presets/boulevard-of-broken-dreams.md
git commit -m "feat: document Boulevard BlackBox presets"
```
