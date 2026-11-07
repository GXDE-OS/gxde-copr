#!/usr/bin/env python3
"""Generate the RPM file list for gxde-display-manager runtime."""
from pathlib import Path
import sys


def main():
    root, libdir = map(Path, sys.argv[1:])
    common = {'/etc', '/etc/gxdm', '/etc/xdg', '/etc/xdg/autostart',
              '/usr', '/usr/bin', '/usr/lib', '/usr/lib64', '/usr/lib/gxdm',
              '/usr/lib/systemd', '/usr/lib/systemd/system',
              '/usr/share', '/usr/share/dbus-1', '/usr/share/dbus-1/services',
              '/usr/share/dbus-1/system.d',
              '/usr/share/gxdm', '/usr/share/gxdm/scripts',
              '/usr/share/gxdm/translations-qt6',
              '/usr/share/gxdm/themes', '/usr/share/gxdm/faces', '/usr/share/gxdm/flags',
              '/usr/share/icons', '/usr/share/icons/hicolor',
              '/usr/share/selinux', '/usr/share/selinux/packages',
              '/usr/share/wayland-sessions', '/usr/share/xsessions',
              '/var', '/var/lib', '/var/lib/gxdm', '/var/log',
              str(libdir), f'{libdir}/qt6', f'{libdir}/qt6/qml', f'{libdir}/qt6/plugins'}
    runtime = []
    for file in sorted(root.rglob('*')):
        path = '/' + file.relative_to(root).as_posix()
        if file.is_dir() and not file.is_symlink() and path in common:
            continue
        if any(char in path for char in ('"', '\n', '%')):
            raise ValueError(f'Unsupported RPM path: {path!r}')
        manifest = ('%dir ' if file.is_dir() and not file.is_symlink() else '') + f'"{path}"'
        if path.startswith('/etc/') and file.is_file() and not file.is_symlink():
            # PAM and OMG.conf are declared as %config(noreplace) in the spec,
            # so skip them here to avoid double-declaration.
            if path.startswith('/etc/pam.d/') or path == '/etc/gxdm/OMG.conf':
                continue
            manifest = '%config(noreplace) ' + manifest
        # Skip /usr/share/licenses directory entries — the license files
        # themselves are included below; the directory is auto-created by
        # %license in the spec.
        if path == '/usr/share/licenses/gxde-display-manager':
            continue
        if path == '/usr/share/selinux/packages/gxdm.pp.bz2':
            continue
        runtime.append(manifest)
    if not runtime:
        raise ValueError('Empty RPM package: runtime')
    Path('runtime.files').write_text('\n'.join(runtime) + '\n')


if __name__ == '__main__':
    main()
