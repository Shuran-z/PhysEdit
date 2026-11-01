"""Add read-only contact telemetry to the exact recovered T12 renderer source.

The original file is never modified. Physics calls and their order are retained.
The generated copy must be admitted only after comparing source trajectories.
"""
import hashlib

ORIGINAL_SHA256 = '35b487c58fd2c6a4490d074fbb150640fa9496fb00c61ad3750bdaa7321b49c5'

HELPER = '''
def _contact_protocol_readback(entries, step_index):
    actors = {e['name']: e['entity'] for e in entries}
    a, b = actors['t12_stapler'], actors['t12_tissue_box']
    data = a.get_contacts(with_entity=b)
    if 'valid_mask' in data:
        raise ValueError('contact amendment expects one non-parallel scene')
    geoms_a = data['geom_a'].detach().cpu().tolist()
    geoms_b = data['geom_b'].detach().cpu().tolist()
    positions = data['position'].detach().cpu().tolist()
    if not (len(geoms_a) == len(geoms_b) == len(positions)):
        raise ValueError('native contact arrays disagree')
    return [dict(entity_a='t12_stapler', entity_b='t12_tissue_box',
                 geom_a=ga, geom_b=gb, position=pos,
                 physics_step_index=step_index,
                 telemetry='RigidEntity.get_contacts(with_entity=other)')
            for ga, gb, pos in zip(geoms_a, geoms_b, positions)]

'''


def instrument(raw):
    if hashlib.sha256(raw).hexdigest() != ORIGINAL_SHA256:
        raise ValueError('T12 original renderer identity changed')
    text = raw.decode('utf-8')
    changes = [
        ('from PIL import Image\n', 'from PIL import Image\n' + HELPER),
        ('    for i in range(frames):\n',
         "    for i in range(frames):\n        contact_protocol_rows = []\n"),
        ('                scene.step()\n',
         '                scene.step()\n                contact_protocol_rows.extend(_contact_protocol_readback(dynamic_entries, _physics_step_idx))\n'),
        ("            annotations['frames'].append(frame_ann)",
         "            if static_phase:\n                contact_protocol_rows = _contact_protocol_readback(dynamic_entries, -1)\n            frame_ann['contacts'] = contact_protocol_rows\n            frame_ann['contact_telemetry_complete'] = True\n            annotations['frames'].append(frame_ann)"),
    ]
    for old, new in changes:
        if text.count(old) != 1:
            raise ValueError('unrecognized original telemetry insertion point')
        text = text.replace(old, new, 1)
    return text.encode('utf-8')
