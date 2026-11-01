import copy

import pytest

from physedit.event_output import normalize_registered_event_payload


def record(label='yes'):
    return dict(label=label, confidence=.95, evidence_times_s=[.866667],
                reason='Visible original actors.', contradictions=[])


def test_missing_envelope_preserves_exact_observations_and_raw_timestamp():
    payload = {'contact': record()}
    original = copy.deepcopy(payload)
    result, repair = normalize_registered_event_payload(payload, ['contact'])
    assert result == {'events': original}
    assert repair == 'wrapped_exact_registered_event_map'
    assert payload == original
    assert result['events']['contact']['evidence_times_s'] == [.866667]


def test_canonical_envelope_is_not_marked_repaired():
    payload = {'events': {'contact': record('uncertain')}}
    result, repair = normalize_registered_event_payload(payload, ['contact'])
    assert result == payload and repair is None


@pytest.mark.parametrize('payload', [
    {'other_contact': record()},
    {'contact': record(), 'extra': record()},
    {'events': {'contact': record(), 'extra': record()}},
    {'events': {'contact': record()}, 'quality': {'status': 'pass'}},
    {'contact': {'label': 'not sure'}},
    {'contact': []},
])
def test_ambiguous_or_mismatched_outputs_are_not_silently_salvaged(payload):
    with pytest.raises(ValueError):
        normalize_registered_event_payload(payload, ['contact'])


def test_multiple_events_must_all_be_present():
    with pytest.raises(ValueError):
        normalize_registered_event_payload({'first': record()}, ['first', 'second'])
    result, repair = normalize_registered_event_payload(
        {'first': record(), 'second': record('no')}, ['first', 'second'])
    assert set(result['events']) == {'first', 'second'} and repair
