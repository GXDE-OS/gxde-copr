#!/usr/bin/env python3
"""Generate exact runtime/development file lists for GXTK7 packages."""
from pathlib import Path
import sys


def category(path, libdir):
    parent = path.rsplit('/', 1)[0]
    if (path.startswith('/usr/include/') or path.startswith('/usr/share/cmake/')
            or path.startswith('/usr/share/pkgconfig/')
            or path.startswith(f'{libdir}/cmake/') or path.startswith(f'{libdir}/pkgconfig/')
            or path.endswith(('.a', '.prl'))
            or (parent == libdir and path.endswith('.so'))):
        return 'devel'
    return 'runtime'


def main():
    root = Path(sys.argv[1])
    libdir = sys.argv[2]
    common = {'/usr', '/usr/bin', '/usr/lib', '/usr/lib64', '/usr/include',
              '/usr/share', '/usr/share/doc', '/usr/share/man', '/usr/share/man/man3',
              libdir, f'{libdir}/cmake', f'{libdir}/pkgconfig',
              f'{libdir}/qt6', f'{libdir}/qt6/qml',
              f'{libdir}/qt6/qml/QtQuick', f'{libdir}/qt6/qml/QtQuick/Controls'}
    groups = {'runtime': [], 'devel': []}
    for item in sorted(root.rglob('*')):
        path = '/' + item.relative_to(root).as_posix()
        if item.is_dir() and not item.is_symlink() and path in common:
            continue
        if any(char in path for char in ('"', '\n', '%')):
            raise ValueError(f'Unsupported RPM path: {path!r}')
        line = ('%dir ' if item.is_dir() and not item.is_symlink() else '') + f'"{path}"'
        groups[category(path, libdir)].append(line)
    for name, paths in groups.items():
        if paths:
            Path(f'{name}.files').write_text('\n'.join(paths) + '\n')
        elif name == 'runtime':
            raise ValueError('Empty runtime package')


if __name__ == '__main__':
    main()
