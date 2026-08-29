"""Real bytes captured from the owner's M-Vave BlackBox over USB MIDI SysEx.

Transcribed from docs/reverse-engineering/device-validation.md, which is the
transcript of the one hardware validation session (2026-08-28, serial
whose serial is intentionally omitted). Every command in that session was read-only.

These are the regression fixtures. The worked example in the upstream
usb_sysex_protocol.md is NOT usable as one: its raw and encoded lines do not
correspond to each other. Use the SysEx/frame pairs below instead - they are
real, they round trip, and their checksums validate.

GPL-3.0. See ../../LICENSE and ../../NOTICE.
"""

from __future__ import annotations


def h(text: str) -> bytes:
    """Parse the space-separated hex the RE documentation uses."""
    return bytes.fromhex("".join(text.split()))


# --- The seven read commands transmitted, byte for byte -------------------

READ_COMMANDS: dict[str, bytes] = {
    "ram_dump": h("00 59 23 08 00 00 04 00 00 00 10 5C 00 00 8F"),
    "preset_sync": h("00 59 23 08 00 00 04 00 00 00 20 04 00 00 D7"),
    "cab_names": h("00 59 23 08 00 00 05 00 00 00 80 18 01 00 61"),
    "amp_names": h("00 59 23 08 00 00 05 00 00 00 90 18 01 00 51"),
    "flash_00": h("00 59 23 08 00 00 04 00 00 00 00 5C 00 00 9F"),
    "flash_02": h("00 59 23 08 00 00 04 B8 00 00 00 5C 00 00 E7"),
    "flash_40": h("00 59 23 08 00 00 04 60 0E 00 00 5C 00 00 31"),
}

# --- Outbound SysEx as it went on the wire --------------------------------

TX_SYSEX: dict[str, bytes] = {
    "ram_dump": h("F0 00 32 0D 41 00 00 00 02 00 00 00 00 41 0B 00 00 0F 01 F7"),
    "preset_sync": h("F0 00 32 0D 41 00 00 00 02 00 00 00 00 42 00 00 00 57 01 F7"),
    "cab_names": h("F0 00 32 0D 41 00 00 40 02 00 00 00 00 08 23 00 00 61 00 F7"),
    "amp_names": h("F0 00 32 0D 41 00 00 40 02 00 00 00 00 09 23 00 00 51 00 F7"),
    "flash_00": h("F0 00 32 0D 41 00 00 00 02 00 00 00 00 40 0B 00 00 1F 01 F7"),
    "flash_02": h("F0 00 32 0D 41 00 00 00 02 38 01 00 00 40 0B 00 00 67 01 F7"),
    "flash_40": h("F0 00 32 0D 41 00 00 00 02 60 1C 00 00 40 0B 00 00 31 00 F7"),
}

# --- The seven unique reply frames ----------------------------------------
#
# 29 inbound SysEx messages across the logs collapse to these 7 unique frames.
# checksum_rx (sum from offset 5) validates 7/7. checksum_tx (offset 4)
# validates 5/7, failing on exactly the two 295-byte name blocks, which are the
# only replies with byte[4] == 0x01.

REPLY_RAM_DUMP = h("""
00 59 23 64 00 00 04 00 00 00 10 5C 00 00 55 00 00 01 05 02 04 03 01 01 00 00 01
01 02 02 00 03 01 04 15 00 35 00 3A 00 32 00 00 00 00 00 17 00 43 00 2B 00 2E 00
3E 00 00 00 3C 00 32 00 48 00 00 00 00 00 00 00 54 00 2F 00 0F 00 00 00 00 00 00
00 0A 00 0F 00 30 00 31 00 1E 00 00 00 44 00 16 00 64 00 00 00 00 00 00 00 D6
""")

REPLY_PRESET_SYNC = h("00 59 23 0C 00 00 04 00 00 00 20 04 00 00 02 02 00 00 D3")

