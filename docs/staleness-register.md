# Staleness and coverage register

Audit date: 2026-08-28. Scope: everything outside `docs/reverse-engineering/`, which a
separate auditor is handling. The reverse-engineering documents are used here as evidence,
not audited.

Method: every document listed below was read in full; `git log --stat` was read back to the
first commit; the M-EFCS sandbox library was inspected read only; `blackboxctl selftest`,
`library list` and `library diff` were run; the twenty factory IR files and the nineteen
mapped IR files were re-measured from their RIFF headers.

**One limitation of that method, and it produced a wrong finding.** The `git log` pass
covered only this branch's history, not `--all`. Commit `da7aee9` sits on the unmerged
branch `codex/greenday-boulevard-presets` and was therefore invisible, which is why A2 and
A3 concluded that the Boulevard plan was never executed. Both are corrected below. Any
future archaeology on this repository should use `git log --all`.

No command of any kind was sent to the pedal. Nothing under
`~/Library/Containers/com.digAmp.dgAmp/` was modified.

> **This is an audit snapshot, taken *before* the documentation consolidation, plus a
> disposition line added to each finding afterwards.** Every finding now opens with a
> **Status** line: **APPLIED** with the file and section where the fix landed, **APPLIED IN
> PART**, **OPEN**, or **REFUTED** where a later check overturned the finding itself. The
> body text and the **Recommendation** lines are the audit's own wording and are preserved
> deliberately; where a Recommendation reads as an instruction, the Status line is the
> record of what actually happened. Do not re-do an APPLIED finding. Two findings are
> corrected rather than dispositioned — A2 and A3 — because `git log --all` refutes them.

Documents audited:

- `AGENTS.md`
- `presets/library.md`, `presets/hana.md`, `presets/boulevard-of-broken-dreams.md`
- `docs/superpowers/plans/*.md`, `docs/superpowers/specs/*.md`
- `tools/blackboxctl/README.md`, `tools/blackboxctl/STATUS.md`

---

## Summary

35 findings, every one now carrying a Status line. As dispositioned during the fix pass:
**23 APPLIED**, **5 APPLIED IN PART**, **1 OPEN** (C6), **1 REFUTED** (A3), and the five
duplications in section D all still stand. The four that mattered most at audit time:

1. `docs/superpowers/plans/` contains two live, unmarked, executable plans whose targets
   were abandoned and whose instructions would write to the pedal (A1).
2. `presets/library.md` names the wrong file as the 32-bit float factory IR; the evidence
   for its central argument about the vendor spec is misattributed (B1, B2).
3. The pending slot writes will silently repoint presets P06-P40, which nobody has read
   and no document mentions (C2).
4. The predecessor transport module, the reference codec implementation and the only
   library backup all live in temp directories that will be purged (C3).

---

## A. Stale

### A1. The superpowers plans are unmarked, executable, and aimed at abandoned targets

**Status: APPLIED IN PART.** A superseded banner was added to the top of both plans and both specs, above the agentic-worker directive, naming what replaced them and stating the outcome. The files were **not** moved to `docs/history/`; they are still at `docs/superpowers/`, and the root `README.md` labels that directory "History only. Do not execute."

**Where:** `docs/superpowers/plans/2026-07-20-hana-blackbox-presets.md`,
`docs/superpowers/plans/2026-07-26-greenday-boulevard-blackbox-presets.md`
**Severity:** high

Both files open with `> **For agentic workers:** REQUIRED SUB-SKILL: Use
superpowers:subagent-driven-development ... to implement this plan task-by-task.` Every
step is an unchecked `- [ ]`. The Boulevard plan's Task 2 and Task 3 are explicit device
writes: select `1J900_CL`, set Gain 28, select `2JVM_1960_57`, click `Save`.

Those targets are built-in amp models. `AGENTS.md` Tone Source Policy says built-in models
are abandoned and the factory presets are dropped. The current working rule is that
nothing is sent to the pedal at all. An agent that opened either plan file on its own
would follow it.

**Recommendation:** put a superseded banner at the top of both plans and both specs,
immediately under the title and above the agentic-worker directive, naming what replaced
them (`presets/hana.md`, `presets/boulevard-of-broken-dreams.md`, `presets/library.md`) and
stating that the plans are kept as history and must not be executed. Move all four files to
`docs/history/` so the path itself signals the status. They are worth keeping: they are the
only record of why P04 and P05 exist as a section pair and why two alternative approaches
were rejected.

### A2. Unchecked checkboxes mean two opposite things

**Status: APPLIED, and the finding itself was partly wrong.** Both plans and both specs now
carry a superseded banner stating the outcome. The claim below that "the Boulevard plan was
not executed" is **REFUTED** — see the correction in A3.

**Where:** both plan files, all steps
**Severity:** medium

The Hana plan was executed. Commit `c47a50a` (2026-07-20) is its Task 1 Step 4 verbatim,
and `fc841a6` is its Task 5 Step 4 verbatim; `presets/hana.md` records the writes as
passed. ~~The Boulevard plan was not executed.~~ **Struck: it was.** Both files present
identically unchecked boxes, so the reader cannot tell a completed plan from an abandoned
one.

**Recommendation:** if the plans are kept as history, replace the checkbox column with a
short outcome line per task, or state the outcome once in the banner from A1.

