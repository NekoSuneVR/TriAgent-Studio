import os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from app import core
from app.providers import config

class SharedProviderTests(unittest.TestCase):
    def test_shared_omniroute_key_url_and_role_model(self):
        with patch.dict(os.environ,{'AI_PROVIDER':'omniroute','AI_API_URL':'https://omni.example/v1','AI_API_KEY':'test-key','AI_MODEL':'auto/coding:free','BACKEND_MODEL':'auto/coding:reliable'},clear=True):
            self.assertEqual(config('frontend'),('omniroute','https://omni.example/v1','test-key','auto/coding:free'))
            self.assertEqual(config('backend')[-1],'auto/coding:reliable')

class SetupTests(unittest.TestCase):
    def test_setup_is_one_time(self):
        from app.setup import SetupInput,enroll,setup_status
        from fastapi import HTTPException
        class FakeRequest:
            class URL:scheme='https'
            url=URL()
            class Client:host='127.0.0.1'
            client=Client()
            headers={}
        with tempfile.TemporaryDirectory() as tmp, patch.object(core,'ROOT',Path(tmp)),patch.object(core,'DB',Path(tmp)/'test.sqlite3'),patch.dict(os.environ,{'DASHBOARD_PASSWORD_HASH':'','SESSION_SECRET':'','DASHBOARD_SETUP_TOKEN':''}):
            self.assertTrue(setup_status()['setup_required'])
            result=enroll(SetupInput(username='testadmin',password='long-secure-password-123'),FakeRequest())
            self.assertIn('access_token',result)
            self.assertFalse(setup_status()['setup_required'])
            with self.assertRaises(HTTPException) as cm:
                enroll(SetupInput(username='second',password='different-password-123'),FakeRequest())
            self.assertEqual(cm.exception.status_code,409)

if __name__=='__main__':unittest.main()
