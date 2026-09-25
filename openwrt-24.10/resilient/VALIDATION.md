# Resilient r9 validation

Validated on 2026-09-25 in a disposable local OpenWrt 24.10.4 armsr/armv8
VM, Linux 6.6.110, 256 MiB RAM. No production subscriptions were used.

Application source: `4e8fc7d466e75d7a0287e709885f7a4b6643ec68`.
Packaging source: `dbd0e1808476eacc3dff7fd2c65c5e0f0e4179bf`.
Service/core: `2.5.7-resilient.3-r9.resilient1`.
LuCI: `26.268.0-r9.resilient1`.

## Application checks

All 12 scenarios in `tests/openwrt/automation.py` passed using actual VLESS
connections, synthetic subscriptions and an independent direct-traffic trap:

1. The direct trap is reachable before interception, validating the fixture.
2. Automatic membership checks the entire catalog (two subscriptions plus
   standalone nodes), rejects dead/wrong-UUID/blackhole nodes and works while
   the main core is stopped.
3. Dashboard TCP and HTTP latency checks retain interception.
4. Losing the fastest node falls back to a healthy later subscription.
5. An empty automatic group blocks assigned traffic, retains TPROXY and
   produces no direct escapes during reloads or dashboard latency checks.
6. Recovery from the retained catalog repopulates the empty group.
7. Disabling automatic membership preserves members and suppresses scans.
8. New timers persist, old switches are absent and zero failure interval
   is rejected.
9. Regular interval zero still permits bounded one-minute failure retries.
10. A retry discovers a new working node; retries stop after recovery.
11. Manual stop remains stopped while automation is enabled.
12. Explicitly starting an empty automatic group succeeds and blocks traffic.

The minute-retry tests use real elapsed time. Continuous IPv4 TCP traffic
checks reload windows against a separate direct-escape endpoint. Earlier
candidates failed this test because dashboard latency checks removed firewall
rules or stopped the core when the group was empty; the published source
fixes both paths.

GUI lint, typecheck, six-locale validation, 217 tests and production build
passed. The live dialogs were checked at phone width in light/dark themes.
Primary explanations use 16px body text; details use muted 12px text.
Service/core build and vet passed; targeted database/service/controller race
tests passed. The full macOS suite has the existing Linux-only resolver test
failure; the kernel/resolver suite passed as root in this VM, with explicit
environment-dependent skips. Real-core HTTP 204/302/503, closed-port and
blackhole probe tests passed on Linux.

## Package checks

The package index is signed using the existing Resilient key
`9f02e659f24749fa`. Exact service/core dependencies prevent mismatched pairs.
The three package payloads were built from the source revisions above.
The prior r8 signed-feed installation through LuCI is already verified;
the r8-to-r9 public-feed upgrade is being verified before release handoff.

## Scope

Blocking assertions cover router-originated IPv4 TCP with nftables TPROXY.
This is not a system-wide kill switch for service/core crashes, manual
shutdown, TUN or custom hooks. IPv6/UDP escape paths, physical Cudy TR3000
hardware, wireless/offload and a full OpenWrt SDK build are not validated.
The VM uses a test-only Cortex-A53 package alias on generic ARM64; do not
add architecture aliases on production routers.
