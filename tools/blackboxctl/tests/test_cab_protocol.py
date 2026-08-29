"""Captured M-EFCS CAB staging and save protocol. GPL-3.0."""

from blackboxctl import protocol


def test_cab_stage_sequence_matches_observed_addresses_and_sizes():
    record = bytes(protocol.CAB_RECORD_SIZE)
    consent = protocol.WriteConsent(
        path_key="stage-cab", confirmed_by_user=True, accept_unverified=True
    )
    frames = [
        protocol.parse_frame(raw)
        for raw in protocol.cmd_stage_cab(record, consent=consent)
    ]
    assert [frame.address for frame in frames[:-1]] == [
        0x0000,
        0x03F7,
        0x07EE,
        0x0BE5,
        0x0FDC,
        0x13D3,
        0x17CA,
    ]
    assert [len(frame.payload) for frame in frames[:-1]] == [
        1015,
        1015,
        1015,
        1015,
        1015,
        1015,
        74,
    ]
    assert all(frame.well_formed for frame in frames)
    assert frames[-1].address == protocol.ADDR_LIBRARY_ACTIVATE
    assert frames[-1].payload == b"\x02"


def test_cab_slot_20_save_trigger_matches_capture():
    header = b"CAB\x00" + b"20AC_TAYLOR".ljust(14, b"\x00") + b"\x01\x32"
    consent = protocol.WriteConsent(
        path_key="save-cab",
        confirmed_by_user=True,
        accept_unverified=True,
        allow_flash=True,
    )
    frames = [
        protocol.parse_frame(raw)
        for raw in protocol.cmd_save_cab_header(19, header, consent=consent)
    ]
    assert frames[0].address == 0 and frames[0].payload == header
    assert frames[1].address == 0xF0000113
    assert frames[1].payload == b"\x00"
    assert all(frame.well_formed for frame in frames)


def test_amp_stage_and_slot_20_save_match_capture():
    record = bytes(protocol.AMP_RECORD_SIZE)
    stage_consent = protocol.WriteConsent(
        path_key="stage-amp", confirmed_by_user=True, accept_unverified=True
    )
    stage = [
        protocol.parse_frame(raw)
        for raw in protocol.cmd_stage_amp(record, consent=stage_consent)
    ]
    assert [len(frame.payload) for frame in stage[:-1]] == [
        1015,
        1015,
        1015,
        1015,
        1015,
        1015,
        182,
    ]
    assert stage[-1].address == 0xA0000000
    assert stage[-1].payload == b"\x01"

    save_consent = protocol.WriteConsent(
        path_key="save-amp",
        confirmed_by_user=True,
        accept_unverified=True,
        allow_flash=True,
    )
    save = [
        protocol.parse_frame(raw)
        for raw in protocol.cmd_save_amp(19, record, consent=save_consent)
    ]
    assert save[-1].address == 0xF0000013
    assert save[-1].payload == b"\x00"
    assert all(frame.well_formed for frame in stage + save)
