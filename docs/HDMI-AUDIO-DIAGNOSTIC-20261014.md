# HDMI input audio diagnostic kernel

This test branch starts at ece02db197b0ce1c8b4667d98ccbcd579307872b,
the kernel used in the Android TV HDMI recovery image. It changes logging
only, plus the release suffix to `-opi5plus-tv-hdmi-diag1`. It is not a
confirmed audio fix and must not replace the published baseline.

Two consecutive cable reconnections were observed: the first restored video
and audible audio; the second restored video but ALSA capture remained RUNNING
with hw_ptr zero. I2S CLR was 0x2 in the failed state versus zero after a fresh
boot. Restarting the app/audio service and rebinding drivers did not restore
audio. A reboot restored DMA progress. These observations do not establish
whether the missing step is receiver packet/clock recovery or I2S reset.

`0005-hdmirx-audio-diagnostics.patch` adds AUDDIAG snapshots on link changes,
shutdown, and hw_params before its fallback sample rate. While the audio worker
runs, a snapshot is emitted at most once per five seconds. Snapshots record
measured sample rate, configured sample rate, link/stream/worker flags, audio
clock rate, global enable, audio processing configuration, FIFO status, and
TMDS clock measurement. The existing fs=48000 log can be a fallback and is not
proof of valid incoming audio packets.

Diagnostics are enabled by default only in this test build. They can be disabled
with `echo N > /sys/module/synopsys_hdmirx/parameters/audio_diag`. Logging can
influence timing; disappearance of the failure alone does not prove a fix.
No new register writes, resets, lock changes, or recovery behavior are introduced.

## Hardware test

Use the matching Image, DTB and modules from this build. Save dmesg from before
the first disconnect; sample /proc/asound/card2/pcm0c/sub0/status, verifying the
card identity first. Feed stereo PCM HDMI audio continuously, disconnect for
15 seconds, reconnect, and confirm video and audible audio. Repeat separately
and compare measured fs/FIFO/enable states with DMA progress. Preserve the
failed state before restarting anything. Five successful cycles, including a
longer interruption, are required before calling a later correction reliable.

## Validation

Patch application is checked against the exact preceding HDMI receiver source.
The modified receiver object is cross-compiled locally; the complete matching
kernel/module bundle is built by GitHub Actions. Hardware validation is pending.
