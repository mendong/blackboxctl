# blackboxctl — current status

Last updated: 2026-08-29. This file supersedes older read-only status notes.

For the end-to-end implementation history, resolved review findings, and evidence-layer
closeout, see [`docs/blackboxctl-review-2026-08-29.md`](../../docs/blackboxctl-review-2026-08-29.md).

## Completed and verified on the owner's pedal

- CoreMIDI endpoint discovery, SysEx transport, Base-128 codec, frame parser,
  checksum, request/reply routing, and exact compact ACK recognition.
- Read/decode of live RAM, the active preset, all 80 flash presets, and both
  20-entry AMP/CAB name tables. Flash indices 0–79 answer; index 80 is refused.
- Lossless, checksummed backup of all 80 raw 92-byte preset images.
- Live preset load, knob, toggle, model, routing, and full-image restoration.
  Each reversible probe restored all 92 RAM bytes exactly.
- Inactive P80 flash save, complete read-back, and exact restoration of its
  incumbent image, with active preset and live RAM unchanged.
- Declarative preset export/render, RAM audition, inactive-slot save, automatic
  rollback on mismatch, and persistent rollback files.
- CAB conversion to the exact 6,164-byte M-EFCS staging record, seven-chunk staging,
  activation, header save, and slot commit. CAB20 was saved and name-verified.
- AMP normalization, deterministic 68-byte runtime block generation, exact
  6,272-byte seven-chunk upload, activation, and slot commit. AMP20 was saved
  and name-verified. The computed record matched a captured M-EFCS transfer
  byte-for-byte before the CLI hardware test.
- Resumable batch application of a 40-entry AMP/CAB manifest. On 2026-08-29 it
  saved 37 slots, skipped three already matching slots, and then read back the
  complete intended 20 AMP + 20 CAB name tables. The mode-0600 journal is:
  `~/.local/share/blackboxctl/journal/library-apply-20260829-123820.json`.

The pre-write preset backup is:
`~/.local/share/blackboxctl/backups/blackbox-before-cli-writes-20260829.json`,
SHA-256 `13bf6bf7a83d8e76284430cfe8d96d74a0a922f670c1669b6ca62a9f996b59ef`.

## Safety boundary

All writes are dry-run by default and require `--yes`. The transport has no
generic arbitrary-address or firmware-write surface. Every write requires a
specific capability, and flash needs a second explicit capability.

Preset saves are byte-readable, so they are backed up, written, and compared
exactly; a mismatch triggers an immediate rollback. AMP/CAB payloads are not
readable through any known command, so those saves require ACKs and a matching
persistent slot-name read. A lost final commit ACK is accepted only when the
name changed to the target; otherwise the journal records an uncertain commit.
That proves transfer and commit, not sound or byte-for-byte payload. Audible
verification is still separate.

`device library-apply` validates and builds all source records before opening
the pedal, applies one slot at a time, records an atomic mode-0600 journal after
every commit, and stops on the first failure. Re-running skips only a slot whose
same source hash is still the latest authoritative verified result in that
journal and whose persistent name still matches. An uncertain rewrite
invalidates older evidence; `--rewrite` deliberately retransmits the slot.

## Remaining limitations

1. AMP runtime generation currently uses the installed editor's
   `/Applications/M-EFCS.app/Contents/Frameworks/libamx_parser.dylib`. The GUI,
   click automation, and M-EFCS USB path are no longer used, but a clean Mac
   without that helper cannot yet prepare AMP records. A pure-Python LMT
   implementation is the remaining portability task.
2. The firmware exposes no known AMP-weight or CAB-waveform read-back command.
   Keep source files, manifest hashes, the factory blobs, and the apply journal.
3. AM4 upload is not implemented. AM2 and AM3 records are accepted by the
   current preparation path; malformed known `am2converter` magic is normalized
   only in the transmitted copy.
4. Firmware writes are intentionally outside blackboxctl. The official recovery
   path is M-UPGRADE. No authoritative hard-brick forced-bootloader procedure was
   found; see `../../docs/blackboxctl-recovery.md`.
5. Physical listening through the intended guitar/pickup/output path is still
   required. Name read-back is not an audible test.

## Tests

The latest completed full-suite run in this worktree reports:

```text
408 passed
```

Verified on Python 3.10. One device-absence case is skipped only when a
pedal is actually connected. `selftest` reports 21/21 and `--json doctor`
is valid uncontaminated JSON. The test suite locks the real captured
device frames, write gates, exact AMP/CAB chunk layouts, preset
backup/render behavior, manifest preflight, and dry-run defaults.
