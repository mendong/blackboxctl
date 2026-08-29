# blackboxctl implementation review — 2026-08-29

Historical closeout. Test counts in this file may lag; use
[`tools/blackboxctl/STATUS.md`](../tools/blackboxctl/STATUS.md) for the current
offline suite result.

This is a closeout review of the CLI's implementation history, current safety
boundary, and code structure. It distinguishes offline/unit evidence, physical
device evidence, and audible evidence; none substitutes for another.

## How the CLI was built

1. **Read-only foundation.** The Base-128 codec, frame parser, checksums, memory
   map, preset decoder, CoreMIDI receive path, and strict read allowlist were
   implemented against upstream protocol work and captured device replies.
2. **Bounded live writes.** Each write builder gained a path-specific
   `WriteConsent`; a reversible AMP Gain change established the first RAM write.
   Toggle, model, routing, load, full live-image apply, and exact restoration
   were then verified separately.
3. **Recovery before persistence.** All 80 presets and both name tables were
   backed up before the inactive P80 flash probe. Preset saves preserve an exact
   92-byte rollback image, reconcile lost ACKs with read-back, and restore on an
   uncertain target.
4. **AMP/CAB replacement.** Captured M-EFCS staging and commit sequences were
   implemented as explicit capabilities. CAB20 and AMP20 were used as bounded
   probes before the 20+20 library migration. Permanent names are readable;
   neural weights and CAB waveform payloads are not.
5. **Declarative bank migration.** P01-P12 were rendered from their preserved
   pre-migration images, saved individually, and compared as complete 92-byte
   flash images. Specs, base images, and rendered images remain separate so the
   bank can be reproduced or the former bytes restored.

The dated physical evidence and current feature boundary live in
[`tools/blackboxctl/STATUS.md`](../tools/blackboxctl/STATUS.md). Earlier reverse-
engineering documents are historical snapshots, not a second current-status
authority.

## Review findings resolved

- CoreMIDI partial-open failures now release every native/CF resource and allow
  the same object to retry.
- Endpoint resolution refuses ambiguous Jieli source/destination sets instead
  of guessing a cross-device pair.
- A private cross-process lock serializes every blackboxctl device session from
  endpoint discovery through close. Failure, close, and Ctrl-C all release it.
- An incomplete asynchronous CoreMIDI SysEx now blocks that connection from
  sending a retry or recovery frame; unrelated notifications no longer consume
  the one allowed reply attempt, and ACK/reply timeouts remain distinct from a
  missing transport.
- AMP/CAB audition performs a safe BlackBox-specific read handshake before its
  first write-only transfer.
- AMP/CAB standalone and batch saves share one staging/commit transaction;
  final-ACK reconciliation and name-table polling no longer have three copies.
- Ctrl-C after a permanent commit cannot silently skip the batch journal update;
  uncertain and verified outcomes are fsynced before interruption is delivered.
- Default journal names include a random suffix, so same-second invocations
  cannot overwrite one another before the device lock is acquired.
- A journal-specific sidecar lock now covers journal load through the final
  fsync. Resume trusts only the latest authoritative result per AMP/CAB slot;
  an uncertain rewrite invalidates older success evidence even if the name and
  source hash are unchanged.
- Backup, rollback, journal, rename, extracted/rendered output, and M-EFCS
  library writes use one mode-0600 atomic storage primitive with durable parent
  directories and atomic no-clobber publication.
- Atomic replacement keeps the requested final path lexical, so a destination
  symlink is replaced rather than followed. M-EFCS library installs also refuse
  symlinked target directories and destination files.
- Preset-file and CLI decode paths now share the same full-frame validation, so
  a corrupt or wrong-address 107-byte reply is never decoded as a preset.
- Preset export validates that routing is an exact six-block permutation before
  looking up block names, so malformed images produce a normal CLI/JSON error
  instead of leaking a `KeyError` traceback.
