# M-VAVE BlackBox tools

[![CI](https://github.com/mendong/blackboxctl/actions/workflows/ci.yml/badge.svg)](https://github.com/mendong/blackboxctl/actions/workflows/ci.yml)

A macOS CLI, protocol notes, and an example 12-preset bank for the M-VAVE
BlackBox guitar amp modeller. Published at
[github.com/mendong/blackboxctl](https://github.com/mendong/blackboxctl).

This project is independent interoperability work. It is not affiliated with
or endorsed by M-VAVE.

The repository holds four things:

- **`blackboxctl`** — read and write the pedal over USB MIDI SysEx, and manage
  the M-EFCS on-disk capture/IR library. No third-party Python packages.
- **Protocol documentation** — community reverse engineering, then validated
  against one physical pedal.
- **An example preset bank** — declarative P01–P12 specs and 92-byte images.
- **Slot maps** — which capture and IR roles occupy the 20 AMP and 20 CAB
  slots on that example bank.

No third-party capture, IR, manual, or firmware binary is committed. The
92-byte `.bin` files under `presets/` are preset images from the author's
device, kept so the specs remain reproducible.

## Quick start

Python 3.10 or newer. Device commands are macOS-only and need the pedal
plugged in. Preparing a new AMP record also needs the installed M-EFCS
`libamx_parser.dylib`; other non-device commands work offline.

```sh
cd tools/blackboxctl
python -m pip install -e ".[dev]"     # optional; pytest and ruff
python -m blackboxctl doctor          # protocol, MIDI, and M-EFCS readiness
python -m blackboxctl device endpoints
python -m blackboxctl write-paths     # every mutation and its safeguards
```

Every device and library mutation is a **dry run unless `--yes` is passed**.
Read [tools/blackboxctl/STATUS.md](tools/blackboxctl/STATUS.md) before trusting
a claim about hardware support.

## Safety

- Reads are allowlisted. Writes need an operation-specific consent; flash
  needs a second capability. There is no generic address writer or firmware
  writer.
- Preset saves keep rollback bytes and verify all 92 bytes. AMP/CAB saves
  require ACKs plus a persistent name-table match. Their audio payload still
  needs listening: the firmware exposes no AMP-weight or CAB-waveform
  read-back.
- `library install` writes into another application's sandbox container.
  `library restart-editor` quits M-EFCS and discards unsaved GUI work.
- Recovery: [docs/blackboxctl-recovery.md](docs/blackboxctl-recovery.md).

## Hardware

| | |
| --- | --- |
| Pedal | M-VAVE BlackBox, USB-C. App-reported label `BLACKBOX v20` |
| Capacity | 20 AMP slots, 20 IR/CAB slots, 80 preset slots |
| Editor | `/Applications/M-EFCS.app` (`com.digAmp.dgAmp`) |
| File library | `~/Library/Containers/com.digAmp.dgAmp/Data/Documents/M-EFCS/` |
| Transport | Base-128 packed SysEx over USB MIDI; CoreMIDI manufacturer `Jieli Technology` |

The author's unit was migrated with this CLI on 2026-08-29. That session is
recorded in [tools/blackboxctl/STATUS.md](tools/blackboxctl/STATUS.md). Re-run
endpoint and name-table checks on your own pedal before writing.

## Repository map

| Path | What it is |
| --- | --- |
| [`tools/blackboxctl/`](tools/blackboxctl/) | The CLI, tests, `LICENSE`, `NOTICE`, `STATUS.md` |
| [`docs/reverse-engineering/`](docs/reverse-engineering/README.md) | Wire protocol, capture format, validation logs. Start here for protocol work |
| [`docs/sources.md`](docs/sources.md) | Provenance and licence inventory |
| [`docs/blackboxctl-recovery.md`](docs/blackboxctl-recovery.md) | Backup, restore, brick boundary |
| [`presets/core-bank.md`](presets/core-bank.md) | Example P01–P12 roles |
| [`presets/device-library.json`](presets/device-library.json) | Example 20+20 AMP/CAB manifest |
| [`AGENTS.md`](AGENTS.md) | Operator rules for changing a connected pedal |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) / [`SECURITY.md`](SECURITY.md) | How to patch, and how to report a device-safety bug privately |
| [`docs/superpowers/`](docs/superpowers/) | **History only.** Superseded July 2026 plans. Do not execute |

Where two documents disagree about the 2026-08-28 *read* protocol, measurements
from the pedal ([`device-validation.md`](docs/reverse-engineering/device-validation.md))
beat inference from prior art, and
[`protocol-spec.md` §2](docs/reverse-engineering/protocol-spec.md#2-frame-format--the-canonical-model)
is canonical for the wire frame. Those confidence labels are a dated read-only
snapshot. Current write evidence lives in `tools/blackboxctl/STATUS.md`.

## Example preset bank

P01–P12 in [`presets/core-bank.md`](presets/core-bank.md) are an author's
working bank, not factory content. Spatial effects are intentional: rhythm
presets keep them short and low; Chime and Ambient Lead use delay and reverb
as part of the sound. Exact parameters are the JSON specs under
[`presets/specs/`](presets/specs/).

Tone source policy, slot pairing, and community capture notes:
[`presets/library.md`](presets/library.md). Song notes:
[`presets/hana.md`](presets/hana.md),
[`presets/boulevard-of-broken-dreams.md`](presets/boulevard-of-broken-dreams.md).

## License

- **`tools/blackboxctl/` is GPL-3.0-or-later.** Its packet layout, codec,
  checksum rule and memory map were reconstructed from GPL-3.0 reference code
  and CC BY-SA 4.0 documentation. See
  [`tools/blackboxctl/LICENSE`](tools/blackboxctl/LICENSE) and
  [`tools/blackboxctl/NOTICE`](tools/blackboxctl/NOTICE).
- **Protocol documentation adapted from `mvave-blackbox-ble` is CC BY-SA 4.0**,
  attributed to Joel Victor. Share-alike applies.
- **Remaining original docs and the example preset bank are CC BY-SA 4.0.**
  See [LICENSE](LICENSE).

The full inventory of sources is [`docs/sources.md`](docs/sources.md).

## Related projects

These are sibling tools and prior art, not drop-in replacements.

| Project | Role | Difference |
| --- | --- | --- |
| [mvave-blackbox-edit](https://github.com/jvsobrinho/mvave-blackbox-edit) | Browser editor over Web Bluetooth | Live GUI on BLE. No USB SysEx CLI, no AMP/CAB IR upload, no checksummed 80-slot backup yet. |
| [mvave-blackbox-ble](https://github.com/jvsobrinho/mvave-blackbox-ble) | Protocol documentation | The wire format this CLI implements and, where measured, corrects. |
| [cuvave-midi](https://github.com/pferreir/cuvave-midi) | Cube Baby SysEx parser | Same vendor family, different product and memory map. |
| [am2manager](https://github.com/walterwanderley/am2manager) | `.am2` / `.am2Data` converter | Capture-file conversion only; does not talk to the pedal. |
| M-EFCS | Official GUI editor | Same USB MIDI protocol and on-disk library. This CLI is the scriptable, dry-run-default path. |
