#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Fail-closed attribution of captured guest faults; synthetic tests are not VM evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

SOURCE = '8fd3defabb841083192cd1d9c4eb1cde83027579'
HEADER = re.compile(r'^\s*.*?-(\d+)\s+\[(\d+)\]\s+.*?\s+\d+\.\d+:\s+(.*)$')
RESULT = re.compile(r'RESULT pid=(\d+) nth=(\d+) ret=(-?\d+) errno=(\d+) remaining=(\d+) child_status=(-?\d+) retry_status=(-?\d+)')


def need(value, reason):
    if not value:
        raise ValueError(reason)


def field(text, name):
    match = re.search(r'(?:^|\s)' + name + r'=([^\s]+)', text)
    need(match, 'Missing field ' + name)
    return match[1]


def zero(value):
    return value in ('(nil)', '(null)') or re.fullmatch(r'(?:0x)?0+', value) is not None


def events(text, pid):
    rows = []
    for line in text.splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        if line.lstrip().startswith('=> '):
            need(rows and rows[-1]['body'] == '<stack trace>', 'Orphan stack frame')
            rows[-1]['frames'].append(line.strip()[3:])
            continue
        match = HEADER.fullmatch(line)
        need(match, 'Unrecognized trace record: ' + line)
        owner, cpu, body = match.groups()
        # Stack triggers must carry the same actor/context as the actual decision.
        need(int(owner) == pid, 'Unexpected trace actor')
        rows.append(dict(cpu=cpu, body=body, frames=[]))
    arm = [i for i,r in enumerate(rows) if r['body'] == 'tracing_mark_write: ARM']
    end = [i for i,r in enumerate(rows) if r['body'] == 'tracing_mark_write: DISARM']
    need(len(arm) == len(end) == 1 and arm[0] < end[0], 'Missing/duplicate/reordered armed interval')
    return rows[arm[0]+1:end[0]]


def no_loss(stats, probes):
    for stat in stats:
        for key in ('overrun', 'commit overrun', 'dropped events'):
            vals = re.findall(r'^' + key + r':\s*(\d+)\s*$', stat, re.M)
            need(vals == ['0'], 'Missing/nonzero trace loss: ' + key)
    found = set()
    for line in probes.splitlines():
        cols = line.split()
        if not cols or cols[0] not in {'page_decision','slab_decision','pages_result'}:
            continue
        need(len(cols) == 3 and cols[1].isdigit() and cols[2] == '0', 'Probe misses or malformed profile')
        need(cols[0] not in found, 'Duplicate probe profile')
        found.add(cols[0])
    need(found == {'page_decision','slab_decision','pages_result'}, 'Probe inventory differs')


