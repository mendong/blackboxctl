# blackboxctl: M-EFCS replacement plan

**Completed 2026-08-29.** This is the delivery record, not an open backlog.
Current command support is [`tools/blackboxctl/STATUS.md`](../tools/blackboxctl/STATUS.md).

Status date: 2026-08-29

## Goal

Replace repeated M-EFCS mouse operations with a scriptable, read-back-verified
CLI for the M-VAVE BlackBox. The CLI should cover connection diagnostics,
full backup, preset editing and saving, AMP capture and CAB/IR upload, library
management, and recovery documentation. Factory-content restore and firmware recovery are
explicit non-goals for this CLI; they remain official M-EFCS/M-UPGRADE operations.

"Command sent" is never considered success. Every mutable operation must be
followed by a device read-back or another device-originated check.

## Delivery gates

1. **Lossless read path** — read P01-P80, live RAM, active slot, AMP names and
   CAB names; store a checksummed JSON backup containing every raw 92-byte
   image. Restore-critical data must not depend on the decoder knowing every
   firmware field.
2. **Preset editor** — create a preset image from a stored slot or backup;
   change volume, routing, block on/off, model slot, and knob values with range
   validation; produce a byte diff before touching hardware.
3. **Reversible RAM apply** — apply one image field-by-field, read live RAM
   back, and automatically restore the original RAM image on mismatch.
4. **Flash save/restore** — first prove an idempotent P80 write using the exact
   bytes already stored there. Then save a changed disposable slot, read all 92
   bytes back, and restore the pre-write image. Only after those checks may the
   general `preset save` and backup restore commands be enabled.
5. **AMP/CAB transport** — identify the vendor command queue and chunk framing
   from the installed M-EFCS implementation. Test with a factory image already
   bundled in M-EFCS, one disposable slot at a time, and verify the returned
   name plus the resulting audio. Large binary writes stay disabled until this
   protocol is measured, not guessed.
6. **Recovery** — keep pre-write backups outside the app sandbox; preserve the
   M-EFCS factory AMP/CAB and preset binaries; document official firmware V20
   and M-UPGRADE recovery. Do not claim hard-brick recovery until a forced
   bootloader entry procedure is confirmed by the vendor or on hardware.
7. **Migration** — install the selected 20 AMP captures and 20 IRs, then write
   P01-P12 from the declarative preset library. Verify saved bytes, displayed
   slot names, switching, and audible output separately.

## Current execution state

- Gates 1–4 passed: all 80 presets were backed up; declarative editing, exact
  RAM apply/restore, inactive-slot flash save/read-back/rollback, and general
  preset save are physically verified.
- Gate 5 passed at the protocol level: CAB20 and AMP20 disposable-slot proofs
  passed, followed by a full 40-entry migration. The final device name tables
  exactly match `presets/device-library.json`. Audible verification remains a
  separate player task because AMP weights and CAB waveforms are not readable.
- Gate 6 is documented in `blackboxctl-recovery.md`. Durable preset/library
  backups and the four factory blobs are preserved outside the app sandbox.
  M-UPGRADE's official USB-reconnect recovery is recorded; forced bootloader
  recovery remains unconfirmed and is not claimed.
- Gate 7 passed for stored state: P01–P12 were rendered from the pre-write
  backup, saved individually, and all twelve 92-byte images matched a final
  flash read. The bank is documented in `presets/core-bank.md`. Matched-volume
  listening and adjustment remain.

## Completion definition

The CLI now replaces M-EFCS's GUI for backup, editing, audition, preset save,
AMP/CAB upload, and complete library migration on this Mac. One implementation
dependency remains: preparing a new AMP record calls M-EFCS's installed
`libamx_parser.dylib` to calculate the 68-byte runtime LMT block. It does not
launch or automate the GUI. A clean-room LMT implementation is future
portability work, not a blocker for the current Mac.