REPLY_FLASH_00 = h("""
00 59 23 64 00 00 04 00 00 00 00 5C 00 00 55 00 01 05 02 04 00 03 01 01 01 01 01
01 02 01 00 03 00 0A 05 00 23 00 37 00 32 00 00 00 00 00 19 00 46 00 2D 00 37 00
2F 00 00 00 14 00 14 00 0A 00 00 00 00 00 00 00 12 00 06 00 06 00 00 00 00 00 00
00 1C 00 14 00 3C 00 2D 00 2D 00 00 00 46 00 18 00 64 00 00 00 00 00 00 00 CA
""")

REPLY_FLASH_02 = h("""
00 59 23 64 00 00 04 B8 00 00 00 5C 00 00 55 00 00 01 05 02 04 03 01 01 00 00 01
01 02 02 00 03 01 04 15 00 35 00 3A 00 32 00 00 00 00 00 17 00 43 00 2B 00 2E 00
3E 00 00 00 3C 00 32 00 48 00 00 00 00 00 00 00 54 00 2F 00 0F 00 00 00 00 00 00
00 0A 00 0F 00 30 00 31 00 1E 00 00 00 44 00 16 00 64 00 00 00 00 00 00 00 2E
""")

REPLY_FLASH_40 = h("""
00 59 23 64 00 00 04 60 0E 00 00 5C 00 00 55 00 01 05 02 04 00 03 01 01 01 00 01
01 02 00 00 03 00 06 0F 00 23 00 37 00 37 00 00 00 00 00 2D 00 46 00 28 00 3E 00
3C 00 00 00 14 00 16 00 0C 00 00 00 00 00 00 00 29 00 1E 00 1D 00 07 00 32 00 32
00 19 00 0C 00 3C 00 37 00 0F 00 00 00 4B 00 1A 00 64 00 00 00 00 00 00 00 93
""")

REPLY_CAB_NAMES = h("""
00 59 23 20 01 00 05 00 00 00 80 18 01 00 31 4D 4C 5F 42 45 53 54 5F 49 52 00 00
00 32 4A 56 4D 5F 31 39 36 30 5F 35 37 00 00 33 56 33 30 5F 4D 44 34 32 31 00 00
00 00 34 47 31 32 2D 45 56 48 5F 43 54 00 00 00 35 48 49 46 49 5F 4F 4B 00 00 00
00 00 00 36 57 41 4E 47 53 32 31 32 5F 45 43 4D 00 37 56 4F 58 5F 41 43 33 30 00
00 00 00 00 38 46 52 4D 41 4E 31 31 32 00 00 00 00 00 39 4D 65 4F 53 69 63 6B 2D
49 49 49 00 00 31 30 53 6F 6C 64 53 43 34 31 32 00 00 00 31 31 46 44 5F 54 57 31
39 38 30 00 00 00 31 32 4D 45 53 41 5F 34 31 32 00 00 00 00 31 33 48 49 57 34 31
32 53 57 46 00 00 00 31 34 52 65 63 74 6F 5F 31 31 32 00 00 00 31 35 4A 43 31 32
30 5F 42 4F 58 00 00 00 31 36 41 67 75 6C 61 34 31 30 00 00 00 00 31 37 41 67 53
56 54 34 31 30 00 00 00 00 31 38 44 67 44 47 32 31 32 4E 00 00 00 00 31 39 4D 62
53 77 61 79 32 31 30 00 00 00 32 30 54 61 63 65 34 31 32 00 00 00 00 00 20
""")

