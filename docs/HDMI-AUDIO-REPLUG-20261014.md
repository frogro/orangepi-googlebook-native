# HDMI input audio recovery candidate

Hardware evidence on Android TV, kernel 6.18.55-opi5plus-tv-hw1:
short unplug was reported to recover. Longer unplug caused camera configuration
failure followed by recovered video and no capture DMA progress. At inspection,
the ThinkPad default sink and both playback streams were HDMI. Reopening PCM,
restarting the app, rebinding receiver/I2S/sound card and renewing EDID did not
restore capture. A full reboot restored progressing DMA and user-confirmed sound.

Candidate 0004 separates requested capture from running audio work, drains work
before link reset, replays audio setup after signal lock/datapath reset, rejects
clock setup failures and avoids FIFO clock adjustment with invalid ACR. Control
paths are serialized with audio_lock; the worker does not acquire that lock.
Removal disarms work before codec removal. No HDCP/DRM changes are involved.

Reference: CERALIVE/rk3588-kernel-patches, patch 0047-hdmirx-audio-worker-lifetime.patch
and patch 0048-hdmirx-audio-channel-routing.patch. This is a narrow adaptation to
our older driver, not an import of the full v7.2 patch stack.
https://github.com/CERALIVE/rk3588-kernel-patches

Local ARM64 object compilation against prepared 6.18.55 headers passed.
Full kernel compilation and hardware recovery verification are still pending.
Do not describe this candidate as a verified fix or ship it as the stable image.
Required tests: boot with/without HDMI source; start/stop app; 3 long unplug/replug
cycles; DMA progression, audible output and source routing; no kernel oops or
stuck work; stable capture after recovery. The camera no-signal UI still needs
separate handling; configuration failure while disconnected is not an audio fix.
