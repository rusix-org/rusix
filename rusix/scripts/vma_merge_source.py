# SPDX-License-Identifier: GPL-2.0-only
"""Explicit reviewed merge source/config contract; no compiler/runtime claim."""
import hashlib
from pathlib import Path
import re
import vma_modify_source as modify
ID = 'vma-merge-v1'
SELECTOR = 'CONFIG_RUSIX_VMA_MERGE_RUST'
PROFILES = {'vma-merge-c': False, 'vma-merge-rust': True}
BASE_SHA256 = '2d551b10a78e5a79b4b0418f13c0ccdad16e1f71c160f6a7dd3e45915bfff410'
REVIEWED = {'mm/vma.c': '03370ea1bb2e5d49ee499e4104038f22211e4d442312acb15a7c7f98acffc933',
 'mm/vma_merge.h': '304ca575e56aa94e1be104c14724e921f97c9710884a530a737954d6ebe4377c',
 'mm/vma_merge_impl.h': '191ef7fd0058c9dc9f13b71ff2db0438d545ff2491fb2359e990a5cb62603cd3',
 'mm/vma_merge_rust.rs': '01f77b0980f892e5c16bbfcfbc8603669ba762be0dbe22e670780cb22b4dca43'}
NATIVE = ('vma_is_fork_child',
 'is_mergeable_vma',
 'is_mergeable_anon_vma',
 'can_vma_merge_before',
 'can_vma_merge_after',
 'can_vma_merge_left',
 'can_vma_merge_right',
 'can_merge_remove_vma',
 'dup_anon_vma',
 'vmg_adjust_set_range',
 'commit_merge',
 'vma_merge_existing_range',
 'vma_merge_new_range',
 'vma_merge_copied_range',
 'vma_expand',
 'vma_shrink',
 'vma_merge_extend')
PRIMITIVES = ('rusix_merge_mm',
 'rusix_merge_prev',
 'rusix_merge_set_middle',
 'rusix_merge_set_next',
 'rusix_merge_target',
 'rusix_merge_set_target',
 'rusix_merge_copied_from',
 'rusix_merge_set_copied_from',
 'rusix_merge_set_start',
 'rusix_merge_set_end',
 'rusix_merge_pgoff',
 'rusix_merge_set_pgoff',
 'rusix_merge_vm_flags',
 'rusix_merge_anon_vma',
 'rusix_merge_file',
 'rusix_merge_just_expand',
 'rusix_merge_set_adjust_middle_start',
 'rusix_merge_set_adjust_next_start',
 'rusix_merge_set_remove_middle',
 'rusix_merge_set_remove_next',
 'rusix_merge_set_state',
 'rusix_merge_singular',
 'rusix_merge_policy_equal',
 'rusix_merge_uffd_equal',
 'rusix_merge_name_equal',
 'rusix_merge_set_anon',
 'rusix_merge_assert_mm',
 'rusix_merge_assert_vma',
 'rusix_merge_warn',
 'rusix_merge_warn_range',
 'rusix_merge_warn_vmg',
 'rusix_merge_iter_addr',
 'rusix_merge_iter_next_range',
 'rusix_merge_iter_prev_range',
 'rusix_merge_iter_set',
 'rusix_merge_iter_load',
 'rusix_merge_iter_store',
 'rusix_merge_iter_clear',
 'rusix_merge_iter_next_rewind',
 'rusix_merge_adjust_huge',
 'rusix_merge_flags_set',
 'rusix_merge_khugepaged')
REUSED = ('rusix_modify_vmi',
 'rusix_modify_middle',
 'rusix_modify_next',
 'rusix_modify_start',
 'rusix_modify_end',
 'rusix_modify_give_up_on_oom',
 'rusix_modify_adjust_middle_start',
 'rusix_modify_adjust_next_start',
 'rusix_modify_remove_middle',
 'rusix_modify_remove_next',
 'rusix_copy_start',
 'rusix_copy_end',
 'rusix_copy_pgoff',
 'rusix_copy_anon',
 'rusix_modify_flags',
 'rusix_remove_file',
 'rusix_remove_ops',
 'rusix_copy_clone_anon',
 'rusix_copy_unlink_anon',
 'rusix_copy_set_range',
 'rusix_link_config',
 'rusix_link_prealloc',
 'rusix_link_start_write',
 'rusix_modify_prev',
 'rusix_modify_mm',
 'rusix_link_validate',
 'rusix_init_multi_vma_prep',
 'rusix_init_vma_prep',
 'rusix_vma_prepare',
 'rusix_vma_complete',
 'rusix_remove_close')
