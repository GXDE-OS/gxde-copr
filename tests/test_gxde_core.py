import json
import re
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_dtk5 import load

core = load('gxde_core_sources', 'scripts/gxde-core-sources.py')
split = load('gxde_core_split', 'packages/gxde-core/split-files.py')


def fake_download(url, path, expected=None):
    """Create a minimal real tarball whose top dir mimics codeload naming."""
    top = Path(path).name[:-len('.tar.gz')]
    with tarfile.open(path, 'w:gz') as tar:
        info = tarfile.TarInfo(top + '/')
        info.type = tarfile.DIRTYPE
        tar.addfile(info)
    return 'digest'


def renamed_download(rename):
    """fake_download variant: simulate an upstream repo rename for one module."""
    def _download(url, path, expected=None):
        top = Path(path).name[:-len('.tar.gz')]
        if top.startswith(rename + '-'):
            top = rename + '-old-' + top[len(rename) + 1:]
        with tarfile.open(path, 'w:gz') as tar:
            info = tarfile.TarInfo(top + '/')
            info.type = tarfile.DIRTYPE
            tar.addfile(info)
        return 'digest'
    return _download


class Tags(unittest.TestCase):
    def test_arch_release_preferred_and_annotated_tag_peeled(self):
        refs = ('a refs/tags/6.0.24\n'
                'b refs/tags/6.0.24-arch1\n'
                'c refs/tags/6.0.24-arch1^{}\n'
                'd refs/tags/6.0.24-gxde2\n')
        self.assertEqual(core.latest_tag(refs), ('6.0.24-arch1', 'c'))
        self.assertEqual(core.rpm_version('6.1.2'), '6.1.2')

    def test_gxde_suffix_rpm_version(self):
        self.assertEqual(core.rpm_version('5.2.1-gxde3'), '5.2.1.gxde3')
        self.assertEqual(core.rpm_version('1.0.0-arch1'), '1.0.0.1')
        self.assertEqual(core.rpm_version('0.4.3-arch1'), '0.4.3.1')

    def test_no_unlisted_head_fallback(self):
        with self.assertRaises(ValueError):
            core.latest_tag('a refs/heads/main')

    def test_branch_map_covers_aur_modules(self):
        self.assertEqual(core.BRANCH['gxde-sni-server'], 'main')
        self.assertEqual(core.BRANCH['gxde-top-panel-plugins'], 'd20')
        self.assertEqual(core.BRANCH['gxde-file-manager'], 'char/qt6_migration')
        self.assertEqual(core.BRANCH['gxde-terminal'], 'dtk6')
        self.assertEqual(core.BRANCH['rofd'], 'main')

    def test_module_count_matches_aur_minus_shell_tools(self):
        # AUR _mods has 43 entries plus gxde-network-utils-qt6 and the new
        # wallpaper chooser; gxde-shell-tools (packaging only) is dropped.
        self.assertEqual(len(core.MODULES), 44)
        self.assertEqual(len(set(core.MODULES)), 44)
        self.assertNotIn('gxde-bernese', core.MODULES)
        self.assertIn('gxde-wallpaper-chooser', core.MODULES)

    def test_meta_version_follows_control_center(self):
        self.assertEqual(core.META_NAME, 'gxde-core')
        self.assertEqual(core.META_VERSION_FROM, 'gxde-control-center')

    def test_non_branch_rollback_rejected(self):
        old = {"components": {"gxde-control-center": {"tag": "6.1.2", "commit": "old"}}}
        with patch.object(core.sources.subprocess, "check_output",
                          return_value="new refs/tags/6.0.0"), \
             patch.object(core, "describe_branch_tag", return_value=("0.0.1", "fake")), \
             patch.object(core.sources, "download", return_value="digest"):
            with self.assertRaisesRegex(ValueError, "rollback"):
                core.resolve(old, Path("unused"))

    def test_non_branch_moved_tag_rejected(self):
        old = {"components": {"gxde-control-center": {"tag": "6.1.2", "commit": "old"}}}
        with patch.object(core.sources.subprocess, "check_output",
                          return_value="new refs/tags/6.1.2"), \
             patch.object(core, "describe_branch_tag", return_value=("0.0.1", "fake")), \
             patch.object(core.sources, "download", return_value="digest"):
            with self.assertRaisesRegex(ValueError, "moved"):
                core.resolve(old, Path("unused"))


