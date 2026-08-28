# M-VAVE BlackBox workspace

A working repository for one guitarist's M-VAVE BlackBox amp modeller and capture pedal.
It holds four independent things:

- **Preset designs** for specific songs, written as exact parameter values.
- **A capture and IR library map** — which community capture and which impulse response
  belongs in each of the pedal's 20 amp and 20 IR slots, and why.
- **Protocol and file-format documentation**, reverse engineered from community prior art
  and then validated read-only against this specific pedal.
- **`blackboxctl`**, a dependency-free, read-only CLI that talks to the pedal over USB MIDI
  SysEx and manages the editor's on-disk file library.

Everything here is written in English, including for a Korean-reading owner. It is
documentation and tooling, not audio content: no capture, IR, manual, or firmware binary is
committed.

## Hardware and software

| | |
| --- | --- |
| Pedal | M-VAVE BlackBox, connected to a Mac over USB-C; app-reported label `BLACKBOX v20` |
| Capacity | 20 amp slots, 20 IR/CAB slots, both replaceable; presets `P01`–`P41` used here |
| Editor | `/Applications/M-EFCS.app` (`com.digAmp.dgAmp`), version `3.5.2615`, Mac App Store build |
| File library | `~/Library/Containers/com.digAmp.dgAmp/Data/Documents/M-EFCS/` — `ampFile` for captures, `cabFile` for IRs. Scanned once at app launch. |
| Transport | Proprietary packets as Base-128 packed SysEx over USB MIDI; the pedal appears in CoreMIDI as manufacturer `Jieli Technology` |

The pedal is **connected**, and every read command is verified working as of 2026-08-28.

## Current state

**Tone source.** The factory presets and built-in amp models were abandoned. Presets are
built from community capture files plus third-party IRs, with ML Sound Lab's free
"Best IR in the World" as the default IR. Reasoning and sources:
[`presets/library.md`](presets/library.md).

**On the Mac.** 24 captures and 83 IRs were installed into the M-EFCS library, on top of
the 15 captures and 210 IRs already there, and confirmed visible in the AMP and CAB tabs
after an app restart.

