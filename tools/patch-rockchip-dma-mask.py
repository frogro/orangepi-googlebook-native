#!/usr/bin/env python3
"""Port the Pro Android display DMA fix, before component registration."""
import sys
from pathlib import Path
p = Path(sys.argv[1]) / 'drivers/gpu/drm/rockchip/rockchip_drm_drv.c'
s = p.read_text()
start = s.index('static int rockchip_drm_platform_probe(')
end = s.index('static void rockchip_drm_platform_remove(', start)
probe = s[start:end]
fix = """	/* Android/Mesa buffers may reside above the default 32-bit DMA mask.
	 * Set the display master's mask before component binding can map buffers.
	 */
	ret = dma_coerce_mask_and_coherent(dev, DMA_BIT_MASK(64));
	if (ret)
		return ret;

"""
anchor = '\tmatch = rockchip_drm_match_add(dev);'
if fix in probe:
    print('Rockchip display DMA mask already patched')
    sys.exit(0)
if 'dma_coerce_mask_and_coherent' in probe or probe.count(anchor) != 1:
    sys.exit('Unexpected DRM probe layout; review instead of patching blindly')
p.write_text(s[:start] + probe.replace(anchor, fix + anchor) + s[end:])
print('Applied Rockchip display DMA mask fix before component registration')
