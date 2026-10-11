#!/usr/bin/env python3
"""Create and verify an isolated disk base. Not a bootable Googlebook port yet."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import tempfile
import uuid
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('layout', ROOT / 'tools/plan-native-disk.py')
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)
CHUNK = 4 * 1024 * 1024


def digest_range(file, start, size):
    file.seek(start)
    digest = hashlib.sha256()
    while size:
        data = file.read(min(size, CHUNK))
        if not data:
            raise ValueError('Unexpected end of image')
        digest.update(data)
        size -= len(data)
    return digest.hexdigest()


def copy_range(source, output, start, target, size):
    source.seek(start)
    output.seek(target)
    digest = hashlib.sha256()
    while size:
        data = source.read(min(size, CHUNK))
        if not data:
            raise ValueError('Unexpected end of source image')
        digest.update(data)
        # New sparse output only; skipping zero blocks is safe here.
        if any(data):
            output.write(data)
        else:
            output.seek(len(data), os.SEEK_CUR)
        size -= len(data)
    return digest.hexdigest()


def make_header(original, entries, current, backup, first, last, table_lba):
    result = bytearray(original)
    struct.pack_into('<QQQQ', result, 24, current, backup, first, last)
    struct.pack_into('<Q', result, 72, table_lba)
    struct.pack_into('<I', result, 88, zlib.crc32(entries))
    struct.pack_into('<I', result, 16, 0)
    struct.pack_into('<I', result, 16, zlib.crc32(result[:struct.unpack_from('<I', result, 12)[0]]))
    return result


def assemble(recovery, firmware, target):
    sources = json.loads((ROOT / 'sources.json').read_text())
    for path in (recovery, firmware):
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError('Input must be a regular image file')
    plan = layout.plan(recovery, firmware, sources)
    with recovery.open('rb') as source:
        print('Verifying full recovery SHA256 before assembly', flush=True)
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
        if digest != sources['googlebook']['raw_sha256']:
            raise ValueError('Recovery checksum mismatch')
        source.seek(512)
        header = source.read(512)
        table_lba, count, entry_size = struct.unpack_from('<QII', header, 72)
        table_size = count * entry_size
        table_sectors = (table_size + 511) // 512
        # Keep GPT table clear of the Rockchip loader at LBA64.
        if 2 + table_sectors > 64:
            raise ValueError('GPT table overlaps Rockchip loader')
        source.seek(table_lba * 512)
        entries = bytearray(source.read(table_size))
        free = []
        shift_sectors = plan['partition_shift_bytes'] // 512
        for idx in range(count):
            pos = idx * entry_size
            if not any(entries[pos:pos + 16]):
                free.append(pos)
                continue
            start, end = struct.unpack_from('<QQ', entries, pos + 32)
            struct.pack_into('<QQ', entries, pos + 32, start + shift_sectors, end + shift_sectors)
        if not free:
            raise ValueError('No free GPT entry for ESP')
        esp = plan['efi_system_partition']
        pos = free[0]
        entries[pos:pos + entry_size] = bytes(entry_size)
        entries[pos:pos + 16] = uuid.UUID('c12a7328-f81f-11d2-ba4b-00a0c93ec93b').bytes_le
        entries[pos + 16:pos + 32] = uuid.uuid4().bytes_le
        struct.pack_into('<QQ', entries, pos + 32, esp['offset'] // 512,
                         (esp['offset'] + esp['bytes']) // 512 - 1)
        entries[pos + 56:pos + 62] = 'EFI'.encode('utf-16le')
        disk_size = plan['minimum_image_bytes']
        last_lba = disk_size // 512 - 1
        first_usable = 2 + table_sectors
        last_usable = last_lba - table_sectors - 1
        primary = make_header(header, entries, 1, last_lba, first_usable, last_usable, 2)
        backup = make_header(header, entries, last_lba, 1, first_usable, last_usable,
                             last_lba - table_sectors)
        # Exclusive creation: existing files, symlinks and block devices cannot be overwritten.
        with target.open('xb+') as out:
            out.truncate(disk_size)
            mbr = bytearray(512)
            mbr[446 + 4] = 0xee
            struct.pack_into('<II', mbr, 446 + 8, 1, min(last_lba, 0xffffffff))
            mbr[510:512] = b'\x55\xaa'
            out.write(mbr)
            out.seek(512); out.write(primary)
            out.seek(1024); out.write(entries)
            out.seek((last_lba - table_sectors) * 512); out.write(entries)
            out.seek(last_lba * 512); out.write(backup)
            with firmware.open('rb') as boot:
                region = plan['firmware_copy']
                copy_range(boot, out, region['source_offset'], region['target_offset'], region['bytes'])
            hashes = {}
            for part in plan['partitions']:
                print('Copying ' + part['name'], flush=True)
                hashes[part['name']] = copy_range(source, out, part['source_offset'],
                                                   part['target_offset'], part['bytes'])
            with tempfile.TemporaryDirectory(prefix='native-esp-', dir=target.parent) as tmp:
                fat = Path(tmp) / 'esp.img'
                with fat.open('xb') as f:
                    f.truncate(esp['bytes'])
                subprocess.run(['mkfs.vfat', '-F', '32', '-n', 'GBNATIVE', str(fat)], check=True)
                with fat.open('rb') as f:
                    hashes['EFI'] = copy_range(f, out, 0, esp['offset'], esp['bytes'])
            out.flush(); os.fsync(out.fileno())
            for part in plan['partitions'] + [dict(name='EFI', target_offset=esp['offset'], bytes=esp['bytes'])]:
                print('Verifying ' + part['name'], flush=True)
                if digest_range(out, part['target_offset'], part['bytes']) != hashes[part['name']]:
                    raise ValueError('Partition copy mismatch: ' + part['name'])
        # Re-read GPT and Android LP metadata with independent bounds/checksum checks.
        physical, logical = layout.audit.partitions(target)
        for part in plan['partitions']:
            if physical[part['name']] != (part['target_offset'], part['target_offset'] + part['bytes']):
                raise ValueError('GPT layout mismatch')
        if logical != plan['logical_partitions']:
            raise ValueError('Logical partition offsets mismatch')
        result = dict(plan, partition_sha256=hashes,
                      status='VERIFIED_DISK_BASE_ONLY; ESP has no boot application; Android adaptations pending')
        report = target.with_suffix(target.suffix + '.json')
        with report.open('x') as f:
            json.dump(result, f, indent=2)
            f.write('\n')
        print('Verified disk base: ' + str(target), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('recovery', type=Path)
    p.add_argument('firmware', type=Path)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    if args.output.exists() or args.output.is_symlink():
        p.error('Output must not already exist')
    if args.output.with_suffix(args.output.suffix + '.json').exists():
        p.error('Output report must not already exist')
    assemble(args.recovery, args.firmware, args.output)


if __name__ == '__main__':
    main()
