# Fujii Kaze `Hana` BlackBox Presets Design

## Goal

Create three complementary guitar-accompaniment presets for Fujii Kaze's `Hana` on an HSS Strat-style guitar and store them in M-VAVE BlackBox slots P01, P02, and P03.

## Safety and Source State

- Inspect and document the existing contents of P01, P02, and P03 before changing them.
- Do not change the protected P41 `Wonderwall Live` preset.
- Treat the live M-EFCS model names and parameter controls as authoritative because firmware and editor versions can differ.
- If a named model below is unavailable, choose the closest model in the same amp/cab family and record the substitution.

## Shared Guitar Setup

- Guitar: HSS Strat-style guitar.
- Default pickup: neck single-coil for P01 and P02.
- P03 may use neck+middle if the guitar has the standard five-way positions; otherwise use the middle single-coil.
- Start with guitar volume at 10 and tone at approximately 7-8.
- Match preset output levels by ear before comparing tone. Louder must not be mistaken for better.

## P01: Hana Warm Clean

Purpose: the default tone for soft chord voicings and arpeggios that should blend into the original synth-led arrangement.

- Dynamics: light compressor, enough to even arpeggios without flattening the pick attack.
- Amp: American/Fender-style clean model with low gain.
- Cab: open-back 1x12 or 2x12 clean cab.
- EQ: controlled bass, warm mids, softened upper treble and presence.
- Modulation: very light chorus, audible mainly as width rather than pitch wobble.
- Delay: short, quiet delay with low feedback.
- Reverb: medium plate or hall, wide but not washed out.
- Gain target: fully clean under normal picking, only a hint of edge under the hardest attack.

Starting ranges on a 0-100 scale:

- Compressor sustain: 30-40; level: unity.
- Amp gain: 20-28; bass: 42-48; middle: 50-56; treble: 44-50; presence: 35-42.
- Chorus mix: 8-12.
- Delay time: 90-120 ms; mix: 5-8; feedback: 0-8.
- Reverb mix: 18-24.

## P02: Hana Edge

Purpose: a more present chorus or live-band accompaniment tone with restrained breakup.

- Dynamics: lighter compression than P01.
- Drive: transparent low-gain drive if needed; keep drive low and output near unity.
- Amp: British chime/VOX-style amp at edge of breakup.
- Cab: matching open-back 2x12 British cab.
- EQ: less bass than P01, forward low mids, smooth treble.
- Modulation: off or nearly off.
- Delay: short room/slap support with low mix.
- Reverb: compact room or plate.
- Gain target: clean when picked lightly and softly gritty on accented chords.

Starting ranges on a 0-100 scale:

- Compressor sustain: 20-30; level: unity.
- Drive gain: 8-14; tone: 42-48; level: unity, when used.
- Amp gain: 32-40; bass: 38-44; middle: 54-62; treble: 46-52; presence: 40-46.
- Delay time: 110-140 ms; mix: 6-10; feedback: 0-8.
- Reverb mix: 12-18.

## P03: Hana Acoustic Clean

Purpose: a bright, percussive tone for solo vocal accompaniment where one guitar needs to fill more space.

- Dynamics: firmer compression than P01.
- Amp: acoustic simulator if available; otherwise the cleanest neutral amp model at very low gain.
- Cab: neutral/full-range or bright open-back clean cab, whichever sounds less boxy.
- EQ: tight bass, slightly scooped low mids, clear upper mids and treble without ice-pick attack.
- Modulation: optional minimal chorus.
- Delay: off.
- Reverb: short room or plate.
- Gain target: completely clean with crisp chord separation.

Starting ranges on a 0-100 scale:

- Compressor sustain: 45-55; level: unity.
- Amp gain: 10-18; bass: 38-44; middle: 42-48; treble: 56-64; presence: 48-56.
- Chorus mix: 0-6.
- Delay: off.
- Reverb mix: 12-18.

## Validation

For each slot:

1. Confirm the intended slot is selected before editing.
2. Save the preset and re-open the slot to confirm every value persisted.
3. Compare at matched output volume against the `Hana` instrumental or original track.
4. Test soft arpeggios, full chords, and hard accents for unwanted clipping, harshness, or excessive ambience.
5. Switch away from the slot and back to it to verify persistence.
6. Record the final model names and exact values in `presets/hana.md`.

## Success Criteria

- P01 is the natural default for the original arrangement.
- P02 adds chorus/live-band presence without becoming a rock distortion preset.
- P03 supports singing with one guitar and preserves clear chord separation.
- P01-P03 persist on the device, are close in perceived loudness, and can be reproduced from the repository documentation.
- P41 remains unchanged.
