import pathlib
import tempfile
import unittest
from app.worker import safe_path, execute

class WorkspaceSecurityTests(unittest.TestCase):
    def test_parent_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                safe_path(pathlib.Path(d), '../outside')
    def test_absolute_paths_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                safe_path(pathlib.Path(d), '/etc/passwd')
    def test_git_access_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                safe_path(pathlib.Path(d), '.git/config')
    def test_symlink_escape_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d)
            (root/'outside').symlink_to('/etc')
            with self.assertRaises(ValueError):
                safe_path(root, 'outside/passwd')
    def test_file_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d)
            self.assertIn('Wrote',execute(root,'write_file',{'path':'src/main.py','content':'print(1)'}))
            self.assertEqual(execute(root,'read_file',{'path':'src/main.py'}),'print(1)')
    def test_unknown_command_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIn('blocked',execute(pathlib.Path(d),'run_command',{'command':'curl https://example.com'}).lower())

if __name__=='__main__':
    unittest.main()
