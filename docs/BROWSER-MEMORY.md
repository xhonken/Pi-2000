# Browser memory protection

Each streamed Browser session includes Chromium, a virtual display, audio and video streaming processes. The configured memory ceiling is 1536 MiB for the whole group, with a 1024 MiB memory.high threshold and up to 256 MiB swap. The session service also has its own aggregate resource limits.

Before starting a new session, Pi-2000Web requires at least 2048 MiB of MemAvailable (1536 MiB session budget plus 512 MiB reserve). This conservative admission check uses reclaimable memory, not MemFree. It does not prevent another application from allocating memory later. Reconnecting to an existing session bypasses the new-session check.

A five-second watchdog remains as a fallback. It records memory, disk, process-crash and idle-timeout stops separately. Browser polls its own status, warns at 1200 MiB and removes a stopped stream so the user can select Reconnect. It does not automatically restart a process repeatedly after a memory failure. Saved browser profiles are retained; unsaved web-page state is not guaranteed after a crash.

## Enable the hard limit on Raspberry Pi OS

Check the live kernel, not just the configuration file:

```sh
cat /sys/fs/cgroup/cgroup.controllers
```

The result must include `memory`. If it is absent, the configured cgroup memory limits are not enforced by the kernel. On current Raspberry Pi kernels, add `cgroup_enable=memory` at the end of the single line in `/boot/firmware/cmdline.txt`, keeping all existing root/boot arguments. Back up the file before editing. Schedule a reboot after saving work and ending live SSH jobs.

Raspberry Pi's device tree can prepend `cgroup_disable=memory`; a later `cgroup_enable=memory` overrides it. Use the v2 controller files to verify support rather than the legacy `/proc/cgroups` list. See the [Raspberry Pi kernel maintainer discussion](https://github.com/raspberrypi/linux/issues/6980).

## Verify after reboot

```sh
cat /sys/fs/cgroup/cgroup.controllers
sudo ./scripts/doctor.sh
```

Open Browser and inspect the actual group (replace USER_ID with the numeric account ID):

```sh
sudo cat /sys/fs/cgroup/system.slice/win2k-sessions.service/browser-USER_ID/memory.max
sudo cat /sys/fs/cgroup/system.slice/win2k-sessions.service/browser-USER_ID/memory.high
sudo cat /sys/fs/cgroup/system.slice/win2k-sessions.service/browser-USER_ID/memory.events
```

Expected max: `1610612736`; high: `1073741824`. The authenticated `/api/browser/status` endpoint also reports `memory_hard_limit` for the current account's running Browser. An `oom_kill` increase records a kernel memory-limit kill; a crashed process without that evidence is reported as an unexpected stop.

A cgroup configuration written to disk is not proof of enforcement. Verify after reboot, and perform an intentional memory-limit stress test only in an isolated test group/installation. Do not deliberately exhaust the live host's RAM to test a fallback watchdog.