def classify(worker, trace, calibration, stats, probes):
    match = RESULT.fullmatch(worker.strip())
    need(match, 'Malformed worker result')
    pid,nth,ret,error,remaining,child,retry = map(int, match.groups())
    need(pid > 1 and 0 <= nth <= 16 and 0 <= remaining <= nth and child == retry == 0, 'Worker/child/retry failure')
    no_loss(stats, probes)
    rows = events(trace, pid)
    decisions = [(i,r) for i,r in enumerate(rows) if
                 (r['body'].startswith('page_decision:') and field(r['body'],'injected') == '1') or
                 (r['body'].startswith('slab_decision:') and field(r['body'],'result') == '-12')]
    if nth == 0:
        need(ret > 0 and not decisions, 'Calibration fork failed or injected')
        for kind, frame, value in [('slab_decision:',calibration['slab_frame'],'result'), ('page_decision:',calibration['stack_frame'],'injected')]:
            need(any(r['body'].startswith(kind) and field(r['body'],value)=='0' and i+1<len(rows) and rows[i+1]['body']=='<stack trace>' and rows[i+1]['cpu']==r['cpu'] and frame in rows[i+1]['frames'] for i,r in enumerate(rows)), 'Missing successful allocation stack calibration')
        return {'classification':'uninjected-control','pid':pid}
    if remaining:
        need(ret > 0 and not decisions, 'Unconsumed request did not succeed cleanly')
        return {'classification':'not-injected','pid':pid,'nth':nth}
    need(ret == -1 and error == 12 and len(decisions) == 1, 'Need one observed injection and ENOMEM')
    index, decision = decisions[0]
    need(index+1 < len(rows), 'Missing decision stack')
    stack = rows[index+1]
    need(stack['body'] == '<stack trace>' and stack['cpu'] == decision['cpu'] and stack['frames'], 'Unattributed injection stack')
    need(not any(r['body'].startswith('sched_process_fork:') for r in rows), 'Child published in failed attempt')
    allocations = [r['body'] for r in rows if r['body'].startswith('kmem_cache_alloc:') and field(r['body'],'name') == 'task_struct']
    frees = [r['body'] for r in rows if r['body'].startswith('kmem_cache_free:') and field(r['body'],'name') == 'task_struct']
    if decision['body'].startswith('slab_decision:'):
        need(calibration['slab_frame'] in stack['frames'], 'Slab failure not at calibrated constructor callsite')
        need(len(allocations) == 1 and zero(field(allocations[0],'ptr')) and not frees, 'Slab failure acquired/freed unexpected task')
        alloc_index = next(i for i,r in enumerate(rows) if r['body'] == allocations[0])
        need(index + 1 < alloc_index, 'Wrong slab decision/stack/NULL allocation order')
        return {'classification':'task-slab-failure','pid':pid,'nth':nth}
    need(field(decision['body'],'order') == '2', 'Wrong allocation order')
    if calibration['stack_frame'] not in stack['frames']:
        # Keep unsuccessful sweep attribution honest; do not call every ENOMEM a stack hit.
        return {'classification':'other-page-failure','pid':pid,'nth':nth}
    need(len(allocations) == len(frees) == 1, 'Need one task allocation and matching rollback free')
    ptr = field(allocations[0],'ptr')
    need(re.fullmatch(r'(?:0x)?[0-9a-f]{8,16}',ptr) and not zero(ptr) and field(frees[0],'ptr') == ptr, 'Task slab rollback identity mismatch or unavailable pointer')
    alloc_index = next(i for i,r in enumerate(rows) if r['body'] == allocations[0])
    free_index = next(i for i,r in enumerate(rows) if r['body'] == frees[0])
    returns = [i for i,r in enumerate(rows) if r['body'].startswith('pages_result:') and field(r['body'],'order') == '2' and zero(field(r['body'],'result'))]
    need(len(returns) == 1 and alloc_index < index < returns[0] < free_index, 'Wrong allocation/injection/NULL-return/free order')
    return {'classification':'stack-page-failure','pid':pid,'nth':nth}


