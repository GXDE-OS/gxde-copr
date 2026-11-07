import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_dtk5 import load

infra = load('infra_sources', 'scripts/infra-sources.py')
split = load('infra_split', 'packages/gxde-infra/split-files.py')


class Infra(unittest.TestCase):
    def test_arch_release_preferred_and_annotated_tag_peeled(self):
        refs = ('a refs/tags/4.0.6-2\n'
                'b refs/tags/4.0.6-gxde2\n'
                'c refs/tags/4.0.6-arch1\n'
                'd refs/tags/4.0.6-arch1^{}\n')
        self.assertEqual(infra.latest_tag(refs), ('4.0.6-arch1', 'd'))
        self.assertEqual(infra.rpm_version('2026.10.12'), '2026.10.12')
        self.assertEqual(infra.rpm_version('0.9.3+16.04.20160218-arch1'),
                         '0.9.3.16.04.20160218.1')

    def test_no_unlisted_head_fallback(self):
        with self.assertRaises(ValueError):
            infra.latest_tag('a refs/heads/master')

    def test_split_keeps_protocols_and_sdk_files_in_devel(self):
        libdir = '/usr/lib64'
        self.assertEqual(split.category('/usr/share/treeland-protocols/a.xml', libdir), 'devel')
        self.assertEqual(split.category('/usr/lib64/libudisks2-qt6.so', libdir), 'devel')
        self.assertEqual(split.category('/usr/lib64/libudisks2-qt6.so.1', libdir), 'runtime')
        self.assertEqual(split.category('/usr/libexec/xdg-desktop-portal-gxde', libdir), 'runtime')

    def test_polkit_compat_owns_parent_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'root'
            policy = root / 'var/lib/polkit-1/localauthority/10-vendor.d/gxde.pkla'
            policy.parent.mkdir(parents=True)
            policy.write_text('[GXDE]\n')
            sdk = root / 'usr/lib64/libtest.so'
            sdk.parent.mkdir(parents=True)
            sdk.write_text('')
            subprocess.run([sys.executable, str(infra.sources.ROOT / 'packages/gxde-infra/split-files.py'),
                            str(root), '/usr/lib64'], cwd=tmp, check=True)
            runtime = (Path(tmp) / 'runtime.files').read_text()
            self.assertIn('"/var/lib/polkit-1/localauthority/10-vendor.d/gxde.pkla"', runtime)
            self.assertNotIn('%dir "/var/lib/polkit-1', runtime)

    def test_prepared_spec_pins_all_sources(self):
        lock = json.loads((infra.sources.PACKAGE / 'upstream-lock.json').read_text())
        self.assertEqual(len(lock['components']), 16)
        self.assertEqual(lock['components']['deepin-keyring']['tag'], 'branch:master')
        with tempfile.TemporaryDirectory() as tmp, patch.object(infra.sources, 'download'):
            infra.prepare(lock, Path(tmp))
            spec = (Path(tmp) / 'SPECS/gxde-infra.spec').read_text()
            self.assertIn(f'Version:        {lock["version"]}', spec)
            self.assertIn('treeland-protocols/tar.gz/', spec)
            self.assertIn('Source24:       gxde-k9.tmpfiles.conf', spec)
            self.assertIn("sed -i '/^export .*QT_QPA_PLATFORM=/d'", spec)
            self.assertIn("! grep -Eq '^export .*QT_QPA_PLATFORM='", spec)
            self.assertIn("XDG_CURRENT_DESKTOP=KDE", spec)
            self.assertIn("XDG_CURRENT_DESKTOP=GXDE", spec)
            self.assertIn("*:GXDE:*|*:Deepin:*|*:deepin:*|*:gxde-flakewm:*)", spec)


if __name__ == '__main__':
    unittest.main()
