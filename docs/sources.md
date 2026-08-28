# Sources and provenance

Every external thing this project depends on, in one place: what it is, where it came from,
what this repository took from it, under what terms, and what a future reader needs to know
before relying on it.

This file is the canonical inventory. Where another document lists sources for its own
narrower scope — `presets/library.md`, the five documents under `docs/reverse-engineering/`,
`tools/blackboxctl/NOTICE` — those lists remain valid and are cross-referenced here, but
this file is the one that is meant to be complete.

Compiled 2026-08-28. URLs are recorded exactly as the documents that fetched them recorded
them; none were re-fetched while writing this file, so treat every "as of" claim as being
as of the session that captured it.

## How to read the licence column

- **Known** means the upstream repository or page states the licence.
- **Unknown** means nobody recorded one. It is not a claim that the work is unlicensed.
- **Quoted for interoperability** means vendor copyright material used as factual reference
  about hardware the user owns. That is a use position, not a licence grant.

---

## 1. Korean community sources

These are what started the project. The decision to abandon the factory presets, the choice
of pack, and the default IR all come from here.

### 1.1 petra7, BlackBox amp modeler and effects processor review (V16.8)

- URL: <https://www.mule.co.kr/m/guide/63185935>
- What it is: a long Korean-language review and setup guide on mule.co.kr, a Korean music
  community. The canonical Korean-language BlackBox resource.
- What this project took: the assessment that the factory presets are a mess and the 20
  built-in IRs are clearly weaker than Soundwoofer and ML IRs (appendix 3); the
  recommendation to keep the 20 stock M-VAVE amp captures but replace the IRs; the known
  device limits recorded in `presets/library.md` (latency figures, no BPM entry, the
  `Analog` delay behaving digitally, Windows-only firmware updates, the Bluetooth
  helicopter noise).
- Terms: forum post, no licence stated. Facts and measurements were extracted; no text was
  reproduced.
- Caveat: written against firmware V16.8. This pedal runs V19 and the app reports
  `BLACKBOX v20`. Behavioural claims may have aged.

### 1.2 petra7, BlackBox capture and IR update information

