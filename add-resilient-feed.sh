#!/bin/sh
# Add the signed Resilient feed; install the fork later through LuCI Software.
set -eu
umask 077
[ "$(id -u)" = 0 ] || { echo 'Run as root on OpenWrt.' >&2; exit 1; }
. /etc/openwrt_release
[ "$DISTRIB_RELEASE" = '24.10.4' ] || { echo 'Validated for OpenWrt 24.10.4 only.' >&2; exit 1; }
opkg print-architecture | awk '$2 == "aarch64_cortex-a53" {found=1} END {exit !found}' || {
    echo 'Requires aarch64_cortex-a53; do not override your router architecture.' >&2; exit 1;
}
feed_url='https://raw.githubusercontent.com/wywywywycloud/v2rayA-current/openwrt-feed/openwrt-24.10/resilient/aarch64_cortex-a53'
key_url='https://raw.githubusercontent.com/wywywywycloud/v2rayA-current/openwrt-feed/key.pub'
key_sha256='6ef5500355caf6da06e020818151ee1a6533336387450b7ac28dcaba5540d979'
key_id='9f02e659f24749fa'
work_dir=$(mktemp -d /tmp/v2raya-resilient.XXXXXX)
trap 'rm -rf "$work_dir"' EXIT
trap 'exit 1' HUP INT TERM
wget -O "$work_dir/key.pub" "$key_url"
printf '%s  %s\n' "$key_sha256" "$work_dir/key.pub" | sha256sum -c -
[ "$(usign -F -p "$work_dir/key.pub")" = "$key_id" ]
wget -O "$work_dir/Packages" "$feed_url/Packages"
wget -O "$work_dir/Packages.sig" "$feed_url/Packages.sig"
usign -V -m "$work_dir/Packages" -p "$work_dir/key.pub" -x "$work_dir/Packages.sig"
mkdir -p /etc/opkg/keys
cp "$work_dir/key.pub" "/etc/opkg/keys/$key_id"
chmod 644 "/etc/opkg/keys/$key_id"
touch /etc/opkg/customfeeds.conf
cp /etc/opkg/customfeeds.conf "$work_dir/customfeeds.before"
# Replace only this project's previous sources; preserve all unrelated feeds.
awk '$2 != "v2raya_resilient" && $2 != "v2raya_levin" && $2 != "v2raya_current" && $2 != "v2raya_fork"' /etc/opkg/customfeeds.conf > "$work_dir/customfeeds.conf"
printf 'src/gz v2raya_resilient %s\n' "$feed_url" >> "$work_dir/customfeeds.conf"
if ! cmp -s "$work_dir/customfeeds.before" "$work_dir/customfeeds.conf"; then
    cp "$work_dir/customfeeds.before" /etc/opkg/customfeeds.conf.before-resilient
    cat "$work_dir/customfeeds.conf" > /etc/opkg/customfeeds.conf
fi
rm -f /var/opkg-lists/v2raya_levin /var/opkg-lists/v2raya_levin.sig /var/opkg-lists/v2raya_current /var/opkg-lists/v2raya_fork
opkg update
echo 'Feed added. In LuCI: System > Software > filter resilient > Install luci-app-v2raya-resilient.'
echo 'No application package or application setting was changed by this script.'
