import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_dtk5 import load

gxdm = load('gxdm_sources', 'scripts/gxde-display-manager-sources.py')


class Tags(unittest.TestCase):
    def test_gxde_suffix_preferred(self):
        refs = ('a refs/tags/1.3.2-gxde1\n'
                'b refs/tags/1.3.2-gxde1^{}\n'
                'c refs/tags/1.3.2-gxde2\n'
                'd refs/tags/1.3.2-gxde2^{}\n')
        self.assertEqual(gxdm.latest_tag(refs), ('1.3.2-gxde2', 'd'))

    def test_rpm_version_gxde_suffix(self):
        self.assertEqual(gxdm.rpm_version('1.3.2-gxde2'), '1.3.2.gxde2')
        self.assertEqual(gxdm.rpm_version('1.0.0-gxde1'), '1.0.0.gxde1')

    def test_no_head_fallback(self):
        with self.assertRaises(ValueError):
            gxdm.latest_tag('a refs/heads/main')

    def test_moved_tag_rejected(self):
        old = {"components": {"gxde-display-manager": {"tag": "1.3.2-gxde2", "commit": "old"}}}
        with patch.object(gxdm.sources.subprocess, "check_output",
                          return_value="new refs/tags/1.3.2-gxde2"):
            with self.assertRaisesRegex(ValueError, "moved"):
                gxdm.resolve(old, Path("unused"))

    def test_rollback_rejected(self):
        old = {"components": {"gxde-display-manager": {"tag": "1.3.2-gxde2", "commit": "old"}}}
        with patch.object(gxdm.sources.subprocess, "check_output",
                          return_value="new refs/tags/1.0.0-gxde1"):
            with self.assertRaisesRegex(ValueError, "rollback"):
                gxdm.resolve(old, Path("unused"))

    def test_module_count(self):
        self.assertEqual(len(gxdm.sources.MODULES), 2)

    def test_mavenpro_commit_fixed(self):
        self.assertEqual(gxdm.MAVENPRO_COMMIT,
                         '1c21ee500b7b87a4871696519fc84107a1a001df')
        self.assertEqual(gxdm.MAVENPRO_SHA256,
                         'e0cde1a4993ed689d463d5e2401f4a60c54cc48a14253ab0f8012d722c417038')


class Prepare(unittest.TestCase):
    def test_lock_has_three_components(self):
        lock = json.loads((gxdm.sources.PACKAGE / 'upstream-lock.json').read_text())
        self.assertEqual(len(lock['components']), 3)
        self.assertEqual(lock['components']['gxde-display-manager']['tag'], '1.3.6-gxde6')
        self.assertEqual(lock['components']['gxdm-emergency-mode']['tag'], '1.0.0-gxde2')
        self.assertEqual(lock['components']['MavenPro-OFL']['commit'],
                         '1c21ee500b7b87a4871696519fc84107a1a001df')

    def test_prepared_spec_has_fedora_pam_sources(self):
        lock = json.loads((gxdm.sources.PACKAGE / 'upstream-lock.json').read_text())

        def fake_vendor(src_dir, tarball):
            tarball.write_bytes(b'vendored')

        def fake_download(url, path, expected=None):
            # Create a valid (empty) tar.gz for the emergency-mode source so
            # prepare() can extract it before calling the mocked _cargo_vendor.
            import io, tarfile
            commit = lock['components']['gxdm-emergency-mode']['commit']
            if 'gxdm-emergency-mode' in str(path) and 'vendor' not in str(path):
                buf = io.BytesIO()
                with tarfile.open(fileobj=buf, mode='w:gz') as tar:
                    info = tarfile.TarInfo(name=f'gxdm-emergency-mode-{commit}')
                    info.type = tarfile.DIRTYPE
                    info.mode = 0o755
                    tar.addfile(info)
                Path(path).write_bytes(buf.getvalue())
            else:
                Path(path).write_bytes(b'downloaded')
            return expected or 'fake'

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(gxdm.sources, 'download', side_effect=fake_download), \
             patch.object(gxdm, '_cargo_vendor', side_effect=fake_vendor):
            gxdm.prepare(lock, Path(tmp))
            spec = (Path(tmp) / 'SPECS/gxde-display-manager.spec').read_text()
            self.assertIn(f'Version:        {lock["version"]}', spec)
            # Two module sources + vendor tarball + MavenPro OFL.
            for i in range(2):
                self.assertIn(f'Source{i}:', spec)
            self.assertIn('Source2: gxdm-emergency-mode-vendor.tar.gz', spec)
            self.assertIn('Source3: MavenPro-OFL.txt', spec)
            # Fedora PAM files.
            for pam in ('gxdm.pam', 'gxdm-autologin.pam',
                        'gxdm-greeter.pam', 'gxdm-rescue.pam'):
                self.assertIn(pam, spec, f'{pam} missing from spec')
            self.assertIn('Source14:       gxdm.te', spec)
            self.assertIn('Source15:       gxdm.fc', spec)
            self.assertIn('Patch0:         0001-systemd-conflict-with-kmscon-vt.patch', spec)
            self.assertIn('%patch -P 0 -p1', spec)
            self.assertIn('%package selinux', spec)
            self.assertIn('%selinux_modules_install', spec)
            self.assertIn('%selinux_modules_install -s %{selinuxtype} %{_datadir}', spec)
            self.assertTrue((Path(tmp) / 'SOURCES/gxdm.te').exists())
            self.assertTrue((Path(tmp) / 'SOURCES/gxdm.fc').exists())
            self.assertTrue((Path(tmp) / 'SOURCES/0001-systemd-conflict-with-kmscon-vt.patch').exists())
            self.assertIn('kmsconvt@tty1.service', spec)
            # PAM install disabled in cmake (build.sh, not spec).
            build_sh = (gxdm.sources.PACKAGE / 'build.sh').read_text()
            self.assertIn('INSTALL_PAM_CONFIGURATION=OFF', build_sh)
            # No devel subpackage (gxdm has no .so/.pc/.cmake devel files).
            self.assertNotIn('%package devel', spec)
            self.assertNotIn('%files devel', spec)
            # sha256 check file.
            self.assertTrue((Path(tmp) / 'SOURCES/sources.sha256').exists())


if __name__ == '__main__':
    unittest.main()