def callsite_proof(symbols, disassembly, calibration):
    """Bind exact stack PCs to real call instructions, not supplied frame labels."""
    symbol_rows = {}
    for line in symbols.splitlines():
        m = re.fullmatch(r'([0-9a-f]+) ([0-9a-f]+) [Tt] (\S+)', line.strip())
        if m:
            need(m[3] not in symbol_rows, 'Duplicate code symbol')
            symbol_rows[m[3]] = (int(m[1],16),int(m[2],16))
    instructions = []
    for line in disassembly.splitlines():
        m = re.match(r'^\s*([0-9a-f]+):\s+(.+)$',line)
        if m: instructions.append((int(m[1],16),m[2]))
    range_name = calibration['range_symbol']
    need(range_name in symbol_rows, 'Missing constructor caller range')
    start,size = symbol_rows[range_name]
    need(int(calibration['range_start'],0)==start and int(calibration['range_end'],0)==start+size, 'Required range does not match actual symbol extent')
    need(re.fullmatch(r'copy_process(?:\.(?:isra|constprop)\.\d+)?',range_name), 'Expected copy_process lifetime context')
    for key, allowed in [('slab_frame',{'kmem_cache_alloc_node_noprof'}), ('stack_frame',{'__alloc_pages_noprof','__alloc_frozen_pages_noprof'})]:
        m=re.fullmatch(r'([A-Za-z0-9_.$]+)\+0x([0-9a-f]+)/0x([0-9a-f]+)',calibration[key])
        need(m and m[1] in symbol_rows,'Unknown frame symbol')
        if calibration.get('implementation','c')=='rust':
            owners={'rusix_dup_task_struct','rusix_task_alloc'} if key=='slab_frame' else {'rusix_task_alloc_stack'}
            need(m[1] in owners,'Frame is outside Rust constructor adapters')
        else:
            need(re.fullmatch(r'(?:copy_process|dup_task_struct|alloc_task_struct_node|alloc_thread_stack_node)(?:\.(?:isra|constprop)\.\d+)?',m[1]),'Frame is outside C constructor allocation chain')
        base,size=symbol_rows[m[1]]; offset=int(m[2],16)
        need(int(m[3],16)==size and 0<=offset<size,'Wrong frame extent')
        pc=base+offset
        candidates=[(ins,next_ins) for ins,next_ins in zip(instructions,instructions[1:]) if next_ins[0]==pc]
        need(len(candidates)==1,'Frame PC outside disassembled instructions')
        (address,text),(next_address,_)=candidates[0]
        # This ordinary trace instance prints saved return PCs unchanged.
        # Require the address immediately after a real call instruction.
        need(pc==next_address and re.match(r'callq?\s',text),'Frame is not an allocation call return PC')
        target=re.search(r'<([^>]+)>',text)
        need(target,'Unresolved call target')
        callee=target[1]
        targets=allowed | ({'rusix_task_alloc'} if key=='slab_frame' else set())
        qualifying=[t for a,t in instructions if base<=a<base+size and re.match(r'callq?\s',t) and any(re.search(r'<'+re.escape(name)+r'>',t) for name in targets)]
        need(len(qualifying)==1,'Ambiguous allocator sites in constructor owner; require reviewed argument/source mapping')
        if key=='slab_frame' and callee=='rusix_task_alloc':
            need(callee in symbol_rows,'Missing allocator adapter')
            ab,sz=symbol_rows[callee]
            branches=[t for a,t in instructions if ab<=a<ab+sz and re.match(r'(?:callq?|jmpq?)\s',t)]
            need(len(branches)==1 and re.match(r'jmpq?\s',branches[0]) and re.search(r'<kmem_cache_alloc_node_noprof>',branches[0]),'Adapter is not the exact allocator tail jump')
        else:
            need(callee in allowed,'Frame call is not the required allocator')
    return True


def disassembly_matches(recorded, actual, recorded_path, actual_path):
    """Allow only the ELF filename heading to follow a verified path remap."""
    def bound_heading(text, filename):
        filename = str(filename)
        need(filename and not any(c in filename for c in '\r\n'),
             'Invalid disassembly filename')
        lines = text.splitlines(keepends=True)
        prefix = filename + ':\tfile format '
        need(len(lines) >= 2 and lines[0] == '\n' and lines[1].startswith(prefix),
             'Missing or wrong disassembly filename heading')
        need(sum('\tfile format ' in line for line in lines) == 1,
             'Duplicate disassembly file heading')
        # Preserve format, whitespace, newlines and the entire instruction body.
        # Only the exact expected filename bytes at the fixed heading are omitted.
        return lines[0] + lines[1][len(filename):] + ''.join(lines[2:])
    return bound_heading(recorded, recorded_path) == bound_heading(actual, actual_path)


