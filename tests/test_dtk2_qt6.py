import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_dtk5 import load

sources = load('dtk2_qt6', 'scripts/dtk2-qt6-sources.py').sources
split = load('split2_qt6', 'packages/gxde-dtk2-qt6/split-files.py')


class DTK2Qt6(unittest.TestCase):
    def test_latest_arch_tag_and_annotated_widget_tag(self):
        refs = ('a refs/tags/6.0.1-5\n'
                'b refs/tags/6.0.1-arch1\n'
                'c refs/tags/6.2.3\n'
                'd refs/tags/6.2.3^{}\n')
        self.assertEqual(sources.latest_tag(refs), ('6.2.3', 'd'))
        self.assertEqual(sources.latest_tag(refs.split('c refs/tags')[0]), ('6.0.1-arch1', 'b'))
        self.assertGreater(sources.tag_key('6.0.1-arch1'), sources.tag_key('6.0.1-5'))

    def test_runtime_and_development_split(self):
        libdir, qtdata = '/usr/lib64', '/usr/lib64/qt6'
        self.assertEqual(split.category('/usr/lib64/libdtk2widget.so.6', libdir, qtdata), 'runtime')
        self.assertEqual(split.category('/usr/lib64/qt6/plugins/styles/libdstyleplugin-gxde-qt6.so', libdir, qtdata), 'runtime')
        self.assertEqual(split.category('/usr/lib64/libdtk2widget.so', libdir, qtdata), 'devel')
        self.assertEqual(split.category('/usr/lib64/pkgconfig/dtk2widget.pc', libdir, qtdata), 'devel')

    def test_prepared_sources_are_pinned(self):
        lock = json.loads((sources.PACKAGE / 'upstream-lock.json').read_text())
        with tempfile.TemporaryDirectory() as tmp, patch.object(sources, 'download'):
            sources.prepare(lock, Path(tmp))
            spec = (Path(tmp) / 'SPECS/gxde-dtk2-qt6.spec').read_text()
            self.assertIn(f'Version:        {lock["version"]}', spec)
            integration = lock['components']['gxde-qt6-integration']
            self.assertIn(f'gxde-qt6-integration/tar.gz/{integration["commit"]}', spec)


if __name__ == '__main__':
    unittest.main()
