#!/usr/bin/env python3
"""Disposable OpenWrt LAN-client verification; never targets a physical router."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import time
import urllib.request

from fixtures import Node, Proxy


def main():
    p = argparse.ArgumentParser()
    for name in ('output', 'service', 'core', 'image', 'kernel', 'ssh-key', 'xray'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--qemu', default='qemu-system-aarch64')
    p.add_argument('--keep-running', action='store_true')
    args = p.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    args.host_address = '10.0.2.2'
    token = None
    direct = node = None
    known = args.output / 'known_hosts'
    known.unlink(missing_ok=True)
    key = args.ssh_key.resolve()
    base = ['-F', '/dev/null', '-i', str(key), '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=accept-new', '-o', f'UserKnownHostsFile={known}', '-o', 'LogLevel=ERROR', '-o', 'ConnectTimeout=3']

    def ssh(command, check=True, timeout=120):
        result = subprocess.run(['ssh', *base, '-p', '22522', 'root@127.0.0.1', command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, text=True)
        if check and result.returncode:
            raise RuntimeError(f'{command}\n{result.stdout}')
        return result.stdout

    def scp(source, dest):
        subprocess.run(['scp', '-O', *base, '-P', '22522', str(source), f'root@127.0.0.1:{dest}'], check=True, timeout=60)

    def api(path, data=None, method=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        req = urllib.request.Request('http://127.0.0.1:22517/api/' + path, data=None if data is None else json.dumps(data).encode(), headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as response:
            reply = json.load(response)
        assert reply['code'] == 'SUCCESS', reply
        return reply['data']

    def wait(fn, seconds=35):
        last = None
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                result = fn()
                if result:
                    return result
            except Exception as error:
                last = error
            time.sleep(.3)
        raise TimeoutError(str(last))

    log = (args.output / 'qemu.log').open('wb')
    qemu = subprocess.Popen([
        args.qemu, '-machine', 'virt', '-accel', 'hvf', '-cpu', 'host', '-smp', '2', '-m', '256',
        '-kernel', str(args.kernel.resolve()), '-append', 'root=/dev/vda rootwait console=ttyAMA0',
        '-drive', f'if=none,file={args.image.resolve()},format=raw,snapshot=on,id=root', '-device', 'virtio-blk-pci,drive=root',
        '-netdev', 'user,id=wan,hostfwd=tcp:127.0.0.1:22522-:22,hostfwd=tcp:127.0.0.1:22517-:2017,hostfwd=tcp:127.0.0.1:22580-:80',
        '-device', 'virtio-net-pci,netdev=wan', '-device', 'virtio-rng-pci', '-display', 'none', '-monitor', 'none', '-serial', 'stdio',
    ], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    checks = []
    try:
        wait(lambda: 'READY' in ssh('echo READY', timeout=6))
        print('VM booted', flush=True)
        ssh('/etc/init.d/v2raya stop; rm -rf /tmp/bridge-review-state; mkdir -p /tmp/bridge-review-state')
        install = ssh('opkg update && opkg install ip-full kmod-veth curl', timeout=240)
        (args.output / 'dependencies.log').write_text(install)
        scp(args.service, '/tmp/bridge-review-v2raya')
        scp(args.core, '/tmp/v2raya_core')
        ssh('chmod +x /tmp/bridge-review-v2raya /tmp/v2raya_core; V2RAYA_CONFIG=/tmp/bridge-review-state V2RAYA_V2RAY_BIN=/tmp/v2raya_core V2RAYA_V2RAY_ASSETSDIR=/usr/share/v2ray /tmp/bridge-review-v2raya --address 0.0.0.0:2017 >/tmp/bridge-review.log 2>&1 </dev/null &')
        wait(lambda: api('version'))
        token = api('account', {'username': 'bridge-test', 'password': 'disposable-vm-only'})['token']
        setting = api('setting')['setting']
        expected = 'docker*,veth*,wg*,ppp*'
        assert setting['tproxyExcludedInterfaces'] == expected, setting
        checks.append('fresh OpenWrt default includes LAN bridges')
        # An independent network stack acts as the LAN client. Its packets enter
        # the router via a bridge slave, and IPv4 prerouting sees iifname br-lan.
        ssh('set -e; ip netns add bridge-client; ip link add lan-client type veth peer name client-eth; ip link set lan-client master br-lan; ip link set lan-client up; ip link set client-eth netns bridge-client; ip addr add 192.0.2.1/24 dev br-lan; ip -n bridge-client link set lo up; ip -n bridge-client addr add 192.0.2.2/24 dev client-eth; ip -n bridge-client link set client-eth up; ip -n bridge-client route add default via 192.0.2.1; sysctl -w net.ipv4.ip_forward=1')
        node, direct = Node('LAN-VPN', 0, args), Proxy('DIRECT-ESCAPE')
        trap = '''table ip bridge_review {
 chain trace { type filter hook prerouting priority -156; policy accept;
  iifname "br-lan" ip saddr 192.0.2.2 ip daddr 198.18.0.1 tcp dport 80 counter meta nftrace set 1
 }
 chain escape { type nat hook prerouting priority dstnat; policy accept;
  iifname "br-lan" ip saddr 192.0.2.2 ip daddr 198.18.0.1 tcp dport 80 meta mark & 0xc0 != 0x40 counter dnat to 10.0.2.2:%d
 }
 chain snat_client { type nat hook postrouting priority srcnat; policy accept;
  ip saddr 192.0.2.2 ip daddr 10.0.2.2 tcp dport %d masquerade
 }
}''' % (direct.server_address[1], direct.server_address[1])
        ssh('printf %s ' + shlex.quote(trap) + ' | nft -f -')
        client_command = 'ip netns exec bridge-client curl --noproxy "*" -fsS --max-time 6 http://198.18.0.1/traffic'
        assert ssh(client_command).strip() == 'DIRECT-ESCAPE'
        checks.append('independent LAN client reaches direct trap before TPROXY starts')
        api('ports', {'socks5': 20170, 'http': 20171, 'socks5WithPac': 0, 'httpWithPac': 0, 'vmess': 0}, 'PUT')
        api('import', {'url': node.link})
        setting.update(portSharing=True, transparent='proxy', transparentType='tproxy')
        api('setting', setting, 'PUT')
        api('connection', {'_type': 'server', 'id': 1, 'sub': 0, 'outbound': 'proxy'}, 'POST')
        wait(lambda: ssh(client_command).strip() == 'LAN-VPN')
        ssh('nft monitor trace >/tmp/bridge-trace.log 2>&1 </dev/null &')
        start_direct = direct.requests
        for _ in range(5):
            assert ssh(client_command).strip() == 'LAN-VPN'
        assert direct.requests == start_direct, (direct.requests, start_direct)
        trace = ssh('cat /tmp/bridge-trace.log')
        (args.output / 'forwarded-trace.log').write_text(trace)
        assert 'iif "br-lan"' in trace, trace
        assert 'tproxy ip to 127.0.0.1:52345' in trace, trace[-4000:]
        checks.append('forwarded LAN TCP hits br-lan, mark 0x40 and TPROXY to 127.0.0.1:52345; five requests use VLESS with no direct escapes')
        (args.output / 'working-rules.nft').write_text(ssh('nft list table inet v2raya'))
        # Reproduce the previous exclusion while the service remains running
        # (restarting would intentionally migrate the exact historical default).
        api('v2ray', {}, 'DELETE')
        setting = api('setting')['setting']
        setting['tproxyExcludedInterfaces'] = expected + ',br-*'
        api('setting', setting, 'PUT')
        api('v2ray', {}, 'POST')
        assert wait(lambda: ssh(client_command).strip() == 'DIRECT-ESCAPE')
        checks.append('historical br-* exclusion reproduces a LAN direct escape')
        # Verify a custom list also bypasses deliberately, rather than being
        # silently overridden by the new defaults.
        api('v2ray', {}, 'DELETE')
        setting['tproxyExcludedInterfaces'] = 'br-lan,wg*'
        api('setting', setting, 'PUT')
        api('v2ray', {}, 'POST')
        assert wait(lambda: ssh(client_command).strip() == 'DIRECT-ESCAPE')
        checks.append('explicit custom br-lan exclusion remains effective')
        api('v2ray', {}, 'DELETE')
        setting['tproxyExcludedInterfaces'] = expected
        api('setting', setting, 'PUT')
        api('v2ray', {}, 'POST')
        assert wait(lambda: ssh(client_command).strip() == 'LAN-VPN')
        checks.append('restoring OpenWrt default restores LAN interception')
        evidence = {'result': 'PASS', 'board': json.loads(ssh('ubus call system board')), 'version': api('version'), 'client': ssh('ip -n bridge-client addr; ip -n bridge-client route; ip link show master br-lan'), 'checks': checks, 'direct_requests': direct.requests, 'proxy_requests': node.fixture.requests}
        (args.output / 'result.json').write_text(json.dumps(evidence, indent=2) + '\n')
        (args.output / 'service.log').write_text(ssh('cat /tmp/bridge-review.log'))
        print(json.dumps(evidence, indent=2), flush=True)
        if args.keep_running:
            print('VM kept running for GUI check; terminate this process to stop it.', flush=True)
            while qemu.poll() is None:
                time.sleep(1)
    finally:
        if qemu.poll() is None:
            qemu.terminate()
            qemu.wait(timeout=10)
        log.close()
        if node:
            node.close()
        if direct:
            direct.shutdown()
            direct.server_close()


if __name__ == '__main__':
    main()