NATIVE_BODY = {'can_merge_remove_vma': ('static bool can_merge_remove_vma(struct vm_area_struct *vma)\n',
                          '0280b4f93a84f81e4590063909fd2866e6be2eaad6668aca995029f9dd7109f3'),
 'can_vma_merge_after': ('static bool can_vma_merge_after(struct vma_merge_struct *vmg)\n',
                         '1fb3ed469edb4c6c2c0ac1370e39c5b7cd72a9927ac97eac3f4e53d6bd20e636'),
 'can_vma_merge_before': ('static bool can_vma_merge_before(struct vma_merge_struct *vmg)\n',
                          '9752f923ed5411ce6731216db8a9ee8d6bbcb0802d9c9d2024b05fc436ab2ccd'),
 'can_vma_merge_left': ('static bool can_vma_merge_left(struct vma_merge_struct *vmg)\n\n',
                        'f7af785d5791c5e5184175db4fee26ec053608527a4e621c9172d59361edc0fc'),
 'can_vma_merge_right': ('static bool can_vma_merge_right(struct vma_merge_struct *vmg,\n'
                         '\t\t\t\tbool can_merge_left)\n',
                         '3bac069c7537b004ae140c9f5e6a8d83953661f729cdba185168ab22acbb3c2d'),
 'commit_merge': ('static int commit_merge(struct vma_merge_struct *vmg)\n',
                  'c95b58cd70702126e7c29d2fc271ac0eb15e6869bd53aebd01abe9044708d267'),
 'dup_anon_vma': ('static int dup_anon_vma(struct vm_area_struct *dst,\n'
                  '\t\t\tstruct vm_area_struct *src, struct vm_area_struct **dup)\n',
                  '9358815eb8ec49e752a1ee57490396fd10b702a5f27208553838e01f43a87f25'),
 'is_mergeable_anon_vma': ('static bool is_mergeable_anon_vma(struct vma_merge_struct *vmg, bool '
                           'merge_next)\n',
                           '00be8a723b0c37c685b64f99b0ed5ce09042dd5dee46950d72655379c7fd684d'),
 'is_mergeable_vma': ('static inline bool is_mergeable_vma(struct vma_merge_struct *vmg, bool '
                      'merge_next)\n',
                      '5e5ad37b9ab68a61d0aa942e4d371999bea9c7952c30d57fab43a482017ba903'),
 'vma_expand': ('int vma_expand(struct vma_merge_struct *vmg)\n',
                '5e4889f2d22241b43a6861d9eae65d5f94b0df409afedfde36c0ca4548656ad6'),
 'vma_is_fork_child': ('static bool vma_is_fork_child(struct vm_area_struct *vma)\n',
                       'ce852d998dddc123957cc7104f00f49abdd234e91d637806c3254594e89e5395'),
 'vma_merge_copied_range': ('static struct vm_area_struct *vma_merge_copied_range(struct '
                            'vma_merge_struct *vmg)\n',
                            '0d72b53595744ea71ae23e34d99fbb2f64ae9546c7d8902b3948c7de413beda3'),
 'vma_merge_existing_range': ('static __must_check struct vm_area_struct '
                              '*vma_merge_existing_range(\n'
                              '\t\tstruct vma_merge_struct *vmg)\n',
                              '7b89536dd35ea973e12bd38b9f9c830865c05152b39b5ab29d34d239e8152689'),
 'vma_merge_extend': ('struct vm_area_struct *vma_merge_extend(struct vma_iterator *vmi,\n'
                      '\t\t\t\t\tstruct vm_area_struct *vma,\n'
                      '\t\t\t\t\tunsigned long delta)\n',
                      '7936990027981b71bbc2218f9003c099a0a1ee965a4800c208d47d33f5839d37'),
 'vma_merge_new_range': ('struct vm_area_struct *vma_merge_new_range(struct vma_merge_struct '
                         '*vmg)\n',
                         '0480ec0f9776b544672ccd9ddee082451bb144e43b7a1a5edf812ef6486abb6d'),
 'vma_shrink': ('int vma_shrink(struct vma_iterator *vmi, struct vm_area_struct *vma,\n'
                '\t       unsigned long start, unsigned long end, pgoff_t pgoff)\n',
                '5e88204daca442d32b2cf56a3667ba6a834a3b9dc8e3e06e1b3dc373a9bc0c78'),
 'vmg_adjust_set_range': ('static void vmg_adjust_set_range(struct vma_merge_struct *vmg)\n',
                          'f1910099983cc58eee7c0684fb49c7b90cf3f524bc5a7db62b98152cc40147af')}
CONSTANTS = ('rusix_merge_sticky', 'rusix_merge_special', 'rusix_merge_ignore',
             'rusix_merge_nomerge', 'rusix_merge_success', 'rusix_merge_nomem')
