# Security and device safety

`blackboxctl` talks to a USB guitar pedal. A bad write can destroy stored
presets or AMP/CAB slots. Firmware writing is intentionally not implemented.

## What this tool will not do

- There is no generic address writer.
- There is no firmware update or bootloader path.
- State-changing commands are dry runs unless `--yes` is supplied.
- Flash writes require an extra capability on top of a per-path consent.

If USB MIDI still works, presets can be restored from a `device backup`
JSON file. AMP weights and CAB waveforms cannot be read back; recover those
by re-uploading the source files or by using official M-EFCS factory restore.

If the unit has no display, no USB MIDI, and M-UPGRADE cannot see it, stop.
There is no supported forced-bootloader procedure. See
[docs/blackboxctl-recovery.md](docs/blackboxctl-recovery.md).

## Reporting a vulnerability

Please report safety-relevant bugs privately rather than in a public issue:
unexpected writes, consent bypasses, or anything that could brick a pedal.

Use GitHub's private advisory form:

https://github.com/mendong/blackboxctl/security/advisories/new

Include the command line, whether `--yes` was passed, and `blackboxctl --version`.
