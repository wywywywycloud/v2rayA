#!/bin/sh
# Install the signed fork feed and its complete package set on OpenWrt 24.10.4.
set -eu
[ "$(id -u)" = 0 ] || { echo 'Run this script as root on the router.' >&2; exit 1; }
. /etc/openwrt_release
[ "$DISTRIB_RELEASE" = '24.10.4' ] || { echo 'This installer is validated for OpenWrt 24.10.4 only.' >&2; exit 1; }
opkg print-architecture | awk '$2 == "aarch64_cortex-a53" {found=1} END {exit !found}' || {
    echo 'This feed requires the aarch64_cortex-a53 package architecture.' >&2; exit 1;
}
feed_url='https://raw.githubusercontent.com/wywywywycloud/v2rayA/openwrt-feed/openwrt-24.10/aarch64_cortex-a53'
key_url='https://raw.githubusercontent.com/wywywywycloud/v2rayA/openwrt-feed/key.pub'
key_sha256='6ef5500355caf6da06e020818151ee1a6533336387450b7ac28dcaba5540d979'
key_id='9f02e659f24749fa'
work_dir=$(mktemp -d /tmp/v2raya-feed.XXXXXX)
trap 'rm -rf "$work_dir"' EXIT
trap 'exit 1' HUP INT TERM
wget -O "$work_dir/key.pub" "$key_url"
printf '%s  %s\n' "$key_sha256" "$work_dir/key.pub" | sha256sum -c -
[ "$(usign -F -p "$work_dir/key.pub")" = "$key_id" ]
# Authenticate the index before changing the router's feed configuration.
wget -O "$work_dir/Packages" "$feed_url/Packages"
wget -O "$work_dir/Packages.sig" "$feed_url/Packages.sig"
usign -V -m "$work_dir/Packages" -p "$work_dir/key.pub" -x "$work_dir/Packages.sig"
if [ -d /etc/v2raya ]; then
    backup="/tmp/v2raya-before-fork-$(date +%Y%m%d-%H%M%S).tar.gz"
    tar -czf "$backup" /etc/v2raya /etc/config/v2raya
    echo "Settings backup: $backup (copy it off the router before rebooting)."
fi
mkdir -p /etc/opkg/keys
cp "$work_dir/key.pub" "/etc/opkg/keys/$key_id"
chmod 644 "/etc/opkg/keys/$key_id"
touch /etc/opkg/customfeeds.conf
awk '$2 != "v2raya_fork"' /etc/opkg/customfeeds.conf > "$work_dir/customfeeds.conf"
printf 'src/gz v2raya_fork %s\n' "$feed_url" >> "$work_dir/customfeeds.conf"
cat "$work_dir/customfeeds.conf" > /etc/opkg/customfeeds.conf
opkg update
opkg install v2raya-fork
uci set v2raya.config.enabled='1'
uci commit v2raya
/etc/init.d/v2raya enable
/etc/init.d/v2raya restart
echo 'Installed. Open LuCI > Services > v2rayA, or http://ROUTER:2017.'
