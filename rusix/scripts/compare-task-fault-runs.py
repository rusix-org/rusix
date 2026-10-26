#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Revalidate two completed diagnostic runs before reporting a matched pair."""
import argparse
import hashlib
import importlib.util
import json
import shlex
from pathlib import Path

spec=importlib.util.spec_from_file_location('fault_vm',Path(__file__).with_name('test-task-faults-vm.py'))
vm=importlib.util.module_from_spec(spec);spec.loader.exec_module(vm)


def remapper(output_root=None, source_root=None):
    def mapped(path):
        for old,new in [(Path('/out'),output_root),(Path('/src'),source_root)]:
            if new is not None and path.is_relative_to(old):
                return new.resolve()/path.relative_to(old)
        return path
    return mapped


def verify(path, implementation, remap=lambda p:p):
    need=vm.fault_gate.need
    need((path/'runner.exit').read_text().strip()=='0','Runner did not finish successfully')
    inputs=json.loads((path/'inputs.json').read_text())
    result=json.loads((path/'result.json').read_text())
    need(inputs['implementation']==result['implementation']==implementation,'Wrong pair implementation')
    need(inputs['profile']==f'task-construction-fault-{implementation}','Wrong diagnostic profile')
    need(result['status']=='PASS' and result['source_revision']==inputs['source_revision'],'Wrong result/source identity')
    need(vm.common.digest(path/'config')==inputs['config_sha256'],'Resolved config changed')
    for file,digest in inputs['sources'].items():
        need(vm.common.digest(remap(Path(inputs['source_root']))/file)==digest,'Fixture source changed')
    for file,digest in inputs['artifacts'].items():
        need(vm.common.digest(remap(Path(file)))==digest,'Guest artifact changed')
    selection=json.loads((path/'selection.json').read_text())
    need(selection==inputs['selection'] and selection['status']=='PASS','Selection proof changed')
    for file,digest in selection['input_sha256'].items():
        need(vm.common.digest(remap(Path(file)))==digest,'Selection input changed')
    config=(path/'config').read_text()
    target=remap(Path(inputs['source_root']))/'rusix/configs/x86_64-server.config'
    need(vm.validate_config(inputs['profile'],config,target.read_text())==implementation,'Wrong resolved config')
    artifacts={Path(name).name:Path(name) for name in inputs['artifacts']}
    need(set(artifacts)=={'bzImage','init','controller','worker','initramfs.cpio'},'Guest artifact inventory differs')
    expected=vm.qemu_command(artifacts['bzImage'],artifacts['initramfs.cpio'])
    need(shlex.split((path/'command.sh').read_text())==expected,'QEMU arguments differ from bounded diagnostic contract')
    records=vm.decode_console((path/'console.log').read_text(),int((path/'qemu.exit').read_text()))
    cal,sha=vm.fault_gate.load_reviewed_calibration(path/'calibration/packet.json',remap)
    need(cal['build_source']==inputs['source_revision'],'Calibration source mismatch')
    need(hashlib.sha256(records['calibration.tsv']).hexdigest()==sha,'Guest calibration mismatch')
    for name,data in records.items():
        need(data==(path/'records'/name).read_bytes(),'Decoded capture changed')
    need(vm.attribute(records,cal)==result['attempts'],'Attribution result changed')
    binaries={name:inputs['artifacts'][str(artifacts[name])] for name in ('init','controller','worker')}
    return inputs,result,binaries


def matched_inputs(c, r):
    for key in ('source_revision','container_image','sources'):
        vm.fault_gate.need(c[key]==r[key],'Unmatched pair input: '+key)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--c',type=Path,required=True)
    parser.add_argument('--rust',type=Path,required=True)
    parser.add_argument('--c-output-root',type=Path,help='Host directory mounted at /out for C run')
    parser.add_argument('--rust-output-root',type=Path,help='Host directory mounted at /out for Rust run')
    parser.add_argument('--source-root',type=Path,help='Current checkout mounted at /src for both runs')
    args=parser.parse_args()
    c,cr,cb=verify(args.c,'c',remapper(args.c_output_root,args.source_root))
    r,rr,rb=verify(args.rust,'rust',remapper(args.rust_output_root,args.source_root))
    need=vm.fault_gate.need
    matched_inputs(c,r)
    need(cb==rb,'Compiled guest fixture binaries differ')
    for name in ('rustc','gcc','readelf','qemu'):
        need((args.c/f'{name}-version.log').read_bytes()==(args.rust/f'{name}-version.log').read_bytes(),'Tool versions differ')
    vm.selection.compare(vm.selection.config_values((args.c/'config').read_text()),vm.selection.config_values((args.rust/'config').read_text()))
    print(json.dumps(dict(status='PASS',scope='Matched diagnostic constructor allocation-failure pair',source_revision=c['source_revision'],attempts_per_side=len(cr['attempts'])),indent=2))
if __name__=='__main__':main()
