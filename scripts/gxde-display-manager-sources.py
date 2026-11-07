#!/usr/bin/env python3
"""Lock GXDE Display Manager (SDDM fork) and emergency-mode to release tags.

gxdm-emergency-mode has no vendored Rust deps; we run `cargo vendor` during
prepare (on the dev machine, which has network + cargo) and ship the vendored
crate set as an extra Source so COPR can build offline.
"""
import importlib.util
import re
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

spec = importlib.util.spec_from_file_location('dtk_sources', Path(__file__).with_name('dtk5-sources.py'))
sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sources)

sources.MODULES = ('gxde-display-manager', 'gxdm-emergency-mode')
sources.CORE_MODULE = 'gxde-display-manager'
sources.SPEC_NAME = 'gxde-display-manager'
sources.PACKAGE = sources.ROOT / 'packages/gxde-display-manager'
sources.DEFAULT_OUTPUT = sources.ROOT / 'build/gxdm-rpmbuild'

TAG = re.compile(r'v?(\d+(?:\.\d+)*)(?:-?gxde(\d+))?$')

# MavenPro OFL license — fixed commit matching AUR.
MAVENPRO_COMMIT = '1c21ee500b7b87a4871696519fc84107a1a001df'
MAVENPRO_SHA256 = 'e0cde1a4993ed689d463d5e2401f4a60c54cc48a14253ab0f8012d722c417038'
MAVENPRO_URL = f'https://raw.githubusercontent.com/googlefonts/mavenproFont/{MAVENPRO_COMMIT}/OFL.txt'


def tag_key(tag):
    match = TAG.fullmatch(tag)
    if not match:
        raise ValueError(f'Unsupported release tag: {tag}')
    numbers = tuple(map(int, match[1].split('.')))
    return numbers + (0,) * (8 - len(numbers)), int(match[2] or 0)


def latest_tag(refs):
    tags, peeled = {}, {}
    for line in refs.splitlines():
        sha, ref = line.split()
        if not ref.startswith('refs/tags/'):
            continue
        name = ref.removeprefix('refs/tags/')
        if name.endswith('^{}'):
            peeled[name[:-3]] = sha
        elif TAG.fullmatch(name):
            tags[name] = sha
    if not tags:
        raise ValueError('No stable numeric release tags found; refusing a HEAD fallback')
    tag = max(tags, key=lambda value: (tag_key(value), value))
    return tag, peeled.get(tag, tags[tag])


def rpm_version(tag):
    match = TAG.fullmatch(tag)
    if not match:
        raise ValueError(f'Unsupported release tag: {tag}')
    return match[1] + (f'.gxde{match[2]}' if match[2] else '')


def resolve(old, cache):
    components = {}
    for name in sources.MODULES:
        refs = subprocess.check_output(['git', 'ls-remote', '--tags',
                                        f'https://github.com/GXDE-OS/{name}.git'],
                                       text=True, timeout=120)
        tag, commit = latest_tag(refs)
        previous = old.get('components', {}).get(name)
        if previous and tag_key(tag) < tag_key(previous['tag']):
            raise ValueError(f'{name}: upstream tag rollback requires manual review')
        if previous and previous['tag'] == tag and previous['commit'] != commit:
            raise ValueError(f'{name}: released tag moved; refusing automatic update')
        url = f'https://codeload.github.com/GXDE-OS/{name}/tar.gz/{commit}'
        item = {'tag': tag, 'commit': commit, 'url': url}
        item['sha256'] = sources.download(url, cache / f'{name}-{commit}.tar.gz',
                                          previous['sha256'] if previous and previous['commit'] == commit else None)
        components[name] = item
        print(f'{name}: {tag} ({commit[:12]})', flush=True)
    # MavenPro OFL license (static commit, not a git tag)
    components['MavenPro-OFL'] = {
        'tag': f'commit:{MAVENPRO_COMMIT[:12]}',
        'commit': MAVENPRO_COMMIT,
        'url': MAVENPRO_URL,
        'sha256': sources.download(MAVENPRO_URL, cache / f'MavenPro-OFL-{MAVENPRO_COMMIT}.txt', MAVENPRO_SHA256),
    }
    version = rpm_version(components[sources.CORE_MODULE]['tag'])
    changed = components != old.get('components')
    release = old.get('release', 0) + int(changed) if version == old.get('version') else 1
    return {'version': version, 'release': release, 'components': components}


sources.tag_key = tag_key
sources.latest_tag = latest_tag
sources.rpm_version = rpm_version
sources.resolve = resolve


