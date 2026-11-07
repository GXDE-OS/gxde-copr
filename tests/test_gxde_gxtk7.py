import importlib.util
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'gxde_gxtk7_sources', ROOT / 'scripts/gxde-gxtk7-sources.py')
gxtk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gxtk)


def fake_download(url, path, expected=None):
    path = Path(path)
    top = path.name.removesuffix('.tar.gz')
    with tarfile.open(path, 'w:gz') as tar:
        info = tarfile.TarInfo(top + '/')
        info.type = tarfile.DIRTYPE
        tar.addfile(info)
    return expected or 'digest'


class GXTK7Sources(unittest.TestCase):
    def test_lock_contains_both_release_components(self):
        lock = json.loads(gxtk.LOCK_PATH.read_text())
        self.assertEqual({'gxde-bernese', 'gxde-gxtk7'}, set(lock))
        self.assertEqual('1.0.3-gxde5', lock['gxde-bernese']['tag'])
        self.assertEqual('0.1.1-3', lock['gxde-gxtk7']['tag'])

    def test_prepared_specs_pin_sources_and_dependency_order(self):
        lock = json.loads(gxtk.LOCK_PATH.read_text())
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(gxtk, 'ROOT', Path(tmp)), \
             patch.object(gxtk.sources, 'download', side_effect=fake_download):
            for name in gxtk.PACKAGES:
                gxtk.prepare_one(name, lock)
            bernese = (Path(tmp) / 'build/gxde-bernese-rpmbuild/SPECS/gxde-bernese.spec').read_text()
            style = (Path(tmp) / 'build/gxde-gxtk7-rpmbuild/SPECS/gxde-gxtk7.spec').read_text()
        self.assertIn(f'Version:        {lock["gxde-bernese"]["version"]}', bernese)
        self.assertIn('qt6-qtbase-private-devel', bernese)
        self.assertIn('BuildRequires:  gxde-bernese-devel', style)
        self.assertIn('-DGXTK7_BUILD_EXAMPLES=OFF', style)

    def test_moved_tag_is_rejected(self):
        previous = {'tag': '1.0.0', 'commit': 'a' * 40, 'version': '1.0.0',
                    'release': 1, 'sha256': 'b' * 64}
        with patch.object(gxtk.subprocess, 'check_output',
                          return_value='c' * 40 + '\trefs/tags/1.0.0\n'):
            with self.assertRaisesRegex(ValueError, 'released tag moved'):
                gxtk.resolve_one('gxde-bernese', gxtk.PACKAGES['gxde-bernese'],
                                 previous, Path('unused'))


if __name__ == '__main__':
    unittest.main()
