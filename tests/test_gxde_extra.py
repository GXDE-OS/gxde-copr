import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('gxde_extra_sources', ROOT / 'scripts/gxde-extra-sources.py')
extra = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extra)


class ExtraSourceTests(unittest.TestCase):
    def test_manifest_and_lock_cover_25_aur_packages_and_helpers(self):
        manifest = json.loads((ROOT / 'packages/gxde-extra/manifest.json').read_text())
        lock = json.loads((ROOT / 'packages/gxde-extra/upstream-lock.json').read_text())
        self.assertEqual(27, len(manifest))
        self.assertEqual(25, sum(bool(item['aur']) for item in manifest.values()))
        self.assertEqual(set(manifest), set(lock))
        self.assertEqual('copy', manifest['gxde-downloader-neo']['build'])
        self.assertEqual('qmake6', manifest['gxde-voice-recorder']['build'])

    def test_metapackage_requires_each_aur_application_only(self):
        extra.prepare_meta()
        spec = (ROOT / 'build/gxde-extra-rpmbuild/SPECS/gxde-extra.spec').read_text()
        requires = {line.split(':', 1)[1].strip() for line in spec.splitlines()
                    if line.startswith('Requires:')}
        expected = {name for name, item in extra.MANIFEST.items() if item['aur']}
        self.assertEqual(expected, requires)
        self.assertNotIn('gio-qt6', requires)
        self.assertNotIn('libimagevisualresult6', requires)

    def test_released_tag_move_is_rejected(self):
        previous = {'tag': '1.2.3', 'commit': 'a' * 40, 'version': '1.2.3',
                    'release': 1, 'sha256': 'b' * 64}
        refs = 'c' * 40 + '\trefs/tags/1.2.3\n'
        with mock.patch.object(extra.subprocess, 'check_output', return_value=refs):
            with self.assertRaisesRegex(ValueError, 'released tag moved'):
                extra.resolve_one('gxde-calculator', extra.MANIFEST['gxde-calculator'], previous)

    def test_released_tag_rollback_is_rejected(self):
        previous = {'tag': '1.2.4', 'commit': 'a' * 40, 'version': '1.2.4',
                    'release': 1, 'sha256': 'b' * 64}
        refs = 'c' * 40 + '\trefs/tags/1.2.3\n'
        with mock.patch.object(extra.subprocess, 'check_output', return_value=refs):
            with self.assertRaisesRegex(ValueError, 'rolled back'):
                extra.resolve_one('gxde-calculator', extra.MANIFEST['gxde-calculator'], previous)

    def test_unchanged_tag_preserves_release(self):
        previous = {'tag': '1.2.3', 'commit': 'a' * 40, 'version': '1.2.3',
                    'release': 3, 'sha256': 'b' * 64}
        refs = 'a' * 40 + '\trefs/tags/1.2.3\n'
        with mock.patch.object(extra.subprocess, 'check_output', return_value=refs):
            with mock.patch.object(extra.sources, 'download', return_value='b' * 64):
                _, item = extra.resolve_one('gxde-calculator', extra.MANIFEST['gxde-calculator'], previous)
        self.assertEqual(3, item['release'])

    def test_music_missing_header_patch_is_registered(self):
        patches = extra.PACKAGE_PATCHES[('gxde-music', '4.0.2')]
        self.assertEqual(['gxde-music-4.0.2-add-missing-ui-theme-token.patch'], patches)
        patch = ROOT / 'packages/gxde-extra' / patches[0]
        self.assertTrue(patch.is_file())
        self.assertIn('src/music-player/view/uithemetoken.h', patch.read_text())
        template = (ROOT / 'packages/gxde-extra/extra.spec.in').read_text()
        self.assertIn('@PATCHES@', template)
        self.assertIn('@PREP_PATCHES@', template)


if __name__ == '__main__':
    unittest.main()
