#!/bin/sh
# Install the current-source service, matching core and LuCI on OpenWrt 24.10.4.
set -eu
umask 077
[ "$(id -u)" = 0 ] || { echo 'Run as root on the router.' >&2; exit 1; }
. /etc/openwrt_release
[ "$DISTRIB_RELEASE" = '24.10.4' ] || { echo 'Validated for OpenWrt 24.10.4 only.' >&2; exit 1; }
opkg print-architecture | awk '$2 == "aarch64_cortex-a53" {found=1} END {exit !found}' || {
    echo 'Requires the aarch64_cortex-a53 package architecture.' >&2; exit 1;
}
feed_url='https://raw.githubusercontent.com/wywywywycloud/v2rayA/openwrt-feed/openwrt-24.10/current/aarch64_cortex-a53'
key_url='https://raw.githubusercontent.com/wywywywycloud/v2rayA/openwrt-feed/key.pub'
key_sha256='6ef5500355caf6da06e020818151ee1a6533336387450b7ac28dcaba5540d979'
key_id='9f02e659f24749fa'
work_dir=$(mktemp -d /tmp/v2raya-current.XXXXXX)
was_running=0
if pidof v2raya >/dev/null 2>&1; then was_running=1; fi
cleanup() {
    result=$?
    trap - EXIT
    rm -rf "$work_dir"
    if [ "$result" != 0 ] && [ "$was_running" = 1 ]; then
        /etc/init.d/v2raya start || true
    fi
    exit "$result"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
if [ -d /etc/v2raya ]; then
    backup="/tmp/v2raya-before-current-$(date +%Y%m%d-%H%M%S).tar.gz"
    tar -czf "$backup" /etc/v2raya /etc/config/v2raya
    echo "Settings backup: $backup (copy off the router before rebooting)."
fi
# A broken transparent proxy must not intercept the package download itself.
if [ -x /etc/init.d/v2raya ]; then /etc/init.d/v2raya stop; fi
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
awk '$2 != "v2raya_current" && $2 != "v2raya_fork"' /etc/opkg/customfeeds.conf > "$work_dir/customfeeds.conf"
printf 'src/gz v2raya_current %s\n' "$feed_url" >> "$work_dir/customfeeds.conf"
cat "$work_dir/customfeeds.conf" > /etc/opkg/customfeeds.conf
opkg update
# The old bundle pins v2raya 2.2.x; remove only that metapackage, not user data.
if opkg status v2raya-fork | grep -q '^Status:.* installed$'; then
    opkg remove v2raya-fork
fi
opkg install luci-app-v2raya
[ -x /usr/bin/v2raya ] && [ -x /usr/bin/v2raya_core ] || {
    echo 'Installation incomplete; inspect the opkg output.' >&2; exit 1;
}
uci set v2raya.config.enabled='1'
uci commit v2raya
/etc/init.d/v2raya enable
/etc/init.d/v2raya restart
echo 'Installed. Open LuCI > Services > v2rayA. Verify that the service reports a matching core version.'
