#!/usr/bin/env python3
"""Exercise the production setupUserHome without starting a Darling container."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ('Documents', 'Desktop', 'Downloads', 'Movies', 'Music', 'Pictures', 'Public')


def snapshot_home(home):
    entries = {}
    for directory, dirs, files in os.walk(home, followlinks=False):
        for path in [Path(directory), *(Path(directory) / name for name in dirs + files)]:
            st = path.lstat()
            entries[str(path.relative_to(home))] = (
                st.st_mode, st.st_ino, st.st_mtime_ns,
                os.readlink(path) if path.is_symlink() else None,
            )
    return entries

class HomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = Path(tempfile.mkdtemp(prefix='isolated-home-test-'))
        text = (ROOT / 'src/darlingserver.cpp').read_text()
        function = text[text.index('void setupUserHome('):text.index('void setupCoredumpPattern(')]
        helper = '#include "isolated-home.hpp"\n' if (ROOT / 'src/isolated-home.hpp').exists() else ''
        source = cls.work / 'driver.cpp'
        source.write_text('''#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cerrno>
#include <unistd.h>
#include <sys/stat.h>
#include <pwd.h>
''' + helper + '''
const char* xdgDirectory(const char*) { return "/host-test-folder"; }
''' + function + '''
int main(int argc, char** argv) {
 if (argc != 2) return 2;
 setupUserHome(argv[1], getuid());
 return 0;
}
''')
        cls.driver = cls.work / 'driver'
        subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-Wall', '-Wextra', '-Werror',
                        '-Wno-sign-compare', '-I', str(ROOT / 'src'), str(source),
                        '-o', str(cls.driver)], check=True)
        import pwd
        cls.login = pwd.getpwuid(os.getuid()).pw_name

    def setUp(self):
        self.prefix = Path(tempfile.mkdtemp(dir=self.work, prefix='prefix-'))
        self.home = self.prefix / 'Users' / self.login

    def run_setup(self, value='1', success=True):
        env = os.environ.copy()
        env.pop('DARLING_ISOLATED_HOME', None)
        if value is not None:
            env['DARLING_ISOLATED_HOME'] = value
        result = subprocess.run([str(self.driver), str(self.prefix)], env=env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stderr)

    def test_isolated_directories_persist(self):
        self.run_setup()
        for folder in FOLDERS:
            path = self.home / folder
            self.assertFalse(path.is_symlink(), str(path))
            self.assertTrue(path.is_dir(), str(path))
            (path / 'marker').write_text('prefix only')
        self.assertFalse((self.home / 'LinuxHome').exists())
        self.run_setup()
        for folder in FOLDERS:
            self.assertEqual((self.home / folder / 'marker').read_text(), 'prefix only')

    def test_default_and_non_one_values_keep_host_links(self):
        for value in (None, '', '0', 'true', '01'):
            with self.subTest(value=value):
                self.setUp()
                self.run_setup(value)
                for folder in FOLDERS:
                    self.assertTrue((self.home / folder).is_symlink())
                self.assertTrue((self.home / 'LinuxHome').is_symlink())

    def test_existing_shared_prefix_is_refused_without_mutation(self):
        self.run_setup(None)
        before = snapshot_home(self.home)
        self.run_setup(success=False)
        self.assertEqual(snapshot_home(self.home), before)

    def test_symlink_parent_is_refused(self):
        outside = self.prefix / 'outside'
        outside.mkdir()
        (self.prefix / 'Users').symlink_to(outside)
        self.run_setup(success=False)
        self.assertTrue((self.prefix / 'Users').is_symlink())
        self.assertEqual(list(outside.iterdir()), [])

    def test_regular_file_is_preserved(self):
        self.home.mkdir(parents=True)
        (self.home / 'Documents').write_text('keep')
        self.run_setup(success=False)
        self.assertEqual((self.home / 'Documents').read_text(), 'keep')

if __name__ == '__main__':
    unittest.main()
