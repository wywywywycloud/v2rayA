# Signed-feed validation

Validated on 2026-09-25. Application commit: `c39977ab7061c6b87b6b8c025f733d141fb3c47e`.

## Environment

Official OpenWrt 24.10.4 ARM64 guest, kernel 6.6.110, 256 MiB RAM, two virtual CPUs. The disposable root filesystem was expanded offline to 512 MiB to accommodate the full package set without bypassing opkg space checks. The generic ARM64 guest used a test-only Cortex-A53 package architecture alias; official dependencies and kernel modules came from its own matching feeds. This alias is not part of the router installer.

## Results

- **Clean installation: PASS.** v2rayA, Xray and LuCI were absent before installing from the public HTTPS feed. The signed bundle installed the fork, Xray 25.1.30-r1, geo assets, LuCI and its v2rayA service page. Installed application SHA-256 matched `9033ed34a0ddf55ab0acb26d3a692711d55221c2e13944114222be67c070b521`; API reported `2.2.7.3-failover.3`.
- **GUI: PASS.** Browser verification reached LuCI Services → v2rayA, with the service running, enabled, and the application link present. The application binary contains the already-tested fork GUI.
- **Signature rejection: PASS.** A modified package index served with the original signature was rejected by guest opkg and was not retained as an available index.
- **Repeated installation: PASS.** One custom feed entry remained; official feed configuration was unchanged. Login, subscription remarks, scheduling settings and a manually stopped connection were retained.
- **Official-to-fork upgrade: PASS.** After reinstalling the official 2.2.7.3 package, the public installer upgraded back to failover.3 and retained the checked settings. Backups were created.
- **VPN regression suite: 12 PASS.** Real VLESS traffic; dead first node, invalid credentials and blackhole skipping; two consecutive failovers; all-dead preservation; later-node recovery; reordering and concurrent changes; failed/empty subscriptions; router-originated nftables/TPROXY traffic; service restart; probe cleanup and memory checks. `curl` was installed separately as a test tool after clean installation verification.
- **Packaging regression: PASS.** The first bundle exposed missing parent directory entries in its data archive. The corrected `.feed1` bundle includes them, a unit test checks directory ordering and permissions, and the installer checks the installed bundle file. Clean installation was repeated successfully. The defective bundle was withdrawn.

The final bundle is `v2raya-fork_2.2.7.3-r4.failover3.feed1_aarch64_cortex-a53.ipk`. Its application payload is unchanged from the previously tested failover.3 build. Earlier monitoring and selection-policy tests remain documented in the application validation report; they are not counted as new feed tests.

## Limits

The physical Cudy TR3000, physical LAN forwarding, provider credentials and TLS/REALITY endpoints were not tested. The VM validates package installation and real synthetic VLESS traffic on the matching OpenWrt release, not every hardware or provider configuration. Actual router storage and official-feed availability must still satisfy opkg. The prepared application VM archive predates this feed and remains a separate reproducible application-test fixture.
