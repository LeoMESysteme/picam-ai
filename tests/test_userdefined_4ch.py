"""Vierkanal-Drahtvertrag, ohne Hardware."""
import pytest


def tick(**changes):
    from dispread.live.tick import Tick

    return Tick(**{'seq': 7, 'valid': True, 'value_text': '0.63956',
                   'time_unix_ns': 1794397184232361000, 'frame_sequence': 42, **changes})


def test_exact_four_channel_bytes_and_capabilities():
    from dispread.records import InvalidValuePolicy
    from dispread.sink.protocol.userdefined_4ch import TickFormatter

    formatter = TickFormatter()
    assert formatter.format_tick(tick()) == b'%0.63956;1;7;1794397184.232361\r\n'
    assert formatter.format_tick(tick(seq=8, valid=False, value_text=None, frame_sequence=None)) == (
        b'%99999999.0;0;8;1794397184.232361\r\n')                 # nichts zu halten: Fehlwert
    assert formatter.format_tick(tick(seq=8, valid=False, value_text=None, frame_sequence=None), '0.63956') == (
        b'%0.63956;0;8;1794397184.232361\r\n')                    # Entscheidung 13.11.: Kanal 1 haelt
    caps = formatter.capabilities
    assert caps.format_id == 'gsvmulti_userdefined_4ch_v1'
    assert caps.channel_count == 4 and caps.provisional and caps.carries_capture_timestamp
    assert caps.timestamp_resolution_ns == 1000
    assert caps.supported_invalid_policies == frozenset({InvalidValuePolicy.MARK_RECORD})


@pytest.mark.parametrize('text', ['1e2', 'NaN', 'Inf', '99999999.0', '+099999999.00',
                                 '99999999', '１', '1;2', '1\r\n', '', None])
def test_reject_unsafe_valid_text(text):
    from dispread.sink.protocol.userdefined_4ch import TickFormatter

    with pytest.raises(ValueError):
        TickFormatter().format_tick(tick(value_text=text))


def test_preserve_decimal_text_and_round_time_without_float_loss():
    from dispread.sink.protocol.userdefined_4ch import TickFormatter

    assert TickFormatter().format_tick(tick(value_text='+ 000.001', time_unix_ns=1794397184999999999)) == (
        b'%+000.001;1;7;1794397185.000000\r\n')


def test_serial_sink_format_holds_last_valid_value_per_formatter():
    """UART direkt: ein Formatter je Lauf; vor dem ersten gültigen Wert der Fehlwert."""
    from dispread.sink.protocol.userdefined_4ch import TickFormatter

    formatter = TickFormatter()
    invalid = dict(valid=False, value_text=None, frame_sequence=None)
    assert formatter.format(tick(seq=1, **invalid)).startswith(b'%99999999.0;0;1;')
    assert formatter.format(tick(seq=2)).startswith(b'%0.63956;1;2;')
    assert formatter.format(tick(seq=3, **invalid)).startswith(b'%0.63956;0;3;')
    assert formatter.format(tick(seq=4, value_text='0.64001')).startswith(b'%0.64001;1;4;')
    assert formatter.format(tick(seq=5, **invalid)).startswith(b'%0.64001;0;5;')


def test_held_value_must_still_be_a_checked_decimal():
    from dispread.sink.protocol.userdefined_4ch import TickFormatter

    with pytest.raises(ValueError):
        TickFormatter().format_tick(tick(seq=8, valid=False, value_text=None, frame_sequence=None), '1e2')