### A3. The Boulevard plan's own completion step never happened — **REFUTED**

**Status: REFUTED by `git log --all`, and the correct account is below.** The original
finding is preserved because it explains a real gap: the completion commit is not reachable
from `main` or from this branch.

**Where:** `docs/superpowers/plans/2026-07-26-greenday-boulevard-blackbox-presets.md`
Task 4 Step 6
**Severity:** medium

**Corrected.** The plan's Task 4 Step 6 *did* happen. Commit `da7aee9`, dated
`Sun Jul 26 11:23:08 2026 +0900`, message exactly `feat: document Boulevard BlackBox
presets`, adds `presets/boulevard-of-broken-dreams.md` (69 lines) — precisely that step.
It lives on the branch `codex/greenday-boulevard-presets` and **is not an ancestor of
`main` or of this branch**, which is why an archaeology pass limited to this branch missed
it. `git show da7aee9` therefore fails for anyone who clones only `main`.

The original finding, kept for the record: "The plan ends by committing
`presets/boulevard-of-broken-dreams.md` with the message `feat: document Boulevard BlackBox
presets`. The actual 2026-07-26 commit is `1c0a85d`, `docs: define Boulevard BlackBox
presets`, and it contains only the plan and the spec." `1c0a85d` is real and does contain
only the plan and the spec; what was wrong was concluding that no completion commit exists.
The file on this branch was rewritten against captures in `27b2042` on 2026-08-28, which is
a separate event.

**Recommendation:** the plan's banner now cites `da7aee9` and says it is on an unmerged
branch. This does **not** weaken
`presets/boulevard-of-broken-dreams.md`'s "no read-back exists" statement: `da7aee9` is a
record of a GUI session, not a flash read, and P04/P05 have still never been read out of
the device.

### A4. The "Superseded" values in hana.md are what is on the device right now

**Status: APPLIED.** `presets/hana.md`'s heading is now `## Currently on the device — the built-in-amp-model version`, it says so in the first sentence, it carries the 2026-08-28 flash-read citation, and a `## What is on the device right now` section sits directly under the Device block.

**Where:** `presets/hana.md` lines 100-130, heading
`## Superseded — built-in amp model version`
**Severity:** high

The heading text says "Kept for reference. These were the values before the move to
capture files. They are no longer the target for P01-P03." Nothing says they are the live
device contents. They are.

`docs/reverse-engineering/device-validation.md` STEP 6a read flash index 0 (P01) on
2026-08-28 and decoded: volume 85, all blocks on, FX Compress, AMP model 1 to `FD_CL` with
Gain 25 Level 70 Bass 45 Mid 55 Treble 47, CAB model 10 to `FD_TW1980` Level 70, Chorus
20/20/10, Dual 18/6/6, Room 28/20/60/45/45. That is `hana.md`'s superseded P01 field for
field. STEP 2 read live RAM and STEP 6b read flash index 2 (P03) and confirmed them
byte-identical; the decode is AMP model 2 to `JC120_CL` Gain 23 Level 67 Bass 43 Mid 46
Treble 62, CAB model 4 to `HIFI_OK` Level 68, FX 21/53/58/50, Hall 10/15/48/49/30, Dual
84/47/15 with delay off, MOD off. That is `hana.md`'s superseded P03 field for field.

P02 was never read from flash, so its state remains asserted from the July GUI session
only.

**Recommendation:** rename the heading to say both things, for example
`## Currently on the device — built-in amp model version, superseded as a target`, and add
the 2026-08-28 flash-read citation. A reader asking "what will I overwrite?" must land
here, not on `Before overwrite`.

### A5. hana.md's "Before overwrite" record is no longer restorable

**Status: APPLIED.** The heading is now `## Historical record — state before the 2026-07-20 overwrite`, and it says explicitly that it is not a restore point, that IR slot 1 has since changed, and what restoring it would take.

**Where:** `presets/hana.md` lines 12-41
**Severity:** medium

P01's recorded pre-July cab is `1AC-SeVin`, which is IR slot 1. IR slot 1 was overwritten
with `1ML_BEST_IR` on 2026-08-28. Restoring the recorded chain would now load the ML Best
IR, not the factory `1AC-SeVin` IR. The section reads as a restore point and is no longer
one without first restoring IR slot 1 from `cabFile/1AC-SeVin.wav`.

**Recommendation:** add one line to the section saying it is a historical record of the
2026-07-20 state, that IR slot 1 has since changed, and what restoring it would take.

### A6. AGENTS.md assumes a connected pedal; the pedal is disconnected

**Status: APPLIED.** `AGENTS.md` §1 opens with "The pedal is unplugged", and `tools/blackboxctl/STATUS.md` remains the place the connection state is measured.

**Where:** `AGENTS.md` line 5, and the whole of `## Driving M-EFCS from a Session` and
`## Mac Monitoring Path`
**Severity:** medium

`AGENTS.md` opens "for the user's connected M-VAVE BlackBox" and both procedural sections
presuppose a live device. `tools/blackboxctl/STATUS.md` records the opposite as of the same
date: 0 CoreMIDI sources and destinations, `MIDIGetNumberOfDevices() == 6` with the Jieli
endpoint flagged `kMIDIPropertyOffline == 1`, and no Jieli device in
`system_profiler SPUSBDataType`. `AGENTS.md` states no connection state at all, and line 28
tells the reader to treat connection labels as time-sensitive without saying where the
current answer lives.

