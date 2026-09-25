# Forwarded LAN traffic: PR #2057 follow-up

Observed on 2026-09-25, application commit `58af604a`, using an isolated
OpenWrt 24.10.5 ARM64 VM (Linux 6.6.119, two virtual CPUs, 256 MiB RAM).
The base image already had the signed Resilient feed dependencies installed;
the test replaced the service/core with this PR's binaries and used a fresh
configuration directory. The test boots with QEMU's temporary snapshot mode,
so it leaves the base disk unchanged.

## Topology and assertion

```text
LAN client namespace: 192.0.2.2, default route via 192.0.2.1
  client-eth <-> lan-client (veth pair)
                  |
router namespace: br-lan (192.0.2.1 and QEMU DHCP 10.0.2.15)
                  |
              v2rayA TPROXY -> matching core -> real VLESS fixture
```

The client has its own network namespace and routing table. Its TCP request
is destined for `198.18.0.1:80`, not a router address. The namespace separation
means this is an incoming LAN flow through `br-lan`, not a request originated
by the router. No HTTP/SOCKS proxy option is passed to curl.

An independent prerouting DNAT trap returns `DIRECT-ESCAPE` only if the flow
has not acquired the TPROXY mark. The VLESS server returns `LAN-VPN`. Both
endpoints run locally on the host and the test needs no public VPN account.
The trap is restricted to the test client's source address and test destination.

Results of the final complete run:

1. With the core stopped, the client received `DIRECT-ESCAPE`.
2. With the new OpenWrt default, an initial request and five subsequent
   requests received `LAN-VPN`. The direct endpoint's request count did not
   increase during those five requests.
3. `nft monitor trace` showed the same SYN entering with `iif "br-lan"`,
   traversing `tp_pre -> tp_rule -> tp_mark`, receiving mark `0x40`, then
   matching `tproxy ip to 127.0.0.1:52345`. The DNAT escape rule was skipped.
4. Applying the historical `docker*,veth*,wg*,ppp*,br-*` value while the
   service stayed up reproduced the direct escape. A service restart is
   intentionally avoided here, because startup migrates that exact value.
5. An explicit custom `br-lan,wg*` exclusion also produced `DIRECT-ESCAPE`.
6. Restoring `docker*,veth*,wg*,ppp*` restored `LAN-VPN`.

The final counters were three direct fixture requests (the three expected
control cases) and seven VLESS fixture requests. See [result.json](bridge-review/result.json),
[the first forwarded SYN trace](bridge-review/first-forwarded-syn.trace) and
[the active v2rayA rules](bridge-review/working-rules.nft).

This validates nftables TPROXY with forwarded IPv4 TCP. It does not validate
physical hardware, Wi-Fi, hardware offload, IPv6, UDP or legacy iptables runtime.

## Reproduce

Use macOS ARM64 with QEMU/HVF, Python 3 and a host-compatible Xray binary for
the VLESS fixture. The prepared OpenWrt 24.10.5 ARM64 ext4 image must have
`br-lan` configured for DHCP (QEMU's default user network), a disposable root
SSH key installed, nftables TPROXY support, curl, and geodata in
`/usr/share/v2ray`. The runner installs `ip-full` and the release-native
`kmod-veth` from the guest's configured official feeds. Ports 22522, 22517 and
22580 must be free. Never use a physical-router image as a writable live disk.

Build the service and core from the reviewed application branch with the
same version stamp. The GUI must be built and copied into
`service/server/router/web` before building the service. Then run:

```sh
python3 tests/openwrt/lan_bridge_forwarding.py \
  --output /tmp/bridge-review-results \
  --service /path/to/linux-arm64-v2raya \
  --core /path/to/linux-arm64-v2raya_core \
  --image /path/to/prepared-openwrt-24.10.5-rootfs.img \
  --kernel /path/to/openwrt-24.10.5-armsr-armv8-generic-kernel.bin \
  --ssh-key /path/to/disposable-vm-key \
  --xray /path/to/host-xray \
  --qemu /opt/homebrew/bin/qemu-system-aarch64
```

`--keep-running` leaves the VM available for a GUI check until interrupted;
the runner closes its QEMU and fixture processes in `finally`.

## Build and GUI checks

- Go 1.26.0: service/core `go build ./...` and `go vet ./...` passed.
- Service `go test ./...` encountered the pre-existing macOS failure in
  `TestBackupAndRestoreResolvSymlink`. The complete suite with only that
  Linux-only test skipped passed. The configure and iptables tests also passed.
- Node 24.19.0: GUI lint, typecheck, i18n-check, all 43 test files / 213 tests,
  and production build passed.
- The new help and placeholder were inspected in the VM's embedded GUI,
  including the expanded help text at 390x844 in light and dark themes.
  The six locale files now omit `br-*` from the example and explain that
  explicitly adding it excludes OpenWrt's LAN bridges.

Binary SHA-256 values:

```text
8937064fae491345bc17340cc343af2e9d85d2c1f1d0b69d12d0d2d5a2c17dfe  v2raya
5d008474f8699e10d031baa25517fabf067ffb867939c269639b856a8efbad99  v2raya_core
```

## Legacy flag scope

The current service still registers `legacyTproxy.AddIPWhitelist` through
`SetWatcher(Tproxy) -> NewLocalIPWatcher -> SyncIP`. That callback was retained;
only the obsolete `TproxyNotSkipBr` variable and its insertion-offset branch
were removed. The unchanged default insertion offset is seven.

The SDK recipe in v2raya-openwrt still pins v2.2.7.4, where the old
`core/iptables.TproxyNotSkipBr` package path exists and the flag actively
controls bridge exclusions. Removing it would regress that historical recipe.
PR #66 documents this distinction; its current-source pipeline does not pass
the old flag and should build sources containing #2057.
