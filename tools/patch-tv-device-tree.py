#!/usr/bin/env python3
from pathlib import Path
import sys, shutil
src=Path(sys.argv[1]); lab=Path(__file__).resolve().parents[1]
d=src/'arch/arm64/boot/dts/rockchip'
p=d/'rk3588-orangepi-5-plus.dts'
s=p.read_text()
for label in ('hdmi_receiver:', 'i2s7_8ch:'):
    if not any(label in x.read_text() for x in d.glob('rk3588*.dtsi')):
        raise SystemExit('Missing expected DT label: '+label)
shutil.copyfile(lab/'config/opi5plus-tv-hardware.dtsi',d/'opi5plus-tv-hardware.dtsi')
include='#include "opi5plus-tv-hardware.dtsi"'
if include not in s: p.write_text(s+'\n'+include+'\n')