**Recommendation:** state the connection posture once, in the Current State section, and
have `STATUS.md` be the place it is measured.

### A7. The slot-name length limit is now measured, not approximate

**Status: APPLIED.** `presets/library.md`'s IR slot map and `AGENTS.md` §4 both state 13 characters including the prefix for slots 1–9 and 12 for slots 10–20, citing the measured 14-byte stride.

**Where:** `presets/library.md` line 141
**Severity:** low

"Device slot names are limited to roughly 12 characters" predates the flash read.
`device-validation.md` STEP 4 measured the record exactly: 14-byte stride, so 13 usable
characters including the numeric prefix, which is 12 usable for slots 10-20. All nineteen
proposed short names fit.

### A8. Two "unknown" markers now have a cheap read-only answer

**Status: APPLIED.** Both `presets/boulevard-of-broken-dreams.md` and `presets/hana.md` now open with a `## What is on the device right now` section giving the exact `device preset N` commands, P02 included.

**Where:** `presets/boulevard-of-broken-dreams.md` lines 17-22 and 86
**Severity:** medium

"it is unknown whether those built-in-model values were actually written to the device" and
"Read-only inspection of the current P04 and P05: not done yet" are both still true, but
since 2026-08-28 there is a one-command answer that does not touch the GUI and does not
load the preset: `python -m blackboxctl device preset 4` and `device preset 5`. No document
names it. The same is true of P02 in `hana.md`.

**Recommendation:** replace "inspect P04 and P05 read-only" with the exact command, and add
P02 to the list.

### A9. Pending-work lists are accurate but unsourced

**Status: APPLIED.** `presets/library.md`'s device write log now cites `device-validation.md` STEP 4 and STEP 5 as the evidence for what has *not* been written.

**Where:** `AGENTS.md` line 161, `presets/library.md` line 202
**Severity:** low

Both say IR slots 2-6 and 8-20 and amp slots 2-20 are still pending. That is correct, and
it is now provable rather than remembered: `device-validation.md` STEP 4 and STEP 5 read
all forty slot names out of flash and every amp slot 1-20 and every IR slot 2-20 came back
with its factory name. Neither document cites it.

---

## B. Contradicted by later work, or wrong about the world

### B1. library.md names the wrong file as the 32-bit float factory IR

**Status: APPLIED.** `presets/library.md` now carries a full 20-row table measured from the RIFF `fmt ` chunk: `7VOX_AC30` is format tag 1 (32-bit integer PCM) and `10SoldSC412` is format tag 3 (32-bit IEEE float). Re-verified during the fix pass. See also contradiction-register C12.

**Where:** `presets/library.md` lines 74-84, the measured-IR table row
`factory 7VOX_AC30 | 2048 | 46 ms | 44.1 kHz, **32-bit float**`
**Severity:** high

Measured from the file's own `fmt ` chunk:

```
7VOX_AC30.wav    fmt tag 0x0001 (WAVE_FORMAT_PCM),   1 ch, 44100 Hz, 32 bit, 2048 frames
10SoldSC412.wav  fmt tag 0x0003 (WAVE_FORMAT_IEEE_FLOAT), 1 ch, 44100 Hz, 32 bit, 1020 frames
```

`7VOX_AC30` is 32-bit integer PCM. The one 32-bit float file in the factory set is
`10SoldSC412.wav`, which is exactly what `tools/blackboxctl/STATUS.md` line 55 says. The
two documents contradict each other and `library.md` is the wrong one.

The likely cause is stated in `library.md` itself: it says the measurement was made "with
`wave`". The standard-library `wave` module reports `sampwidth == 4` and has no way to
distinguish integer from float, so a 32-bit PCM file and a 32-bit float file look
identical to it.

This matters beyond a typo. `7VOX_AC30` is IR slot 7, the slot reserved for the protected
P41, so the document is making a format claim about the one IR it has promised not to
touch. And the conclusion drawn from it — "the pedal is demonstrably running a 32-bit
float factory IR ... which means it converts rather than rejects" — is true, but only via
`10SoldSC412`.

**Recommendation:** correct the row to `44.1 kHz, 24-bit-container 32-bit integer PCM`, add
a `10SoldSC412` row as the actual float case, and state the measurement method as reading
the `fmt ` chunk's `wFormatTag` rather than `wave`.

### B2. "The pedal's own factory IRs measure 2048 frames" over-generalises, and the

**Status: APPLIED.** Superseded by the full 20-row table in `presets/library.md`. See also contradiction-register C32.
counter-example is the one that matters

**Where:** `presets/library.md` lines 69-72
**Severity:** medium

Measured across all twenty factory IRs in `cabFile`: sixteen are 2048 frames. The four that
are not:

| File | Frames | Rate | Note |
| --- | ---: | ---: | --- |
| `1AC-SeVin` | 10000 | 44.1 kHz | |
| `5HIFI_OK` | 22026 | 44.1 kHz | |
| `10SoldSC412` | **1020** | 44.1 kHz | 32-bit float; essentially the vendor's 1024 |
| `15JC120_BOX` | 13230 | 44.1 kHz | |

