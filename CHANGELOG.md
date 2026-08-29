# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Added

- Public repository at https://github.com/mendong/blackboxctl
- GitHub issue and pull-request templates, plus a private safety-advisory link

- `blackboxctl doctor` reports Python, protocol self-test, MIDI transport,
  BlackBox endpoint readiness, the M-EFCS AMP helper, and the on-disk library.
  `--require-device` exits 3 when no pedal pair is ready.
- `blackboxctl backup extract-all` writes all 80 raw 92-byte images from a
  checksummed backup, the librarian-style dump used by similar SysEx tools.
- GitHub Actions CI for Python 3.10 and 3.12 (offline tests; device cases skip).
- Makefile targets for `selftest`, `doctor`, `test`, and `lint`.

### Changed

- `--help` includes copy-pasteable examples.
- README names sibling BlackBox/capture projects and what this CLI does
  differently.
