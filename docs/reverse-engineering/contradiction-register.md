# Contradiction register

An audit of every place the five reverse-engineering documents disagree with each other,
with the repository's other documents, or with themselves.

Audited 2026-08-28. No command was sent to the pedal; it was unplugged. The M-EFCS
library was read, never modified. No code under `tools/blackboxctl/` was changed.

> **This is an audit snapshot, taken *before* the documentation consolidation, plus a
> disposition column added afterwards.** Every row in Part 2 now carries a **Status**:
> **APPLIED** with the file and section where the fix landed, **OPEN**, or
> **REPORTED-ONLY** for the two findings about code that workspace rule 4 correctly left
> alone (C23, C30's gate). The "Recommended resolution" column is the audit's own wording
> and is deliberately preserved; where it reads as an instruction, the Status column is the
> record of what actually happened. Do not re-do an APPLIED row.
>
> **Licence.** This document is adapted from CC BY-SA 4.0 documentation by Joel Victor
> (<https://github.com/jvsobrinho/mvave-blackbox-ble>) and is therefore itself licensed
> **CC BY-SA 4.0**. Attribution: *based on protocol research by Joel Victor,
> https://github.com/jvsobrinho/mvave-blackbox-ble*.

## Sources audited

| Short name | Path |
| :--- | :--- |
| `protocol-spec` | `docs/reverse-engineering/protocol-spec.md` |
| `protocol-algorithms` | `docs/reverse-engineering/protocol-algorithms.md` |
| `device-validation` | `docs/reverse-engineering/device-validation.md` |
| `capture-format-spec` | `docs/reverse-engineering/capture-format-spec.md` |
| `official-docs` | `docs/reverse-engineering/official-docs.md` |
| `library.md` | `presets/library.md` |
| `AGENTS.md` | `AGENTS.md` |
| `hana.md` | `presets/hana.md` |
| `README` / `STATUS` | `tools/blackboxctl/README.md`, `tools/blackboxctl/STATUS.md` |
| `protocol.py` | `tools/blackboxctl/blackboxctl/protocol.py` |

## Ranking rule used

`device-validation` holds the only bytes this pedal actually sent and received, so it
outranks documents derived from third-party prose. Where a claim can be checked
arithmetically against those bytes, the arithmetic was re-run during this audit and the
result is stated. Where the bytes cannot distinguish two readings, the entry says
**unresolved** and names the test.

Arithmetic re-run here, independently of every document:

* All seven transmitted commands in `device-validation`'s safety record encode to exactly
  the SysEx strings logged beside them, under the LSB-first continuous 8→7 packer. 7/7.
* Their stored checksums reproduce at sum-offsets 4, 5 **and** 6 (all outbound frames have
  `byte[4] == byte[5] == 0x00`).
* The two 295-byte name replies have `byte[4] == 0x01`; their stored checksums reproduce
  at offsets 5 and 6 but **not** at 4. Offset 4 fails 2/7; offsets 5 and 6 each explain
  7/7 and are indistinguishable on this corpus.
* All 20 factory IR `.wav` files in `cabFile` were re-measured by RIFF chunk walk.

---

## Part 1 — the three frame models

This is the headline dispute, so it is resolved before the table.

### The three descriptions

| | Where | Model |
| :-- | :--- | :--- |
| **M1** | `protocol-spec` §2.7.1 (it was §2.1–2.2 as originally published; §2.1–2.2 now carry the reconciled model, so a reader following this row must go to §2.7.1) | `header(3) \| command type(1) \| routing(3) \| target id(1) \| padding(2) \| sub-address(2) \| payload@14 \| cs`, with a **third, different** "string form" in which the 32-bit address sits at offsets **10–13** and there is no length field |
| **M2** | `protocol-algorithms` §3 | `00 59 \| cmd(1)@2 \| payload_length 24-bit LE@3..5 \| payload@6.. \| cs`, total `7 + length`; for `0x22`/`0x23` the payload is `space(1) \| address LE32 \| length LE24 \| data` |
| **M3** | `device-validation` STEP 7 | `magic(3) \| length LE16@3 \| space LE16@5 \| address LE32@7 \| size LE24@11 \| payload@14 \| cs` |

### Resolution

**M2 and M3 are the same model.** For every packet either can parse they carve the same
bytes into the same values and produce byte-identical output. The only real difference is
who owns **byte 5**: M2 calls it the top byte of a 24-bit payload length, M3 calls it the
low byte of a 16-bit space selector. Byte 5 is `0x00` in all 14 observed packets, so no
observation distinguishes them. They would only diverge at a payload of 65528 bytes or
more, which cannot occur — the largest transfer in the address map is 280 bytes.

**M1 is a misalignment of the same bytes and must be retired.** It is not merely a
different naming of the same fields:

* M1's "routing" field is `00 00 04` / `00 00 05` at offsets 4–6. The two 295-byte name
  replies have `01 00 05` there, because byte 4 is the high byte of the length 288. M1
  cannot describe a packet the device actually sent.
* M1's "string form" reads the AMP-names address as `0x00011890` at offsets 10–13, with
  no length field. The device's own reply echoes address `00 00 00 90` at offsets 7–10
  and size `18 01 00` = 280 at offsets 11–13, and its length field `20 01` = 288 = 280 + 8
  is otherwise unexplained. This is the single most load-bearing error in M1: a client
  built on it cannot form a generalised read.
* M1's "command type" at offset 3 tracks the packet size exactly (`08`→15, `09`→16,
  `0A`→17, `0E`→21, `64`→107) because it is the length low byte. The device returns `0x64`
  in every 92-byte read reply, which under M1 reads as the Write-Flash opcode being echoed
  at us.

**But M2 is strictly more general than M3, and this matters.** M3 fixes a 15-byte minimum
frame with space/address/size always present. Three frames documented in the corpus cannot
be expressed in it at all:

| Frame | Bytes | M3 | M2 |
| :--- | :--- | :-- | :-- |
| Success ACK | `00 59 00 01 00 00 00 FF` (8) | rejected, "frame too short" | `cmd 0x00`, len 1, payload `00`, cs `FF` ✔ |
| Query name/version | `00 59 11 00 00 00 FF` (7) | rejected | `cmd 0x11`, len 0, cs `FF` ✔ |
| cbix discovery reply | `00 59 11 1B 00 00 "FootCtrl_031"… DF` (34) | space would read `0x4600` — nonsense | `cmd 0x11`, len 27, cs `DF` ✔ (verified here) |

So: **space / address / size are the payload structure of opcodes `0x22` and `0x23`, not
universal header fields.** `STATUS.md` already notices the symptom — "`ACK_FRAME` … is only
8 bytes … so it does NOT fit the field model at all" — and attributes it to a possible
upstream transcription error. It is not a transcription error; it is M3 being a
specialisation.

### Recommended single model

```
offset 0..1   00 59                      fixed magic
offset 2      command                    00 ACK/init, 11 query, 21 erase, 22 write, 23 read
offset 3..5   payload length, 24-bit LE  (bytes 4..5 are 00 for every packet ever seen)
offset 6..    payload, exactly `length` bytes
last byte     checksum = (0xFF - sum(payload)) & 0xFF

payload of 0x22 / 0x23:
  [0]      space      04 = parameter/preset, 05 = string block
  [1..5]   address    32-bit LE
  [5..8]   size       24-bit LE
  [8..]    data       present on writes and read replies; absent on read requests
```

Frame length is `7 + length`. For `0x22`/`0x23` this puts data at offset 14, which is what
all three documents already agree on. Present M3's field table as the derived view for
memory operations — it is the one the code uses and the one that is confirmed on this
hardware — and mark byte 5 explicitly as **unresolved between "length bits 16–23" and
"space high byte"**, settled only by a transfer of 256 bytes or more, which the address map
does not contain.

### What the working code encodes

`protocol.py` implements **M3 exactly** (`build_frame`, lines ~283–309; `parse_frame`,
~311–330): `magic(3)`, `length LE16` at 3, `space LE16` at 5, `address LE32` at 7,
`size LE24` at 11, payload at 14. `checksum_tx` sums from offset 4, `checksum_rx` from
offset 5, and `MAX_TX_PAYLOAD = 247` deliberately refuses to build any frame where those
two would diverge. That is a correct and conservative implementation for the read paths it
is allowed to use, and it produced the byte-exact frames the pedal answered. Its one
consequence is that `parse_frame` raises `frame too short` on an 8-byte ACK, so the tool
could not decode an acknowledgement even if one arrived — unreachable today because every
write path is `hardware_confirmed=False`. **Reported, not changed** (workspace rule 4).

---

## Part 2 — register

Ordered by severity. "Settled by device-validation" means the raw bytes in that document
decide it.

| # | Status | Sev | Issue | Side A | Side B | Evidence cited | Settled by device-validation? | Recommended resolution (the audit's own wording, preserved) |
| :-- | :--- | :-- | :--- | :--- | :--- | :--- | :--- | :--- |
| C01 | **APPLIED** — `protocol-spec` §2 (canonical), §2.7.1 (M1 retired) | high | Wire frame field layout | `protocol-spec` §2.1–2.2 as originally published, now retired to §2.7.1 (M1): command type @3, routing @4–6, target @7, sub-address @10–11 | `protocol-algorithms` §3 (M2) and `device-validation` STEP 7 (M3): length @3, space, address @7, size @11 | A: upstream CC BY-SA prose plus `bbedit` hard-coded literals. B: `cuvave/src/parser.rs` grammar; 14 real packets | **Yes.** M1 cannot describe the two 295-byte name replies (`byte[4] == 0x01`) | M1 was retired; the M2 outer grammar was adopted with M3's field table as the `0x22`/`0x23` payload view, and M1's text kept only as a labelled "how the upstream doc reads it, and why that is wrong" note |
| C02 | **APPLIED** — `protocol-spec` §2.2 address map, §10 row 6 struck | high | AMP/CAB name-block base address | `protocol-spec` §3.1, §2.2 "string form": address `0x00011890` / `0x00011880`, no length field | `protocol-algorithms` §8 item 5 and `device-validation` STEP 7: address `0x90000000` / `0x80000000`, size 280 | A: upstream `memory_map.md` "AMP Names Base Address `90 18 01 00` (Little Endian)". B: reply echo | **Yes.** Reply bytes 7–10 = `00 00 00 90`, bytes 11–13 = `18 01 00` = 280 = 20 × 14 | Address `0x90000000` / `0x80000000`, size 280. `protocol-spec`'s "real asymmetry, not a typo" verdict (§10 row 6) was wrong and has been struck |
| C03 | **APPLIED** — `device-validation` STEP 2, STEP 3, correction 5; `protocol-spec` §2.1, §10 row 5b | high | Is offset 3 a command type? | `protocol-spec` §2.1: "Command type — `08` read, `09` 1-byte write, `0A` knob, `0E` routing, `64` flash write" | `protocol-algorithms` §8 item 2 and `device-validation` correction 5: it is the length low byte | A: upstream table. B: values track packet size exactly; device returns `0x64` in read replies it was never sent | **Yes.** `0x64` appears in every 92-byte reply (92 + 8 = 100); `0x0C` in the 19-byte sync reply (4 + 8 = 12); `20 01` in name replies (280 + 8 = 288) | Length field. The real command byte is offset 2. `device-validation` STEP 2 and STEP 3 called these "command type `0x64`" / "`0x0C`" in their own verdict text, an internal contradiction with its own STEP 7; both verdicts were rewritten in terms of the length field |
| C04 | **APPLIED** — `protocol-spec` §2.3; `device-validation` correction 2. Offsets 5 vs 6 stay **OPEN** (U1) | high | Checksum byte range | `protocol-spec` §2.3 and `bbedit`: `0xFF - sum(frame[4:len-1])` | `device-validation` correction 2: sum from offset **5**. `protocol-algorithms` §3: sum of **payload only**, i.e. offset 6 | A: upstream prose + `app.js:551`. B: 7 unique replies. C: `cuvave` `calc_checksum` is literally `!sum(payload)` | **Partly.** Re-verified here: offset 4 explains 5/7, offsets 5 and 6 each explain 7/7. Offsets 5 and 6 are indistinguishable — byte 5 is `0x00` in every observed packet | The payload-sum rule (offset 6) is now stated as the definition, with a note that offsets 4/5/6 coincide whenever bytes 4–5 are zero and that offset 4 is refuted. `protocol.py`'s tx@4 / rx@5 split was kept, which is safe for every frame it can build |
| C05 | **APPLIED** — `protocol-spec` §2.5 | high | Does the frame model cover ACK / query / erase? | `protocol-spec` §3.3: 8-byte ACK, CONFIRMED (docs+code) | `STATUS.md` and `protocol.py`: "only 8 bytes … does NOT fit the confirmed field model … either the doc transcribed it wrongly or ACKs use a different shape" | A: upstream + `bbedit`. B: M3's 15-byte minimum | **No — but the arithmetic settles it.** Verified here: under M2 the ACK is `cmd 0x00, len 1, payload 00, cs FF` and validates; so do the 7-byte query and the 34-byte cbix discovery reply | The doc is not wrong and ACKs are not a different shape — M3 is a specialisation. Adopting M2 (C01) dissolved this. Note that `parse_frame` would reject a real ACK; that is latent, not live, because no write can be sent |
| C06 | **APPLIED** — `README.md` "The three IR figures, reconciled"; `official-docs` §3; `capture-format-spec` §7.1; `presets/library.md`. Code figure is C23 | high | IR length budget | `official-docs` §3: **1024 samples / 23.2 ms**, CONFIRMED from three official sources | `capture-format-spec` §7.1: the on-device `CAB` record is **1358 samples / 30.8 ms**, CONFIRMED from the factory `*_ampCab.bin` blobs. `library.md`: the pedal's own factory IRs measure **2048** frames | A: Korean manual p.13, vendor product copy, web search. B: 4096-byte record, `0x14` + 4074 bytes = 1358 × 3. C: `wave` on two library files | No — the protocol session never touched IR storage | They measure three different things and all three are now stated as such: 1024 = vendor spec line (intent); 1358 = what an on-device `CAB` flash record physically holds (the real ceiling); 2048 = the frame count of most factory source `.wav` files in the Mac library, which are *inputs* to the upload path, not device storage. The on-device figure outranks the others for "what the pedal keeps". `protocol.py`'s sibling `captures.py` uses `IR_TAPS = 1024` and warns from that; reconcile deliberately |
| C07 | **APPLIED** — `protocol-spec` §4.1, §10 row 2. Write direction stays **OPEN** (U2) | high | `Write_Address = Dump_Index + 2` — confidence label | `protocol-spec` §4.1: identity, **CONFIRMED**, "proven four ways". `protocol-algorithms` §8 item 4: identity, CONFIRMED (code) | `device-validation` correction 7 and `README`/`STATUS`: identity, **HYPOTHESIS (high confidence)** — "not promoted to CONFIRMED because no write was performed" | A: doc table read in one radix, `bbedit` indexing, arithmetic closure at 92. B: read-direction decode only | **Yes, for reads.** Seven independently known P41 GUI values decode correctly under identity; all of P01's and P03's values match `hana.md`'s recorded slot contents under identity (checked in this audit) | The claim was split. **Read direction: CONFIRMED** — the decode of the 92-byte image uses identity and matches on three presets. **Write direction: HYPOTHESIS** — `0x10000000 + dump_index` is inferred from documented write literals only. Both documents are right about different halves; neither says which half it means |
| C08 | **APPLIED** — `protocol-spec` §1.4, §10 row 1 | high | The Base-128 worked example | `protocol-spec` §1.4 and §10 row 1: **UNRESOLVED**, "the single most important thing to verify on real hardware", "do not ship a client that silently assumes either answer" | `protocol-algorithms` §2 and `device-validation` STEP 1: settled — the doc pasted an encoded array from a different message; the algorithm is correct | A: local recomputation only. B: `decode(doc_encoded)` is exactly `cuvave`'s `test_encode_1` raw vector; hardware answered every frame the codec built | **Yes.** All seven transmitted commands re-encode bit-exactly here, and the device replied correctly to all seven | `protocol-spec` §1.4 and §10 row 1 were stale and have been rewritten as CONFIRMED-doc-defect. Trustworthy test vectors, in order: (1) the seven request/SysEx pairs and three reply pairs logged in `device-validation`, now mirrored in `tools/blackboxctl/tests/fixtures/device_frames.py`; (2) `cuvave`'s `parser.rs` vectors; **never** the `usb_sysex_protocol.md` pair |
| C09 | **APPLIED** — `protocol-spec` §10 row 15; `device-validation` correction 9 | med | `.am2` vs `.am3` vs `.am4` | `protocol-spec` §4.2, §10 row 15: "`.am4` is unverified upstream prose, treat the doc as wrong". `protocol-algorithms` §8 item 7: "the `.am4` claim is wrong for this device" | `capture-format-spec` §4.2: **AM4 is real** — 7868-byte record, 928-parameter GRU, shipped in `blackbox_am4_ampCab.bin`. `official-docs` §5: AM2→AM3→AM4 are firmware generations. `device-validation` "Corrections and clarifications to the published documentation" item 9: unresolved | A: absence from the user's library. B: factory blob hexdump; vendor release notes and SINCO changelog | No — the wire protocol does not touch file extensions, and `device-validation` says so | One statement: the **record magic** `AM4\0` is real and confirmed in factory data; the **file extension** `.am4` has never been observed on this machine; the upstream doc conflated the two. `protocol-spec` and `protocol-algorithms` were stale and now defer to `capture-format-spec` §4.2 and `official-docs` §5 |
| C10 | **APPLIED as a recorded UNRESOLVED** — `README.md` §D, `official-docs` §5, `presets/library.md`, `device-validation` open questions. The question itself is **OPEN** (U4) | med | Which firmware is on the pedal | `official-docs` §5: "**The pedal in this project runs V19** (2025-10-17) … so this device supports AM2 and AM3 but NOT AM4" — labelled HYPOTHESIS, inferred from a firmware filename on disk | `library.md`, `AGENTS.md`, `hana.md`, `boulevard-of-broken-dreams.md`: "Connected device label: **`BLACKBOX v20`**" | A: filename `BlackBox-V19-Firmware-2025-10-17.fwsc`. B: M-EFCS's own connection label, recorded four times | No — no version was read over the wire | **Unresolved, and consequential** — it decides whether AM4 captures are loadable. `official-docs`' inference is the weaker evidence, but "BLACKBOX v20" may be a product/model label rather than a firmware version, so the labels are not directly comparable. Settling test, read-only and safe: send the `0x11` query (`00 59 11 00 00 00 FF`), or read the device settings screen. Recorded as UNRESOLVED in `README.md` §D, `official-docs` §5, `library.md` and `device-validation`'s open questions. Until a version is read, do not repeat "this device is V19" as fact |
| C11 | **APPLIED** — `official-docs` §2 restricts the oracle; corroboration recorded in `device-validation` STEP 6a and `presets/hana.md`, with the Low Cut caveat this row originally missed | med | The factory P01–P40 table as a validation oracle | `official-docs` §2: "This table is a **free, no-write validation oracle** … read slot 0 and check that its AMP model id decodes to `1J900_CL` and its CAB id to `1AC-SeVin`" | `device-validation` STEP 6a: flash index 0 decodes to AMP `0x01` → `FD_CL`, CAB `0x0A` → `FD_TW1980` | A: `ANNBLACKBOX_en.pdf` extracted with pdfminer. B: real flash bytes | **Yes, and it falsifies the oracle for this pedal** | The oracle is valid only for slots never edited. P01–P05 and P41 are known-edited on this device. Cross-checked in this audit: `device-validation`'s P01 and P03 decodes match `hana.md`'s built-in-amp-model records field for field. **One correction to this row as first written:** the two CAB Low Cut fields are not exact matches. `protocol-spec` §4.3 gives `Hz = 20 + (raw/100) * 280`, so raw 24 is 87.2 Hz and raw 22 is 81.6 Hz against GUI records of 87 and 81 — both reproduce only under a truncating display convention, which is inferred from these two samples and documented nowhere upstream. Those two fields agree to within one display step; every other field is an exact integer match. That corroboration is still stronger than the vendor table and has been recorded in `device-validation` STEP 6a and `presets/hana.md`. `official-docs`' oracle claim is now restricted to untouched slots (P06 onward) |
| C12 | **APPLIED** — `presets/library.md` "IR format, measured rather than assumed" | med | Which factory IR is 32-bit float | `library.md`: "factory `7VOX_AC30` … 44.1 kHz, **32-bit float**" | `STATUS.md` and `captures.py`: "the pedal's own CAB slot 10 IR, `10SoldSC412.wav`, **is** 32-bit float". `capture-format-spec` §8.1: exactly one PCM-32 file and one IEEE-float-32 file among 293 | A: `wave` module, which reports bit depth but not format tag. B: format-tag inspection | No — file formats, not protocol | **`library.md` is wrong.** Re-measured in this audit by RIFF `fmt ` chunk: `7VOX_AC30.wav` is format tag **1** (integer PCM), 32-bit, 2048 frames; `10SoldSC412.wav` is format tag **3** (IEEE float), 32-bit, 1020 frames. Both statements are about different files and `capture-format-spec`'s counts reconcile them. `library.md` was corrected. Note that its "the pedal is demonstrably running a 32-bit float factory IR" argument did **not** survive intact: the measurement is of the Mac-side source `.wav`, and the on-device `CAB` record is 24-bit PCM (`capture-format-spec` §7.1), so `library.md` now states only what is demonstrated |
| C13 | **APPLIED** — `protocol-spec` §3.1, §9.2, §10 row 13 | med | Read Flash Preset, and reply lengths 107/19/8 | `protocol-spec` §3.1, §9.2: **HYPOTHESIS** — "never exercised by `bbedit`", "the response length and framing are assumed, not observed"; reply lengths are "inherited claims" | `device-validation` STEP 2, 3, 6: CONFIRMED — 107-byte and 19-byte replies observed, flash reads answered at indices 0, 2 and 40 | A: absence of a code path upstream. B: the logged replies | **Yes** | `protocol-spec` §3.1, §9.2 and §10 row 13 were stale; all three were rewritten as CONFIRMED citing `device-validation` STEP 6. The 8-byte ACK stays HYPOTHESIS — it is the one length still unobserved, because no write was sent |
| C14 | **APPLIED** — `protocol-spec` §6.2; `device-validation` correction 3 | med | Name-block fragmentation and stop condition | `protocol-spec` §6.2–6.3: expect fragmentation; run a stateful accumulator; "stop when 20 non-empty names have accumulated" | `device-validation` STEP 4 and correction 3: over USB the whole dictionary arrives as **one 340-byte SysEx**; records are a fixed **14-byte stride**, so slot *N* is at `body[(N-1)*14]` and null-splitting is unnecessary | A: upstream BLE MTU reasoning. B: the logged 340-byte message; 19 consecutive deltas of exactly 14 on both blocks | **Yes** | The accumulator is kept documented as the BLE path and `protocol-spec` §6 now leads with the USB reality: one message, direct indexing |
| C15 | **APPLIED** — `protocol-spec` §6.2, §10 row 8; `device-validation` correction 4 | med | The trailing checksum byte on a name fragment | `protocol-spec` §6.2: `bbedit` does not strip it, but "the bug is masked … harmless" | `device-validation` correction 4 and STEP 5: the AMP reply's checksum is `0x36` = ASCII `"6"`, and a naive null-split yields a **phantom 21st name `"6"`** | A: reasoning about printable ranges. B: the actual byte | **Yes, and it refutes "harmless"** | Not masked. Strip the trailing checksum before splitting, or take only the first 20 records. `protocol-spec` §6.2 and §10 row 8 were corrected accordingly |
| C16 | **APPLIED** — `capture-format-spec` §9 | med | Capture validation: error or warning? | `capture-format-spec` §9: **Errors** (reject the file) include `magic ∈ {AM2\0, AM3\0}` and `size ∈ {6144, 6204}`; its own corpus run reports `ampFile … PASS 33 FAIL 6` | `STATUS.md`: "all 39 `ampFile` … entries parse **without error** (previously 6 amp and 1 IR were refused)"; corrupt magic is "treated as a warning, not a refusal, because a hard refusal … would block 4 of the files `presets/library.md` requires" | A: the reference parser `amx.py`. B: the shipped `captures.py` | No — file formats | Both are defensible; they are simply different policies, and the spec now describes a parser the tool deliberately does not implement. A line was added to `capture-format-spec` §9 recording that `blackboxctl` demotes the magic and IR-format rules to warnings, and why |
| C17 | **APPLIED** — `official-docs` §2; `README.md` §C. The read that would settle it is **OPEN** (U5) | med | `PRESET_COUNT = 80` | `protocol-spec` §4.2: CONFIRMED (code) — `bbedit` builds 80 slots. `official-docs` §2: CONFIRMED from three official sources, with a "40+40" spec line | `STATUS.md` and `protocol.py`: **HYPOTHESIS** — "evidence is a vendor PDF and `bbedit`, not this pedal; the highest flash index ever read here is 40" | A: vendor manual, TikTok copy, Korean manual, `app.js:227`. B: absence of a device read above index 40 | No — index 79/80 was never read | Both labels are right about different questions, and both documents now say so: 80 is CONFIRMED as a **product specification**, HYPOTHESIS as a **flash bound on this unit**. The distinction matters only because `check_preset_index` is the sole bound on the flash-write target address. Settling read is cheap and safe: read flash index 79, then 80 |
| C18 | **APPLIED as a recorded dispute** — `protocol-spec` §3.3, §10 row 18. The question itself is **OPEN** (U3) | med | ACK payload-byte semantics | `protocol-spec` §3.3: "Success ACK", trailing `FF` verifies, emitted after a successful write | `protocol-algorithms` §5 and §8 item 11: `cuvave` reads the payload as `ACK(val[0] > 0)`, i.e. `0x00` means **failure**, while `bbedit` treats the identical packet as success. "One of the two is wrong" | A: upstream prose + `bbedit`. B: two prior-art implementations disagreeing | No — no ACK was ever received | **Unresolved.** Settling test requires a write: compare the payload byte after a valid command against one with a deliberately bad checksum. Out of scope while writes are disabled. `protocol-spec` §3.3 and §10 row 18 now carry the dispute rather than asserting "Success ACK" flatly. The question itself stays open |
| C19 | **APPLIED** — precedence banners in `protocol-spec` §0 and `protocol-algorithms` front matter; this directory's `README.md` | med | Both protocol documents disclaim hardware validation | `protocol-spec` front matter: "**Nothing in this document has been validated against the physical pedal.**" `protocol-algorithms` front matter: "Nothing in this document was verified against the physical pedal" | `device-validation` exists in the same directory and validates much of both | — | — | Navigation defect, not a factual one, but the most likely to mislead: a reader opening `protocol-spec` first meets the wrong frame model under a banner saying nothing has been checked, with no pointer onward. A precedence line was added to the top of both, and this directory's `README.md` is the index |
| C20 | **APPLIED** — `protocol-algorithms` §6 | med | AMP / CAB factory name tables | `protocol-algorithms` §6: "AMP and CAB factory names — **HYPOTHESIS (medium-high)**", ordering inferred from `descriptions.js` insertion order | `device-validation` STEP 4–5: all 40 names read from flash. `official-docs` §2.1–2.2: both lists CONFIRMED from `ANNBLACKBOX_en.pdf` | A: insertion order of a name→description dictionary. B: flash bytes; vendor PDF | **Yes** | The inferred ordering was exactly right — checked here, all 20 AMP names and 19 of 20 CAB names match position for position (CAB slot 1 differs only because the user overwrote it with `1ML_BEST_IR`). Promoted to CONFIRMED in `protocol-algorithms` §6, citing both `device-validation` and `official-docs` |
| C21 | **APPLIED in part** — `capture-format-spec` §2.2 withdraws the prose figures and keeps the offset table; the corpus re-derivation is **OPEN** | med | `capture-format-spec` internal: header byte ranges | §2.2 table: `level` 50–255, `gain_max` 40–100, `gain_min` 0–60 | §2.2 prose, two paragraphs later: "`0x12`–`0x15` are single bytes whose values top out at **100/200/90/53**" | Same corpus, same document | n/a — internal | Self-contradiction. 255 vs 200, 100 vs 90, 60 vs 53. One of the two passes was over a different subset. `capture-format-spec` §2.2 now **withdraws** the prose figures and keeps the offset table as the one to trust; re-deriving from the corpus is still outstanding, and the document says so |
| C22 | **APPLIED** — `device-validation` STEP 2 and STEP 3 verdicts | med | `device-validation` internal: reply opcodes | STEP 2 verdict: "command type `0x64` **in the reply** … the device also uses it as the reply opcode for 92-byte-payload reads". STEP 3: "Reply command type is `0x0C`" | STEP 7 and correction 5: "There is no `0x64` 'write' opcode being echoed back at us" — offsets 3–4 are the length | Same document | n/a — internal | STEP 7 supersedes STEPs 2–3, and the earlier text had never been corrected. The STEP 2 and STEP 3 verdicts were rewritten in terms of the length field |
| C23 | **REPORTED-ONLY** — `captures.py`'s `IR_TAPS` is code; workspace rule 4 forbids the change. The documentation side is C06 | med | IR warning threshold in code | `capture-format-spec` §8.2 rule 1: warn above **30.8 ms** (1358 taps), "the device stores 1358 taps" | `tools/blackboxctl/blackboxctl/captures.py`: `IR_TAPS = 1024`, "(23.2 ms) … DOCUMENTED FIGURES, not validation requirements" | A: factory blob layout. B: vendor spec line | No | Downstream of C06. Whichever figure C06 settles on, the code comment and the spec should quote the same one and name the other. Reported only — no code change made |
| C24 | **APPLIED** — suite re-run 2026-08-28 (`221 passed`); `tools/blackboxctl/README.md`, `tools/blackboxctl/STATUS.md` and root `README.md` agree on 221 | low | Test count | `README`: "`python -m pytest` — **212 tests**" | `STATUS.md`: "**221 tests** pass" | Both undated relative to each other | n/a | **Settled by running the suite.** `pytest` is not installed on this machine's `PATH`, so it was installed into a throwaway virtualenv: `python -m pytest` under Python 3.14.3 / pytest 9.1.1 reports **`221 passed`**. 221 is correct and 212 was stale (114 test functions plus 16 `parametrize` sites). `tools/blackboxctl/README.md`, `tools/blackboxctl/STATUS.md` and the root `README.md` now all say 221, and `README.md` records how the figure was obtained |
| C25 | **APPLIED** — `presets/library.md` IR slot map; `AGENTS.md` §4 | low | Device slot-name capacity | `library.md`: "Device slot names are limited to **roughly 12** characters". `AGENTS.md` / `library.md` GUI notes: "about 12 characters fit" | `device-validation` STEP 5: "the usable field is **13 characters including the numeric prefix** (12 for slots 10–20)" | A: the M-EFCS dialog's pre-fill behaviour. B: the 14-byte record with `6WANGS212_ECM` at 13 characters | **Yes** | 13 for slots 1–9, 12 for slots 10–20, both including the prefix. `library.md` and `AGENTS.md` §4 now cite the exact figure |
| C26 | **APPLIED** — `official-docs` §6 | low | FX model count | `official-docs` §6, Korean manual: "FX types: Noise Gate, Boost, Compressor (**3**)" | `protocol-spec` §4.2 / `protocol-algorithms` §6: **4** — `00` Noise Gate++, `01` Boost, `02` Compress, `03` AI Gate MS | A: manual spec table. B: `bbedit.BLOCKS` | No, but reconcilable | `official-docs` §7.3 already records that V17 (2025-06-06) added "AI Ms Gate". The manual predates it, and `official-docs` §6 now says so where the 3 appears |
| C27 | **APPLIED** — `capture-format-spec` §9 | low | `capture-format-spec` internal: corrupt-magic counts | §1 and §6.1: **322** corrupt-magic files (318 + 2 + 1 + 1) | §9 warning table: "magic looks like `am2manager` `InitData` damage — **321**" | Same corpus | n/a — internal | The warning fires only on the `00 00 xx 00` family (321) while the error count includes `2f 0b 32 00` (322). True but confusing; the split is now stated in `capture-format-spec` §9 |
| C28 | **APPLIED** — `capture-format-spec` §1 naming note; `presets/library.md` sources | low | Capture pack name | `capture-format-spec` §1: corpus source `Black_Box_Captures_V16.8` | `library.md` sources: `ANN_Captures_IRs_V16.8.zip`, 44.3 MB | Same pack, different label | n/a | `capture-format-spec` §1 now states that the archive expands to that directory, and `library.md`'s sources section names both |
| C29 | **APPLIED** — all seven logs committed to `docs/reverse-engineering/logs/` | low | Raw device logs live outside the repository | `device-validation` artifacts table points at `scratchpad/proto/log_all.txt` and six siblings | The scratchpad is a session-local temp directory under `/private/tmp/claude-501/…` | Verified present today (374 lines total across 7 logs) | n/a | These were the irreplaceable byte logs the workspace rules forbid deleting, in a directory that would not survive. **All seven have been copied into `docs/reverse-engineering/logs/`.** Note two corrections to this row as first written: `log_all.txt` records **six** unsolicited `20 04` frames, not five (one during the CAB-name read, five during the flash-index-2 read), and they are **not** unique to it — `log_flash.txt` holds five and `log_generic.txt` two, thirteen in all |
| C30 | **APPLIED (documentation)** — `tools/blackboxctl/STATUS.md` safety model. **REPORTED-ONLY (code)** — the gate was not widened | low | The safest first-contact command is unreachable | `protocol-algorithms` §8 item 8: command `0x11` "should be the first thing our CLI sends" — zero-length payload, read-only | `protocol.py` `assert_read_only`: accepts only the `00 59 23` read header, so `00 59 11 00 00 00 FF` is refused | A: `cuvave` `test_encode_2`, cbix discovery pair. B: the safety gate | No — never sent | Gap, not a contradiction, but it is also the cheapest way to settle C10 (firmware version). `STATUS.md` now records the exclusion as deliberate and says why. Widening the gate is a code change and was not made — reported only |
| C31 | **APPLIED** — `protocol-spec` §6.4 | low | `protocol-spec`'s name-decoding worked example | §6.4: `1AC-SeVin` is CAB slot 1 | `library.md` device write log and `device-validation` STEP 4: slot 1 is now `1ML_BEST_IR`; `1AC-SeVin` was overwritten on 2026-08-28 | A: upstream example. B: flash read plus the write log | **Yes** | Harmless as an upstream illustration; `protocol-spec` §6.4 now labels it as such so nobody treats it as this device's current state |
| C32 | **APPLIED** — `presets/library.md` full 20-row table | low | "The pedal's own factory IRs measure 2048 frames" | `library.md`: 2048, from two files | Re-measured here across all 20: **15 of 20** are 2048 frames; `1AC-SeVin` is 10000, `5HIFI_OK` is 22026, `15JC120_BOX` is 13230, `10SoldSC412` is 1020 | Direct measurement, read-only | n/a | Softened, and then some: `library.md` now carries the full 20-row measured table. The generalisation is load-bearing for the "spec is intent, not contract" argument, and the argument gets *stronger* from the full data, not weaker |
| C33 | **APPLIED** — `presets/library.md` | low | Factory IRs and the 44.1 kHz spec | `library.md` implies the vendor's own factory IRs conform and only user IRs deviate ("5 are 48 kHz" is said of the installed user IRs) | Re-measured here: `3V30_MD421`, `4G12-EVH_CT`, `11FD_TW1980` are **48 kHz**; `8FRMAN112` and `14Recto_112` are **96 kHz** | Direct measurement | n/a | Added to `library.md`. The vendor's own factory IR set violates the vendor's own spec line in 5 of 20 cases, which is the single strongest piece of evidence for `library.md`'s "intent, not contract" position and for C06 |
| C34 | **APPLIED** — `presets/library.md` | low | Two library filenames carry a trailing space | — | `17AgSVT410 .wav` and `20Tace412 .wav` in `cabFile` | Directory listing | n/a | Not a documentation contradiction, but it will break any exact-name lookup written from `library.md`'s slot table. A line was added to `library.md` |

---

## Part 3 — unresolved, with the test that would settle each

All eight below are **OPEN**. Nothing in the consolidation closed any of them; where a
document now mentions one, it mentions it as unresolved.

| # | Question | Why the evidence does not settle it | Settling test |
| :-- | :--- | :--- | :--- |
| U1 | Does byte 5 belong to the length or to the space selector? | It is `0x00` in all 14 observed packets and in every frame the code can build | A transfer of ≥256 payload bytes. The known address map contains none, so this may be permanently undecidable — and harmless |
| U2 | Is the RAM write address `0x10000000 + dump_index` or `+ 2`? | Read-direction decoding proves identity for *reading*; no write was ever sent | `STATUS.md`'s procedure: one Change Knob to `0x10000000 + 0x20`, re-dump, compare byte `0x20`. Requires explicit user consent |
| U3 | Does the ACK payload byte `0x00` mean success or failure? | `cuvave` and `bbedit` read the same byte oppositely; no ACK has ever been received here | Compare the ACK payload after a valid write against one with a deliberate bad checksum. Requires a write |
| U4 | Is the pedal running V19 or V20 firmware? | `official-docs` infers V19 from a filename; four preset documents record the label `BLACKBOX v20`; the two may not be the same kind of identifier | Send the read-only `0x11` query, or read the device settings screen. Decides whether AM4 records are loadable (C09, C10) |
| U5 | How many preset slots does this unit actually have? | Never read above flash index 40 | Read flash index 79 and index 80; see which answers. Read-only and safe |
| U6 | What does the pedal do with a 48 kHz or stereo IR on upload? | `library.md` shows one demonstrated case — a 48 kHz 65536-frame mono source accepted into slot 1 — and nothing at all about stereo or about bit depths other than 24. Note that the factory IR set failing the vendor spec line is evidence about the *vendor's source files*, not about the import path | Upload one known stereo IR through M-EFCS and read the resulting `CAB` record back; or diff the bytes M-EFCS uploads for a 44.1 mono file against a 48 kHz stereo one |
| U7 | Does patching a corrupt `00 00 32 00` magic fix the audition problem? | 322 corpus files carry it; the mechanism is a plausible but untested hypothesis | `capture-format-spec` §6.3's copy-and-patch experiment. No device write needed |
| U8 | Does the `.am4` file extension exist in the wild? | The `AM4\0` record magic is confirmed in factory blobs; no `.am4` file has been seen on this machine | Look for one in the vendor community library or the SINCO trainer's output |

---

## Part 4 — corroborations found during this audit that no document records

1. **`device-validation`'s P01 and P03 flash decodes match `hana.md`, field for field with
   one caveat.** STEP 6a (flash index 0) reproduces `hana.md`'s built-in-amp-model P01
   record: AMP model `0x01` → `2FD_CL`, CAB `0x0A` → `11FD_TW1980`, gain 25, level 70,
   bass 45, mid 55, treble 47, chorus 20/20/10, room 28/20/60/45/45, dual delay 18/6/6,
   CAB level 70, High Cut raw 100 → 18.0 kHz. STEP 2 and STEP 6b (P03) likewise reproduce
   the P03 record, including FX Compress 21/53/58/50.

   **The caveat, corrected after this row was first written:** the two CAB Low Cut fields
   are not exact matches. `protocol-spec` §4.3's mapping `Hz = 20 + (raw/100) * 280` gives
   raw 24 = **87.2 Hz** and raw 22 = **81.6 Hz**, against GUI records of 87 and 81. Both
   reproduce under truncation toward zero; under round-half-up P03 would read 82 and
   disagree by one step. Truncation is what the two records are consistent with, but the
   convention is inferred from these two samples and is documented nowhere upstream. So
   those two fields agree **to within one display step**; every other field is an exact
   integer match.

   `device-validation` originally cross-checked only P41 and claimed "seven independent
   fields agreeing is decisive"; in fact **three presets and roughly forty fields agree**,
   all exactly except the two Low Cut fields. This is still the strongest single validation
   in the repository. It has since been recorded in `device-validation` STEP 6a and
   `presets/hana.md`.
2. **All seven transmitted commands re-encode bit-exactly** to the SysEx strings logged
   beside them, checked independently here against a fresh implementation of the codec.
3. **The `0x11` frames from third-party dumps validate under the M2 grammar** — the
   7-byte query, the 8-byte ACK and the 34-byte `FootCtrl_031` discovery reply all satisfy
   `length == 7 + payload` with a correct payload-sum checksum. This is the decisive
   argument for C01/C05 and appears in no document.

---

## Part 5 — consolidation guidance

* Nothing in this register calls for deleting technical substance. Every disputed claim
  has a correct home; the fix is almost always to relabel, cross-link, or narrow the scope
  of a statement.
* `protocol-spec`'s §2.1, §2.2, §3.1 (string reads), §9.2 and §10 are the highest
  concentration of stale material. They should be rewritten against `device-validation`,
  with the upstream reading preserved in a clearly marked "what the published doc says,
  and why it is a misparse" subsection — that history is useful to anyone who reads the
  upstream repository next.
* `device-validation` is the tiebreaker but is not internally consistent (C22): its early
  step verdicts predate its own STEP 7. Fix those before quoting it as authority.
* The raw byte logs (C29) must be moved into the repository before anything else is
  reorganised.