The document's argument is that the vendor spec line "1024 sampling points" is intent
rather than contract, because no factory IR is 1024. One factory IR is 1020, and it is the
same file B1 concerns. The conclusion survives — sixteen of twenty are 2048 and one is
22026 — but the sentence as written is falsified by the pedal's own files.

**Recommendation:** state the distribution rather than a single number.

### B3. The factory IR set is itself mixed-rate, which the document does not use

**Status: APPLIED.** `presets/library.md` now lists the three 48 kHz and two 96 kHz factory IRs and uses them as the evidence for "intent, not contract". Note the separate correction under "What that does and does not prove": the factory set failing the spec line is evidence about the vendor's *source files*, not about what the pedal does on import.

**Where:** `presets/library.md` lines 74-84
**Severity:** low

`3V30_MD421`, `4G12-EVH_CT` and `11FD_TW1980` are 48 kHz. `8FRMAN112` and `14Recto_112`
are 96 kHz. The document argues "the pedal converts rather than rejects" from a single
48 kHz user IR in slot 1. Five factory IRs at 48 and 96 kHz are stronger evidence for the
same conclusion and are not mentioned.

### B4. "Only 7 match the vendor spec exactly" is looser than it reads

**Status: APPLIED.** `presets/library.md` now says the seven match "on channel count, sample rate and bit depth", states that none matches on length, and flags slot 8 as the most exposed file in the map.

**Where:** `presets/library.md` line 86
**Severity:** low

The three classification lists were re-measured and are all correct: stereo is slots
2, 3, 4, 8, 9, 11, 12; 48 kHz is slots 1, 5, 15, 16, 18; the remainder is 6, 10, 13, 14,
17, 19, 20. But none of those seven is 1024 frames — they measure 8850, 22050, 22051,
8192, 16538, 2048 and 22050. They match on channel count, sample rate and bit depth only.

Related and worth adding: the longest tail among the mapped IRs is slot 8,
`04D_Vox 4 AC30 1966 Top Boost`, at 66150 frames / 1500 ms, and it is also stereo. It is
the CAB for Hana P02. By the document's own "prefer IRs whose useful energy is early" rule
it is the mapped IR most exposed to whatever truncation the upload path does.

### B5. README.md and STATUS.md disagree on the test count

**Status: APPLIED — settled by running the suite.** `pytest` was installed into a throwaway
virtualenv and `python -m pytest` reported **`221 passed`** (Python 3.14.3, pytest 9.1.1,
2026-08-28). `tools/blackboxctl/README.md`, `tools/blackboxctl/STATUS.md` and the root
`README.md` now all say 221, and `STATUS.md` records that the figure is from a real run
rather than the cache. See also contradiction-register C24.

**Where:** `tools/blackboxctl/README.md` line 185 said `python -m pytest # 212 tests`;
`tools/blackboxctl/STATUS.md` said 221 tests pass
**Severity:** medium

`tools/blackboxctl/.pytest_cache/v/cache/nodeids` holds 221 node ids (untracked — the
directory is in `.gitignore`), and 221 is what a real run produces: 114 test functions plus
16 `parametrize` sites. README was stale.

### B6. Six slot-map filenames in library.md do not match the files on disk

**Status: APPLIED.** `presets/library.md` states once that its filenames are abbreviated stems, names `library diff` as the authority on resolution, and spells out the full names for amp slots 4 and 9, IR slot 15 and the audition list.

**Where:** `presets/library.md` amp slot map rows 4 and 9, IR slot map row 15, and the
"Left in the Mac library for auditioning" list
**Severity:** medium

| Document says | On disk |
| --- | --- |
| `016B_Clean_Fender_Princeton_1962_Chris_Stapleton_Edition_V7_T8` | `016B_..._V7_T8_AuditionX_A+.am2data` |
| `009_Clean_Vox_AC30_212g12_30k` | `009_Clean_Vox_AC30_212g12_30k_AuditionX.am2data` |
| `07A_Celestion_V30 2x12 Ball 0.0in 0in_High_Quality` | `07A_..._High_Quality For_Mesa_Orange_Diezel_Soldano_BlackStar.wav` |
| `101_OD_Friedman BE100 C45 SAT` | `101_OD_Friedman BE100 C45 SAT_100K Epochs_use_Friedman_IR.am2Data` |
| `108_OD_Vox_AC30_Drive` | `108_OD_Vox_AC30_Drive_AuditionX.am2data` |
| `021_Clean_Marshall_JCM2000_DSL` | `021_Clean_Marshall_JCM2000_DSL_AuditionX.am2data` |

`blackboxctl library diff` matches by stem prefix and reports `ok=38 reserved=2`, so the
tool is unaffected. A human following `library.md`'s own "How to write one slot in M-EFCS"
procedure would type the documented string into the M-EFCS search box; the search is a
fuzzy subsequence match so it would still hit, but the document nowhere says its filenames
are abbreviations.

**Recommendation:** either use full stems, or state once that stems are abbreviated and
that `library diff` is the authority on resolution.

### B7. Two factory IR files are stored with a trailing space

