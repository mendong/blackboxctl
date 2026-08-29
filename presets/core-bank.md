# BlackBox P01–P12 core bank

Written and byte-verified: 2026-08-29. The pedal does not store these descriptive names;
this file is the slot-to-role authority. Exact machine-readable values are in
[`specs/`](specs/) and the rendered 92-byte images are in [`rendered/`](rendered/).

The 92-byte images under [`base-before-20260829/`](base-before-20260829/) are the
pre-migration source for each slot. They serve two separate purposes: exact restoration
of the former P01-P12 contents, and preservation of reserved bytes while each declarative
spec is rendered. `tests/test_preset_bank.py` regenerates all twelve outputs and requires
byte-for-byte equality with `rendered/`.

## Design basis

P01–P05 preserve the two existing song workflows, now using captures and matching IR
families. P06–P12 fill distinct reusable playing roles for the owner's HSS Strat rather
than trying to cover genres with arbitrary factory patches. Clean captures start with
higher output and moderate gain; driven captures start closer to the middle. AMP and IR
families are paired first, then compressor/boost, EQ, modulation, delay, reverb, and final
level are set in that order. Community combinations are starting evidence, not universal
answers.

Spatial effects are intentional. Rhythm presets keep them short and low; chime and lead
presets use them as part of the role. P07's Autofilter and P09's Univibe are deliberate
character presets, while P10 stays tight with delay/modulation off.

| Slot | Working name | Pickup / role | AMP | CAB | Character |
| --- | --- | --- | --- | --- | --- |
| P01 | Hana Warm Clean | neck single; song clean | 2 `2FD65_DLX` | 5 `5FD_DLX_C12K` | compression, light chorus, short delay, room |
| P02 | Hana Edge | neck single; accents | 12 `12VOX_CRUNCH` | 8 `8VOX_AC30_TB` | edge-of-breakup, analog delay, hall |
| P03 | Hana Acoustic Clean | middle / neck+middle | 20 `20AC_PREAMP` | 19 `19AC_D35` | acoustic body, hall, delay off |
| P04 | Boulevard Pulse Clean | bridge humbucker; verse | 13 `13JTM45` | 11 `11MR_1960VB` | tremolo pulse, room, delay off |
| P05 | Boulevard Chorus Crunch | bridge humbucker; chorus | 15 `15JCM800_OD` | 12 `12MR_JCM800` | boost, forward mids, tight room |
| P06 | General Clean | neck single; neutral clean | 3 `3FD_TWIN` | 4 `4FD_TWIN57` | transparent compression, subtle chorus/space |
| P07 | Funk Clean | neck+middle; percussive | 7 `7CORYWONG` | 1 `1ML_BEST_IR` | fast compression, low mids, Autofilter |
| P08 | Chime Clean | neck+middle; open chords | 11 `11MATCHLESS` | 10 `10VOX_BLUE` | chorus, analog delay, larger hall |
| P09 | Marshall Edge | bridge humbucker; dynamic crunch | 13 `13JTM45` | 11 `11MR_1960VB` | low boost, Univibe, short delay |
| P10 | Rock Rhythm | bridge humbucker; tight rhythm | 15 `15JCM800_OD` | 12 `12MR_JCM800` | boost, delay/mod off, short room |
| P11 | BE100 Gain | bridge humbucker; modern gain | 17 `17BE100_OD` | 14 `14FRIEDMAN` | controlled boost, small delay/room |
| P12 | Ambient Lead | bridge humbucker; sustained lead | 1 `1BE100_C45` | 14 `14FRIEDMAN` | chorus, dual delay, hall |

## Write evidence and rollback

The active preset was moved outside the target bank to P80. P01 through P12 were then
saved individually with `blackboxctl device save`; each save preserved the incumbent
92-byte image under `~/.local/share/blackboxctl/rollback/` and compared the full flash
read-back with the rendered target. All twelve comparisons passed.

The exact twelve bases used for rendering are also retained in
[`base-before-20260829/`](base-before-20260829/). They are dated design/provenance inputs;
the checksummed 80-slot JSON backup in the recovery runbook remains the complete restore
authority.

This proves stored bytes and numeric slot references. It does not prove the sound. The
next pass is a matched-loudness listening session using the listed pickup positions. Tune
in this order: gain/dynamics, AMP EQ, CAB, modulation, delay, reverb, output volume.
