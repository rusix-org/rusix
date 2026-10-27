#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Discover unique constructor allocation PCs from actual linked artifacts."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

spec = importlib.util.spec_from_file_location('fault_trace', Path(__file__).with_name('validate-task-fault-trace.py'))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def discover(symbols, disassembly, implementation):
    owners = []
    for line in symbols.splitlines():
        match = re.fullmatch(r'([0-9a-f]+) ([0-9a-f]+) [Tt] (\S+)', line.strip())
        if match:
            owners.append((int(match[1], 16), int(match[2], 16), match[3]))
    ranges = [(a,s,n) for a,s,n in owners if re.fullmatch(r'copy_process(?:\.(?:isra|constprop)\.\d+)?', n)]
    gate.need(len(ranges) == 1, 'Ambiguous/missing copy_process range')
    start, size, name = ranges[0]
    instructions = []
    for line in disassembly.splitlines():
        match = re.match(r'^\s*([0-9a-f]+):\s+(.+)$', line)
        if match:
            instructions.append((int(match[1],16), match[2]))
    frames = {'slab_frame':set(), 'stack_frame':set()}
    for (address, ins), (next_address, _) in zip(instructions, instructions[1:]):
        if not re.match(r'callq?\s', ins):
            continue
        for key, targets in [('slab_frame', ('kmem_cache_alloc_node_noprof','rusix_task_alloc')),
                             ('stack_frame', ('__alloc_pages_noprof','__alloc_frozen_pages_noprof'))]:
            if not any(f'<{target}>' in ins for target in targets):
                continue
            for base, extent, owner in owners:
                if base <= address < next_address < base + extent:
                    frames[key].add(f'{owner}+0x{next_address-base:x}/0x{extent:x}')
    accepted = []
    for slab in sorted(frames['slab_frame']):
        for stack in sorted(frames['stack_frame']):
            candidate = dict(implementation=implementation, range_symbol=name,
                             range_start=hex(start), range_end=hex(start+size),
                             slab_frame=slab, stack_frame=stack)
            try:
                gate.callsite_proof(symbols, disassembly, candidate)
            except ValueError:
                continue
            accepted.append(candidate)
    gate.need(len(accepted) == 1, f'Expected one attributable callsite pair, found {len(accepted)}; compiled form requires review')
    return accepted[0]


def generate(vmlinux, config, revision, implementation, output):
    gate.need(re.fullmatch('[0-9a-f]{40}', revision), 'Invalid build source')
    output.mkdir(parents=True, exist_ok=False)
    def checked(argv):
        result = subprocess.run(argv, capture_output=True, check=True)
        gate.need(not result.stderr, 'ELF tool diagnostics')
        return result.stdout
    before = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (vmlinux,config)}
    symbols = checked(['llvm-nm','-S','--defined-only',str(vmlinux)])
    disassembly = checked(['llvm-objdump','-d','--no-show-raw-insn',str(vmlinux)])
    (output/'symbols').write_bytes(symbols)
    (output/'disassembly').write_bytes(disassembly)
    with tempfile.TemporaryDirectory(prefix='extract-', dir=output) as temporary:
        checked(['llvm-objcopy','--dump-section',f'.notes={output.resolve() / "notes"}',str(vmlinux),str(Path(temporary)/'copy.elf')])
    cal = dict(schema='1',policy_base=gate.SOURCE,build_source=revision,
               notes_hex=(output/'notes').read_bytes().hex(),
               **discover(symbols.decode(),disassembly.decode(),implementation))
    (output/'calibration.tsv').write_text(''.join(f'{k}\t{v}\n' for k,v in sorted(cal.items())))
    inputs = {'vmlinux':vmlinux.resolve(),'config':config.resolve(),
              **{name:(output/name).resolve() for name in ('symbols','disassembly','notes','calibration.tsv')}}
    packet = dict(policy_base=gate.SOURCE,build_source=revision,inputs={name:dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for name,p in inputs.items()})
    (output/'packet.json').write_text(json.dumps(packet,indent=2)+'\n')
    gate.need(before == {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (vmlinux,config)},'Build inputs changed during discovery')
    # Reuse the independent packet validation path; guest success traces are
    # intentionally not prerequisites here, but are mandatory after execution.
    gate.load_reviewed_calibration(output/'packet.json')
    return cal


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vmlinux',type=Path,required=True)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--source',required=True)
    parser.add_argument('--implementation',choices=('c','rust'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    generate(args.vmlinux,args.config,args.source,args.implementation,args.output)
if __name__=='__main__':main()