**Status: APPLIED.** `presets/library.md` names `17AgSVT410 .wav` and `20Tace412 .wav` and warns that an exact-name lookup will miss them.

**Where:** `presets/library.md` line 175, "All twenty are still present as files in
`cabFile`, so any slot can be put back"
**Severity:** medium

The claim is true, but `17AgSVT410` and `20Tace412` are on disk as `17AgSVT410 .wav` and
`20Tace412 .wav`, with a space before the extension. A restore keyed on the documented
name fails to find them. Both measure 44.1 kHz, 24-bit, mono, 2048 frames. All eighteen
other factory IR files match their documented names exactly.

### B8. The IR slot 1 write log cites the weaker of two available proofs

**Status: APPLIED.** The write log now cites both proofs, and names the same flash read as the evidence for what has not been written.

**Where:** `presets/library.md` lines 196-202, `## Device write log`
**Severity:** medium

The log's evidence is "passed, verified in the `Position` dropdown". A stronger,
independent confirmation exists and is not referenced: `device-validation.md` STEP 4 read
the IR name table straight out of flash over USB MIDI SysEx, and slot 1 came back
`1ML_BEST_IR`. The same read is also the direct proof of the "Remaining:" line, since every
other amp and IR slot came back with its factory name.

### B9. The Mac-side library has nine folders, not four

**Status: APPLIED.** `presets/library.md` lists all nine subfolders with a "Backed up" column.

**Where:** `presets/library.md` lines 36-42
**Severity:** low

`~/Library/Containers/com.digAmp.dgAmp/Data/Documents/M-EFCS/` contains `aiToneFile` (with
`amp`, `cab`, `ds` subfolders), `ampFile`, `audio_library` (with `files`), `cabFile`,
`downloadFile` (empty), `dsFile`, `model`, `otherFile` (empty), `shareFile` (empty). The
document's table lists four. The backup covers `ampFile`, `cabFile`, `dsFile` only, which
is defensible, but the document does not say what it is leaving out or why.

### B10. README.md gives two different counts for the read commands

**Status: APPLIED.** The reconciliation is now stated as one line — **four read command
shapes, five address bases, seven transmitted byte literals** (sixteen transmissions across
the seven logs) — in the root `README.md`, in
`docs/reverse-engineering/README.md`, in `tools/blackboxctl/STATUS.md` and in
`docs/reverse-engineering/device-validation.md`'s safety record.

**Where:** `tools/blackboxctl/README.md` line 52 says `selftest` verifies "the seven
read-command literals"; line 143 says "all four read commands"
**Severity:** low

Both are true — four command shapes, seven transmitted literals — but the page never
reconciles them. `selftest` prints `21/21 checks passed`, of which seven are read literals.

### Verified correct, no action needed

**Status: all still correct.** Spot-re-checked during the fix pass: the `fmt `-chunk
measurements behind B1, the `git ls-files` census, the seven log files and their frame
counts, and the test count. Recorded so a later auditor does not repeat the work.

- `ampFile` holds 39 files, `cabFile` 293, `dsFile` 14. `library.md`'s "24 captures added
  on top of the 15 that were already there" and "83 IRs added on top of the 210" both
  reconcile exactly, and the backup tarball contains exactly 15, 210 and 14.
- The ML Best IR SHA-256 is
  `0cafcee04e2c9e6794b4d98c8fcf7168131b8eb78c460ed88d53f843983e4e2e`, matching the
  abbreviated `0cafcee0…3e4e2e` in `library.md`.
- M-EFCS is `3.5.2615`, `CFBundleVersion` `3052615`, bundle id `com.digAmp.dgAmp`, as all
  four preset documents state.
- The `model` blob is 114,573,416 bytes, matching "114 MB".
- `cliclick` is present at the documented `/opt/homebrew/bin/cliclick`.
- `blackboxctl selftest` passes 21/21; `library list` reports 332 files with no parse
  error; `library diff` reports `ok=38 reserved=2`, matching STATUS.md.
- Every amp and IR slot number cited in `hana.md` and `boulevard-of-broken-dreams.md`
  resolves to the file `library.md` maps to that slot. All nineteen proposed IR short names
  fit the measured 13-character field.
- Every factory amp model name used in `hana.md` (`12FRIMAN`, `5RAT_OD`, `6M-VAVE_OD`,
  `2FD_CL`, `3JC120_CL`, `4BLUE_OD`) and `boulevard-of-broken-dreams.md` (`1J900_CL`,
  `9J900_DS`) matches the names read out of the pedal's flash.
- The P41 values in `AGENTS.md` that overlap the flash decode all match: amp `1J900_CL`,
  gain 45, cab `7VOX_AC30`, chorus mix 12, room mix 12, delay off, volume 85.

---

## C. Gaps

### C1. No entry point

**Status: APPLIED.** The root `README.md` now exists and is the entry point.

**Severity:** high

There is no top-level `README.md`. Nothing states what this project is, that it has four
independent parts — per-song preset designs, a capture and IR library map, a protocol
reverse-engineering corpus, and a CLI — or which document to open first. `AGENTS.md` is the
de facto entry point and is written for agents: it opens with a tone-source policy and
never explains the project. See section E.

### C2. The blast radius of the pending slot writes is unanalysed for P06-P40