- URL: <https://www.mule.co.kr/m/guide/63692036>
- What this project took: the capture and IR pack link, the pairing and level advice that
  became the working rules in `presets/library.md` (family pairing, clean captures recorded
  quiet and high-gain captures recorded loud, `IR_included` / `CabOn` / `full rig` captures
  already containing a cabinet, the ML Best IR mid-forward fix of pulling amp MID to about
  15-20, the AMP-on CAB-off preference into a real amp's return), and the author's level
  reference of master 50 / preset 80 / IR 100.
- Terms: forum post, no licence stated.

### 1.3 petra7, free IRs and M-VAVE BlackBox capture profile material

- URL: <https://mule.co.kr/m/muleboard/63236984>
- What this project took: the free-IR pointers, including Soundwoofer and ML Sound Lab.
- Terms: forum post, no licence stated.
- Caveat: this one is on `muleboard`, not `guide`, and the URL is recorded without the
  `www.` prefix the other two carry. Both are as originally recorded.

### 1.4 An unattributed BlackBox owner's write-up

- URL: **not recorded.**
- What this project took: `presets/library.md` opens by citing "two independent Korean
  community sources", the first of which is described only as "a BlackBox owner's write-up"
  saying the factory presets are not catastrophic but there is no reason to use them once
  captures are available, and whose working rig is an `OD + Friedman BE100` capture with an
  IR whose name starts with `ML BEST`. The same write-up is credited later in the same file
  as the likely explanation for the "other IRs produced no sound" symptom.
- Terms: unknown.
- Caveat: **this is a live attribution gap.** A load-bearing claim — half the stated
  justification for abandoning the factory presets — is sourced to a document with no URL,
  no author name, and no date. It cannot currently be re-read or verified. It is also
  possible that this and item 1.3 are the same post; nothing in the repository settles that.

---

## 2. Capture and IR content

### 2.1 The community capture and IR pack

- Filename as recorded in `presets/library.md`: `ANN_Captures_IRs_V16.8.zip`, 44.3 MB.
- Filename as recorded in `docs/reverse-engineering/capture-format-spec.md`:
  `Black_Box_Captures_V16.8` (the extracted directory, which supplied 384 6144-byte and 1249
  6204-byte records plus one zero-byte file to the corpus behind the container analysis).
- URL: the Google Drive folder linked from the petra7 posts above —
  <https://drive.google.com/drive/folders/1f9G_xo7ev32TdYt5zyP6fjiXbPGMSi8->
- Contents: roughly 500 captures plus curated IRs. 24 captures and 83 IRs from it were
  installed into the M-EFCS sandbox library.
- What this project took: the amp and IR slot maps in `presets/library.md`; the corpus that
  the `.am2` / `.am2Data` / `.am3Data` container specification was derived from; the
  observation that much of the pack carries an `am2converter`-written `00 00 32 00` magic
  rather than the `AM2` magic.
- Terms: **mixed and largely unknown.** See section 8.
- Caveats:
  - The two filenames above are not reconciled anywhere. It is not recorded whether the zip
    and the directory are the same artefact under two names or two different downloads.
  - No SHA-256 or size checksum was recorded for the zip itself, so a future download
    cannot be proven identical to the one this work was based on.
  - Google Drive folders are mutable and can be revoked by their owner. The pack is not
    archived inside this repository and there is no fallback mirror recorded.

### 2.2 ML Sound Lab, "The Best IR in the World"

- URL as recorded: <http://bit.ly/MLSoundLab>
- Community discussion thread:
  <https://forum.fractalaudio.com/threads/the-best-ir-in-the-world-free.137347/>
- What it is: a free single-IR giveaway by ML Sound Lab, distributed by the vendor from
  their own Dropbox.
- What this project took: it is the default IR for everything in this repository. It is the
  one slot ever written to the pedal — IR slot 1, `1AC-SeVin` replaced by `1ML_BEST_IR`, on
  2026-08-28.
- Provenance, CONFIRMED: the pack's copy,
  `01A_ML Sound Lab's BEST IR IN THE WORLD_Use_This_IR_as_Main_Default.wav`, is
  byte-identical (SHA-256 `0cafcee0…3e4e2e`) to the file in ML Sound Lab's own free Dropbox
  giveaway. The pack copy is therefore the genuine vendor file, not a re-render.
- Terms: **not recorded.** It is a free giveaway, which establishes that the vendor
  distributes it at no cost; it does not by itself establish redistribution rights. ML Sound
  Lab's own terms for the giveaway were never captured into this repository.
- Caveats:
  - `bit.ly` is a link shortener. It can rot, and its target can be changed by whoever owns
    the link without the URL changing. The vendor's own canonical URL was not recorded.
  - Measured, not assumed: this IR is 48 kHz, 24-bit, mono, 65536 frames (1365 ms), against
    a vendor spec line of "44.1K/24Bit mono WAV, 1024 sampling points". It was written to IR
    slot 1 through M-EFCS and the slot works, which makes it the **one demonstrated case** of
    the import path accepting a non-conforming file. It does not establish what the pedal does
    with a stereo source or a different bit depth. The canonical statement of what is and is
    not demonstrated is in `presets/library.md`, under "What that does and does not prove".

### 2.3 Soundwoofer free IR library

- URL: <https://soundwoofer.com/Library/Index>
- What this project took: nothing. Recommended by petra7 and recorded for completeness; the
  host was unreachable during the session that tried it.
- Terms: unknown, never reached.

### 2.4 M-VAVE community capture and IR sharing site

- URL: <https://community.m-vave.com> — also reachable from the `Community` tab inside
  M-EFCS.
- What this project took: nothing directly, except that the same host serves the official
  ANNBLACKBOX preset PDF (section 4.2).
- Terms: vendor-operated community site; per-upload terms unknown.

### 2.5 am2manager capture search

- URL: <https://am2manager.fly.dev/find-capture>
- What it is: a hosted capture search front-end, operated by the author of `am2manager`
  (section 3.4).
- What this project took: nothing yet; recorded as a lookup route.
- Terms: unknown.

---

## 3. Reverse-engineering prior art

The protocol was not discovered here. It was reverse engineered by the community, and this
project validated that work against one specific pedal and put an interface on it. These
are the obligations that follow.

### 3.1 jvsobrinho/mvave-blackbox-ble — the primary source

- Author: **Joel Victor**
- URL: <https://github.com/jvsobrinho/mvave-blackbox-ble>
- Licence: **documentation CC BY-SA 4.0; reference code GPL-3.0.**
- Files used: `README.md`, `docs/ble_protocol.md`, `docs/memory_map.md`,
  `docs/usb_sysex_protocol.md`.
- What this project took: essentially the whole protocol description — the BLE and USB
  transport description, the SysEx encapsulation, the packet field names, the 92-byte preset
  memory map, the knob and block dictionaries, the routing bytes, and the amp/cab name
  handshake.
- Obligation: **CC BY-SA 4.0 is both attribution and share-alike.** Anything in this
  repository adapted from that documentation must credit Joel Victor and must itself be
  CC BY-SA 4.0. Code written from it inherits the GPL-3.0 reference-code obligation.
  Required attribution string, as used in the documents that carry it correctly: *based on
  protocol research by Joel Victor, https://github.com/jvsobrinho/mvave-blackbox-ble*.
- Corrections this project has made to it, all with evidence in
  `docs/reverse-engineering/device-validation.md`:
  1. the worked Base-128 example's raw and encoded lines do not correspond;
  2. inbound checksums sum from offset 5, not offset 4;
  3. there is no "command type" byte — offsets 3..4 are a 16-bit length;
  4. "AMP names base address `90 18 01 00`" is address `0x90000000` plus a 24-bit size of
     280;
  5. the `Write_Address = Dump_Index + 2` rule does not hold; the mapping is the identity.
- Caveat: correcting an upstream document does not discharge the share-alike obligation. The
  corrected version is a derivative and stays CC BY-SA 4.0.

### 3.2 jvsobrinho/mvave-blackbox-edit (bbedit)

- Author: **Joel Victor**
- URL: <https://github.com/jvsobrinho/mvave-blackbox-edit>
- Licence: **MIT**
- What this project took: `app.js`'s `encodeSysEx` / `decodeSysEx` as the Base-128 codec
  reference; the packet builders, polling loop and handshake as the arbiter wherever the
  upstream prose is ambiguous; the model and parameter tables including the `isDynamic`
  distinction that marks the amp and cab blocks as having a fixed knob layout, which became
  the block dictionaries in `blackboxctl/protocol.py`; `app.js:227` as one of the two
  sources for `PRESET_COUNT = 80`. `descriptions.js:133-248` was read and rejected as a
  name-to-description dictionary rather than a parameter table.
- Obligation: MIT requires that its copyright notice and permission notice accompany
  substantial portions of the software. `tools/blackboxctl/NOTICE` is what serves that
  purpose.

### 3.3 pferreir/cuvave-midi

- Author: **Pedro Ferreira** (`pferreir`)
- URL: <https://github.com/pferreir/cuvave-midi>
- Licence: **GPL-3.0**
- What this project took: the structure of the Base-128 encode/decode algorithm, the
  envelope grammar and the command opcodes, read from `src/parser.rs` and `src/lib.rs`. An
  independent implementation derived from its test vectors was used as a cross-check against
  `blackboxctl`'s codec; the two agree bit for bit on 299 random buffers and on all 13
  SysEx messages in the end-to-end device run — the same phrasing used in
  `docs/reverse-engineering/protocol-spec.md`, `tools/blackboxctl/STATUS.md`,
  `tools/blackboxctl/NOTICE` and `docs/reverse-engineering/reference/README.md`. (Twenty-nine
  inbound SysEx messages exist across all seven logs; thirteen is the count in
  `log_all.txt`, the end-to-end run.)
- Obligation: **this is the strongest single reason `blackboxctl` is GPL-3.0.** GPL-3.0
  reference logic propagates its licence to derivative code.
- Caveat: `docs/reverse-engineering/protocol-spec.md` records this as a named upstream that
  was *not* read directly for that document; `docs/reverse-engineering/protocol-algorithms.md`
  records that its `src/parser.rs` *was* read and reproduced. Both are true of their own
  document. The obligation follows the code that was read.

### 3.4 walterwanderley/am2manager

- Author: **Walter Wanderley**
- URL: <https://github.com/walterwanderley/am2manager>
- Licence: **Apache-2.0**
- Files used: `am2.go`, `cmd/am2converter`, `cmd/am2protector`.
- What this project took: the 60-byte-header / 6144-byte-payload split; the `Mix`, `Level`,
  `GainMax`, `GainMin` header field names used in `blackboxctl/captures.py`; the
  promote-a-bare-`.am2` defaults (Mix 100, Level 100, GainMax 60, GainMin 30); and
  critically the `am2.go:14` `InitData` literal, which is what identifies the `00 00 32 00`
  magic seen across much of the community pack as something `am2converter` wrote rather than
  as file damage.
- Obligation: Apache-2.0 requires that a NOTICE carried by the upstream work be reproduced
  in redistributions, and that modified files be marked. `blackboxctl` vendors no
  am2manager code; it uses field names and a published constant.
- Caveat: `tools/blackboxctl/NOTICE` states the Apache-2.0 NOTICE obligation as though it
  binds unconditionally. In fact clause 4(d) applies only when the upstream distribution
  includes a NOTICE file and you distribute a derivative work of it. Since no code is
  vendored, carrying it is correct practice rather than a strict requirement. Keep it; the
  wording overstates slightly.

### 3.5 suckyble/PocketEdit

- URL: <https://github.com/suckyble/PocketEdit>
- Licence: **unknown, never recorded.**
- What this project took: **nothing.** It is listed for provenance as the editor that bbedit
  was adapted from.
- Caveat, and it matters: `docs/reverse-engineering/protocol-algorithms.md` section 8
  CONFIRMED by fetching it that PocketEdit's `tools/SYSEX_PAYLOAD_FORMAT.md` documents a
  completely different wire format for a different product (Pocket Master) — nibble
  expansion, CRC-8/SMBus, packet-count and packet-index fields, a `0101 04xx` command
  taxonomy, no `00 59` magic, no Base-128, no complement checksum. **The user interface may
  be ancestral to bbedit's; the protocol is not.** Do not mine PocketEdit for BlackBox byte
  formats. `tools/blackboxctl/NOTICE` describes it flatly as "the editor bbedit was adapted
  from" without this qualification.

### 3.6 cbix/mvave-chocolate-sysex

- Author: `cbix`
- URL: <https://github.com/cbix/mvave-chocolate-sysex>
- Licence: **unknown** — recorded as "see repo" and never resolved.
- What this project took: empirical SysEx hex dumps, used as cross-check vectors for the
  frame grammar. `protocol-spec.md` records it as a named upstream that was not read
  directly; `protocol-algorithms.md` records the dumps as having been fetched and used.

### 3.7 michaelforney, Looper Pro protocol notes (gist)

- URL: <https://gist.github.com/michaelforney/d3a2790bb5f8cbcb1c931eabb50b5f20>
- Licence: **unknown** — recorded as "see gist" and never resolved.
- What this project took: the prose statement of the Base-128 model and the envelope field
  layout; named upstream of the SysEx encapsulation.

---

## 4. Vendor material

All of the following are M-VAVE copyright, retrieved from vendor-controlled hosts, and
quoted here for interoperability documentation of hardware the user owns. None of it is
redistributed in this repository. All were fetched to a session scratchpad, not committed.

### 4.1 Firmware release note — the source of the MIDI chart

- URL: <https://yms-file-store.oss-cn-hongkong.aliyuncs.com/software/releaseNote/firmware/BlackBox.txt>
- What it is: the official per-firmware release notes, GBK-encoded with CRLF line endings.
- What this project took: **the official MIDI implementation chart**, which appears in no
  user manual. Transcribed verbatim in `docs/reverse-engineering/official-docs.md` section 1
  from the entry `BLACKBOX_2024_07_08`, decoded with `iconv -f GBK`. It documents USB MIDI
  and BLE-MIDI, PC00-PC80 for presets, and CC 0-5 for the six module toggles. The same file
  supplied the firmware version history.
- Caveat: this is the only published location of the chart. The upstream
  `mvave-blackbox-ble` README's claim that "the manual documents PC for presets, CC for
  basic toggles" is right in substance and wrong about the location.

### 4.2 ANNBLACKBOX preset document

- URL: <https://community.m-vave.com/bbs/api/software?file=ANNBLACKBOX_en.pdf>
  (Chinese edition at the same endpoint with `_cn`)
- What this project took: the official AMP list (20), CAB list (20), and the factory preset
  P01-P40 AMP/CAB table, used as a write-free validation oracle for the 92-byte preset
  memory map and the name string blocks; also one of the two sources for `PRESET_COUNT = 80`.

### 4.3 ANN white paper

- URL: <https://yms-file-store.oss-cn-hongkong.aliyuncs.com/manual/white-paper/ANN.pdf>
- What this project took: the vendor's account of what ANN (Audio Neural Network) is.

### 4.4 MK300 MIDI control mapping table

- URL: <https://yms-file-store.oss-cn-hongkong.aliyuncs.com/software/releaseNote/firmware/MK300%20MIDI%20Control%20Mapping%20Table.docx>
- What this project took: a sibling product's full MIDI CC chart, used to establish family
  conventions.

### 4.5 Chocolate Plus software instructions

- URL: <https://manualf.oss-cn-hongkong.aliyuncs.com/manual/CUBE-TURNER/Chocolate%20Plus-Software%20instructions.pdf>
- What this project took: the Chocolate Plus MIDI sender modes, needed to decode the mode
  names used in the BlackBox chart.

### 4.6 M-VAVE download index

- URL: <https://www.m-vave.com/download>
- What this project took: the source of every vendor URL above, plus the corroborating
  observation that only FM-1 and MK300 carry MIDI control document links while ANNBLACKBOX
  carries only Preset EN / Preset CN.

### 4.7 Firmware container

- File: `BlackBox-V19-Firmware-2025-10-17.fwsc`, SHA-256
  `6ce0c976bc1a563388d5d8acade9912044543823a0825891b1716aec419db993`. Pre-existing on the
  user's machine, not fetched.
- Next version for comparison:
  <https://yms-file-store.oss-cn-hongkong.aliyuncs.com/software/firmware/BlackBox.fwsc>
- What this project took: entropy and structure analysis only. Established as a JieLi
  AC791N container, mostly opaque. Two labelled HYPOTHESES about selective encryption and
  the absence of signing are recorded in `official-docs.md` section 7, along with the
  V19-vs-V20 diff that would settle them.
- Caveat: the file is not committed and must not be. It is vendor firmware.

### 4.8 Korean manual — not an M-VAVE document

- File: `BlackBox_Manual_kor_web.pdf`, pre-existing.
- What it actually is: a **Gopherwood "SquareMoon" Korean rebrand manual**, © 주식회사 고퍼우드
  (Gopherwood Co., Ltd.), `gopherwood.co.kr`. Same hardware.
- What this project took: the hard specification limits table in `official-docs.md` section 6
  — sample rate, dynamic range, module counts and types, delay ranges, tuner reference,
  battery and current figures, I/O.
- Caveat: **cite it for specifications, not for protocol.** It contains no MIDI content.

### 4.9 A discarded source, recorded so nobody re-fetches it

An SEO-spam PDF from a Webflow CDN that keyword-stuffed the manual text was fetched and
deleted as worthless. `manuals.plus` was used only for a targeted transcription of the
English manual's section list, which confirmed the absence of MIDI content there.

---

## 5. Proprietary binaries inspected on this machine

Read-only static inspection of software the user has installed. No code was copied, no
debugger was attached, and nothing from these is redistributed.

| Item | Owner | What was taken |
| :--- | :--- | :--- |
| `/Applications/M-EFCS.app/Contents/Frameworks/libamx_parser.dylib` | M-Vave / Zhuhai Shengke | The neural topology and exact weight offsets inside a capture payload, via `objdump` and `nm`. The exported `_calc_bias_gru` symbol is the anchor. Also the `_ANN_Unit_proc` symbol referenced in `official-docs.md`. |
| `M-EFCS.app/…/App.framework/…/lib/resources/bin/blackbox/*_ampCab.bin` | M-Vave | Factory amp and cab blobs, used to establish the flash record layout. |

The user's own M-EFCS library under
`~/Library/Containers/com.digAmp.dgAmp/Data/Documents/M-EFCS` was also read for the corpus
counts. It is the user's own data, and the workspace rules make it read-only.

## 6. Other references

- **Green Day rig rundown**, Premier Guitar:
  <https://www.premierguitar.com/videos/rig-rundown/green-day>. Cited in
  `docs/superpowers/specs/2026-07-26-greenday-boulevard-blackbox-presets-design.md` for
  Armstrong's clean preamp and modified Marshall heads into 1960B cabinets with Vintage 30
  speakers, which is what justifies the P04 and P05 signal paths. Editorial content,
  copyright Premier Guitar; used as a factual reference, not reproduced.
- **GNU General Public License v3**, <http://www.gnu.org/licenses/> — the full text is
  vendored at `tools/blackboxctl/LICENSE`, which is exactly what the GPL requires.

---

## 7. Licence obligations that bind this repository

Three distinct obligations are live at once. They are not interchangeable.

**GPL-3.0 on `tools/blackboxctl/`.** The CLI is GPL-3.0-or-later, declared in
`pyproject.toml`, with the full text in `LICENSE` and attribution in `NOTICE`. This is not a
default choice. Its packet layout, Base-128 codec, checksum rule, memory map and command
builders were reconstructed from GPL-3.0 reference code (`cuvave-midi`) and CC BY-SA 4.0
documentation (`mvave-blackbox-ble`). Anyone redistributing the CLI, modified or not, must
carry `LICENSE` and `NOTICE`, must keep the source available, and must license their
modifications GPL-3.0-or-later. Every module carries a one-line GPL notice in its docstring
pointing at both files.

**CC BY-SA 4.0 on documentation adapted from `mvave-blackbox-ble`.** Attribution alone is
not enough — share-alike means a document adapted from that documentation must itself be
CC BY-SA 4.0, and anyone reusing it must say so. **All seven documents under
`docs/reverse-engineering/` now carry an explicit self-label**: `protocol-spec.md`,
`capture-format-spec.md`, `protocol-algorithms.md`, `device-validation.md`,
`official-docs.md`, and — stated in `README.md`'s provenance section — that directory's own
`README.md` and `contradiction-register.md`. An earlier revision of this file said three of
them did not; that was true when the audit was written and is no longer true.

**MIT and Apache-2.0 notice-carrying.** `tools/blackboxctl/NOTICE` is the single artefact
that discharges the MIT notice obligation for `mvave-blackbox-edit` and carries the
Apache-2.0 notice for `am2manager`. It must travel with any redistribution of the CLI.

**Trademarks.** "M-VAVE", "CUVAVE", "BlackBox" and "M-EFCS" are the marks of their owners.
This project is not affiliated with, endorsed by, or supported by them. It exists so that
the owner of a BlackBox can talk to their own hardware.

Note an unresolved detail: `protocol-spec.md` and `capture-format-spec.md` name the mark
owner as **Zhuhai Shengke Intelligent Technology Co., Ltd.**, while `official-docs.md`
attributes vendor material to **M-VAVE / Sinco / Cuvave (Zhuhai Rich Technology)**. These
are not obviously the same entity and nothing in the repository reconciles them. Neither was
verified against a corporate registry. Treat both as unconfirmed.

---

## 8. Redistribution position

**No capture, IR, firmware, manual, or other third-party binary is committed to this
repository.** The census below is scoped to **the commit that adds this file**, not to the
tree as it stood before it: that commit adds six Markdown files, seven plain-text device
logs and four Python reference modules. Re-run `git ls-files` and `file --mime-type` at
commit time if either number needs to be trusted again.

As of that commit: **58 tracked files — 21 Markdown, 26 Python, 7 plain-text device
transcripts, one `pyproject.toml`, one `LICENSE`, one `NOTICE`, one `.gitignore`.**
`file --mime-type` reports 53 as `text/plain`, 3 as `text/x-script.python` and 2 as
`inode/x-empty` (the two empty `__init__.py` files) — nothing binary. There is no `.wav`, no
`.am2` / `.am2Data` / `.am3Data`, no `.zip`, no `.pdf`, no `.fwsc`.

The seven `.txt` files are the **first non-Markdown text in the repository** and deserve a
sentence of their own: they are `docs/reverse-engineering/logs/log_{all,amp,cab,flash,
generic,preset,ram}.txt`, verbatim transcripts of this project's own read-only USB MIDI
session against the owner's own pedal on 2026-08-28. They contain no third-party content —
the hex in them is the pedal's own output — and they cannot be recaptured without the
hardware, which is why workspace rule 5 forbids deleting them.

What the repository does contain is **maps and documentation**: slot maps naming files by
name, install procedures, measured format findings, and specifications. Reproducing a
filename is not redistributing the file.

That distinction is what keeps the position defensible, because the upstream content is not
clean:

- **The community pack redistributes third-party captures and IRs of mixed provenance.** It
  was assembled by community members from many origins. For most files the provenance is
  whatever the original uploader supplied, which in practice is often nothing. Capture
  filenames in the pack reference commercial amplifier names and, in places, other vendors'
  modelling products; the pack does not establish that those uploads were authorised.
- **The one file whose provenance is established is the ML Best IR**, and it is established
  by checksum against the vendor's own free giveaway rather than by any statement travelling
  with the pack.
- **Even for that file, redistribution rights were never confirmed.** Free-of-charge is not
  the same as freely redistributable.

The honest statement, and the one this repository should keep making: the pack was
downloaded and used locally on hardware the user owns, its contents were installed into the
user's own sandbox library, and nothing from it is republished here. Anyone who wants to
redistribute any of it needs to establish rights per file, which this project has not done
and is not in a position to do.

The same applies to the vendor material in section 4 and the proprietary binaries in
section 5: fetched, read, analysed, quoted for facts, never republished.

---

## 9. Attribution gaps and unresolved points

Recorded rather than fixed, so that a future reader knows what is missing rather than
assuming the inventory is complete.

1. ~~**Three reverse-engineering documents derive from CC BY-SA 4.0 material without
   labelling their own licence.**~~ **CLOSED.** All five now carry an explicit
   "this file is licensed CC BY-SA 4.0" line with the attribution string —
   `protocol-algorithms.md` in its attribution section, `device-validation.md` in
   "Attribution and licence", `official-docs.md` at the end of its source list — and the
   two documents added later, `docs/reverse-engineering/README.md` and
   `contradiction-register.md`, are covered by an explicit statement in the former's
   provenance section. Recorded as closed rather than deleted so the obligation is not
   forgotten: share-alike is not discharged by crediting.
2. **The repository has no top-level `LICENSE`.** `tools/blackboxctl/LICENSE` covers the
   CLI subtree only, so the status of `AGENTS.md`, `presets/` and `docs/superpowers/` is
   still undefined by any licence file. The *entry point* half of this gap is closed: the
   root `README.md` now exists and carries a `## Licensing and attribution` section with
   routes to `LICENSE`, `NOTICE` and this file.
3. **One of the two founding Korean sources has no URL** (section 1.4). It cannot be
   re-read, re-verified, or credited.
4. **The community pack is identified by two different names** in two documents
   (section 2.1), with no checksum for either, hosted on a mutable Google Drive folder.
5. **ML Sound Lab's terms were never captured** (section 2.2), and the only recorded URL is
   a `bit.ly` redirector whose target the link owner can change.
6. **Three prior-art sources have unrecorded licences** — `PocketEdit`,
   `mvave-chocolate-sysex`, and the michaelforney gist. Two of them supplied cross-check
   vectors that were actually used.
7. **`NOTICE`'s PocketEdit entry is thinner than the evidence.** It repeats the
   "editor bbedit was adapted from" claim without the finding in
   `protocol-algorithms.md` section 8 that the protocols are entirely unrelated. Anyone
   reading `NOTICE` alone could reasonably go looking for BlackBox byte formats there.
8. **`NOTICE`'s Apache-2.0 sentence slightly overstates the obligation** (section 3.4).
9. **The trademark owner is recorded two incompatible ways** (section 7).
10. ~~**`tools/blackboxctl/README.md` says "212 tests"**~~ **CLOSED.** The suite was run:
    `python -m pytest` reports `221 passed` (Python 3.14.3, pytest 9.1.1, 2026-08-28), so
    221 was right and 212 was stale. `tools/blackboxctl/README.md`,
    `tools/blackboxctl/STATUS.md` and the root `README.md` now agree. Two details of this
    entry as first written were also wrong: `AGENTS.md` never gave a test count at all, and
    the figure `STATUS.md` quoted came from the untracked `.pytest_cache`, not from a run.
    See contradiction-register C24 and staleness-register B5.
