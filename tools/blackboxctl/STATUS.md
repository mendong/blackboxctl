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

Verified in the 2026-08-28 session, by the predecessor module
`scratchpad/proto/midi_transport.py`. Every command in that session was
read-only; no `00 59 22` frame and no command type `0x64` was ever transmitted.

| Capability | How it was verified |
| :--- | :--- |
| Base-128 codec | 340-byte SysEx from the device decoded to a checksum-valid 295-byte frame; a second, independently sourced implementation agreed bit for bit on 299 random buffers and on all 13 captured messages |
| Frame model `magic \| length LE16 \| space LE16 \| address LE32 \| size LE24 \| payload \| cs` | fits 7 transmitted requests and 7 unique reply frames with no exceptions |
| Inbound checksum sums from **offset 5** | offset 5 validates 7/7 unique replies, offset 4 validates 5/7, failing on exactly the two name blocks (`byte[4] == 0x01`) |
| All four read commands | the pedal answered every one; the byte literals are locked in `tests/test_frames.py` |
| 92-byte preset memory map | seven P41 values known independently from the M-EFCS GUI (amp, gain, cab, chorus mix, reverb mix, delay off, volume) all matched the decode |
| `address = preset_index * 92`, 0-based | flash index 2 returned a payload byte-identical to the live RAM dump, and preset-sync reported the active preset as `0x02` |
| 20 amp + 20 IR slot names, 14-byte stride | all 40 read back; the 9 already known from the GUI matched character for character |
| The device emits unsolicited `0x20000000` frames | 5 arrived unrequested during the flash-read step; replies must be routed by address, not arrival order |

**Verified today, offline, in this tree:** 221 tests pass. The fixtures are the
real recorded bytes, so `tests/test_decode_preset.py` replays P01, P03, P41 and
the live RAM dump against the values recorded from the GUI, and
`tests/test_device_replay.py` runs the whole `device` command path —
request, reassembly, address demultiplexing, parse, decode, render — against
those same recorded replies.

**Verified today against the user's live files, read-only:** all 39 `ampFile`,
293 `cabFile` and 14 `dsFile` entries parse without error (previously 6 amp and
1 IR were refused), and `library diff` reports `ok=38 reserved=2` against
`presets/library.md`.

## Implemented but unverified

| Thing | Why it is unverified |
| :--- | :--- |
| **`transport.py`'s send path** — `MIDISendSysex`, the `MIDISysexSendRequest` struct, the 2.0 s completion wait | This module is a **rewrite** of the one that produced the hardware logs. No log records *this* file transmitting anything. The struct layout and the read commands it builds are identical, but that is inheritance, not verification. |
| **`transport.py`'s CoreMIDI receive registration** — `MIDIInputPortCreate`, `MIDIPortConnectSource`, endpoint resolution | Same reason. The `MIDIReadProc` packet-walk *logic* is covered by synthetic `MIDIPacketList` buffers in `tests/test_transport_rx.py`; the CoreMIDI plumbing around it is not. |
| **Real-time byte filtering** (`0xF8`–`0xFE` inside a SysEx) | Permitted by the MIDI spec, never observed from this pedal. HYPOTHESIS-level hardening, tested only synthetically. |
| **`PRESET_COUNT = 80`** | Evidence is a vendor PDF and bbedit's `app.js:227`. The highest flash index ever read here is 40. Relabelled HYPOTHESIS. |
| **Every write path** | See below. Nothing has ever been written to this pedal. |
| **Whether the device accepts an `am2converter` `00 00 32 00` magic** | Untested. `am2.go:14`'s `InitData` is literally `{0, 0, 50, 0, ...}` and matches those 60 header bytes exactly, so the header was *written* that way, not corrupted — but whether M-EFCS/V19 loads it is unknown. Treated as a warning, not a refusal, because a hard refusal would overstate the evidence and would block 4 of the files `presets/library.md` requires. |
| **Whether a V19 pedal tolerates a 7868-byte AM4 record, or a 32-bit-float IR** | Untested. Both are warnings. The float case is not speculative in one direction: the pedal's own CAB slot 10 IR, `10SoldSC412.wav`, *is* 32-bit float, so refusing it would condemn a file the device is demonstrably running. |
| **`ACK_FRAME`** | Documented as 8 bytes, which is shorter than the confirmed 15-byte minimum, so it does not fit the field model at all. Never observed, because no write was ever sent. |

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
4. **`PRESET_COUNT`** is blocked on one read: try flash index 79 and index 80
   and see which answers.

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
