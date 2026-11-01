import os
import tempfile
from pathlib import Path
from app import core
import unittest
from unittest.mock import patch
from app import github_settings as settings

class GitHubSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.patch=patch.dict(os.environ,{'GITHUB_ALLOWED_REPOS':'NekoSuneVR/TriAgent-Studio,TestOwner/TestRepo'})
        self.patch.start()
        self.root_patch=patch.object(core,'ROOT',Path(self.temp.name))
        self.db_patch=patch.object(core,'DB',Path(self.temp.name)/'tasks.sqlite3')
        self.root_patch.start()
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.root_patch.stop()
        self.patch.stop()
        self.temp.cleanup()

    def test_boolean_setting_persists(self):
        settings.update({'review_prs':True,'poll_seconds':240})
        self.assertTrue(settings.enabled('review_prs'))
        self.assertEqual(settings.get('poll_seconds'),'240')
        self.assertFalse(settings.enabled('autopublish'))

    def test_reject_repo_not_allowlisted(self):
        with self.assertRaises(ValueError):
            settings.update({'monitor_repo':'attacker/repo'})

    def test_reject_unknown_keys_and_invalid_values(self):
        for changes in ({'GITHUB_APP_PRIVATE_KEY':'secret'}, {'autopublish':'true'}, {'poll_seconds':5}, {'monitor_repo':'../../etc'}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):settings.update(changes)

    def test_settings_are_atomic(self):
        with self.assertRaises(ValueError):
            settings.update({'review_prs':True,'monitor_repo':'other/notallowed'})
        self.assertFalse(settings.enabled('review_prs'))

if __name__=='__main__':
    unittest.main()
