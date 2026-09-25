# v2rayA Levin: OpenWrt GUI installation validation

Tested on 2026-09-25 using official OpenWrt **24.10.4**, armsr/armv8,
kernel **6.6.110**, 256 MiB RAM and two virtual CPUs.

## Final published build

- `luci-app-v2raya-levin`: `26.268.0-r7.levin2`
- `v2raya-levin` and `v2raya-levin-core`: `2.5.7-recovery.2-r7.levin2`
- Service and core runtime version: `2.5.7-recovery.2`, matching check passed.
- Application source: `b3c6789330daf3c25f4aaa5464ad2385a7e3c35a`.
- Packaging source: `21396d9afbab14cc8edfc9a936ef69d5e7a782f8`.

## Installation result

**PASS:** downloaded and ran the public `add-levin-feed.sh` on the VM. The
script checked the pinned signing key and feed signature, added the HTTPS
source, and installed no application. Running it again left exactly one feed
entry and still did not create the application binary or configuration.

**PASS:** opened LuCI **System > Software**, updated lists, filtered `levin`,
and installed **luci-app-v2raya-levin**. The force-overwrite option stayed off.
The actual installation ran from the GUI, not an SSH install command.

The GUI downloaded the service, core and LuCI IPKs from the public GitHub feed,
plus absent `v2ray-geoip` and `v2ray-geosite` packages from official OpenWrt
24.10.4 feeds. Existing CA, LuCI and nftables kernel dependencies were satisfied.
All three fork packages showed **Installed**, with no Errors section in the
final installation dialog.

**PASS:** Services > **v2rayA Levin** initially showed **NOT RUNNING** with
Enable unchecked, preserving the clean-install disabled default. Checking
Enable and using **Save & Apply** changed the status to **RUNNING**. The API
confirmed a matching core and a fresh database.

**PASS:** rebooted the VM after the traffic tests. The source and packages
persisted, the service started automatically, and coreVersionValid remained
true. Runtime and package evidence is included in the local release bundle.

## Actual VPN traffic after the final GUI installation

All six `tests/openwrt/groups.py` scenarios passed on the installed final
packages, using real host-side VLESS servers and a generated subscription:

1. Preserve all group members and route through the fastest healthy server,
   despite a dead first entry, invalid UUID and blackhole entries.
2. Switch traffic to a later healthy member when the fastest server disappears.
3. Preserve group membership when every server is down.
4. Resume actual traffic when a server returns.
5. Preserve membership and traffic across a service restart.
6. Pass router-originated traffic through nftables TPROXY.

The earlier recovery.2 application build also passed 15 policy/recovery tests.
Those 15 were not rerun for this packaging-only release; the six traffic tests
above were rerun after installing the final packages through the GUI.

## Migration and fixes found during this task

An earlier GUI upgrade candidate replaced the generic-name recovery r6 packages
automatically. The existing test account and subscription survived, and the UCI
configuration SHA256 remained unchanged. This does not assert migration of every
possible production 2.2.x database.

GUI testing found and fixed two packaging problems: a missing final blank line
hid the last package in Software, and stopping an absent service produced false
installation errors. The first fix also went into upstream OpenWrt PR #66.
The final package guards stop operations and respects disabled configuration.

Previous IPKs remain available for clients with cached indices; the active
index advertises only the latest three packages. GitHub's raw-file cache can
delay a newly published index by approximately five minutes.

## Scope

The Cortex-A53 package architecture was accepted by a test-only generic ARM64
VM alias. Do not add that alias to a physical router. This validates userspace
installation and operation on OpenWrt 24.10.4, not Cudy TR3000 wireless hardware,
offload or flash upgrades. The build uses the standalone source packaging
pipeline, not a full OpenWrt SDK build. No production router was modified.
