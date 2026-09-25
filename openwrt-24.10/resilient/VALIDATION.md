# Resilient r10 validation

Validated on 2026-09-25 in a disposable local OpenWrt 24.10.4 armsr/armv8
VM, Linux 6.6.110, 256 MiB RAM. No production subscriptions were used.

Application source: `a0bad190fc7aad17b916c03fbc849a376b7f188f`.
Packaging source: `bd94f47861e3400e7a076a3fad2f7607ada366aa`.
Service/core: `2.5.7-resilient.4-r10.resilient1`.
LuCI: `26.268.0-r10.resilient1`.

## Application checks

The release branch combines the independently reviewed upstream changes for
marked dashboard probes, OpenWrt LAN bridges, per-subscription update modes and
automatic proxy-group membership. The subscription dialog contains one
four-value update-mode selector: Disabled, On service start, At an interval and
At an interval with fail-safe recovery. The retired per-subscription auto-select
switch is absent. Automatic server membership is a separate switch in each
proxy group's settings.

GUI lint, type checking, six-locale validation, 217 tests across 45 files and
the production build passed. The complete service Go suite passed apart from the
existing host-dependent resolver symlink test, which was explicitly skipped.
The matching core built for Linux ARM64 with Go 1.26. Its macOS-only process
ownership test cannot read the protected kernel socket table in this runner;
the Linux ARM64 core starts normally in the VM and reports a matching version.

The automatic-group VM harness passed these scenarios with real core processes:

1. A newly enabled automatic group changes the legacy `60s` probe default to
   `300s`.
2. Probes cover two subscriptions and standalone nodes in the complete Proxies
   catalog, with no more than two temporary probe cores at once.
3. Automatic mode owns the group member list and rejects manual edits; disabling
   it freezes the last members and restores manual editing.
4. Failed nodes are removed and recovered nodes return on the next pass.
5. An empty automatic group blocks only traffic assigned to that group. Direct
   and unrelated routes remain usable; retained transparent-proxy rules prevent
   a silent direct escape.
6. Database migration enables `PROXY` automatic membership once when any old
   subscription used auto-select, is idempotent and preserves later user edits.
7. A 200-node catalog completed in 2.90 seconds with a 101156 KiB peak RSS.

Subscription-policy tests cover legacy migration, all four modes, startup and
regular scheduling, bounded fail-safe retries, retained nodes after failed or
empty downloads, manual-stop behavior and non-overlapping work.

## Package and feed checks

The package index is signed with the existing Resilient key
`9f02e659f24749fa`; verification succeeded before installation. Exact package
dependencies require the matching service/core pair.

A signed-feed r9-to-r10 upgrade on the VM passed:

- `opkg update` accepted the index signature and listed all three r10 upgrades.
- Installing only `luci-app-v2raya-resilient` upgraded the exact service/core
  dependencies.
- The existing database stayed byte-for-byte identical during package upgrade,
  SHA256 `e60f1df93992a40dc6d0450a42bdf35ab743635fdc41da3285be9921b9e125aa`.
- The account and saved subscription remained available after startup.
- LuCI System > Software displayed all three packages as Installed at r10.
- The running API reported service/core `2.5.7-resilient.4` and
  `coreVersionValid=true`.

A clean signed-feed install also passed after removing the three packages and
all disposable test configuration. Installing the LuCI package pulled the
service and core, created a disabled UCI configuration, left the service stopped
until enabled, and then started with `hasAccounts=false`, matching versions and
`coreVersionValid=true`. The preserved test database and UCI file were restored
after the clean-install check.

The r9 source and feed remain available in the
`release/resilient-openwrt-24.10-r9` and `openwrt-feed-r9` branches. The normal
feed URL now provides r10 so existing installations can upgrade without adding
another source.

## Scope

Blocking assertions cover router-originated IPv4 TCP with nftables TPROXY. This
is not a system-wide kill switch for service/core crashes, manual shutdown, TUN
or custom hooks. IPv6/UDP escape paths, physical Cudy TR3000 hardware,
wireless/offload and a full OpenWrt SDK build are not validated. The VM uses a
test-only Cortex-A53 package alias on generic ARM64; do not add architecture
aliases on production routers.
