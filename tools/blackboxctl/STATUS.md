# blackboxctl — status

Last updated: 2026-08-28. Read this before trusting any claim in the source.

**The pedal was NOT connected while this status was written.** CoreMIDI reported
0 sources and 0 destinations, `MIDIGetNumberOfDevices() == 6` with
`USB Composite Device` / `Jieli Technology` flagged `kMIDIPropertyOffline == 1`,
and `system_profiler SPUSBDataType` enumerated no Jieli device. Everything below
labelled "hardware" therefore comes from the single validation session of
2026-08-28 recorded in
[`docs/reverse-engineering/device-validation.md`](../../docs/reverse-engineering/device-validation.md),
not from a live read taken today.

---

## Works today, verified on hardware

Verified in the 2026-08-28 session, by the predecessor module now preserved at
`docs/reverse-engineering/reference/midi_transport.py` (it was written to a
session-scoped scratchpad that no longer exists). Every command in that session
was read-only; no `00 59 22` write frame was ever transmitted.

| Capability | How it was verified |
| :--- | :--- |
| Base-128 codec | 340-byte SysEx from the device decoded to a checksum-valid 295-byte frame; a second, independently sourced implementation agreed bit for bit on 299 random buffers and on all 13 captured messages |
| Frame model `magic \| length LE16 \| space LE16 \| address LE32 \| size LE24 \| payload \| cs` | fits 7 transmitted requests and 7 unique reply frames with no exceptions |
| Inbound checksum sums from **offset 5** | offset 5 validates 7/7 unique replies, offset 4 validates 5/7, failing on exactly the two name blocks (`byte[4] == 0x01`) |
| All four read commands | the pedal answered every one; the byte literals are locked in `tests/test_frames.py`. Three counts are all correct and are not the same count: **four read command shapes**, **five address bases**, **seven transmitted byte literals** (sixteen transmissions across the seven preserved logs) |
| 92-byte preset memory map | seven P41 values known independently from the M-EFCS GUI (amp, gain, cab, chorus mix, reverb mix, delay off, volume) all matched the decode |
| `address = preset_index * 92`, 0-based | flash index 2 returned a payload byte-identical to the live RAM dump, and preset-sync reported the active preset as `0x02` |
| 20 amp + 20 IR slot names, 14-byte stride | all 40 read back; the 9 already known from the GUI matched character for character |
| The device emits unsolicited `0x20000000` frames | six arrived unrequested in the end-to-end run (`logs/log_all.txt`: one during the CAB-name read, five during the flash-index-2 read), and more in the per-step runs (`log_flash.txt` five, `log_generic.txt` two); replies must be routed by address, not arrival order |

