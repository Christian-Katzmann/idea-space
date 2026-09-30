import concurrent.futures
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/idea_space.py'
spec = importlib.util.spec_from_file_location('store', SCRIPT)
store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)


class Notebook(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'notebook'

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args, ok=True):
        r = subprocess.run([sys.executable, str(SCRIPT), '--root', str(self.root), *args], capture_output=True, text=True)
        self.assertEqual(r.returncode == 0, ok, r.stderr)
        return json.loads(r.stdout) if ok else r.stderr

    def capture(self, thought='First thought'):
        return self.run_cli('capture', '--title', 'Same title', '--thought', thought)['id']

    def test_lifecycle_preserves_original_and_archive_state(self):
        thought = '  æøå\nsecond line\n$(do not execute)  '
        identity = self.capture(thought)
        self.run_cli('append', identity, '--thought', 'New context: zEBra')
        self.assertEqual(self.run_cli('get', identity)['thought'], thought)
        self.assertEqual(len(self.run_cli('find', 'zebra')), 1)
        self.run_cli('archive', identity)
        self.assertEqual(self.run_cli('list'), [])
        self.run_cli('delete', identity)
        self.run_cli('get', identity, ok=False)
        self.run_cli('append', identity, '--thought', 'no', ok=False)
        self.run_cli('restore', identity)
        self.assertEqual(self.run_cli('get', identity)['status'], 'archived')
        self.run_cli('unarchive', identity)
        self.assertEqual(len(self.run_cli('list')), 1)

    def test_purge_is_blocked_until_backup_is_safe(self):
        identity = self.capture()
        backup = Path(self.temp.name) / 'backup.json'
        self.run_cli('purge', identity, '--confirm-id', identity, '--backup', str(backup), ok=False)
        self.run_cli('delete', identity)
        backup.write_text('DO NOT OVERWRITE')
        self.run_cli('purge', identity, '--confirm-id', identity, '--backup', str(backup), ok=False)
        self.assertEqual(backup.read_text(), 'DO NOT OVERWRITE')
        self.assertEqual(self.run_cli('get', identity, '--include-deleted')['status'], 'deleted')
        backup.unlink()
        self.run_cli('purge', identity, '--confirm-id', 'wrong', '--backup', str(backup), ok=False)
        self.run_cli('purge', identity, '--confirm-id', identity, '--backup', str(backup))
        self.assertEqual(json.loads(backup.read_text())['ideas'][0]['id'], identity)
        self.run_cli('get', identity, '--include-deleted', ok=False)
        self.run_cli('import-backup', str(backup))
        self.run_cli('restore', identity)
        self.assertEqual(self.run_cli('get', identity)['thought'], 'First thought')

    def test_backup_roundtrip_and_conflict_roll_back_whole_import(self):
        first = self.capture('one')
        second = self.capture('two')
        self.run_cli('append', first, '--thought', 'addition')
        target = Path(self.temp.name) / 'backup.json'
        self.run_cli('export', '--output', str(target))
        self.assertEqual(self.run_cli('import-backup', str(target))['already_present'], 2)
        original = json.loads(target.read_text())
        self.root = Path(self.temp.name) / 'restored'
        self.run_cli('import-backup', str(target))
        self.assertEqual(self.run_cli('get', first), original['ideas'][0])
        tampered = json.loads(target.read_text())
        tampered['ideas'][0]['id'] = 'f' * 32
        tampered['ideas'][1]['thought'] = 'conflict'
        target.write_text(json.dumps(tampered))
        self.run_cli('import-backup', str(target), ok=False)
        self.assertEqual(len(self.run_cli('list')), 2)
        self.assertEqual(self.run_cli('get', second)['thought'], 'two')

    def test_exports_and_legacy_import_are_non_destructive(self):
        legacy = Path(self.temp.name) / 'legacy'
        legacy.mkdir()
        original = '# Old idea\n\nUnstructured original text\n'
        (legacy / 'idea.md').write_text(original)
        self.run_cli('import-legacy', str(legacy))
        self.assertEqual(self.run_cli('import-legacy', str(legacy))['already_imported'], 1)
        self.assertEqual((legacy / 'idea.md').read_text(), original)
        dest = Path(self.temp.name) / 'all.json'
        self.run_cli('export', '--output', str(dest))
        self.assertEqual(json.loads(dest.read_text())['ideas'][0]['thought'], original)
        before = dest.read_bytes()
        self.run_cli('export', '--output', str(dest), ok=False)
        self.assertEqual(dest.read_bytes(), before)
        md = Path(self.temp.name) / 'all.md'
        self.run_cli('export', '--format', 'markdown', '--output', str(md))
        self.assertIn(original, md.read_text())

    def test_concurrent_capture_and_append(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            ids = list(pool.map(lambda i: self.capture(str(i)), range(12)))
        self.assertEqual(len(set(ids)), 12)
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda i: self.run_cli('append', ids[0], '--thought', str(i)), range(12)))
        self.assertEqual(len(self.run_cli('get', ids[0])['additions']), 12)
        self.assertEqual(len(self.run_cli('list')), 12)

    def test_unrecognized_schema_and_symlink_refused(self):
        self.root.mkdir()
        dbpath = self.root / 'ideas.sqlite3'
        db = sqlite3.connect(dbpath)
        db.execute('PRAGMA user_version=42')
        db.close()
        before = dbpath.read_bytes()
        self.run_cli('list', ok=False)
        self.assertEqual(dbpath.read_bytes(), before)
        other = self.root / 'other.db'
        dbpath.rename(other)
        dbpath.symlink_to(other)
        self.run_cli('list', ok=False)
        self.assertEqual(other.read_bytes(), before)

    def test_atomic_export_failure_preserves_destination(self):
        target = Path(self.temp.name) / 'existing'
        target.write_text('original')
        with self.assertRaises(FileExistsError):
            store.exclusive_write(target, 'replacement')
        self.assertEqual(target.read_text(), 'original')
        self.assertFalse(list(target.parent.glob('.idea-export-*')))


if __name__ == '__main__':
    unittest.main()
