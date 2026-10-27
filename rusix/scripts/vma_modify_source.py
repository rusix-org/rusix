# SPDX-License-Identifier: GPL-2.0-only
"""Strict source/config scaffolding only; no compiled selection or runtime proof."""
import hashlib
import importlib.util
from pathlib import Path
import re
ID = 'vma-modify-v1'
SELECTOR = 'CONFIG_RUSIX_VMA_MODIFY_RUST'
PROFILES = {'vma-modify-c': False, 'vma-modify-rust': True}
BASE_SHA256 = 'ae07770c413cf47155e342b58a8ad5706ac7e69d190c0732ae208e98cf7f3abc'
REGIONS = (('#ifdef CONFIG_RUSIX_VMA_MODIFY_RUST',
  '4c3700575ef827573065c14435135fc871ec7c6cd180c8363c417ac7a8fc2018',
  False),
 ('#ifdef CONFIG_RUSIX_VMA_MODIFY_RUST',
  'dc1c237085e9679aaea7e88bdfcad0e010211def0698d6076c7eda8497266b19',
  True),
 ('#ifdef CONFIG_RUSIX_VMA_MODIFY_RUST',
  '3c2aa93289bb5ad78cc0fb46260c4797f9259b8b3087c11ead1f2c1a1812acca',
  True),
 ('#ifdef CONFIG_RUSIX_VMA_MODIFY_RUST',
  '21709ce0e08c5a54498da43181a522fb4e40a5bc9d2ca051ed0f6017aafb6a3d',
  True),
 ('#ifdef CONFIG_RUSIX_VMA_MODIFY_RUST',
  'cf4140afee60e6a4dd94a299ffd5cce31b0ae9501b0f93f38cde152dd444bb9c',
  True),
 ('#ifdef CONFIG_RUSIX_VMA_MODIFY_RUST',
  'f215e41663ee418cdf6767fa075d33152a9758e55a7295bfa715fd2f07e8cd5a',
  True),
 ('#ifndef CONFIG_RUSIX_VMA_MODIFY_RUST',
  'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  False),
 ('#ifndef CONFIG_RUSIX_VMA_MODIFY_RUST',
  'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  False),
 ('#ifdef CONFIG_RUSIX_VMA_MODIFY_RUST',
  '8c8d6fb314567fe30e4add9f91ffc51fb71a7e1a41f328ecedd674e97a20248b',
  True),
 ('#ifdef CONFIG_RUSIX_VMA_MODIFY_RUST',
  '098c66993971dc38342ee14b0c8a90de5e7690248b5bb8da8e09f7a27fdf632a',
  True),
 ('#ifdef CONFIG_RUSIX_VMA_MODIFY_RUST',
  'fa249220fecc6ed1ad83de6675816c2d1864e21b6cc31470e1f4447e831e6a53',
  True),
 ('#ifdef CONFIG_RUSIX_VMA_MODIFY_RUST',
  'dd3b3c17b4f7e26584d7aff23bc0993ac9f17f1809c36b8f3a62394aa2a6ffd3',
  True),
 ('#ifdef CONFIG_RUSIX_VMA_MODIFY_RUST',
  '5008de1a1299b9d448a3bc249defddfd0dcf2c6e468dd2482bcc24c89009c61a',
  False))
NATIVE = {'init_multi_vma_prep': '949de3dfa734db3e76c5fe269a0db52945ffb1bfb597870446063c25d2384b92',
 'init_vma_prep': 'd46eeeec8c66def709be1b7879324a435af866c28b5d4f65db504c3ec8237854',
 'vma_prepare': '2eb976bddfe4f86ae1098e00e474dd82bd9db2b66c230133a3b161401a712bdb',
 'vma_complete': '1cfecbbc569f81842c60fa3ac9f415192442c124c98dd5894d31635107172b57',
 '__split_vma': 'd21495a5ea87f8a136e838862cb39dce75e6637646228e49a4fd68fa01199655',
 'split_vma': '8552381bd415ae3d91999b267222ef0f947efb7625da2f01b597e12b69af01ea',
 'vma_modify': '18e38c6b9c49aad3b0cfc2296670ea7acee429b9290513ec2e7cfcd9a3849919',
 'vma_modify_flags': '3b8207b3cdccc447ca636341eb8d20819776e7a4686e1c17f4ba958c5db94155',
 'vma_modify_name': 'ce6c9952d913a75eb837b0b58ff2a81bd69e4ffd9ba6ee9b8bae73c2b76cc982',
 'vma_modify_policy': 'a08314dcef274d8fdcdc6699dce78d29bf8835d424306305e619cbacd9a2a187',
 'vma_modify_flags_uffd': '970e7873b1359d1d7b4871ecfbcb1f0bc088c465d00c5660f1670f4d47427c9f'}
PRIMITIVES = ('rusix_prep_vma',
 'rusix_prep_set_vma',
 'rusix_prep_adj_next',
 'rusix_prep_set_adj_next',
 'rusix_prep_file',
 'rusix_prep_set_file',
 'rusix_prep_mapping',
 'rusix_prep_set_mapping',
 'rusix_prep_anon_vma',
 'rusix_prep_set_anon_vma',
 'rusix_prep_insert',
 'rusix_prep_set_insert',
 'rusix_prep_remove',
 'rusix_prep_set_remove',
 'rusix_prep_remove2',
 'rusix_prep_set_remove2',
 'rusix_prep_skip_vma_uprobe',
 'rusix_prep_set_skip_vma_uprobe',
 'rusix_prep_zero',
 'rusix_modify_middle',
 'rusix_modify_next',
 'rusix_modify_remove_middle',
 'rusix_modify_remove_next',
 'rusix_modify_adjust_middle_start',
 'rusix_modify_adjust_next_start',
 'rusix_modify_skip_vma_uprobe',
 'rusix_modify_give_up_on_oom',
 'rusix_modify_start',
 'rusix_modify_end',
 'rusix_modify_vmi',
 'rusix_modify_set_vm_flags',
 'rusix_modify_set_anon_name',
 'rusix_modify_set_policy',
 'rusix_modify_set_give_up_on_oom',
 'rusix_modify_set_uffd',
 'rusix_modify_nomem',
 'rusix_modify_merged',
 'rusix_modify_merge',
 'rusix_modify_error',
 'rusix_modify_is_error',
 'rusix_modify_mm',
 'rusix_modify_flags',
 'rusix_modify_set_start',
 'rusix_modify_set_end',
 'rusix_modify_set_pgoff',
 'rusix_modify_max_map_count',
 'rusix_modify_may_split',
 'rusix_modify_split',
 'rusix_modify_iter_free',
 'rusix_modify_iter_next',
 'rusix_modify_prev',
 'rusix_modify_adjust_huge',
 'rusix_modify_is_hugetlb',
 'rusix_modify_hugetlb_split',
 'rusix_modify_uprobe_unmap',
 'rusix_modify_uprobe_map',
 'rusix_modify_anon_lock',
 'rusix_modify_anon_unlock',
 'rusix_modify_anon_pre',
 'rusix_modify_anon_post',
 'rusix_modify_interval_remove',
 'rusix_modify_unmap_writable',
 'rusix_modify_store_new',
 'rusix_modify_detach',
 'rusix_modify_anon_merge',
 'rusix_modify_warn_start',
 'rusix_modify_warn_end',
 'rusix_modify_warn_anon',
 'rusix_modify_warn_oom',
 'rusix_modify_warn_removed_end')
REVIEWED = {'mm/vma_modify.h': '81b024ee9733eeed8725337ee6f90c4eaec1ef40755ae70f7ebe51c4bd97eded',
 'mm/vma_modify_impl.h': '0989a5bdd3ba3c8fe51834090170d2860d610d4414fbce195e06b03fa552a36f',
 'mm/vma_modify_rust.rs': '8768c8db03c53a20ad0e07819b236005923b1b82d1a8d5893f05fe92feaa6b10'}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def context(value):
    if value != ID:
        raise ValueError('Explicit vma-modify-v1 context required')

def native_body(text, name):
    matches = list(re.finditer(r'\b'+re.escape(name)+r'\s*\([^;{}]*\)\s*\{', text))
    if len(matches) != 1:
        raise ValueError('Missing/duplicate native definition: '+name)
    match = matches[0]
    pos, depth = match.end(), 1
    while pos < len(text) and depth:
        depth += (text[pos] == '{') - (text[pos] == '}')
        pos += 1
    if depth:
        raise ValueError('Unterminated native definition')
    return text[match.start():pos]

def restore(text, *, source_context):
    context(source_context)
    lines = text.splitlines(keepends=True)
    result, found, i = [], [], 0
    while i < len(lines):
        directive = lines[i].strip()
        if directive not in ('#ifdef '+SELECTOR, '#ifndef '+SELECTOR):
            if SELECTOR in lines[i]:
                raise ValueError('Unknown selector guard or use')
            result.append(lines[i]); i += 1
            continue
        start, depth, middle = i, 1, None
        i += 1
        while i < len(lines) and depth:
            line = lines[i].strip()
            if re.match(r'#\s*if(?:def|ndef)?\b', line):
                if SELECTOR in line:
                    raise ValueError('Nested selector guard')
                depth += 1
            elif line.startswith('#endif'):
                depth -= 1
            elif line == '#else' and depth == 1:
                if middle is not None:
                    raise ValueError('Duplicate guard alternative')
                middle = i
            if depth:
                i += 1
        if depth:
            raise ValueError('Unterminated selector guard')
        selected = ''.join(lines[start+1:middle if middle is not None else i]) if directive.startswith('#ifdef') else ''
        found.append((directive, digest(selected.encode()), middle is not None))
        if directive.startswith('#ifndef'):
            if middle is not None:
                raise ValueError('Unexpected native guard alternative')
            result.extend(lines[start+1:i])
        elif middle is not None:
            result.extend(lines[middle+1:i])
        # The two include-only additions also introduce one separating blank.
        elif selected in ('#include "vma_modify.h"\n', '#include "vma_modify_impl.h"\n'):
            if selected.endswith('"vma_modify.h"\n'):
                if i+1 >= len(lines) or lines[i+1] != '\n':
                    raise ValueError('Changed header include boundary')
                i += 1
            elif not result or result.pop() != '\n':
                raise ValueError('Changed helper include boundary')
        else:
            raise ValueError('Unknown selected wrapper')
        expected_end = '#endif' if middle is None and directive.startswith('#ifdef') else '#endif /* '+SELECTOR+' */'
        # The line index may have advanced across the include's blank separator.
        end_index = i-1 if selected == '#include "vma_modify.h"\n' else i
        if lines[end_index].strip() != expected_end:
            raise ValueError('Changed guard terminator')
        i += 1
    if tuple(found) != REGIONS:
        raise ValueError('Missing/duplicate/changed wrapper inventory')
    restored = ''.join(result)
    if digest(restored.encode()) != BASE_SHA256:
        raise ValueError('Original source or boundary changed')
    for name, expected in NATIVE.items():
        if digest(native_body(restored, name).encode()) != expected:
            raise ValueError('Original native body changed: '+name)
    return restored

def source_policy(source, *, source_context):
    context(source_context)
    source = Path(source)
    restored = restore((source/'mm/vma.c').read_text(), source_context=source_context)
    for name, expected in REVIEWED.items():
        if digest((source/name).read_bytes()) != expected:
            raise ValueError('Reviewed primitive/ABI/Rust source changed: '+name)
    impl = (source/'mm/vma_modify_impl.h').read_text()
    names = re.findall(r'^\w[^\n;]*\b(rusix_\w+)\s*\([^;]*?\)\s*\{', impl, re.M)
    if tuple(names) != PRIMITIVES or len(set(names)) != 70:
        raise ValueError('Changed 70-primitive inventory')
    return {'status': 'PASS', 'source_context': ID,
            'restored_vma_sha256': digest(restored.encode()),
            'native_policies': list(NATIVE), 'primitives': list(PRIMITIVES),
            'scope': 'Reviewed source identity only; no compiled selection or execution'}

def copy_gate():
    spec = importlib.util.spec_from_file_location('modify_copy_config', Path(__file__).with_name('verify-copy-vma.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def check_config(profile, values, target, *, source_context):
    context(source_context)
    if profile not in PROFILES:
        raise ValueError('Unknown VMA modify profile')
    copy_gate().check_config('copy-vma-rust', values, target)
    if values.get(SELECTOR) != ('y' if PROFILES[profile] else 'n'):
        raise ValueError('Wrong explicit modify selector')
    if any(k.startswith('CONFIG_RUSIX_') and k.endswith('_TEST') and v != 'n' for k,v in values.items()):
        raise ValueError('Ordinary profile cannot select native fixtures')

def compare(c, rust, target, *, source_context):
    for profile, values in (('vma-modify-c', c), ('vma-modify-rust', rust)):
        check_config(profile, values, target, source_context=source_context)
    changes = {k for k in c.keys() | rust.keys() if c.get(k, 'n') != rust.get(k, 'n')}
    if changes != {SELECTOR}:
        raise ValueError('Only VMA modify selector may differ')
    return sorted(changes)