- Device-library manifests and backup bundles reject JSON booleans in every
  integer field; `true` can no longer silently select slot 1 or level 1.
- Write and editor-restart capabilities accept only the exact boolean `True`;
  truthy strings, integers, and containers cannot authorize a device write or
  discard unsaved M-EFCS work through a programmatic caller.
- The endpoint diagnostic reports ready only for exactly one matching source
  and one destination, matching the transport's ambiguity refusal.
- Unexplained `00 00 35/38 00` capture magics remain inspectable as corpus
  evidence but cannot enter AMP device-record preparation. Only AM2/AM3 is sent.
- JSON mode emits one document for both success and failure. Only a typed
  transport-unavailable error gets the USB guidance and exit code 3; verification
  failures use exit code 1.
- Ruff formatting/linting is repository-configured, and the committed P01-P12
  images are regenerated from base+spec in the test suite.
- The 40-entry device-library manifest pins an ordered source-set hash in
  addition to per-entry hashes, and preparation refuses sources that change
  while they are being read.
- Live-image apply builds and validates the complete ordered write plan before
  sending its first frame. Both live probes preflight that their baseline can
  be represented by the constrained restore builders before any mutation.
- Standalone AMP/CAB save reporting distinguishes a final commit ACK from a
  persistent-name verification. An interruption during name polling no longer
  overstates ACK receipt as a confirmed permanent save.
- WAV conversion rejects partial audio frames and non-finite samples before a
  CAB record can be staged; malformed `data` sizes cannot leak trailing bytes
  into a fabricated sample.

## Current code boundaries

| Module | Responsibility |
| --- | --- |
| `protocol.py` | Pure codecs, frame validation, memory map, write capabilities |
| `transport.py` | CoreMIDI lifetime, endpoint selection, process lock, ACK/reply I/O |
| `captures.py` | AMP capture and WAV/CAB parsing plus record preparation |
| `presetfiles.py` | Lossless preset normalization, declarative edits, export |
| `backups.py` | Checksummed full-device backup schema |
| `device_library.py` | Complete offline manifest preparation |
| `storage.py` | Durable atomic filesystem publication |
| `library.py` | M-EFCS on-disk library inspection and installation |
| `cli.py` | argparse surface, orchestration, recovery state, user output |

The explicit write-path branches in `protocol.py` remain intentionally verbose:
they are an auditable second trust boundary, not duplication to abstract away.
Recovery catches that include `KeyboardInterrupt` also remain intentional.

## Boundaries that remain

- New AMP records still use M-EFCS's installed `libamx_parser.dylib` to produce
  the 68-byte runtime LMT block. A clean-room implementation is portability work.
- AMP weights and CAB waveform payloads have no known read-back path. ACK plus
  persistent-name verification proves the transaction/header, not content or
  sound; listening remains a separate required check.
- The process lock coordinates blackboxctl instances, not M-EFCS. Quit M-EFCS
  before device writes so the GUI cannot race the CLI.
- The undocumented OLED/commit trigger and every firmware/raw-address writer
  remain disabled. Official M-UPGRADE is the firmware boundary.
- No authoritative forced-bootloader procedure is known for a unit that exposes
  neither USB MIDI nor M-UPGRADE. Do not guess a button combination.

## Closeout commands

Run from `tools/blackboxctl/`:

```sh
uvx ruff format --check blackboxctl tests
uvx ruff check blackboxctl tests
uvx pyright blackboxctl
python -m compileall -q blackboxctl
uv run --no-project --with pytest python -m pytest -q
python -m blackboxctl selftest
```

The final offline run passed on both Python 3.10 and the default Python runtime:
`344 passed, 1 skipped`. Ruff, Pyright, and `compileall` were clean; selftest
passed 21/21; and the complete 20-AMP + 20-CAB manifest prepared successfully in
dry-run mode without opening a device.

This review did not send a MIDI packet or mutate the physical pedal.
