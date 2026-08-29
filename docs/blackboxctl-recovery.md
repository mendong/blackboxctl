# BlackBox write and recovery runbook

Last verified: 2026-08-29, against the author's ANNBLACKBOX over USB MIDI.

Dated paths under `~/.local/share/blackboxctl/` in this file are **that
session's local recovery assets**. They are not shipped in the repository.
On another machine, keep your own `device backup` JSON, apply journal, and
source files.

## What is recoverable

There are three different failure layers. Do not treat one as proof of another.

1. **A bad preset, AMP, or CAB while USB MIDI still works.** Stop writing, select a
   known slot, and inspect the device with `blackboxctl`. Preset bytes can be restored
   exactly from the backup below. AMP/CAB contents do not have a known read-back
   command, so recovery is by re-uploading the intended source or by M-EFCS's factory
   restore.
2. **A failed firmware-upgrade handshake.** Use the official M-UPGRADE application and
   the firmware for ANNBLACKBOX only. M-VAVE's published instruction for `Failed to
   enter upgrade mode!` is to leave M-UPGRADE open, unplug and reconnect USB, then
   continue the upgrade.
3. **No display, no USB MIDI, and M-UPGRADE cannot see the unit.** No authoritative
   forced-bootloader or hard-brick procedure was found in M-VAVE's manual, download
   page, or current firmware material. Do not guess button combinations or flash a
   similarly named product's image. Stop and contact M-VAVE or a hardware service
   channel.

The official product page currently lists 80 editable presets, 20 AMP slots, 20 IR
slots, M-EFCS, M-UPGRADE, and ANNBLACKBOX firmware V20 dated 2026-01-31:

- https://www.m-vave.com/product?id=annblack-box
- https://www.m-vave.com/download

## Before any device write

1. Charge the pedal and use a direct, stable USB connection. Do not update firmware
   through an unreliable hub.
2. Quit M-EFCS so it cannot race the CLI for the same MIDI endpoints.
3. Confirm both a source and destination endpoint:

   ```sh
   blackboxctl device endpoints
   ```

4. Keep a full preset backup from `blackboxctl device backup`. The author's
   2026-08-29 file was:

   ```text
   ~/.local/share/blackboxctl/backups/blackbox-before-cli-writes-20260829.json
   SHA-256 13bf6bf7a83d8e76284430cfe8d96d74a0a922f670c1669b6ca62a9f996b59ef
   ```

5. Run the requested operation without `--yes` first. A dry run fully builds and
   validates its data without opening the device.

## Preset restore

Verify the backup, extract one exact 92-byte image, switch the pedal to a different
preset, and save it back:

```sh
blackboxctl backup verify \
  ~/.local/share/blackboxctl/backups/blackbox-before-cli-writes-20260829.json
blackboxctl backup extract \
  ~/.local/share/blackboxctl/backups/blackbox-before-cli-writes-20260829.json \
  12 /tmp/P12-before.bin
blackboxctl device save 12 /tmp/P12-before.bin --yes
```

`device save` refuses the active slot, preserves the incumbent image separately, writes
all 92 bytes, reads them back, and rolls back automatically on a mismatch.

## AMP/CAB recovery assets

The original M-EFCS user library was also copied out of temporary storage to:

```text
~/.local/share/blackboxctl/backups/M-EFCS-library-before-20260828-041029.tgz
SHA-256 8ba9355a2fec2c6e6acdef865eb79c68ef0d25a8a9d5305aa9c67d6bdb49e27a
```

The installed M-EFCS application shipped four factory-content blobs. Read-only copies
were preserved with mode `0600` under `~/.local/share/blackboxctl/factory/`:

| File | SHA-256 |
| --- | --- |
| `ampSim_am3_ampCab.bin` | `a934ff40ed6402ee25c641c4b515d013fa60fe2afa7dfb8889cca4a1077366fe` |
| `ampSim_am3_preset.bin` | `7e670c57170f8e0e0c0553cf0f18dbf0b64757f28d682a17e5338dc6f6f315e7` |
| `blackbox_am3_ampCab.bin` | `4bdbd971d68306f4105073d78417a21b4f79ffddfef317096ed0f1ae988827ec` |
| `blackbox_am3_preset.bin` | `8b751dc9a2dc924e96766da3c6b39c200feb87e7542f81f52eb8765ce38f7e52` |

These are evidence and recovery inputs, not yet a supported `blackboxctl` flash format.
Use M-EFCS's factory-restore workflow for them. Never send a whole blob through the
normal 92-byte preset or 6,2xx-byte AMP/CAB commands.

## Interrupted library apply

`device library-apply` writes one slot at a time and verifies the name table after each
commit. Its journal is atomically rewritten with mode `0600`. The first complete run is:

```text
~/.local/share/blackboxctl/journal/library-apply-20260829-123820.json
```

After an interruption, reconnect and run the same manifest with the same journal path.
A slot is skipped only when that journal records a verified save of the same source hash
and the persistent name still matches; `--rewrite` deliberately retransmits it. A name
match proves the slot header/commit, not byte-for-byte AMP weights or CAB waveform,
because the firmware does not expose those payloads for read-back. Always perform a
separate audible check.

## Firmware boundary

`blackboxctl` does not and must not write firmware. Firmware recovery belongs to the
official M-UPGRADE path. Before updating, retain the preset backup and library manifest;
a working editor or name table is not proof that firmware recovery mode works.