**Status: APPLIED.** `presets/library.md` has a `### Slot references are live, and P06–P40 have never been read` section with the affected-preset table and the read-only audit as a stated precondition for the first slot write. The audit itself has not been run — the pedal is unplugged.

**Severity:** high

`AGENTS.md` Preset Safety Rule 2 states the principle: presets reference amp and IR slots
by number, so replacing a slot changes every preset that points at it. The principle is
then applied to exactly one preset, P41.

The flash reads show the exposure is real. P01 currently points at IR slot 11
(`11FD_TW1980`), and `library.md` schedules slot 11 to become `11MR_1960VB`, a Marshall
1960 cab. P03 points at IR slot 5 (`5HIFI_OK`), scheduled to become `5FD_DLX_C12K`. For
P01-P05 this does not matter, because they are being rewritten anyway. For P06-P40 it does:
35 presets have never been read, are not mentioned in any document, and will silently
change the moment amp slots 2-20 and IR slots 2-6 and 8-20 are written.

The audit is cheap and read only: `device names` plus `device preset N` for 1 through 41
gives every preset's amp and cab slot index without loading anything.

**Recommendation:** make that audit a precondition in `library.md` before the first slot
write, and record the resulting slot-to-preset reference table.

### C3. The evidence base lives in temp directories

**Status: APPLIED IN PART.** `midi_transport.py`, `validate.py`, `base128_ref.py` and `amx.py` are committed under `docs/reverse-engineering/reference/`, and all seven raw logs under `docs/reverse-engineering/logs/`. **Still OPEN:** the library backup tarball is still in a session-scoped temp directory. `presets/library.md` records its absolute path and size and says to move it.

**Severity:** high

Three artefacts that the documents depend on are outside the repository, in session-scoped
directories under `/private/tmp/claude-501/` that are purged:

- `scratchpad/proto/midi_transport.py` — the only module that has ever transmitted to this
  pedal. `STATUS.md` attributes every "verified on hardware" claim to it and explicitly
  says `transport.py` in the repository is an unverified rewrite of it. If it is lost, the
  provenance of the hardware claims cannot be re-checked.
- `scratchpad/proto/base128_ref.py` — the 56/56-check reference implementation.
  `protocol-algorithms.md` cites it by absolute path, and that path currently points into a
  different session's scratchpad than the one that wrote the document.
- `M-EFCS-library-before-20260828-041029.tgz` — the only restore point for the 210
  pre-existing IRs and 15 pre-existing captures. `library.md` line 56 gives no path at all,
  only "in the session scratchpad". It is currently at
  `/private/tmp/claude-501/-Users-mendong-Documents-black-box--claude-worktrees-blackbox-presets-ir-setup-d4cb38/e540b214-9e36-4e96-abd6-017d7cf0c2eb/scratchpad/backup/`,
  3,525,756 bytes, verified to contain 15 `ampFile`, 210 `cabFile` and 14 `dsFile` entries.

The raw byte logs themselves are safe — they are in `device-validation.md` and in
`tools/blackboxctl/tests/fixtures/device_frames.py` — so the repository's rule about never
deleting a raw byte log is not yet violated. The tooling and the backup are one cache sweep
from gone.

**Recommendation:** commit the two Python files under `tools/blackboxctl/reference/` or
`docs/reverse-engineering/reference/` with a note that they are the predecessor artefacts,
not maintained code. Move the tarball somewhere durable and record its absolute path and
size in `library.md`.

### C4. The library install is not reproducible

**Status: APPLIED IN PART.** `presets/library.md` now states plainly that the install is not reproducible from this repository and why. **Still OPEN:** no manifest of the 107 installed files, and no archived copy or hash of the pack.

**Severity:** high

`library.md` names the source as `ANN_Captures_IRs_V16.8.zip`, 44.3 MB, from a Google Drive
folder. No copy exists on this machine — `~/Downloads` and every scratchpad were searched.
There is also no manifest recording which of the 24 captures and 83 IRs came from the pack
and which did not. If the Drive link rots, the install cannot be reproduced and the
provenance of individual files cannot be re-established.

**Recommendation:** record a manifest of the 107 installed files with sizes and hashes, and
either archive the pack alongside the backup from C3 or state plainly that the install is
not reproducible without a re-download.

### C5. The protected preset cannot be restored from the document that protects it

**Status: APPLIED.** `AGENTS.md` §5 now carries P41's full 92-byte flash image and its decode, citing `device-validation.md` STEP 6c.

**Severity:** medium

`AGENTS.md` `## Existing Known-Good Preset` lists eight values for P41. The 2026-08-28
flash read produced the complete 92-byte image and roughly thirty decoded fields. Present
in the decode and absent from `AGENTS.md`: FX is `Compress` and enabled; AMP Level 70,
Bass 40, Mid 62, Treble 60; CAB Level 75, Low Cut 26, High Cut 100; MOD Speed 20, Depth 22;
REV Decay 25, HPass 60, LPass 55, Depth 15; block routing `AMP, CAB, MOD, REV, FX, DLY`.

The eight values that are listed all match the decode, so nothing is wrong — the record is
just incomplete, and it is the record a reader is told to protect.

**Recommendation:** copy the full P41 decode and the 92-byte hex image into
`AGENTS.md` or into a `presets/p41-wonderwall-live.md`, citing `device-validation.md`
STEP 6c.