class Groups(unittest.TestCase):
    def test_groups_partition_modules(self):
        seen = [m for g in core.GROUPS.values() for m in g['modules']]
        self.assertEqual(len(seen), len(set(seen)), 'module in two groups')
        self.assertEqual(set(seen), set(core.MODULES))
        self.assertEqual(len(core.GROUPS), 17)

    def test_version_from_in_group_and_script_exists(self):
        for name, group in core.GROUPS.items():
            self.assertIn(group['version_from'], group['modules'], name)
            self.assertTrue((core.PACKAGE / 'groups' / f'{name}.sh').exists(), name)

    def test_lock_has_group_metadata(self):
        lock = json.loads((core.PACKAGE / 'upstream-lock.json').read_text())
        self.assertEqual(len(lock['components']), 44)
        self.assertEqual(len(lock['groups']), 18)  # 17 groups + metapackage
        for name, group in core.GROUPS.items():
            entry = lock['groups'][name]
            self.assertEqual(sorted(entry['commits']), sorted(group['modules']), name)
        # Branch-pinned modules must record their branch.
        for name in ('gxde-sni-server', 'gxde-top-panel-plugins',
                     'gxde-file-manager', 'gxde-terminal', 'rofd'):
            self.assertEqual(lock['components'][name].get('branch'),
                             core.BRANCH[name], f'{name} branch mismatch')


class Split(unittest.TestCase):
    def test_devel_files_separated_from_runtime(self):
        libdir = '/usr/lib64'
        self.assertEqual(split.category('/usr/include/gxde-dock/dock.h', libdir), 'devel')
        self.assertEqual(split.category('/usr/lib64/libgxde-dock.so', libdir), 'devel')
        self.assertEqual(split.category('/usr/lib64/cmake/gxde-dock/gxde-dockConfig.cmake', libdir), 'devel')
        self.assertEqual(split.category('/usr/lib64/pkgconfig/gxde-dock.pc', libdir), 'devel')
        self.assertEqual(split.category('/usr/lib64/libgxde-dock.so.1', libdir), 'runtime')
        self.assertEqual(split.category('/usr/bin/gxde-dock', libdir), 'runtime')
        self.assertEqual(split.category('/usr/share/icons/gxde/apps/48/test.png', libdir), 'runtime')
        self.assertEqual(split.category('/usr/lib64/librofd_ffi.so', libdir), 'devel')
        self.assertEqual(split.category('/usr/lib64/librofd_ffi.so.0.4.3', libdir), 'runtime')

    def test_static_libs_and_prl_are_devel(self):
        libdir = '/usr/lib64'
        self.assertEqual(split.category('/usr/lib64/libtest.a', libdir), 'devel')
        self.assertEqual(split.category('/usr/lib64/libtest.prl', libdir), 'devel')

    def test_plugin_so_in_subdirs_are_runtime(self):
        libdir = '/usr/lib64'
        self.assertEqual(
            split.category('/usr/lib64/gtk-3.0/modules/libappmenu-gtk-module-wayland.so', libdir),
            'runtime')
        self.assertEqual(
            split.category('/usr/lib64/qt6/plugins/styles/libdstyleplugin.so', libdir),
            'runtime')
        self.assertEqual(
            split.category('/usr/lib64/gxde-dock/plugins/libtray.so', libdir),
            'runtime')
        # devel symlink directly in libdir stays devel
        self.assertEqual(split.category('/usr/lib64/libtest.so', libdir), 'devel')


