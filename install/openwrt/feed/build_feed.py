#!/usr/bin/env python3
"""Build and sign the binary opkg feed; keep its private key outside the output."""
import argparse
import gzip
import hashlib
import io
from pathlib import Path
import shutil
import subprocess
import tarfile


def archive(files):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w', format=tarfile.GNU_FORMAT) as tar:
        directories = set()
        for name, data in files.items():
            parts = name.removeprefix('./').split('/')[:-1]
            for depth in range(1, len(parts)+1):
                directory = './' + '/'.join(parts[:depth]) + '/'
                if directory not in directories:
                    entry = tarfile.TarInfo(directory)
                    entry.type, entry.mode, entry.mtime = tarfile.DIRTYPE, 0o755, 0
                    tar.addfile(entry)
                    directories.add(directory)
            entry = tarfile.TarInfo(name)
            entry.size, entry.mode, entry.mtime = len(data), 0o644, 0
            tar.addfile(entry, io.BytesIO(data))
    return gzip.compress(stream.getvalue(), mtime=0)


def control(path):
    with tarfile.open(path) as outer:
        with tarfile.open(fileobj=io.BytesIO(outer.extractfile('./control.tar.gz').read())) as inner:
            return inner.extractfile('./control').read().decode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ipk', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bundle-revision', type=int, default=1)
    parser.add_argument('--secret-key', type=Path, required=True)
    parser.add_argument('--public-key', type=Path, required=True)
    parser.add_argument('--usign', type=Path, required=True)
    args = parser.parse_args()
    if args.secret_key.resolve().is_relative_to(args.output.resolve()):
        parser.error('private signing key must be outside the feed directory')
    if args.bundle_revision < 1:
        parser.error('bundle revision must be positive')
    payload = args.ipk.read_bytes()
    if hashlib.sha256(payload).hexdigest() != args.sha256:
        parser.error('candidate IPK checksum mismatch')
    app_control = control(args.ipk)
    fields = dict(line.split(': ', 1) for line in app_control.splitlines() if ': ' in line and not line.startswith(' '))
    if fields['Package'] != 'v2raya' or fields['Architecture'] != 'aarch64_cortex-a53':
        parser.error('expected the tested Cortex-A53 v2raya package')
    version = fields['Version']
    bundle_version = version + f'.feed{args.bundle_revision}'
    args.output.mkdir(parents=True, exist_ok=True)
    # Reject mixing versions: opkg should see one deliberately released candidate.
    if any(args.output.glob('*.ipk')):
        parser.error('build into a fresh directory; existing IPKs found')
    shutil.copyfile(args.ipk, args.output / args.ipk.name)
    bundle_control = f'''Package: v2raya-fork
Version: {bundle_version}
Architecture: aarch64_cortex-a53
Depends: v2raya (= {version}), xray-core (= 25.1.30-r1), v2ray-geoip, v2ray-geosite, luci-light, luci-app-v2raya
Section: net
License: AGPL-3.0-only
Maintainer: Mikhail Levin
Source: https://github.com/wywywywycloud/v2rayA/tree/fix/openwrt-subscription-failover
Installed-Size: 1024
Description: Tested v2rayA fork with Xray, geodata and LuCI interface
 Installs the tested application, embedded web UI and official dependencies.
'''
    bundle = archive({
        './debian-binary': b'2.0\n',
        './control.tar.gz': archive({'./control': bundle_control.encode()}),
        './data.tar.gz': archive({'./usr/share/v2raya-fork/README': b'The v2rayA fork includes its web UI. LuCI exposes Services > v2rayA.\n'}),
    })
    (args.output / f'v2raya-fork_{bundle_version}_aarch64_cortex-a53.ipk').write_bytes(bundle)
    stanzas = []
    for package in sorted(args.output.glob('*.ipk')):
        data = package.read_bytes()
        # Metadata outside Description is kept before its continuation lines.
        text = control(package)
        extra = f'Filename: {package.name}\nSize: {len(data)}\nSHA256sum: {hashlib.sha256(data).hexdigest()}\n'
        text = text.replace('Description:', extra + 'Description:', 1)
        stanzas.append(text.rstrip() + '\n')
    index = ('\n'.join(stanzas) + '\n').encode()
    (args.output / 'Packages').write_bytes(index)
    (args.output / 'Packages.gz').write_bytes(gzip.compress(index, mtime=0))
    subprocess.run([str(args.usign.resolve()), '-S', '-m', str(args.output/'Packages'), '-s', str(args.secret_key), '-x', str(args.output/'Packages.sig')], check=True)
    subprocess.run([str(args.usign.resolve()), '-V', '-m', str(args.output/'Packages'), '-p', str(args.public_key), '-x', str(args.output/'Packages.sig')], check=True)
    print('Signed feed created:', args.output)


if __name__ == '__main__':
    main()