### C6. There is no single current-device-state page

**Status: OPEN, mitigated.** No `presets/device-state.md` was created. `AGENTS.md` §1 is now the single summary of device state and links out for detail rather than restating slot maps, and the root `README.md` has a `## Current state` section. The done-versus-pending split is still written in two places — see D5.

**Severity:** medium

Answering "what is on the pedal right now?" requires five documents: `AGENTS.md` Current
State, `library.md` Device write log, `hana.md` Superseded (which does not say it is live —
see A4), `boulevard-of-broken-dreams.md` (which says unknown), and `device-validation.md`
(the only place anything was actually measured). The done-versus-pending split is written
twice, at `AGENTS.md` line 161 and `library.md` line 202, and will drift.

**Recommendation:** one `presets/device-state.md` holding the slot maps as-built, the write
log, and per-preset current contents with the date and method each was established. Have
`AGENTS.md` link to it rather than restate it.

### C7. How to run the CLI from a cold start is not written down

**Status: APPLIED.** `tools/blackboxctl/README.md` now states `requires-python >= 3.10`, that `pip install -e .` is required rather than a plain `pip install .` and why, and that `pytest` is neither vendored nor a dependency. `AGENTS.md` §7 carries the `--library-root` caveat.

**Severity:** medium

`README.md` covers `python -m blackboxctl --help` and `pip install -e .`. Not stated
anywhere:

- `requires-python >= 3.10` (it is in `pyproject.toml` only).
- `library diff` finds `presets/library.md` via
  `Path(__file__).resolve().parents[3] / "presets" / "library.md"` in `library.py:306`, so
  it works in place and under `pip install -e .` but breaks under a plain `pip install .`.
  README's "or install the console script" reads as if either would do.
- `pytest` is not vendored and is not installed for the interpreter on `PATH` here, so
  `python -m pytest` as written in README fails on a fresh machine.
- The default `--library-root` is the M-EFCS sandbox path, which means `library list` and
  `library diff` reach outside the repository by default.

### C8. The no-writes posture is not stated as a project rule

**Status: APPLIED.** Stated in `AGENTS.md` §1 and §2, in the root `README.md`, and as hard rule 1 in `docs/reverse-engineering/README.md`. The GUI-driving and monitoring sections in `AGENTS.md` remain, framed as procedure for when writing resumes.

**Severity:** medium

The working rule for the current phase is that nothing is sent to the pedal, not even
reads, and that the M-EFCS container is read only. `AGENTS.md` says the opposite by
implication: it documents cliclick GUI-driving and a GarageBand monitoring path as live
procedure and its Preset Workflow ends "write to the device". `STATUS.md` records that the
pedal is unplugged but frames that as a blocker on the CLI, not as a policy.

**Recommendation:** state the current phase and its constraints at the top of `AGENTS.md`,
and mark the GUI-driving and monitoring sections as procedure for when writing resumes.

### C9. No repository-level licence or notice

**Status: APPLIED IN PART.** The root `README.md` has a `## Licensing and attribution` section and `docs/sources.md` is the full inventory. **Still OPEN:** there is no top-level `LICENSE` file, so the status of `AGENTS.md`, `presets/` and `docs/superpowers/` is still undefined by a licence file.

**Severity:** low

`tools/blackboxctl/` has `LICENSE` (GPL-3.0) and `NOTICE`. The reverse-engineering
documents each carry their own provenance and attribution section for CC BY-SA 4.0
upstreams, which is good. The repository as a whole has no `LICENSE`, so the status of
`AGENTS.md`, `presets/` and `docs/superpowers/` is undefined, and the CC BY-SA share-alike
obligation on the derived documents is stated only inside the documents themselves.

### C10. No stated next step for the preset work

**Status: APPLIED.** `presets/library.md` has a `## Next steps, in order` section.

**Severity:** low

`STATUS.md` has an excellent "single cheapest next step" section for the protocol work.
There is no equivalent for the preset work, whose actual next steps are now identifiable:
read P02, P04 and P05 read only to settle A8; audit P06-P40 slot references per C2; then
write the amp and IR slots; then the presets.

---

## D. Duplication

**Status: all five still stand, and all five are benign today** — every copy agrees with
every other copy, which is what the consistency pass checked. Nothing was consolidated,
because the single-source rule below depends on a `presets/device-state.md` that was not
created (C6). The mitigation actually applied is narrower: `AGENTS.md` §1 links to
`presets/library.md` for the slot maps and the write log instead of restating them, and its
§8 install steps end with a pointer to `presets/library.md` for the detail.

