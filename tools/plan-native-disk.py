#!/usr/bin/env python3
"""Validate donors and emit a non-destructive native disk layout plan."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

MIB = 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audit', ROOT / 'tools/audit-userspace.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def plan(image, firmware, sources):
    if not image.is_file() or not firmware.is_file():
        raise ValueError('Both inputs must be regular image files')
    blob = firmware.read_bytes()
    if hashlib.sha256(blob).hexdigest() != sources['uefi']['sha256']:
        raise ValueError('UEFI checksum mismatch')
    if blob[32768:32772] != b'RKNS':
        raise ValueError('Expected Rockchip loader missing at LBA64')
    physical, logical = audit.partitions(image)
    shift = 32 * MIB
    if len(blob) >= shift:
        raise ValueError('Firmware exceeds reserved boot area')
    entries = []
    previous_end = shift
    for name, (start, end) in sorted(physical.items(), key=lambda kv: kv[1][0]):
        if start + shift < previous_end:
            raise ValueError('Overlapping source partitions')
        entries.append({'name': name, 'source_offset': start,
                        'target_offset': start + shift, 'bytes': end - start})
        previous_end = end + shift
    esp = ((previous_end + MIB - 1) // MIB) * MIB
    if any(p['name'] == 'EFI' for p in entries):
        raise ValueError('EFI partition name already exists')
    return {
        'status': 'LAYOUT_PLAN_ONLY; no output image or physical device written',
        'recovery': str(image.resolve()),
        'recovery_sha256_required_before_assembly': sources['googlebook']['raw_sha256'],
        'firmware_sha256': sources['uefi']['sha256'],
        'reserved_boot_bytes': shift,
        'firmware_copy': {'source_offset': 32768, 'target_offset': 32768,
                          'bytes': len(blob) - 32768},
        'partition_shift_bytes': shift,
        'partitions': entries,
        'efi_system_partition': {'name': 'EFI', 'offset': esp, 'bytes': 512 * MIB},
        'minimum_image_bytes': esp + 513 * MIB,
        'logical_partitions': {
            k: [dict(e, offset=e['offset'] + shift) for e in ext]
            for k, ext in logical.items()},
        'assembly_requirements': [
            'Validate full recovery SHA256 before copying any partition data.',
            'Create fresh primary and backup GPT; retain source partition type, unique GUID and attributes.',
            'Do not copy either donor GPT over the new layout.',
            'LP extent sectors remain relative to super; never add the shift inside LP metadata.',
            'Create FAT32 ESP with board firmware-compatible ARM64 boot application.',
            'Populate matching kernel, DTB, modules and adapted Android ramdisks before boot testing.',
            'Use isolated fresh userdata and metadata, never the running Android installation.',
            'Validate GPT CRCs, all copy bounds and per-partition hashes after assembly.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recovery', type=Path)
    parser.add_argument('firmware', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = plan(args.recovery, args.firmware, json.loads((ROOT / 'sources.json').read_text()))
    with args.output.open('x') as out:
        json.dump(result, out, indent=2)
        out.write('\n')
    print(f"Validated {len(result['partitions'])} partitions; plan: {args.output}")


if __name__ == '__main__':
    main()