REPLY_AMP_NAMES = h("""
00 59 23 20 01 00 05 00 00 00 90 18 01 00 31 4A 39 30 30 5F 43 4C 00 00 00 00 00
00 32 46 44 5F 43 4C 00 00 00 00 00 00 00 00 33 4A 43 31 32 30 5F 43 4C 00 00 00
00 00 34 42 4C 55 45 5F 4F 44 00 00 00 00 00 00 35 52 41 54 5F 4F 44 00 00 00 00
00 00 00 36 4D 2D 56 41 56 45 5F 4F 44 00 00 00 00 37 53 55 50 41 5F 4F 44 00 00
00 00 00 00 38 44 41 52 4B 53 5F 44 53 00 00 00 00 00 39 4A 39 30 30 5F 44 53 00
00 00 00 00 00 31 30 4A 48 53 5F 44 53 00 00 00 00 00 00 31 31 45 56 48 5F 35 31
35 30 00 00 00 00 31 32 46 52 49 4D 41 4E 00 00 00 00 00 00 31 33 58 43 5F 44 53
00 00 00 00 00 00 00 31 34 52 4F 4F 4D 34 30 00 00 00 00 00 00 31 35 4A 56 4D 00
00 00 00 00 00 00 00 00 31 36 41 67 44 62 37 35 30 5F 42 53 00 00 31 37 41 70 53
56 54 5F 42 53 00 00 00 00 31 38 50 6A 42 75 64 64 79 5F 42 53 00 00 31 39 44 67
58 75 5F 42 53 00 00 00 00 00 32 30 4D 61 72 6B 4C 6D 5F 42 53 00 00 00 36
""")

UNIQUE_REPLIES: dict[str, bytes] = {
    "ram_dump": REPLY_RAM_DUMP,
    "preset_sync": REPLY_PRESET_SYNC,
    "flash_00": REPLY_FLASH_00,
    "flash_02": REPLY_FLASH_02,
    "flash_40": REPLY_FLASH_40,
    "cab_names": REPLY_CAB_NAMES,
    "amp_names": REPLY_AMP_NAMES,
}

BYTE4_NONZERO = ("cab_names", "amp_names")
"""The two replies where checksum offset 4 and offset 5 disagree."""

# --- The 340-byte inbound SysEx for the CAB name block ---------------------
#
# This is the pair to use as the codec regression fixture:
#     base128_decode(RX_SYSEX_CAB_NAMES[1:-1]) == REPLY_CAB_NAMES

RX_SYSEX_CAB_NAMES = h("""
F0 00 32 0D 01 12 00 40 02 00 00 00 00 08 23 00 00 31 1A 31 7A 25 28 51 29 54 3E
25 12 05 00 00 00 32 14 59 6A 74 2B 4C 1C 36 60 7C 2A 73 06 00 00 33 2C 4D 01 73
2B 13 22 34 64 44 01 00 00 00 00 34 0E 45 11 53 25 11 2B 48 3E 0D 22 05 00 00 00
35 10 25 32 14 69 57 27 4B 00 00 00 00 00 00 00 36 2E 05 72 74 68 14 19 31 64 7C
2A 34 28 13 00 37 2C 3D 42 75 2B 50 21 33 60 00 00 00 00 00 00 38 0C 49 6A 14 48
53 18 31 64 00 00 00 00 00 00 39 1A 15 7B 34 2A 5A 31 6B 5A 24 4A 14 09 00 00 31
60 4C 7A 46 0D 59 29 43 68 44 11 03 00 00 00 31 62 18 22 74 0B 55 2B 31 72 60 01
03 00 00 00 31 64 34 2A 34 2A 50 2F 34 62 48 01 00 00 00 00 31 66 20 4A 74 0A 4D
18 32 26 5D 32 04 00 00 00 31 68 48 2A 36 0C 5D 37 5F 62 44 11 03 00 00 00 31 6A
28 1A 14 46 0C 18 5F 04 3D 42 05 00 00 00 31 6C 04 3A 56 0E 5B 30 34 62 40 01 00
00 00 00 31 6E 04 3A 36 4A 15 2A 34 62 40 01 00 00 00 00 31 70 10 3A 46 68 11 19
31 64 38 02 00 00 00 00 31 72 34 12 36 6A 5D 30 79 64 44 01 03 00 00 00 32 60 50
0A 36 2C 19 1A 31 64 00 00 00 00 00 00 20 00 F7
""")

# --- Expected decodes -----------------------------------------------------

