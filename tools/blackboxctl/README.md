# blackboxctl

A command line tool for the M-Vave BlackBox guitar amp modeller and the M-EFCS
file library on macOS. It reads and writes the pedal over USB MIDI SysEx,
decodes presets and slot names, converts IRs, prepares AMP records, and manages
the capture and IR files that M-EFCS scans.

All state-changing device commands are dry runs unless `--yes` is supplied.
Preset writes preserve exact rollback bytes; AMP/CAB writes require ACKs and
verify the permanent slot name. A lost final commit ACK must be reconciled by a
changed persistent name or is reported as uncertain. See [Safety model](#safety-model).

This tool is one of four parts of a larger workspace. The repository entry point is
[`../../README.md`](../../README.md); the protocol it implements is documented in
[`../../docs/reverse-engineering/`](../../docs/reverse-engineering/README.md), and
[STATUS.md](STATUS.md) is what to believe about this tool specifically.

```
python -m blackboxctl doctor            # protocol, MIDI, and M-EFCS readiness
python -m blackboxctl device names      # read the 20 amp and 20 IR slot names
python -m blackboxctl device dump       # read and decode the live preset
python -m blackboxctl backup extract-all backup.json ./presets
python -m blackboxctl library diff      # compare presets/library.md to disk
python -m blackboxctl device library-apply ../../presets/device-library.json
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

No third-party Python packages are required. The `device` commands are macOS-only;
preparing a new AMP record additionally calls the installed M-EFCS
`libamx_parser.dylib`. Other non-device commands are portable.

```sh
cd tools/blackboxctl
python -m blackboxctl --help            # run in place
pip install -e ".[dev]"                 # console script plus pytest/ruff
```

`requires-python` is **>= 3.10**. `library diff` first looks for
`presets/library.md` next to this checkout, then walks up from the current
working directory, so an editable install and a clone both work. A wheel
install still needs that document nearby or `--doc PATH`.

## What it does

### `selftest` and `doctor`

`selftest` is the offline protocol check: codec, the seven read-command
literals, and the read-only gate. Touches no hardware and no files.

`doctor` runs that check and then reports Python, MIDI transport, whether a
BlackBox source/destination pair is ready, the M-EFCS AMP helper dylib, and
the on-disk library root. It writes nothing. `--require-device` exits 3 when
no pedal is ready — useful in scripts.

### `device …`

| Command | What it reads |
| :--- | :--- |
| `device endpoints` | CoreMIDI sources and destinations, and whether a BlackBox is among them |
| `device sync` | the active preset id (4 bytes at `0x20000000`) |
| `device dump` | the live, currently sounding 92-byte preset, decoded |
| `device names` | the 20 amp capture names and 20 IR names (280 bytes each) |
| `device preset N` | stored preset `PNN` from flash, decoded, **without loading it** |
| `device backup` | checksummed backup of all 80 raw preset images and both name tables |
| `backup extract-all` | write P01.bin..P80.bin from that JSON backup |
| `device load N --yes` | load a stored preset into live RAM |
| `device audition IMAGE --yes` | apply a 92-byte image to RAM without saving |
| `device save N IMAGE --yes` | save and read back an inactive preset, with rollback |
| `device amp audition/save` | prepare and upload an AMP capture without the GUI |
| `device cab audition/save` | convert and upload a WAV IR without the GUI |
| `device library-apply MANIFEST --yes` | resumable, per-slot verified AMP/CAB batch |

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

Read frames still pass a strict address/size/checksum allowlist. A write frame
requires an explicit per-operation `WriteConsent`; flash paths require an
additional flash capability, and the transport independently checks the final
wire bytes. The CLI exposes no generic address writer and no firmware writer.

Every device mutation is dry-run by default. Live edits and preset saves are
read back byte-for-byte, preset saves keep rollback images, and AMP/CAB saves
require ACKs plus a matching permanent name-table read. A lost final commit ACK
is accepted only when a changed persistent name proves the commit. The firmware
does not expose AMP weights or CAB waveforms for read-back, so their content
verification ends at source hash + ACK + slot name; listening remains a
separate required check. `device library-apply` prebuilds all records before
opening MIDI, stops on the first failure, journals after every slot, and resumes
only when the same journal records a verified save of the same source hash and
the persistent name still matches.

Run `python -m blackboxctl write-paths` to see each state-changing command and
its dry-run, consent, verification, and recovery safeguards.

## What is confirmed and what is not

Every claim in this codebase is labelled CONFIRMED (observed on the owner's own
pedal (with the method stated) or HYPOTHESIS. The hardware serial is deliberately
not retained because it is irrelevant to protocol reproduction. The
full transcript is
[`docs/reverse-engineering/device-validation.md`](../../docs/reverse-engineering/device-validation.md).
See [STATUS.md](STATUS.md) for the current, honest state.

**CONFIRMED on hardware** (2026-08-28 through 2026-08-29):

- the Base-128 codec, the frame layout `magic(3) | length LE16 | space LE16 |
  address LE32 | size LE24 | payload | checksum`, and the address map;
- all four read commands, and a generic `read(space, address, size)` primitive
  that reproduces them byte for byte;
- the 92-byte preset memory map — seven independently known P41 values from the
  M-EFCS GUI all matched the decode;
- the 20 amp and 20 IR slot names, all 40 read back;
- inbound checksums sum from **offset 5**, not the published offset 4.
- all 80 preset slots; indices 0–79 answer and index 80 is refused;
- reversible live knob/toggle/model/routing/load operations and exact RAM restore;
- inactive P80 flash save, full read-back, and exact restore;
- CAB staging/save and AMP staging/save, including large-frame checksum and ACK
  behavior; all 20 AMP and 20 CAB names were replaced/verified by the CLI.

**Still bounded or unverified:** AMP runtime generation currently calls the
installed M-EFCS `libamx_parser.dylib`; a pure-Python replacement is not yet
implemented. AMP weights and CAB waveform cannot be read back. AM4 loading and
firmware writing are unsupported. Hard-brick/forced-bootloader recovery is not
documented by the vendor; see `../../docs/blackboxctl-recovery.md`.

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
pip install -e ".[dev]"
python -m pytest        # full offline regression suite
```

`pytest` is an optional extra, not a runtime dependency. Treat
[`STATUS.md`](STATUS.md) as the dated test-result authority and refresh its result after
changing the suite.

The fixtures are real bytes from the pedal, not synthesised: the seven
transmitted read commands, the seven unique reply frames, the 340-byte SysEx and
its 295-byte decode, and the four recorded preset images with their exact decode
tables. `tests/test_decode_preset.py` in particular replays P01, P03, P41 and the
live RAM dump against the values recorded from the M-EFCS GUI.
