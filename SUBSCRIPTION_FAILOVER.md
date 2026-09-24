# Subscription failover for the OpenWrt 2.2.7.3 package

This branch targets v2rayA 2.2.7.3 with Xray 25.1.30, the versions in the official OpenWrt 24.10.4 package feed. `luci-app-v2raya` opens and controls this service; the selection logic belongs to v2rayA itself.

This compatibility branch omits the old tag's GitHub Actions workflows, including upstream release and cross-repository dispatch jobs. Builds and validation use the reproducible local commands below; this branch does not publish upstream releases or claim hosted CI results.

## Behavior

Enable **Auto Select** in the subscription's **Modify** dialog. Set automatic subscription updates and their interval in **Setting**. Both the subscription's **Update** button and the scheduled update use the same selection code.

1. Download and parse the subscription without changing the current connection.
2. Check every candidate by sending an HTTP request through an isolated Xray process. Check two candidates concurrently to bound memory use on routers. Each request has a five-second timeout; core startup uses the configured core startup timeout.
3. Wait for every result, then choose the reachable server with the lowest measured latency. HTTP 2xx is success; redirects, errors and timeouts are failures. Equal latencies keep list order.
4. Save the updated subscription and all remapped connection references in a single database transaction. Restart the active core only when the chosen server changes.
5. If downloading fails, the new list is empty, or all candidates fail, keep the previous subscription and connection. Return an error to manual updates and log errors from scheduled updates. If applying a selection fails, restore the previous database state and restart the previous core; report restoration failures too.

The active subscription owns the `proxy` outbound. Other subscriptions cannot take it over. If nothing is selected, the first subscription with Auto Select enabled owns the initial selection. A manually selected standalone server is retained. Other outbounds retain their existing endpoints, including nodes removed from the refreshed subscription. Disabling Auto Select retains the original manual selection behavior. The V2Ray multi-server selection path is unchanged.

Subscription downloads retain their existing direct retry after a transport failure, with a timeout on both attempts. A shared HTTP client is never modified. Core shutdown now waits for the child process to finish, so a service restart cannot leave the previous core holding the proxy ports.

The probe URL is the existing `proxy` outbound's `probeURL`, defaulting to `https://gstatic.com/generate_204`. A reachable TCP port alone does not qualify a server. The probe listener binds to loopback; the generated outbound retains v2rayA's transparent-proxy bypass mark when transparent proxying is enabled. The active core is left running during probes. Concurrent API mutations are rejected as busy while the scheduler holds the shared configuration lock.

This implements failover **at subscription refresh**, not continuous monitoring between updates. External-plugin nodes are excluded from isolated probing. The interval still uses the existing whole-hour setting. Native protocols use the existing v2rayA configuration generator.

## Root cause in the base release

`SelectServersFromSubscription` calls `Connect` on each node in list order, then immediately breaks for Xray. `Connect` configures the core but does not prove that the remote node can pass traffic. The scheduler also invokes selection before downloading the subscription and again afterwards. With Xray, even the pre-update "disconnect" call takes the selection path. Manual refresh previously did no health-based selection at all.

The OpenWrt VM exposed an additional lifecycle failure: stopping the service cancelled the core's context but did not wait for the core to terminate. During an OpenWrt service restart, the new v2rayA process could find the old Xray still occupying the ports. Subsequent selection could update the saved identity without changing traffic. The fix explicitly terminates and reaps the managed core before shutdown or replacement, uses `exec.Cmd.Wait` to complete command cleanup, and waits for managed plugin processes too. This finding is why validation checks both the selected identity and the traffic path after restart.

## Reproduce the validation

Use Go 1.23.12 and the official 2.2.7.3 `web.tar.gz` extracted into `service/server/router/web`. Xray is a separate executable. From `service/`:

```sh
CGO_ENABLED=0 go build -trimpath -o /tmp/v2raya .
V2RAYA_V2RAY_BIN=/absolute/path/to/xray go test -race ./core/v2ray ./server/service .
go vet ./core/v2ray ./server/service ./server/router ./db/configure .
```

From the repository root, run the real application and loopback fixtures:

```sh
python3 tests/subscription_e2e.py --binary /tmp/v2raya \
  --xray /absolute/path/to/xray --output /tmp/v2raya-validation
```

The suite creates a disposable local account and subscription, starts the application and Xray, passes real HTTP traffic, exercises refreshes, blocks a candidate, changes server order, removes the active node, tests concurrent mutations, injects a core startup failure, and tests automatic refresh after application restart. `--keep-running` keeps a demo open after successful checks. The Go integration test separately fires the actual subscription ticker.

For real OpenWrt service, VLESS and nftables/TPROXY checks, follow [tests/OPENWRT_VM.md](tests/OPENWRT_VM.md). For installation and rollback on the router, follow [install/openwrt/README.md](install/openwrt/README.md).

## Build the router package

```sh
cd service
CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -trimpath \
  -ldflags '-s -w -X github.com/v2rayA/v2rayA/conf.Version=2.2.7.3-failover.1' \
  -o /tmp/v2raya-linux-arm64 .
cd ..
python3 install/openwrt/repack.py --base /path/to/official-v2raya.ipk \
  --sha256 CHECKSUM_FROM_CURRENT_OFFICIAL_PACKAGES_INDEX \
  --binary /tmp/v2raya-linux-arm64 \
  --output /tmp/v2raya_2.2.7.3-r2.failover1_aarch64_cortex-a53.ipk
```

The repacker retains the official package's init script, configuration file, upgrade retention list, conffiles, dependencies and installation/removal scripts. It replaces the executable and identifies the result as a local fork build. This is an unsigned custom package, not an official OpenWrt release.

The Linux ARM64 executable is static. The OpenWrt VM uses the same release and executable but a generic ARM64 board, not Cudy hardware. Physical LAN forwarding, Wi-Fi, provider-specific credentials and long-running operation on the Cudy TR3000 remain outside the VM test's coverage.
