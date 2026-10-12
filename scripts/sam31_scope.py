"""Run byte-locked observation code with only dataset-size assertions rebound."""
import ast
import copy
import hashlib
import json
import sys
from pathlib import Path

STAGES = (
    'repair_sam31_integrated_full30.py', 'repair_sam31_rgb_health_full30.py',
    'certify_sam31_recovered_rgb_full30.py', 'repair_sam31_visible_projection_full30.py',
)


def bind_scope(data, scope):
    tree = ast.parse(data)
    original = copy.deepcopy(tree)
    sizes = {1038: scope['cases'], 365: scope['book_cases'],
             13918: scope['frames'], 79687: scope['prefix_frames'],
             58: scope['initial_actual_cases']}
    changes = []
    # Only assert TEST expressions are adapted. Image operations and all
    # policy constants remain exactly the original executable AST.
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        for parent in list(ast.walk(node.test)):
            for field, children in list(ast.iter_fields(parent)):
                entries = enumerate(children) if isinstance(children, list) else [(None, children)]
                for index, child in entries:
                    if not isinstance(child, ast.Constant) or type(child.value) is not int:
                        continue
                    old = child.value
                    if old == 519:
                        replacement = ast.parse('_sam31_shard_sizes[w]', mode='eval').body
                        value = 'shard_sizes[w]'
                    elif old in sizes:
                        replacement = ast.Constant(sizes[old])
                        value = sizes[old]
                    else:
                        continue
                    ast.copy_location(replacement, child)
                    changes.append((parent, field, index, child, replacement, value))
    if not changes:
        raise ValueError('No registered scope assertions found')
    def set_child(parent, field, index, child):
        if index is None:
            setattr(parent, field, child)
        else:
            getattr(parent, field)[index] = child
    for parent, field, index, child, replacement, value in changes:
        set_child(parent, field, index, replacement)
    adapted = copy.deepcopy(tree)
    for parent, field, index, child, replacement, value in changes:
        set_child(parent, field, index, child)
    if ast.dump(tree) != ast.dump(original):
        raise ValueError('Scope adapter changed executable policy')
    return ast.fix_missing_locations(adapted), [
        {'line': child.lineno, 'from': child.value, 'to': value}
        for _, _, _, child, _, value in changes]


def main(root, name):
    if not __debug__:
        raise RuntimeError('Frozen source assertions require Python without -O')
    root = Path(root)
    scope = json.loads((root/'generation_scope.json').read_text())
    if name not in STAGES:
        raise ValueError('Unregistered observation stage')
    source = root/name
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != scope['sources'][name]:
        raise ValueError('Frozen source SHA mismatch')
    tree, changes = bind_scope(data, scope)
    (root/'runs'/(name+'.scope_audit.json')).write_text(json.dumps({
        'source_sha256': scope['sources'][name], 'scope_assertion_changes': changes,
        'executable_ast_restores_exactly': True, 'image_policy_changed': False,
        'actual_scope': scope, 'legacy_printed_counters_are_not_scope_evidence': True,
    }, indent=2)+'\n')
    sys.path.insert(0, str(root))
    sys.argv = [str(source), str(root)]
    namespace = {'__name__': 'frozen_scope_module', '__file__': str(source),
                 '_sam31_shard_sizes': scope['shard_sizes']}
    exec(compile(tree, str(source), 'exec'), namespace)
    namespace['main']()


if __name__ == '__main__':
    main(*sys.argv[1:])
