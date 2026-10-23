"""Named native-contact labels; recorded empty contact lists are negatives."""
PAIRS = {
    'T16': [('t16_folder', 't16_support_book'), ('t16_folder', 't16_downstream_box')],
    'T17': [('t17_can', 't17_tissue_box'), ('t17_can', 't17_ramp')],
    'T20': [('t20_book', 't20_can'), ('t20_can', 't20_box'), ('t20_box', 't20_cup')],
}


def vector(row):
    names = {a['name'] for a in row['actors']}
    declared = row['scene_overrides'].get('record_contacts') is True
    indexed = {frozenset(c['pair']): c for c in row['contacts']}
    result, firsts = {}, []
    for pair in PAIRS[row['scene_id']]:
        if not set(pair) <= names:
            continue
        contact = indexed.get(frozenset(pair))
        if contact is None:
            raise ValueError('requested pair was not extracted')
        prefix = 'contact_' + '__'.join(pair)
        for field in ['occurred', 'present_at_end']:
            value = contact.get(field)
            if value is None and declared and contact.get('applicable'):
                value = False
            if value is not None:
                result[prefix + '_' + field] = int(value)
        firsts.append(contact.get('first'))
    if row['scene_id'] == 'T20':
        keys = ['contact_' + '__'.join(p) + '_occurred' for p in PAIRS['T20']]
        if all(k in result for k in keys):
            result['all_three_contacts_observed'] = int(all(result[k] for k in keys))
            result['ordered_first_contacts_observed'] = int(
                all(t is not None for t in firsts) and all(a <= b for a, b in zip(firsts, firsts[1:])))
    return result
