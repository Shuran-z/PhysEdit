"""CPU regressions for PhysRVG manifest metadata compatibility."""
import argparse
import ast
import json
from pathlib import Path

import pytest


def runner_functions(**values):
    source = Path(__file__).resolve().parents[1]/'physedit/runners/physrvg.py'
    tree = ast.parse(source.read_text())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name in {'read_manifest', 'main'}]
    namespace = dict(Path=Path, json=json, **values)
    future = ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)
    module = ast.fix_missing_locations(ast.Module(body=[future, *functions], type_ignores=[]))
    exec(compile(module, str(source), 'exec'), namespace)
    return namespace


def manifest(tmp_path, rows):
    path = tmp_path/'manifest.jsonl'
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    return path


def test_new_rows_default_metadata_and_legacy_metadata_is_preserved(tmp_path):
    rows = [dict(sample_id='new', seed=19, gravity_truth=1.6),
            dict(sample_id='legacy', seed=23, prompt_granularity='fine', gravity_truth=24.)]
    path = manifest(tmp_path, rows)
    loaded = runner_functions()['read_manifest'](path, 1, 0)
    assert loaded == [{**rows[0], 'prompt_granularity':'registered_condition_continuation'}, rows[1]]
    assert [r['seed'] for r in loaded] == [19, 23]
    assert [r['gravity_truth'] for r in loaded] == [1.6, 24.]


@pytest.mark.parametrize('value', [None, '', '  ', 12])
def test_bad_metadata_is_rejected_before_model_loading(tmp_path, value):
    path = manifest(tmp_path, [dict(prompt_granularity=value)])
    ns = runner_functions(parse_args=lambda:argparse.Namespace(manifest=path, num_shards=1,
                         shard_index=0, limit=None),
                         load_pipeline=lambda _:pytest.fail('model must not load'))
    with pytest.raises(ValueError, match='invalid prompt_granularity'):
        ns['main']()


def test_row_sharding_keeps_the_original_members_and_order(tmp_path):
    path = manifest(tmp_path, [dict(sample_id=str(i)) for i in range(5)])
    rows = runner_functions()['read_manifest'](path, 2, 1)
    assert [r['sample_id'] for r in rows] == ['1','3']
    assert all(r['prompt_granularity'] == 'registered_condition_continuation' for r in rows)