def load_reviewed_calibration(path, remap=lambda p: p):
    def unique(pairs):
        result={}
        for key,value in pairs:
            need(key not in result,'Duplicate calibration JSON key')
            result[key]=value
        return result
    packet = json.loads(path.read_text(), object_pairs_hook=unique)
    need(set(packet) == {'policy_base','build_source','inputs'}, 'Calibration packet schema')
    need(packet['policy_base'] == SOURCE and re.fullmatch('[0-9a-f]{40}',packet['build_source']), 'Wrong source identities')
    need(set(packet['inputs']) == {'vmlinux','config','symbols','disassembly','notes','calibration.tsv'}, 'Calibration input inventory')
    inputs={}
    for key,item in packet['inputs'].items():
        need(set(item) == {'path','sha256'}, 'Calibration hash schema')
        p = Path(item['path'])
        if not p.is_absolute(): p = path.parent / p
        p = remap(p)
        need(hashlib.sha256(p.read_bytes()).hexdigest() == item['sha256'], 'Calibration input changed')
        inputs[key]=p
    rows=[line.split('\t') for line in inputs['calibration.tsv'].read_text().splitlines()]
    need(all(len(r)==2 for r in rows) and len({r[0] for r in rows})==len(rows),'Malformed calibration TSV')
    cal=dict(rows)
    need(set(cal)=={'schema','policy_base','build_source','implementation','notes_hex','range_symbol','range_start','range_end','slab_frame','stack_frame'},'Wrong TSV fields')
    need(cal['schema']=='1' and cal['policy_base']==SOURCE and cal['build_source']==packet['build_source'],'Calibration identity mismatch')
    config=inputs['config'].read_text().splitlines()
    selector='CONFIG_RUSIX_TASK_CONSTRUCTION_RUST=y' if cal['implementation']=='rust' else '# CONFIG_RUSIX_TASK_CONSTRUCTION_RUST is not set'
    need(cal['implementation'] in ('c','rust') and selector in config,'Wrong implementation/config')
    need('# CONFIG_VMAP_STACK is not set' in config and '# CONFIG_KASAN is not set' in config,'Wrong stack allocation profile')
    def checked(argv):
        r=subprocess.run(argv,check=True,capture_output=True)
        need(not r.stderr,'ELF tool diagnostics')
        return r.stdout
    symbols=checked(['llvm-nm','-S','--defined-only',str(inputs['vmlinux'])]).decode()
    disassembly=checked(['llvm-objdump','-d','--no-show-raw-insn',str(inputs['vmlinux'])]).decode()
    need(symbols==inputs['symbols'].read_text() and disassembly_matches(
        inputs['disassembly'].read_text(), disassembly,
        packet['inputs']['vmlinux']['path'], inputs['vmlinux']),
        'Supplied symbols/disassembly differ from actual ELF')
    with tempfile.TemporaryDirectory(prefix='task-fault-notes-', dir=path.parent) as tmp:
        notes=Path(tmp)/'notes'
        checked(['llvm-objcopy','--dump-section',f'.notes={notes}',str(inputs['vmlinux']),str(Path(tmp)/'copy.elf')])
        need(notes.read_bytes()==inputs['notes'].read_bytes() and notes.read_bytes().hex()==cal['notes_hex'],'Kernel notes mismatch')
    callsite_proof(symbols,disassembly,cal)
    for key,item in packet['inputs'].items():
        need(hashlib.sha256(inputs[key].read_bytes()).hexdigest()==item['sha256'],'Calibration inputs changed during verification')
    return cal,packet['inputs']['calibration.tsv']['sha256']


def attempt_identity(label, worker, seen):
    match = RESULT.fullmatch(worker.strip())
    need(match, 'Malformed worker result')
    pid, nth = map(int, match.groups()[:2])
    expected = 0 if label == 'calibration' else int(label.rsplit('-',1)[1])
    need(nth == expected, 'Attempt label/request mismatch')
    need(pid not in seen, 'Repeated worker PID/capture')
    seen.add(pid)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--records',type=Path,required=True)
    ap.add_argument('--calibration',type=Path,required=True)
    args=ap.parse_args();cal,cal_sha=load_reviewed_calibration(args.calibration)
    need(hashlib.sha256((args.records/'calibration.tsv').read_bytes()).hexdigest()==cal_sha,'Guest used different calibration')
    result=[];seen=set()
    for label in ['calibration','slab-1']+[f'stack-{n}' for n in range(1,17)]:
        get=lambda ext:(args.records/f'{label}.{ext}').read_text()
        attempt_identity(label,get('worker'),seen)
        result.append(dict(label=label,**classify(get('worker'),get('trace'),cal,[get('cpu0'),get('cpu1')],get('probes'))))
    need(result[0]['classification']=='uninjected-control','Missing uninjected control')
    need(result[1]['classification']=='task-slab-failure','Missing targeted slab failure')
    need(any(r['classification']=='stack-page-failure' for r in result[2:]),'No attributable stack failure in bounded sweep')
    print(json.dumps({'status':'PASS','scope':'Captured raw trace/syscall attribution only; external VM/source/cleanup gates still required','attempts':result},indent=2))
if __name__=='__main__':main()
