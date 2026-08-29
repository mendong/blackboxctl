# Contributing

The supported product is `blackboxctl`. Protocol notes and the example preset
bank exist so the CLI can be reproduced; they are not a second runtime.

Source: [github.com/mendong/blackboxctl](https://github.com/mendong/blackboxctl).
Open a pull request from a fork of that repository.

## Development

Python 3.10 or newer. From `tools/blackboxctl/`:

```sh
python -m pip install -e ".[dev]"
make selftest
make test
make lint
```

Or the same commands without Make: `python -m blackboxctl selftest`,
`python -m pytest`, `ruff format --check blackboxctl tests && ruff check blackboxctl tests`.
GitHub Actions runs those on Python 3.10 and 3.12 for every push.

`pytest` is an optional extra, not a runtime dependency. Device commands are
macOS-only and skip cleanly when no pedal is present.

## Safety

- Device and library mutations are dry runs unless `--yes` is passed.
- Do not add a generic address writer or a firmware writer.
- Do not commit third-party captures, IRs, factory AMP/CAB blobs, firmware
  images, or local journals under `~/.local/share/blackboxctl/`.
- Hardware writes belong in `STATUS.md` only after they have been read back
  on a physical pedal. Offline tests are not audible proof.

## Protocol documentation

`docs/reverse-engineering/` is CC BY-SA 4.0 and is the derivation record of
the 2026-08-28 read-only session. Current write support lives in
`tools/blackboxctl/STATUS.md`. Do not fold later write evidence back into
the historical confidence tables as if it had been true on 2026-08-28.