**Verified offline in this tree, 2026-08-28:** `python -m pytest` reports
`221 passed` (Python 3.14.3, pytest 9.1.1, installed into a throwaway virtualenv
because no `pytest` is present on this machine's `PATH`). An earlier revision of
this line quoted 221 from the untracked `.pytest_cache`; the figure is now from a
real run. The fixtures are the
real recorded bytes, so `tests/test_decode_preset.py` replays P01, P03, P41 and
the live RAM dump against the values recorded from the GUI, and
`tests/test_device_replay.py` runs the whole `device` command path —
request, reassembly, address demultiplexing, parse, decode, render — against
those same recorded replies.

**Verified today against the user's live files, read-only:** all 39 `ampFile`,
293 `cabFile` and 14 `dsFile` entries parse without error (previously 6 amp and
1 IR were refused), and `library diff` reports `ok=38 reserved=2` against
`presets/library.md`.

## Verified on hardware 2026-08-28, second session

The pedal was reconnected and this exact module was exercised against it. Three things
that the table below used to list as unverified are now closed.

- **The send path and the CoreMIDI receive registration are verified.** `MIDISendSysex`,
  the `MIDISysexSendRequest` struct, the completion wait, `MIDIInputPortCreate`,
  `MIDIPortConnectSource` and endpoint resolution by manufacturer all work. `device sync`,
  `device names`, `device dump` and `device preset N` were run against the real pedal.
- **`PRESET_COUNT = 80` is confirmed**, no longer a hypothesis. Flash indices 0–79 all
  return a decodable 92-byte image; index 80 is refused. Indices 41–79 hold unused
  defaults: amp slot 1, IR slot 1, volume 85.
- **A crash in this module was found and fixed.** `open()` was not idempotent.
  `open_device()` returns an already-opened instance, and the CLI then used it as a context
  manager, so `__enter__` called `open()` a second time; that replaced the
  `ctypes.CFUNCTYPE` read trampoline and let the first one be collected while the first
  input port — leaked, never disposed, still connected to the source — could still invoke
  it. CoreMIDI called freed code and every `blackboxctl device …` command died with SIGBUS
  (exit 138) as soon as the pedal replied. `open()` now returns early when already open.
  Regression test: `tests/test_transport_reopen.py`. This is exactly the class of defect
  the "implemented but unverified" table existed to warn about.

Still true after that session: **nothing has ever been written to this pedal.** Every
command sent was a `00 59 23` read.

## Implemented but unverified

| Thing | Why it is unverified |
| :--- | :--- |
| **Real-time byte filtering** (`0xF8`–`0xFE` inside a SysEx) | Permitted by the MIDI spec, never observed from this pedal. HYPOTHESIS-level hardening, tested only synthetically. |
| **Every write path** | See below. Nothing has ever been written to this pedal. |
| **Whether the device accepts an `am2converter` `00 00 32 00` magic** | Untested. `am2.go:14`'s `InitData` is literally `{0, 0, 50, 0, ...}` and matches those 60 header bytes exactly, so the header was *written* that way, not corrupted — but whether M-EFCS/V19 loads it is unknown. Treated as a warning, not a refusal, because a hard refusal would overstate the evidence and would block 4 of the files `presets/library.md` requires. |
| **Whether a V19 pedal tolerates a 7868-byte AM4 record, or a 32-bit-float IR** | Untested. Both are warnings. The float case is not speculative in one direction: the *source* file for the pedal's own CAB slot 10, `10SoldSC412.wav`, is 32-bit IEEE float, so refusing that format would condemn a file the vendor itself ships. Note the limit of that argument — the on-device `CAB` record is 24-bit PCM (`capture-format-spec.md` §7.1), so this says the vendor's source set is non-conforming, not that the pedal runs float. See `presets/library.md`, "What that does and does not prove". |
| **`ACK_FRAME`** | Documented as 8 bytes and never observed, because no write was ever sent. An earlier revision of this line said it "does not fit the field model at all" and guessed at an upstream transcription error. That was wrong: the 8-byte ACK parses cleanly under the general frame grammar (`cmd 0x00`, length 1, payload `00`, checksum `FF` — `protocol-spec.md` §2.5), and the 15-byte minimum this tool enforces is the `0x22`/`0x23` **specialisation**, not the grammar. The consequence is real but latent: `parse_frame` would reject a genuine ACK. Unreachable today because no write path can transmit. See contradiction-register C05. |

## Blocked, and on what

1. **All device commands** are blocked on the pedal being plugged in. Nothing
   else. Reconnect it over USB and `python -m blackboxctl device endpoints`
   should show a source and a destination with manufacturer
   `Jieli Technology`.
2. **Re-verifying `transport.py` itself** is blocked on the same thing. Until it
   happens, treat every "CONFIRMED on the wire" claim attached to this module as
   inherited from its predecessor.
3. **Every write path** is blocked on a deliberate decision, not on a missing
   feature. See below.
4. ~~**`PRESET_COUNT`** is blocked on one read~~ — **done 2026-08-28.** Index 79 answers,
   index 80 is refused, so the count is 80.

## Safety model

Every frame that reaches CoreMIDI passes `protocol.assert_read_only`, which
accepts only the `00 59 23` read header with an empty payload, a size of at most
280 bytes, a valid checksum, and an address wholly inside one of the five
regions actually read from this pedal — the flash preset array, live RAM, the
current-preset register, and the two name tables; the documented write triggers
at `0xE0000000` and `0xF0000000` are excluded even for reads, because the
firmware's behaviour on a read at a trigger register is untested. Building a
write frame requires a `protocol.WriteConsent` capability object naming one
specific `WRITE_PATHS` key with `confirmed_by_user` and `accept_unverified` set,
plus `allow_flash` for anything touching the preset array, and
`BlackBox.send` then re-validates the wire bytes independently of whoever built
them — refusing any `00 59 22` frame whose length low byte is `0x64` or whose
address falls in the flash array without `allow_flash`, and refusing outright
any write path whose `hardware_confirmed` is False. Since every write path is
currently `hardware_confirmed=False`, **no write frame can reach the wire at
all**, from the CLI, a script, or a REPL; `tests/test_no_write_path.py` asserts
this and also asserts that `cli.py` contains no reference to any write builder.
Separately, the three commands with real side effects on disk — `library
install`, `library restart-editor` and `rename --in-place` — are dry runs by
default and require `--yes`, and `install --force` copies the incumbent file to a
timestamped `.bak` before replacing it.

**One read-only command is deliberately excluded.** Opcode `0x11`, the device
name/version query (`00 59 11 00 00 00 FF`), carries a zero-length payload and is
harmless, but `assert_read_only` accepts only the `00 59 23` header, so the gate
refuses it. That is a deliberate narrowing to the frame shapes this pedal has
actually answered, not an oversight — recorded here because `0x11` is also the
cheapest way to settle the pedal's firmware version, which is unresolved. See
`docs/reverse-engineering/contradiction-register.md` C30 and
`docs/reverse-engineering/protocol-algorithms.md` §8 item 8. Widening the gate is
a code change and has not been made.

## The single cheapest next step to unlock verified flash writes

**Send one Change Knob to live RAM and read it back.** Nothing else.

```
write:  00 59 22 0A 00 00 04 20 00 00 10 02 00 00 <lsb> <msb> <cs>
        i.e. build_frame(MAGIC_WRITE, SPACE_PARAM, ADDR_LIVE_RAM + 0x20, 2, value)
read:   00 59 23 08 00 00 04 00 00 00 10 5C 00 00 8F   (cmd_ram_dump)
```

Why this one:

- It is the **only** experiment that resolves the single question every other
  write path depends on: is the RAM write address `0x10000000 + dump_index`
  (identity) or `+ 2`? Everything else — toggle, model, routing, load-preset and
  ultimately flash save — is the same addressing question with a different
  payload.
- It is the **least destructive write in the protocol**. It touches live RAM,
  not flash. Byte `0x20` is AMP Gain, a single knob on the currently loaded
  preset. It is not persisted unless something explicitly saves, and the
  original value is known beforehand from a RAM dump — so it is trivially
  reversible by writing the old value back.
- It is **self-verifying**: read the RAM dump before, write, read after. If byte
  `0x20` changed to the value sent, the identity mapping is CONFIRMED and
  `WRITE_PATHS["set-knob"].hardware_confirmed` can be set to True. If byte
  `0x22` changed instead, the `+2` rule is right and every write address in this
  codebase is wrong by two — which is exactly the failure you want to discover
  on a RAM knob rather than on a flash slot.

Procedure:

1. Reconnect the pedal. Confirm `device endpoints` sees it.
2. **Get the user's explicit consent.** This is a write. It is forbidden without
   it.
3. Note the preset currently loaded (`device sync`) and dump it
   (`device dump`) — record byte `0x20`, and back up the whole 92-byte image.
4. Choose a preset that is NOT P41. P41 "Wonderwall Live" is protected.
5. Write the knob, re-dump, compare, then write the original value back.
6. Record the result in `device-validation.md`, and only then flip
   `WRITE_PATHS["set-knob"].hardware_confirmed` to True.

Flash writes stay off after that. `restore` needs its own consent, its own
verification on a slot the user has explicitly designated as expendable, and a
tested read-back-and-restore path first. There is no shortcut from "one knob
moved" to "rewriting a flash slot is safe."
