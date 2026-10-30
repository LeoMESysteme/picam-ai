from dispread.live.causes import RejectionWindow
from dispread.records import ValueStatus


def test_window_counts_processed_frames_and_primary_cause_once():
    window = RejectionWindow()
    for _ in range(3):
        window.observe(1.0, ValueStatus.VALID, ())
    window.observe(1.0, ValueStatus.UNREADABLE, ('leser:leerzelle_gestoert:14', 'no_value'))
    result = window.snapshot(1.0)
    assert result['frames'] == 4
    assert result['causes'] == [{'reason': 'leser:leerzelle_gestoert:14', 'count': 1, 'fraction': 0.25}]
    assert window.snapshot(11.0)['frames'] == 0


def test_window_expires_on_observation_and_snapshot_and_sorts_causes():
    window = RejectionWindow()
    window.observe(0.0, ValueStatus.UNREADABLE, ('no_value',))
    window.observe(9.9, ValueStatus.TRANSITION, ('awaiting_confirmation',))
    window.observe(10.1, ValueStatus.UNREADABLE, ('leser:zelle_unbekannt:5',))
    window.observe(10.2, ValueStatus.UNREADABLE, ('leser:zelle_unbekannt:5',))
    result = window.snapshot(10.2)
    assert result['frames'] == 3
    assert [c['count'] for c in result['causes']] == [2, 1]
    assert window.snapshot(20.0)['frames'] == 2


def test_window_is_bounded_even_at_unrealistic_frame_rate():
    window = RejectionWindow()
    for _ in range(50_000):
        window.observe(0.0, ValueStatus.VALID, ())
    result = window.snapshot(0.0)
    assert result['frames'] <= 4096
    assert result['limited'] is True
    assert window.snapshot(10.0)['frames'] == 0


def test_german_cause_explains_cell_and_preserves_machine_reason():
    from dispread.workbench.fields import live_cause

    cause = live_cause({'reason': 'leser:leerzelle_gestoert:14', 'count': 1, 'fraction': 0.25})
    assert cause['cell'] == 14
    assert cause['reason'] == 'leser:leerzelle_gestoert:14'
    assert 'rechts der Einheit' in cause['explanation']
    assert 'Kratzer, Staub oder Reflex' in cause['explanation']
    assert live_cause({'reason': 'anzeige_wechselt'})['explanation'] == 'Wert wechselt'
    assert live_cause({'reason': 'testlauf_keine_freigabe'})['explanation'] == 'Testlauf: keine Wertfreigabe'
    assert 'Rahmenbereiche' in live_cause({'reason': 'tracking_lost:rahmen_unstimmig'})['explanation']
