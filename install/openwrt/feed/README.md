# Install from the signed opkg feed

This feed targets **OpenWrt 24.10.4** and **aarch64_cortex-a53**, the package architecture used by the Cudy TR3000. It installs the tested `2.2.7.3-r4.failover3` application. The executable already contains the fork's GUI, including Server Selection and Monitoring.

## Install on the router

Run these commands in an SSH session on the router as root. The installer verifies the repository key and index, adds one custom feed without replacing the official feeds, installs dependencies, and enables/restarts v2rayA. Existing v2rayA settings are retained. A settings backup is created in `/tmp` when an existing configuration is present; copy that backup to your computer before rebooting.

```sh
wget -O /tmp/install-v2raya-fork.sh 'https://raw.githubusercontent.com/wywywywycloud/v2rayA/openwrt-feed/install-feed.sh'
printf '%s  %s\n' '99222fdddaaa48474bac8521b9435fe1ec79c09469bfa53fc2063e3039403981' '/tmp/install-v2raya-fork.sh' | sha256sum -c - && sh /tmp/install-v2raya-fork.sh
```

The installer requires the matching OpenWrt release and package architecture. It never uses `--force-space`, `--force-depends`, or disables signature verification. Check `df -h /overlay /` before installation; a fresh installation needs space for the application, Xray, geodata and LuCI. Dependencies already installed on the router are reused. A generic ARM64 VM's test-only architecture alias must not be copied to the physical router.

Open **LuCI → Services → v2rayA**, or `http://ROUTER:2017`. On a fresh installation, create a v2rayA account, import your subscription and select a connection. Under **Subscription → Modify**, **Server Selection** chooses working-server or always-first behavior; **Monitoring** enables recovery after a sustained outage. Importing or installing packages does not install VPN credentials.

## What opkg installs

Install target: `v2raya-fork`.

| Package | Purpose and source |
| --- | --- |
| `v2raya-fork` | Small bundle from this signed feed; pins the tested application and Xray versions |
| `v2raya` | Fork from this feed, including its complete embedded web GUI |
| `xray-core` | Tested 25.1.30-r1 from the official feed |
| `v2ray-geoip`, `v2ray-geosite` | Official routing assets |
| `luci-light`, `luci-app-v2raya` | Official LuCI web interface and service page |
| `kmod-nft-tproxy`, `ca-bundle`, libraries | Pulled by the package dependencies from the router's own official feeds |

Keep `/etc/opkg/distfeeds.conf` configured for the router's actual OpenWrt release and target. Kernel modules must come from that matching feed. If the official feeds no longer offer the pinned Xray version, installation should fail instead of silently switching to an untested runtime; the bundle must then be updated and validated by the maintainer.

## Feed and signing key

The installed `/etc/opkg/customfeeds.conf` line is:

```text
src/gz v2raya_fork https://raw.githubusercontent.com/wywywywycloud/v2rayA/openwrt-feed/openwrt-24.10/aarch64_cortex-a53
```

The public key is installed at `/etc/opkg/keys/9f02e659f24749fa`.

- Fingerprint: `9f02e659f24749fa`.
- Public key SHA-256: `6ef5500355caf6da06e020818151ee1a6533336387450b7ac28dcaba5540d979`.
- [Public key](https://raw.githubusercontent.com/wywywywycloud/v2rayA/openwrt-feed/key.pub).
- [Feed branch](https://github.com/wywywywycloud/v2rayA/tree/openwrt-feed).

OpenWrt verifies the signature on `Packages`, whose SHA-256 fields authenticate the IPKs. The compressed index contains the same bytes after decompression. This follows the [OpenWrt repository signing model](https://openwrt.org/docs/guide-user/security/release_signatures) and [opkg custom feed configuration](https://openwrt.org/docs/guide-user/additional-software/opkg).

## Updates and removal

After a newer tested bundle is published to this feed:

```sh
opkg update
opkg install v2raya-fork
/etc/init.d/v2raya restart
```

Use package-specific updates; this is not a router-wide upgrade command. The source branch receives code changes independently: only a deliberate signed-feed publication makes a new binary installable.

To return to the official package, remove the bundle first (without `--autoremove`), remove only the `v2raya_fork` feed line, then install the official rollback IPK using `--force-downgrade`. See [installation and rollback](../README.md) for the original package commands. Removing only the feed does not replace an installed fork. Back up `/etc/v2raya` and `/etc/config/v2raya` before a rollback.

## Maintain and publish the feed

The public binary feed lives on `openwrt-feed`; implementation and build scripts live on `fix/openwrt-subscription-failover`. Build the application as described in [SUBSCRIPTION_FAILOVER.md](../../../SUBSCRIPTION_FAILOVER.md), then use a fresh output directory:

```sh
python3 install/openwrt/feed/build_feed.py \
  --ipk /path/to/v2raya_VERSION_aarch64_cortex-a53.ipk \
  --sha256 VERIFIED_PACKAGE_SHA256 \
  --output /tmp/new-feed \
  --secret-key /private/path/to/usign.key \
  --public-key install/openwrt/feed/key.pub \
  --usign /path/to/usign
```

Use the official [OpenWrt usign source](https://github.com/openwrt/usign); this publication used commit `c4c72b1b07945ee192361dc751291a7c98d6adcd`. The builder generates the bundle, package index, compressed index and signature, then verifies the signature. Increase `--bundle-revision` when changing only bundle packaging or dependencies for the same application version. It refuses a mismatched IPK checksum and refuses a secret key located inside its output directory. Review and publish the complete directory in one feed-branch commit after VM installation tests. Keep old versioned IPKs available if supporting older clients; do not overwrite an existing version with different contents.

The private signing key is retained locally in the task's `work/feed-secrets/usign.key` with owner-only permissions. It is not in Git, this document bundle or the binary feed. Back it up securely before removing the task workspace; losing it requires distributing a new trusted public key. Do not generate a new key for ordinary package updates.

## Validation

See [signed-feed validation](VALIDATION.md) for clean installation, signature rejection, upgrade preservation and twelve real-VPN regression checks.
