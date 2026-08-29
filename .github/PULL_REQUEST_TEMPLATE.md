## What

## Safety

- [ ] No generic address writer or firmware writer
- [ ] Device/library mutations stay dry-run without `--yes`

## Test plan

- [ ] `python -m pytest -q` from `tools/blackboxctl/`
- [ ] `python -m blackboxctl selftest`