| # | What is duplicated | Where | Severity | Status |
| --- | --- | --- | --- | --- |
| D1 | The library install procedure, near-verbatim in four numbered steps | `AGENTS.md` §8 and `library.md` `Install procedure` | medium | **OPEN** — both copies remain and agree; `AGENTS.md` §8 now points at `library.md` for the detail |
| D2 | Device and app identity: M-EFCS `3.5.2615` / `3052615`, label `BLACKBOX v20`, 20 amp + 20 IR slots, PC-restore note | `AGENTS.md`, `library.md`, `hana.md`, `boulevard-of-broken-dreams.md` — four copies, all agreeing today | medium | **OPEN** — still four copies; re-checked, all four agree, and all four now qualify `BLACKBOX v20` as the editor's product label rather than a firmware version |
| D3 | Capture-handling rules | `AGENTS.md` and `library.md` `Working rules for capture-based presets` | medium | **APPLIED** — `AGENTS.md` no longer restates the rules; it points at `library.md` as the single copy |
| D4 | The safety-model paragraph | root `README.md` `## Safety model`, `tools/blackboxctl/README.md` `## Safety model` and `STATUS.md` `## Safety model` | low | **OPEN** — three copies, deliberately at three altitudes: the root summarises in five lines and links to the CLI's, which is the detailed one; `STATUS.md`'s is the honesty record. They agree |
| D5 | The pending-writes list | `AGENTS.md` §1 and `library.md` `## Device write log` | low | **OPEN** — both copies remain and agree. The root `README.md` adds a third, also agreeing |

The single-source rule that resolves all five: `library.md` owns the library and the slot
maps, a new `presets/device-state.md` owns what is on the pedal, `STATUS.md` owns the CLI's
honesty, and `AGENTS.md` links rather than restates.

---

## E. Navigation

**Status: APPLIED IN PART.** What was done: the root `README.md` was written and is the
entry point; `docs/reverse-engineering/README.md` was written as the directory index with
the consolidated confidence summary; `docs/reverse-engineering/reference/` and
`docs/reverse-engineering/logs/` were created; `tools/blackboxctl/README.md` now links back
to the root. What was **not** done, so the tree below is a proposal and not a description:
`presets/device-state.md` and `presets/p41-wonderwall-live.md` do not exist (C6, C5 —
P41's full image went into `AGENTS.md` §5 instead), `docs/superpowers/` was **not** renamed
to `docs/history/` and the four files keep their original names, and there is no top-level
`LICENSE` (C9). Links in the tree below that point at `presets/device-state.md` or
`docs/history/` do not resolve.

There is no top-level `README.md` and no ordering between the four bodies of work. Proposed
structure.

### Root

```
README.md          ← new. The entry point for a person.
AGENTS.md          ← trimmed. The entry point for an agent.
LICENSE            ← new, or a licence statement inside README.md.
presets/
docs/
tools/
```

`README.md`, about one screen, in this order:

1. What this is: a workspace for one guitarist's M-VAVE BlackBox — per-song preset designs,
   a capture and IR library map, protocol reverse-engineering documentation, and a
   read-only CLI.
2. Current state in three lines: the library is installed, one IR slot is written, the
   remaining slot and preset writes are pending, and the pedal is currently disconnected.
3. Where to start, by intent:
   - "I want a tone for a song" → `presets/`
   - "I want to know what is on the pedal" → `presets/device-state.md`
   - "I want to install captures or IRs" → `presets/library.md`
   - "I want to talk to the pedal" → `tools/blackboxctl/README.md`, then `STATUS.md`
   - "I want to know how the protocol works" → `docs/reverse-engineering/README.md`
   - "I want to know why it was built this way" → `docs/history/`
4. The hard rules, once: never write to the pedal in the current phase, never modify the
   M-EFCS container, never overwrite P41, never delete a raw byte log.
5. Licensing in two lines: the CLI is GPL-3.0, the protocol documents are CC BY-SA 4.0
   derivatives, and both carry their own attribution.

`AGENTS.md` keeps only what an agent needs that a person does not: the tone-source policy,
the preset safety rules, the preset workflow, the GUI-driving mechanics and their
hard-won gotchas, and the current-phase constraints. Everything factual — device identity,
library location, install procedure, slot maps, pending work — becomes a link.

### presets/

```
presets/
  library.md                    capture and IR library, install, slot maps, working rules
  device-state.md               NEW. What is on the pedal, per slot and per preset, with
                                date and method for each. Absorbs the write log, the
                                pending list, and the P41 full image.
  p41-wonderwall-live.md        NEW, or a section of device-state.md. The protected preset,
                                complete, restorable.
  hana.md
  boulevard-of-broken-dreams.md
```

Each song file keeps the same three-part shape — historical record, current device
contents, capture-based target — with the middle part correctly labelled per A4.

### docs/

```
docs/
  reverse-engineering/
    README.md                   NEW. What the five documents are, which is authoritative
                                for what, and which claims are still unresolved.
    protocol-spec.md
    protocol-algorithms.md
    device-validation.md
    capture-format-spec.md
    official-docs.md
    reference/                  NEW. base128_ref.py and midi_transport.py, preserved per C3.
  history/                      RENAMED from superpowers/. Banner on every file per A1.
    2026-07-20-hana-presets-plan.md
    2026-07-20-hana-presets-design.md
    2026-07-26-boulevard-presets-plan.md
    2026-07-26-boulevard-presets-design.md
  staleness-register.md         this file
```

The `docs/superpowers/` name describes the tool that produced the files, not their content,
and it is the reason they read as current intent. `docs/history/` fixes that at the path
level.

### tools/

Unchanged. `README.md` is how to use it, `STATUS.md` is what to believe, `NOTICE` and
`LICENSE` are the obligations. The one addition is a line in `README.md` pointing back to
the root `README.md` so the CLI is not an island.
