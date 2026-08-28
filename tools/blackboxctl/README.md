# blackboxctl

A command line tool for the M-Vave BlackBox guitar amp modeller and the M-EFCS
file library on macOS. It reads the pedal over USB MIDI SysEx, decodes its
presets and slot names, and manages the capture and IR files that M-EFCS scans.

**Device access is read only.** There is no command in this tool that transmits
a state-changing frame to the pedal, and no flag that enables one. See
[Safety model](#safety-model).

This tool is one of four parts of a larger workspace. The repository entry point is
[`../../README.md`](../../README.md); the protocol it implements is documented in
[`../../docs/reverse-engineering/`](../../docs/reverse-engineering/README.md), and
[STATUS.md](STATUS.md) is what to believe about this tool specifically.

```
python -m blackboxctl selftest          # offline; touches nothing
python -m blackboxctl device names      # read the 20 amp and 20 IR slot names
python -m blackboxctl device dump       # read and decode the live preset
python -m blackboxctl library diff      # compare presets/library.md to disk
```

## License and attribution

blackboxctl is **GPL-3.0-or-later**. The full text is in [LICENSE](LICENSE); the
attribution obligations are in [NOTICE](NOTICE), and both are binding.

This is a derivative work. The protocol was not discovered here — it was
reverse engineered by the community, and this tool exists to validate that work
against one specific pedal and put a usable interface on it.

| Upstream | Author | License | What we use |
| :--- | :--- | :--- | :--- |
| [mvave-blackbox-ble](https://github.com/jvsobrinho/mvave-blackbox-ble) | Joel Victor | docs **CC BY-SA 4.0**, code **GPL-3.0** | the entire protocol description: transport, SysEx encapsulation, memory map, knob dictionaries |
| [mvave-blackbox-edit](https://github.com/jvsobrinho/mvave-blackbox-edit) | Joel Victor | **MIT** | the Base-128 codec reference, the model tables, the `isDynamic` distinction |
| [cuvave-midi](https://github.com/pferreir/cuvave-midi) | Pedro Ferreira | **GPL-3.0** | the Base-128 algorithm structure |
| [am2manager](https://github.com/walterwanderley/am2manager) | Walter Wanderley | **Apache-2.0** | the `.am2` / `.am3` capture header field names |

GPL-3.0 is not a default here: the reference logic is GPL-3.0 and the protocol
documentation is CC BY-SA 4.0, and those licences require it.

## Install

No dependencies beyond the standard library. macOS only for the `device`
commands; everything else is portable.

```sh
cd tools/blackboxctl
python -m blackboxctl --help            # run in place
pip install -e .                        # or install the console script
```

`requires-python` is **>= 3.10** (declared in `pyproject.toml` only). Use `pip
install -e .`, not a plain `pip install .`: `library diff` locates
`presets/library.md` by walking up from its own file, so a non-editable install
puts it outside the repository and the command fails.

## What it does

### `selftest`

Offline verification of the codec, the seven read-command literals, and the
read-only gate. Touches no hardware and no files. Run it first.

### `device …` — read only

| Command | What it reads |
| :--- | :--- |
| `device endpoints` | CoreMIDI sources and destinations, and whether a BlackBox is among them |
| `device sync` | the active preset id (4 bytes at `0x20000000`) |
| `device dump` | the live, currently sounding 92-byte preset, decoded |
| `device names` | the 20 amp capture names and 20 IR names (280 bytes each) |
| `device preset N` | stored preset `PNN` from flash, decoded, **without loading it** |

Endpoints are resolved by `kMIDIPropertyManufacturer == "Jieli Technology"`,
never by an integer ref — refs change across replug.

### `inspect`, `rename`, `decode`

`inspect` parses `.am2` / `.am2Data` / `.am3Data` captures and `.wav` IRs and
reports errors and warnings. `rename` edits a capture's 13-character header name
and can set the `AM` prefix on an `am2converter`-written magic. `decode` decodes
a 92-byte preset image from hex or a file, offline.

`rename` is a dry run unless you pass `--in-place --yes` (which keeps a `.bak`)
or `--output PATH`.

### `library …`

| Command | What it does |
| :--- | :--- |
| `library list` | list installed captures and IRs |
| `library diff` | compare `presets/library.md`'s slot maps against what is on disk |
| `library install FILES… --yes` | copy captures/IRs into the M-EFCS library |
| `library restart-editor --yes` | quit and relaunch M-EFCS so it rescans |

`install` and `restart-editor` are **dry runs by default**. Both have real side
effects outside this repository, and both are the point of the tool rather than
accidents:

> **`library install` writes into another application's sandbox container**,
> `~/Library/Containers/com.digAmp.dgAmp/Data/Documents/M-EFCS/{ampFile,cabFile}`.
> It only writes files you name, never touches `model/`, and with `--force` it
> copies the incumbent to a timestamped `.bak` before replacing it.
>
> **`library restart-editor --yes` quits M-EFCS with an AppleScript `quit`.**
> Any unsaved work in that GUI is lost, and the GUI may be in use by someone
> else at that moment. It exists because M-EFCS scans `ampFile` and `cabFile`
> exactly once at launch and keeps no index, so a restart is the only way to
> make a newly installed file appear.

## Safety model

In one paragraph: every frame that reaches CoreMIDI passes
`protocol.assert_read_only`, which accepts only the `00 59 23` read header with
an empty payload, a size of at most 280 bytes, a valid checksum, and an address
inside one of the five regions that have actually been read from this pedal —
the flash preset array, live RAM, the current-preset register and the two name
tables. The two documented write triggers (`0xE0000000` load-preset,
`0xF0000000` commit) are excluded even for reads, because the firmware's
behaviour on a read at a trigger register is untested. Building a write frame
requires a `protocol.WriteConsent` capability object naming a specific
`WRITE_PATHS` key, with `confirmed_by_user` and `accept_unverified` set, plus
`allow_flash` for anything touching the preset array; `BlackBox.send` then
re-checks the wire bytes independently of whoever built them and refuses any
write path whose `hardware_confirmed` is False. **Every write path is currently
`hardware_confirmed=False`, so no write frame can reach the wire at all** —
from the CLI, from a script, or from a REPL. `tests/test_no_write_path.py`
asserts that, including that `cli.py` contains no reference to any write builder.
File-modifying commands are separately dry-run by default and need `--yes`.

Run `python -m blackboxctl write-paths` to see each state-changing command and
the exact evidence for why it is disabled.

## What is confirmed and what is not

Every claim in this codebase is labelled CONFIRMED (observed on the owner's own
pedal, serial `4150353439333111`, with the method stated) or HYPOTHESIS. The
full transcript is
[`docs/reverse-engineering/device-validation.md`](../../docs/reverse-engineering/device-validation.md).
See [STATUS.md](STATUS.md) for the current, honest state.

**CONFIRMED on hardware** (one session, 2026-08-28, all seven commands
read-only):

- the Base-128 codec, the frame layout `magic(3) | length LE16 | space LE16 |
  address LE32 | size LE24 | payload | checksum`, and the address map;
- all four read commands, and a generic `read(space, address, size)` primitive
  that reproduces them byte for byte;
- the 92-byte preset memory map — seven independently known P41 values from the
  M-EFCS GUI all matched the decode;
- the 20 amp and 20 IR slot names, all 40 read back;
- inbound checksums sum from **offset 5**, not the published offset 4.

**HYPOTHESIS**, and honestly so:

- every write path. **No write frame of any kind has ever been transmitted to
  this pedal.** The RAM write address (`0x10000000 + dump_index`) is
  high-confidence but read-direction evidence only.
- `PRESET_COUNT = 80`. Its evidence is a vendor PDF and bbedit, not this pedal;
  the highest flash index ever read here is 40.
- whether the device accepts an `am2converter`-written `00 00 32 00` magic, an
  AM4 record, or a non-24-bit IR. All three are warnings, not refusals,
  precisely because they are untested.

**UNVERIFIED code**: `transport.py` is a rewrite of the module that produced the
hardware logs. Its own send path, packet parser and request/response matching
have never run against the pedal — see STATUS.md.

## Corrections to the upstream documentation

Recorded with evidence in `device-validation.md`. Anyone re-deriving this
protocol will hit all five:

1. **The worked Base-128 example is internally inconsistent.** Its raw and
   encoded lines do not correspond. Do not use it as a unit-test vector — you
   will conclude your correct encoder is broken. Use the logged 340-byte SysEx →
   295-byte frame pair in `tests/fixtures/device_frames.py` instead.
2. **Inbound checksums sum from offset 5.** Offset 5 validates 7/7 unique
   observed replies; offset 4 validates 5/7, failing on exactly the two name
   blocks — the only replies with `byte[4] != 0`.
3. **There is no "command type" byte.** Offsets 3–4 are a 16-bit little-endian
   length, always `payload + 8`. The `0x64` that looks like a Write Flash opcode
   in a RAM dump reply is just 92 + 8.
4. **"AMP names base address `90 18 01 00`" is a misparse.** The address is
   `0x90000000`; `18 01 00` is the 24-bit size, 280.
5. **`Write_Address = Dump_Index + 2` does not hold.** The mapping is the
   identity. (A uniform +2 shift would be arithmetically fine; it is refuted by
   the documented toggle/knob/routing literals, all three of which are the
   identity.)

## Tests

```sh
python -m pytest        # 221 tests, no hardware required
```

`pytest` is **not** a dependency of this package and is not vendored — install it
first (`pip install pytest`) or the command above fails on a fresh machine. The
figure was re-run on 2026-08-28 under Python 3.14.3 with pytest 9.1.1: `221
passed`. It is the same figure `STATUS.md` reports.

The fixtures are real bytes from the pedal, not synthesised: the seven
transmitted read commands, the seven unique reply frames, the 340-byte SysEx and
its 295-byte decode, and the four recorded preset images with their exact decode
tables. `tests/test_decode_preset.py` in particular replays P01, P03, P41 and the
live RAM dump against the values recorded from the M-EFCS GUI.
