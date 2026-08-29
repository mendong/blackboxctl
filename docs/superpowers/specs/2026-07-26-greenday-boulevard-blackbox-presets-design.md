# Green Day `Boulevard of Broken Dreams` BlackBox Presets Design

> ## SUPERSEDED — HISTORY ONLY.
>
> This design specifies P04-P05 using the BlackBox's **built-in amp models**. That approach
> was abandoned on 2026-08-28 in favour of community capture files plus third-party IRs.
> The values here were written to the device on 2026-07-26, preserved as historical
> evidence, and replaced by the capture-based bank on 2026-08-29. Kept because it is the only
> record of why P04/P05 are a section pair and which two alternative approaches were
> rejected. Current design:
> [`presets/boulevard-of-broken-dreams.md`](../../../presets/boulevard-of-broken-dreams.md).
> Tone source policy: [`presets/library.md`](../../../presets/library.md).

## Goal

Create two section-specific accompaniment presets for Green Day's `Boulevard of Broken Dreams` on the connected M-VAVE BlackBox:

- P04: pulsing clean tone for the intro and verses.
- P05: full British crunch tone for the choruses.

The guitar is the previously documented HSS Strat-style guitar. Both presets start with the bridge humbucker, guitar volume 10, and guitar tone 7-8 so the player can change song sections with only the BlackBox footswitches.

## Approved Approach

Three approaches were considered:

1. **Section pair — approved:** P04 clean tremolo and P05 chorus crunch. This best covers the song's most recognizable contrast and makes live switching simple.
2. **Two gain levels:** mild and heavy British drive. This is simple, but loses the verse pulse that identifies the song.
3. **Studio-layer pair:** acoustic-like clean and wide high-gain rhythm. This reflects the layered record, but one guitarist cannot reproduce the pulsing electric part at the same time.

The user approved approach 1.

## Source and Device Grounding

- A Green Day rig rundown documents Armstrong's clean preamp and modified Marshall heads feeding Marshall 1960B cabinets with Vintage 30 speakers. This supports a clean Marshall-style P04 path and a higher-gain J900/1960-style P05 path: <https://www.premierguitar.com/videos/rig-rundown/green-day>
- Live M-EFCS inspection on 2026-07-26 confirmed the connected label `BLACKBOX v20`.
- The editor exposes `1J900_CL`, `9J900_DS`, and `2JVM_1960_57`, plus a `Tremolo` modulation model with `Speed`, `Depth`, and `Level`.
- P01-P03 contain the existing `Hana` presets. P41 remains the protected `Wonderwall Live` preset. None of those slots will be edited or saved.
- At the user's request, no restoration backup will be created for P04 or P05. The current slot identity and visible chain were inspected before editing only as a wrong-slot guard.

## P04: Boulevard Pulse Clean

Purpose: the recognizable clean pulse under the intro and verses, with enough midrange to avoid a glassy Strat-only sound.

- Pickup: bridge humbucker.
- Guitar: volume 10; tone 7-8.
- Total volume: 85.
- FX: `Compress`; Gate 10, Sustain 30, Attack 60, Level 50; enabled.
- AMP: `1J900_CL`; Gain 28, Level 70, Bass 45, Mid 62, Treble 55; enabled.
- CAB: `2JVM_1960_57`; Level 70, Low Cut 76, High Cut 18.0K; enabled.
- MOD: `Tremolo`; Speed 39, Depth 60, Level 50; enabled.
- REV: `Room`; Decay 25, Mix 12, HPass 65, LPass 50, Depth 25; enabled.
- DLY: disabled. Its stored model and inactive values do not affect the sound.

Playing target: the volume pulse must be clearly audible on sustained chords without fully chopping off the attack. The amp should remain clean under normal rhythm playing and add only a slight edge under hard accents.

## P05: Boulevard Chorus Crunch

Purpose: the wide, forceful chorus rhythm sound without turning into saturated modern metal.

- Pickup: bridge humbucker.
- Guitar: volume 10; tone 7-8.
- Total volume: 85.
- FX: `Boost`; Gate 20, Gain 35; enabled.
- AMP: `9J900_DS`; Gain 58, Level 65, Bass 45, Mid 68, Treble 57; enabled.
- CAB: `2JVM_1960_57`; Level 68, Low Cut 76, High Cut 18.0K; enabled.
- MOD: disabled.
- REV: `Room`; Decay 18, Mix 8, HPass 65, LPass 45, Depth 15; enabled.
- DLY: disabled.

Playing target: open-position power chords should feel larger and denser than P04, while chord changes remain distinct. The midrange stays forward because Green Day's rhythm sound is not a scooped-metal tone.

## Save and Verification

1. Reconfirm `BLACKBOX v20` and the selected slot immediately before each save.
2. Configure and save P04, switch to P05, then re-open P04 and compare all visible values and on/off states.
3. Configure and save P05, switch to P04, then re-open P05 and compare all visible values and on/off states.
4. Open P41 read-only and confirm the protected `Wonderwall Live` values remain unchanged.
5. Record the final reproducible values and persistence result in `presets/boulevard-of-broken-dreams.md`.
6. Leave the device on P04 so the user can begin with the intro/verse sound.

## Listening Check

M-EFCS can prove the write and persistence, but the user must make the final audible judgment with the connected guitar. At matched loudness:

- If P04 pumps too slowly or quickly, adjust Tremolo Speed first.
- If P04 sounds too chopped, reduce Tremolo Depth in steps of 5.
- If P05 is fizzy, reduce Treble before reducing Mid.
- If P05 is too saturated, reduce AMP Gain before disabling Boost.
- Adjust Level or total volume only after the gain and EQ are satisfactory.

## Success Criteria

- P04 and P05 persist with the exact intended model selections, values, and effect states.
- P04 clearly supplies the clean pulsing verse role.
- P05 supplies a mid-forward British chorus crunch and remains articulate.
- P01-P03 and P41 remain unchanged.
- The documentation separates editor persistence from the pending player listening check.
