#!/usr/bin/env python3
"""Read-only dry validator wiring check, not actual Kconfig resolution."""
import ast
import importlib.util
import json
from pathlib import Path
import sys

DRAFT = Path(__file__).resolve().parent
SOURCE = DRAFT.parents[1]/'linux-mm-copy-vma'
sys.path.insert(0, str(SOURCE/'rusix/scripts'))
tree = ast.parse((DRAFT/'check.py').read_text())
calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and
         isinstance(n.func, ast.Attribute) and n.func.attr == 'spec_from_file_location' and
         isinstance(n.args[0], ast.Constant) and n.args[0].value == 'gate']
assert len(calls) == 1
path = eval(compile(ast.Expression(calls[0].args[1]), '<gate path>', 'eval'), {'SOURCE': SOURCE})
assert path == SOURCE/'rusix/scripts/verify-copy-vma.py'
spec = importlib.util.spec_from_file_location('dry_config_gate', path)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
assert gate.PROFILES == {'copy-vma-c': False, 'copy-vma-rust': True}
configs = {}
target = gate.config_values((SOURCE/'rusix/configs/x86_64-server.config').read_text())
for profile in gate.PROFILES:
    values = gate.config_values((SOURCE/f'rusix/configs/x86_64-{profile}.config').read_text())
    # Model architecture/default-derived values absent from allconfig fragments.
    # This validates API wiring only, not actual Kconfig resolution.
    values.update({key: 'y' for key in ('CONFIG_X86_64', 'CONFIG_THREAD_INFO_IN_TASK',
                                      'CONFIG_MMU', 'CONFIG_PER_VMA_LOCK', 'CONFIG_MEMFD_CREATE')})
    gate.check_config(profile, values, target)
    configs[profile] = values
assert gate.compare(configs['copy-vma-c'], configs['copy-vma-rust']) == ['CONFIG_RUSIX_COPY_VMA_RUST']
try:
    gate.check_config('exit-mmap-c', configs['copy-vma-c'], target)
except ValueError:
    pass
else:
    raise AssertionError('Foreign profile accepted')
spec = importlib.util.spec_from_file_location('snapshot', DRAFT/'snapshot.py')
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)
entries = snapshot.paths(SOURCE, '344b3b272c4e94ac5f7d337baa47dbd244bef191')
for path in gate.input_paths(Path('/nonexistent-build'), SOURCE, True):
    if path.is_relative_to(SOURCE):
        name = str(path.relative_to(SOURCE))
        assert any(name == prefix or name.startswith(prefix+'/') for prefix in entries), name
print(json.dumps({'status': 'PASS', 'scope': 'Actual checker import, two fragment policy checks, foreign-profile negative and exact new dependency inclusion; no Kconfig/build/container execution'}))