CAB_NAMES = [
    "1ML_BEST_IR",
    "2JVM_1960_57",
    "3V30_MD421",
    "4G12-EVH_CT",
    "5HIFI_OK",
    "6WANGS212_ECM",
    "7VOX_AC30",
    "8FRMAN112",
    "9MeOSick-III",
    "10SoldSC412",
    "11FD_TW1980",
    "12MESA_412",
    "13HIW412SWF",
    "14Recto_112",
    "15JC120_BOX",
    "16Agula410",
    "17AgSVT410",
    "18DgDG212N",
    "19MbSway210",
    "20Tace412",
]

AMP_NAMES = [
    "1J900_CL",
    "2FD_CL",
    "3JC120_CL",
    "4BLUE_OD",
    "5RAT_OD",
    "6M-VAVE_OD",
    "7SUPA_OD",
    "8DARKS_DS",
    "9J900_DS",
    "10JHS_DS",
    "11EVH_5150",
    "12FRIMAN",
    "13XC_DS",
    "14ROOM40",
    "15JVM",
    "16AgDb750_BS",
    "17ApSVT_BS",
    "18PjBuddy_BS",
    "19DgXu_BS",
    "20MarkLm_BS",
]

# The exact decode tables recorded in device-validation.md STEP 2 / 6a / 6c.
# Knob values as (name, value) pairs in slot order.

EXPECTED_P41 = {
    "volume": 85,
    "routing_names": ["AMP", "CAB", "MOD", "REV", "FX", "DLY"],
    "enabled": {
        "fx": True,
        "amp": True,
        "mod": True,
        "dly": False,
        "rev": True,
        "cab": True,
    },
    "models": {"fx": 2, "amp": 0, "mod": 0, "dly": 3, "rev": 0, "cab": 6},
    "model_names": {"amp": "1J900_CL", "cab": "7VOX_AC30"},
    "amp_knobs": [
        ("Gain", 45),
        ("Level", 70),
        ("Bass", 40),
        ("Mid", 62),
        ("Treble", 60),
    ],
    "cab_knobs": [("Level", 75), ("Low Cut", 26), ("High Cut", 100)],
    "mod_knobs": [("Speed", 20), ("Depth", 22), ("Mix", 12)],
    "rev_knobs": [
        ("Decay", 25),
        ("Mix", 12),
        ("High Pass", 60),
        ("Low Pass", 55),
        ("Depth", 15),
    ],
}

EXPECTED_P01 = {
    "volume": 85,
    "routing_names": ["AMP", "CAB", "MOD", "REV", "FX", "DLY"],
    "models": {"fx": 2, "amp": 1, "mod": 0, "dly": 3, "rev": 0, "cab": 10},
    "model_names": {"amp": "2FD_CL", "cab": "11FD_TW1980"},
    "amp_knobs": [
        ("Gain", 25),
        ("Level", 70),
        ("Bass", 45),
        ("Mid", 55),
        ("Treble", 47),
    ],
    "cab_knobs": [("Level", 70), ("Low Cut", 24), ("High Cut", 100)],
}

EXPECTED_RAM = {
    "volume": 85,
    "routing_names": ["FX", "AMP", "CAB", "MOD", "REV", "DLY"],
    "models": {"fx": 2, "amp": 2, "mod": 0, "dly": 3, "rev": 1, "cab": 4},
    "model_names": {"amp": "3JC120_CL", "cab": "5HIFI_OK"},
    "amp_knobs": [
        ("Gain", 23),
        ("Level", 67),
        ("Bass", 43),
        ("Mid", 46),
        ("Treble", 62),
    ],
    "cab_knobs": [("Level", 68), ("Low Cut", 22), ("High Cut", 100)],
}

# --- Documented write literals (NEVER transmitted) ------------------------
#
# From the upstream documentation, reproduced here only so that tests can assert
# the builders match the doc AND that every safety gate refuses them.

DOC_WRITE_LITERALS = {
    "toggle_fx_on": h("00 59 22 09 00 00 04 08 00 00 10 01 00 00 01 E1"),
    "commit": h("00 59 22 08 00 00 04 00 00 00 F0 00 00 00 0B"),
}
