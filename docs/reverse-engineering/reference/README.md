# Preserved predecessor artefacts — not maintained code

These three files are kept as evidence, not as a library. Nothing in the repository imports
them, they receive no tests and no maintenance, and the supported CLI is
`tools/blackboxctl/`. They were preserved because
[`device-validation.md`](../device-validation.md) and
[`protocol-algorithms.md`](../protocol-algorithms.md) cite them as the artefacts behind
their claims, and they were living in a session-scoped temporary directory that does not
survive.

| File | What it is |
| :--- | :--- |
| `midi_transport.py` | The CoreMIDI-over-ctypes transport used in the 2026-08-28 session. **This is the only module that has ever transmitted anything to this pedal.** Its `assert_read_only()` gate refuses any packet that is not one of the four read-only commands, and it was the gate in force for every frame in [`../logs/`](../logs/). |
| `validate.py` | The step-by-step driver that produced those logs (`codec`, `endpoints`, `ram`, `preset`, `cab`, `amp`, `flash`, `flash:N`, `all`). |
| `amx.py` | The reference capture parser behind [`../capture-format-spec.md`](../capture-format-spec.md) — parses a `.am2`/`.am2Data`/`.am3Data` record, splits the payload into named regions, repairs a corrupt magic, rewrites the name field, and splits a factory `*_ampCab.bin`. It implements that document's §9 validation rules, which are deliberately stricter than the ones `tools/blackboxctl` enforces. |
| `base128_ref.py` | An independently written Base-128 codec, derived from `cuvave-midi`'s own Rust test vectors rather than from the JavaScript editor the transport followed. It carries 56 executable assertions including every test vector in `protocol-algorithms.md` §2. It was used as the cross-check that agreed bit-for-bit with `midi_transport.py` on 299 random buffers and on all 13 captured SysEx messages. |

Two notes for anyone reading this code rather than the specification:

* `midi_transport.py`'s gate and its comments predate the frame-model reconciliation. It
  checks `raw[3] != 0x08` under the name "command type" and `raw[4:6]`/`raw[6]` under the
  name "routing". Those checks are *behaviourally correct* for the four read commands — the
  same bytes, the same accept/reject decision — but the field names are the retired upstream
  model, corrected in [`../protocol-spec.md` §2.7.1](../protocol-spec.md#271-the-upstream-published-wording--and-where-it-misleads).
  The names were left as they were transmitted; do not treat them as the field model.
* It carries two checksum helpers: `checksum()` sums from offset 4, which produces correct
  outbound commands (all have `byte[4] == 0x00`), and `checksum_rx()` sums from offset 5,
  added after the offset-4 form was refuted by the two name replies. The canonical
  definition is the payload sum from offset 6, which is identical to offset 5 on every frame
  in evidence. See `../protocol-spec.md` §2.3.

**Do not run these against the pedal.** The current phase sends nothing to the device.
