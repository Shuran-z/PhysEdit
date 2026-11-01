"""Recover a missing JSON envelope without inventing or renaming event observations."""


def normalize_registered_event_payload(payload, event_names):
    expected = set(event_names)
    if not expected or any(not isinstance(name, str) or not name for name in expected) or 'events' in expected:
        raise ValueError('invalid_registered_event_names')
    if not isinstance(payload, dict):
        raise ValueError('event_output_not_object')
    repair = None
    if set(payload) == {'events'}:
        events = payload['events']
    elif set(payload) == expected:
        events = payload
        repair = 'wrapped_exact_registered_event_map'
    else:
        raise ValueError('event_output_keys_do_not_match_registration')
    if not isinstance(events, dict) or set(events) != expected:
        raise ValueError('event_output_keys_do_not_match_registration')
    for record in events.values():
        if not isinstance(record, dict) or record.get('label') not in ('yes', 'no', 'not_observed', 'uncertain'):
            raise ValueError('invalid_registered_event_observation')
    # Values, timestamps, reasons and confidence are retained verbatim. The
    # caller must still validate evidence against actually supplied frames.
    return {'events': events}, repair