**On the device — one amp or IR slot has ever been written, and five presets.** On
2026-08-28, through the M-EFCS GUI, IR slot 1 was changed from the factory `1AC-SeVin` to
`1ML_BEST_IR`; that is the only amp or IR slot ever written, and it was later confirmed
independently by reading the IR name table out of flash. Five presets were also written
through the same GUI earlier: P01–P03 on 2026-07-20 and P04–P05 on 2026-07-26, both from
built-in amp models, and both since superseded as targets. P01 and P03 were confirmed by
flash read on 2026-08-28; P02, P04 and P05 were not. The full device history is in
[`AGENTS.md` §1](AGENTS.md#1-current-state).

**Designed but not written.** Amp slots 2–20, IR slots 2–6 and 8–20, and the
capture-based versions of presets P01–P05 — those five slots still hold their July
built-in-model values. Amp slot 1 and IR slot 7 are deliberately left at their factory
contents because the protected preset P41 `Wonderwall Live` points at them by number.

**Verified on the pedal, read only, in a single session on 2026-08-28.** The Base-128
codec, the wire frame format, the read commands, the 92-byte preset memory map, and all
40 amp and IR slot names, read straight out of flash. Three counts of "the read commands"
appear across these documents and all three are correct: **four read command shapes, five
address bases, seven transmitted byte literals** (sixteen transmissions in total across
the seven preserved logs). The P41 decode matched seven values independently known from
the GUI. Raw byte logs and the full transcript:
[`docs/reverse-engineering/device-validation.md`](docs/reverse-engineering/device-validation.md).

**Assumed, not verified.** Every write path — no write frame of any kind has ever been sent
to this pedal. Also the 80-preset capacity (a vendor figure; the highest flash index ever
read here is 40), and whether the device tolerates a non-conforming capture magic or an AM4
record. On non-conforming IRs there is exactly one demonstrated case: a 48 kHz, 65536-frame
source was accepted into IR slot 1 through the GUI. Bit depth and stereo behaviour on
import remain untested, and the factory IR set failing the vendor's own spec line says
nothing about what the import path does — see
[`presets/library.md`](presets/library.md).

**Audit registers.** Two audits, both taken *before* the documentation consolidation,
catalogued every place the documents contradicted each other or the world. Most of what
they found has since been applied; a few entries are still open. Every entry now carries a
disposition — APPLIED, OPEN or REPORTED-ONLY — so the register reads as a record of what
was fixed and where, not as a to-do list:
[`docs/reverse-engineering/contradiction-register.md`](docs/reverse-engineering/contradiction-register.md)
(the protocol documents) and [`docs/staleness-register.md`](docs/staleness-register.md)
(everything else). Check an entry's disposition before acting on it, and read the relevant
entry before relying on a surprising claim.

## Repository map

| Path | What is there | Read it when |
| --- | --- | --- |
| [`AGENTS.md`](AGENTS.md) | Working guide: tone-source policy, preset safety rules, how to drive the M-EFCS GUI, the Mac monitoring path, preset workflow | You are about to change something on the device or in the library |
| [`presets/library.md`](presets/library.md) | The capture and IR library: why the factory presets were dropped, install procedure, measured IR formats, slot reservations, the 20-amp and 20-IR slot maps, pairing rules, device limits, sources | You want to know what goes in which slot, or how to install files |
| [`presets/hana.md`](presets/hana.md) | Fujii Kaze "Hana", presets P01–P03: pre-overwrite record, capture-based targets, a superseded built-in-model version, verification status | You are building or auditing those presets |
| [`presets/boulevard-of-broken-dreams.md`](presets/boulevard-of-broken-dreams.md) | Green Day "Boulevard of Broken Dreams", presets P04–P05, same shape; its pre-overwrite state was never captured | Same |
| [`docs/reverse-engineering/README.md`](docs/reverse-engineering/README.md) | **Start here for anything protocol-related.** The directory index: reading order, and the one consolidated list of what is CONFIRMED on this pedal, CONFIRMED off-device, HYPOTHESIS and UNRESOLVED | You are about to read any of the five protocol documents |
| [`docs/reverse-engineering/`](docs/reverse-engineering/) | Five large documents — `protocol-spec.md` (canonical wire format), `protocol-algorithms.md` (codec, opcodes, prior-art provenance), `device-validation.md` (the live read-only session and its raw bytes), `capture-format-spec.md` (`.am2`/`.am3`/`.am4` containers and the neural payload), `official-docs.md` (vendor manuals, firmware notes, the MIDI chart) — plus `logs/` (seven verbatim device transcripts), `reference/` (the preserved predecessor modules, including the only one that ever transmitted to this pedal) and `contradiction-register.md` | You are writing code against the protocol or a capture file |
| [`docs/sources.md`](docs/sources.md) | Canonical inventory of every external source, its licence, what was taken from it, and the redistribution position | You need provenance or licence terms for anything |
| [`docs/superpowers/`](docs/superpowers/) | **History only.** July 2026 plans and specs for the original built-in-amp-model presets, since superseded. They read as live executable plans and contain device-write steps. Do not execute them. | You want to know why P04/P05 are a pair, or what was tried before |
| [`tools/blackboxctl/`](tools/blackboxctl/) | The CLI: five modules (`captures`, `cli`, `library`, `protocol`, `transport`) plus `__init__`/`__main__`, 221 tests, `README.md`, `STATUS.md`, `LICENSE`, `NOTICE` | You want to read the device or the library from a terminal |

Where two documents disagree, the ranking is: measurements from the pedal
(`device-validation.md`) beat inference from prior art, and
[`protocol-spec.md` §2](docs/reverse-engineering/protocol-spec.md#2-frame-format--the-canonical-model)
is canonical for the wire frame format. The consolidated confidence labels live in one
place: [`docs/reverse-engineering/README.md`](docs/reverse-engineering/README.md).

## Getting started

### Inspecting the device and the library

No dependencies beyond the standard library; Python 3.10 or newer. The `device` commands
are macOS-only and need the pedal plugged in; everything else works offline.

```sh
cd tools/blackboxctl
python -m blackboxctl selftest          # offline protocol check; touches nothing. Run first.
python -m blackboxctl library diff      # compare presets/library.md's slot maps to disk
python -m blackboxctl device endpoints  # is a Jieli Technology endpoint present?
python -m blackboxctl device names      # the 20 amp and 20 IR slot names, from flash
python -m blackboxctl device preset 41  # decode stored P41 without loading it
python -m blackboxctl write-paths       # every state-changing command, and why it is disabled
```

`device preset N` is the fastest way to record a slot's current contents before overwriting
it. Read [`tools/blackboxctl/STATUS.md`](tools/blackboxctl/STATUS.md) before trusting any
claim about the tool — it separates what was verified on hardware from what was not.

### Understanding or continuing the preset work

1. Read [`presets/library.md`](presets/library.md) first. The slot maps are the shared
   vocabulary; every preset document refers to slots by number.
2. Read the song document for the preset you care about.
3. Read the preset safety rules in [`AGENTS.md`](AGENTS.md). The important one: presets
   reference amp and IR slots by number, so replacing a slot silently changes every preset
   pointing at it. Presets P06–P40 are populated factory presets and will be affected by the pending
   slot writes.
4. Record a slot's current contents before overwriting it.

## Safety model

- **The CLI has never written to this pedal.** Every frame it transmits passes a gate that
  accepts only the read header, with a valid checksum and an address inside one of the five
  regions actually read from this device. Building a write frame additionally requires an
  explicit consent object, and every write path is marked `hardware_confirmed=False`, so no
  write frame can reach the wire at all — from the CLI, a script, or a REPL. A test asserts
  this. Details in [`tools/blackboxctl/README.md`](tools/blackboxctl/README.md#safety-model).
- **The M-EFCS GUI is still the only way a slot or preset gets written.** That is where the
  one IR-slot write happened, and where the remaining ones will happen.
- **File-modifying CLI commands are dry runs by default** and need `--yes`. `library
  install` writes into another application's sandbox container; `library restart-editor`
  quits M-EFCS and discards unsaved GUI work.
- **P41 `Wonderwall Live` is protected.** Do not overwrite it, and keep amp slot 1 and IR
  slot 7 at their factory contents while it is.

## Licensing and attribution

This project is not affiliated with or endorsed by M-VAVE. It is independent
interoperability research on hardware and files the owner owns.

- **`tools/blackboxctl/` is GPL-3.0-or-later.** Its packet layout, codec, checksum rule and
  memory map were reconstructed from GPL-3.0 reference code and CC BY-SA 4.0 documentation,
  which require it. Full text in [`tools/blackboxctl/LICENSE`](tools/blackboxctl/LICENSE);
  binding attribution in [`tools/blackboxctl/NOTICE`](tools/blackboxctl/NOTICE).
- **Documentation adapted from `mvave-blackbox-ble` is CC BY-SA 4.0**, attributed to Joel
  Victor (<https://github.com/jvsobrinho/mvave-blackbox-ble>). Share-alike applies: a
  document adapted from it must carry the same licence and say so.
- **No third-party capture, IR, manual, firmware, or binary is committed here.** The
  repository holds maps and documentation only.

The full inventory — every source, its author, its licence, what was taken, and the
unresolved attribution gaps — is [`docs/sources.md`](docs/sources.md).