REUSED_CONSTANTS = ('rusix_copy_page_shift', 'rusix_copy_enomem')
PREP = ('init_multi_vma_prep', 'init_vma_prep', 'vma_prepare', 'vma_complete')
ENTRIES = ('rusix_merge_existing', 'rusix_merge_new', 'rusix_merge_copied',
           'rusix_merge_expand', 'rusix_merge_extend', 'rusix_merge_shrink')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def context(value):
    if value != ID:
        raise ValueError('Explicit vma-merge-v1 context required')

def restore(text, *, source_context):
    context(source_context)
    if digest(text.encode()) != REVIEWED['mm/vma.c']:
        raise ValueError('Changed reviewed merge source/guard/wrapper/native body')
    for name in ('vma_merge.h', 'vma_merge_impl.h'):
        block='\n#ifdef '+SELECTOR+'\n#include "'+name+'"\n#endif\n'
        if text.count(block) != 1:
            raise ValueError('Missing/duplicate merge include')
        text=text.replace(block, '')
    lines=text.splitlines(keepends=True)
    count=0
    def project(lines):
        nonlocal count
        out=[]; i=0
        while i < len(lines):
            match=re.fullmatch(r'#(ifdef|ifndef) '+SELECTOR+r'\n', lines[i])
            if not match:
                out.append(lines[i]); i+=1; continue
            count+=1; start=i+1; j=start; depth=1; other=None
            while depth and j < len(lines):
                line=lines[j]
                if re.match(r'#\s*(?:if|ifdef|ifndef)\b', line): depth+=1
                elif re.match(r'#\s*endif\b', line): depth-=1
                elif re.match(r'#\s*else\b', line) and depth == 1:
                    if other is not None: raise ValueError('Duplicate alternative')
                    other=j
                j+=1
            if depth: raise ValueError('Unterminated merge selector')
            selected=lines[start:other if other is not None else j-1] if match[1]=='ifndef' else (lines[other+1:j-1] if other is not None else [])
            out.extend(project(selected)); i=j
        return out
    restored=''.join(project(lines))
    if count != 21 or digest(restored.encode()) != BASE_SHA256:
        raise ValueError('Changed 17-policy/four-wrapper full-source restoration')
    for name, (signature, expected) in NATIVE_BODY.items():
        if restored.count(signature+'{') != 1:
            raise ValueError('Missing/duplicate native policy: '+name)
        start=restored.index(signature+'{'); pos=start+len(signature)+1; depth=1
        while pos < len(restored) and depth:
            depth+=(restored[pos]=='{')-(restored[pos]=='}'); pos+=1
        if depth or digest(restored[start:pos].encode()) != expected:
            raise ValueError('Changed native body: '+name)
    return restored

def source_policy(source, *, source_context):
    context(source_context); source=Path(source)
    restored=restore((source/'mm/vma.c').read_text(), source_context=ID)
    for name, expected in REVIEWED.items():
        if digest((source/name).read_bytes()) != expected:
            raise ValueError('Changed reviewed merge input: '+name)
    # Parent source identities remain strict; restoration is source-only and is
    # never supplied to actual preprocessor/ELF selection checks.
    modify.restore(restored, source_context=modify.ID)
    for name, expected in modify.REVIEWED.items():
        if digest((source/name).read_bytes()) != expected:
            raise ValueError('Changed parent input: '+name)
    rust=(source/'mm/vma_merge_rust.rs').read_text()
    links=re.findall(r'#\[link_name = "([^"]+)"\]', rust)
    if len(links)!=81 or set(links)!=set(PRIMITIVES+REUSED+CONSTANTS+REUSED_CONSTANTS):
        raise ValueError('Changed primitive/constant inventory')
    return dict(status='PASS', source_context=ID, restored_vma_sha256=digest(restored.encode()),
                native_policies=list(NATIVE), primitives=list(PRIMITIVES), reused=list(REUSED),
                constants=list(CONSTANTS), reused_constants=list(REUSED_CONSTANTS),
                source_sha256={n:digest((source/n).read_bytes()) for n in REVIEWED},
                scope='Reviewed source identity/restoration only; no compiled selection or execution')

def check_config(profile, values, target, *, source_context):
    context(source_context)
    if profile not in PROFILES: raise ValueError('Unknown merge profile')
    modify.check_config('vma-modify-rust', values, target, source_context=modify.ID)
    if values.get(SELECTOR) != ('y' if PROFILES[profile] else 'n'):
        raise ValueError('Wrong explicit merge selector')

def compare(c, rust, target, *, source_context):
    for profile, values in (('vma-merge-c', c), ('vma-merge-rust', rust)):
        check_config(profile, values, target, source_context=source_context)
    changes={k for k in c.keys() | rust.keys() if c.get(k,'n') != rust.get(k,'n')}
    if changes != {SELECTOR}: raise ValueError('Only merge selector may differ')
    return sorted(changes)