def _cargo_vendor(src_dir, vendor_tarball):
    """Run `cargo vendor` on the extracted gxdm-emergency-mode source."""
    cargo_toml = src_dir / 'Cargo.toml'
    if not cargo_toml.exists():
        raise ValueError(f'{src_dir}: Cargo.toml not found')
    vendor_dir = src_dir / 'vendor'
    if vendor_dir.exists():
        shutil.rmtree(vendor_dir)
    subprocess.run(['cargo', 'vendor', '--locked', '--versioned-dirs', str(vendor_dir)],
                   cwd=src_dir, check=True, timeout=600)
    # Create .cargo/config.toml so --offline finds the vendor dir.
    config_dir = src_dir / '.cargo'
    config_dir.mkdir(exist_ok=True)
    (config_dir / 'config.toml').write_text(
        '[source.crates-io]\n'
        'replace-with = "vendored-sources"\n\n'
        '[source.vendored-sources]\n'
        'directory = "vendor"\n'
    )
    # Pack the vendor dir + .cargo/config.toml into a tarball for the SRPM.
    # Use arcnames without the 'gxdm-emergency-mode/' prefix so that
    # `tar xf vendor.tar.gz -C gxdm-emergency-mode` extracts to
    # gxdm-emergency-mode/vendor/ and gxdm-emergency-mode/.cargo/config.toml.
    with tarfile.open(vendor_tarball, 'w:gz') as tar:
        tar.add(vendor_dir, arcname='vendor',
                filter=lambda info: info)
        tar.add(config_dir / 'config.toml', arcname='.cargo/config.toml')


def prepare(lock, destination):
    import hashlib
    ROOT = sources.ROOT
    PACKAGE = sources.PACKAGE
    MODULES = sources.MODULES

    for directory in ("SOURCES", "SPECS", "BUILD", "BUILDROOT", "RPMS", "SRPMS"):
        (destination / directory).mkdir(parents=True, exist_ok=True)

    definitions, sources_list, checks = [], [], []
    for index, name in enumerate(MODULES):
        component = lock["components"][name]
        commit = component["commit"]
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError(f"Invalid commit for {name}")
        filename = f"{name}-{commit}.tar.gz"
        cached = ROOT / "build/source-cache" / filename
        if cached.exists() and hashlib.sha256(cached.read_bytes()).hexdigest() == component["sha256"]:
            shutil.copyfile(cached, destination / "SOURCES" / filename)
        sources.download(component["url"], destination / "SOURCES" / filename, component["sha256"])
        definitions.append(f"%global commit{index} {commit}")
        sources_list.append(f"Source{index}: {component['url']}#/{filename}")
        checks.append(f"{component['sha256']}  {filename}")

    # Source2: vendored Rust crates for gxdm-emergency-mode (generated locally)
    emergency = lock['components']['gxdm-emergency-mode']
    emergency_tarball = destination / 'SOURCES' / f'gxdm-emergency-mode-{emergency["commit"]}-vendor.tar.gz'
    if not emergency_tarball.exists():
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with tarfile.open(destination / 'SOURCES' / f'gxdm-emergency-mode-{emergency["commit"]}.tar.gz') as tar:
                tar.extractall(tmp)
            src_dir = Path(tmp) / f'gxdm-emergency-mode-{emergency["commit"]}'
            _cargo_vendor(src_dir, emergency_tarball)
    vendor_sha = hashlib.sha256(emergency_tarball.read_bytes()).hexdigest()
    # spec references the short name; create it as a copy.
    shutil.copyfile(emergency_tarball, destination / 'SOURCES' / 'gxdm-emergency-mode-vendor.tar.gz')
    sources_list.append(f'Source2: gxdm-emergency-mode-vendor.tar.gz')
    checks.append(f'{vendor_sha}  gxdm-emergency-mode-vendor.tar.gz')

    # Source3: MavenPro OFL license
    maven = lock['components']['MavenPro-OFL']
    maven_file = destination / 'SOURCES' / f'MavenPro-OFL-{MAVENPRO_COMMIT}.txt'
    sources.download(maven['url'], maven_file, maven['sha256'])
    shutil.copyfile(maven_file, destination / 'SOURCES' / 'MavenPro-OFL.txt')
    sources_list.append(f'Source3: MavenPro-OFL.txt')
    checks.append(f'{maven["sha256"]}  MavenPro-OFL.txt')

    template = (PACKAGE / "gxde-display-manager.spec.in").read_text()
    replacements = {
        "@VERSION@": lock["version"],
        "@RELEASE@": str(lock["release"]),
        "@COMMITS@": "\n".join(definitions),
        "@SOURCES@": "\n".join(sources_list),
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    (destination / "SPECS/gxde-display-manager.spec").write_text(template)
    (destination / "SOURCES/sources.sha256").write_text("\n".join(checks) + "\n")
    for name in ("build.sh", "split-files.py"):
        shutil.copyfile(PACKAGE / name, destination / "SOURCES" / name)
    # Fedora PAM files
    for pam in PACKAGE.glob("*.pam"):
        shutil.copyfile(pam, destination / "SOURCES" / pam.name)
    for policy in ("gxdm.te", "gxdm.fc"):
        shutil.copyfile(PACKAGE / policy, destination / "SOURCES" / policy)
    shutil.copyfile(PACKAGE / "0001-systemd-conflict-with-kmscon-vt.patch",
                    destination / "SOURCES/0001-systemd-conflict-with-kmscon-vt.patch")
    shutil.copyfile(PACKAGE / "upstream-lock.json", destination / "SOURCES/upstream-lock.json")


sources.prepare = prepare

if __name__ == '__main__':
    sources.main()
