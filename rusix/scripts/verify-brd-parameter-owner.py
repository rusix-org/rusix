#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Verify Rust-owned BRD metadata in its ELF object and linked x86_64 kernel.

The fixed record offsets below are an independent oracle for the pinned x86_64
C ABI (kernel_param and obs_kernel_param), not production Rust layout copies.
Section/header validation reuses the existing language-measurement ELF reader;
this reader adds symbols and RELA pointers needed to establish actual ownership.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location(
    "rusix_measure_metadata", Path(__file__).with_name("measure-kernel-languages.py"))
measurement = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = measurement
spec.loader.exec_module(measurement)

EXPECTED = {
    "brd.rd_nr": ("rusix_brd_rd_nr", "param_ops_int", 4),
    "brd.rd_size": ("rd_size", "param_ops_ulong", 8),
    "brd.max_part": ("rusix_brd_max_part", "param_ops_int", 4),
}
MODINFO = {
    b"brd.parmtype=rd_nr:int", b"brd.parm=rd_nr:Maximum number of brd devices",
    b"brd.parmtype=rd_size:ulong", b"brd.parm=rd_size:Size of each RAM disk in kbytes.",
    b"brd.parmtype=max_part:int", b"brd.parm=max_part:Num Minors to reserve between devices",
}
WRAPPERS = {"rusix_brd_params_lock", "rusix_brd_params_unlock"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Elf:
    def __init__(self, path, *, indexed_sections=False):
        # Reuse existing ELF64/x86_64/section extent validation.
        self.sections = measurement.elf_sections(path, indexed=indexed_sections)
        self.data = path.read_bytes()
        header = struct.unpack_from("<16sHHIQQQIHHHHHH", self.data)
        self.relocatable = header[1] == 1
        require(header[1] in (1, 2), "Expected relocatable object or linked executable")
        self.headers = [struct.unpack_from("<IIQQQQIIQQ", self.data, header[6] + 64 * i)
                        for i in range(header[12])]
        strings = self.section_data(header[13])
        self.names = [self.cstring(strings, row[0]) for row in self.headers]
        # Only unambiguous names support name lookup. Relocatable C objects can
        # legitimately repeat patchable-function sections; symbol/relocation
        # access below identifies them by section index instead.
        self.indices = {name: index for index, name in enumerate(self.names)
                        if self.names.count(name) == 1}
        self.symbols = []
        tables = {}
        for index, section in enumerate(self.headers):
            if section[1] != 2:
                continue
            require(section[9] == 24 and section[5] % 24 == 0, "Bad symbol table stride")
            strings = self.section_data(section[6])
            table = []
            entries = self.section_data(index)
            for offset in range(0, section[5], 24):
                name, info, _, shndx, address, size = struct.unpack_from(
                    "<IBBHQQ", entries, offset)
                symbol = dict(name=self.cstring(strings, name), kind=info & 15,
                              section=shndx, address=address, size=size)
                table.append(symbol)
            tables[index] = table
            self.symbols.extend(table)
        self.relocations = {}
        if self.relocatable:
            for index, section in enumerate(self.headers):
                if section[1] != 4:
                    continue
                require(section[9] == 24 and section[5] % 24 == 0, "Bad RELA stride")
                table = tables[section[6]]
                entries = self.section_data(index)
                for offset in range(0, section[5], 24):
                    address, info, addend = struct.unpack_from(
                        "<QQq", entries, offset)
                    key = (section[7], address)
                    require(key not in self.relocations, "Duplicate relocation")
                    self.relocations[key] = (info & 0xffffffff, table[info >> 32], addend)

    @staticmethod
    def cstring(data, offset):
        require(0 <= offset < len(data), "String offset outside section")
        end = data.find(b"\0", offset)
        require(end >= 0, "Unterminated string")
        return data[offset:end].decode()

    def section_data(self, index):
        row = self.headers[index]
        if row[1] == 8:
            return bytes(row[5])
        return self.data[row[4]:row[4] + row[5]]

    def symbol(self, name):
        values = [s for s in self.symbols if s['name'] == name and s['section']]
        require(len(values) == 1, f"Missing/duplicate defined symbol {name}")
        return values[0]

    def location(self, symbol):
        index = symbol['section']
        require(0 < index < len(self.headers), "Symbol has no storage section")
        return index, symbol['address'] - (0 if self.relocatable else self.headers[index][3])

    def at_address(self, address):
        found = [(i, address - row[3]) for i, row in enumerate(self.headers)
                 if row[2] & 2 and row[3] <= address < row[3] + row[5]]
        require(len(found) == 1, f"Pointer outside unique allocated section: {address:x}")
        return found[0]

    def pointer(self, location):
        index, offset = location
        if self.relocatable and location in self.relocations:
            kind, symbol, addend = self.relocations[location]
            require(kind == 1, "Metadata pointer must use R_X86_64_64")
            if not symbol['section']:
                require(addend == 0, "Unexpected external pointer addend")
                return symbol['name']
            target, position = self.location(symbol)
            return target, position + addend
        value = struct.unpack_from('<Q', self.section_data(index), offset)[0]
        if value == 0:
            return None
        require(not self.relocatable, "Unrelocated nonzero metadata pointer")
        return self.at_address(value)

    def text(self, location):
        require(isinstance(location, tuple), "Expected pointer to defined string")
        return self.cstring(self.section_data(location[0]), location[1])

    def permanent(self, location, size=1, writable=False):
        index, offset = location
        row = self.headers[index]
        require(0 <= offset and offset + size <= row[5], "Storage exceeds section")
        require(row[2] & 2 and not self.names[index].startswith('.init'), "Storage is not permanent")
        if writable:
            require(row[2] & 1, "Scalar storage must be writable")
        if not self.relocatable:
            start = self.symbol('__init_begin')['address']
            end = self.symbol('__init_end')['address']
            address = row[3] + offset
            require(not (address < end and address + size > start), "Permanent object overlaps init memory")

    def record_range(self, section, start=None, end=None):
        if self.relocatable:
            require(section in self.indices, f"Missing or ambiguous metadata section: {section}")
            index = self.indices[section]
            return index, 0, self.headers[index][5]
        first, last = self.symbol(start)['address'], self.symbol(end)['address']
        index, offset = self.at_address(first)
        require(last > first and offset + last - first <= self.headers[index][5], "Invalid linker record range")
        return index, offset, offset + last - first


def verify(path, initial):
    elf = Elf(path, indexed_sections=True)
    require(not any(s['name'] in WRAPPERS and s['section'] for s in elf.symbols),
            "BRD-specific C parameter wrappers still defined")
    scalars = {}
    for public, (name, _, size) in EXPECTED.items():
        symbol = elf.symbol(name)
        location = elf.location(symbol)
        require(symbol['kind'] == 1 and symbol['size'] == size, f"Wrong scalar ABI: {name}")
        row = elf.headers[location[0]]
        require(symbol['address'] % size == 0 and row[8] >= size, f"Misaligned scalar {name}")
        elf.permanent(location, size, writable=True)
        value = struct.unpack_from('<i' if size == 4 else '<Q', elf.section_data(location[0]), location[1])[0]
        require(value == initial[public], f"Wrong initial scalar value: {name}")
        scalars[public] = location

    index, start, end = elf.record_range('__param', '__start___param', '__stop___param')
    require(start % 8 == 0 and (end - start) % 40 == 0 and elf.headers[index][8] >= 8,
            "Invalid x86_64 kernel_param alignment/stride")
    if elf.relocatable:
        require(end - start == 120, "Rust BRD object must own exactly three parameter records")
    found = []
    for offset in range(start, end, 40):
        name_pointer = elf.pointer((index, offset))
        name = elf.text(name_pointer)
        if not name.startswith('brd.'):
            continue
        require(name in EXPECTED and name not in found, f"Unexpected/duplicate BRD parameter {name}")
        found.append(name)
        elf.permanent((index, offset), 40)
        elf.permanent(name_pointer, len(name) + 1)
        require(elf.pointer((index, offset + 8)) is None, "Builtin parameter has module pointer")
        ops_name = EXPECTED[name][1]
        expected_ops = ops_name if elf.relocatable else elf.location(elf.symbol(ops_name))
        require(elf.pointer((index, offset + 16)) == expected_ops, f"Wrong ops for {name}")
        perm, level, flags = struct.unpack_from('<HbB', elf.section_data(index), offset + 24)
        require((perm, level, flags) == (0o444, -1, 0), f"Wrong parameter metadata for {name}")
        require(elf.pointer((index, offset + 32)) == scalars[name], f"Wrong argument storage for {name}")
    require(set(found) == set(EXPECTED), "Missing BRD parameter records")

    # vmlinux normally discards .modinfo; the defining Rust object must retain it.
    require(elf.names.count('.modinfo') <= 1, 'Ambiguous modinfo sections')
    if '.modinfo' in elf.indices:
        entries = [s for s in elf.section_data(elf.indices['.modinfo']).split(b'\0')
                   if s.startswith(b'brd.parm')]
        require(len(entries) == 6 and set(entries) == MODINFO, "BRD modinfo differs from C ABI")
    else:
        require(not elf.relocatable, "Rust object lost its parameter modinfo")

    index, start, end = elf.record_range('.init.setup', '__setup_start', '__setup_end')
    require(start % 8 == 0 and (end - start) % 24 == 0 and elf.headers[index][8] >= 8,
            "Invalid x86_64 obs_kernel_param alignment/stride")
    if elf.relocatable:
        require(end - start == 24, "Rust BRD object must own exactly one legacy setup record")
        require(elf.headers[index][2] & 1, "Legacy setup record must retain writable C section")
    legacy = []
    for offset in range(start, end, 24):
        pointer = elf.pointer((index, offset))
        if elf.text(pointer) != 'ramdisk_size=':
            continue
        legacy.append(offset)
        callback = elf.symbol('rusix_brd_legacy_size')
        require(callback['kind'] == 2 and elf.headers[callback['section']][2] & 4,
                "Legacy callback is not executable")
        require(elf.pointer((index, offset + 8)) == elf.location(callback), "Wrong legacy callback")
        require(struct.unpack_from('<i', elf.section_data(index), offset + 16)[0] == 0,
                "Legacy handler must retain early=0")
        require(elf.text(pointer) == 'ramdisk_size=', "Wrong legacy name")
        if elf.relocatable:
            require(elf.names[pointer[0]] == '.init.rodata', "Legacy name lost init-rodata placement")
        else:
            begin, finish = elf.symbol('__init_begin')['address'], elf.symbol('__init_end')['address']
            for location, size in (((index, offset), 24), (pointer, 14)):
                address = elf.headers[location[0]][3] + location[1]
                require(begin <= address and address + size <= finish, "Legacy record/name outside init memory")
    require(len(legacy) == 1, "Missing/duplicate legacy setup record")
    return {'file': str(path), 'parameter_names': sorted(found), 'scalar_symbols':
            [item[0] for item in EXPECTED.values()], 'legacy_setup_count': len(legacy),
            'modinfo': 'verified' if '.modinfo' in elf.indices else 'discarded by final linker'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--object', type=Path, required=True)
    parser.add_argument('--vmlinux', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    config = args.config.read_text()
    def setting(name):
        values = re.findall(r'^CONFIG_' + name + r'=(-?[0-9]+)$', config, re.MULTILINE)
        require(len(values) == 1, f'Missing/duplicate config {name}')
        return int(values[0])
    require('CONFIG_RUSIX_BRD_RUST=y' in config.splitlines(), 'Rust BRD selection required')
    initial = {'brd.rd_nr': setting('BLK_DEV_RAM_COUNT'),
               'brd.rd_size': setting('BLK_DEV_RAM_SIZE'), 'brd.max_part': 1}
    result = [verify(path, initial) for path in (args.object, args.vmlinux)]
    print(json.dumps({'status': 'PASS', 'scope': 'ELF ownership/metadata, not runtime behavior',
                      'objects': result}, indent=2))


if __name__ == '__main__':
    main()
