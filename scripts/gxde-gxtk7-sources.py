#!/usr/bin/env python3
"""Pin GXDE Bernese and GXTK7 release tags and prepare their RPM trees."""
import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'packages/gxde-gxtk7'
LOCK_PATH = PACKAGE / 'upstream-lock.json'
PACKAGES = {
    'gxde-bernese': {'repo': 'GXDE-OS/gxde-bernese', 'upstream': 'gxde-bernese'},
    'gxde-gxtk7': {'repo': 'GXDE-OS/GXTK7', 'upstream': 'GXTK7'},
}


def load_core():
    spec = importlib.util.spec_from_file_location(
        'gxde_core_sources', Path(__file__).with_name('gxde-core-sources.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = load_core()
sources = core.sources


def resolve_one(name, meta, previous, cache):
    refs = subprocess.check_output(
        ['git', 'ls-remote', '--tags', f'https://github.com/{meta["repo"]}.git'],
        text=True, timeout=120)
    tag, commit = core.latest_tag(refs)
    if previous:
        if core.tag_key(tag) < core.tag_key(previous['tag']):
            raise ValueError(f'{name}: release tag rolled back')
        if tag == previous['tag'] and commit != previous['commit']:
            raise ValueError(f'{name}: released tag moved')
    url = f'https://codeload.github.com/{meta["repo"]}/tar.gz/{commit}'
    filename = f'{meta["upstream"]}-{commit}.tar.gz'
    digest = sources.download(
        url, cache / filename,
        previous['sha256'] if previous and previous['commit'] == commit else None)
    version = core.rpm_version(tag)
    if not previous or previous.get('version') != version:
        release = 1
    elif previous['commit'] != commit:
        release = previous.get('release', 1) + 1
    else:
        release = previous.get('release', 1)
    return {'tag': tag, 'version': version, 'release': release,
            'commit': commit, 'url': url, 'sha256': digest}


def update():
    old = json.loads(LOCK_PATH.read_text()) if LOCK_PATH.exists() else {}
    cache = ROOT / 'build/source-cache'
    cache.mkdir(parents=True, exist_ok=True)
    lock = {}
    for name, meta in PACKAGES.items():
        lock[name] = resolve_one(name, meta, old.get(name), cache)
        print(f'{name}: {lock[name]["tag"]} ({lock[name]["commit"][:12]})', flush=True)
    LOCK_PATH.write_text(json.dumps(lock, indent=2) + '\n')


def prepare_one(name, lock):
    item = lock[name]
    meta = PACKAGES[name]
    commit = item['commit']
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError(f'{name}: invalid commit')
    output = ROOT / 'build' / f'{name}-rpmbuild'
    for directory in ('SOURCES', 'SPECS', 'BUILD', 'BUILDROOT', 'RPMS', 'SRPMS'):
        (output / directory).mkdir(parents=True, exist_ok=True)
    filename = f'{meta["upstream"]}-{commit}.tar.gz'
    source = output / 'SOURCES' / filename
    cache = ROOT / 'build/source-cache' / filename
    if cache.exists() and hashlib.sha256(cache.read_bytes()).hexdigest() == item['sha256']:
        shutil.copyfile(cache, source)
    sources.download(item['url'], source, item['sha256'])
    with tarfile.open(source, 'r:gz') as tar:
        top = next(iter(tar)).name.split('/')[0]
    if top != f'{meta["upstream"]}-{commit}':
        raise ValueError(f'{name}: unexpected codeload top directory {top}')
    (output / 'SOURCES/sources.sha256').write_text(f'{item["sha256"]}  {filename}\n')
    shutil.copyfile(PACKAGE / 'split-files.py', output / 'SOURCES/split-files.py')
    (output / 'SOURCES/upstream-lock.json').write_text(json.dumps(item, indent=2) + '\n')
    spec = (PACKAGE / f'{name}.spec.in').read_text()
    for key, value in {'@TAG@': item['tag'], '@COMMIT@': commit,
                       '@VERSION@': item['version'], '@RELEASE@': str(item['release']),
                       '@URL@': item['url']}.items():
        spec = spec.replace(key, value)
    if re.search(r'@[A-Z_]+@', spec):
        raise ValueError(f'{name}: unresolved spec placeholder')
    (output / 'SPECS' / f'{name}.spec').write_text(spec)
    print(f'prepared {name} -> {output}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('update', 'prepare'))
    parser.add_argument('--package', choices=(*PACKAGES, 'all'), default='all')
    args = parser.parse_args()
    if args.command == 'update':
        update()
        return
    lock = json.loads(LOCK_PATH.read_text())
    names = PACKAGES if args.package == 'all' else (args.package,)
    for name in names:
        prepare_one(name, lock)


if __name__ == '__main__':
    main()
