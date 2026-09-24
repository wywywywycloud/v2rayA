# Validation report

Validated on September 25, 2026, using the OpenWrt 24.10.4 release and a local Apple Silicon host.

## Outcome

The official v2rayA 2.2.7.3-r1 package reproduced the reported defect: automatic subscription refresh selected an unreachable first server and traffic failed while later servers remained available.

The final fork passed the complete OpenWrt VM suite with **256 MiB RAM**, including multiple consecutive failures while all six subscription entries stayed present. Every successful switch was checked against both the saved server identity and real traffic through a VLESS server. The functional scenarios also ran with 512 MiB RAM. Native application tests, real scheduler tests and targeted race checks passed.

## Environment

| Component | Version or configuration |
| --- | --- |
| OpenWrt | 24.10.4, r28959-29397011cc |
| Guest kernel | Linux 6.6.110, ARM64 |
| VM board | QEMU `virt`, `armsr/armv8`, two vCPUs |
| Final full-suite memory | 256 MiB, no swap |
| Official baseline package | v2raya 2.2.7.3-r1 |
| Candidate package | v2raya 2.2.7.3-r2.failover1 |
| Guest Xray | Official OpenWrt xray-core 25.1.30-r1 |
| Host Xray fixtures | Xray 25.1.30, macOS ARM64 |
| LuCI package installed | luci-app-v2raya 26.259.57575~0aa55c7 |
| Compiler | Go 1.23.12, static Linux ARM64 build |
| Production service mode | Normal root service through the official OpenWrt init script; Lite disabled |

## Traffic tests

The six-entry subscription contained a dead first endpoint, wrong VLESS credentials, an authenticated blackhole, and three working VLESS endpoints named `slow`, `backup` and `fast`. Each working endpoint used a separate real Xray server and returned a distinct marker through a deterministic HTTP backend. Tests did not use a provider subscription or real user credentials.

| Scenario | Observed result |
| --- | --- |
| Initial manual connection | Real traffic passed through `slow` |
| Refresh with dead first node | Selected `fast`, the sixth entry; traffic returned `fast` |
| Kill `fast`, retain all entries | Selected `backup`; traffic returned `backup` |
| Kill `backup`, retain all entries | Selected `slow`; traffic returned `slow` |
| Kill all working nodes | Refresh failed, previous state retained, traffic failed as expected |
| Restore a later node | Selected restored `fast`, with failed entries still present |
| Reorder nodes while probes run | Active traffic kept working; final identity still matched `fast` |
| Concurrent mutation | Rejected while refresh was running |
| Subscription HTTP 503 / empty body | Previous subscription and working connection retained |
| nftables/TPROXY | Unproxied HTTP requests originating on the guest followed `fast` to `backup` after failure |
| OpenWrt service restart | Startup refresh selected recovered `fast`; HTTP proxy and TPROXY traffic both returned `fast` |
| Cleanup | No temporary probe configuration files; exactly one managed Xray remained |

The full 256 MiB run produced 12 passing records including environment and cleanup checks. During the sampled two-probe interval, `MemAvailable` was 122,844 KiB (about 120 MiB). After completion it was 128,444 KiB. These are snapshots, not a measured peak or a long-duration memory benchmark. Kernel logs contained no out-of-memory kills during the run. Xray's large virtual address-space value in `ps` is not its resident memory usage.

## Findings used to refine the fork

1. **Selection was positional.** The baseline configured the first Xray node without checking whether it passed traffic. Selection now waits for every supported candidate's actual HTTP probe and uses the fastest successful result.
2. **Subscription download retry could lose its timeout.** The initial code copied an HTTP client without using the copy, and the shared helper retried with an unbounded default client. Both download attempts now have a timeout, and shared clients remain unchanged.
3. **Service restart could leave the old core on its ports.** The VM caught a case where the saved selection changed but traffic still used the previous core. Context cancellation alone did not synchronously terminate the child. Shutdown now terminates and reaps the managed core before returning and completes `exec.Cmd.Wait` cleanup. The repeated VM restart test passed after this change.

Fixture issues were corrected separately: the guest HTTP proxy needed port sharing for the host-forwarded test; `touch` is deliberately busy during a manual update in this release; and BusyBox process matching needed the full Xray command line. These fixture corrections were not counted as product fixes.

## Other validation

- Native application suite: nine scenarios passed with the real final application and Xray, including injected core-start failure, database rollback and restoration of the previous traffic path.
- `go test -race ./core/v2ray ./server/service .`: passed, including real Xray HTTP status/timeout checks, connection ownership, reference remapping, failed downloads and synchronous process shutdown.
- `go vet ./core/v2ray ./server/service ./server/router ./db/configure .`: passed.
- The actual subscription ticker was fired by the integration test inside OpenWrt with the real guest Xray. This uses a shortened test-only tick, not a claim that a full one-hour production interval elapsed.
- Final IPK contents were checked against the checksum-verified official package. The UCI file, init script, upgrade retention list, conffiles, installation/removal hooks, dependencies and executable mode were preserved. The installed guest executable's SHA-256 matched the built executable.
- `git diff --check`: passed.

The whole-repository test and vet commands are **not green on the pristine upstream tag on this Mac**. Baseline comparison reproduced the existing `common` test import cycle, platform-specific pcap code errors, legacy external-download/hardcoded-path tests, and existing vet findings. These are outside the changed paths; the targeted results above must not be read as a passing whole-repository suite.

## Scope and limits

Failover happens at subscription refresh, including scheduled refresh. There is no continuous monitor between refreshes. Failed downloads or a wholly unavailable subscription preserve saved state and return an error; preserved state is not a promise of working traffic.

The VM validates the same OpenWrt release and application binary on a generic ARM64 board. It does not validate the Cudy TR3000's SoC, Wi-Fi, flash layout, physical LAN forwarding, real provider credentials, TLS/REALITY variants, external plugins or long-running production load. TPROXY was checked with traffic originating on the guest, not a separate LAN client. External-plugin nodes are excluded from isolated selection probes.

Reproduction instructions: [OPENWRT_VM.md](OPENWRT_VM.md). Installation and rollback: [OpenWrt README](../install/openwrt/README.md).