class Prepare(unittest.TestCase):
    def _prepare(self, group, tmp, download=fake_download):
        lock = json.loads((core.PACKAGE / 'upstream-lock.json').read_text())
        with patch.object(core.sources, 'download', side_effect=download):
            core.prepare_group(group, lock, Path(tmp))
        return lock, (Path(tmp) / f'SPECS/{group}.spec').read_text()

    def test_prepared_spec_pins_group_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock, spec = self._prepare('gxde-libs', tmp)
            glock = lock['groups']['gxde-libs']
            self.assertIn(f'Version:        {glock["version"]}', spec)
            self.assertIn(f'Release:        {glock["release"]}', spec)
            modules = core.GROUPS['gxde-libs']['modules']
            for i in range(len(modules)):
                self.assertIn(f'Source{i}:', spec)
            self.assertNotIn(f'Source{len(modules)}:', spec)
            setup_line = next(line for line in spec.splitlines()
                              if line.startswith('%setup'))
            self.assertEqual(len(re.findall(r'-a \d+', setup_line)), len(modules))
            self.assertEqual(len(re.findall(r'^mv ', spec, re.MULTILINE)), len(modules))
            self.assertTrue((Path(tmp) / 'SOURCES/sources.sha256').exists())
            self.assertTrue((Path(tmp) / 'SOURCES/common.sh').exists())
            self.assertTrue((Path(tmp) / 'SOURCES/split-files.py').exists())
            # Group build script becomes SOURCES/build.sh
            build_sh = (Path(tmp) / 'SOURCES/build.sh').read_text()
            self.assertIn('gxde-network-utils-qt6', build_sh)
            # devel subpackage declared for devel groups, with macro-based
            # Requires so %{?dist} is included (exact-version match)
            self.assertIn('%package devel', spec)
            self.assertIn('Requires:       gxde-libs%{?_isa} = %{version}-%{release}', spec)
            self.assertIn('%files devel -f devel.files', spec)

    def test_codeload_repo_rename_derives_mv_from_tarball(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock, spec = self._prepare(
                'gxde-installer', tmp,
                download=renamed_download('deepin-installer-reborn'))
            self.assertIn('mv deepin-installer-reborn-old-', spec)
            self.assertRegex(spec, r'mv deepin-installer-reborn-old-[0-9a-f]{40} deepin-installer-reborn')

    def test_non_devel_group_has_no_devel_subpackage(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, spec = self._prepare('gxde-artwork', tmp)
            self.assertNotIn('%package devel', spec)
            self.assertIn('%global debug_package %{nil}', spec)

    def test_tools_and_scriptlets_land_in_right_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, spec = self._prepare('gxde-daemon', tmp)
            self.assertIn('Source105:      deepin-policy-ts-convert', spec)
            self.assertIn('%post', spec)
            self.assertIn('update-gtk-settings', spec)
            self.assertIn('BuildRequires:  golang', spec)
            self.assertTrue((Path(tmp) / 'SOURCES/deepin-policy-ts-convert').exists())
        with tempfile.TemporaryDirectory() as tmp:
            _, spec = self._prepare('gxde-session-ui', tmp)
            self.assertIn('Source106:      deepin-desktop-ts-convert', spec)
            self.assertIn('perl-XML-LibXML', spec)

    def test_prepared_specs_have_copr_build_requires(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, dock = self._prepare('gxde-dock', tmp)
            for dep in ('gxde-dtk5-devel', 'gxde-dtk6-devel', 'gxde-dtk2-qt6-devel',
                        'gxde-infra-devel', 'gxde-libs-devel', 'layer-shell-qt-devel'):
                self.assertIn(dep, dock, f'{dep} missing from gxde-dock BuildRequires')
        with tempfile.TemporaryDirectory() as tmp:
            _, search = self._prepare('gxde-search', tmp)
            for dep in ('lucene++-devel', 'gxde-app-management-devel',
                        'gxde-file-manager-devel'):
                self.assertIn(dep, search, f'{dep} missing from gxde-search BuildRequires')
        for group in ('gxde-top-panel', 'gxde-control-center', 'gxde-file-manager'):
            with tempfile.TemporaryDirectory() as tmp:
                _, generated = self._prepare(group, tmp)
            self.assertIn('gxde-bernese-devel', generated, group)

    def test_wallpaper_chooser_is_a_separate_core_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, generated = self._prepare('gxde-wallpaper-chooser', tmp)
            build_sh = (Path(tmp) / 'SOURCES/build.sh').read_text()
        self.assertIn('Requires:       gxde-file-manager gxde-control-center', generated)
        self.assertIn('Provides:       gxde-wallpaper', generated)
        self.assertIn('qt6-qtmultimedia-devel', generated)
        self.assertIn('_cmake gxde-wallpaper-chooser', build_sh)

    def test_file_manager_strips_bogus_pc_requires(self):
        # util-dfm's dfm6-search.pc lists CMake target names (Boostsystem,
        # Threads) in Requires:; rpm6 ignores %global __requires_exclude, so
        # the group build script must rewrite the staged .pc files instead.
        with tempfile.TemporaryDirectory() as tmp:
            lock, spec = self._prepare('gxde-file-manager', tmp)
            self.assertNotIn('__requires_exclude', spec)
            self.assertIn('gxde-compressor-devel', spec)
            build_sh = (Path(tmp) / 'SOURCES/build.sh').read_text()
            self.assertIn('Boostsystem', build_sh)
            self.assertIn("find \"$stage\" -name '*.pc'", build_sh)

    def test_meta_spec_requires_all_groups(self):
        lock = json.loads((core.PACKAGE / 'upstream-lock.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            core.prepare_meta(lock, Path(tmp))
            spec = (Path(tmp) / 'SPECS/gxde-core.spec').read_text()
        for name in core.GROUPS:
            self.assertRegex(spec, rf'Requires:.*\b{name}\b', f'{name} missing from meta')
        self.assertIn('BuildArch:      noarch', spec)
        # rpm6 silently skips binary packaging without a %files section.
        self.assertRegex(spec, r'(?m)^%files\s*$')
        meta = lock['groups']['gxde-core']
        self.assertIn(f'Version:        {meta["version"]}', spec)


if __name__ == '__main__':
    unittest.main()
